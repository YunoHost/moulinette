# -*- coding: utf-8 -*-

import re
import logging
import argparse
import copy
import datetime
from collections import OrderedDict
from json.encoder import JSONEncoder
from typing import Optional

from moulinette import m18n

logger = logging.getLogger("moulinette.interface")


# Base Class -----------------------------------------------------------


class BaseActionsMapParser:

    """Actions map's base Parser

    Each interfaces must implement an ActionsMapParser class derived
    from this class which must overrides virtual properties and methods.
    It is used to parse the main parts of the actions map (i.e. global
    arguments, categories and actions). It implements methods to set/get
    the global and actions configuration.

    Keyword arguments:
        - parent -- A parent BaseActionsMapParser derived object

    """

    def __init__(self, parent=None, **kwargs):
        pass

    # Virtual properties
    # Each parser classes must implement these properties.

    """The name of the interface for which it is the parser"""
    interface: Optional[str] = None

    # Virtual methods
    # Each parser classes must implement these methods.

    @staticmethod
    def format_arg_names(name, full):
        """Format argument name

        Format agument name depending on its 'full' parameter and return
        a list of strings which will be used as name or option strings
        for the argument parser.

        Keyword arguments:
            - name -- The argument name
            - full -- The argument's 'full' parameter

        Returns:
            A list of option strings

        """
        raise NotImplementedError("derived class must override this method")

    def has_global_parser(self):
        return False

    def add_global_parser(self, **kwargs):
        """Add a parser for global arguments

        Create and return an argument parser for global arguments.

        Returns:
            An ArgumentParser based object

        """
        raise NotImplementedError(
            "derived class '%s' must override this method" % self.__class__.__name__
        )

    def add_category_parser(self, name, **kwargs):
        """Add a parser for a category

        Create a new category and return a parser for it.

        Keyword arguments:
            - name -- The category name

        Returns:
            A BaseParser based object

        """
        raise NotImplementedError(
            "derived class '%s' must override this method" % self.__class__.__name__
        )

    def add_action_parser(self, name, tid, **kwargs):
        """Add a parser for an action

        Create a new action and return an argument parser for it.

        Keyword arguments:
            - name -- The action name
            - tid -- The tuple identifier of the action

        Returns:
            An ArgumentParser based object

        """
        raise NotImplementedError(
            "derived class '%s' must override this method" % self.__class__.__name__
        )

    def auth_method(self, *args, **kwargs):
        """Check if authentication is required to run the requested action

        Keyword arguments:
            - args -- Arguments string or dict (TODO)

        Returns:
            False, or the authentication profile required

        """
        raise NotImplementedError(
            "derived class '%s' must override this method" % self.__class__.__name__
        )

    def parse_args(self, args, **kwargs):
        """Parse arguments

        Convert argument variables to objects and assign them as
        attributes of the namespace.

        Keyword arguments:
            - args -- Arguments string or dict (TODO)

        Returns:
            The populated namespace

        """
        raise NotImplementedError(
            "derived class '%s' must override this method" % self.__class__.__name__
        )


# Argument parser ------------------------------------------------------


class _ExtendedSubParsersAction(argparse._SubParsersAction):

    """Subparsers with extended properties for argparse

    It provides the following additional properties at initialization,
    e.g. using `parser.add_subparsers`:
      - required -- Either the subparser is required or not (default: False)

    It also provides the following additional properties for parsers,
    e.g. using `subparsers.add_parser`:
      - deprecated -- Wether the command is deprecated
      - deprecated_alias -- A list of deprecated command alias names

    """

    def __init__(self, *args, **kwargs):
        required = kwargs.pop("required", False)
        super(_ExtendedSubParsersAction, self).__init__(*args, **kwargs)

        self.required = required
        self._deprecated_command_map = {}

    def add_parser(self, name, type_=None, **kwargs):
        hide_in_help = kwargs.pop("hide_in_help", False)
        deprecated = kwargs.pop("deprecated", False)
        deprecated_alias = kwargs.pop("deprecated_alias", [])

        if deprecated:
            self._deprecated_command_map[name] = None

        if deprecated or hide_in_help:
            if "help" in kwargs:
                del kwargs["help"]

        parser = super(_ExtendedSubParsersAction, self).add_parser(name, **kwargs)

        # Append each deprecated command alias name
        for command in deprecated_alias:
            self._deprecated_command_map[command] = name
            self._name_parser_map[command] = parser

        parser.type = type_

        return parser

    def __call__(self, parser, namespace, values, option_string=None):
        parser_name = values[0]

        try:
            # Check for deprecated command name
            correct_name = self._deprecated_command_map[parser_name]
        except KeyError:
            pass
        else:
            # Warn the user about deprecated command
            if correct_name is None:
                logger.warning(
                    m18n.g("deprecated_command", prog=parser.prog, command=parser_name)
                )
            else:
                logger.warning(
                    m18n.g(
                        "deprecated_command_alias",
                        old=parser_name,
                        new=correct_name,
                        prog=parser.prog,
                    )
                )
                values[0] = correct_name

        return super(_ExtendedSubParsersAction, self).__call__(
            parser, namespace, values, option_string
        )


class ExtendedArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super(ExtendedArgumentParser, self).__init__(
            formatter_class=PositionalsFirstHelpFormatter, *args, **kwargs
        )

        # Register additional actions
        self.register("action", "parsers", _ExtendedSubParsersAction)

    def add_arguments(
        self, arguments, extraparser, format_arg_names=None, validate_extra=True
    ):
        for argument_name, argument_options in arguments.items():
            # will adapt arguments name for cli or api context
            names = format_arg_names(
                str(argument_name), argument_options.pop("full", None)
            )

            if "type" in argument_options:
                argument_options["type"] = eval(argument_options["type"])

            if "extra" in argument_options:
                extra = argument_options.pop("extra")
                argument_dest = self.add_argument(*names, **argument_options).dest
                extraparser.add_argument(
                    self.get_default("_tid"), argument_dest, extra, validate_extra
                )
                continue

            self.add_argument(*names, **argument_options)

    def _get_nargs_pattern(self, action):
        if action.nargs == argparse.PARSER and not action.required:
            return "([-AO]*)"
        else:
            return super(ExtendedArgumentParser, self)._get_nargs_pattern(action)

    def _get_values(self, action, arg_strings):
        if action.nargs == argparse.PARSER and not action.required:
            value = [self._get_value(action, v) for v in arg_strings]
            if value:
                self._check_value(action, value[0])
            else:
                value = argparse.SUPPRESS
        else:
            value = super(ExtendedArgumentParser, self)._get_values(action, arg_strings)
        return value

    # Adapted from :
    # https://github.com/python/cpython/blob/af26c15110b76195e62a06d17e39176d42c0511c/Lib/argparse.py#L2293-L2314
    def format_help(self):
        formatter = self._get_formatter()

        # usage
        formatter.add_usage(self.usage, self._actions, self._mutually_exclusive_groups)

        # description
        formatter.add_text(self.description)

        # positionals, optionals and user-defined groups
        for action_group in self._action_groups:
            # Dirty hack to separate 'subcommands'
            # into 'actions' and 'subcategories'
            if action_group.title == "subcommands":
                # Make a copy of the "action group actions"...
                choice_actions = action_group._group_actions[0]._choices_actions
                actions_subparser = copy.copy(action_group._group_actions[0])
                subcategories_subparser = copy.copy(action_group._group_actions[0])

                # Filter "action"-type and "subcategory"-type commands
                actions_subparser.choices = OrderedDict(
                    [
                        (k, v)
                        for k, v in actions_subparser.choices.items()
                        if v.type == "action"
                    ]
                )
                subcategories_subparser.choices = OrderedDict(
                    [
                        (k, v)
                        for k, v in subcategories_subparser.choices.items()
                        if v.type == "subcategory"
                    ]
                )

                actions_choices = actions_subparser.choices.keys()
                subcategories_choices = subcategories_subparser.choices.keys()

                actions_subparser._choices_actions = [
                    c for c in choice_actions if c.dest in actions_choices
                ]
                subcategories_subparser._choices_actions = [
                    c for c in choice_actions if c.dest in subcategories_choices
                ]

                # Display each section (actions and subcategories)
                if actions_choices:
                    formatter.start_section("actions")
                    formatter.add_arguments([actions_subparser])
                    formatter.end_section()

                if subcategories_choices:
                    formatter.start_section("subcategories")
                    formatter.add_arguments([subcategories_subparser])
                    formatter.end_section()

            else:
                formatter.start_section(action_group.title)
                formatter.add_text(action_group.description)
                formatter.add_arguments(action_group._group_actions)
                formatter.end_section()

        # epilog
        formatter.add_text(self.epilog)

        # determine help from format above
        return formatter.format_help()


# This is copy-pasta from the original argparse.HelpFormatter :
# https://github.com/python/cpython/blob/1e73dbbc29c96d0739ffef92db36f63aa1aa30da/Lib/argparse.py#L293-L383
# tweaked to display positional arguments first in usage/--help
#
# This is motivated by the "bug" / inconsistent behavior described here :
# http://bugs.python.org/issue9338
# and fix is inspired from here :
# https://stackoverflow.com/questions/26985650/argparse-do-not-catch-positional-arguments-with-nargs/26986546#26986546
class PositionalsFirstHelpFormatter(argparse.HelpFormatter):
    def _format_usage(self, usage, actions, groups, prefix):
        if prefix is None:
            # TWEAK : not using gettext here...
            prefix = "usage: "

        # if usage is specified, use that
        if usage is not None:
            usage = usage % dict(prog=self._prog)

        # if no optionals or positionals are available, usage is just prog
        elif usage is None and not actions:
            usage = "%(prog)s" % dict(prog=self._prog)

        # if optionals and positionals are available, calculate usage
        elif usage is None:
            prog = "%(prog)s" % dict(prog=self._prog)

            # split optionals from positionals
            optionals = []
            positionals = []
            for action in actions:
                if action.option_strings:
                    optionals.append(action)
                else:
                    positionals.append(action)

            # build full usage string
            format = self._format_actions_usage
            # TWEAK here : positionals first
            action_usage = format(positionals + optionals, groups)
            usage = " ".join([s for s in [prog, action_usage] if s])

            # wrap the usage parts if it's too long
            text_width = self._width - self._current_indent
            if len(prefix) + len(usage) > text_width:
                # break usage into wrappable parts
                part_regexp = r"\(.*?\)+|\[.*?\]+|\S+"
                opt_usage = format(optionals, groups)
                pos_usage = format(positionals, groups)
                opt_parts = re.findall(part_regexp, opt_usage)
                pos_parts = re.findall(part_regexp, pos_usage)
                assert " ".join(opt_parts) == opt_usage
                assert " ".join(pos_parts) == pos_usage

                # helper for wrapping lines
                def get_lines(parts, indent, prefix=None):
                    lines = []
                    line = []
                    if prefix is not None:
                        line_len = len(prefix) - 1
                    else:
                        line_len = len(indent) - 1
                    for part in parts:
                        if line_len + 1 + len(part) > text_width:
                            lines.append(indent + " ".join(line))
                            line = []
                            line_len = len(indent) - 1
                        line.append(part)
                        line_len += len(part) + 1
                    if line:
                        lines.append(indent + " ".join(line))
                    if prefix is not None:
                        lines[0] = lines[0][len(indent) :]
                    return lines

                # if prog is short, follow it with optionals or positionals
                if len(prefix) + len(prog) <= 0.75 * text_width:
                    indent = " " * (len(prefix) + len(prog) + 1)
                    # START TWEAK : pos_parts first, then opt_parts
                    if pos_parts:
                        lines = get_lines([prog] + pos_parts, indent, prefix)
                        lines.extend(get_lines(opt_parts, indent))
                    elif opt_parts:
                        lines = get_lines([prog] + opt_parts, indent, prefix)
                    # END TWEAK
                    else:
                        lines = [prog]

                # if prog is long, put it on its own line
                else:
                    indent = " " * len(prefix)
                    parts = pos_parts + opt_parts
                    lines = get_lines(parts, indent)
                    if len(lines) > 1:
                        lines = []
                        # TWEAK here : pos_parts first, then opt_part
                        lines.extend(get_lines(pos_parts, indent))
                        lines.extend(get_lines(opt_parts, indent))
                    lines = [prog] + lines

                # join lines into usage
                usage = "\n".join(lines)

        # prefix with 'usage:'
        return "{}{}\n\n".format(prefix, usage)


class JSONExtendedEncoder(JSONEncoder):

    """Extended JSON encoder

    Extend default JSON encoder to recognize more types and classes. It will
    never raise an exception if the object can't be encoded and return its repr
    instead.

    The following objects and types are supported:
        - set: converted into list

    """

    def default(self, o):
        import pytz  # Lazy loading, this takes like 3+ sec on a RPi2 ?!

        """Return a serializable object"""
        # Convert compatible containers into list
        if isinstance(o, set) or (hasattr(o, "__iter__") and hasattr(o, "next")):
            return list(o)

        # Display the date in its iso format ISO-8601 Internet Profile (RFC 3339)
        if isinstance(o, datetime.date):
            if o.tzinfo is None:
                o = o.replace(tzinfo=pytz.utc)
            return o.isoformat()

        # Return the repr for object that json can't encode
        logger.warning(
            "cannot properly encode in JSON the object %s, " "returned repr is: %r",
            type(o),
            o,
        )
        return repr(o)
