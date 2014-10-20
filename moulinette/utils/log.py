import os
import logging


# Global configuration and functions -----------------------------------

DEFAULT_LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '%(asctime)-15s %(levelname)-8s %(name)s - %(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'formatter': 'simple',
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stdout',
        },
    },
    'loggers': {
        'moulinette': {
            'level': 'DEBUG',
            'handlers': ['console'],
        },
    },
}

def configure_logging(logging_config=None):
    """Configure logging with default and optionally given configuration

    Keyword arguments:
        - logging_config -- A dict containing logging configuration

    """
    from logging.config import dictConfig

    dictConfig(DEFAULT_LOGGING)
    if logging_config:
        dictConfig(logging_config)


# Action logging -------------------------------------------------------

pid = os.getpid()
action_id = 0

def _get_action_id():
    return '%d.%d' % (pid, action_id)

def start_action_logging():
    """Configure logging for a new action

    Returns:
        The new action id

    """
    global action_id
    action_id += 1

    return _get_action_id()

class ActionLoggerAdapter(logging.LoggerAdapter):
    """Adapter for action loggers

    Extend an action logging output by processing both the logging message and the
    contextual information. The action id is prepended to the message and the
    following keyword arguments are added:
        - action_id -- the current action id

    """
    def process(self, msg, kwargs):
        """Process the logging call for the action

        Process the logging call by retrieving the action id and prepending it to
        the log message. It will also be added to the 'extra' keyword argument.

        """
        try:
            action_id = self.extra['action_id']
        except KeyError:
            action_id = _get_action_id()

        # Extend current extra keyword argument
        extra = kwargs.get('extra', {})
        extra['action_id'] = action_id
        kwargs['extra'] = extra

        return '[{:s}] {:s}'.format(action_id, msg), kwargs

def getActionLogger(name=None, logger=None, action_id=None):
    """Get the logger adapter for an action

    Return an action logger adapter with the specified name or logger and
    optionally for a given action id, creating it if necessary.

    Either a name or a logger must be specified.
    
    """
    if not name and not logger:
        raise ValueError('Either a name or a logger must be specified')

    extra = {'action_id': action_id} if action_id else {}
    return ActionLoggerAdapter(logger or logging.getLogger(name), extra)
