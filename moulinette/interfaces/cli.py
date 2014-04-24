# -*- coding: utf-8 -*-

import os
import errno
import getpass
import argparse

from moulinette.core import MoulinetteError
from moulinette.interfaces import (BaseActionsMapParser, BaseInterface)

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
    return '\033[{:d}m\033[1m{:s}\033[m'.format(colors_codes[color], astr)

def pretty_print_dict(d, depth=0):
    """Print a dictionary recursively

    Print a dictionary recursively with colors to the standard output.

    Keyword arguments:
        - d -- The dictionary to print
        - depth -- The recursive depth of the dictionary

    """
    for k,v in sorted(d.items(), key=lambda x: x[0]):
        k = colorize(str(k), 'purple')
        if isinstance(v, list) and len(v) == 1:
            v = v[0]
        if isinstance(v, dict):
            print(("  ") * depth + ("%s: " % str(k)))
            pretty_print_dict(v, depth+1)
        elif isinstance(v, list):
            print(("  ") * depth + ("%s: " % str(k)))
            for key, value in enumerate(v):
                if isinstance(value, tuple):
                    pretty_print_dict({value[0]: value[1]}, depth+1)
                elif isinstance(value, dict):
                    pretty_print_dict({key: value}, depth+1)
                else:
                    print(("  ") * (depth+1) + "- " +str(value))
        else:
            if not isinstance(v, basestring):
                v = str(v)
            print(("  ") * depth + "%s: %s" % (str(k), v))


# CLI Classes Implementation -------------------------------------------

class ActionsMapParser(BaseActionsMapParser):
    """Actions map's Parser for the CLI

    Provide actions map parsing methods for a CLI usage. The parser for
    the arguments is represented by a argparse.ArgumentParser object.

    Keyword arguments:
        - parser -- The argparse.ArgumentParser object to use

    """
    def __init__(self, parent=None, parser=None):
        super(ActionsMapParser, self).__init__(parent)

        self._parser = parser or argparse.ArgumentParser()
        self._subparsers = self._parser.add_subparsers()


    ## Implement virtual properties

    interface = 'cli'


    ## Implement virtual methods

    @staticmethod
    def format_arg_names(name, full):
        if name[0] == '-' and full:
            return [name, full]
        return [name]

    def add_global_parser(self, **kwargs):
        return self._parser

    def add_category_parser(self, name, category_help=None, **kwargs):
        """Add a parser for a category

        Keyword arguments:
            - category_help -- A brief description for the category

        Returns:
            A new ActionsMapParser object for the category

        """
        parser = self._subparsers.add_parser(name, help=category_help)
        return self.__class__(self, parser)

    def add_action_parser(self, name, tid, action_help=None, **kwargs):
        """Add a parser for an action

        Keyword arguments:
            - action_help -- A brief description for the action

        Returns:
            A new argparse.ArgumentParser object for the action

        """
        return self._subparsers.add_parser(name, help=action_help)

    def parse_args(self, args, **kwargs):
        ret = self._parser.parse_args(args)

        if not self.get_conf(ret._tid, 'lock'):
            os.environ['BYPASS_LOCK'] = 'yes'

        # Perform authentication if needed
        if self.get_conf(ret._tid, 'authenticate'):
            auth_conf, klass = self.get_conf(ret._tid, 'authenticator')

            # TODO: Catch errors
            auth = msignals.authenticate(klass(), **auth_conf)
            if not auth.is_authenticated:
                # TODO: Set proper error code
                raise MoulinetteError(errno.EACCES, _("This action need authentication"))
            if self.get_conf(ret._tid, 'argument_auth') and \
               self.get_conf(ret._tid, 'authenticate') == 'all':
                ret.auth = auth

        return ret


class Interface(BaseInterface):
    """Command-line Interface for the moulinette

    Initialize an interface connected to the standard input/output
    stream and to a given actions map.

    Keyword arguments:
        - actionsmap -- The ActionsMap instance to connect to

    """
    def __init__(self, actionsmap):
        # Connect signals to handlers
        msignals.set_handler('authenticate', self._do_authenticate)
        msignals.set_handler('display', self._do_display)
        msignals.set_handler('prompt', self._do_prompt)

        self.actionsmap = actionsmap

    def run(self, args):
        """Run the moulinette

        Process the action corresponding to the given arguments 'args'
        and print the result.

        Keyword arguments:
            - args -- A list of argument strings

        """
        try:
            ret = self.actionsmap.process(args, timeout=5)
        except KeyboardInterrupt, EOFError:
            raise MoulinetteError(errno.EINTR, _("Interrupted"))

        if isinstance(ret, dict):
            pretty_print_dict(ret)
        elif ret:
            print(ret)


    ## Signals handlers

    def _do_authenticate(self, authenticator, help):
        """Process the authentication

        Handle the core.MoulinetteSignals.authenticate signal.

        """
        # TODO: Allow token authentication?
        msg = help or _("Password")
        return authenticator(password=self._do_prompt(msg, True, False))

    def _do_prompt(self, message, is_password, confirm):
        """Prompt for a value

        Handle the core.MoulinetteSignals.prompt signal.

        """
        if is_password:
            prompt = lambda m: getpass.getpass(colorize(_('%s: ') % m, 'blue'))
        else:
            prompt = lambda m: raw_input(colorize(_('%s: ') % m, 'blue'))
        value = prompt(message)

        if confirm:
            if prompt(_('Retype %s') % message) != value:
                raise MoulinetteError(errno.EINVAL, _("Values don't match"))

        return value

    def _do_display(self, message, style):
        """Display a message

        Handle the core.MoulinetteSignals.display signal.

        """
        if style == 'success':
            print('%s %s' % (colorize(_("Success!"), 'green'), message))
        elif style == 'warning':
            print('%s %s' % (colorize(_("Warning!"), 'yellow'), message))
        else:
            print(message)
