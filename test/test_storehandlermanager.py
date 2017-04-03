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
Tests for commissaire_service.storage.StoreHandlerManager.
"""


from . import TestCase, mock

import commissaire.models as models

from commissaire.containermgr import ContainerManagerBase
from commissaire.storage import StoreHandlerBase
from commissaire.util.config import ConfigurationError
from commissaire_service.storage import StoreHandlerManager


class StoreHandlerTest(StoreHandlerBase):
    """
    Minimal store handler implementation to aid in unit testing.
    """

    @classmethod
    def check_config(cls, config):
        return True


class TestStoreHandlerManager(TestCase):
    """
    Tests for the StoreHandlerManager class.
    """

    def setUp(self):
        """
        Called before each test case.
        """
        self.manager = StoreHandlerManager()

    def test_register_store_handler(self):
        """
        Verify StoreHandlerManager.register_store_handler works as intended
        """

        # Valid registration, implicit name.
        implicit_name = __name__
        config = {}
        model_type = models.Host
        self.manager.register_store_handler(
            StoreHandlerTest, config, model_type)
        self.assertEqual(config.get('name'), implicit_name)
        self.assertIn(implicit_name, self.manager._definitions_by_name)
        self.assertIn(model_type, self.manager._definitions_by_model_type)

        # Valid registration, explicit name.
        explicit_name = 'handle_me_harder'
        config = {'name': explicit_name}
        model_type = models.Cluster
        self.manager.register_store_handler(
            StoreHandlerTest, config, model_type)
        self.assertEqual(config.get('name'), explicit_name)
        self.assertIn(explicit_name, self.manager._definitions_by_name)
        self.assertIn(model_type, self.manager._definitions_by_model_type)

        # Valid registration, implicit name, ID collision.
        implicit_name = __name__ + '-1'
        config = {}
        model_type = models.Network
        self.manager.register_store_handler(
            StoreHandlerTest, config, model_type)
        self.assertEqual(config.get('name'), implicit_name)
        self.assertIn(implicit_name, self.manager._definitions_by_name)
        self.assertIn(model_type, self.manager._definitions_by_model_type)

        # Valid registration, implicit name, multiple model types.
        implicit_name = __name__ + '-2'
        config = {}
        model_types = (
            models.ClusterDeploy,
            models.ClusterRestart,
            models.ClusterUpgrade
        )
        self.manager.register_store_handler(
            StoreHandlerTest, config, *model_types)
        self.assertEqual(config.get('name'), implicit_name)
        self.assertIn(implicit_name, self.manager._definitions_by_name)
        for mt in model_types:
            self.assertIn(mt, self.manager._definitions_by_model_type)

        # Invalid registration, explicit name, name collision.
        config = {'name': 'handle_me_harder'}
        model_type = models.ContainerManagerConfig
        self.assertRaises(
            ConfigurationError,
            self.manager.register_store_handler,
            StoreHandlerTest, config, model_type)

        # Invalid registration, implicit name, model type collision.
        config = {}
        model_type = models.Host
        self.assertRaises(
            ConfigurationError,
            self.manager.register_store_handler,
            StoreHandlerTest, config, model_type)

        # Verify StoreHandlerManager state.
        self.assertEquals(len(self.manager._definitions_by_name), 4)
        self.assertEquals(len(self.manager._definitions_by_model_type), 6)
        expect_handlers = [
            (StoreHandlerTest,
                {'name': __name__},
                (models.Host,)),
            (StoreHandlerTest,
                {'name': 'handle_me_harder'},
                (models.Cluster,)),
            (StoreHandlerTest,
                {'name': __name__ + '-1'},
                (models.Network,)),
            (StoreHandlerTest,
                {'name': __name__ + '-2'},
                (models.ClusterDeploy,
                 models.ClusterRestart,
                 models.ClusterUpgrade))
        ]
        # Note, actual_handlers is unordered.
        actual_handlers = self.manager.list_store_handlers()
        self.assertEquals(len(actual_handlers), 4)
        for handler in expect_handlers:
            self.assertIn(handler, actual_handlers)

    def test_get_handler(self):
        """
        Verify StoreHandlerManager._get_handler() works as intended
        """
        self.manager.register_store_handler(
            StoreHandlerTest, {'name': 'default'}, models.Host)
        self.manager.register_store_handler(
            StoreHandlerTest, {'name': 'alternate'})

        self.assertEquals(len(self.manager._handlers_by_name), 0)
        self.assertEquals(len(self.manager._handlers_by_model_type), 0)

        # Select default handler for Host with no source value.
        model = models.Host.new(address='127.0.0.1')
        handler = self.manager._get_handler(model)
        default_handler = self.manager._handlers_by_name.get('default')
        self.assertIsInstance(handler, StoreHandlerTest)
        self.assertIs(handler, default_handler)

        # Select alternate handler for Host with a source value.
        model = models.Host.new(address='127.0.0.1', source='alternate')
        handler = self.manager._get_handler(model)
        alternate_handler = self.manager._handlers_by_name.get('alternate')
        self.assertIsInstance(handler, StoreHandlerTest)
        self.assertIs(handler, alternate_handler)

        # Verify KeyError for unsupported model type.
        model = models.Cluster.new(name='honeynut')
        self.assertRaises(KeyError, self.manager._get_handler, model)

        # Verify KeyError for Host with invalid source value.
        model = models.Host.new(address='127.0.0.1', source='bogus')
        self.assertRaises(KeyError, self.manager._get_handler, model)

    @mock.patch('commissaire_service.storage.StoreHandlerManager._get_handler')
    def test_save(self, get_handler):
        """
        Verify StoreHandlerManager.save() works as intended
        """
        handler = mock.MagicMock()
        get_handler.return_value = handler

        model = models.Host.new(address='127.0.0.1')
        handler._save.return_value = model

        new_model = self.manager.save(model)
        handler._save.assert_called_once_with(model)

        handler.reset_mock()

        model.address = None  # wrong type
        self.assertRaises(models.ValidationError, self.manager.save, model)
        # The input model is validated before calling _save().
        handler._save.assert_not_called()

    @mock.patch('commissaire_service.storage.StoreHandlerManager._get_handler')
    def test_get(self, get_handler):
        """
        Verify StoreHandlerManager.get() works as intended
        """
        handler = mock.MagicMock()
        get_handler.return_value = handler

        model = models.Host.new(address='127.0.0.1')
        handler._get.return_value = model

        new_model = self.manager.get(model)
        handler._get.assert_called_once_with(model)

        handler.reset_mock()

        model.address = None  # wrong type
        self.assertRaises(models.ValidationError, self.manager.get, model)
        # The output model is validated after calling _get().
        handler._get.assert_called_once_with(model)

    @mock.patch('commissaire_service.storage.StoreHandlerManager._get_handler')
    def test_delete(self, get_handler):
        """
        Verify StoreHandlerManager.delete() works as intended
        """
        handler = mock.MagicMock()
        get_handler.return_value = handler

        model = models.Host.new(address='127.0.0.1')

        self.manager.delete(model)
        handler._delete.assert_called_once_with(model)

    @mock.patch('commissaire_service.storage.StoreHandlerManager._get_handler')
    def test_list(self, get_handler):
        """
        Verify StoreHandlerManager.list() works as intended
        """
        handler = mock.MagicMock()
        get_handler.return_value = handler

        host = models.Host.new(address='127.0.0.1')
        handler._list.return_value = models.Hosts.new(hosts=[host])

        list_of_models = self.manager.list(models.Hosts.new())
        self.assertIsInstance(list_of_models, list)
        self.assertEquals(len(list_of_models), 1)
        self.assertIsInstance(list_of_models[0], models.Host)
