# -*- coding: utf-8 -*-

import os
import sys
import errno
import getpass
import locale
import logging
from argparse import SUPPRESS
from collections import OrderedDict

import argcomplete

from moulinette.core import MoulinetteError
from moulinette.interfaces import (
    BaseActionsMapParser, BaseInterface, ExtendedArgumentParser,
)
from moulinette.utils import log


logger = log.getLogger('moulinette.cli')


# CLI helpers ----------------------------------------------------------

CLI_COLOR_TEMPLATE = '\033[{:d}m\033[1m'
END_CLI_COLOR = '\033[m'

colors_codes = {
    'red': CLI_COLOR_TEMPLATE.format(31),
    'green': CLI_COLOR_TEMPLATE.format(32),
    'yellow': CLI_COLOR_TEMPLATE.format(33),
    'blue': CLI_COLOR_TEMPLATE.format(34),
    'purple': CLI_COLOR_TEMPLATE.format(35),
    'cyan': CLI_COLOR_TEMPLATE.format(36),
    'white': CLI_COLOR_TEMPLATE.format(37),
}


def colorize(astr, color):
    """Colorize a string

    Return a colorized string for printing in shell with style ;)

    Keyword arguments:
        - astr -- String to colorize
        - color -- Name of the color

    """
    if os.isatty(1):
        return '{:s}{:s}{:s}'.format(colors_codes[color], astr, END_CLI_COLOR)
    else:
        return astr


def plain_print_dict(d, depth=0):
    """Print in a plain way a dictionary recursively

    Print a dictionary recursively for scripting usage to the standard output.

    Output formatting:
      >>> d = {'key': 'value', 'list': [1,2], 'dict': {'key2': 'value2'}}
      >>> plain_print_dict(d)
      #key
      value
      #list
      1
      2
      #dict
      ##key2
      value2

    Keyword arguments:
        - d -- The dictionary to print
        - depth -- The recursive depth of the dictionary

    """
    # skip first key printing
    if depth == 0 and (isinstance(d, dict) and len(d) == 1):
        _, d = d.popitem()
    if isinstance(d, (tuple, set)):
        d = list(d)
    if isinstance(d, list):
        for v in d:
            plain_print_dict(v, depth + 1)
    elif isinstance(d, dict):
        for k, v in d.items():
            print("{}{}".format("#" * (depth + 1), k))
            plain_print_dict(v, depth + 1)
    else:
        if isinstance(d, unicode):
            d = d.encode('utf-8')
        print(d)


def pretty_print_dict(d, depth=0):
    """Print in a pretty way a dictionary recursively

    Print a dictionary recursively with colors to the standard output.

    Keyword arguments:
        - d -- The dictionary to print
        - depth -- The recursive depth of the dictionary

    """
    keys = d.keys()
    if not isinstance(d, OrderedDict):
        keys = sorted(keys)
    for k in keys:
        v = d[k]
        k = colorize(str(k), 'purple')
        if isinstance(v, (tuple, set)):
            v = list(v)
        if isinstance(v, list) and len(v) == 1:
            v = v[0]
        if isinstance(v, dict):
            print("{:s}{}: ".format("  " * depth, k))
            pretty_print_dict(v, depth + 1)
        elif isinstance(v, list):
            print("{:s}{}: ".format("  " * depth, k))
            for key, value in enumerate(v):
                if isinstance(value, tuple):
                    pretty_print_dict({value[0]: value[1]}, depth + 1)
                elif isinstance(value, dict):
                    pretty_print_dict({key: value}, depth + 1)
                else:
                    if isinstance(value, unicode):
                        value = value.encode('utf-8')
                    print("{:s}- {}".format("  " * (depth + 1), value))
        else:
            if isinstance(v, unicode):
                v = v.encode('utf-8')
            print("{:s}{}: {}".format("  " * depth, k, v))


def get_locale():
    """Return current user locale"""
    lang = locale.getdefaultlocale()[0]
    if not lang:
        return ''
    return lang[:2]


# CLI Classes Implementation -------------------------------------------

class TTYHandler(logging.StreamHandler):
    """TTY log handler

    A handler class which prints logging records for a tty. The record is
    neverthemess formatted depending if it is connected to a tty(-like)
    device.
    If it's the case, the level name - optionnaly colorized - is prepended
    to the message and the result is stored in the record as `message_key`
    attribute. That way, a custom formatter can be defined. The default is
    to output just the formatted message.
    Anyway, if the stream is not a tty, just the message is output.

    Note that records with a level higher or equal to WARNING are sent to
    stderr. Otherwise, they are sent to stdout.

    """
    LEVELS_COLOR = {
        log.NOTSET: 'white',
        log.DEBUG: 'white',
        log.INFO: 'cyan',
        log.SUCCESS: 'green',
        log.WARNING: 'yellow',
        log.ERROR: 'red',
        log.CRITICAL: 'red',
    }

    def __init__(self, message_key='fmessage'):
        logging.StreamHandler.__init__(self)
        self.message_key = message_key

    def format(self, record):
        """Enhance message with level and colors if supported."""
        msg = record.getMessage()
        if self.supports_color():
            level = ''
            if self.level <= log.DEBUG:
                # add level name before message
                level = '%s ' % record.levelname
            elif record.levelname in ['SUCCESS', 'WARNING', 'ERROR']:
                # add translated level name before message
                level = '%s ' % m18n.g(record.levelname.lower())
            color = self.LEVELS_COLOR.get(record.levelno, 'white')
            msg = '{0}{1}{2}{3}'.format(
                colors_codes[color], level, END_CLI_COLOR, msg)
        if self.formatter:
            # use user-defined formatter
            record.__dict__[self.message_key] = msg
            return self.formatter.format(record)
        return msg

    def emit(self, record):
        # set proper stream first
        if record.levelno >= log.WARNING:
            self.stream = sys.stderr
        else:
            self.stream = sys.stdout
        logging.StreamHandler.emit(self, record)

    def supports_color(self):
        """Check whether current stream supports color."""
        if hasattr(self.stream, 'isatty') and self.stream.isatty():
            return True
        return False


class ActionsMapParser(BaseActionsMapParser):
    """Actions map's Parser for the CLI

    Provide actions map parsing methods for a CLI usage. The parser for
    the arguments is represented by a ExtendedArgumentParser object.

    Keyword arguments:
        - parser -- The ExtendedArgumentParser object to use
        - subparser_kwargs -- Arguments to pass to the sub-parser group
        - top_parser -- An ArgumentParser object whose arguments should
            be take into account but not parsed

    """

    def __init__(self, parent=None, parser=None, subparser_kwargs=None,
                 top_parser=None, **kwargs):
        super(ActionsMapParser, self).__init__(parent)

        if subparser_kwargs is None:
            subparser_kwargs = {'title': "categories", 'required': False}

        self._parser = parser or ExtendedArgumentParser()
        self._subparsers = self._parser.add_subparsers(**subparser_kwargs)
        self.global_parser = parent.global_parser if parent else None

        if top_parser:
            self.global_parser = self._parser.add_argument_group("global arguments")

            # Append each top parser action to the global group
            for action in top_parser._actions:
                action.dest = SUPPRESS
                self.global_parser._add_action(action)

    # Implement virtual properties

    interface = 'cli'

    # Implement virtual methods

    @staticmethod
    def format_arg_names(name, full):
        if name[0] == '-' and full:
            return [name, full]
        return [name]

    def has_global_parser(self):
        return True

    def add_category_parser(self, name, category_help=None, **kwargs):
        """Add a parser for a category

        Keyword arguments:
            - category_help -- A brief description for the category

        Returns:
            A new ActionsMapParser object for the category

        """
        parser = self._subparsers.add_parser(name, help=category_help, **kwargs)
        return self.__class__(self, parser, {
            'title': "actions", 'required': True
        })

    def add_action_parser(self, name, tid, action_help=None, deprecated=False,
                          deprecated_alias=[], **kwargs):
        """Add a parser for an action

        Keyword arguments:
            - action_help -- A brief description for the action
            - deprecated -- Wether the action is deprecated
            - deprecated_alias -- A list of deprecated action alias names

        Returns:
            A new ExtendedArgumentParser object for the action

        """
        return self._subparsers.add_parser(name, help=action_help,
                                           deprecated=deprecated,
                                           deprecated_alias=deprecated_alias)

    def add_global_arguments(self, arguments):
        for argument_name, argument_options in arguments.items():
            # will adapt arguments name for cli or api context
            names = self.format_arg_names(str(argument_name),
                                          argument_options.pop('full', None))

            self.global_parser.add_argument(*names, **argument_options)


    def parse_args(self, args, **kwargs):
        try:
            ret = self._parser.parse_args(args)
        except SystemExit:
            raise
        except:
            logger.exception("unable to parse arguments '%s'", ' '.join(args))
            raise MoulinetteError(errno.EINVAL, m18n.g('error_see_log'))
        else:
            self.prepare_action_namespace(getattr(ret, '_tid', None), ret)
            self._parser.dequeue_callbacks(ret)
            return ret


class Interface(BaseInterface):
    """Command-line Interface for the moulinette

    Initialize an interface connected to the standard input/output
    stream and to a given actions map.

    Keyword arguments:
        - actionsmap -- The ActionsMap instance to connect to

    """

    def __init__(self, actionsmap):
        # Set user locale
        m18n.set_locale(get_locale())

        # Connect signals to handlers
        msignals.set_handler('display', self._do_display)
        if os.isatty(1):
            msignals.set_handler('authenticate', self._do_authenticate)
            msignals.set_handler('prompt', self._do_prompt)

        self.actionsmap = actionsmap

    def run(self, args, output_as=None, password=None, timeout=None):
        """Run the moulinette

        Process the action corresponding to the given arguments 'args'
        and print the result.

        Keyword arguments:
            - args -- A list of argument strings
            - output_as -- Output result in another format. Possible values:
                - json: return a JSON encoded string
                - plain: return a script-readable output
                - none: do not output the result
            - password -- The password to use in case of authentication
            - timeout -- Number of seconds before this command will timeout because it can't acquire the lock (meaning that another command is currently running), by default there is no timeout and the command will wait until it can get the lock

        """
        if output_as and output_as not in ['json', 'plain', 'none']:
            raise MoulinetteError(errno.EINVAL, m18n.g('invalid_usage'))

        # auto-complete
        argcomplete.autocomplete(self.actionsmap.parser._parser)

        # Set handler for authentication
        if password:
            msignals.set_handler('authenticate',
                                 lambda a, h: a(password=password))

        try:
            ret = self.actionsmap.process(args, timeout=timeout)
        except (KeyboardInterrupt, EOFError):
            raise MoulinetteError(errno.EINTR, m18n.g('operation_interrupted'))

        if ret is None or output_as == 'none':
            return

        # Format and print result
        if output_as:
            if output_as == 'json':
                import json
                from moulinette.utils.serialize import JSONExtendedEncoder
                print(json.dumps(ret, cls=JSONExtendedEncoder))
            else:
                plain_print_dict(ret)
        elif isinstance(ret, dict):
            pretty_print_dict(ret)
        else:
            print(ret)

    # Signals handlers

    def _do_authenticate(self, authenticator, help):
        """Process the authentication

        Handle the core.MoulinetteSignals.authenticate signal.

        """
        # TODO: Allow token authentication?
        msg = m18n.n(help) if help else m18n.g('password')
        return authenticator(password=self._do_prompt(msg, True, False,
                                                      color='yellow'))

    def _do_prompt(self, message, is_password, confirm, color='blue'):
        """Prompt for a value

        Handle the core.MoulinetteSignals.prompt signal.

        Keyword arguments:
            - color -- The color to use for prompting message

        """
        if is_password:
            prompt = lambda m: getpass.getpass(colorize(m18n.g('colon', m),
                                                        color))
        else:
            prompt = lambda m: raw_input(colorize(m18n.g('colon', m), color))
        value = prompt(message)

        if confirm:
            m = message[0].lower() + message[1:]
            if prompt(m18n.g('confirm', prompt=m)) != value:
                raise MoulinetteError(errno.EINVAL, m18n.g('values_mismatch'))

        return value

    def _do_display(self, message, style):
        """Display a message

        Handle the core.MoulinetteSignals.display signal.

        """
        if isinstance(message, unicode):
            message = message.encode('utf-8')
        if style == 'success':
            print('{} {}'.format(colorize(m18n.g('success'), 'green'), message))
        elif style == 'warning':
            print('{} {}'.format(colorize(m18n.g('warning'), 'yellow'), message))
        elif style == 'error':
            print('{} {}'.format(colorize(m18n.g('error'), 'red'), message))
        else:
            print(message)
