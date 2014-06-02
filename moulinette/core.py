# -*- coding: utf-8 -*-

import os
import sys
import time
import json
import errno
import logging

from importlib import import_module

# Package manipulation -------------------------------------------------

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
            self._localedir = '%s/locales' % basedir
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


# Internationalization -------------------------------------------------

class Translator(object):
    """Internationalization class

    Provide an internationalization mechanism based on JSON files to
    translate a key in the proper locale.

    Keyword arguments:
        - locale_dir -- The directory where locale files are located
        - default_locale -- The default locale to use

    """
    def __init__(self, locale_dir, default_locale='en'):
        self.locale_dir = locale_dir
        self.locale = default_locale
        self._translations = {}

        # Attempt to load default translations
        if not self._load_translations(default_locale):
            raise ValueError("Unable to load locale '%s' from '%s'"
                    % (default_locale, locale_dir))
        self.default_locale = default_locale

    def get_locales(self):
        """Return a list of the avalaible locales"""
        locales = []

        for f in os.listdir(self.locale_dir):
            if f.endswith('.json'):
                # TODO: Validate locale
                locales.append(f[:-5])
        return locales

    def set_locale(self, locale):
        """Set the locale to use

        Set the locale to use at first. If the locale is not available,
        the default locale is used.

        Keyword arguments:
            - locale -- The locale to use

        Returns:
            True if the locale has been set, otherwise False

        """
        if locale not in self._translations:
            if not self._load_translations(locale):
                logging.info("unable to load locale '%s' from '%s'"
                        % (self.default_locale, self.locale_dir))

                # Revert to default locale
                self.locale = self.default_locale
                return False

        # Set current locale
        self.locale = locale
        return True

    def translate(self, key, *args, **kwargs):
        """Retrieve proper translation for a key

        Attempt to retrieve translation for a key using the current locale
        or the default locale if 'key' is not found.

        Keyword arguments:
            - key -- The key to translate

        """
        try:
            value = self._translations[self.locale][key]
        except KeyError:
            try:
                value = self._translations[self.default_locale][key]
                logging.info("untranslated key '%s' for locale '%s'" %
                        (key, self.locale))
            except KeyError:
                logging.warning("unknown key '%s' for locale '%s'" %
                        (key, self.default_locale))
                return key
        return value.encode('utf-8').format(*args, **kwargs)

    def _load_translations(self, locale, overwrite=False):
        """Load translations for a locale

        Attempt to load translations for a given locale. If 'overwrite' is
        True, translations will be loaded again.

        Keyword arguments:
            - locale -- The locale to load
            - overwrite -- True to overwrite existing translations

        Returns:
            True if the translations have been loaded, otherwise False

        """
        if not overwrite and locale in self._translations:
            return True

        try:
            with open('%s/%s.json' % (self.locale_dir, locale), 'r') as f:
                j = json.load(f, 'utf-8')
        except IOError:
            return False
        else:
            self._translations[locale] = j
        return True


class Moulinette18n(object):
    """Internationalization service for the moulinette

    Manage internationalization and access to the proper keys translation
    used in the moulinette and libraries.

    Keyword arguments:
        - package -- The current Package instance
        - default_locale -- The default locale to use

    """
    def __init__(self, package, default_locale='en'):
        self.default_locale = default_locale
        self.locale = default_locale
        self.pkg = package

        # Init translators
        self._global = Translator(self.pkg.localedir, default_locale)
        self._namespace = None

    def load_namespace(self, namespace):
        """Load the namespace to use

        Load and set translations of a given namespace. Those translations
        are accessible with Moulinette18n.n().

        Keyword arguments:
            - namespace -- The namespace to load

        """
        if self._namespace and self._namespace[0] == namespace:
            return

        self._namespace = (namespace, Translator('%s/%s/locales'
                % (self.pkg.libdir, namespace), self.default_locale))
        self._namespace[1].set_locale(self.locale)

    def set_locale(self, locale):
        """Set the locale to use"""
        self.locale = locale

        self._global.set_locale(locale)
        if self._namespace:
            self._namespace[1].set_locale(locale)

    def g(self, key, *args, **kwargs):
        """Retrieve proper translation for a moulinette key

        Attempt to retrieve value for a key from moulinette translations
        using the current locale or the default locale if 'key' is not found.

        Keyword arguments:
            - key -- The key to translate

        """
        return self._global.translate(key, *args, **kwargs)

    def n(self, key, *args, **kwargs):
        """Retrieve proper translation for a moulinette key

        Attempt to retrieve value for a key from loaded namespace translations
        using the current locale or the default locale if 'key' is not found.

        Keyword arguments:
            - key -- The key to translate

        """
        if not self._namespace:
            raise RuntimeError("No namespace loaded for translation")
        return self._namespace[1].translate(key, *args, **kwargs)


class MoulinetteSignals(object):
    """Signals connector for the moulinette

    Allow to easily connect signals from the moulinette to handlers. A
    signal is emitted by calling the relevant method which call the
    handler.
    For the moment, a return value can be requested by a signal to its
    connected handler - make them not real-signals.

    Keyword arguments:
        - kwargs -- A dict of {signal: handler} to connect

    """
    def __init__(self, **kwargs):
        # Initialize handlers
        for s in self.signals:
            self.clear_handler(s)

        # Iterate over signals to connect
        for s, h in kwargs.items():
            self.set_handler(s, h)

    def set_handler(self, signal, handler):
        """Set the handler for a signal"""
        if signal not in self.signals:
            raise ValueError("unknown signal '%s'" % signal)
        setattr(self, '_%s' % signal, handler)

    def clear_handler(self, signal):
        """Clear the handler of a signal"""
        if signal not in self.signals:
            raise ValueError("unknown signal '%s'" % signal)
        setattr(self, '_%s' % signal, self._notimplemented)


    ## Signals definitions

    """The list of available signals"""
    signals = { 'authenticate', 'prompt', 'display' }

    def authenticate(self, authenticator, help):
        """Process the authentication

        Attempt to authenticate to the given authenticator and return
        it.
        It is called when authentication is needed (e.g. to process an
        action).

        Keyword arguments:
            - authenticator -- The authenticator object to use
            - help -- A help message for the authenticator

        Returns:
            The authenticator object

        """
        if authenticator.is_authenticated:
            return authenticator
        return self._authenticate(authenticator, help)

    def prompt(self, message, is_password=False, confirm=False):
        """Prompt for a value

        Prompt the interface for a parameter value which is a password
        if 'is_password' and must be confirmed if 'confirm'.
        Is is called when a parameter value is needed and when the
        current interface should allow user interaction (e.g. to parse
        extra parameter 'ask' in the cli).

        Keyword arguments:
            - message -- The message to display
            - is_password -- True if the parameter is a password
            - confirm -- True if the value must be confirmed

        Returns:
            The collected value

        """
        return self._prompt(message, is_password, confirm)

    def display(self, message, style='info'):
        """Display a message

        Display a message with a given style to the user.
        It is called when a message should be printed to the user if the
        current interface allows user interaction (e.g. print a success
        message to the user).

        Keyword arguments:
            - message -- The message to display
            - style -- The type of the message. Possible values are:
                info, success, warning

        """
        try:
            self._display(message, style)
        except NotImplementedError:
            pass

    @staticmethod
    def _notimplemented(*args, **kwargs):
        raise NotImplementedError("this signal is not handled")


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
    except ImportError as e:
        # TODO: List available interfaces
        raise ImportError("Unable to load interface '%s': %s" % (name, str(e)))
    else:
        try:
            # Retrieve interface classes
            parser = mod.ActionsMapParser
            interface = mod.Interface
        except AttributeError as e:
            raise ImportError("Invalid interface '%s': %s" % (name, e))

    # Instantiate or retrieve ActionsMap
    if isinstance(actionsmap, dict):
        amap = ActionsMap(actionsmap.pop('parser', parser), **actionsmap)
    elif isinstance(actionsmap, ActionsMap):
        amap = actionsmap
    else:
        raise ValueError("Invalid actions map '%r'" % actionsmap)

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
    except ImportError as e:
        # TODO: List available authenticators vendors
        raise ImportError("Unable to load authenticator vendor '%s': %s"
                % (vendor, str(e)))
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
        self._bypass = False

    def acquire(self):
        """Attempt to acquire the lock for the moulinette instance

        It will try to write to the lock file only if it doesn't exist.
        Otherwise, it will wait and try again until the timeout expires
        or the lock file doesn't exist.

        """
        start_time = time.time()

        while True:
            if 'BYPASS_LOCK' in os.environ and os.environ['BYPASS_LOCK'] == 'yes':
                self._bypass = True
                break

            if not os.path.isfile(self._lockfile):
                # Create the lock file
                try:
                    (open(self._lockfile, 'w')).close()
                except IOError:
                    raise MoulinetteError(errno.EPERM,
                                          '%s. %s.' % (m18n.g('permission_denied'), m18n.g('root_required')))
                break

            if (time.time() - start_time) > self.timeout:
                raise MoulinetteError(errno.EBUSY,
                                      m18n.g('instance_already_running'))
            # Wait before checking again
            time.sleep(self.interval)
        self._locked = True

    def release(self):
        """Release the lock of the moulinette instance

        It will delete the lock file if the lock has been acquired.

        """
        if self._locked:
            if not self._bypass:
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
