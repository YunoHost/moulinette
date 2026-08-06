#!/usr/bin/env python3
#
# Copyright (c) 2024 YunoHost Contributors
#
# This file is part of YunoHost (see https://yunohost.org)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#

import logging

from moulinette.core import MoulinetteAuthenticationError, MoulinetteError

logger = logging.getLogger("moulinette.authenticator")


# Base Class -----------------------------------------------------------


class BaseAuthenticator:
    """Authenticator base representation

    Each authenticators must implement an Authenticator class derived
    from this class which must overrides virtual properties and methods.
    It is used to authenticate and manage session. It implements base
    methods to authenticate with credentials or a session token.

    Authenticators configurations are identified by a profile name which
    must be given on instantiation - with the corresponding vendor
    configuration of the authenticator.

    """

    # Virtual methods
    # Each authenticator classes must implement these methods.

    def authenticate_credentials(self, credentials):
        try:
            # Attempt to authenticate
            auth_info = self._authenticate_credentials(credentials) or {}
        except MoulinetteError:
            raise
        except Exception as e:
            logger.exception(f"authentication {self.name} failed because '{e}'")
            raise MoulinetteAuthenticationError("unable_authenticate")

        return auth_info
