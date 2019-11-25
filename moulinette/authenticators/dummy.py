# -*- coding: utf-8 -*-

import logging
from moulinette.core import MoulinetteError
from moulinette.authenticators import BaseAuthenticator

logger = logging.getLogger("moulinette.authenticator.dummy")

# Dummy authenticator implementation


class Authenticator(BaseAuthenticator):

    """Dummy authenticator used for tests
    """

    vendor = "dummy"

    def __init__(self, name, vendor, parameters, extra):
        logger.debug("initialize authenticator dummy")
        super(Authenticator, self).__init__(name)

    def authenticate(self, password):

        if not password == "Yoloswag":
            raise MoulinetteError("Invalid password!")

        return self
