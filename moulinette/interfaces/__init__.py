# -*- coding: utf-8 -*-

import re
import os
import errno
import logging
import argparse
from collections import deque

from moulinette.core import (init_authenticator, MoulinetteError)

logger = logging.getLogger('moulinette.interface')

GLOBAL_SECTION = '_global'
TO_RETURN_PROP = '_to_return'
CALLBACKS_PROP = '_callbacks'


# Base Class -----------------------------------------------------------

class BaseActionsMapParser(object):
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
        if parent:
            self._o = parent
        else:
            logger.debug('initializing base actions map parser for %s',
                         self.interface)
            msettings['interface'] = self.interface

            self._o = self
            self._global_conf = {}
            self._conf = {}

    # Virtual properties
    # Each parser classes must implement these properties.

    """The name of the interface for which it is the parser"""
    interface = None

    # Virtual methods
    # Each parser classes must implement these methods.

    @staticmethod
    def format_arg_names(self, name, full):
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
        raise NotImplementedError("derived class '%s' must override this method" %
                                  self.__class__.__name__)

    def add_global_parser(self, **kwargs):
        """Add a parser for global arguments

        Create and return an argument parser for global arguments.

        Returns:
            An ArgumentParser based object

        """
        raise NotImplementedError("derived class '%s' must override this method" %
                                  self.__class__.__name__)

    def add_category_parser(self, name, **kwargs):
        """Add a parser for a category

        Create a new category and return a parser for it.

        Keyword arguments:
            - name -- The category name

        Returns:
            A BaseParser based object

        """
        raise NotImplementedError("derived class '%s' must override this method" %
                                  self.__class__.__name__)

    def add_action_parser(self, name, tid, **kwargs):
        """Add a parser for an action

        Create a new action and return an argument parser for it.

        Keyword arguments:
            - name -- The action name
            - tid -- The tuple identifier of the action

        Returns:
            An ArgumentParser based object

        """
        raise NotImplementedError("derived class '%s' must override this method" %
                                  self.__class__.__name__)

    def parse_args(self, args, **kwargs):
        """Parse arguments

        Convert argument variables to objects and assign them as
        attributes of the namespace.

        Keyword arguments:
            - args -- Arguments string or dict (TODO)

        Returns:
            The populated namespace

        """
        raise NotImplementedError("derived class '%s' must override this method" %
                                  self.__class__.__name__)

    # Arguments helpers

    def prepare_action_namespace(self, tid, namespace=None):
        """Prepare the namespace for a given action"""
        # Validate tid and namespace
        if not isinstance(tid, tuple) and \
                (namespace is None or not hasattr(namespace, TO_RETURN_PROP)):
            raise MoulinetteError(errno.EINVAL, m18n.g('invalid_usage'))
        elif not tid:
            tid = GLOBAL_SECTION

        # Prepare namespace
        if namespace is None:
            namespace = argparse.Namespace()
        namespace._tid = tid

        # Check lock
        if not self.get_conf(tid, 'lock'):
            os.environ['BYPASS_LOCK'] = 'yes'

        # Perform authentication if needed
        if self.get_conf(tid, 'authenticate'):
            auth_conf, cls = self.get_conf(tid, 'authenticator')

            # TODO: Catch errors
            auth = msignals.authenticate(cls(), **auth_conf)
            if not auth.is_authenticated:
                raise MoulinetteError(errno.EACCES,
                                      m18n.g('authentication_required_long'))
            if self.get_conf(tid, 'argument_auth') and \
                    self.get_conf(tid, 'authenticate') == 'all':
                namespace.auth = auth

        return namespace

    # Configuration access

    @property
    def global_conf(self):
        """Return the global configuration of the parser"""
        return self._o._global_conf

    def get_global_conf(self, name, profile='default'):
        """Get the global value of a configuration

        Return the formated global value of the configuration 'name' for
        the given profile. If the configuration doesn't provide profile,
        the formated default value is returned.

        Keyword arguments:
            - name -- The configuration name
            - profile -- The profile of the configuration

        """
        if name == 'authenticator':
            value = self.global_conf[name][profile]
        else:
            value = self.global_conf[name]
        return self._format_conf(name, value)

    def set_global_conf(self, configuration):
        """Set global configuration

        Set the global configuration to use for the parser.

        Keyword arguments:
            - configuration -- The global configuration

        """
        self._o._global_conf.update(self._validate_conf(configuration, True))

    def get_conf(self, action, name):
        """Get the value of an action configuration

        Return the formated value of configuration 'name' for the action
        identified by 'action'. If the configuration for the action is
        not set, the default one is returned.

        Keyword arguments:
            - action -- An action identifier
            - name -- The configuration name

        """
        try:
            value = self._o._conf[action][name]
        except KeyError:
            return self.get_global_conf(name)
        else:
            return self._format_conf(name, value)

    def set_conf(self, action, configuration):
        """Set configuration for an action

        Set the configuration to use for a given action identified by
        'action' which is specific to the parser.

        Keyword arguments:
            - action -- The action identifier
            - configuration -- The configuration for the action

        """
        self._o._conf[action] = self._validate_conf(configuration)

    def _validate_conf(self, configuration, is_global=False):
        """Validate configuration for the parser

        Return the validated configuration for the interface's actions
        map parser.

        Keyword arguments:
            - configuration -- The configuration to pre-format

        """
        # TODO: Create a class with a validator method for each configuration
        conf = {}

        # -- 'authenficate'
        try:
            ifaces = configuration['authenticate']
        except KeyError:
            pass
        else:
            if ifaces == 'all':
                conf['authenticate'] = ifaces
            elif ifaces is False:
                conf['authenticate'] = False
            elif isinstance(ifaces, list):
                # Store only if authentication is needed
                conf['authenticate'] = True if self.interface in ifaces else False
            else:
                logger.error("expecting 'all', 'False' or a list for "
                             "configuration 'authenticate', got %r", ifaces)
                raise MoulinetteError(errno.EINVAL, m18n.g('error_see_log'))

        # -- 'authenticator'
        try:
            auth = configuration['authenticator']
        except KeyError:
            pass
        else:
            if not is_global and isinstance(auth, str):
                try:
                    # Store needed authenticator profile
                    conf['authenticator'] = self.global_conf['authenticator'][auth]
                except KeyError:
                    logger.error("requesting profile '%s' which is undefined in "
                                 "global configuration of 'authenticator'", auth)
                    raise MoulinetteError(errno.EINVAL, m18n.g('error_see_log'))
            elif is_global and isinstance(auth, dict):
                if len(auth) == 0:
                    logger.warning('no profile defined in global configuration '
                                   "for 'authenticator'")
                else:
                    auths = {}
                    for auth_name, auth_conf in auth.items():
                        # Add authenticator profile as a 3-tuple
                        # (identifier, configuration, parameters) with
                        # - identifier: the authenticator vendor and its
                        #     profile name as a 2-tuple
                        # - configuration: a dict of additional global
                        #     configuration (i.e. 'help')
                        # - parameters: a dict of arguments for the
                        #     authenticator profile
                        auths[auth_name] = ((auth_conf.get('vendor'), auth_name),
                                            {'help': auth_conf.get('help', None)},
                                            auth_conf.get('parameters', {}))
                    conf['authenticator'] = auths
            else:
                logger.error("expecting a dict of profile(s) or a profile name "
                             "for configuration 'authenticator', got %r", auth)
                raise MoulinetteError(errno.EINVAL, m18n.g('error_see_log'))

        # -- 'argument_auth'
        try:
            arg_auth = configuration['argument_auth']
        except KeyError:
            pass
        else:
            if isinstance(arg_auth, bool):
                conf['argument_auth'] = arg_auth
            else:
                logger.error("expecting a boolean for configuration "
                             "'argument_auth', got %r", arg_auth)
                raise MoulinetteError(errno.EINVAL, m18n.g('error_see_log'))

        # -- 'lock'
        try:
            lock = configuration['lock']
        except KeyError:
            pass
        else:
            if isinstance(lock, bool):
                conf['lock'] = lock
            else:
                logger.error("expecting a boolean for configuration 'lock', "
                             "got %r", lock)
                raise MoulinetteError(errno.EINVAL, m18n.g('error_see_log'))

        return conf

    def _format_conf(self, name, value):
        """Format a configuration value

        Return the formated value of the configuration 'name' from its
        given value.

        Keyword arguments:
            - name -- The name of the configuration
            - value -- The value to format

        """
        if name == 'authenticator' and value:
            (identifier, configuration, parameters) = value

            # Return global configuration and an authenticator
            # instanciator as a 2-tuple
            return (configuration,
                    lambda: init_authenticator(identifier, parameters))

        return value


class BaseInterface(object):
    """Moulinette's base Interface

    Each interfaces must implement an Interface class derived from this
    class which must overrides virtual properties and methods.
    It is used to provide a user interface for an actions map.

    Keyword arguments:
        - actionsmap -- The ActionsMap instance to connect to

    """
    # TODO: Add common interface methods and try to standardize default ones

    def __init__(self, actionsmap):
        raise NotImplementedError("derived class '%s' must override this method" %
                                  self.__class__.__name__)


# Argument parser ------------------------------------------------------

class _CallbackAction(argparse.Action):

    def __init__(self,
                 option_strings,
                 dest,
                 nargs=0,
                 callback={},
                 default=argparse.SUPPRESS,
                 help=None):
        if not callback or 'method' not in callback:
            raise ValueError('callback must be provided with at least '
                             'a method key')
        super(_CallbackAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=nargs,
            default=default,
            help=help)
        self.callback_method = callback.get('method')
        self.callback_kwargs = callback.get('kwargs', {})
        self.callback_return = callback.get('return', False)
        logger.debug("registering new callback action '{0}' to {1}".format(
            self.callback_method, option_strings))

    @property
    def callback(self):
        if not hasattr(self, '_callback'):
            self._retrieve_callback()
        return self._callback

    def _retrieve_callback(self):
        # Attempt to retrieve callback method
        mod_name, func_name = (self.callback_method).rsplit('.', 1)
        try:
            mod = __import__(mod_name, globals=globals(), level=0,
                             fromlist=[func_name])
            func = getattr(mod, func_name)
        except (AttributeError, ImportError):
            raise ValueError('unable to import method {0}'.format(
                self.callback_method))
        self._callback = func

    def __call__(self, parser, namespace, values, option_string=None):
        parser.enqueue_callback(namespace, self, values)
        if self.callback_return:
            setattr(namespace, TO_RETURN_PROP, {})

    def execute(self, namespace, values):
        try:
            # Execute callback and get returned value
            value = self.callback(namespace, values, **self.callback_kwargs)
        except:
            logger.exception("cannot get value from callback method "
                "'{0}'".format(self.callback_method))
            raise MoulinetteError(errno.EINVAL, m18n.g('error_see_log'))
        else:
            if value:
                if self.callback_return:
                    setattr(namespace, TO_RETURN_PROP, value)
                else:
                    setattr(namespace, self.dest, value)


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
        required = kwargs.pop('required', False)
        super(_ExtendedSubParsersAction, self).__init__(*args, **kwargs)

        self.required = required
        self._deprecated_command_map = {}

    def add_parser(self, name, **kwargs):
        deprecated = kwargs.pop('deprecated', False)
        deprecated_alias = kwargs.pop('deprecated_alias', [])

        if deprecated:
            self._deprecated_command_map[name] = None
            if 'help' in kwargs:
                del kwargs['help']

        parser = super(_ExtendedSubParsersAction, self).add_parser(
            name, **kwargs)

        # Append each deprecated command alias name
        for command in deprecated_alias:
            self._deprecated_command_map[command] = name
            self._name_parser_map[command] = parser

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
                logger.warning(m18n.g('deprecated_command', prog=parser.prog,
                                      command=parser_name))
            else:
                logger.warning(m18n.g('deprecated_command_alias',
                                      old=parser_name, new=correct_name,
                                      prog=parser.prog))
                values[0] = correct_name

        return super(_ExtendedSubParsersAction, self).__call__(
            parser, namespace, values, option_string)


class ExtendedArgumentParser(argparse.ArgumentParser):

    def __init__(self, *args, **kwargs):
        super(ExtendedArgumentParser, self).__init__(
                formatter_class=PositionalsFirstHelpFormatter, *args, **kwargs)

        # Register additional actions
        self.register('action', 'callback', _CallbackAction)
        self.register('action', 'parsers', _ExtendedSubParsersAction)

    def enqueue_callback(self, namespace, callback, values):
        queue = self._get_callbacks_queue(namespace)
        queue.append((callback, values))

    def dequeue_callbacks(self, namespace):
        queue = self._get_callbacks_queue(namespace, False)
        for _i in xrange(len(queue)):
            c, v = queue.popleft()
            # FIXME: break dequeue if callback returns
            c.execute(namespace, v)
        try:
            delattr(namespace, CALLBACKS_PROP)
        except:
            pass

    def _get_callbacks_queue(self, namespace, create=True):
        try:
            queue = getattr(namespace, CALLBACKS_PROP)
        except AttributeError:
            if create:
                queue = deque()
                setattr(namespace, CALLBACKS_PROP, queue)
            else:
                queue = list()
        return queue

    def _get_nargs_pattern(self, action):
        if action.nargs == argparse.PARSER and not action.required:
            return '([-AO]*)'
        else:
            return super(ExtendedArgumentParser, self)._get_nargs_pattern(
                action)

    def _get_values(self, action, arg_strings):
        if action.nargs == argparse.PARSER and not action.required:
            value = [self._get_value(action, v) for v in arg_strings]
            if value:
                self._check_value(action, value[0])
            else:
                value = argparse.SUPPRESS
        else:
            value = super(ExtendedArgumentParser, self)._get_values(
                action, arg_strings)
        return value


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
                prefix = 'usage: '

            # if usage is specified, use that
            if usage is not None:
                usage = usage % dict(prog=self._prog)

            # if no optionals or positionals are available, usage is just prog
            elif usage is None and not actions:
                usage = '%(prog)s' % dict(prog=self._prog)

            # if optionals and positionals are available, calculate usage
            elif usage is None:
                prog = '%(prog)s' % dict(prog=self._prog)

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
                usage = ' '.join([s for s in [prog, action_usage] if s])

                # wrap the usage parts if it's too long
                text_width = self._width - self._current_indent
                if len(prefix) + len(usage) > text_width:

                    # break usage into wrappable parts
                    part_regexp = r'\(.*?\)+|\[.*?\]+|\S+'
                    opt_usage = format(optionals, groups)
                    pos_usage = format(positionals, groups)
                    opt_parts = re.findall(part_regexp, opt_usage)
                    pos_parts = re.findall(part_regexp, pos_usage)
                    assert ' '.join(opt_parts) == opt_usage
                    assert ' '.join(pos_parts) == pos_usage

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
                                lines.append(indent + ' '.join(line))
                                line = []
                                line_len = len(indent) - 1
                            line.append(part)
                            line_len += len(part) + 1
                        if line:
                            lines.append(indent + ' '.join(line))
                        if prefix is not None:
                            lines[0] = lines[0][len(indent):]
                        return lines

                    # if prog is short, follow it with optionals or positionals
                    if len(prefix) + len(prog) <= 0.75 * text_width:
                        indent = ' ' * (len(prefix) + len(prog) + 1)
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
                        indent = ' ' * len(prefix)
                        parts = pos_parts + opt_parts
                        lines = get_lines(parts, indent)
                        if len(lines) > 1:
                            lines = []
                            # TWEAK here : pos_parts first, then opt_part
                            lines.extend(get_lines(pos_parts, indent))
                            lines.extend(get_lines(opt_parts, indent))
                        lines = [prog] + lines

                    # join lines into usage
                    usage = '\n'.join(lines)

            # prefix with 'usage:'
            return '%s%s\n\n' % (prefix, usage)
