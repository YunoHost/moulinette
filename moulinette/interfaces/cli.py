# -*- coding: utf-8 -*-

import os
import errno
import getpass
import locale
import logging

from moulinette.core import MoulinetteError
from moulinette.interfaces import (
    BaseActionsMapParser, BaseInterface, ExtendedArgumentParser,
)


logger = logging.getLogger('moulinette.cli')


# CLI helpers ----------------------------------------------------------

colors_codes = {
    'red'   : 31,
    'green' : 32,
    'yellow': 33,
    'blue'  : 34,
    'purple': 35,
    'cyan'  : 36,
    'white' : 37
}

def colorize(astr, color):
    """Colorize a string

    Return a colorized string for printing in shell with style ;)

    Keyword arguments:
        - astr -- String to colorize
        - color -- Name of the color

    """
    if os.isatty(1):
        return '\033[{:d}m\033[1m{:s}\033[m'.format(colors_codes[color], astr)
    else:
        return astr

def pretty_print_dict(d, depth=0):
    """Print a dictionary recursively

    Print a dictionary recursively with colors to the standard output.

    Keyword arguments:
        - d -- The dictionary to print
        - depth -- The recursive depth of the dictionary

    """
    for k,v in d.items():
        k = colorize(str(k), 'purple')
        if isinstance(v, (tuple, set)):
            v = list(v)
        if isinstance(v, list) and len(v) == 1:
            v = v[0]
        if isinstance(v, dict):
            print("{:s}{}: ".format("  " * depth, k))
            pretty_print_dict(v, depth+1)
        elif isinstance(v, list):
            print("{:s}{}: ".format("  " * depth, k))
            for key, value in enumerate(v):
                if isinstance(value, tuple):
                    pretty_print_dict({value[0]: value[1]}, depth+1)
                elif isinstance(value, dict):
                    pretty_print_dict({key: value}, depth+1)
                else:
                    if isinstance(value, unicode):
                        value = value.encode('utf-8')
                    print("{:s}- {}".format("  " * (depth+1), value))
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

class ActionsMapParser(BaseActionsMapParser):
    """Actions map's Parser for the CLI

    Provide actions map parsing methods for a CLI usage. The parser for
    the arguments is represented by a ExtendedArgumentParser object.

    Keyword arguments:
        - parser -- The ExtendedArgumentParser object to use
        - subparser_kwargs -- Arguments to pass to the sub-parser group

    """
    def __init__(self, parent=None, parser=None, subparser_kwargs=None):
        super(ActionsMapParser, self).__init__(parent)

        if subparser_kwargs is None:
            subparser_kwargs = {'title': "categories", 'required': False}

        self._parser = parser or ExtendedArgumentParser()
        self._subparsers = self._parser.add_subparsers(**subparser_kwargs)


    ## Implement virtual properties

    interface = 'cli'


    ## Implement virtual methods

    @staticmethod
    def format_arg_names(name, full):
        if name[0] == '-' and full:
            return [name, full]
        return [name]

    def add_global_parser(self, **kwargs):
        return self._parser.add_mutually_exclusive_group()

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

    def add_action_parser(self, name, tid, action_help=None, **kwargs):
        """Add a parser for an action

        Keyword arguments:
            - action_help -- A brief description for the action

        Returns:
            A new ExtendedArgumentParser object for the action

        """
        return self._subparsers.add_parser(name, help=action_help)

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

    def run(self, args, print_json=False):
        """Run the moulinette

        Process the action corresponding to the given arguments 'args'
        and print the result.

        Keyword arguments:
            - args -- A list of argument strings
            - print_json -- True to print result as a JSON encoded string

        """
        try:
            ret = self.actionsmap.process(args, timeout=5)
        except KeyboardInterrupt, EOFError:
            raise MoulinetteError(errno.EINTR, m18n.g('operation_interrupted'))

        if ret is None:
            return

        # Format and print result
        if print_json:
            import json
            from moulinette.utils.serialize import JSONExtendedEncoder
            print(json.dumps(ret, cls=JSONExtendedEncoder))
        elif isinstance(ret, dict):
            pretty_print_dict(ret)
        else:
            print(ret)


    ## Signals handlers

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
            if prompt(m18n.g('confirm', m)) != value:
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
