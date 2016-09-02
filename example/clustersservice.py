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
Prototype cluster service.
"""

import logging

from kombu import Queue

from commissaire_service.service import CommissaireService

# NOTE: Only added for this example
logger = logging.getLogger('ClustersService')
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(
    '%(name)s.%(process)d(%(levelname)s): %(message)s'))
logger.handlers.append(handler)
# --


class ClustersService(CommissaireService):
    """
    An example prototype service.
    """

    def on_list(self, message):
        """
        Lists all clusters.
        """
        self.logger.debug('Responding to {0}'.format(
            message.properties['reply_to']))

        # NOTE: action is an example. We will need to define verbs
        #       this is just an example stub
        response, outcome = self.send_request('storage', {'action': 'list'})
        self.logger.debug('Got {} {}'.format(response, outcome))
        # Return result
        return ({'clusters': ['...']}, 'success')


if __name__ == '__main__':
    queue = Queue('clusters', routing_key='http.clusters.*')

    try:
        # NOTE: Using redis in the prototype
        ClustersService(
            'commissaire',
            'redis://127.0.0.1:6379/',
            [queue]
        ).run()
    except KeyboardInterrupt:
        pass
