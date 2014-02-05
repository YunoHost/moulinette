# -*- coding: utf-8 -*-

import argparse
import getpass
import marshal
import pickle
import yaml
import re
import os

from .. import __version__
from ..config import actionsmap_path, actionsmap_cache_path
from helpers import YunoHostError, colorize

class _HTTPArgumentParser(object):

    def __init__(self, method, uri):
        # Initialize the ArgumentParser object
        self._parser = argparse.ArgumentParser(usage='',
                                               prefix_chars='@',
                                               add_help=False)
        self._parser.error = self._error

        self.method = method
        self.uri = uri

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
        raise Exception(message)

class HTTPParser(object):
    """
    Object for parsing HTTP requests into Python objects.

    """

    def __init__(self):
        self._parsers = {}   # dict({(method, uri): _HTTPArgumentParser})

    @property
    def routes(self):
        """Get current routes"""
        return self._parsers.keys()

    def add_parser(self, method, uri):
        """
        Add a parser for a given route

        Keyword arguments:
            - method -- The route's HTTP method (GET, POST, PUT, DELETE)
            - uri -- The route's URI

        Returns:
            A new _HTTPArgumentParser object for the route

        """
        # Check if a parser already exists for the route
        key = (method, uri)
        if key in self.routes:
            raise ValueError("A parser for '%s' already exists" % key)

        # Create and append parser
        parser = _HTTPArgumentParser(method, uri)
        self._parsers[key] = parser

        # Return the created parser
        return parser

    def parse_args(self, method, uri, args={}):
        """
        Convert argument variables to objects and assign them as
        attributes of the namespace for a given route

        Keyword arguments:
            - method -- The route's HTTP method (GET, POST, PUT, DELETE)
            - uri -- The route's URI
            - args -- Argument variables for the route

        Returns:
            The populated namespace

        """
        # Retrieve the parser for the route
        key = (method, uri)
        if key not in self.routes:
            raise ValueError("No parser for '%s %s' found" % key)

        return self._parsers[key].parse_args(args)


class _ExtraParameters(object):

    CLI_PARAMETERS = ['ask', 'password', 'pattern']
    API_PARAMETERS = ['pattern']
    AVAILABLE_PARAMETERS = CLI_PARAMETERS

    def __init__(self, **kwargs):
        self._params = {}

        for k, v in kwargs.items():
            if k in self.AVAILABLE_PARAMETERS:
                self._params[k] = v

    def validate(self, p_name, p_value):
        ret = type(p_value)() if p_value is not None else None

        for p, v in self._params.items():
            func = getattr(self, 'process_' + p)

            if isinstance(ret, list):
                for p_v in p_value:
                    r = func(v, p_name, p_v)
                    if r is not None:
                        ret.append(r)
            else:
                r = func(v, p_name, p_value)
                if r is not None:
                    ret = r

        return ret


    ## Parameters validating's method
    # TODO: Add doc

    def process_ask(self, message, p_name, p_value):
        # TODO: Fix asked arguments ordering
        if not self._can_prompt(p_value):
            return p_value

        # Skip password asking
        if 'password' in self._params.keys():
            return None

        ret =  raw_input(colorize(message + ': ', 'cyan'))
        return ret

    def process_password(self, is_password, p_name, p_value):
        if not self._can_prompt(p_value):
            return p_value

        message = self._params['ask']
        pwd1 = getpass.getpass(colorize(message + ': ', 'cyan'))
        pwd2 = getpass.getpass(colorize('Retype ' + message + ': ', 'cyan'))
        if pwd1 != pwd2:
            raise YunoHostError(22, _("Passwords don't match"))
        return pwd1

    def process_pattern(self, pattern, p_name, p_value):
        # TODO: Add a pattern_help parameter
        # TODO: Fix missing pattern matching on asking
        if p_value is not None and not re.match(pattern, p_value):
            raise YunoHostError(22, _("'%s' argument not match pattern" % p_name))
        return p_value


    ## Private method

    def _can_prompt(self, p_value):
        if os.isatty(1) and (p_value is None or p_value == ''):
            return True
        return False


class ActionsMap(object):
    """
    Validate and process action defined into the actions map.

    The actions map defines features and their usage of the main
    application. It is composed by categories which contain one or more
    action(s). Moreover, the action can have specific argument(s).

    Keyword arguments:

        - interface -- Interface type that requires the actions map.
            Possible value is one of:
                - 'cli' for the command line interface
                - 'api' for an API usage (HTTP requests)

        - use_cache -- False if it should parse the actions map file
            instead of using the cached one.

    """
    IFACE_CLI = 'cli'
    IFACE_API = 'api'

    def __init__(self, interface, use_cache=True):
        if interface not in [self.IFACE_CLI,self.IFACE_API]:
            raise ValueError(_("Invalid interface '%s'" % interface))
        self.interface = interface

        # Iterate over actions map namespaces
        actionsmap = {}
        for n in self.get_actionsmap_namespaces():
            if use_cache:
                cache_file = '%s/%s.pkl' % (actionsmap_cache_path, n)
                if os.path.isfile(cache_file):
                    with open(cache_file, 'r') as f:
                        actionsmap[n] = pickle.load(f)
                else:
                    actionsmap = self.generate_cache()
            else:
                am_file = '%s/%s.yml' % (actionsmap_path, n)
                with open(am_file, 'r') as f:
                    actionsmap[n] = yaml.load(f)

        self.parser = self._construct_parser(actionsmap)

    def process(self, args, route=None):
        """
        Parse arguments and process the proper action

        Keyword arguments:
            - args -- The arguments to parse
            - route -- A tupple (method, uri) of the requested route (api only)

        """
        arguments = None

        # Parse arguments
        if self.interface ==self.IFACE_CLI:
            arguments = self.parser.parse_args(args)
        elif self.interface ==self.IFACE_API:
            if route is None:
                # TODO: Raise a proper exception
                raise Exception(_("Missing route argument"))
            method, uri = route
            arguments = self.parser.parse_args(method, uri, args)
        arguments = vars(arguments)

        # Parse extra parameters
        arguments = self._parse_extra_parameters(arguments)

        # Retrieve action information
        namespace = arguments['_info']['namespace']
        category = arguments['_info']['category']
        action = arguments['_info']['action']
        del arguments['_info']

        module = '%s.%s' % (namespace, category)
        function = '%s_%s' % (category, action)

        try:
            mod = __import__(module, globals=globals(), fromlist=[function], level=2)
            func = getattr(mod, function)
        except (AttributeError, ImportError):
            raise YunoHostError(168, _('Function is not defined'))
        else:
            # Process the action
            return func(**arguments)

    @staticmethod
    def get_actionsmap_namespaces(path=actionsmap_path):
        """
        Retrieve actions map namespaces in a given path

        """
        namespaces = []

        for f in os.listdir(path):
            if f.endswith('.yml'):
                namespaces.append(f[:-4])
        return namespaces

    @classmethod
    def generate_cache(cls):
        """
        Generate cache for the actions map's file(s)

        """
        actionsmap = {}

        if not os.path.isdir(actionsmap_cache_path):
            os.makedirs(actionsmap_cache_path)

        for n in cls.get_actionsmap_namespaces():
            am_file = '%s/%s.yml' % (actionsmap_path, n)
            with open(am_file, 'r') as f:
                actionsmap[n] = yaml.load(f)
            cache_file = '%s/%s.pkl' % (actionsmap_cache_path, n)
            with open(cache_file, 'w') as f:
                pickle.dump(actionsmap[n], f)

        return actionsmap


    ## Private class and methods

    def _store_extra_parameters(self, parser, arg_name, arg_params):
        """
        Store extra parameters for a given parser's argument name

        Keyword arguments:
            - parser -- Parser object of the argument
            - arg_name -- Argument name
            - arg_params -- Argument parameters

        """
        params = {}
        keys = []

        # Get available parameters for the current interface
        if self.interface ==self.IFACE_CLI:
            keys = _ExtraParameters.CLI_PARAMETERS
        elif self.interface ==self.IFACE_API:
            keys = _ExtraParameters.API_PARAMETERS

        for k in keys:
            if k in arg_params:
                params[k] = arg_params[k]

        if len(params) > 0:
            # Retrieve all extra parameters from the parser
            extra = parser.get_default('_extra')
            if not extra or not isinstance(extra, dict):
                extra = {}

            # Add completed extra parameters to the parser
            extra[arg_name] = _ExtraParameters(**params)
            parser.set_defaults(_extra=extra)

        return parser

    def _parse_extra_parameters(self, args):
        # Retrieve extra parameters from the arguments
        if '_extra' not in args:
            return args
        extra = args['_extra']
        del args['_extra']

        # Validate extra parameters for each arguments
        for n, e in extra.items():
            args[n] = e.validate(n, args[n])

        return args

    def _construct_parser(self, actionsmap):
        """
        Construct the parser with the actions map

        Keyword arguments:
            - actionsmap -- Multi-level dictionnary of
                categories/actions/arguments list

        Returns:
            Interface relevant's parser object

        """
        top_parser = None
        iface = self.interface

        # Create parser object
        if iface ==self.IFACE_CLI:
            # TODO: Add descritpion (from __description__)
            top_parser = argparse.ArgumentParser()
            top_subparsers = top_parser.add_subparsers()
        elif iface ==self.IFACE_API:
            top_parser = HTTPParser()

        ## Extract option strings from parameters
        def _option_strings(arg_name, arg_params):
            if iface ==self.IFACE_CLI:
                if arg_name[0] == '-' and 'full' in arg_params:
                    return [arg_name, arg_params['full']]
                return [arg_name]
            elif iface ==self.IFACE_API:
                if arg_name[0] != '-':
                    return [arg_name]
                if 'full' in arg_params:
                    return [arg_params['full'].replace('--', '@', 1)]
                if arg_name.startswith('--'):
                    return [arg_name.replace('--', '@', 1)]
                return [arg_name.replace('-', '@', 1)]

        ## Extract a key from parameters
        def _key(arg_params, key, default=str()):
            if key in arg_params:
                return arg_params[key]
            return default

        ## Remove extra parameters
        def _clean_params(arg_params):
            keys = list(_ExtraParameters.AVAILABLE_PARAMETERS)
            keys.append('full')

            for k in keys:
                if k in arg_params:
                    del arg_params[k]
            return arg_params

        # Iterate over actions map namespaces
        for n in self.get_actionsmap_namespaces():
            # Parse general arguments for the cli only
            if iface ==self.IFACE_CLI:
                for an, ap in actionsmap[n]['general_arguments'].items():
                    if 'version' in ap:
                        ap['version'] = ap['version'].replace('%version%', __version__)
                    top_parser.add_argument(*_option_strings(an, ap), **_clean_params(ap))
            del actionsmap[n]['general_arguments']

            # Parse categories
            for cn, cp in actionsmap[n].items():
                if 'actions' not in cp:
                    continue

                # Add category subparsers for the cli only
                if iface ==self.IFACE_CLI:
                    c_help = _key(cp, 'category_help')
                    subparsers = top_subparsers.add_parser(cn, help=c_help).add_subparsers()

                # Parse actions
                for an, ap in cp['actions'].items():
                    parser = None

                    # Add parser for the current action
                    if iface ==self.IFACE_CLI:
                        a_help = _key(ap, 'action_help')
                        parser = subparsers.add_parser(an, help=a_help)
                    elif iface ==self.IFACE_API and 'api' in ap:
                        # Extract method and uri
                        m = re.match('(GET|POST|PUT|DELETE) (/\S+)', ap['api'])
                        if m:
                            parser = top_parser.add_parser(m.group(1), m.group(2))
                    if not parser:
                        continue

                    # Store action information
                    parser.set_defaults(_info={'namespace': n,
                                               'category': cn,
                                               'action': an})

                    # Add arguments
                    if not 'arguments' in ap:
                        continue
                    for argn, argp in ap['arguments'].items():
                        arg = parser.add_argument(*_option_strings(argn, argp),
                                                  **_clean_params(argp.copy()))
                        parser = self._store_extra_parameters(parser, arg.dest, argp)

        return top_parser
