# -*- coding: utf-8 -*-

import os
import logging
import hashlib
import hmac

from moulinette.cache import open_cachefile, get_cachedir, cachefile_exists
from moulinette.core import MoulinetteError, MoulinetteAuthenticationError

logger = logging.getLogger("moulinette.authenticator")


# Base Class -----------------------------------------------------------


class BaseAuthenticator(object):

    """Authenticator base representation

    Each authenticators must implement an Authenticator class derived
    from this class which must overrides virtual properties and methods.
    It is used to authenticate and manage session. It implements base
    methods to authenticate with a password or a session token.

    Authenticators configurations are identified by a profile name which
    must be given on instantiation - with the corresponding vendor
    configuration of the authenticator.

    Keyword arguments:
        - name -- The authenticator profile name

    """

    def __init__(self, name, vendor, parameters, extra):
        self._name = name
        self.vendor = vendor
        self.is_authenticated = False
        self.extra = extra

    @property
    def name(self):
        """Return the name of the authenticator instance"""
        return self._name

    # Virtual properties
    # Each authenticator classes must implement these properties.

    """The vendor name of the authenticator"""
    vendor = None

    # Virtual methods
    # Each authenticator classes must implement these methods.

    def authenticate(self, password=None):
        """Attempt to authenticate

        Attempt to authenticate with given password. It should raise an
        AuthenticationError exception if authentication fails.

        Keyword arguments:
            - password -- A clear text password

        """
        raise NotImplementedError(
            "derived class '%s' must override this method" % self.__class__.__name__
        )

    # Authentication methods

    def __call__(self, password=None, token=None):
        """Attempt to authenticate

        Attempt to authenticate either with password or with session
        token if 'password' is None. If the authentication succeed, the
        instance is returned and the session is registered for the token
        if 'token' and 'password' are given.
        The token is composed by the session identifier and a session
        hash (the "true token") - to use for encryption - as a 2-tuple.

        Keyword arguments:
            - password -- A clear text password
            - token -- The session token in the form of (id, hash)

        Returns:
            The authenticated instance

        """
        if self.is_authenticated:
            return self

        #
        # Authenticate using the password
        #
        if password:
            try:
                # Attempt to authenticate
                self.authenticate(password)
            except MoulinetteError:
                raise
            except Exception as e:
                logger.exception(
                    "authentication (name: '%s', vendor: '%s') fails because '%s'",
                    self.name,
                    self.vendor,
                    e,
                )
                raise MoulinetteAuthenticationError("unable_authenticate")

            self.is_authenticated = True

            # Store session for later using the provided (new) token if any
            if token:
                try:
                    s_id, s_token = token
                    self._store_session(s_id, s_token)
                except Exception as e:
                    import traceback

                    traceback.print_exc()
                    logger.exception("unable to store session because %s", e)
                else:
                    logger.debug("session has been stored")

        #
        # Authenticate using the token provided
        #
        elif token:
            try:
                s_id, s_token = token
                # Attempt to authenticate
                self._authenticate_session(s_id, s_token)
            except MoulinetteError:
                raise
            except Exception as e:
                logger.exception(
                    "authentication (name: '%s', vendor: '%s') fails because '%s'",
                    self.name,
                    self.vendor,
                    e,
                )
                raise MoulinetteAuthenticationError("unable_authenticate")
            else:
                self.is_authenticated = True

        #
        # No credentials given, can't authenticate
        #
        else:
            raise MoulinetteAuthenticationError("unable_authenticate")

        return self

    # Private methods

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
