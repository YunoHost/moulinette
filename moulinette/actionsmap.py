# -*- coding: utf-8 -*-

import os
import re
import errno
import logging
import yaml
import cPickle as pickle
from collections import OrderedDict

from moulinette.core import (MoulinetteError, MoulinetteLock)
from moulinette.interfaces import BaseActionsMapParser

## Extra parameters ----------------------------------------------------

# Extra parameters definition

class _ExtraParameter(object):
    """
    Argument parser for an extra parameter.

    It is a pure virtual class that each extra parameter classes must
    implement.

    """
    def __init__(self, iface):
        # TODO: Add conn argument which contains authentification object
        self.iface = iface


    ## Required variables
    # Each extra parameters classes must overwrite these variables.

    """The extra parameter name"""
    name = None


    ## Optional variables
    # Each extra parameters classes can overwrite these variables.

    """A list of interface for which the parameter doesn't apply"""
    skipped_iface = []


    ## Virtual methods
    # Each extra parameters classes can implement these methods.

    def __call__(self, parameter, arg_name, arg_value):
        """
        Parse the argument

        Keyword arguments:
            - parameter -- The value of this parameter for the action
            - arg_name -- The argument name
            - arg_value -- The argument value

        Returns:
            The new argument value

        """
        return arg_value

    @staticmethod
    def validate(value, arg_name):
        """
        Validate the parameter value for an argument

        Keyword arguments:
            - value -- The parameter value
            - arg_name -- The argument name

        Returns:
            The validated parameter value

        """
        return value

class AskParameter(_ExtraParameter):
    """
    Ask for the argument value if possible and needed.

    The value of this parameter corresponds to the message to display
    when asking the argument value.

    """
    name = 'ask'
    skipped_iface = [ 'api' ]

    def __call__(self, message, arg_name, arg_value):
        # TODO: Fix asked arguments ordering
        if arg_value:
            return arg_value

        try:
            # Ask for the argument value
            return msignals.prompt(message)
        except NotImplementedError:
            return arg_value

    @classmethod
    def validate(klass, value, arg_name):
        # Allow boolean or empty string
        if isinstance(value, bool) or (isinstance(value, str) and not value):
            logging.debug("value of '%s' extra parameter for '%s' argument should be a string" \
                % (klass.name, arg_name))
            value = arg_name
        elif not isinstance(value, str):
            raise TypeError("Invalid type of '%s' extra parameter for '%s' argument" \
                % (klass.name, arg_name))
        return value

class PasswordParameter(AskParameter):
    """
    Ask for the password argument value if possible and needed.

    The value of this parameter corresponds to the message to display
    when asking the password.

    """
    name = 'password'

    def __call__(self, message, arg_name, arg_value):
        if arg_value:
            return arg_value

        try:
            # Ask for the password
            return msignals.prompt(message, True, True)
        except NotImplementedError:
            return arg_value

class PatternParameter(_ExtraParameter):
    """
    Check if the argument value match a pattern.

    The value of this parameter corresponds to a list of the pattern and
    the message to display if it doesn't match.

    """
    name = 'pattern'

    def __call__(self, arguments, arg_name, arg_value):
        pattern, message = (arguments[0], arguments[1])

        if arg_value and not re.match(pattern, arg_value or ''):
            raise MoulinetteError(errno.EINVAL, message)
        return arg_value

    @staticmethod
    def validate(value, arg_name):
        # Tolerate string type
        if isinstance(value, str):
            logging.warning("value of 'pattern' extra parameter for '%s' argument should be a list" % arg_name)
            value = [value, _("'%s' argument is not matching the pattern") % arg_name]
        elif not isinstance(value, list) or len(value) != 2:
            raise TypeError("Invalid type of 'pattern' extra parameter for '%s' argument" % arg_name)
        return value

"""
The list of available extra parameters classes. It will keep to this list
order on argument parsing.

"""
extraparameters_list = [AskParameter, PasswordParameter, PatternParameter]

# Extra parameters argument Parser

class ExtraArgumentParser(object):
    """
    Argument validator and parser for the extra parameters.

    Keyword arguments:
        - iface -- The running interface

    """
    def __init__(self, iface):
        self.iface = iface
        self.extra = OrderedDict()

        # Append available extra parameters for the current interface
        for klass in extraparameters_list:
            if iface in klass.skipped_iface:
                continue
            self.extra[klass.name] = klass

    def validate(self, arg_name, parameters):
        """
        Validate values of extra parameters for an argument

        Keyword arguments:
            - arg_name -- The argument name
            - parameters -- A dict of extra parameters with their values

        """
        # Iterate over parameters to validate
        for p, v in parameters.items():
            klass = self.extra.get(p, None)
            if not klass:
                # Remove unknown parameters
                del parameters[p]
            else:
                # Validate parameter value
                parameters[p] = klass.validate(v, arg_name)

        return parameters

    def parse(self, arg_name, arg_value, parameters):
        """
        Parse argument with extra parameters

        Keyword arguments:
            - arg_name -- The argument name
            - arg_value -- The argument value
            - parameters -- A dict of extra parameters with their values

        """
        # Iterate over available parameters
        for p, klass in self.extra.items():
            if p not in parameters.keys():
                continue

            # Initialize the extra parser
            parser = klass(self.iface)

            # Parse the argument
            if isinstance(arg_value, list):
                for v in arg_value:
                    r = parser(parameters[p], arg_name, v)
                    if r not in arg_value:
                        arg_value.append(r)
            else:
                arg_value = parser(parameters[p], arg_name, arg_value)

        return arg_value


## Main class ----------------------------------------------------------

class ActionsMap(object):
    """Validate and process actions defined into an actions map

    The actions map defines the features - and their usage - of an
    application which will be available through the moulinette.
    It is composed by categories which contain one or more action(s).
    Moreover, the action can have specific argument(s).

    This class allows to manipulate one or several actions maps
    associated to a namespace. If no namespace is given, it will load
    all available namespaces.

    Keyword arguments:
        - parser -- The BaseActionsMapParser derived class to use for
            parsing the actions map
        - namespaces -- The list of namespaces to use
        - use_cache -- False if it should parse the actions map file
            instead of using the cached one.

    """
    def __init__(self, parser, namespaces=[], use_cache=True):
        self.use_cache = use_cache
        if not issubclass(parser, BaseActionsMapParser):
            raise ValueError("Invalid parser class '%s'" % parser.__name__)
        self._parser_class = parser

        logging.debug("initializing ActionsMap for the interface '%s'" % parser.interface)

        if len(namespaces) == 0:
            namespaces = self.get_namespaces()
        actionsmaps = OrderedDict()

        # Iterate over actions map namespaces
        for n in namespaces:
            logging.debug("loading '%s' actions map namespace" % n)

            if use_cache:
                try:
                    # Attempt to load cache
                    with open('%s/actionsmap/%s.pkl' % (pkg.cachedir, n)) as f:
                        actionsmaps[n] = pickle.load(f)
                # TODO: Switch to python3 and catch proper exception
                except IOError:
                    self.use_cache = False
                    actionsmaps = self.generate_cache(namespaces)
                    break
            else:
                with open('%s/actionsmap/%s.yml' % (pkg.datadir, n)) as f:
                    actionsmaps[n] = yaml.load(f)

        # Generate parsers
        self.extraparser = ExtraArgumentParser(parser.interface)
        self._parser = self._construct_parser(actionsmaps)

    @property
    def parser(self):
        """Return the instance of the interface's actions map parser"""
        return self._parser

    def get_authenticator(self, profile='default'):
        """Get an authenticator instance

        Retrieve the authenticator for the given profile and return a
        new instance.

        Keyword arguments:
            - profile -- An authenticator profile name

        Returns:
            A new _BaseAuthenticator derived instance

        """
        try:
            auth = self.parser.get_global_conf('authenticator', profile)[1]
        except KeyError:
            raise ValueError("Unknown authenticator profile '%s'" % profile)
        else:
            return auth()

    def process(self, args, timeout=0, **kwargs):
        """
        Parse arguments and process the proper action

        Keyword arguments:
            - args -- The arguments to parse
            - timeout -- The time period before failing if the lock
                cannot be acquired for the action
            - **kwargs -- Additional interface arguments

        """
        # Parse arguments
        arguments = vars(self.parser.parse_args(args, **kwargs))
        for an, parameters in (arguments.pop('_extra', {})).items():
            arguments[an] = self.extraparser.parse(an, arguments[an], parameters)

        # Retrieve action information
        namespace, category, action = arguments.pop('_tid')
        func_name = '%s_%s' % (category, action.replace('-', '_'))

        # Lock the moulinette for the namespace
        with MoulinetteLock(namespace, timeout):
            try:
                mod = __import__('%s.%s' % (namespace, category),
                                 globals=globals(), level=0,
                                 fromlist=[func_name])
                func = getattr(mod, func_name)
            except (AttributeError, ImportError):
                raise ImportError("Unable to load function %s.%s/%s"
                        % (namespace, category, func_name))
            else:
                # Load translation and process the action
                m18n.load_namespace(namespace)
                return func(**arguments)

    @staticmethod
    def get_namespaces():
        """
        Retrieve available actions map namespaces

        Returns:
            A list of available namespaces

        """
        namespaces = []

        for f in os.listdir('%s/actionsmap' % pkg.datadir):
            if f.endswith('.yml'):
                namespaces.append(f[:-4])
        return namespaces

    @classmethod
    def generate_cache(klass, namespaces=None):
        """
        Generate cache for the actions map's file(s)

        Keyword arguments:
            - namespaces -- A list of namespaces to generate cache for

        Returns:
            A dict of actions map for each namespaces

        """
        actionsmaps = {}
        if not namespaces:
            namespaces = klass.get_namespaces()

        # Iterate over actions map namespaces
        for n in namespaces:
            logging.debug("generating cache for '%s' actions map namespace" % n)

            # Read actions map from yaml file
            am_file = '%s/actionsmap/%s.yml' % (pkg.datadir, n)
            with open(am_file, 'r') as f:
                actionsmaps[n] = yaml.load(f)

            # Cache actions map into pickle file
            with pkg.open_cachefile('%s.pkl' % n, 'w', subdir='actionsmap') as f:
                pickle.dump(actionsmaps[n], f)

        return actionsmaps


    ## Private methods

    def _construct_parser(self, actionsmaps):
        """
        Construct the parser with the actions map

        Keyword arguments:
            - actionsmaps -- A dict of multi-level dictionnary of
                categories/actions/arguments list for each namespaces

        Returns:
            An interface relevant's parser object

        """
        ## Get extra parameters
        if not self.use_cache:
            _get_extra = lambda an, e: self.extraparser.validate(an, e)
        else:
            _get_extra = lambda an, e: e

        ## Add arguments to the parser
        def _add_arguments(parser, arguments):
            extras = {}
            for argn, argp in arguments.items():
                names = top_parser.format_arg_names(argn,
                                                    argp.pop('full', None))
                try: argp['type'] = eval(argp['type'])
                except: pass

                try:
                    extra = argp.pop('extra')
                    arg_dest = (parser.add_argument(*names, **argp)).dest
                    extras[arg_dest] = _get_extra(arg_dest, extra)
                except KeyError:
                    # No extra parameters
                    parser.add_argument(*names, **argp)
            if extras:
                parser.set_defaults(_extra=extras)

        # Instantiate parser
        top_parser = self._parser_class()

        # Iterate over actions map namespaces
        for n, actionsmap in actionsmaps.items():
            # Retrieve global parameters
            _global = actionsmap.pop('_global', {})

            # -- Parse global configuration
            if 'configuration' in _global:
                # Set global configuration
                top_parser.set_global_conf(_global['configuration'])

            # -- Parse global arguments
            if 'arguments' in _global:
                try:
                    # Get global arguments parser
                    parser = top_parser.add_global_parser()
                except AttributeError:
                    # No parser for global arguments
                    pass
                else:
                    # Add arguments
                    _add_arguments(parser, _global['arguments'])

            # -- Parse categories
            for cn, cp in actionsmap.items():
                try:
                    actions = cp.pop('actions')
                except KeyError:
                    # Invalid category without actions
                    logging.warning("no actions found in category '%s'" % cn)
                    continue

                # Get category parser
                cat_parser = top_parser.add_category_parser(cn, **cp)

                # -- Parse actions
                for an, ap in actions.items():
                    args = ap.pop('arguments', {})
                    tid = (n, cn, an)
                    try:
                        conf = ap.pop('configuration')
                        _set_conf = lambda p: p.set_conf(tid, conf)
                    except KeyError:
                        # No action configuration
                        _set_conf = lambda p: False

                    try:
                        # Get action parser
                        parser = cat_parser.add_action_parser(an, tid, **ap)
                    except AttributeError:
                        # No parser for the action
                        continue
                    except ValueError as e:
                        logging.warning("cannot add action (%s, %s, %s): %s" % (n, cn, an, e))
                        continue
                    else:
                        # Store action identifier and add arguments
                        parser.set_defaults(_tid=tid)
                        _add_arguments(parser, args)
                        _set_conf(cat_parser)

        return top_parser
