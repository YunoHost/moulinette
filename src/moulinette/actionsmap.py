# -*- coding: utf-8 -*-

import argparse
import yaml
import re
import os
import cPickle as pickle
from collections import OrderedDict

import logging

from . import __version__
from .core import MoulinetteError, MoulinetteLock, init_authenticator

## Actions map Signals -------------------------------------------------

class _AMapSignals(object):
    """Actions map's Signals interface

    Allow to easily connect signals of the actions map to handlers. They
    can be given as arguments in the form of { signal: handler }.

    """
    def __init__(self, **kwargs):
        # Initialize handlers
        for s in self.signals:
            self.clear_handler(s)

        # Iterate over signals to connect
        for s, h in kwargs.items():
            self.set_handler(s, h)

    def set_handler(self, signal, handler):
        """Set the handler for a signal"""
        if signal not in self.signals:
            raise ValueError("unknown signal '%s'" % signal)
        setattr(self, '_%s' % signal, handler)

    def clear_handler(self, signal):
        """Clear the handler of a signal"""
        if signal not in self.signals:
            raise ValueError("unknown signal '%s'" % signal)
        setattr(self, '_%s' % signal, self._notimplemented)


    ## Signals definitions

    """The list of available signals"""
    signals = { 'authenticate', 'prompt' }

    def authenticate(self, authenticator, name, help):
        """Process the authentication

        Attempt to authenticate to the given authenticator and return
        it.
        It is called when authentication is needed (e.g. to process an
        action).

        Keyword arguments:
            - authenticator -- The authenticator to use
            - name -- The authenticator name in the actions map
            - help -- A help message for the authenticator

        Returns:
            The authenticator object

        """
        if authenticator.is_authenticated:
            return authenticator
        return self._authenticate(authenticator, name, help)

    def prompt(self, message, is_password=False, confirm=False):
        """Prompt for a value

        Prompt the interface for a parameter value which is a password
        if 'is_password' and must be confirmed if 'confirm'.
        Is is called when a parameter value is needed and when the
        current interface should allow user interaction (e.g. to parse
        extra parameter 'ask' in the cli).

        Keyword arguments:
            - message -- The message to display
            - is_password -- True if the parameter is a password
            - confirm -- True if the value must be confirmed

        Returns:
            The collected value

        """
        return self._prompt(message, is_password, confirm)

    @staticmethod
    def _notimplemented(**kwargs):
        raise NotImplementedError("this signal is not handled")

shandler = _AMapSignals()


## Interfaces' Actions map Parser --------------------------------------

class _AMapParser(object):
    """Actions map's base Parser

    Each interfaces must implement a parser class derived from this
    class. It is used to parse the main parts of the actions map (i.e.
    global arguments, categories and actions).

    """
    def __init__(self, parent=None):
        if parent:
            self._o = parent
        else:
            self._o = self
            self._global_conf = {}
            self._conf = {}


    ## Virtual properties
    # Each parser classes must implement these properties.

    """The name of the interface for which it is the parser"""
    name = None


    ## Virtual methods
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
        raise NotImplementedError("derived class '%s' must override this method" % \
                                    self.__class__.__name__)

    def add_global_parser(self, **kwargs):
        """Add a parser for global arguments

        Create and return an argument parser for global arguments.

        Returns:
            An ArgumentParser based object

        """
        raise NotImplementedError("derived class '%s' must override this method" % \
                                    self.__class__.__name__)

    def add_category_parser(self, name, **kwargs):
        """Add a parser for a category

        Create a new category and return a parser for it.

        Keyword arguments:
            - name -- The category name

        Returns:
            A BaseParser based object

        """
        raise NotImplementedError("derived class '%s' must override this method" % \
                                    self.__class__.__name__)

    def add_action_parser(self, name, tid, conf=None, **kwargs):
        """Add a parser for an action

        Create a new action and return an argument parser for it. It
        should set the configuration 'conf' for the action which can be
        identified by the tuple identifier 'tid' - it is usually in the
        form of (namespace, category, action).

        Keyword arguments:
            - name -- The action name
            - tid -- The tuple identifier of the action
            - conf -- A dict of configuration for the action

        Returns:
            An ArgumentParser based object

        """
        raise NotImplementedError("derived class '%s' must override this method" % \
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
        raise NotImplementedError("derived class '%s' must override this method" % \
                                    self.__class__.__name__)


    ## Configuration access

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
        try:
            if name == 'authenticator':
                value = self.global_conf[name][profile]
            else:
                value = self.global_conf[name]
        except KeyError:
            return None
        else:
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
        conf = {}

        # -- 'authenficate'
        try:
            ifaces = configuration['authenticate']
        except KeyError:
            pass
        else:
            if ifaces == 'all':
                conf['authenticate'] = ifaces
            elif ifaces == False:
                conf['authenticate'] = False
            elif isinstance(ifaces, list):
                # Store only if authentication is needed
                conf['authenticate'] = True if self.name in ifaces else False
            else:
                # TODO: Log error instead and tell valid values
                raise MoulinetteError(22, "Invalid value '%r' for configuration 'authenticate'" % ifaces)

        # -- 'authenticator'
        try:
            auth = configuration['authenticator']
        except KeyError:
            pass
        else:
            if not is_global and isinstance(auth, str):
                try:
                    # Store parameters of the required authenticator
                    conf['authenticator'] = self.global_conf['authenticator'][auth]
                except KeyError:
                    raise MoulinetteError(22, "Authenticator '%s' is not defined in global configuration" % auth)
            elif is_global and isinstance(auth, dict):
                if len(auth) == 0:
                    logging.warning('no authenticator defined in global configuration')
                else:
                    auths = {}
                    for auth_name, auth_conf in auth.items():
                        # Add authenticator name
                        auths[auth_name] = ({ 'name': auth_name,
                                              'vendor': auth_conf.get('vendor'),
                                              'help': auth_conf.get('help', None)
                                            },
                                            auth_conf.get('parameters', {}))
                    conf['authenticator'] = auths
            else:
                # TODO: Log error instead and tell valid values
                raise MoulinetteError(22, "Invalid value '%r' for configuration 'authenticator'" % auth)

        # -- 'argument_auth'
        try:
            arg_auth = configuration['argument_auth']
        except KeyError:
            pass
        else:
            if isinstance(arg_auth, bool):
                conf['argument_auth'] = arg_auth
            else:
                # TODO: Log error instead and tell valid values
                raise MoulinetteError(22, "Invalid value '%r' for configuration 'argument_auth'" % arg_auth)

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
            auth_conf, auth_params = value
            auth_vendor = auth_conf.pop('vendor')

            # Return authenticator configuration and an instanciator for
            # it as a 2-tuple
            return (auth_conf,
                    lambda: init_authenticator(auth_conf['name'],
                                               auth_vendor, **auth_params))

        return value

# CLI Actions map Parser

class CLIAMapParser(_AMapParser):
    """Actions map's CLI Parser

    """
    def __init__(self, parent=None, parser=None):
        super(CLIAMapParser, self).__init__(parent)

        self._parser = parser or argparse.ArgumentParser()
        self._subparsers = self._parser.add_subparsers()


    ## Implement virtual properties

    name = 'cli'


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
            A new CLIParser object for the category

        """
        parser = self._subparsers.add_parser(name, help=category_help)
        return self.__class__(self, parser)

    def add_action_parser(self, name, tid, conf=None, action_help=None, **kwargs):
        """Add a parser for an action

        Keyword arguments:
            - action_help -- A brief description for the action

        Returns:
            A new argparse.ArgumentParser object for the action

        """
        if conf:
            self.set_conf(tid, conf)
        return self._subparsers.add_parser(name, help=action_help)

    def parse_args(self, args, **kwargs):
        ret = self._parser.parse_args(args)

        # Perform authentication if needed
        if self.get_conf(ret._tid, 'authenticate'):
            auth_conf, klass = self.get_conf(ret._tid, 'authenticator')

            # TODO: Catch errors
            auth = shandler.authenticate(klass(), **auth_conf)
            if not auth.is_authenticated:
                # TODO: Set proper error code
                raise MoulinetteError(1, _("This action need authentication"))
            if self.get_conf(ret._tid, 'argument_auth') and \
               self.get_conf(ret._tid, 'authenticate') == 'all':
                ret.auth = auth

        return ret

# API Actions map Parser

class _HTTPArgumentParser(object):
    """Argument parser for HTTP requests

    Object for parsing HTTP requests into Python objects. It is based
    on argparse.ArgumentParser class and implements some of its methods.

    """
    def __init__(self):
        # Initialize the ArgumentParser object
        self._parser = argparse.ArgumentParser(usage='',
                                               prefix_chars='@',
                                               add_help=False)
        self._parser.error = self._error

        self._positional = []   # list(arg_name)
        self._optional = {}     # dict({arg_name: option_strings})

    def set_defaults(self, **kwargs):
        return self._parser.set_defaults(**kwargs)

    def get_default(self, dest):
        return self._parser.get_default(dest)

    def add_argument(self, *args, **kwargs):
        action = self._parser.add_argument(*args, **kwargs)

        # Append newly created action
        if len(action.option_strings) == 0:
            self._positional.append(action.dest)
        else:
            self._optional[action.dest] = action.option_strings

        return action

    def parse_args(self, args):
        arg_strings = []

        ## Append an argument to the current one
        def append(arg_strings, value, option_string=None):
            # TODO: Process list arguments
            if isinstance(value, bool):
                # Append the option string only
                if option_string is not None:
                    arg_strings.append(option_string)
            elif isinstance(value, str):
                if option_string is not None:
                    arg_strings.append(option_string)
                    arg_strings.append(value)
                else:
                    arg_strings.append(value)

            return arg_strings

        # Iterate over positional arguments
        for dest in self._positional:
            if dest in args:
                arg_strings = append(arg_strings, args[dest])

        # Iterate over optional arguments
        for dest, opt in self._optional.items():
            if dest in args:
                arg_strings = append(arg_strings, args[dest], opt[0])
        return self._parser.parse_args(arg_strings)

    def _error(self, message):
        # TODO: Raise a proper exception
        raise MoulinetteError(1, message)

class APIAMapParser(_AMapParser):
    """Actions map's API Parser

    """

    def __init__(self):
        super(APIAMapParser, self).__init__()

        self._parsers = {} # dict({(method, path): _HTTPArgumentParser})

    @property
    def routes(self):
        """Get current routes"""
        return self._parsers.keys()


    ## Implement virtual properties

    name = 'api'

    
    ## Implement virtual methods

    @staticmethod
    def format_arg_names(name, full):
        if name[0] != '-':
            return [name]
        if full:
            return [full.replace('--', '@', 1)]
        if name.startswith('--'):
            return [name.replace('--', '@', 1)]
        return [name.replace('-', '@', 1)]

    def add_global_parser(self, **kwargs):
        raise AttributeError("global arguments are not managed")

    def add_category_parser(self, name, **kwargs):
        return self

    def add_action_parser(self, name, tid, conf=None, api=None, **kwargs):
        """Add a parser for an action

        Keyword arguments:
            - api -- The action route (e.g. 'GET /' )

        Returns:
            A new _HTTPArgumentParser object for the route

        """
        try:
            # Validate action route
            m = re.match('(GET|POST|PUT|DELETE) (/\S+)', api)
        except TypeError:
            raise AttributeError("the action '%s' doesn't provide api access" % name)
        if not m:
            # TODO: Log error
            raise ValueError("the action '%s' doesn't provide api access" % name)

        # Check if a parser already exists for the route
        key = (m.group(1), m.group(2))
        if key in self.routes:
            raise AttributeError("a parser for '%s' already exists" % key)

        # Create and append parser
        parser = _HTTPArgumentParser()
        self._parsers[key] = parser
        if conf:
            self.set_conf(key, conf)

        # Return the created parser
        return parser

    def parse_args(self, args, route, **kwargs):
        """Parse arguments

        Keyword arguments:
            - route -- The action route (e.g. 'GET /' )

        """
        # Retrieve the parser for the route
        if route not in self.routes:
            raise MoulinetteError(22, "No parser for '%s %s' found" % key)

        # TODO: Implement authentication

        return self._parsers[route].parse_args(args)

"""
The dict of interfaces names and their associated parser class.

"""
actionsmap_parsers = {
    'api': APIAMapParser,
    'cli': CLIAMapParser
}


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
    skipped_iface = {}


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
    skipped_iface = { 'api' }

    def __call__(self, message, arg_name, arg_value):
        # TODO: Fix asked arguments ordering
        if arg_value:
            return arg_value

        try:
            # Ask for the argument value
            return shandler.prompt(message)
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
            return shandler.prompt(message, True, True)
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

        if not re.match(pattern, arg_value or ''):
            raise MoulinetteError(22, message)
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
extraparameters_list = {AskParameter, PasswordParameter, PatternParameter}

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

    The actions map defines the features and their usage of the main
    application. It is composed by categories which contain one or more
    action(s). Moreover, the action can have specific argument(s).

    This class allows to manipulate one or several actions maps
    associated to a namespace. If no namespace is given, it will load
    all available namespaces.

    Keyword arguments:
        - interface -- The type of interface which needs the actions map.
            Possible values are:
                - 'cli' for the command line interface
                - 'api' for an API usage (HTTP requests)
        - namespaces -- The list of namespaces to use
        - use_cache -- False if it should parse the actions map file
            instead of using the cached one.

    """
    def __init__(self, interface, namespaces=[], use_cache=True):
        self.use_cache = use_cache
        self.interface = interface

        try:
            # Retrieve the interface parser
            self._parser_class = actionsmap_parsers[interface]
        except KeyError:
            raise MoulinetteError(22, _("Invalid interface '%s'" % interface))

        logging.debug("initializing ActionsMap for the '%s' interface" % interface)

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
        self.extraparser = ExtraArgumentParser(interface)
        self._parser = self._construct_parser(actionsmaps)

    @property
    def parser(self):
        """Return the instance of the interface's actions map parser"""
        return self._parser

    def connect(self, signal, handler):
        """Connect a signal to a handler

        Connect a signal emitted by actions map while processing to a
        handler. Note that some signals need a return value.

        Keyword arguments:
            - signal -- The name of the signal
            - handler -- The method to handle the signal

        """
        global shandler
        shandler.set_handler(signal, handler)

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
                raise MoulinetteError(168, _('Function is not defined'))
            else:
                # Process the action
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
                extra = argp.pop('extra', None)

                arg = parser.add_argument(*names, **argp)
                if extra:
                    extras[arg.dest] = _get_extra(arg.dest, extra)
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
                    continue

                # Get category parser
                cat_parser = top_parser.add_category_parser(cn, **cp)

                # -- Parse actions
                for an, ap in actions.items():
                    conf = ap.pop('configuration', None)
                    args = ap.pop('arguments', {})
                    tid = (n, cn, an)

                    try:
                        # Get action parser
                        parser = cat_parser.add_action_parser(an, tid, conf, **ap)
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

        return top_parser
