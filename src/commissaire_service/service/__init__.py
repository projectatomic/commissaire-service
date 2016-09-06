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

    def create_id(self):
        """
        Creates a new unique identifier.

        :returns: A unique identification string.
        :rtype: str
        """
        return str(uuid.uuid4())

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
        Called when a non-jsonrpc message arrives.

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
        Wraps on_message for jsonrpc routing and logging.

        :param body: Body of the message.
        :type body: str
        :param message: The message instance.
        :type message: kombu.message.Message
        """
        self.logger.debug('Received message "{}" {}'.format(
            message.delivery_tag, body))
        expected_method = message.delivery_info['routing_key'].rsplit(
            '.', 1)[1]
        # If we have a method and it matches the routing key treat it
        # as a jsonrpc call
        if 'method' in body.keys() and body['method'] == expected_method:
            try:
                result = getattr(
                    self, 'on_{}'.format(body['method']))(
                        message=message, **body['params'])
                message.ack()
            except Exception as error:
                result = 'Error:' + str(error) + str(type(error))
                message.reject()
            if message.properties.get('reply_to'):
                response_queue = self.connection.SimpleQueue(
                    message.properties['reply_to'])
                response_queue.put({
                    'result': result,
                })
                response_queue.close()
        # Otherwise send it to on_message
        else:
            self.on_message(body, message)
        self.logger.debug('Message "{0}" {1} ackd'.format(
            message.delivery_tag,
            ('was' if message.acknowledged else 'was not')))

    def send_response(self, queue_name, id, payload, **kwargs):
        """
        Sends a response to a simple queue. Responses are sent back to a
        request and never should be the owner of the queue.

        :param queue_name: The name of the queue to use.
        :type queue_name: str
        :param id: The unique request id
        :type id: str
        :param payload: The content of the message.
        :type payload: dict
        :param kwargs: Keyword arguments to pass to SimpleQueue
        :type kwargs: dict
        """
        self.logger.debug('Sending response for message id "{}"'.format(id))
        send_queue = self.connection.SimpleQueue(queue_name, **kwargs)
        jsonrpc_msg = {
            'jsonrpc': "2.0",
            'id': id,
            'result': payload,
        }
        self.logger.debug('jsonrpc msg: {}'.format(jsonrpc_msg))
        send_queue.put(jsonrpc_msg)
        self.logger.debug('Sent response for message id "{}"'.format(id))
        send_queue.close()

    def send_request(self, routing_key, id, method, params={}, **kwargs):
        """
        Sends a request to a simple queue. Requests create the initial response
        queue and wait for a response.

        :param routing_key: The routing key to publish on.
        :type routing_key: str
        :param id: The unique request id
        :type id: str
        :param method: The remote method to request.
        :type method: str
        :param params: Keyword parameters to pass to the remote method.
        :type params: dict
        :param kwargs: Keyword arguments to pass to SimpleQueue
        :type kwargs: dict
        :returns: Result
        :rtype: tuple
        """
        response_queue_name = 'response-{}'.format(self.create_id())
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

        jsonrpc_msg = {
            'jsonrpc': "2.0",
            'id': id,
            'method': method,
            'params': params,
        }
        self.logger.debug('jsonrpc message for id "{}": "{}"'.format(
            id, jsonrpc_msg))

        self.producer.publish(
            jsonrpc_msg,
            routing_key,
            declare=[self._exchange],
            reply_to=response_queue_name)

        self.logger.debug(
            'Sent message id "{}" to "{}". Waiting on response...'.format(
                id, response_queue_name))

        result = response_queue.get(block=False, timeout=1)
        result.ack()
        if 'error' in result.payload.keys():
            self.logger.warn(
                'Error returned from the message id "{}"'.format(
                    id, result.payload))

        self.logger.debug(
            'Result retrieved from response queue "{}": payload="{}"'.format(
                response_queue_name, result))
        self.logger.debug('Closing queue {}'.format(response_queue_name))
        response_queue.close()
        return result.payload

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
