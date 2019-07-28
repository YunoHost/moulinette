# -*- coding: utf-8 -*-

import gnupg
import logging

from moulinette.cache import open_cachefile
from moulinette.core import MoulinetteError

logger = logging.getLogger('moulinette.authenticator')


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

    def __init__(self, name):
        self._name = name

    @property
    def name(self):
        """Return the name of the authenticator instance"""
        return self._name

    # Virtual properties
    # Each authenticator classes must implement these properties.

    """The vendor name of the authenticator"""
    vendor = None

    @property
    def is_authenticated(self):
        """Either the instance is authenticated or not"""
        raise NotImplementedError("derived class '%s' must override this property" %
                                  self.__class__.__name__)

    # Virtual methods
    # Each authenticator classes must implement these methods.

    def authenticate(self, password=None):
        """Attempt to authenticate

        Attempt to authenticate with given password. It should raise an
        AuthenticationError exception if authentication fails.

        Keyword arguments:
            - password -- A clear text password

        """
        raise NotImplementedError("derived class '%s' must override this method" %
                                  self.__class__.__name__)

    # Authentication methods

    def __call__(self, password=None, token=None):
        """Attempt to authenticate

        Attempt to authenticate either with password or with session
        token if 'password' is None. If the authentication succeed, the
        instance is returned and the session is registered for the token
        if 'token' and 'password' are given.
        The token is composed by the session identifier and a session
        hash - to use for encryption - as a 2-tuple.

        Keyword arguments:
            - password -- A clear text password
            - token -- The session token in the form of (id, hash)

        Returns:
            The authenticated instance

        """
        if self.is_authenticated:
            return self
        store_session = True if password and token else False

        if token:
            try:
                # Extract id and hash from token
                s_id, s_hash = token
            except TypeError as e:
                logger.error("unable to extract token parts from '%s' because '%s'", token, e)
                if password is None:
                    raise MoulinetteError('error_see_log')

                logger.info("session will not be stored")
                store_session = False
            else:
                if password is None:
                    # Retrieve session
                    password = self._retrieve_session(s_id, s_hash)

        try:
            # Attempt to authenticate
            self.authenticate(password)
        except MoulinetteError:
            raise
        except Exception as e:
            logger.exception("authentication (name: '%s', vendor: '%s') fails because '%s'",
                             self.name, self.vendor, e)
            raise MoulinetteError('unable_authenticate')

        # Store session
        if store_session:
            try:
                self._store_session(s_id, s_hash, password)
            except Exception as e:
                import traceback
                traceback.print_exc()
                logger.exception("unable to store session because %s", e)
            else:
                logger.debug("session has been stored")

        return self

    # Private methods

    def _open_sessionfile(self, session_id, mode='r'):
        """Open a session file for this instance in given mode"""
        return open_cachefile('%s.asc' % session_id, mode,
                              subdir='session/%s' % self.name)

    def _store_session(self, session_id, session_hash, password):
        """Store a session and its associated password"""
        gpg = gnupg.GPG()
        gpg.encoding = 'utf-8'

        # Encrypt the password using the session hash
        s = str(gpg.encrypt(password, None, symmetric=True, passphrase=session_hash))
        assert len(s), "For some reason GPG can't perform encryption, maybe check /root/.gnupg/gpg.conf or re-run with gpg = gnupg.GPG(verbose=True) ?"

        with self._open_sessionfile(session_id, 'w') as f:
            f.write(s)

    def _retrieve_session(self, session_id, session_hash):
        """Retrieve a session and return its associated password"""
        try:
            with self._open_sessionfile(session_id, 'r') as f:
                enc_pwd = f.read()
        except IOError as e:
            logger.debug("unable to retrieve session", exc_info=1)
            raise MoulinetteError('unable_retrieve_session', exception=e)
        else:
            gpg = gnupg.GPG()
            gpg.encoding = 'utf-8'

            decrypted = gpg.decrypt(enc_pwd, passphrase=session_hash)
            if decrypted.ok is not True:
                error_message = "unable to decrypt password for the session: %s" % decrypted.status
                logger.error(error_message)
                raise MoulinetteError('unable_retrieve_session', exception=error_message)
            return decrypted.data
