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

    def _authenticate_credentials(self, credentials=None):

        if not credentials == self.name:
            raise MoulinetteError("invalid_password", raw_msg=True)

        return
