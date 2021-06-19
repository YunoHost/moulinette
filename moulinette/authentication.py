# -*- coding: utf-8 -*-

import os
import logging
import hashlib
import hmac

from moulinette.utils.text import random_ascii
from moulinette.cache import open_cachefile, get_cachedir, cachefile_exists
from moulinette.core import MoulinetteError, MoulinetteAuthenticationError

logger = logging.getLogger("moulinette.authenticator")


# Base Class -----------------------------------------------------------


class BaseAuthenticator(object):

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

    def authenticate_credentials(self, credentials, store_session=False):

        try:
            # Attempt to authenticate
            self._authenticate_credentials(credentials)
        except MoulinetteError:
            raise
        except Exception as e:
            logger.exception(f"authentication {self.name} failed because '{e}'")
            raise MoulinetteAuthenticationError("unable_authenticate")

        # Store session for later using the provided (new) token if any
        if store_session:
            try:
                s_id = random_ascii()
                s_token = random_ascii()
                self._store_session(s_id, s_token)
            except Exception as e:
                import traceback

                traceback.print_exc()
                logger.exception(f"unable to store session because {e}")
            else:
                logger.debug("session has been stored")

    def _authenticate_credentials(self, credentials=None):
        """Attempt to authenticate

        Attempt to authenticate with given credentials. It should raise an
        AuthenticationError exception if authentication fails.

        Keyword arguments:
            - credentials -- A string containing the credentials to be used by the authenticator

        """
        raise NotImplementedError(
            "derived class '%s' must override this method" % self.__class__.__name__
        )

    def _open_sessionfile(self, session_id, mode="r"):
        """Open a session file for this instance in given mode"""
        return open_cachefile(
            "%s.asc" % session_id, mode, subdir="session/%s" % self.name
        )

    def _session_exists(self, session_id):
        """Check a session exists"""
        return cachefile_exists("%s.asc" % session_id, subdir="session/%s" % self.name)

    def _store_session(self, session_id, session_token):
        """Store a session to be able to use it later to reauthenticate"""

        # We store a hash of the session_id and the session_token (the token is assumed to be secret)
        to_hash = "{id}:{token}".format(id=session_id, token=session_token).encode()
        hash_ = hashlib.sha256(to_hash).hexdigest()
        with self._open_sessionfile(session_id, "w") as f:
            f.write(hash_)

    def authenticate_session(self, s_id, s_token):
        try:
            # Attempt to authenticate
            self._authenticate_session(s_id, s_token)
        except MoulinetteError:
            raise
        except Exception as e:
            logger.exception(f"authentication {self.name} failed because '{e}'")
            raise MoulinetteAuthenticationError("unable_authenticate")

    def _authenticate_session(self, session_id, session_token):
        """Checks session and token against the stored session token"""
        if not self._session_exists(session_id):
            raise MoulinetteAuthenticationError("session_expired")
        try:
            # FIXME : shouldn't we also add a check that this session file
            # is not too old ? e.g. not older than 24 hours ? idk...

            with self._open_sessionfile(session_id, "r") as f:
                stored_hash = f.read()
        except IOError as e:
            logger.debug("unable to retrieve session", exc_info=1)
            raise MoulinetteAuthenticationError("unable_retrieve_session", exception=e)
        else:
            #
            # session_id (or just id) : This is unique id for the current session from the user. Not too important
            # if this info gets stolen somehow. It is stored in the client's side (browser) using regular cookies.
            #
            # session_token (or just token) : This is a secret info, like some sort of ephemeral password,
            # used to authenticate the session without the user having to retype the password all the time...
            #    - It is generated on our side during the initial auth of the user (which happens with the actual admin password)
            #    - It is stored on the client's side (browser) using (signed) cookies.
            #    - We also store it on our side in the form of a hash of {id}:{token} (c.f. _store_session).
            #      We could simply store the raw token, but hashing it is an additonal low-cost security layer
            #      in case this info gets exposed for some reason (e.g. bad file perms for reasons...)
            #
            # When the user comes back, we fetch the session_id and session_token from its cookies. Then we
            # re-hash the {id}:{token} and compare it to the previously stored hash for this session_id ...
            # It it matches, then the user is authenticated. Otherwise, the token is invalid.
            #
            to_hash = "{id}:{token}".format(id=session_id, token=session_token).encode()
            hash_ = hashlib.sha256(to_hash).hexdigest()

            if not hmac.compare_digest(hash_, stored_hash):
                raise MoulinetteAuthenticationError("invalid_token")
            else:
                return

    def _clean_session(self, session_id):
        """Clean a session cache

        Remove cache for the session 'session_id' and for this authenticator profile

        Keyword arguments:
            - session_id -- The session id to clean
        """
        sessiondir = get_cachedir("session")

        try:
            os.remove(os.path.join(sessiondir, self.name, "%s.asc" % session_id))
        except OSError:
            pass
