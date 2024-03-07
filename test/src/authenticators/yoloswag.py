# -*- coding: utf-8 -*-

import logging
from moulinette.utils.text import random_ascii
from moulinette.core import MoulinetteError, MoulinetteAuthenticationError
from moulinette.authentication import BaseAuthenticator

logger = logging.getLogger("moulinette.authenticator.yoloswag")

# Dummy authenticator implementation

session_secret = random_ascii()


class Authenticator(BaseAuthenticator):
    """Dummy authenticator used for tests"""

    name = "yoloswag"

    def __init__(self, *args, **kwargs):
        pass

    def _authenticate_credentials(self, credentials=None):
        if not credentials == self.name:
            raise MoulinetteError("invalid_password", raw_msg=True)

        return

    def set_session_cookie(self, infos):
        from bottle import response

        assert isinstance(infos, dict)

        # This allows to generate a new session id or keep the existing one
        current_infos = self.get_session_cookie(raise_if_no_session_exists=False)
        new_infos = {"id": current_infos["id"]}
        new_infos.update(infos)

        response.set_cookie(
            "moulitest",
            new_infos,
            secure=True,
            secret=session_secret,
            httponly=True,
            # samesite="strict", # Bottle 0.12 doesn't support samesite, to be added in next versions
        )

    def get_session_cookie(self, raise_if_no_session_exists=True):
        from bottle import request

        try:
            infos = request.get_cookie("moulitest", secret=session_secret, default={})
        except Exception:
            if not raise_if_no_session_exists:
                return {"id": random_ascii()}
            raise MoulinetteAuthenticationError("unable_authenticate")

        if not infos and raise_if_no_session_exists:
            raise MoulinetteAuthenticationError("unable_authenticate")

        if "id" not in infos:
            infos["id"] = random_ascii()

        return infos

    def delete_session_cookie(self):
        from bottle import response

        response.set_cookie("moulitest", "", max_age=-1)
        response.delete_cookie("moulitest")
