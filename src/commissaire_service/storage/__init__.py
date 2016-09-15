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

import fnmatch
import importlib
import json

import commissaire.models as models
from commissaire import constants as C

from commissaire_service.service import CommissaireService, ServiceManager
from commissaire_service.storage.storehandlermanager import (
    StoreHandlerManager, ConfigurationError)


# FIXME This should be moved to a place for utilities.
def read_config_file(path=None):
    """
    Attempts to parse a configuration file, formatted as a JSON object.

    If a config file path is explicitly given, then failure to open the
    file will raise an IOError.  Otherwise a default path is tried, but
    no IOError is raised on failure.  If the file can be opened but not
    parsed, an exception is always raised.

    :param path: Full path to the config file, or None
    :type path: str or None
    :returns: configuration content as a dictionary
    :rtype: dict
    :raises: IOError, TypeError, ValueError
    """
    json_object = {}
    using_default = False

    if path is None:
        path = '/etc/commissaire/commissaire.conf'
        using_default = True

    try:
        with open(path, 'r') as fp:
            json_object = json.load(fp)
        if using_default:
            print('Using configuration in {0}'.format(path))
    except IOError:
        if not using_default:
            raise

    if type(json_object) is not dict:
        raise TypeError(
            '{0}: File content must be a JSON object'.format(path))

    # Special case:
    #
    # In the configuration file, the "authentication-plugin" member
    # can also be specified as a JSON object.  The object must have
    # at least a 'name' member specifying the plugin module name.
    auth_key = 'authentication-plugin'
    auth_plugin = json_object.get(auth_key)
    if type(auth_plugin) is dict:
        if 'name' not in auth_plugin:
            raise ValueError(
                '{0}: "{1}" is missing a "name" member'.format(
                    path, auth_key))

    # Special case:
    #
    # In the configuration file, the "storage-handlers" member can
    # be specified as a JSON object or a list of JSON objects.
    handler_key = 'storage-handlers'
    handler_list = json_object.get(handler_key)
    if type(handler_list) is dict:
        json_object[handler_key] = [handler_list]

    return json_object


class StorageService(CommissaireService):
    """
    Provides access to data stores to other services.
    """

    def __init__(self, exchange_name, connection_url, config_file=None):
        """
        Creates a new StorageService and sets up StoreHandler instances
        according to the config_file.  If config_file is omitted, it will
        try the default location (/etc/commissaire/commissaire.conf).

        :param exchange_name: Name of the topic exchange
        :type exchange_name: str
        :param connection_url: Kombu connection URL
        :type connection_url: str
        :param config_file: Optional configuration file path
        :type config_file: str or None
        """
        queue_kwargs = [ {'routing_key': 'storage.*'} ]
        CommissaireService.__init__(
            self, exchange_name, connection_url, queue_kwargs)

        self._manager = StoreHandlerManager()

        # Collect all model types in commissaire.models.
        self._model_types = {k: v for k, v in models.__dict__.items()
                             if isinstance(v, type)
                             and issubclass(v, models.Model)}

        config_data = read_config_file(config_file)
        store_handlers = config_data.get('storage-handlers', [])

        # Configure store handlers from user data.
        if len(store_handlers) == 0:
            store_handlers = [
                C.DEFAULT_ETCD_STORE_HANDLER
            ]
        for config in store_handlers:
            self.register_store_handler(config)

    def register_store_handler(self, config):
        """
        Registers a new store handler type after extracting and validating
        information required for registration from the configuration data.

        :param config: A configuration dictionary
        :type config: dict
        """
        if type(config) is not dict:
            raise ConfigurationError(
                'Store handler format must be a JSON object, got a '
                '{} instead: {}'.format(type(config).__name__, config))

        # Import the handler class.
        try:
            module_name = config.pop('name')
        except KeyError:
            raise ConfigurationError(
                'Store handler configuration missing "name" key: '
                '{}'.format(config))
        try:
            module = importlib.import_module(module_name)
            handler_type = getattr(module, 'StoreHandler')
        except ImportError:
            raise ConfigurationError(
                'Invalid store handler module name: {}'.format(module_name))

        # Match model types to type name patterns.
        matched_types = set()
        for pattern in config.pop('models', ['*']):
            matches = fnmatch.filter(self._model_types.keys(), pattern)
            if not matches:
                raise ConfigurationError(
                    'No match for model: {}'.format(pattern))
            matched_types.update([self._model_types[name] for name in matches])

        self._manager.register_store_handler(
            handler_type, config, *matched_types)

    def _build_model(self, model_type_name, model_json_data):
        """
        Builds a model instance from a type name and JSON representation.

        :param model_type_name: Model type for the JSON data
        :type model_type_name: str
        :param model_json_data: JSON representation of a model
        :type model_json_data: str
        :returns: a model instance
        :rtype: commissaire_service.storage.models.Model
        """
        model_type = self._model_types[model_type_name]
        return model_type.new(**json.loads(model_json_data))

    def on_save(self, message, model_type_name, model_json_data):
        """
        Handler for the "storage.save" routing key.

        Takes model data which may have omitted optional fields, applies
        default values as needed, and saves it to a store; then returns the
        full saved JSON data.

        :param message: A message instance
        :type message: kombu.message.Message
        :param model_type_name: Model type for the JSON data
        :type model_type_name: str
        :param model_json_data: JSON representation of a model
        :type model_json_data: str
        :returns: full JSON representation of the model
        :rtype: str
        """
        model_instance = self._build_model(model_type_name, model_json_data)
        saved_model_instance = self._manager.save(model_instance)
        return saved_model_instance.to_json()

    def on_get(self, message, model_type_name, model_json_data):
        """
        Handler for the "storage.get" routing key.

        Returns JSON data from a store.  The input model data need only
        have enough information to uniquely identify the model.

        :param message: A message instance
        :type message: kombu.message.Message
        :param model_type_name: Model type for the JSON data
        :type model_type_name: str
        :param model_json_data: JSON identification of a model
        :type model_json_data: str
        :returns: full JSON representation of the model
        :rtype: str
        """
        model_instance = self._build_model(model_type_name, model_json_data)
        full_model_instance = self._manager.get(model_instance)
        return full_model_instance.to_json()

    def on_delete(self, message, model_type_name, model_json_data):
        """
        Handler for the "storage.delete" routing key.

        Deletes JSON data from a store.  The input model data need only
        have enough information to uniquely identify the model.

        :param message: A message instance
        :type message: kombu.message.Message
        :param model_type_name: Model type for the JSON data
        :type model_type_name: str
        :param model_json_data: JSON identification of a model
        :type model_json_data: str
        """
        model_instance = self._build_model(model_type_name, model_json_data)
        self._manager.delete(model_instance)

    def on_list(self, message, model_type_name):
        """
        Handler for the "storage.list" routing key.

        Lists available data for the given model type from a store.

        :param message: A message instance
        :type message: kombu.message.Message
        :param model_type_name: Model type for the JSON data
        :type model_type_name: str
        :returns: a list of model representations as JSON strings
        :rtype: list
        """
        model_type = self._model_types[model_type_name]
        model_list = self._manager.list(model_type.new())
        return [model_instance.to_json() for model_instance in model_list]


if __name__ == '__main__':
    try:
        service = StorageService(
            exchange_name='commissaire',
            connection_url='redis://127.0.0.1:6379/',
            config_file=None)
        service.run()
    except KeyboardInterrupt:
        pass
