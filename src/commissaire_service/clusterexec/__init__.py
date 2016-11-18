# Copyright (C) 2016  Red Hat, Inc
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import json

from commissaire.models import (
    ClusterDeploy, ClusterUpgrade, ClusterRestart, Cluster, Host)
from commissaire.util.date import formatted_dt
from commissaire.util.ssh import TemporarySSHKey

from commissaire_service.oscmd import get_oscmd
from commissaire_service.service import CommissaireService
from commissaire_service.transport import ansibleapi


class ClusterExecService(CommissaireService):
    """
    Executes operations over a cluster by way of remote shell commands.
    """

    def __init__(self, exchange_name, connection_url):
        """
        Creates a new ClusterExecService.

        :param exchange_name: Name of the topic exchange
        :type exchange_name: str
        :param connection_url: Kombu connection URL
        :type connection_url: str
        """
        queue_kwargs = [
            {'routing_key': 'jobs.clusterexec.*'}
        ]
        super().__init__(exchange_name, connection_url, queue_kwargs)

    def _execute(self, message, model_instance, command_args,
                 finished_hosts_key):
        """
        Remotely executes OS-specific shell commands across a cluster.

        :param message: A message instance
        :type message: kombu.message.Message
        :param model_instance: Initial model for the async operation
        :type model_instance: commissaire.models.Model
        :param command_args: Command name + arguments as a tuple
        :type command_args: tuple
        :param finished_hosts_key: Model attribute name for finished hosts
        :type finished_hosts_key: str
        """
        # Split out the command name.
        command_name = command_args[0]
        command_args = command_args[1:]

        end_status = 'finished'

        # XXX We assume the model instance names a cluster.
        #     Note, cluster_name is used in the except clause,
        #     so it must be reliably defined.
        cluster_name = getattr(model_instance, 'name', None)

        try:
            assert cluster_name is not None
            model_json_data = model_instance.to_json()

            # Set the initial status in the store.
            self.logger.info('Setting initial status.')
            self.logger.debug('Status={}'.format(model_json_data))
            params = {
                'model_type_name': model_instance.__class__.__name__,
                'model_json_data': model_json_data
            }
            self.request('storage.save', params=params)

            # Respond to the caller with the initial status.
            if message.properties.get('reply_to'):
                # XXX Have to dig up the message ID again.
                #     CommissaireService.on_message() already
                #     does this, but doesn't pass it to us.
                body = message.body
                if isinstance(body, bytes):
                    body = json.loads(body.decode())
                self.respond(
                    message.properties['reply_to'],
                    body.get('id', -1),
                    model_json_data)
        except Exception as error:
            self.logger.error(
                'Unable to save initial state for "{}" clusterexec due to '
                '{}: {}'.format(cluster_name, type(error), error))
            raise error

        # Collect all host addresses in the cluster.

        try:
            cluster = Cluster.new(name=cluster_name)
            params = {
                'model_type_name': cluster.__class__.__name__,
                'model_json_data': cluster.to_json(),
                'secure': True
            }
            response = self.request('storage.get', params=params)
            cluster = Cluster.new(**response['result'])
        except Exception as error:
            self.logger.warn(
                'Unable to continue for cluster "{}" due to '
                '{}: {}'.format(cluster_name, type(error), error))
            raise error

        n_hosts = len(cluster.hostset)
        if n_hosts:
            self.logger.debug(
                '{} hosts in cluster "{}"'.format(n_hosts, cluster_name))
        else:
            self.logger.warn('No hosts in cluster "{}"'.format(cluster_name))

        for address in cluster.hostset:
            try:
                host = Host.new(address=address)
                params = {
                    'model_type_name': host.__class__.__name__,
                    'model_json_data': host.to_json(),
                    'secure': True
                }
                response = self.request('storage.get', params=params)
                host = Host.new(**response['result'])
            except Exception as error:
                self.logger.warn(
                    'Unable to get host info for "{}" due to '
                    '{}: {}'.format(address, type(error), error))
                raise error

            oscmd = get_oscmd(host.os)

            # os_command is only used for logging
            os_command = getattr(oscmd, command_name)(*command_args)
            self.logger.info('Executing {} on {}...'.format(
                os_command, host.address))

            model_instance.in_process.append(host.address)
            try:
                params = {
                    'model_type_name': model_instance.__class__.__name__,
                    'model_json_data': model_instance.to_json()
                }
                self.request('storage.save', params=params)
            except Exception as error:
                self.logger.error(
                    'Unable to save in_process state for "{}" clusterexec '
                    'due to {}: {}'.format(cluster_name, type(error), error))
                raise error

            with TemporarySSHKey(host, self.logger) as key:
                try:
                    transport = ansibleapi.Transport(host.remote_user)
                    method = getattr(transport, command_name)
                    method(host.address, key.path, oscmd, command_args)
                except Exception as error:
                    # If there was a failure, set the end_status and break.
                    end_status = 'failed'
                    self.logger.error(
                        'Clusterexec {} for {} failed: {}: {}'.format(
                            command_name, host.address, type(error), error))
                    break

            # Set the finished hosts.
            finished_hosts = getattr(model_instance, finished_hosts_key)
            finished_hosts.append(host.address)
            try:
                index = model_instance.in_process.index(host.address)
                model_instance.in_process.pop(index)
            except ValueError:
                self.logger.warn(
                    'Host {} was not in_process for {} {}'.format(
                        host.address, command_name, cluster_name))
            try:
                params = {
                    'model_type_name': model_instance.__class__.__name__,
                    'model_json_data': model_instance.to_json()
                }
                self.request('storage.save', params=params)
            except Exception as error:
                self.logger.error(
                    'Unable to save cluster state for "{}" clusterexec '
                    'due to {}: {}'.format(cluster_name, type(error), error))
                raise error

            self.logger.info(
                'Finished executing {} for {} in {}'.format(
                    command_name, host.address, cluster_name))

        # Final set of command result.

        model_instance.finished_at = formatted_dt()
        model_instance.status = end_status

        self.logger.info(
            'Cluster {} final {} status: {}'.format(
                cluster_name, command_name, model_instance.to_json()))

        try:
            params = {
                'model_type_name': model_instance.__class__.__name__,
                'model_json_data': model_instance.to_json()
            }
            self.request('storage.save', params=params)
        except Exception as error:
            self.logger.error(
                'Unable to save final state for "{}" clusterexec '
                'due to {}: {}'.format(cluster_name, type(error), error))

    def on_upgrade(self, message, cluster_name):
        """
        Executes an upgrade command on hosts across a cluster.

        :param message: A message instance
        :type message: kombu.message.Message
        :param cluster_name: The name of a cluster
        :type cluster_name: str
        """
        self.logger.info(
            'Received message: Upgrade cluster "{}"'.format(cluster_name))
        command_args = ('upgrade',)
        model_instance = ClusterUpgrade.new(
            name=cluster_name,
            status='in_process',
            started_at=formatted_dt(),
            upgraded=[],
            in_process=[]
        )
        self._execute(message, model_instance, command_args, 'upgraded')

    def on_restart(self, message, cluster_name):
        """
        Executes a restart command on hosts across a cluster.

        :param message: A message instance
        :type message: kombu.message.Message
        :param cluster_name: The name of a cluster
        :type cluster_name: str
        """
        self.logger.info(
            'Received message: Restart cluster "{}"'.format(cluster_name))
        command_args = ('restart',)
        model_instance = ClusterRestart.new(
            name=cluster_name,
            status='in_process',
            started_at=formatted_dt(),
            restarted=[],
            in_process=[]
        )
        self._execute(message, model_instance, command_args, 'restarted')

    def on_deploy(self, message, cluster_name, version):
        """
        Executes a deploy command on atomic hosts across a cluster.

        :param message: A message instance
        :type message: kombu.message.Message
        :param cluster_name: The name of a cluster
        :type cluster_name: str
        :param version: The tree image version to deploy
        :type version: str
        """
        self.logger.info(
            'Received message: Deploy version "{}" on cluster "{}"'.format(
                version, cluster_name))
        command_args = ('deploy', version)
        model_instance = ClusterDeploy.new(
            name=cluster_name,
            status='in_process',
            started_at=formatted_dt(),
            version=version,
            deployed=[],
            in_process=[]
        )
        self._execute(message, model_instance, command_args, 'deployed')


def main():  # pragma: no cover
    """
    Main entry point.
    """
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-c', '--config', type=str,
        help='Configuration file to use.')
    parser.add_argument(
        '--bus-exchange', type=str, default='commissaire',
        help='Message bus exchange name.')
    parser.add_argument(
        '--bus-uri', type=str, metavar='BUS_URI',
        default='redis://127.0.0.1:6379/',  # FIXME: Remove before release
        help=(
            'Message bus connection URI. See:'
            'http://kombu.readthedocs.io/en/latest/userguide/connections.html')
    )

    args = parser.parse_args()

    try:
        service = ClusterExecService(
            exchange_name=args.bus_exchange,
            connection_url=args.bus_uri)
        service.run()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':  # pragma: no cover
    main()
