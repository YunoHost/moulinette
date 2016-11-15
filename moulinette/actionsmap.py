# -*- coding: utf-8 -*-

import os
import re
import errno
import logging
import yaml
import cPickle as pickle
from time import time
from collections import OrderedDict

from moulinette.core import (MoulinetteError, MoulinetteLock)
from moulinette.interfaces import (
    BaseActionsMapParser, GLOBAL_SECTION, TO_RETURN_PROP
)
from moulinette.utils.log import start_action_logging

logger = logging.getLogger('moulinette.actionsmap')


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
        if arg_value:
            return arg_value

        try:
            # Ask for the argument value
            return msignals.prompt(m18n.n(message))
        except NotImplementedError:
            return arg_value

    @classmethod
    def validate(klass, value, arg_name):
        # Deprecated boolean or empty string
        if isinstance(value, bool) or (isinstance(value, str) and not value):
            logger.warning("expecting a string for extra parameter '%s' of " \
                           "argument '%s'", klass.name, arg_name)
            value = arg_name
        elif not isinstance(value, str):
            raise TypeError("parameter value must be a string, got %r" \
                                % value)
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
            return msignals.prompt(m18n.n(message), True, True)
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

        # Use temporarly utf-8 encoded value
        try:
            v = unicode(arg_value, 'utf-8')
        except:
            v = arg_value

        if v and not re.match(pattern, v or '', re.UNICODE):
            logger.debug("argument value '%s' for '%s' doesn't match pattern '%s'",
                         v, arg_name, pattern)

            # Attempt to retrieve message translation
            msg = m18n.n(message)
            if msg == message:
                msg = m18n.g(message)

            raise MoulinetteError(errno.EINVAL,
                                  m18n.g('invalid_argument',
                                         argument=arg_name, error=msg))
        return arg_value

    @staticmethod
    def validate(value, arg_name):
        # Deprecated string type
        if isinstance(value, str):
            logger.warning("expecting a list for extra parameter 'pattern' of " \
                           "argument '%s'", arg_name)
            value = [value, 'pattern_not_match']
        elif not isinstance(value, list) or len(value) != 2:
            raise TypeError("parameter value must be a list, got %r" \
                                % value)
        return value

class RequiredParameter(_ExtraParameter):
    """
    Check if a required argument is defined or not.

    The value of this parameter must be a boolean which is set to False by
    default.
    """
    name = 'required'

    def __call__(self, required, arg_name, arg_value):
        if required and (arg_value is None or arg_value == ''):
            logger.debug("argument '%s' is required",
                         v, arg_name, pattern)
            raise MoulinetteError(errno.EINVAL,
                                  m18n.g('argument_required',
                                         argument=arg_name))
        return arg_value

    @staticmethod
    def validate(value, arg_name):
        if not isinstance(value, bool):
            raise TypeError("parameter value must be a list, got %r" \
                                % value)
        return value

"""
The list of available extra parameters classes. It will keep to this list
order on argument parsing.

"""
extraparameters_list = [ AskParameter, PasswordParameter, RequiredParameter,
                         PatternParameter ]

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
        self._extra_params = {GLOBAL_SECTION: {}}

        # Append available extra parameters for the current interface
        for klass in extraparameters_list:
            if iface in klass.skipped_iface:
                continue
            self.extra[klass.name] = klass
        logger.debug('extra parameter classes loaded: %s', self.extra.keys())

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
                try:
                    # Validate parameter value
                    parameters[p] = klass.validate(v, arg_name)
                except Exception as e:
                    logger.error("unable to validate extra parameter '%s' " \
                                 "for argument '%s': %s", p, arg_name, e)
                    raise MoulinetteError(errno.EINVAL, m18n.g('error_see_log'))

        return parameters

    def add_argument(self, tid, arg_name, parameters, validate=True):
        """
        Add extra parameters to apply on an action argument

        Keyword arguments:
            - tid -- The tuple identifier of the action or GLOBAL_SECTION
                for global extra parameters
            - arg_name -- The argument name
            - parameters -- A dict of extra parameters with their values
            - validate -- False to not validate extra parameters values

        """
        if validate:
            parameters = self.validate(arg_name, parameters)
        try:
            self._extra_params[tid][arg_name] = parameters
        except KeyError:
            self._extra_params[tid] = OrderedDict({arg_name: parameters})

    def parse_args(self, tid, args):
        """
        Parse arguments for an action with extra parameters

        Keyword arguments:
            - tid -- The tuple identifier of the action
            - args -- A dict of argument name associated to their value

        """
        extra_args = OrderedDict(self._extra_params.get(GLOBAL_SECTION, {}))
        extra_args.update(self._extra_params.get(tid, {}))

        # Iterate over action arguments with extra parameters
        for arg_name, extra_params in extra_args.items():
            # Iterate over available extra parameters
            for p, cls in self.extra.items():
                try:
                    extra_value = extra_params[p]
                except KeyError:
                    continue
                arg_value = args.get(arg_name, None)

                # Initialize the extra parser
                parser = cls(self.iface)

                # Parse the argument
                if isinstance(arg_value, list):
                    for v in arg_value:
                        r = parser(extra_value, arg_name, v)
                        if r not in arg_value:
                            arg_value.append(r)
                else:
                    arg_value = parser(extra_value, arg_name, arg_value)

                # Update argument value
                if arg_value is not None:
                    args[arg_name] = arg_value
        return args


## Main class ----------------------------------------------------------

def ordered_yaml_load(stream):
    class OrderedLoader(yaml.Loader):
        pass
    OrderedLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        lambda loader, node: OrderedDict(loader.construct_pairs(node)))
    return yaml.load(stream, OrderedLoader)


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
        - parser_class -- The BaseActionsMapParser derived class to use
            for parsing the actions map
        - namespaces -- The list of namespaces to use
        - use_cache -- False if it should parse the actions map file
            instead of using the cached one
        - parser_kwargs -- A dict of arguments to pass to the parser
            class at construction

    """
    def __init__(self, parser_class, namespaces=[], use_cache=True,
                 parser_kwargs={}):
        if not issubclass(parser_class, BaseActionsMapParser):
            raise ValueError("Invalid parser class '%s'" % parser_class.__name__)
        self.parser_class = parser_class
        self.use_cache = use_cache

        if len(namespaces) == 0:
            namespaces = self.get_namespaces()
        actionsmaps = OrderedDict()

        # Iterate over actions map namespaces
        for n in namespaces:
            logger.debug("loading actions map namespace '%s'", n)

            actionsmap_yml = '%s/actionsmap/%s.yml' % (pkg.datadir, n)
            actionsmap_yml_stat=os.stat(actionsmap_yml)
            actionsmap_pkl = '%s/actionsmap/%s-%d-%d.pkl' % (pkg.cachedir, n,
                                actionsmap_yml_stat.st_size,
                                actionsmap_yml_stat.st_mtime)

            if use_cache and os.path.exists(actionsmap_pkl):
                try:
                    # Attempt to load cache
                    with open(actionsmap_pkl) as f:
                        actionsmaps[n] = pickle.load(f)
                # TODO: Switch to python3 and catch proper exception
                except IOError:
                    self.use_cache = False
                    actionsmaps = self.generate_cache(namespaces)
            elif use_cache:  # cached file doesn't exists
                self.use_cache = False
                actionsmaps = self.generate_cache(namespaces)
            elif n not in actionsmaps:
                with open(actionsmap_yml) as f:
                    actionsmaps[n] = ordered_yaml_load(f)

            # Load translations
            m18n.load_namespace(n)

        # Generate parsers
        self.extraparser = ExtraArgumentParser(parser_class.interface)
        self._parser = self._construct_parser(actionsmaps, **parser_kwargs)

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

        # Retrieve tid and parse arguments with extra parameters
        tid = arguments.pop('_tid')
        arguments = self.extraparser.parse_args(tid, arguments)

        # Return immediately if a value is defined
        if TO_RETURN_PROP in arguments:
            return arguments.get(TO_RETURN_PROP)

        # Retrieve action information
        namespace, category, action = tid
        func_name = '%s_%s' % (category, action.replace('-', '_'))

        # Lock the moulinette for the namespace
        with MoulinetteLock(namespace, timeout):
            try:
                mod = __import__('%s.%s' % (namespace, category),
                                 globals=globals(), level=0,
                                 fromlist=[func_name])
                func = getattr(mod, func_name)
            except (AttributeError, ImportError):
                logger.exception("unable to load function %s.%s.%s",
                                 namespace, category, func_name)
                raise MoulinetteError(errno.EIO, m18n.g('error_see_log'))
            else:
                log_id = start_action_logging()
                if logger.isEnabledFor(logging.DEBUG):
                    # Log arguments in debug mode only for safety reasons
                    logger.info('processing action [%s]: %s.%s.%s with args=%s',
                                log_id, namespace, category, action, arguments)
                else:
                    logger.info('processing action [%s]: %s.%s.%s',
                                log_id, namespace, category, action)

                # Load translation and process the action
                m18n.load_namespace(namespace)
                start = time()
                try:
                    return func(**arguments)
                finally:
                    stop = time()
                    logger.debug('action [%s] ended after %.3fs',
                                 log_id, stop - start)

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
            logger.debug("generating cache for actions map namespace '%s'", n)

            # Read actions map from yaml file
            am_file = '%s/actionsmap/%s.yml' % (pkg.datadir, n)
            with open(am_file, 'r') as f:
                actionsmaps[n] = yaml.load(f)

            # clean old cached files
            for i in os.listdir('%s/actionsmap/' % pkg.cachedir):
                if i.endswith(".pkl"):
                    os.remove('%s/actionsmap/%s' % (pkg.cachedir, i))

            # Cache actions map into pickle file
            am_file_stat=os.stat(am_file)
            pkl='%s-%d-%d.pkl' % (n, am_file_stat.st_size, am_file_stat.st_mtime)
            with pkg.open_cachefile(pkl, 'w', subdir='actionsmap') as f:
                pickle.dump(actionsmaps[n], f)

        return actionsmaps


    ## Private methods

    def _construct_parser(self, actionsmaps, **kwargs):
        """
        Construct the parser with the actions map

        Keyword arguments:
            - actionsmaps -- A dict of multi-level dictionnary of
                categories/actions/arguments list for each namespaces
            - **kwargs -- Additionnal arguments to pass at the parser
                class instantiation

        Returns:
            An interface relevant's parser object

        """
        ## Get extra parameters
        if not self.use_cache:
            validate_extra = True
        else:
            validate_extra = False

        ## Add arguments to the parser
        def _add_arguments(tid, parser, arguments):
            for argn, argp in arguments.items():
                names = top_parser.format_arg_names(str(argn),
                                                    argp.pop('full', None))
                try: argp['type'] = eval(argp['type'])
                except: pass

                try:
                    extra = argp.pop('extra')
                    arg_dest = (parser.add_argument(*names, **argp)).dest
                    self.extraparser.add_argument(tid, arg_dest, extra,
                                                  validate_extra)
                except KeyError:
                    # No extra parameters
                    parser.add_argument(*names, **argp)

        # Instantiate parser
        top_parser = self.parser_class(**kwargs)

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
                    _add_arguments(GLOBAL_SECTION, parser,
                                   _global['arguments'])

            # -- Parse categories
            for cn, cp in actionsmap.items():
                try:
                    actions = cp.pop('actions')
                except KeyError:
                    # Invalid category without actions
                    logger.warning("no actions found in category '%s' in " \
                                   "namespace '%s'", cn, n)
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
                        a_parser = cat_parser.add_action_parser(an, tid, **ap)
                    except AttributeError:
                        # No parser for the action
                        continue
                    except ValueError as e:
                        logger.warning("cannot add action (%s, %s, %s): %s",
                                       n, cn, an, e)
                        continue
                    else:
                        # Store action identifier and add arguments
                        a_parser.set_defaults(_tid=tid)
                        _add_arguments(tid, a_parser, args)
                        _set_conf(cat_parser)

        return top_parser
