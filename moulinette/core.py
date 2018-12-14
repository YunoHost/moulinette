# -*- coding: utf-8 -*-

import os
import time
import json
import logging
import psutil

from importlib import import_module

import moulinette
from moulinette.globals import LOCALES_DIR, LIB_DIR
from moulinette.cache import get_cachedir


logger = logging.getLogger('moulinette.core')


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
            logger.error("unable to load locale '%s' from '%s'",
                         default_locale, locale_dir)
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
                logger.debug("unable to load locale '%s' from '%s'",
                             self.default_locale, self.locale_dir)

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
        failed_to_format = False
        if key in self._translations.get(self.locale, {}):
            try:
                return self._translations[self.locale][key].encode('utf-8').format(*args, **kwargs)
            except KeyError as e:
                logger.exception("Failed to format translated string '%s' with error: %s" % (key, e))
                failed_to_format = True

        if failed_to_format or (self.default_locale != self.locale and key in self._translations.get(self.default_locale, {})):
            logger.info("untranslated key '%s' for locale '%s'",
                        key, self.locale)

            try:
                return self._translations[self.default_locale][key].encode('utf-8').format(*args, **kwargs)
            except KeyError as e:
                logger.exception("Failed to format translatable string '%s' with error: %s" % (key, e))
                return self._translations[self.locale][key].encode('utf-8')

        logger.exception("unable to retrieve key '%s' for default locale '%s'",
                         key, self.default_locale)
        return key

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

    def __init__(self, default_locale='en'):
        self.default_locale = default_locale
        self.locale = default_locale

        # Init global translator
        self._global = Translator(LOCALES_DIR, default_locale)

        # Define namespace related variables
        self._namespaces = {}
        self._current_namespace = None

    def load_namespace(self, namespace):
        """Load the namespace to use

        Load and set translations of a given namespace. Those translations
        are accessible with Moulinette18n.n().

        Keyword arguments:
            - namespace -- The namespace to load

        """
        if namespace not in self._namespaces:
            # Create new Translator object
            translator = Translator('%s/%s/locales' % (LIB_DIR, namespace),
                                    self.default_locale)
            translator.set_locale(self.locale)
            self._namespaces[namespace] = translator

        # Set current namespace
        self._current_namespace = namespace

    def set_locale(self, locale):
        """Set the locale to use"""
        self.locale = locale

        self._global.set_locale(locale)
        for n in self._namespaces.values():
            n.set_locale(locale)

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

        Attempt to retrieve value for a key from current loaded namespace
        translations using the current locale or the default one if 'key' is
        not found.

        Keyword arguments:
            - key -- The key to translate

        """
        return self._namespaces[self._current_namespace].translate(key, *args, **kwargs)


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
            logger.error("unknown signal '%s'", signal)
            return
        setattr(self, '_%s' % signal, handler)

    def clear_handler(self, signal):
        """Clear the handler of a signal"""
        if signal not in self.signals:
            logger.error("unknown signal '%s'", signal)
            return
        setattr(self, '_%s' % signal, self._notimplemented)

    # Signals definitions

    """The list of available signals"""
    signals = {'authenticate', 'prompt', 'display'}

    def authenticate(self, authenticator, help):
        """Process the authentication

        Attempt to authenticate to the given authenticator and return
        it.
        It is called when authentication is needed (e.g. to process an
        action).

        Keyword arguments:
            - authenticator -- The authenticator object to use
            - help -- The translation key of the authenticator's help message

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
    except ImportError:
        logger.exception("unable to load interface '%s'", name)
        raise MoulinetteError('error_see_log')
    else:
        try:
            # Retrieve interface classes
            parser = mod.ActionsMapParser
            interface = mod.Interface
        except AttributeError:
            logger.exception("unable to retrieve classes of interface '%s'", name)
            raise MoulinetteError('error_see_log')

    # Instantiate or retrieve ActionsMap
    if isinstance(actionsmap, dict):
        amap = ActionsMap(actionsmap.pop('parser', parser), **actionsmap)
    elif isinstance(actionsmap, ActionsMap):
        amap = actionsmap
    else:
        logger.error("invalid actionsmap value %r", actionsmap)
        raise MoulinetteError('error_see_log')

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
        logger.exception("unable to load authenticator vendor '%s'", vendor)
        raise MoulinetteError('error_see_log')
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
    sessiondir = get_cachedir('session')
    if not profiles:
        profiles = os.listdir(sessiondir)

    for p in profiles:
        try:
            os.unlink(os.path.join(sessiondir, p, '%s.asc' % session_id))
        except OSError:
            pass


# Moulinette core classes ----------------------------------------------

class MoulinetteError(Exception):
    """Moulinette base exception"""
    def __init__(self, key, raw_msg=False, *args, **kwargs):
        if raw_msg:
            msg = key
        else:
            msg = moulinette.m18n.g(key, *args, **kwargs)
        super(MoulinetteError, self).__init__(msg)
        self.strerror = msg


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

    def __init__(self, namespace, timeout=None, interval=.5):
        self.namespace = namespace
        self.timeout = timeout
        self.interval = interval

        self._lockfile = '/var/run/moulinette_%s.lock' % namespace
        self._stale_checked = False
        self._locked = False

    def acquire(self):
        """Attempt to acquire the lock for the moulinette instance

        It will try to write to the lock file only if it doesn't exist.
        Otherwise, it will wait and try again until the timeout expires
        or the lock file doesn't exist.

        """
        start_time = time.time()

        while True:

            lock_pids = self._lock_PIDs()

            if self._is_son_of(lock_pids):
                return

            if lock_pids == []:
                self._lock()
                break
            elif not self._stale_checked:
                self._stale_checked = True
                # Check locked process still exist and take lock if it doesnt
                # FIXME : what do in the context of multiple locks :|
                first_lock = lock_pids[0]
                if not os.path.exists(os.path.join('/proc', str(first_lock), 'exe')):
                    logger.debug('stale lock file found')
                    self._lock()
                    break

            if self.timeout is not None and (time.time() - start_time) > self.timeout:
                raise MoulinetteError('instance_already_running')
            # Wait before checking again
            time.sleep(self.interval)

        logger.debug('lock has been acquired')
        self._locked = True

    def release(self):
        """Release the lock of the moulinette instance

        It will delete the lock file if the lock has been acquired.

        """
        if self._locked:
            os.unlink(self._lockfile)
            logger.debug('lock has been released')
            self._locked = False

    def _lock(self):
        try:
            with open(self._lockfile, 'w') as f:
                f.write(str(os.getpid()))
        except IOError:
            raise MoulinetteError('root_required')

    def _lock_PIDs(self):

        if not os.path.isfile(self._lockfile):
            return []

        with open(self._lockfile) as f:
            lock_pids = f.read().strip().split('\n')

        # Make sure to convert those pids to integers
        lock_pids = [int(pid) for pid in lock_pids if pid.strip() != '']

        return lock_pids

    def _is_son_of(self, lock_pids):

        if lock_pids == []:
            return False

        # Start with self
        parent = psutil.Process()

        # While there is a parent... (e.g. init has no parent)
        while parent is not None:
            # If parent PID is the lock, then yes! we are a son of the process
            # with the lock...
            if parent.pid in lock_pids:
                return True
            # Otherwise, try 'next' parent
            parent = parent.parent()

        return False

    def __enter__(self):
        if not self._locked:
            self.acquire()
        return self

    def __exit__(self, *args):
        self.release()

    def __del__(self):
        self.release()
