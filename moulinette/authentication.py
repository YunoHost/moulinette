# -*- coding: utf-8 -*-

import logging

from moulinette.core import MoulinetteError, MoulinetteAuthenticationError

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
