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

import os
import binascii
import logging
import json
from moulinette.core import MoulinetteError, MoulinetteAuthenticationError
from moulinette.authentication import BaseAuthenticator

logger = logging.getLogger("moulinette.authenticator.yoloswag")

# Dummy authenticator implementation


def random_ascii(length: int = 40) -> str:
    """Return a random ascii string"""
    return binascii.hexlify(os.urandom(length)).decode("ascii")[:length]


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
            json.dumps(new_infos),
            secure=True,
            secret=session_secret,
            httponly=True,
            # samesite="strict", # Bottle 0.12 doesn't support samesite, to be added in next versions
        )

    def get_session_cookie(self, raise_if_no_session_exists=True):
        from bottle import request

        try:
            infos = request.get_cookie("moulitest", secret=session_secret, default={})
            infos = json.loads(infos)
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
