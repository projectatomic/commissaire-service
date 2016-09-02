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
import uuid

from kombu import Connection, Exchange, Producer
from kombu.mixins import ConsumerMixin


class CommissaireService(ConsumerMixin):
    """
    An example prototype CommissaireService base class.
    """

    def __init__(self, exchange_name, connection_url, queues):
        """
        Initializes a new Service instance.

        :param exchange_name: Name of the topic exchange.
        :type exchange_name: str
        :param connection_url: Kombu connection url.
        :type connection_url: str
        :param queues: List of kombu.Queues to consume
        :type queues: list
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug('Initializing {0}'.format(self.__class__.__name__))
        self.connection = Connection(connection_url)
        self._channel = self.connection.channel()
        self._exchange = Exchange(exchange_name, type='topic').bind(
            self._channel)
        self._exchange.declare()

        # Set up queues
        self._queues = []
        for queue in queues:
            queue.exchange = self._exchange
            queue = queue.bind(self._channel)
            self._queues.append(queue)
            self.logger.debug(queue.as_dict())

        # Create producer for publishing on topics
        self.producer = Producer(self._channel, self._exchange)
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

    def on_message(self, body, message):
        """
        Called when a non-action message arrives.

        :param body: Body of the message.
        :type body: str
        :param message: The message instance.
        :type message: kombu.message.Message
        """
        self.logger.error(
            'Rejecting unknown message: payload="{}", properties="{}"'.format(
                body, message.properties))
        message.reject()

    def _wrap_on_message(self, body, message):
        """
        Wraps on_message for action routing and logging.

        :param body: Body of the message.
        :type body: str
        :param message: The message instance.
        :type message: kombu.message.Message
        """
        self.logger.debug('Received message "{}" {}'.format(
            message.delivery_tag, body))
        action = message.delivery_info['routing_key'].rsplit('.', 1)[1]
        # If we have action and args treat it is an action request
        if 'args' in body.keys():
            try:
                result, outcome = getattr(
                    self, 'on_{}'.format(action))(
                        message=message, **body['args'])
                message.ack()
            except Exception as error:
                result = str(error)
                outcome = 'error'
                message.reject()
            if message.properties.get('reply_to'):
                response_queue = self.connection.SimpleQueue(
                    message.properties['reply_to'])
                response_queue.put({
                    'result': result,
                }, outcome=outcome)
                response_queue.close()
        # Otherwise send it to on_message
        else:
            self.on_message(body, message)
        self.logger.debug('Message "{0}" {1} ackd'.format(
            message.delivery_tag,
            ('was' if message.acknowledged else 'was not')))

    def send_response(self, queue_name, payload, **kwargs):
        """
        Sends a response to a simple queue. Responses are sent back to a
        request and never should be the owner of the queue.

        :param queue_name: The name of the queue to use.
        :type queue_name: str
        :param payload: The content of the message.
        :type payload: dict
        :param kwargs: Keyword arguments to pass to SimpleQueue
        :type kwargs: dict
        """
        self.logger.debug('Sending "{}" to "{}"'.format(payload, queue_name))
        send_queue = self.connection.SimpleQueue(queue_name, **kwargs)

        send_queue.put(payload)
        self.logger.debug('Sent "{}" to "{}"'.format(payload, queue_name))
        send_queue.close()

    def send_request(self, routing_key, payload, **kwargs):
        """
        Sends a request to a simple queue. Requests create the initial response
        queue and wait for a response.

        :param routing_key: The routing key to publish on.
        :type routing_key: str
        :param payload: The content of the message.
        :type payload: dict
        :param kwargs: Keyword arguments to pass to SimpleQueue
        :type kwargs: dict
        :returns: Tuple of result, outcome
        :rtype: tuple
        """
        response_queue_name = 'response-{}'.format(uuid.uuid4())
        self.logger.debug('Creating response queue "{}"'.format(
            response_queue_name))
        queue_opts = {
            'auto_delete': True,
            'durable': False,
        }
        if kwargs.get('queue_opts'):
            queue_opts.update(kwargs.pop('queue_opts'))

        response_queue = self.connection.SimpleQueue(
            response_queue_name,
            queue_opts=queue_opts,
            **kwargs)

        self.producer.publish(
            payload,
            routing_key,
            declare=[self._exchange],
            reply_to=response_queue_name)

        self.logger.debug('Sent "{}" to "{}". Waiting on response...'.format(
            payload, response_queue_name))

        try:
            result = response_queue.get(block=False, timeout=1)
            result.ack()
            outcome = result.properties.get('outcome', 'error')
            if outcome is 'success':
                result = result.payload['result']
            else:
                self.logger.warn(
                    'Unexpected outcome: outcome="{}", payload="{}"'.format(
                        outcome, result.payload))
                raise Exception('TODO make me a real exception.')
        except Exception as error:
            result = {'error': {
                'type': type(error),
                'message': str(error),
            }}
            outcome = 'error'

        self.logger.debug(
            'Result retrieved from {}: outcome="{}" payload="{}"'.format(
                response_queue_name, outcome, result))
        self.logger.debug('Closing queue {}'.format(response_queue_name))
        response_queue.close()
        return result, outcome

    def onconnection_revived(self):
        """
        Called when a reconnection occurs.
        """
        self.logger.info('Connection (re)established')

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
