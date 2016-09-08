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
Tests for commissaire_service.service.ServiceManager class.
"""

import logging
import os

import kombu

from . import TestCase, mock
from commissaire_service.service import ServiceManager, run_service


class TestServiceManager(TestCase):
    """
    Tests for the ServiceManager class.
    """

    def setUp(self):
        """
        Set up before each test.
        """
        self._connection_patcher = mock.patch(
            'commissaire_service.service.Connection')
        self._exchange_patcher = mock.patch(
            'commissaire_service.service.Exchange')
        self._producer_patcher = mock.patch(
            'commissaire_service.service.Producer')
        self._mppool_patcher = mock.patch(
            'multiprocessing.Pool')

        self._connection = self._connection_patcher.start()
        self._exchange = self._exchange_patcher.start()
        self._producer = self._producer_patcher.start()
        self._mppool = self._mppool_patcher.start()

        self.queue_kwargs = [
            {'name': 'simple', 'routing_key': 'simple.*'},
        ]

        self.manager_instance = ServiceManager(
            mock.MagicMock(),
            1,
            'commissaire',
            'redis://127.0.0.1:6379/',
            self.queue_kwargs
        )

    def tearDown(self):
        """
        Stop all patchers.
        """
        self._connection.stop()
        self._exchange.stop()
        self._producer.stop()
        self._mppool.stop()

    def test_initialization(self):
        """
        Verify CommissaireService initializes as expected.
        """
        # We should have a pool
        self._mppool.assert_called_once_with(
            1, maxtasksperchild=1)

    def test__start_process(self):
        """
        Verify CommissaireService._start_process creates a single subprocess.
        """
        self.manager_instance._start_process()

        self.manager_instance._pool.apply_async.assert_called_once_with(
            run_service,
            args=[self.manager_instance.service_class],
            kwds={'kwargs': {
                'exchange_name': self.manager_instance.exchange_name,
                'connection_url': self.manager_instance.connection_url,
                'qkwargs': self.manager_instance.qkwargs,
            }})

    def test_run(self):
        """
        Verify ServiceManager.run starts up all processes.
        """
        self.manager_instance._start_process = mock.MagicMock()
        with mock.patch('commissaire_service.service.sleep') as _sleep:
            _sleep.side_effect = Exception
            # We should get through one iteration before raising
            self.assertRaises(Exception, self.manager_instance.run)
            # We should have one process started
            self.manager_instance._start_process.assert_called_once_with()
