import os

# import all constants because other modules try to import them from this
# module because SUCCESS is defined in this module
from logging import (
    addLevelName,
    setLoggerClass,
    Logger,
    getLogger,
    NOTSET,  # noqa
    DEBUG,
    INFO,
    WARNING,
    ERROR,
    CRITICAL,
)

__all__ = [
    "NOTSET",  # noqa
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL",
    "SUCCESS",
]


# Global configuration and functions -----------------------------------

SUCCESS = 25

DEFAULT_LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "%(asctime)-15s %(levelname)-8s %(name)s - %(message)s"},
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "formatter": "simple",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {"moulinette": {"level": "DEBUG", "handlers": ["console"]}},
}


def configure_logging(logging_config=None):
    """Configure logging with default and optionally given configuration

    Keyword arguments:
        - logging_config -- A dict containing logging configuration

    """
    from logging.config import dictConfig

    # add custom logging level and class
    addLevelName(SUCCESS, "SUCCESS")
    setLoggerClass(MoulinetteLogger)

    # load configuration from dict
    dictConfig(DEFAULT_LOGGING)
    if logging_config:
        dictConfig(logging_config)


def getHandlersByClass(classinfo, limit=0):
    """Retrieve registered handlers of a given class."""

    from logging import _handlers

    handlers = []
    for ref in _handlers.itervaluerefs():
        o = ref()
        if o is not None and isinstance(o, classinfo):
            if limit == 1:
                return o
            handlers.append(o)
    if limit != 0 and len(handlers) > limit:
        return handlers[: limit - 1]
    return handlers


class MoulinetteLogger(Logger):

    """Custom logger class

    Extend base Logger class to provide the SUCCESS custom log level with
    a convenient logging method. It also consider an optionnal action_id
    which corresponds to the associated logged action. It is added to the
    LogRecord extra and can be used with the ActionFilter.

    """

    action_id = None

    def success(self, msg, *args, **kwargs):
        """Log 'msg % args' with severity 'SUCCESS'."""
        if self.isEnabledFor(SUCCESS):
            self._log(SUCCESS, msg, args, **kwargs)

    def findCaller(self, *args):
        """Override findCaller method to consider this source file."""

        from logging import currentframe, _srcfile

        f = currentframe()
        if f is not None:
            f = f.f_back
        rv = "(unknown file)", 0, "(unknown function)", None
        while hasattr(f, "f_code"):
            co = f.f_code
            filename = os.path.normcase(co.co_filename)
            if filename == _srcfile or filename == __file__:
                f = f.f_back
                continue
            rv = (co.co_filename, f.f_lineno, co.co_name, None)
            break

        return rv
