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
Service base class.
"""
import logging

from kombu import Producer
from kombu.mixins import ConsumerMixin


class CommissaireService(ConsumerMixin):
    """
    An example prototype CommissaireService base class.
    """

    def __init__(self, connection, exchange, queues):
        """
        Initializes a new Service instance.

        :param connection: A kombu connection.
        :type connection: kombu.Connection
        :param connection: A kombu Exchange.
        :type connection: kombu.Exchange
        :param queues: List of kombu.Queues to consume
        :type queues: list
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug('Initializing {0}'.format(self.__class__.__name__))
        self._queues = queues
        self._exchange = exchange
        self.connection = connection
        self.producer = Producer(self.connection.channel(), exchange)
        self.logger.debug('Initializing finished')

    def get_consumers(self, Consumer, channel):
        """
        Returns the a list of consumers to watch. Called by the parent Mixin.

        :param Consumer: Message consumer class.
        :type Consumer: kombu.Consumer
        :param channel: An opened channel.
        :type channel: kombu.transport.*.Channel
        :returns: A list of Consumer instances.
        :rtype: list
        """
        consumers = []
        for queue in self._queues:
            self.logger.debug('Will consume on {0}'.format(queue.name))
            consumers.append(
                Consumer(queue, callbacks=[self._wrap_on_message]))
        return consumers

    def _wrap_on_message(self, body, message):
        """
        Wraps on_message for logging.

        :param body: Body of the message.
        :type body: str
        :param message: The message instance.
        :type message: kombu.message.Message
        """
        self.logger.debug('Received message "{0}"'.format(
            message.delivery_tag))
        self.on_message(body, message)
        self.logger.debug('Message "{0}" {1} ackd'.format(
            message.delivery_tag,
            ('was' if message.acknowledged else 'was not')))

    def on_connection_revived(self):
        """
        Called when a reconnection occurs.
        """
        self.logger.info('Connection reestablished')

    def on_consume_ready(self, connection, channel, consumers):  # NOQA
        """
        Called when the service is ready to consume messages.

        :param connection: The current connection instance.
        :type connection: kombu.Connection
        :param channel: The current channel.
        :type channel: kombu.transport.*.Channel
        :param consumers: A list of consumers.
        :type consumers: list
        """
        self.logger.info('Ready to consume')
        if self.logger.level == logging.DEBUG:
            queue_names = []
            for consumer in consumers:
                queue_names += [x.name for x in consumer.queues]
            self.logger.debug(
                'Consuming via connection "{0}" and channel "{1}" on '
                'the following queues: "{2}"'.format(
                    connection.as_uri(), channel, '", "'.join(queue_names)))

    def on_consume_end(self, connection, channel):  # NOQA
        """
        Called when the service stops consuming.

        :param connection: The current connection instance.
        :type connection: kombu.Connection
        :param channel: The current channel.
        :type channel: kombu.transport.*.Channel
        """
        self.logger.warn('Consuming has ended')

    def __del__(self):  # NOQA
        """
        Called upon instance death.
        """
        self.logger.debug(
            '{0} instance has is being destroyed by garbage collection'.format(
                self))
