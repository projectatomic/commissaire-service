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
Test for commissaire_service.service.run_service function.
"""

from . import TestCase, mock
from commissaire_service.service import run_service


class Test_run_service(TestCase):
    """
    Test for the run_service helper function.
    """

    def test_run_service(self):
        """
        Verify run_service creates an instance and calls the instance.run().
        """
        service = mock.MagicMock()
        kwargs = {'test': 'input'}

        run_service(service, kwargs)
        # The instance should be created with the provided kwargs
        service.assert_called_once_with(**kwargs)
        # An the instances run method should have been called
        service.__call__().run.assert_called_once_with()
