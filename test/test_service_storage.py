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

import json

from commissaire import models
from commissaire.storage import StoreHandlerBase
from commissaire.util.config import ConfigurationError
from commissaire_service.storage import StorageService
from commissaire_service.storage.custodia import CustodiaStoreHandler


SECRET_MODEL_TYPES = (
    models.SecretModel,
    models.HostCreds)


class StoreHandlerTest(StoreHandlerBase):
    """
    Minimal store handler implementation to aid in unit testing.
    """

    @classmethod
    def check_config(cls, config):
        return True


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

        patcher = mock.patch('commissaire_service.storage.import_plugin')
        patcher.start().return_value = StoreHandlerTest
        self.addCleanup(patcher.stop)

        # This gets the StorageService created without registering any
        # store handlers.
        with mock.patch(
                'commissaire_service.service.read_config_file') as rcf, \
            mock.patch(
                'commissaire_service.storage.'
                'StorageService._register_store_handler') as rsh:
            rcf.return_value = {}
            self.service_instance = StorageService(
                'commissaire',
                'redis://127.0.0.1:6379/')

    def test_register_store_handler(self):
        """
        Verify StorageService._register_store_handler works as intended
        """
        # Shorter names for data structures.
        definitions_by_name = \
            self.service_instance._definitions_by_name
        definitions_by_model_type = \
            self.service_instance._definitions_by_model_type

        # Factor builtin definitions in our final checks.
        builtin_by_name = len(definitions_by_name)
        builtin_by_model_type = len(definitions_by_model_type)

        # Verify SecretModel registrations are rejected.
        for model_type in SECRET_MODEL_TYPES:
            self.assertTrue(issubclass(model_type, models.SecretModel))
            config = {
                'type': 'test',
                'models': [model_type.__name__]
            }
            self.assertRaises(
                ConfigurationError,
                self.service_instance._register_store_handler,
                config)

        # Valid registration, implicit name.
        implicit_name = __name__
        model_type = models.Host
        config = {
            'type': 'test',
            'models': [model_type.__name__]
        }
        self.service_instance._register_store_handler(config)
        self.assertEqual(config.get('name'), implicit_name)
        self.assertIn(implicit_name, definitions_by_name)
        self.assertIn(model_type, definitions_by_model_type)

        # Valid registration, explicit name.
        explicit_name = 'handle_me_harder'
        model_type = models.Cluster
        config = {
            'type': 'test',
            'name': explicit_name,
            'models': [model_type.__name__]
        }
        self.service_instance._register_store_handler(config)
        self.assertEqual(config.get('name'), explicit_name)
        self.assertIn(explicit_name, definitions_by_name)
        self.assertIn(model_type, definitions_by_model_type)

        # Valid registration, implicit name, ID collision.
        implicit_name = __name__ + '-1'
        model_type = models.Network
        config = {
            'type': 'test',
            'name': implicit_name,
            'models': [model_type.__name__]
        }
        self.service_instance._register_store_handler(config)
        self.assertEqual(config.get('name'), implicit_name)
        self.assertIn(implicit_name, definitions_by_name)
        self.assertIn(model_type, definitions_by_model_type)

        # Valid registration, implicit name, multiple model types.
        implicit_name = __name__ + '-2'
        model_types = (
            models.ClusterDeploy,
            models.ClusterRestart,
            models.ClusterUpgrade
        )
        config = {
            'type': 'test',
            'name': implicit_name,
            'models': [mt.__name__ for mt in model_types]
        }
        self.service_instance._register_store_handler(config)
        self.assertEqual(config.get('name'), implicit_name)
        self.assertIn(implicit_name, definitions_by_name)
        for mt in model_types:
            self.assertIn(mt, definitions_by_model_type)

        # Invalid registration, explicit name, name collision.
        model_type = models.ContainerManagerConfig
        config = {
            'type': 'test',
            'name': 'handle_me_harder',
            'models': [model_type.__name__]
        }
        self.assertRaises(
            ConfigurationError,
            self.service_instance._register_store_handler,
            config)

        # Invalid registration, implicit name, model type collision.
        model_type = models.Host
        config = {
            'type': 'test',
            'models': [model_type.__name__]
        }
        self.assertRaises(
            ConfigurationError,
            self.service_instance._register_store_handler,
            config)

        # Verify StoreHandlerManager state.
        self.assertEquals(
            len(definitions_by_name),
            4 + builtin_by_name)
        self.assertEquals(
            len(definitions_by_model_type),
            6 + builtin_by_model_type)
        expect_handlers = [
            (StoreHandlerTest,
                {'name': __name__},
                set([models.Host])),
            (StoreHandlerTest,
                {'name': 'handle_me_harder'},
                set([models.Cluster])),
            (StoreHandlerTest,
                {'name': __name__ + '-1'},
                set([models.Network])),
            (StoreHandlerTest,
                {'name': __name__ + '-2'},
                set([models.ClusterDeploy,
                     models.ClusterRestart,
                     models.ClusterUpgrade]))
        ]
        # Note, actual_handlers is unordered.
        actual_handlers = list(definitions_by_name.values())
        self.assertEquals(len(actual_handlers), 4 + builtin_by_name)
        for handler in expect_handlers:
            self.assertIn(handler, actual_handlers)

    def test_register_store_handler_wildcards(self):
        """
        Verify wildcard patterns in "models" excludes SecretModels
        """
        config = {
            'type': 'test',
            'models': ['*']
        }
        # This would throw a ConfigurationError if SecretModel types
        # WERE included, since the matched types would conflict with
        # pre-registered SecretModel types.
        self.service_instance._register_store_handler(config)

    def test_get_handler(self):
        """
        Verify StorageService._get_handler() works as intended
        """
        default_config = {
            'type': 'test',
            'name': 'default',
            'models': ['Host']
        }
        self.service_instance._register_store_handler(default_config)
        alternate_config = {
            'type': 'test',
            'name': 'alternate',
            'models': []
        }
        self.service_instance._register_store_handler(alternate_config)

        # Shorter names for data structures.
        handlers_by_name = \
            self.service_instance._handlers_by_name
        handlers_by_model_type = \
            self.service_instance._handlers_by_model_type

        self.assertEquals(len(handlers_by_name), 0)
        self.assertEquals(len(handlers_by_model_type), 0)

        # Select default handler for models.Host with no source value.
        model = models.Host.new(address='127.0.0.1')
        handler = self.service_instance._get_handler(model)
        default_handler = handlers_by_name.get('default')
        self.assertIsInstance(handler, StoreHandlerTest)
        self.assertIs(handler, default_handler)

        # Select alternate handler for models.Host with a source value.
        model = models.Host.new(address='127.0.0.1', source='alternate')
        handler = self.service_instance._get_handler(model)
        alternate_handler = handlers_by_name.get('alternate')
        self.assertIsInstance(handler, StoreHandlerTest)
        self.assertIs(handler, alternate_handler)

        # Verify KeyError for unsupported model type.
        model = models.Cluster.new(name='honeynut')
        self.assertRaises(
            KeyError,
            self.service_instance._get_handler,
            model)

        # Verify KeyError for models.Host with invalid source value.
        model = models.Host.new(address='127.0.0.1', source='bogus')
        self.assertRaises(
            KeyError,
            self.service_instance._get_handler,
            model)

        # Verify HostCreds instance returns CustodiaStoreHandler.
        model = models.HostCreds.new(address='127.0.0.1')
        handler = self.service_instance._get_handler(model)
        self.assertIsInstance(handler, CustodiaStoreHandler)

    @mock.patch('commissaire_service.storage.StorageService._get_handler')
    def test_on_get_with_dict(self, get_handler):
        """
        Verify StorageService.on_get handles dictionary input
        """
        handler = mock.MagicMock()
        get_handler.return_value = handler

        address = '127.0.0.1'
        type_name = 'Host'
        json_data = {'address': address}

        host = models.Host.new(**json_data)
        handler._get.return_value = host

        message = mock.MagicMock()
        result = self.service_instance.on_get(message, type_name, json_data)

        self.assertEquals(handler._get.call_count, 1)
        self.assertEquals(result, host.to_dict())

    @mock.patch('commissaire_service.storage.StorageService._get_handler')
    def test_on_get_with_str(self, get_handler):
        """
        Verify StorageService.on_get handles string input
        """
        handler = mock.MagicMock()
        get_handler.return_value = handler

        address = '127.0.0.1'
        type_name = 'Host'
        json_data = '{{"address": "{}"}}'.format(address)

        host = models.Host.new(**json.loads(json_data))
        handler._get.return_value = host

        message = mock.MagicMock()
        result = self.service_instance.on_get(message, type_name, json_data)

        self.assertEquals(handler._get.call_count, 1)
        self.assertEquals(result, host.to_dict())

    @mock.patch('commissaire_service.storage.StorageService._get_handler')
    def test_on_get_with_invalid_data(self, get_handler):
        """
        Verify StorageService.on_get rejects invalid stored data
        """
        handler = mock.MagicMock()
        get_handler.return_value = handler

        address = '127.0.0.1'
        type_name = 'Host'
        json_data = {'address': address}

        host = models.Host.new(**json_data)
        host.address = None  # wrong type
        handler._get.return_value = host

        message = mock.MagicMock()
        self.assertRaises(
            models.ValidationError,
            self.service_instance.on_get,
            message, type_name, json_data)

        # The output model is validated after calling handler._get().
        self.assertEquals(handler._get.call_count, 1)

    @mock.patch('commissaire_service.storage.StorageService._get_handler')
    def test_on_get_with_list(self, get_handler):
        """
        Verify StorageService.on_get handles list input
        """
        handler = mock.MagicMock()
        get_handler.return_value = handler

        address1 = '192.168.1.1'
        address2 = '192.168.1.2'
        type_name = 'Host'
        json_data = [{'address': address1}, {'address': address2}]

        hosts = [models.Host.new(**x) for x in json_data]
        handler._get.side_effect = hosts

        message = mock.MagicMock()
        result = self.service_instance.on_get(message, type_name, json_data)

        self.assertIsInstance(result, list)
        self.assertEquals(len(result), 2)
        self.assertEquals(handler._get.call_count, 2)
        self.assertEquals(result[0], hosts[0].to_dict())
        self.assertEquals(result[1], hosts[1].to_dict())

    @mock.patch('commissaire_service.storage.StorageService._get_handler')
    def test_on_get_with_invalid_list(self, get_handler):
        """
        Verify StorageService.on_get handles invalid list input
        """
        handler = mock.MagicMock()
        get_handler.return_value = handler

        type_name = 'Host'

        # 1st item valid, 2nd item invalid
        json_data = [{'address': '127.0.0.1'}, {}]

        message = mock.MagicMock()
        self.assertRaises(
            TypeError, self.service_instance.on_get,
            message, type_name, json_data)

        # Even though 1st item is valid, handler._get() should not be called.
        handler._get.assert_not_called()

    @mock.patch('commissaire_service.storage.StorageService._get_handler')
    def test_on_save_with_dict(self, get_handler):
        """
        Verify StorageService.on_save handles dictionary input
        """
        handler = mock.MagicMock()
        get_handler.return_value = handler

        address = '127.0.0.1'
        type_name = 'Host'
        json_data = {'address': address}

        host = models.Host.new(**json_data)
        handler._save.return_value = host

        message = mock.MagicMock()
        result = self.service_instance.on_save(message, type_name, json_data)

        self.assertEquals(handler._save.call_count, 1)
        self.assertEquals(result, host.to_dict())

    @mock.patch('commissaire_service.storage.StorageService._get_handler')
    def test_on_save_with_str(self, get_handler):
        """
        Verify StorageService.on_save handles string input
        """
        handler = mock.MagicMock()
        get_handler.return_value = handler

        address = '127.0.0.1'
        type_name = 'Host'
        json_data = '{{"address": "{}"}}'.format(address)

        host = models.Host.new(**json.loads(json_data))
        handler._save.return_value = host

        message = mock.MagicMock()
        result = self.service_instance.on_save(message, type_name, json_data)

        self.assertEquals(handler._save.call_count, 1)
        self.assertEquals(result, models.Host.new(address=address).to_dict())

    @mock.patch('commissaire_service.storage.StorageService._get_handler')
    def test_on_save_with_invalid_data(self, get_handler):
        """
        Verify StorageService.on_save rejects invalid input data
        """
        handler = mock.MagicMock()
        get_handler.return_value = handler

        address = None  # wrong type
        type_name = 'Host'
        json_data = {'address': address}

        message = mock.MagicMock()
        self.assertRaises(
            models.ValidationError,
            self.service_instance.on_save,
            message, type_name, json_data)

        # The input model is validated before calling handler._save().
        handler._save.assert_not_called()

    @mock.patch('commissaire_service.storage.StorageService._get_handler')
    def test_on_save_with_list(self, get_handler):
        """
        Verify StorageService.on_save handles list input
        """
        handler = mock.MagicMock()
        get_handler.return_value = handler

        address1 = '192.168.1.1'
        address2 = '192.168.1.2'
        type_name = 'Host'
        json_data = [{'address': address1}, {'address': address2}]

        hosts = [models.Host.new(**x) for x in json_data]
        handler._save.side_effect = hosts

        message = mock.MagicMock()
        result = self.service_instance.on_save(message, type_name, json_data)

        self.assertIsInstance(result, list)
        self.assertEquals(len(result), 2)
        self.assertEquals(handler._save.call_count, 2)
        self.assertEquals(result[0], hosts[0].to_dict())
        self.assertEquals(result[1], hosts[1].to_dict())

    @mock.patch('commissaire_service.storage.StorageService._get_handler')
    def test_on_save_with_invalid_list(self, get_handler):
        """
        Verify StorageService.on_save handles invalid list input
        """
        handler = mock.MagicMock()
        get_handler.return_value = handler

        type_name = 'Host'

        # 1st item valid, 2nd item invalid
        json_data = [{'address': '127.0.0.1'}, {}]

        message = mock.MagicMock()
        self.assertRaises(
            TypeError, self.service_instance.on_save,
            message, type_name, json_data)

        # Even though 1st item is valid, handler._save() should not be called.
        handler._save.assert_not_called()

    @mock.patch('commissaire_service.storage.StorageService._get_handler')
    def test_on_delete_with_dict(self, get_handler):
        """
        Verify StorageService.on_delete handles dictionary input
        """
        handler = mock.MagicMock()
        get_handler.return_value = handler

        address = '127.0.0.1'
        type_name = 'Host'
        json_data = {'address': address}

        message = mock.MagicMock()
        self.service_instance.on_delete(message, type_name, json_data)

        self.assertEquals(handler._delete.call_count, 1)

    @mock.patch('commissaire_service.storage.StorageService._get_handler')
    def test_on_delete_with_str(self, get_handler):
        """
        Verify StorageService.on_delete handles string input
        """
        handler = mock.MagicMock()
        get_handler.return_value = handler

        address = '127.0.0.1'
        type_name = 'Host'
        json_data = '{{"address": "{}"}}'.format(address)

        message = mock.MagicMock()
        self.service_instance.on_delete(message, type_name, json_data)

        self.assertEquals(handler._delete.call_count, 1)

    @mock.patch('commissaire_service.storage.StorageService._get_handler')
    def test_on_delete_with_list(self, get_handler):
        """
        Verify StorageService.on_delete handles list input
        """
        handler = mock.MagicMock()
        get_handler.return_value = handler

        address1 = '192.168.1.1'
        address2 = '192.168.1.2'
        type_name = 'Host'
        json_data = [{'address': address1}, {'address': address2}]

        message = mock.MagicMock()
        self.service_instance.on_delete(message, type_name, json_data)

        self.assertEquals(handler._delete.call_count, 2)

    @mock.patch('commissaire_service.storage.StorageService._get_handler')
    def test_on_delete_with_invalid_list(self, get_handler):
        """
        Verify StorageService.on_delete handles invalid list input
        """
        handler = mock.MagicMock()
        get_handler.return_value = handler

        type_name = 'Host'

        # 1st item valid, 2nd item invalid
        json_data = [{'address': '127.0.0.1'}, {}]

        message = mock.MagicMock()
        self.assertRaises(
            TypeError, self.service_instance.on_delete,
            message, type_name, json_data)

        # Even though 1st item is valid, handler._delete() should not be called.
        handler._delete.assert_not_called()

    @mock.patch('commissaire_service.storage.StorageService._get_handler')
    def test_on_list(self, get_handler):
        """
        Verify StorageService.on_list works as intended
        """
        handler = mock.MagicMock()
        get_handler.return_value = handler

        host = models.Host.new(address='127.0.0.1')
        handler._list.return_value = models.Hosts.new(hosts=[host])

        message = mock.MagicMock()
        self.service_instance.on_list(message, 'Hosts')

        list_of_models = self.service_instance.on_list(message, 'Hosts')
        self.assertIsInstance(list_of_models, list)
        self.assertEquals(len(list_of_models), 1)
        self.assertEquals(list_of_models[0], host.to_dict())
