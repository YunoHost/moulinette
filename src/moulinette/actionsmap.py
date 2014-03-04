# -*- coding: utf-8 -*-

import pickle
import yaml
import re
import os
from collections import OrderedDict

import logging

from . import __version__, curr_namespace, MoulinetteError
from .extra.parameters import extraparameters_list

## Extra parameters Parser

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
        self.use_cache = use_cache

        try:
            # Retrieve the interface parser
            mod = __import__('interface.%s' % interface,
                             globals=globals(), level=1,
                             fromlist=['actionsmap_parser'])
            parser = getattr(mod, 'actionsmap_parser')
        except (AttributeError, ImportError):
            raise MoulinetteError(22, _("Invalid interface '%s'" % interface))
        else:
            self._parser_class = parser

        logging.debug("initializing ActionsMap for the '%s' interface" % interface)

        actionsmaps = {}
        namespaces = self.get_actionsmap_namespaces()
        if curr_namespace and curr_namespace in namespaces:
            namespaces = [curr_namespace]

        # Iterate over actions map namespaces
        for n in namespaces:
            logging.debug("loading '%s' actions map namespace" % n)

            if use_cache:
                # Attempt to load cache if it exists
                cache_file = '%s/%s.pkl' % (pkg.cachedir('actionsmap'), n)
                if os.path.isfile(cache_file):
                    with open(cache_file, 'r') as f:
                        actionsmaps[n] = pickle.load(f)
                else:
                    self.use_cache = False
                    actionsmaps = self.generate_cache(namespaces)
                    break
            else:
                am_file = '%s/%s.yml' % (pkg.datadir('actionsmap'), n)
                with open(am_file, 'r') as f:
                    actionsmaps[n] = yaml.load(f)

        # Generate parsers
        self.extraparser = ExtraParser(interface)
        self.parser = self._construct_parser(actionsmaps)

    def process(self, args, **kwargs):
        """
        Parse arguments and process the proper action

        Keyword arguments:
            - args -- The arguments to parse
            - **kwargs -- Additional interface arguments

        """
        # Parse arguments
        arguments = vars(self.parser.parse_args(args, **kwargs))
        arguments = self._parse_extra_parameters(arguments)

        # Retrieve action information
        namespace, category, action = arguments.pop('_info')
        func_name = '%s_%s' % (category, action)

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
    def get_actionsmap_namespaces():
        """
        Retrieve actions map namespaces from a given path

        Returns:
            A list of available namespaces

        """
        namespaces = []

        for f in os.listdir(pkg.datadir('actionsmap')):
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
            namespaces = klass.get_actionsmap_namespaces()

        # Iterate over actions map namespaces
        for n in namespaces:
            logging.debug("generating cache for '%s' actions map namespace" % n)

            # Read actions map from yaml file
            am_file = pkg.datafile('actionsmap/%s.yml' % n)
            with open(am_file, 'r') as f:
                actionsmaps[n] = yaml.load(f)

            # Cache actions map into pickle file
            cache_file = pkg.cachefile('actionsmap/%s.pkl' % n, make_dir=True)
            with open(cache_file, 'w') as f:
                pickle.dump(actionsmaps[n], f)

        return actionsmaps


    ## Private class and methods

    def _store_extra_parameters(self, parser, arg_name, arg_extra):
        """
        Store extra parameters for a given argument

        Keyword arguments:
            - parser -- Parser object for the arguments
            - arg_name -- Argument name
            - arg_extra -- Argument extra parameters

        Returns:
            The parser object

        """
        if arg_extra:
            # Retrieve current extra parameters dict
            extra = parser.get_default('_extra')
            if not extra or not isinstance(extra, dict):
                extra = {}

            if not self.use_cache:
                # Validate extra parameters for the argument
                extra[arg_name] = self.extraparser.validate(arg_name, arg_extra)
            else:
                extra[arg_name] = arg_extra
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
        # Retrieve extra parameters for the arguments
        extra = args.pop('_extra', None)
        if not extra:
            return args

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
        # Instantiate parser
        top_parser = self._parser_class()

        # Iterate over actions map namespaces
        for n, actionsmap in actionsmaps.items():
            if 'general_arguments' in actionsmap:
                # Parse general arguments
                if top_parser.parse_general:
                    parser = top_parser.add_general_parser()
                    for an, ap in actionsmap['general_arguments'].items():
                        if 'version' in ap:
                            ap['version'] = ap['version'].replace('%version%',
                                                                  __version__)
                        argname = top_parser.format_arg_name(an, ap.pop('full', None))
                        parser.add_argument(*argname, **ap)
                del actionsmap['general_arguments']

            # Parse categories
            for cn, cp in actionsmap.items():
                if 'actions' not in cp:
                    continue
                actions = cp.pop('actions')

                # Add category parser
                if top_parser.parse_category:
                    cat_parser = top_parser.add_category_parser(cn, **cp)
                else:
                    cat_parser = top_parser

                # Parse actions
                if not top_parser.parse_action:
                    continue
                for an, ap in actions.items():
                    arguments = ap.pop('arguments', {})

                    # Add action parser
                    parser = cat_parser.add_action_parser(an, **ap)
                    if not parser:
                        continue

                    # Store action information
                    parser.set_defaults(_info=(n, cn, an))

                    # Add action arguments
                    for argn, argp in arguments.items():
                        name = top_parser.format_arg_name(argn, argp.pop('full', None))
                        extra = argp.pop('extra', None)

                        arg = parser.add_argument(*name, **argp)
                        parser = self._store_extra_parameters(parser, arg.dest, extra)

        return top_parser
