# -*- coding: utf-8 -*-

import os
import sys
import time
import gettext
import logging

from .helpers import colorize

# Package manipulation -------------------------------------------------

def install_i18n(namespace=None):
    """Install internationalization

    Install translation based on the package's default gettext domain or
    on 'namespace' if provided.

    Keyword arguments:
        - namespace -- The namespace to initialize i18n for

    """
    if namespace:
        try:
            t = gettext.translation(namespace, pkg.localedir)
        except IOError:
            # TODO: Log error
            return
        else:
            t.install()
    else:
        gettext.install('moulinette', pkg.localedir)

class Package(object):
    """Package representation and easy access methods

    Initialize directories and variables for the package and give them
    easy access.

    Keyword arguments:
        - _from_source -- Either the package is running from source or
            not (only for debugging)

    """
    def __init__(self, _from_source=False):
        if _from_source:
            import sys
            basedir = os.path.abspath(os.path.dirname(sys.argv[0]) +'/../')

            # Set local directories
            self._datadir = '%s/data' % basedir
            self._libdir = '%s/lib' % basedir
            self._localedir = '%s/po' % basedir
            self._cachedir = '%s/cache' % basedir
        else:
            import package

            # Set system directories
            self._datadir = package.datadir
            self._libdir = package.libdir
            self._localedir = package.localedir
            self._cachedir = package.cachedir

    def __setattr__(self, name, value):
        if name[0] == '_' and self.__dict__.has_key(name):
            # Deny reassignation of package directories
            raise TypeError("cannot reassign constant '%s'")
        self.__dict__[name] = value


    ## Easy access to package directories

    @property
    def datadir(self):
        """Return the data directory of the package"""
        return self._datadir

    @property
    def libdir(self):
        """Return the lib directory of the package"""
        return self._libdir

    @property
    def localedir(self):
        """Return the locale directory of the package"""
        return self._localedir

    @property
    def cachedir(self):
        """Return the cache directory of the package"""
        return self._cachedir


    ## Additional methods

    def get_cachedir(self, subdir='', make_dir=True):
        """Get the path to a cache directory

        Return the path to the cache directory from an optional
        subdirectory and create it if needed.

        Keyword arguments:
            - subdir -- A cache subdirectory
            - make_dir -- False to not make directory if it not exists

        """
        path = os.path.join(self.cachedir, subdir)

        if make_dir and not os.path.isdir(path):
            os.makedirs(path)
        return path

    def open_cachefile(self, filename, mode='r', **kwargs):
        """Open a cache file and return a stream

        Attempt to open in 'mode' the cache file 'filename' from the
        default cache directory and in the subdirectory 'subdir' if
        given. Directories are created if needed and a stream is
        returned if the file can be written.

        Keyword arguments:
            - filename -- The cache filename
            - mode -- The mode in which the file is opened
            - **kwargs -- Optional arguments for get_cachedir

        """
        # Set make_dir if not given
        kwargs['make_dir'] = kwargs.get('make_dir',
                                        True if mode[0] == 'w' else False)
        return open('%s/%s' % (self.get_cachedir(**kwargs), filename), mode)


# Authenticators -------------------------------------------------------

import ldap
import gnupg

class AuthenticationError(Exception):
    pass

class _BaseAuthenticator(object):

    def __init__(self, name):
        self._name = name

    @property
    def name(self):
        """Return the name of the authenticator instance"""
        return self._name


    ## Virtual properties
    # Each authenticator classes must implement these properties.

    """The vendor of the authenticator"""
    vendor = None

    @property
    def is_authenticated(self):
        """Either the instance is authenticated or not"""
        raise NotImplementedError("derived class '%s' must override this property" % \
                                      self.__class__.__name__)


    ## Virtual methods
    # Each authenticator classes must implement these methods.

    def authenticate(password=None):
        """Attempt to authenticate

        Attempt to authenticate with given password. It should raise an
        AuthenticationError exception if authentication fails.

        Keyword arguments:
            - password -- A clear text password

        """
        raise NotImplementedError("derived class '%s' must override this method" % \
                                      self.__class__.__name__)


    ## Authentication methods

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
            except TypeError:
                if not password:
                    raise MoulinetteError(22, _("Invalid format for token"))
                else:
                    # TODO: Log error
                    store_session = False
            else:
                if password is None:
                    # Retrieve session
                    password = self._retrieve_session(s_id, s_hash)

        try:
            # Attempt to authenticate
            self.authenticate(password)
        except AuthenticationError as e:
            raise MoulinetteError(13, str(e))
        except Exception as e:
            logging.error("authentication (name: '%s', type: '%s') fails: %s" % \
                              (self.name, self.vendor, e))
            raise MoulinetteError(13, _("Unable to authenticate"))

        # Store session
        if store_session:
            self._store_session(s_id, s_hash, password)

        return self


    ## Private methods

    def _open_sessionfile(self, session_id, mode='r'):
        """Open a session file for this instance in given mode"""
        return pkg.open_cachefile('%s.asc' % session_id, mode,
                                  subdir='session/%s' % self.name)

    def _store_session(self, session_id, session_hash, password):
        """Store a session and its associated password"""
        gpg = gnupg.GPG()
        gpg.encoding = 'utf-8'
        with self._open_sessionfile(session_id, 'w') as f:
            f.write(str(gpg.encrypt(password, None, symmetric=True,
                                    passphrase=session_hash)))

    def _retrieve_session(self, session_id, session_hash):
        """Retrieve a session and return its associated password"""
        try:
            with self._open_sessionfile(session_id, 'r') as f:
                enc_pwd = f.read()
        except IOError:
            # TODO: Set proper error code
            raise MoulinetteError(167, _("Unable to retrieve session"))
        else:
            gpg = gnupg.GPG()
            gpg.encoding = 'utf-8'
            return str(gpg.decrypt(enc_pwd, passphrase=session_hash))


class LDAPAuthenticator(_BaseAuthenticator):

    def __init__(self, uri, base_dn, user_rdn=None, **kwargs):
        super(LDAPAuthenticator, self).__init__(**kwargs)

        self.uri = uri
        self.basedn = base_dn
        if user_rdn:
            self.userdn = '%s,%s' % (user_rdn, base_dn)
            self.con = None
        else:
            # Initialize anonymous usage
            self.userdn = ''
            self.authenticate(None)


    ## Implement virtual properties

    vendor = 'ldap'

    @property
    def is_authenticated(self):
        try:
            # Retrieve identity
            who = self.con.whoami_s()
        except:
            return False
        else:
            if who[3:] == self.userdn:
                return True
        return False


    ## Implement virtual methods

    def authenticate(self, password):
        try:
            con = ldap.initialize(self.uri)
            if self.userdn:
                con.simple_bind_s(self.userdn, password)
            else:
                con.simple_bind_s()
        except ldap.INVALID_CREDENTIALS:
            raise AuthenticationError(_("Invalid password"))
        else:
            self.con = con


def init_authenticator(_name, _vendor, **kwargs):
    if _vendor == 'ldap':
        return LDAPAuthenticator(name=_name, **kwargs)

def clean_session(session_id, profiles=[]):
    sessiondir = pkg.get_cachedir('session')
    if len(profiles) == 0:
        profiles = os.listdir(sessiondir)

    for p in profiles:
        try:
            os.unlink(os.path.join(sessiondir, p, '%s.asc' % session_id))
        except OSError:
            pass


# Moulinette core classes ----------------------------------------------

class MoulinetteError(Exception):
    """Moulinette base exception

    Keyword arguments:
        - code -- Integer error code
        - message -- Error message to display

    """
    def __init__(self, code, message):
        self.code = code
        self.message = message

        errorcode_desc = {
            1   : _('Fail'),
            13  : _('Permission denied'),
            17  : _('Already exists'),
            22  : _('Invalid arguments'),
            87  : _('Too many users'),
            111 : _('Connection refused'),
            122 : _('Quota exceeded'),
            125 : _('Operation canceled'),
            167 : _('Not found'),
            168 : _('Undefined'),
            169 : _('LDAP operation error')
        }
        if code in errorcode_desc:
            self.desc = errorcode_desc[code]
        else:
            self.desc = _('Error %s' % code)

    def __str__(self, colorized=False):
        desc = self.desc
        if colorized:
            desc = colorize(self.desc, 'red')
        return _('%s: %s' % (desc, self.message))

    def colorize(self):
        return self.__str__(colorized=True)


class MoulinetteLock(object):
    """Locker for a moulinette instance

    It provides a lock mechanism for a given moulinette instance. It can
    be used in a with statement as it has a context-manager support.

    Keyword arguments:
        - namespace -- The namespace to lock
        - timeout -- The time period before failing if the lock cannot
            be acquired
        - interval -- The time period before trying again to acquire the
            lock

    """
    def __init__(self, namespace, timeout=0, interval=.5):
        self.namespace = namespace
        self.timeout = timeout
        self.interval = interval

        self._lockfile = '/var/run/moulinette_%s.lock' % namespace
        self._locked = False

    def acquire(self):
        """Attempt to acquire the lock for the moulinette instance

        It will try to write to the lock file only if it doesn't exist.
        Otherwise, it will wait and try again until the timeout expires
        or the lock file doesn't exist.

        """
        start_time = time.time()

        while True:
            if not os.path.isfile(self._lockfile):
                # Create the lock file
                (open(self._lockfile, 'w')).close()
                break

            if (time.time() - start_time) > self.timeout:
                raise MoulinetteError(1, _("An instance is already running for '%s'") \
                                            % self.namespace)
            # Wait before checking again
            time.sleep(self.interval)
        self._locked = True

    def release(self):
        """Release the lock of the moulinette instance

        It will delete the lock file if the lock has been acquired.

        """
        if self._locked:
            os.unlink(self._lockfile)
            self._locked = False

    def __enter__(self):
        if not self._locked:
            self.acquire()
        return self

    def __exit__(self, *args):
        self.release()

    def __del__(self):
        self.release()
