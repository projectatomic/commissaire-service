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
"""
Custodia based StoreHandler.
"""

import requests

from urllib.parse import quote

from commissaire.bus import StorageLookupError
from commissaire.storage import StoreHandlerBase
from commissaire.util.unixadapter import UnixAdapter


HTTP_SOCKET_PREFIX = 'http+unix://'
DEFAULT_SOCKET_PATH = '/var/run/custodia/custodia.sock'


class CustodiaStoreHandler(StoreHandlerBase):
    """
    Handler for securely storing secrets via a local Custodia service.
    """

    # Connection should be nearly instantaneous.
    CUSTODIA_TIMEOUT = (1.0, 5.0)  # seconds

    @classmethod
    def check_config(cls, config):
        """
        This store handler has no configuration checks.
        """
        pass

    def __init__(self, config):
        """
        Creates a new instance of CustodiaStoreHandler.
        :param config: Not applicable to this handler
        :type config: None
        """
        super().__init__(config)

        self.session = requests.Session()
        self.session.headers['REMOTE_USER'] = 'commissaire'
        self.session.mount(HTTP_SOCKET_PREFIX, UnixAdapter())
        socket_path = config.get('socket_path', DEFAULT_SOCKET_PATH)
        self.socket_url = HTTP_SOCKET_PREFIX + quote(socket_path, safe='')

    def _build_key_container_url(self, model_instance):
        """
        Builds a Custodia key container URL for the given SecretModel.

        :param model_instance: A SecretModel instance.
        :type model_instance: commissaire.model.SecretModel
        :returns: A URL string
        :rtype: str
        """
        return '{}/secrets/{}/'.format(
            self.socket_url, model_instance._key_container)

    def _build_key_url(self, model_instance):
        """
        Builds a Custodia key URL for the given SecretModel.

        :param model_instance: A SecretModel instance.
        :type model_instance: commissaire.model.SecretModel
        :returns: A URL string
        :rtype: str
        """
        base_url = self._build_key_container_url(model_instance)
        return base_url + model_instance.primary_key

    def _save(self, model_instance):
        """
        Submits a serialized SecretModel string to Custodia and returns the
        model instance.

        :param model_instance: SecretModel instance to save.
        :type model_instance: commissaire.model.SecretModel
        :returns: The saved model instance.
        :rtype: commissaire.model.SecretModel
        :raises requests.HTTPError: if the request fails
        """
        # Create a key container for the model.  If it already exists,
        # catch the failure and move on.  This operation should really
        # be idempotent, but Custodia returns a 409 Conflict.
        # (see https://github.com/latchset/custodia/issues/206)
        try:
            url = self._build_key_container_url(model_instance)

            response = self.session.request(
                'POST', url, timeout=self.CUSTODIA_TIMEOUT)
            response.raise_for_status()
        except requests.HTTPError as error:
            # XXX bool(response) defers to response.ok, which is a misfeature.
            #     Have to explicitly test "if response is None" to know if the
            #     object is there.
            have_response = response is not None
            if not (have_response and error.response.status_code == 409):
                raise error

        data = model_instance.to_json()
        headers = {
            'Content-Type': 'application/octet-stream',
            'Content-Length': str(len(data))
        }
        url = self._build_key_url(model_instance)

        response = self.session.request(
            'PUT', url, headers=headers, data=data,
            timeout=self.CUSTODIA_TIMEOUT)
        response.raise_for_status()

        return model_instance

    def _get(self, model_instance):
        """
        Retrieves a serialized SecretModel string from Custodia and constructs
        a model instance.

        :param model_instance: SecretModel instance to search and get.
        :type model_instance: commissaire.model.SecretModel
        :returns: The saved model instance.
        :rtype: commissaire.model.SecretModel
        :raises StorageLookupError: if data lookup fails (404 Not Found)
        :raises requests.HTTPError: if the request fails (other than 404)
        """
        headers = {
            'Accept': 'application/octet-stream'
        }
        url = self._build_key_url(model_instance)

        try:
            response = self.session.request(
                'GET', url, headers=headers,
                timeout=self.CUSTODIA_TIMEOUT)
            response.raise_for_status()

            return model_instance.new(**response.json())
        except requests.HTTPError as error:
            # XXX bool(response) defers to response.ok, which is a misfeature.
            #     Have to explicitly test "if response is None" to know if the
            #     object is there.
            have_response = response is not None
            if have_response and error.response.status_code == 404:
                raise StorageLookupError(str(error), model_instance)
            else:
                raise error

    def _delete(self, model_instance):
        """
        Deletes a serialized SecretModel string from Custodia.

        :param model_instance: SecretModel instance to delete.
        :type model_instance: commissaire.model.SecretModel
        :raises StorageLookupError: if data lookup fails (404 Not Found)
        :raises requests.HTTPError: if the request fails (other than 404)
        """
        url = self._build_key_url(model_instance)

        try:
            response = self.session.request(
                'DELETE', url, timeout=self.CUSTODIA_TIMEOUT)
            response.raise_for_status()
        except requests.HTTPError as error:
            # XXX bool(response) defers to response.ok, which is a misfeature.
            #     Have to explicitly test "if response is None" to know if the
            #     object is there.
            have_response = response is not None
            if have_response and error.response.status_code == 404:
                raise StorageLookupError(str(error), model_instance)
            else:
                raise error
