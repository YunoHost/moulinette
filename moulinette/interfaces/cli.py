# -*- coding: utf-8 -*-

import os
import sys
import locale
import logging
import argparse
import tempfile
from collections import OrderedDict
from datetime import date, datetime
from subprocess import call

from moulinette import m18n, Moulinette
from moulinette.actionsmap import ActionsMap
from moulinette.core import MoulinetteError, MoulinetteValidationError
from moulinette.interfaces import (
    BaseActionsMapParser,
    ExtendedArgumentParser,
    JSONExtendedEncoder,
)
from moulinette.utils import log

# Monkeypatch _get_action_name function because there is an annoying bug
# Explained here: https://bugs.python.org/issue29298
# Fixed by: https://github.com/python/cpython/pull/3680
# To reproduce the bug, just launch a command line without action
# For example:
#       yunohost firewall
# It should display:
#       usage: yunohost firewall {list,reload,allow,disallow,upnp,stop} ... [-h]
#       yunohost firewall: error: the following arguments are required: {list,reload,allow,disallow,upnp,stop}
# But it display instead:
#       Error: unable to parse arguments 'firewall' because: sequence item 0: expected str instance, NoneType found


def monkey_get_action_name(argument):
    if argument is None:
        return None
    elif argument.option_strings:
        return "/".join(argument.option_strings)
    elif argument.metavar not in (None, argparse.SUPPRESS):
        return argument.metavar
    elif argument.dest not in (None, argparse.SUPPRESS):
        return argument.dest
    elif argument.choices:
        return "{" + ",".join(argument.choices) + "}"
    else:
        return None


argparse._get_action_name = monkey_get_action_name

logger = log.getLogger("moulinette.cli")


# CLI helpers ----------------------------------------------------------

CLI_COLOR_TEMPLATE = "\033[{:d}m\033[1m"
END_CLI_COLOR = "\033[m"

colors_codes = {
    "red": CLI_COLOR_TEMPLATE.format(31),
    "green": CLI_COLOR_TEMPLATE.format(32),
    "yellow": CLI_COLOR_TEMPLATE.format(33),
    "blue": CLI_COLOR_TEMPLATE.format(34),
    "purple": CLI_COLOR_TEMPLATE.format(35),
    "cyan": CLI_COLOR_TEMPLATE.format(36),
    "white": CLI_COLOR_TEMPLATE.format(37),
}


def colorize(astr, color):
    """Colorize a string

    Return a colorized string for printing in shell with style ;)

    Keyword arguments:
        - astr -- String to colorize
        - color -- Name of the color

    """
    if os.isatty(1):
        return "{:s}{:s}{:s}".format(colors_codes[color], astr, END_CLI_COLOR)
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
        print(d)


def pretty_date(_date):
    """Display a date in the current time zone without ms and tzinfo

    Argument:
        - date -- The date or datetime to display
    """
    import pytz  # Lazy loading, this takes like 3+ sec on a RPi2 ?!

    # Deduce system timezone
    nowutc = datetime.now(tz=pytz.utc)
    nowtz = datetime.now()
    nowtz = nowtz.replace(tzinfo=pytz.utc)
    offsetHour = nowutc - nowtz
    offsetHour = int(round(offsetHour.total_seconds() / 3600))
    localtz = "Etc/GMT%+d" % offsetHour

    # Transform naive date into UTC date
    if _date.tzinfo is None:
        _date = _date.replace(tzinfo=pytz.utc)

    # Convert UTC date into system locale date
    _date = _date.astimezone(pytz.timezone(localtz))
    if isinstance(_date, datetime):
        return _date.strftime("%Y-%m-%d %H:%M:%S")
    else:
        return _date.strftime("%Y-%m-%d")


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
        k = colorize(str(k), "purple")
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
                    if isinstance(v, date):
                        v = pretty_date(v)
                    print("{:s}- {}".format("  " * (depth + 1), value))
        else:
            if isinstance(v, date):
                v = pretty_date(v)
            print("{:s}{}: {}".format("  " * depth, k, v))


def get_locale():
    """Return current user eocale"""
    try:
        lang = locale.getdefaultlocale()[0]
    except Exception:
        # In some edge case the locale lib fails ...
        # c.f. https://forum.yunohost.org/t/error-when-trying-to-enter-user-information-in-admin-panel/11390/11
        lang = os.getenv("LANG")
    if not lang:
        return ""
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
        log.NOTSET: "white",
        log.DEBUG: "white",
        log.INFO: "cyan",
        log.SUCCESS: "green",
        log.WARNING: "yellow",
        log.ERROR: "red",
        log.CRITICAL: "red",
    }

    def __init__(self, message_key="fmessage"):
        logging.StreamHandler.__init__(self)
        self.message_key = message_key

    def format(self, record):
        """Enhance message with level and colors if supported."""
        msg = record.getMessage()
        if self.supports_color():
            level = ""
            if self.level <= log.DEBUG:
                # add level name before message
                level = "%s " % record.levelname
            elif record.levelname in ["SUCCESS", "WARNING", "ERROR", "INFO"]:
                # add translated level name before message
                level = "%s " % m18n.g(record.levelname.lower())
            color = self.LEVELS_COLOR.get(record.levelno, "white")
            msg = "{}{}{}{}".format(colors_codes[color], level, END_CLI_COLOR, msg)
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
        if hasattr(self.stream, "isatty") and self.stream.isatty():
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

    def __init__(
        self, parent=None, parser=None, subparser_kwargs=None, top_parser=None
    ):

        super(ActionsMapParser, self).__init__(parent)

        if subparser_kwargs is None:
            subparser_kwargs = {"title": "categories", "required": False}
        self._parser = parser or ExtendedArgumentParser()
        self._subparsers = self._parser.add_subparsers(**subparser_kwargs)
        self.global_parser = parent.global_parser if parent else None

        if top_parser:
            self.global_parser = self._parser.add_argument_group("global arguments")

            # Append each top parser action to the global group
            for action in top_parser._actions:
                action.dest = argparse.SUPPRESS
                self.global_parser._add_action(action)

    # Implement virtual properties

    interface = "cli"

    # Implement virtual methods

    @staticmethod
    def format_arg_names(name, full):
        if name.startswith("-") and full:
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
        parser = self._subparsers.add_parser(
            name, description=category_help, help=category_help, **kwargs
        )
        return self.__class__(
            parent=self,
            parser=parser,
            subparser_kwargs={"title": "subcommands", "required": True},
        )

    def add_subcategory_parser(self, name, subcategory_help=None, **kwargs):
        """Add a parser for a subcategory

        Keyword arguments:
            - subcategory_help -- A brief description for the category

        Returns:
            A new ActionsMapParser object for the category

        """
        parser = self._subparsers.add_parser(
            name,
            type_="subcategory",
            description=subcategory_help,
            help=subcategory_help,
            **kwargs,
        )
        return self.__class__(
            parent=self,
            parser=parser,
            subparser_kwargs={"title": "actions", "required": True},
        )

    def add_action_parser(
        self,
        name,
        tid,
        action_help=None,
        deprecated=False,
        deprecated_alias=[],
        hide_in_help=False,
        **kwargs,
    ):
        """Add a parser for an action

        Keyword arguments:
            - action_help -- A brief description for the action
            - deprecated -- Wether the action is deprecated
            - deprecated_alias -- A list of deprecated action alias names

        Returns:
            A new ExtendedArgumentParser object for the action

        """
        return self._subparsers.add_parser(
            name,
            type_="action",
            help=action_help,
            description=action_help,
            deprecated=deprecated,
            deprecated_alias=deprecated_alias,
            hide_in_help=hide_in_help,
        )

    def auth_method(self, args):

        ret = self.parse_args(args)
        tid = getattr(ret, "_tid", [])

        # We go down in the subparser tree until we find the leaf
        # corresponding to the tid with a defined authentication
        # (yeah it's a mess because the datastructure is a mess..)
        _p = self._subparsers
        for word in tid[1:]:
            _p = _p.choices[word]
            if hasattr(_p, "authentication"):
                return _p.authentication
            else:
                _p = _p._actions[1]

        raise MoulinetteError(f"Authentication undefined for {tid} ?", raw_msg=True)

    def parse_args(self, args, **kwargs):
        try:
            return self._parser.parse_args(args)
        except SystemExit:
            raise
        except Exception as e:
            error_message = "unable to parse arguments '{}' because: {}".format(
                " ".join(args),
                e,
            )
            logger.exception(error_message)
            raise MoulinetteValidationError(error_message, raw_msg=True)

    def want_to_take_lock(self, args):

        ret = self.parse_args(args)
        tid = getattr(ret, "_tid", [])
        if len(tid) == 3:
            _p = self._subparsers.choices[tid[1]]._actions[1].choices[tid[2]]
        elif len(tid) == 4:
            _p = (
                self._subparsers.choices[tid[1]]
                ._actions[1]
                .choices[tid[2]]
                ._actions[1]
                .choices[tid[3]]
            )

        return getattr(_p, "want_to_take_lock", True)


class Interface:

    """Command-line Interface for the moulinette

    Initialize an interface connected to the standard input/output
    stream and to a given actions map.

    Keyword arguments:
        - actionsmap -- The ActionsMap instance to connect to

    """

    type = "cli"

    def __init__(
        self,
        top_parser=None,
        load_only_category=None,
        actionsmap=None,
        locales_dir=None,
    ):

        # Set user locale
        m18n.set_locale(get_locale())

        self.actionsmap = ActionsMap(
            actionsmap,
            ActionsMapParser(top_parser=top_parser),
            load_only_category=load_only_category,
        )

        Moulinette._interface = self

    def run(self, args, output_as=None, timeout=None):
        """Run the moulinette

        Process the action corresponding to the given arguments 'args'
        and print the result.

        Keyword arguments:
            - args -- A list of argument strings
            - output_as -- Output result in another format. Possible values:
                - json: return a JSON encoded string
                - plain: return a script-readable output
                - none: do not output the result
            - timeout -- Number of seconds before this command will timeout because it can't acquire the lock (meaning that another command is currently running), by default there is no timeout and the command will wait until it can get the lock

        """

        if output_as and output_as not in ["json", "plain", "none"]:
            raise MoulinetteValidationError("invalid_usage")

        try:
            ret = self.actionsmap.process(args, timeout=timeout)
        except (KeyboardInterrupt, EOFError):
            raise MoulinetteError("operation_interrupted")

        if ret is None or output_as == "none":
            return

        # Format and print result
        if output_as:
            if output_as == "json":
                import json

                print(json.dumps(ret, cls=JSONExtendedEncoder))
            else:
                plain_print_dict(ret)
        elif isinstance(ret, dict):
            pretty_print_dict(ret)
        else:
            print(ret)

    def authenticate(self, authenticator):
        # Hmpf we have no-use case in yunohost anymore where we need to auth
        # because everything is run as root ...
        # I guess we could imagine some yunohost-independant use-case where
        # moulinette is used to create a CLI for non-root user that needs to
        # auth somehow but hmpf -.-
        msg = m18n.g("password")
        credentials = self.prompt(msg, True, False, color="yellow")
        return authenticator.authenticate_credentials(credentials=credentials)

    def prompt(
        self,
        message,
        is_password=False,
        confirm=False,
        color="blue",
        prefill="",
        is_multiline=False,
        autocomplete=[],
        help=None,
    ):
        """Prompt for a value

        Keyword arguments:
            - color -- The color to use for prompting message
        """

        if not os.isatty(1):
            raise MoulinetteError(
                "Not a tty, can't do interactive prompts", raw_msg=True
            )

        def _prompt(message):

            if not is_multiline:

                import prompt_toolkit
                from prompt_toolkit.completion import WordCompleter
                from prompt_toolkit.styles import Style

                autocomplete_ = WordCompleter(autocomplete)
                style = Style.from_dict(
                    {
                        "": "",
                        "message": f"#ansi{color} bold",
                    }
                )

                if help:

                    def bottom_toolbar():
                        return [("class:", help)]

                else:
                    bottom_toolbar = None

                colored_message = [
                    ("class:message", message),
                    ("class:", ": "),
                ]

                return prompt_toolkit.prompt(
                    colored_message,
                    bottom_toolbar=bottom_toolbar,
                    style=style,
                    default=prefill,
                    completer=autocomplete_,
                    complete_while_typing=True,
                    is_password=is_password,
                )

            else:
                while True:
                    value = input(
                        colorize(m18n.g("edit_text_question", message), color)
                    )
                    value = value.lower().strip()
                    if value in ["", "n", "no"]:
                        return prefill
                    elif value in ["y", "yes"]:
                        break

                initial_message = prefill.encode("utf-8")

                with tempfile.NamedTemporaryFile(suffix=".tmp") as tf:
                    tf.write(initial_message)
                    tf.flush()
                    call(["editor", tf.name])
                    tf.seek(0)
                    edited_message = tf.read()
                return edited_message.decode("utf-8")

        value = _prompt(message)

        if confirm:
            m = message[0].lower() + message[1:]
            if _prompt(m18n.g("confirm", prompt=m)) != value:
                raise MoulinetteValidationError("values_mismatch")

        return value

    def display(self, message, style="info"):  # i18n: info
        """Display a message"""
        if style == "success":
            print("{} {}".format(colorize(m18n.g("success"), "green"), message))
        elif style == "warning":
            print("{} {}".format(colorize(m18n.g("warning"), "yellow"), message))
        elif style == "error":
            print("{} {}".format(colorize(m18n.g("error"), "red"), message))
        else:
            print(message)
