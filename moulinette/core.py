# -*- coding: utf-8 -*-

import os
import sys
import time
import errno
import gettext
import logging

from importlib import import_module

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


# Interfaces & Authenticators management -------------------------------

def init_interface(name, kwargs={}, actionsmap={}):
    """Return a new interface instance

    Retrieve the given interface module and return a new instance of its
    Interface class. It is initialized with arguments 'kwargs' and
    connected to 'actionsmap' if it's an ActionsMap object, otherwise
    a new ActionsMap instance will be initialized with arguments
    'actionsmap'.

    Keyword arguments:
        - name -- The interface name
        - kwargs -- A dict of arguments to pass to Interface
        - actionsmap -- Either an ActionsMap instance or a dict of
            arguments to pass to ActionsMap

    """
    from moulinette.actionsmap import ActionsMap

    try:
        mod = import_module('moulinette.interfaces.%s' % name)
    except ImportError:
        # TODO: List available interfaces
        raise MoulinetteError(errno.EINVAL, _("Unknown interface '%s'" % name))
    else:
        try:
            # Retrieve interface classes
            parser = mod.ActionsMapParser
            interface = mod.Interface
        except AttributeError as e:
            raise MoulinetteError(errno.EFAULT, _("Invalid interface '%s': %s") % (name, e))

    # Instantiate or retrieve ActionsMap
    if isinstance(actionsmap, dict):
        amap = ActionsMap(actionsmap.pop('parser', parser), **actionsmap)
    elif isinstance(actionsmap, ActionsMap):
        amap = actionsmap
    else:
        raise MoulinetteError(errno.EINVAL, _("Invalid actions map '%r'" % actionsmap))

    return interface(amap, **kwargs)

def init_authenticator((vendor, name), kwargs={}):
    """Return a new authenticator instance

    Retrieve the given authenticator vendor and return a new instance of
    its Authenticator class for the given profile.

    Keyword arguments:
        - vendor -- The authenticator vendor name
        - name -- The authenticator profile name
        - kwargs -- A dict of arguments for the authenticator profile

    """
    try:
        mod = import_module('moulinette.authenticators.%s' % vendor)
    except ImportError:
        # TODO: List available authenticators vendors
        raise MoulinetteError(errno.EINVAL, _("Unknown authenticator vendor '%s'" % vendor))
    else:
        return mod.Authenticator(name, **kwargs)

def clean_session(session_id, profiles=[]):
    """Clean a session cache

    Remove cache for the session 'session_id' and for profiles in
    'profiles' or for all of them if the list is empty.

    Keyword arguments:
        - session_id -- The session id to clean
        - profiles -- A list of profiles to clean

    """
    sessiondir = pkg.get_cachedir('session')
    if not profiles:
        profiles = os.listdir(sessiondir)

    for p in profiles:
        try:
            os.unlink(os.path.join(sessiondir, p, '%s.asc' % session_id))
        except OSError:
            pass


# Moulinette core classes ----------------------------------------------

class MoulinetteError(OSError):
    """Moulinette base exception"""
    pass


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
                raise MoulinetteError(errno.EBUSY, _("An instance is already running for '%s'") \
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
