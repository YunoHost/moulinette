# -*- coding: utf-8 -*-

import logging
from moulinette.core import MoulinetteError
from moulinette.authentication import BaseAuthenticator

logger = logging.getLogger("moulinette.authenticator.yoloswag")

# Dummy authenticator implementation


class Authenticator(BaseAuthenticator):

    """Dummy authenticator used for tests"""

    name = "yoloswag"

    def __init__(self, *args, **kwargs):
        pass

    def authenticate(self, password=None):

        if not password == self.name:
            raise MoulinetteError("invalid_password")

        return
