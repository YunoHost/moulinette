import os
import logging

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
    handlers = []
    for ref in logging._handlers.itervaluerefs():
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
        f = logging.currentframe()
        if f is not None:
            f = f.f_back
        rv = "(unknown file)", 0, "(unknown function)"
        while hasattr(f, "f_code"):
            co = f.f_code
            filename = os.path.normcase(co.co_filename)
            if filename == logging._srcfile or filename == __file__:
                f = f.f_back
                continue
            rv = (co.co_filename, f.f_lineno, co.co_name)
            break
        return rv

    def _log(self, *args, **kwargs):
        """Append action_id if available to the extra."""
        if self.action_id is not None:
            extra = kwargs.get("extra", {})
            if "action_id" not in extra:
                # FIXME: Get real action_id instead of logger/current one
                extra["action_id"] = _get_action_id()
                kwargs["extra"] = extra
        return super()._log(*args, **kwargs)


# Action logging -------------------------------------------------------

pid = os.getpid()
action_id = 0


def _get_action_id():
    return "%d.%d" % (pid, action_id)


def start_action_logging():
    """Configure logging for a new action

    Returns:
        The new action id

    """
    global action_id
    action_id += 1

    return _get_action_id()


def getActionLogger(name=None, logger=None, action_id=None):
    """Get the logger adapter for an action

    Return a logger for the specified name - or use given logger - and
    optionally for a given action id, retrieving it if necessary.

    Either a name or a logger must be specified.

    """
    if not name and not logger:
        raise ValueError("Either a name or a logger must be specified")

    logger = logger or getLogger(name)
    logger.action_id = action_id if action_id else _get_action_id()
    return logger


class ActionFilter(object):

    """Extend log record for an optionnal action

    Filter a given record and look for an `action_id` key. If it is not found
    and `strict` is True, the record will not be logged. Otherwise, the key
    specified by `message_key` will be added to the record, containing the
    message formatted for the action or just the original one.

    """

    def __init__(self, message_key="fmessage", strict=False):
        self.message_key = message_key
        self.strict = strict

    def filter(self, record):
        msg = record.getMessage()
        action_id = record.__dict__.get("action_id", None)
        if action_id is not None:
            msg = "[{:s}] {:s}".format(action_id, msg)
        elif self.strict:
            return False
        record.__dict__[self.message_key] = msg
        return True
