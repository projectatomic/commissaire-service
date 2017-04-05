# Copyright (C) 2016-2017  Red Hat, Inc
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
import json

import commissaire.models as models

from commissaire import constants as C
from commissaire.storage import StoreHandlerBase
from commissaire.util.config import (ConfigurationError, import_plugin)

from commissaire_service.service import (
    CommissaireService, add_service_arguments)


class StorageService(CommissaireService):
    """
    Provides access to data stores to other services.
    """

    #: Default configuration file
    _default_config_file = '/etc/commissaire/storage.conf'

    def __init__(self, exchange_name, connection_url, config_file=None):
        """
        Creates a new StorageService and sets up StoreHandler instances
        according to the config_file.  If config_file is omitted, it will
        try the default location (/etc/commissaire/storage.conf).

        :param exchange_name: Name of the topic exchange
        :type exchange_name: str
        :param connection_url: Kombu connection URL
        :type connection_url: str
        :param config_file: Optional configuration file path
        :type config_file: str or None
        """
        queue_kwargs = [
            {'routing_key': 'storage.*'},
        ]

        super().__init__(
            exchange_name,
            connection_url,
            queue_kwargs,
            config_file=config_file)

        # Store handler definitions by name.
        # { name : ( handler_type, config, ( model_type, ...) ) }
        self._definitions_by_name = {}

        # Storage handler definitions for particular model types.
        # { model_type : ( handler_type, config, ( model_type, ...) ) }
        self._definitions_by_model_type = {}

        # Store handler instances with no associated model types.
        # Instantiated on-demand from self._definitions_by_name.
        # { name : handler_instance }
        self._handlers_by_name = {}

        # Storage handler instances for particular model types.
        # Instantiated on-demand from self._definitions_by_model_type.
        # { model_type : handler_instance }
        self._handlers_by_model_type = {}

        # Collect all model types in commissaire.models.
        self._model_types = {k: v for k, v in models.__dict__.items()
                             if isinstance(v, type) and
                             issubclass(v, models.Model)}

        store_handlers = self._config_data.get('storage_handlers', [])

        # Configure store handlers from user data.
        if len(store_handlers) == 0:
            store_handlers = [
                C.DEFAULT_ETCD_STORE_HANDLER
            ]
        for config in store_handlers:
            self._register_store_handler(config)

    def _register_store_handler(self, config):
        """
        Registers a new store handler type after extracting and validating
        information required for registration from the configuration data.

        This will raise a ConfigurationError if any configuration parameters
        are invalid.

        :param config: A configuration dictionary
        :type config: dict
        :raises: commissaire.util.config.ConfigurationError
        """
        if type(config) is not dict:
            raise ConfigurationError(
                'Store handler format must be a JSON object, got a '
                '{} instead: {}'.format(type(config).__name__, config))

        # Import the handler class.
        try:
            module_name = config.pop('type')
        except KeyError:
            raise ConfigurationError(
                'Store handler configuration missing "type" key: '
                '{}'.format(config))
        handler_type = import_plugin(
            module_name, 'commissaire.storage', StoreHandlerBase)

        # Match model types to type name patterns.
        matched_types = set()
        for pattern in config.pop('models', ['*']):
            matches = fnmatch.filter(self._model_types.keys(), pattern)
            if not matches:
                raise ConfigurationError(
                    'No match for model: {}'.format(pattern))
            matched_types.update([self._model_types[name] for name in matches])

        handler_type.check_config(config)

        definition = (handler_type, config, matched_types)

        name = config.get('name', '').strip()
        if not name:
            # If the store handler definition was not given a
            # name, derive a unique name from its module name.
            suffix = 1
            name = handler_type.__module__
            while name in self._definitions_by_name:
                name = '{}-{}'.format(handler_type.__module__, suffix)
                suffix += 1
            config['name'] = name

        if name in self._definitions_by_name:
            raise ConfigurationError(
                'Duplicate storage handlers named "{}"'.format(name))

        for mt in matched_types:
            if mt in self._definitions_by_model_type:
                conflicting_type, _, _ = \
                    self._definitions_by_model_type[mt]
                raise ConfigurationError(
                    'Model "{}" already assigned to "{}"'.format(
                        getattr(mt, '__name__', '?'),
                        getattr(conflicting_type, '__module__', '?')))

        # Add definition after all checks pass.
        self._definitions_by_name[name] = definition
        new_items = {mt: definition for mt in matched_types}
        self._definitions_by_model_type.update(new_items)

    def _create_handler(self, definition):
        """
        Creates a handler instance from a handler definition, and adds the
        handler instance to various internal data structures.
        """
        handler_type, config, model_types = definition
        handler = handler_type(config)
        handler.notify.connect(self._exchange, self._channel)
        self._handlers_by_name[config['name']] = handler
        new_items = {mt: handler for mt in model_types}
        self._handlers_by_model_type.update(new_items)
        return handler

    def _get_handler(self, model):
        """
        Looks up, and if necessary instantiates, a StoreHandler instance
        for the given model.  Raises KeyError if no handler is registered
        for that type of model.
        """
        handler = None
        model_type = type(model)

        # Special case: If the model is a Host, check for a handler name
        #               in its "source" attribute and use the definition
        #               registered under that name.
        if model_type is models.Host:
            name = getattr(model, 'source', '').strip()
            if name:
                handler = self._handlers_by_name.get(name)
                if handler is None:
                    # Let this raise a KeyError if the lookup fails.
                    definition = self._definitions_by_name[name]
                    handler = self._create_handler(definition)

        if handler is None:
            handler = self._handlers_by_model_type.get(model_type)

        if handler is None:
            # Let this raise a KeyError if the registry lookup fails.
            definition = self._definitions_by_model_type[model_type]
            handler = self._create_handler(definition)

        return handler

    def _build_model(self, model_type_name, model_json_data):
        """
        Builds a model instance from a type name and model data, which may
        either be a dictionary or a JSON-parsable string.

        :param model_type_name: Model type for the JSON data
        :type model_type_name: str
        :param model_json_data: JSON representation of a model
        :type model_json_data: dict or str
        :returns: a model instance
        :rtype: commissaire_service.storage.models.Model
        """
        if isinstance(model_json_data, str):
            model_json_data = json.loads(model_json_data)
            if not isinstance(model_json_data, dict):
                raise json.decoder.JSONDecodeError(
                    'Model data expected to be a JSON object')
        model_type = self._model_types[model_type_name]
        return model_type.new(**model_json_data)

    def _save_model(self, model_instance):
        """
        Saves data to a store and returns back a saved model.

        :param model_instance: Model instance to save
        :type model_instance: commissaire.model.Model
        :returns: The saved model instance
        :rtype: commissaire.model.Model
        """
        handler = self._get_handler(model_instance)
        # Validate before saving
        try:
            model_instance._validate()
        except models.ValidationError as ve:
            self.logger.error(ve.args[0])
            self.logger.error(ve.args[1])
            raise ve
        self.logger.debug('> SAVE {}'.format(model_instance))
        model_instance = handler._save(model_instance)
        self.logger.debug('< SAVE {}'.format(model_instance))
        return model_instance

    def _get_model(self, model_instance):
        """
        Returns data from a store and returns back a model.

        :param model_instance: Model instance to search and get
        :type model_instance: commissaire.model.Model
        :returns: The saved model instance
        :rtype: commissaire.model.Model
        """
        handler = self._get_handler(model_instance)
        self.logger.debug('> GET {}'.format(model_instance))
        model_instance = handler._get(model_instance)
        # Validate after getting
        try:
            model_instance._validate()
        except models.ValidationError as ve:
            self.logger.error(ve.args[0])
            self.logger.error(ve.args[1])
            raise ve
        self.logger.debug('< GET {}'.format(model_instance))
        return model_instance

    def _delete_model(self, model_instance):
        """
        Deletes data from a store.

        :param model_instance: Model instance to delete
        :type model_instance:
        """
        handler = self._get_handler(model_instance)
        self.logger.debug('> DELETE {}'.format(model_instance))
        handler._delete(model_instance)

    def _list_models(self, model_instance):
        """
        Lists data at a location in a store and returns back model instances.

        :param model_instance: List model instance indicating the data type
                               to search for
        :type model_instance: commissaire.model.ListModel
        :returns: A list of models
        :rtype: list
        """
        handler = self._get_handler(model_instance)
        self.logger.debug('> LIST {}'.format(model_instance))
        model_instance = handler._list(model_instance)
        self.logger.debug('< LIST {}'.format(model_instance))
        return getattr(model_instance, model_instance._list_attr, [])

    def on_save(self, message, model_type_name, model_json_data):
        """
        Handler for the "storage.save" routing key.

        Takes model data which may have omitted optional fields, applies
        default values as needed, and saves it to a store; then returns the
        full saved JSON data.

        The JSON data argument may also be a list of models of the same type,
        which returns a list of full models; equivalent to calling the method
        once for each list item, with fewer bus messages.

        :param message: A message instance
        :type message: kombu.message.Message
        :param model_type_name: Model type for the JSON data
        :type model_type_name: str
        :param model_json_data: JSON representation of one or more models
        :type model_json_data: dict, str, [dict, ...] or [str, ...]
        :returns: full dict representation of the model(s)
        :rtype: dict or [dict, ...]
        """
        if isinstance(model_json_data, list):
            # Build all models first so we catch invalid input before
            # touching permanent storage.
            models = [self._build_model(model_type_name, x)
                      for x in model_json_data]
            return [self._save_model(x).to_dict() for x in models]
        else:
            model = self._build_model(model_type_name, model_json_data)
            return self._save_model(model).to_dict()

    def on_get(self, message, model_type_name, model_json_data):
        """
        Handler for the "storage.get" routing key.

        Returns JSON data from a store.  The input model data need only
        have enough information to uniquely identify the model.

        The JSON data argument may also be a list of models of the same type,
        which returns a list of full models; equivalent to calling the method
        once for each list item, with fewer bus messages.

        :param message: A message instance
        :type message: kombu.message.Message
        :param model_type_name: Model type for the JSON data
        :type model_type_name: str
        :param model_json_data: JSON identification of one or more models
        :type model_json_data: dict, str, [dict, ...] or [str, ...]
        :returns: full dict representation of the model(s)
        :rtype: dict or [dict, ...]
        """
        if isinstance(model_json_data, list):
            # Build all models first so we catch invalid input before
            # touching permanent storage.
            models = [self._build_model(model_type_name, x)
                      for x in model_json_data]
            return [self._get_model(x).to_dict() for x in models]
        else:
            model = self._build_model(model_type_name, model_json_data)
            return self._get_model(model).to_dict()

    def on_delete(self, message, model_type_name, model_json_data):
        """
        Handler for the "storage.delete" routing key.

        Deletes JSON data from a store.  The input model data need only
        have enough information to uniquely identify the model.

        The JSON data argument may also be a list of models of the same type;
        equivalent to calling the method once for each list item, with fewer
        bus messages.

        :param message: A message instance
        :type message: kombu.message.Message
        :param model_type_name: Model type for the JSON data
        :type model_type_name: str
        :param model_json_data: JSON identification of one or more models
        :type model_json_data: dict, str, [dict, ...] or [str, ...]
        """
        if not isinstance(model_json_data, list):
            model_json_data = [model_json_data]
        # Build all models first so we catch invalid input before touching
        # permanent storage.
        models = [self._build_model(model_type_name, x)
                  for x in model_json_data]
        for model_instance in models:
            self._delete_model(model_instance)

    def on_list(self, message, model_type_name):
        """
        Handler for the "storage.list" routing key.

        Lists available data for the given model type from a store.

        :param message: A message instance
        :type message: kombu.message.Message
        :param model_type_name: Model type for the JSON data
        :type model_type_name: str
        :returns: a list of model representations as dicts
        :rtype: list
        """
        model_type = self._model_types[model_type_name]
        model_list = self._list_models(model_type.new())
        return [model_instance.to_dict() for model_instance in model_list]

    def on_list_store_handlers(self, message):
        """
        Handler for the "storage.list_store_handlers" routing key.

        Returns a list of registered store handlers as dictionaries.
        Each dictionary contains the following:

           'handler_type' : Type name of the store handler
           'config'       : Dictionary of configuration values
           'model_types'  : List of model type names handled

        :param message: A message instance
        :type message: kombu.message.Message
        """
        result = []
        handlers = self._definitions_by_name.values()
        for handler_type, config, model_types in handlers:
            model_types = [mt.__name__ for mt in model_types]
            model_types.sort()  # Just for readability
            result.append({
                'handler_type': handler_type.__name__,
                'config': config,
                'model_types': model_types
            })
        return result


def main():  # pragma: no cover
    """
    Main entry point.
    """
    import argparse

    parser = argparse.ArgumentParser()
    add_service_arguments(parser)

    args = parser.parse_args()

    try:
        service = StorageService(
            exchange_name=args.bus_exchange,
            connection_url=args.bus_uri,
            config_file=args.config_file)
        service.run()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':  # pragma: no cover
    main()
