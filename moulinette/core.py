# -*- coding: utf-8 -*-

import os
import time
import json
import logging

import moulinette

logger = logging.getLogger("moulinette.core")


def during_unittests_run():
    return "TESTS_RUN" in os.environ


# Internationalization -------------------------------------------------


class Translator:
    """Internationalization class

    Provide an internationalization mechanism based on JSON files to
    translate a key in the proper locale.

    Keyword arguments:
        - locale_dir -- The directory where locale files are located
        - default_locale -- The default locale to use

    """

    def __init__(self, locale_dir, default_locale="en"):
        self.locale_dir = locale_dir
        self.locale = default_locale
        self._translations = {}

        # Attempt to load default translations
        if not self._load_translations(default_locale):
            logger.error(
                f"unable to load locale '{default_locale}' from '{locale_dir}'. Does the file '{locale_dir}/{default_locale}.json' exists?",
            )
        self.default_locale = default_locale

    def get_locales(self):
        """Return a list of the avalaible locales"""
        locales = []

        for f in os.listdir(self.locale_dir):
            if f.endswith(".json"):
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
                logger.debug(
                    "unable to load locale '%s' from '%s'",
                    self.default_locale,
                    self.locale_dir,
                )

                # Revert to default locale
                self.locale = self.default_locale
                return False

        # Set current locale
        self.locale = locale
        return True

    def key_exists(self, key):
        return key in self._translations[self.default_locale]

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
                return self._translations[self.locale][key].format(*args, **kwargs)
            except Exception as e:
                unformatted_string = self._translations[self.locale][key]
                error_message = (
                    "Failed to format translated string '%s': '%s' with arguments '%s' and '%s, raising error: %s(%s) (don't panic this is just a warning)"
                    % (key, unformatted_string, args, kwargs, e.__class__.__name__, e)
                )

                if not during_unittests_run():
                    logger.warning(error_message)
                else:
                    raise Exception(error_message)

                failed_to_format = True

        if failed_to_format or (
            self.default_locale != self.locale
            and key in self._translations.get(self.default_locale, {})
        ):
            try:
                return self._translations[self.default_locale][key].format(
                    *args, **kwargs
                )
            except Exception as e:
                unformatted_string = self._translations[self.default_locale][key]
                error_message = (
                    "Failed to format translatable string '%s': '%s' with arguments '%s' and '%s', raising  error: %s(%s) (don't panic this is just a warning)"
                    % (key, unformatted_string, args, kwargs, e.__class__.__name__, e)
                )
                if not during_unittests_run():
                    logger.warning(error_message)
                else:
                    raise Exception(error_message)

                return self._translations[self.default_locale][key]

        error_message = (
            "unable to retrieve string to translate with key '%s' for default locale 'locales/%s.json' file (don't panic this is just a warning)"
            % (key, self.default_locale)
        )

        if not during_unittests_run():
            logger.warning(error_message)
        else:
            raise Exception(error_message)

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
            with open(f"{self.locale_dir}/{locale}.json", "r", encoding="utf-8") as f:
                j = json.load(f)
        except IOError:
            return False
        else:
            self._translations[locale] = j
        return True


class Moulinette18n:
    """Internationalization service for the moulinette

    Manage internationalization and access to the proper keys translation
    used in the moulinette and libraries.

    Keyword arguments:
        - package -- The current Package instance
        - default_locale -- The default locale to use

    """

    def __init__(self, default_locale="en"):
        self.default_locale = default_locale
        self.locale = default_locale

        # Init global translator
        global_locale_dir = "/usr/share/moulinette/locales"
        if during_unittests_run():
            global_locale_dir = os.path.dirname(__file__) + "/../locales"

        self._global = Translator(global_locale_dir, default_locale)

    def set_locales_dir(self, locales_dir):
        self.translator = Translator(locales_dir, self.default_locale)

    def set_locale(self, locale):
        """Set the locale to use"""

        self.locale = locale
        self._global.set_locale(locale)
        self.translator.set_locale(locale)

    def g(self, key: str, *args, **kwargs) -> str:
        """Retrieve proper translation for a moulinette key

        Attempt to retrieve value for a key from moulinette translations
        using the current locale or the default locale if 'key' is not found.

        Keyword arguments:
            - key -- The key to translate

        """
        return self._global.translate(key, *args, **kwargs)

    def n(self, key: str, *args, **kwargs) -> str:
        """Retrieve proper translation for a moulinette key

        Attempt to retrieve value for a key from current loaded namespace
        translations using the current locale or the default one if 'key' is
        not found.

        Keyword arguments:
            - key -- The key to translate

        """
        return self.translator.translate(key, *args, **kwargs)

    def key_exists(self, key: str) -> bool:
        """Check if a key exists in the translation files

        Keyword arguments:
            - key -- The key to translate

        """
        return self.translator.key_exists(key)


# Moulinette core classes ----------------------------------------------


class MoulinetteError(Exception):
    http_code = 500

    """Moulinette base exception"""

    def __init__(self, key, raw_msg=False, *args, **kwargs):
        if raw_msg:
            msg = key
        else:
            msg = moulinette.m18n.g(key, *args, **kwargs)
        super(MoulinetteError, self).__init__(msg)
        self.strerror = msg

    def content(self) -> str:
        return self.strerror


class MoulinetteValidationError(MoulinetteError):
    http_code = 400


class MoulinetteAuthenticationError(MoulinetteError):
    http_code = 401


class MoulinetteLock:
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

    base_lockfile = "/var/run/moulinette_%s.lock"

    def __init__(self, namespace, timeout=None, enable_lock=True, interval=0.5):
        self.namespace = namespace
        self.timeout = timeout
        self.interval = interval
        self.enable_lock = enable_lock

        self._lockfile = self.base_lockfile % namespace
        self._stale_checked = False
        self._locked = False

    def acquire(self):
        """Attempt to acquire the lock for the moulinette instance

        It will try to write to the lock file only if it doesn't exist.
        Otherwise, it will wait and try again until the timeout expires
        or the lock file doesn't exist.

        """
        start_time = time.time()

        # for UX reason, we are going to warn the user that we are waiting for
        # another yunohost command to end, otherwise the user is very confused
        # and don't understand that and think yunohost is broken
        # we are going to warn the user after 15 seconds of waiting time then
        # after 15*4 seconds, then 15*4*4 seconds...
        warning_treshold = 15

        logger.debug("acquiring lock...")

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
                if not os.path.exists(os.path.join("/proc", str(first_lock), "exe")):
                    logger.debug("stale lock file found")
                    self._lock()
                    break

            if self.timeout is not None and (time.time() - start_time) > self.timeout:
                raise MoulinetteError("instance_already_running")

            # warn the user if it's been too much time since they are waiting
            if (time.time() - start_time) > warning_treshold:
                if warning_treshold == 15:
                    logger.warning(
                        moulinette.m18n.g("warn_the_user_about_waiting_lock")
                    )
                else:
                    logger.warning(
                        moulinette.m18n.g("warn_the_user_about_waiting_lock_again")
                    )
                warning_treshold *= 4

            # Wait before checking again
            time.sleep(self.interval)

        # we have warned the user that we were waiting, for better UX also them
        # that we have stop waiting and that the command is processing now
        if warning_treshold != 15:
            logger.warning(moulinette.m18n.g("warn_the_user_that_lock_is_acquired"))
        logger.debug("lock has been acquired")
        self._locked = True

    def release(self):
        """Release the lock of the moulinette instance

        It will delete the lock file if the lock has been acquired.

        """
        if self._locked:
            if os.path.exists(self._lockfile):
                os.unlink(self._lockfile)
            else:
                logger.warning(
                    "Uhoh, somehow the lock %s did not exist ..." % self._lockfile
                )
            logger.debug("lock has been released")
            self._locked = False

    def _lock(self):
        try:
            with open(self._lockfile, "w") as f:
                f.write(str(os.getpid()))
        except IOError:
            raise MoulinetteError("root_required")

    def _lock_PIDs(self):
        if not os.path.isfile(self._lockfile):
            return []

        with open(self._lockfile) as f:
            lock_pids = f.read().strip().split("\n")

        # Make sure to convert those pids to integers
        lock_pids = [int(pid) for pid in lock_pids if pid.strip() != ""]

        return lock_pids

    def _is_son_of(self, lock_pids):
        import psutil

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
        if self.enable_lock and not self._locked:
            self.acquire()
        return self

    def __exit__(self, *args):
        self.release()

    def __del__(self):
        self.release()
