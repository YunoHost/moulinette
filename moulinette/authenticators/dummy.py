# -*- coding: utf-8 -*-

import logging
from moulinette.core import MoulinetteError
from moulinette.authenticators import BaseAuthenticator

logger = logging.getLogger("moulinette.core")

# Dummy authenticator implementation


class Authenticator(BaseAuthenticator):

    """Dummy authenticator used for tests"""

    vendor = "dummy"

    def __init__(self, name, vendor, parameters, extra):
        logger.debug("initialize authenticator dummy")

        super(Authenticator, self).__init__(name, vendor, parameters, extra)

    def authenticate(self, password=None):

        if not password == self.name:
            raise MoulinetteError("invalid_password")

        return self
