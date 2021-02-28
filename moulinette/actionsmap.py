# -*- coding: utf-8 -*-

import os
import re
import logging
import yaml
import glob
import pickle as pickle

from time import time
from collections import OrderedDict
from importlib import import_module

from moulinette import m18n, msignals
from moulinette.cache import open_cachefile
from moulinette.globals import init_moulinette_env
from moulinette.core import MoulinetteError, MoulinetteLock
from moulinette.interfaces import BaseActionsMapParser, GLOBAL_SECTION, TO_RETURN_PROP
from moulinette.utils.log import start_action_logging

logger = logging.getLogger("moulinette.actionsmap")


# Extra parameters ----------------------------------------------------

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

    # Required variables
    # Each extra parameters classes must overwrite these variables.

    """The extra parameter name"""
    name = None

    # Optional variables
    # Each extra parameters classes can overwrite these variables.

    """A list of interface for which the parameter doesn't apply"""
    skipped_iface = []

    # Virtual methods
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


class CommentParameter(_ExtraParameter):
    name = "comment"
    skipped_iface = ["api"]

    def __call__(self, message, arg_name, arg_value):
        if arg_value is None:
            return
        return msignals.display(m18n.n(message))

    @classmethod
    def validate(klass, value, arg_name):
        # Deprecated boolean or empty string
        if isinstance(value, bool) or (isinstance(value, str) and not value):
            logger.warning(
                "expecting a non-empty string for extra parameter '%s' of "
                "argument '%s'",
                klass.name,
                arg_name,
            )
            value = arg_name
        elif not isinstance(value, str):
            raise TypeError("parameter value must be a string, got %r" % value)
        return value


class AskParameter(_ExtraParameter):

    """
    Ask for the argument value if possible and needed.

    The value of this parameter corresponds to the message to display
    when asking the argument value.

    """

    name = "ask"
    skipped_iface = ["api"]

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
            logger.warning(
                "expecting a non-empty string for extra parameter '%s' of "
                "argument '%s'",
                klass.name,
                arg_name,
            )
            value = arg_name
        elif not isinstance(value, str):
            raise TypeError("parameter value must be a string, got %r" % value)
        return value


class PasswordParameter(AskParameter):

    """
    Ask for the password argument value if possible and needed.

    The value of this parameter corresponds to the message to display
    when asking the password.

    """

    name = "password"

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

    name = "pattern"

    def __call__(self, arguments, arg_name, arg_value):
        pattern, message = (arguments[0], arguments[1])

        # Use temporarly utf-8 encoded value
        try:
            v = str(arg_value, "utf-8")
        except Exception:
            v = arg_value

        if v and not re.match(pattern, v or "", re.UNICODE):
            logger.warning(
                "argument value '%s' for '%s' doesn't match pattern '%s'",
                v,
                arg_name,
                pattern,
            )

            # Attempt to retrieve message translation
            msg = m18n.n(message)
            if msg == message:
                msg = m18n.g(message)

            raise MoulinetteError("invalid_argument", argument=arg_name, error=msg)
        return arg_value

    @staticmethod
    def validate(value, arg_name):
        # Deprecated string type
        if isinstance(value, str):
            logger.warning(
                "expecting a list as extra parameter 'pattern' of " "argument '%s'",
                arg_name,
            )
            value = [value, "pattern_not_match"]
        elif not isinstance(value, list) or len(value) != 2:
            raise TypeError("parameter value must be a list, got %r" % value)
        return value


class RequiredParameter(_ExtraParameter):

    """
    Check if a required argument is defined or not.

    The value of this parameter must be a boolean which is set to False by
    default.
    """

    name = "required"

    def __call__(self, required, arg_name, arg_value):
        if required and (arg_value is None or arg_value == ""):
            logger.warning("argument '%s' is required", arg_name)
            raise MoulinetteError("argument_required", argument=arg_name)
        return arg_value

    @staticmethod
    def validate(value, arg_name):
        if not isinstance(value, bool):
            raise TypeError("parameter value must be a boolean, got %r" % value)
        return value


"""
The list of available extra parameters classes. It will keep to this list
order on argument parsing.

"""
extraparameters_list = [
    CommentParameter,
    AskParameter,
    PasswordParameter,
    RequiredParameter,
    PatternParameter,
]

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

    def validate(self, arg_name, parameters):
        """
        Validate values of extra parameters for an argument

        Keyword arguments:
            - arg_name -- The argument name
            - parameters -- A dict of extra parameters with their values

        """
        # Iterate over parameters to validate
        for p in list(parameters):
            klass = self.extra.get(p, None)
            if not klass:
                # Remove unknown parameters
                del parameters[p]
            else:
                try:
                    # Validate parameter value
                    parameters[p] = klass.validate(parameters[p], arg_name)
                except Exception as e:
                    error_message = (
                        "unable to validate extra parameter '%s' for argument '%s': %s"
                        % (p, arg_name, e)
                    )
                    logger.error(error_message)
                    raise MoulinetteError(error_message, raw_msg=True)

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


# Main class ----------------------------------------------------------


def ordered_yaml_load(stream):
    class OrderedLoader(yaml.Loader):
        pass

    OrderedLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        lambda loader, node: OrderedDict(loader.construct_pairs(node)),
    )
    return yaml.load(stream, OrderedLoader)


class ActionsMap(object):

    """Validate and process actions defined into an actions map

    The actions map defines the features - and their usage - of an
    application which will be available through the moulinette.
    It is composed by categories which contain one or more action(s).
    Moreover, the action can have specific argument(s).

    This class allows to manipulate one or several actions maps
    associated to a namespace.

    Keyword arguments:
        - top_parser -- A BaseActionsMapParser-derived instance to use for
                        parsing the actions map
        - load_only_category -- A name of a category that should only be the
                        one loaded because it's been already determined
                        that's the only one relevant ... used for optimization
                        purposes...
    """

    def __init__(self, top_parser, load_only_category=None):

        assert isinstance(top_parser, BaseActionsMapParser), (
            "Invalid parser class '%s'" % top_parser.__class__.__name__
        )

        moulinette_env = init_moulinette_env()
        DATA_DIR = moulinette_env["DATA_DIR"]
        CACHE_DIR = moulinette_env["CACHE_DIR"]

        actionsmaps = OrderedDict()

        self.from_cache = False
        # Iterate over actions map namespaces
        for n in self.get_namespaces():
            logger.debug("loading actions map namespace '%s'", n)

            actionsmap_yml = "%s/actionsmap/%s.yml" % (DATA_DIR, n)
            actionsmap_yml_stat = os.stat(actionsmap_yml)
            actionsmap_pkl = "%s/actionsmap/%s-%d-%d.pkl" % (
                CACHE_DIR,
                n,
                actionsmap_yml_stat.st_size,
                actionsmap_yml_stat.st_mtime,
            )

            if os.path.exists(actionsmap_pkl):
                try:
                    # Attempt to load cache
                    with open(actionsmap_pkl, "rb") as f:
                        actionsmaps[n] = pickle.load(f)

                    self.from_cache = True
                # TODO: Switch to python3 and catch proper exception
                except (IOError, EOFError):
                    actionsmaps[n] = self.generate_cache(n)
            else:  # cache file doesn't exists
                actionsmaps[n] = self.generate_cache(n)

            # If load_only_category is set, and *if* the target category
            # is in the actionsmap, we'll load only that one.
            # If we filter it even if it doesn't exist, we'll end up with a
            # weird help message when we do a typo in the category name..
            if load_only_category and load_only_category in actionsmaps[n]:
                actionsmaps[n] = {
                    k: v
                    for k, v in actionsmaps[n].items()
                    if k in [load_only_category, "_global"]
                }

            # Load translations
            m18n.load_namespace(n)

        # Generate parsers
        self.extraparser = ExtraArgumentParser(top_parser.interface)
        self.parser = self._construct_parser(actionsmaps, top_parser)

    def get_authenticator_for_profile(self, auth_profile):

        # Fetch the configuration for the authenticator module as defined in the actionmap
        try:
            auth_conf = self.parser.global_conf["authenticator"][auth_profile]
        except KeyError:
            raise ValueError("Unknown authenticator profile '%s'" % auth_profile)

        # Load and initialize the authenticator module
        try:
            mod = import_module("moulinette.authenticators.%s" % auth_conf["vendor"])
        except ImportError:
            error_message = (
                "unable to load authenticator vendor module 'moulinette.authenticators.%s'"
                % auth_conf["vendor"]
            )
            logger.exception(error_message)
            raise MoulinetteError(error_message, raw_msg=True)
        else:
            return mod.Authenticator(**auth_conf)

    def check_authentication_if_required(self, args, **kwargs):

        auth_profile = self.parser.auth_required(args, **kwargs)

        if not auth_profile:
            return

        authenticator = self.get_authenticator_for_profile(auth_profile)
        auth = msignals.authenticate(authenticator)

        if not auth.is_authenticated:
            raise MoulinetteError("authentication_required_long")

    def process(self, args, timeout=None, **kwargs):
        """
        Parse arguments and process the proper action

        Keyword arguments:
            - args -- The arguments to parse
            - timeout -- The time period before failing if the lock
                cannot be acquired for the action
            - **kwargs -- Additional interface arguments

        """

        # Perform authentication if needed
        self.check_authentication_if_required(args, **kwargs)

        # Parse arguments
        arguments = vars(self.parser.parse_args(args, **kwargs))

        # Retrieve tid and parse arguments with extra parameters
        tid = arguments.pop("_tid")
        arguments = self.extraparser.parse_args(tid, arguments)

        # Return immediately if a value is defined
        if TO_RETURN_PROP in arguments:
            return arguments.get(TO_RETURN_PROP)

        # Retrieve action information
        if len(tid) == 4:
            namespace, category, subcategory, action = tid
            func_name = "%s_%s_%s" % (
                category,
                subcategory.replace("-", "_"),
                action.replace("-", "_"),
            )
            full_action_name = "%s.%s.%s.%s" % (
                namespace,
                category,
                subcategory,
                action,
            )
        else:
            assert len(tid) == 3
            namespace, category, action = tid
            subcategory = None
            func_name = "%s_%s" % (category, action.replace("-", "_"))
            full_action_name = "%s.%s.%s" % (namespace, category, action)

        # Lock the moulinette for the namespace
        with MoulinetteLock(namespace, timeout):
            start = time()
            try:
                mod = __import__(
                    "%s.%s" % (namespace, category),
                    globals=globals(),
                    level=0,
                    fromlist=[func_name],
                )
                logger.debug(
                    "loading python module %s took %.3fs",
                    "%s.%s" % (namespace, category),
                    time() - start,
                )
                func = getattr(mod, func_name)
            except (AttributeError, ImportError) as e:
                import traceback

                traceback.print_exc()
                error_message = "unable to load function %s.%s because: %s" % (
                    namespace,
                    func_name,
                    e,
                )
                logger.exception(error_message)
                raise MoulinetteError(error_message, raw_msg=True)
            else:
                log_id = start_action_logging()
                if logger.isEnabledFor(logging.DEBUG):
                    # Log arguments in debug mode only for safety reasons
                    logger.debug(
                        "processing action [%s]: %s with args=%s",
                        log_id,
                        full_action_name,
                        arguments,
                    )
                else:
                    logger.debug("processing action [%s]: %s", log_id, full_action_name)

                # Load translation and process the action
                m18n.load_namespace(namespace)
                start = time()
                try:
                    return func(**arguments)
                finally:
                    stop = time()
                    logger.debug("action [%s] executed in %.3fs", log_id, stop - start)

    @staticmethod
    def get_namespaces():
        """
        Retrieve available actions map namespaces

        Returns:
            A list of available namespaces

        """
        namespaces = []

        moulinette_env = init_moulinette_env()
        DATA_DIR = moulinette_env["DATA_DIR"]

        # This var is ['*'] by default but could be set for example to
        # ['yunohost', 'yml_*']
        NAMESPACE_PATTERNS = moulinette_env["NAMESPACES"]

        # Look for all files that match the given patterns in the actionsmap dir
        for namespace_pattern in NAMESPACE_PATTERNS:
            namespaces.extend(
                glob.glob("%s/actionsmap/%s.yml" % (DATA_DIR, namespace_pattern))
            )

        # Keep only the filenames with extension
        namespaces = [os.path.basename(n)[:-4] for n in namespaces]

        return namespaces

    @classmethod
    def generate_cache(klass, namespace):
        """
        Generate cache for the actions map's file(s)

        Keyword arguments:
            - namespace -- The namespace to generate cache for

        Returns:
            The action map for the namespace
        """
        moulinette_env = init_moulinette_env()
        CACHE_DIR = moulinette_env["CACHE_DIR"]
        DATA_DIR = moulinette_env["DATA_DIR"]

        # Iterate over actions map namespaces
        logger.debug("generating cache for actions map namespace '%s'", namespace)

        # Read actions map from yaml file
        am_file = "%s/actionsmap/%s.yml" % (DATA_DIR, namespace)
        with open(am_file, "r") as f:
            actionsmap = ordered_yaml_load(f)

        # at installation, cachedir might not exists
        for old_cache in glob.glob("%s/actionsmap/%s-*.pkl" % (CACHE_DIR, namespace)):
            os.remove(old_cache)

        # Cache actions map into pickle file
        am_file_stat = os.stat(am_file)

        pkl = "%s-%d-%d.pkl" % (namespace, am_file_stat.st_size, am_file_stat.st_mtime)

        with open_cachefile(pkl, "wb", subdir="actionsmap") as f:
            pickle.dump(actionsmap, f)

        return actionsmap

    # Private methods

    def _construct_parser(self, actionsmaps, top_parser):
        """
        Construct the parser with the actions map

        Keyword arguments:
            - actionsmaps -- A dict of multi-level dictionnary of
                categories/actions/arguments list for each namespaces
            - top_parser -- A BaseActionsMapParser-derived instance to use for
                parsing the actions map

        Returns:
            An interface relevant's parser object

        """

        logger.debug("building parser...")
        start = time()

        # If loading from cache, extra were already checked when cache was
        # loaded ? Not sure about this ... old code is a bit mysterious...
        validate_extra = not self.from_cache

        # namespace, actionsmap is a tuple where:
        #
        # * namespace define the top "name", for us it will always be
        #   "yunohost" and there well be only this one
        # * actionsmap is the actual actionsmap that we care about
        for namespace, actionsmap in actionsmaps.items():
            # Retrieve global parameters
            _global = actionsmap.pop("_global", {})

            # Set the global configuration to use for the parser.
            top_parser.set_global_conf(_global["configuration"])

            if top_parser.has_global_parser():
                top_parser.add_global_arguments(_global["arguments"])

            # category_name is stuff like "user", "domain", "hooks"...
            # category_values is the values of this category (like actions)
            for category_name, category_values in actionsmap.items():

                if "actions" in category_values:
                    actions = category_values.pop("actions")
                else:
                    actions = {}

                if "subcategories" in category_values:
                    subcategories = category_values.pop("subcategories")
                else:
                    subcategories = {}

                # Get category parser
                category_parser = top_parser.add_category_parser(
                    category_name, **category_values
                )

                # action_name is like "list" of "domain list"
                # action_options are the values
                for action_name, action_options in actions.items():
                    arguments = action_options.pop("arguments", {})
                    tid = (namespace, category_name, action_name)

                    # Get action parser
                    action_parser = category_parser.add_action_parser(
                        action_name, tid, **action_options
                    )

                    if action_parser is None:  # No parser for the action
                        continue

                    # Store action identifier and add arguments
                    action_parser.set_defaults(_tid=tid)
                    action_parser.add_arguments(
                        arguments,
                        extraparser=self.extraparser,
                        format_arg_names=top_parser.format_arg_names,
                        validate_extra=validate_extra,
                    )

                    if "configuration" in action_options:
                        category_parser.set_conf(tid, action_options["configuration"])

                # subcategory_name is like "cert" in "domain cert status"
                # subcategory_values is the values of this subcategory (like actions)
                for subcategory_name, subcategory_values in subcategories.items():

                    actions = subcategory_values.pop("actions")

                    # Get subcategory parser
                    subcategory_parser = category_parser.add_subcategory_parser(
                        subcategory_name, **subcategory_values
                    )

                    # action_name is like "status" of "domain cert status"
                    # action_options are the values
                    for action_name, action_options in actions.items():
                        arguments = action_options.pop("arguments", {})
                        tid = (namespace, category_name, subcategory_name, action_name)

                        try:
                            # Get action parser
                            action_parser = subcategory_parser.add_action_parser(
                                action_name, tid, **action_options
                            )
                        except AttributeError:
                            # No parser for the action
                            continue

                        # Store action identifier and add arguments
                        action_parser.set_defaults(_tid=tid)
                        action_parser.add_arguments(
                            arguments,
                            extraparser=self.extraparser,
                            format_arg_names=top_parser.format_arg_names,
                            validate_extra=validate_extra,
                        )

                        if "configuration" in action_options:
                            category_parser.set_conf(
                                tid, action_options["configuration"]
                            )

        logger.debug("building parser took %.3fs", time() - start)
        return top_parser
