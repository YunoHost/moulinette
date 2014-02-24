# -*- coding: utf-8 -*-

import argparse
import pickle
import yaml
import re
import os
from collections import OrderedDict

import logging

from .. import __version__
from ..config import actionsmap_path, actionsmap_cache_path

from extraparameters import extraparameters_list
from helpers import Interface, YunoHostError

## Additional parsers

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

class ExtraParser(object):
    """
    Global parser for the extra parameters.

    """
    def __init__(self, iface):
        self.iface = iface
        self.extra = OrderedDict()

        # Append available extra parameters for the current interface
        for klass in extraparameters_list:
            if iface in klass.skipped_iface:
                continue
            if klass.name in self.extra:
                logging.warning("extra parameter named '%s' was already added" % klass.name)
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
            # Remove unknow parameters
            if p not in self.extra.keys():
                del parameters[p]

            # Validate parameter value
            parameters[p] = self.extra[p].validate(v, arg_name)

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


## Main class

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
    def __init__(self, interface, use_cache=True):
        if interface not in Interface.all():
            raise ValueError(_("Invalid interface '%s'" % interface))
        self.interface = interface
        self.use_cache = use_cache

        logging.debug("initializing ActionsMap for the '%s' interface" % interface)

        # Iterate over actions map namespaces
        actionsmaps = {}
        for n in self.get_actionsmap_namespaces():
            logging.debug("loading '%s' actions map namespace" % n)

            if use_cache:
                # Attempt to load cache if it exists
                cache_file = '%s/%s.pkl' % (actionsmap_cache_path, n)
                if os.path.isfile(cache_file):
                    with open(cache_file, 'r') as f:
                        actionsmaps[n] = pickle.load(f)
                else:
                    self.use_cache = False
                    actionsmaps = self.generate_cache()
                    break
            else:
                am_file = '%s/%s.yml' % (actionsmap_path, n)
                with open(am_file, 'r') as f:
                    actionsmaps[n] = yaml.load(f)

        # Generate parsers
        self.extraparser = ExtraParser(interface)
        self.parser = self._construct_parser(actionsmaps)

    def process(self, args, route=None):
        """
        Parse arguments and process the proper action

        Keyword arguments:
            - args -- The arguments to parse
            - route -- A tupple (method, uri) of the requested route (api only)

        """
        arguments = None

        # Parse arguments
        if self.interface == Interface.cli:
            arguments = self.parser.parse_args(args)
        elif self.interface == Interface.api:
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
        Retrieve actions map namespaces from a given path

        Returns:
            A list of available namespaces

        """
        namespaces = []

        for f in os.listdir(path):
            if f.endswith('.yml'):
                namespaces.append(f[:-4])
        return namespaces

    @classmethod
    def generate_cache(klass):
        """
        Generate cache for the actions map's file(s)

        Returns:
            A dict of actions map for each namespaces

        """
        actionsmaps = {}

        if not os.path.isdir(actionsmap_cache_path):
            os.makedirs(actionsmap_cache_path)

        # Iterate over actions map namespaces
        for n in klass.get_actionsmap_namespaces():
            logging.debug("generating cache for '%s' actions map namespace" % n)

            # Read actions map from yaml file
            am_file = '%s/%s.yml' % (actionsmap_path, n)
            with open(am_file, 'r') as f:
                actionsmaps[n] = yaml.load(f)

            # Cache actions map into pickle file
            cache_file = '%s/%s.pkl' % (actionsmap_cache_path, n)
            with open(cache_file, 'w') as f:
                pickle.dump(actionsmaps[n], f)

        return actionsmaps


    ## Private class and methods

    def _store_extra_parameters(self, parser, arg_name, arg_params):
        """
        Store extra parameters for a given argument

        Keyword arguments:
            - parser -- Parser object for the arguments
            - arg_name -- Argument name
            - arg_params -- Argument parameters

        Returns:
            The parser object

        """
        if 'extra' in arg_params:
            # Retrieve current extra parameters dict
            extra = parser.get_default('_extra')
            if not extra or not isinstance(extra, dict):
                extra = {}

            if not self.use_cache:
                # Validate extra parameters for the argument
                extra[arg_name] = self.extraparser.validate(arg_name, arg_params['extra'])
            else:
                extra[arg_name] = arg_params['extra']
            parser.set_defaults(_extra=extra)

        return parser

    def _parse_extra_parameters(self, args):
        """
        Parse arguments with their extra parameters

        Keyword arguments:
            - args -- A dict of all arguments

        Return:
            The parsed arguments dict

        """
        # Retrieve extra parameters from the arguments
        if '_extra' not in args:
            return args
        extra = args['_extra']
        del args['_extra']

        # Validate extra parameters for each arguments
        for an, parameters in extra.items():
            args[an] = self.extraparser.parse(an, args[an], parameters)

        return args

    def _construct_parser(self, actionsmaps):
        """
        Construct the parser with the actions map

        Keyword arguments:
            - actionsmaps -- A dict of multi-level dictionnary of
                categories/actions/arguments list for each namespaces

        Returns:
            An interface relevant's parser object

        """
        top_parser = None
        iface = self.interface

        # Create parser object
        if iface == Interface.cli:
            # TODO: Add descritpion (from __description__?)
            top_parser = argparse.ArgumentParser()
            top_subparsers = top_parser.add_subparsers()
        elif iface == Interface.api:
            top_parser = HTTPParser()

        ## Format option strings from argument parameters
        def _option_strings(arg_name, arg_params):
            if iface == Interface.cli:
                if arg_name[0] == '-' and 'full' in arg_params:
                    return [arg_name, arg_params['full']]
                return [arg_name]
            elif iface == Interface.api:
                if arg_name[0] != '-':
                    return [arg_name]
                if 'full' in arg_params:
                    return [arg_params['full'].replace('--', '@', 1)]
                if arg_name.startswith('--'):
                    return [arg_name.replace('--', '@', 1)]
                return [arg_name.replace('-', '@', 1)]

        ## Remove extra parameters
        def _clean_params(arg_params):
            for k in {'full', 'extra'}:
                if k in arg_params:
                    del arg_params[k]
            return arg_params

        # Iterate over actions map namespaces
        for n, actionsmap in actionsmaps.items():
            # Parse general arguments for the cli only
            if iface == Interface.cli:
                for an, ap in actionsmap['general_arguments'].items():
                    if 'version' in ap:
                        ap['version'] = ap['version'].replace('%version%', __version__)
                    top_parser.add_argument(*_option_strings(an, ap), **_clean_params(ap))
            del actionsmap['general_arguments']

            # Parse categories
            for cn, cp in actionsmap.items():
                if 'actions' not in cp:
                    continue

                # Add category subparsers for the cli only
                if iface == Interface.cli:
                    c_help = cp.get('category_help')
                    subparsers = top_subparsers.add_parser(cn, help=c_help).add_subparsers()

                # Parse actions
                for an, ap in cp['actions'].items():
                    parser = None

                    # Add parser for the current action
                    if iface == Interface.cli:
                        a_help = ap.get('action_help')
                        parser = subparsers.add_parser(an, help=a_help)
                    elif iface == Interface.api and 'api' in ap:
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
