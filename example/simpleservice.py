#!/usr/bin/env python3
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
"""
Example simple service
"""

import logging

from commissaire_service.service import CommissaireService, ServiceManager

# NOTE: Only these logging sections are added just for the examples
#       You can safely skip this section
logger = logging.getLogger('SimpleService')
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(
    '%(name)s.%(process)d(%(levelname)s): %(message)s'))
logger.handlers.append(handler)

slogger = logging.getLogger('ServiceManager')
slogger.setLevel(logging.DEBUG)
shandler = logging.StreamHandler()
shandler.setFormatter(logging.Formatter(
    '%(name)s.%(process)d(%(levelname)s): %(message)s'))
slogger.handlers.append(shandler)
# -----


class SimpleService(CommissaireService):
    """
    A simple example service which exposes two methods on the bus:

    - add: Takes two integers and returns their sum.
    - wordy_add: Takes two integers, adds them, and returns a wordy result.
    """

    def on_add(self, x, y, message):
        """
        Adds two integers together. On the bus this would be exposed as add().
        """
        # Return the result back on the bus
        return int(x) + int(y)

    def on_wordy_add(self, x, y, message):
        """
        Adds two integers and returns a wordy response. On the bus this is
        exposed as wordy_add().
        """
        # Call on_add via the bus. Normally you wouldn't do this since it's
        # a local method already, but we are doing this to show how the remote
        # calls are done.
        response = self.send_request(
            routing_key='simple.add',
            method='add',
            params=[int(x), int(y)])
        # Return the result back on the bus
        # TODO: Fix response to be full jsonrpc 2.0
        return 'Adding {} plus {} results in {}'.format(
            x, y, response['result'])


if __name__ == '__main__':
    # queue_kwargs are the keyword arguments that are used when creating
    # kombu.Queues. We do this instead of passing objects directly so that
    # the service can create and handle the Queue's itself within it's owner
    # process scope.
    queue_kwargs = [
        {'name': 'simple', 'routing_key': 'simple.*'},
    ]
    # Here we use a ServiceManager to have 3 instances of SimepleService
    # running at all times. It will run until a KeyboardInterrupt is raised.
    try:
        ServiceManager(
            SimpleService,
            3,
            'commissaire',
            'redis://127.0.0.1:6379/',
            queue_kwargs
        ).run()
    except KeyboardInterrupt:
        pass

    # If you wanted to run just one process without the ServiceManager:
    # try:
    #     SimpleService(
    #         'commissaire',
    #         'redis://127.0.0.1:6379/',
    #         queue_kwargs
    #     ).run()
    # except KeyboardInterrupt:
    #     pass
