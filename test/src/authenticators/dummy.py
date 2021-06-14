# -*- coding: utf-8 -*-

import logging
from moulinette.core import MoulinetteError
from moulinette.authentication import BaseAuthenticator

logger = logging.getLogger("moulinette.authenticator.dummy")

# Dummy authenticator implementation


class Authenticator(BaseAuthenticator):

    """Dummy authenticator used for tests"""

    name = "dummy"

    def __init__(self, *args, **kwargs):
        pass

    def authenticate(self, credentials=None):

        if not credentials == self.name:
            raise MoulinetteError("invalid_password")

        return
