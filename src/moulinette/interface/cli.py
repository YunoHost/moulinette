# -*- coding: utf-8 -*-

import getpass

from ..core import MoulinetteError

# CLI helpers ----------------------------------------------------------

colors_codes = {
    'red'   : 31,
    'green' : 32,
    'yellow': 33,
    'cyan'  : 34,
    'purple': 35
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


# Moulinette Interface -------------------------------------------------

class MoulinetteCLI(object):
    """Moulinette command-line Interface

    Initialize an interface connected to the standard input and output
    stream which allows to process moulinette action.

    Keyword arguments:
        - actionsmap -- The interface relevant ActionsMap instance

    """
    def __init__(self, actionsmap):
        # Connect signals to handlers
        actionsmap.connect('authenticate', self._do_authenticate)
        actionsmap.connect('prompt', self._do_prompt)

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
            raise MoulinetteError(125, _("Interrupted"))

        if isinstance(ret, dict):
            pretty_print_dict(ret)
        elif ret:
            print(ret)


    ## Signals handlers

    def _do_authenticate(self, authenticator, name, help):
        """Process the authentication

        Handle the actionsmap._AMapSignals.authenticate signal.

        """
        # TODO: Allow token authentication?
        msg = help or _("Password")
        return authenticator.authenticate(password=self._do_prompt(msg, True, False))

    def _do_prompt(self, message, is_password, confirm):
        """Prompt for a value

        Handle the actionsmap._AMapSignals.prompt signal.

        """
        if is_password:
            prompt = lambda m: getpass.getpass(colorize(_('%s: ') % m, 'cyan'))
        else:
            prompt = lambda m: raw_input(colorize(_('%s: ') % m, 'cyan'))
        value = prompt(message)

        if confirm:
            if prompt(_('Retype %s: ') % message) != value:
                raise MoulinetteError(22, _("Values don't match"))

        return value
