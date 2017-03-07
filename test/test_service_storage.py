# Copyright (C) 2017  Red Hat, Inc
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
Tests for commissaire_service.storage.StorageService.
"""

from . import TestCase, mock

from commissaire.models import Host
from commissaire_service.storage import StorageService


class TestStorageService(TestCase):
    """
    Tests for the StorageService class.
    """

    def setUp(self):
        """
        Called before each test case.
        """
        patcher = mock.patch('commissaire_service.service.Connection')
        self._connection = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch('commissaire_service.service.Exchange')
        self._exchange = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch('commissaire_service.service.Producer')
        self._producer = patcher.start()
        self.addCleanup(patcher.stop)

        with mock.patch(
                'commissaire.util.config.read_config_file') as rcf, \
            mock.patch(
                'commissaire_service.storage.'
                'StorageService.register_store_handler') as rsh:
            rcf.return_value = {}
            self.service_instance = StorageService(
                'commissaire',
                'redis://127.0.0.1:6379/'
            )

        self.service_instance._manager = mock.MagicMock()
        self.service_instance._manager.get.side_effect = lambda model: model
        self.service_instance._manager.save.side_effect = lambda model: model

    def test_on_get_with_dict(self):
        """
        Verify StorageService.on_get handles dictionary input
        """
        address = '127.0.0.1'
        type_name = 'Host'
        json_data = {'address': address}

        message = mock.MagicMock()
        result = self.service_instance.on_get(message, type_name, json_data)

        self.assertEquals(self.service_instance._manager.get.call_count, 1)
        self.assertEquals(result, Host.new(address=address).to_dict())

    def test_on_get_with_str(self):
        """
        Verify StorageService.on_get handles string input
        """
        address = '127.0.0.1'
        type_name = 'Host'
        json_data = '{{"address": "{}"}}'.format(address)

        message = mock.MagicMock()
        result = self.service_instance.on_get(message, type_name, json_data)

        self.assertEquals(self.service_instance._manager.get.call_count, 1)
        self.assertEquals(result, Host.new(address=address).to_dict())

    def test_on_get_with_list(self):
        """
        Verify StorageService.on_get handles list input
        """
        address1 = '192.168.1.1'
        address2 = '192.168.1.2'
        type_name = 'Host'
        json_data = [{'address': address1}, {'address': address2}]

        message = mock.MagicMock()
        result = self.service_instance.on_get(message, type_name, json_data)

        self.assertIsInstance(result, list)
        self.assertEquals(len(result), 2)
        self.assertEquals(self.service_instance._manager.get.call_count, 2)
        self.assertEquals(result[0], Host.new(address=address1).to_dict())
        self.assertEquals(result[1], Host.new(address=address2).to_dict())

    def test_on_get_with_invalid_list(self):
        """
        Verify StorageService.on_get handles invalid list input
        """
        type_name = 'Host'

        # 1st item valid, 2nd item invalid
        json_data = [{'address': '127.0.0.1'}, {}]

        message = mock.MagicMock()
        self.assertRaises(
            TypeError, self.service_instance.on_get,
            message, type_name, json_data)

        # Even though 1st item is valid, manager.get() should not be called.
        self.service_instance._manager.get.assert_not_called()

    def test_on_save_with_dict(self):
        """
        Verify StorageService.on_save handles dictionary input
        """
        address = '127.0.0.1'
        type_name = 'Host'
        json_data = {'address': address}

        message = mock.MagicMock()
        result = self.service_instance.on_save(message, type_name, json_data)

        self.assertEquals(self.service_instance._manager.save.call_count, 1)
        self.assertEquals(result, Host.new(address=address).to_dict())

    def test_on_save_with_str(self):
        """
        Verify StorageService.on_save handles string input
        """
        address = '127.0.0.1'
        type_name = 'Host'
        json_data = '{{"address": "{}"}}'.format(address)

        message = mock.MagicMock()
        result = self.service_instance.on_save(message, type_name, json_data)

        self.assertEquals(self.service_instance._manager.save.call_count, 1)
        self.assertEquals(result, Host.new(address=address).to_dict())

    def test_on_save_with_list(self):
        """
        Verify StorageService.on_save handles list input
        """
        address1 = '192.168.1.1'
        address2 = '192.168.1.2'
        type_name = 'Host'
        json_data = [{'address': address1}, {'address': address2}]

        message = mock.MagicMock()
        result = self.service_instance.on_save(message, type_name, json_data)

        self.assertIsInstance(result, list)
        self.assertEquals(len(result), 2)
        self.assertEquals(self.service_instance._manager.save.call_count, 2)
        self.assertEquals(result[0], Host.new(address=address1).to_dict())
        self.assertEquals(result[1], Host.new(address=address2).to_dict())

    def test_on_save_with_invalid_list(self):
        """
        Verify StorageService.on_save handles invalid list input
        """
        type_name = 'Host'

        # 1st item valid, 2nd item invalid
        json_data = [{'address': '127.0.0.1'}, {}]

        message = mock.MagicMock()
        self.assertRaises(
            TypeError, self.service_instance.on_save,
            message, type_name, json_data)

        # Even though 1st item is valid, manager.save() should not be called.
        self.service_instance._manager.save.assert_not_called()

    def test_on_delete_with_dict(self):
        """
        Verify StorageService.on_delete handles dictionary input
        """
        address = '127.0.0.1'
        type_name = 'Host'
        json_data = {'address': address}

        message = mock.MagicMock()
        self.service_instance.on_delete(message, type_name, json_data)

        self.assertEquals(self.service_instance._manager.delete.call_count, 1)

    def test_on_delete_with_str(self):
        """
        Verify StorageService.on_delete handles string input
        """
        address = '127.0.0.1'
        type_name = 'Host'
        json_data = '{{"address": "{}"}}'.format(address)

        message = mock.MagicMock()
        self.service_instance.on_delete(message, type_name, json_data)

        self.assertEquals(self.service_instance._manager.delete.call_count, 1)

    def test_on_delete_with_list(self):
        """
        Verify StorageService.on_delete handles list input
        """
        address1 = '192.168.1.1'
        address2 = '192.168.1.2'
        type_name = 'Host'
        json_data = [{'address': address1}, {'address': address2}]

        message = mock.MagicMock()
        self.service_instance.on_delete(message, type_name, json_data)

        self.assertEquals(self.service_instance._manager.delete.call_count, 2)

    def test_on_delete_with_invalid_list(self):
        """
        Verify StorageService.on_delete handles invalid list input
        """
        type_name = 'Host'

        # 1st item valid, 2nd item invalid
        json_data = [{'address': '127.0.0.1'}, {}]

        message = mock.MagicMock()
        self.assertRaises(
            TypeError, self.service_instance.on_delete,
            message, type_name, json_data)

        # Even though 1st item is valid, manager.delete() should not be called.
        self.service_instance._manager.delete.assert_not_called()
