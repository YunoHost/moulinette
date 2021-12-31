# -*- coding: utf-8 -*-

import os
import re
import logging
import glob
import pickle as pickle

from typing import List, Optional
from time import time
from collections import OrderedDict
from importlib import import_module

from moulinette import m18n, Moulinette
from moulinette.core import (
    MoulinetteError,
    MoulinetteLock,
    MoulinetteValidationError,
)
from moulinette.interfaces import BaseActionsMapParser, TO_RETURN_PROP
from moulinette.utils.log import start_action_logging
from moulinette.utils.filesystem import read_yaml

logger = logging.getLogger("moulinette.actionsmap")


# Extra parameters ----------------------------------------------------

# Extra parameters definition


class _ExtraParameter:
    """
    Argument parser for an extra parameter.

    It is a pure virtual class that each extra parameter classes must
    implement.

    """

    name: Optional[str] = None

    """A list of interface for which the parameter doesn't apply to"""
    skipped_iface: List[str] = []

    def __init__(self, iface):
        self.iface = iface

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
        return Moulinette.display(m18n.n(message))

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
            return Moulinette.prompt(m18n.n(message))
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
            return Moulinette.prompt(m18n.n(message), True, True)
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

            raise MoulinetteValidationError(
                "invalid_argument", argument=arg_name, error=msg
            )
        return arg_value

    @staticmethod
    def validate(value, arg_name):
        # Deprecated string type
        if isinstance(value, str):
            logger.warning(
                "expecting a list as extra parameter 'pattern' of " "argument '%s'",
                arg_name,
            )
            value = [value, "pattern_not_match"]  # i18n: pattern_not_match
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
            raise MoulinetteValidationError("argument_required", argument=arg_name)
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


class ExtraArgumentParser:

    """
    Argument validator and parser for the extra parameters.

    Keyword arguments:
        - iface -- The running interface

    """

    def __init__(self, iface):
        self.iface = iface
        self.extra = OrderedDict()
        self._extra_params = {"_global": {}}

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
            - tid -- The tuple identifier of the action or _global
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
        extra_args = OrderedDict(self._extra_params.get("_global", {}))
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


class ActionsMap:

    """Validate and process actions defined into an actions map

    The actions map defines the features - and their usage - of an
    application which will be available through the moulinette.
    It is composed by categories which contain one or more action(s).
    Moreover, the action can have specific argument(s).

    Keyword arguments:
        - top_parser -- A BaseActionsMapParser-derived instance to use for
                        parsing the actions map
        - load_only_category -- A name of a category that should only be the
                        one loaded because it's been already determined
                        that's the only one relevant ... used for optimization
                        purposes...
    """

    def __init__(self, actionsmap_yml, top_parser, load_only_category=None):

        assert isinstance(top_parser, BaseActionsMapParser), (
            "Invalid parser class '%s'" % top_parser.__class__.__name__
        )

        self.from_cache = False

        logger.debug("loading actions map")

        actionsmap_yml_dir = os.path.dirname(actionsmap_yml)
        actionsmap_yml_file = os.path.basename(actionsmap_yml)
        actionsmap_yml_stat = os.stat(actionsmap_yml)

        actionsmap_pkl = f"{actionsmap_yml_dir}/.{actionsmap_yml_file}.{actionsmap_yml_stat.st_size}-{actionsmap_yml_stat.st_mtime}.pkl"

        def generate_cache():

            logger.debug("generating cache for actions map")

            # Read actions map from yaml file
            actionsmap = read_yaml(actionsmap_yml)

            # Delete old cache files
            for old_cache in glob.glob(f"{actionsmap_yml_dir}/.{actionsmap_yml_file}.*.pkl"):
                os.remove(old_cache)

            # at installation, cachedir might not exists
            dir_ = os.path.dirname(actionsmap_pkl)
            if not os.path.isdir(dir_):
                os.makedirs(dir_)

            # Cache actions map into pickle file
            with open(actionsmap_pkl, "wb") as f:
                pickle.dump(actionsmap, f)

            return actionsmap

        if os.path.exists(actionsmap_pkl):
            try:
                # Attempt to load cache
                with open(actionsmap_pkl, "rb") as f:
                    actionsmap = pickle.load(f)

                self.from_cache = True
            # TODO: Switch to python3 and catch proper exception
            except (IOError, EOFError):
                actionsmap = generate_cache()
        else:  # cache file doesn't exists
            actionsmap = generate_cache()

        # If load_only_category is set, and *if* the target category
        # is in the actionsmap, we'll load only that one.
        # If we filter it even if it doesn't exist, we'll end up with a
        # weird help message when we do a typo in the category name..
        if load_only_category and load_only_category in actionsmap:
            actionsmap = {
                k: v
                for k, v in actionsmap.items()
                if k in [load_only_category, "_global"]
            }

        # Generate parsers
        self.extraparser = ExtraArgumentParser(top_parser.interface)
        self.parser = self._construct_parser(actionsmap, top_parser)

    def get_authenticator(self, auth_method):

        if auth_method == "default":
            auth_method = self.default_authentication

        # Load and initialize the authenticator module
        auth_module = f"{self.namespace}.authenticators.{auth_method}"
        logger.debug(f"Loading auth module {auth_module}")
        try:
            mod = import_module(auth_module)
        except ImportError as e:
            import traceback

            traceback.print_exc()
            raise MoulinetteError(
                f"unable to load authenticator {auth_module} : {e}", raw_msg=True
            )
        else:
            return mod.Authenticator()

    def check_authentication_if_required(self, *args, **kwargs):

        auth_method = self.parser.auth_method(*args, **kwargs)

        if auth_method is None:
            return

        authenticator = self.get_authenticator(auth_method)
        Moulinette.interface.authenticate(authenticator)

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
            func_name = "{}_{}_{}".format(
                category,
                subcategory.replace("-", "_"),
                action.replace("-", "_"),
            )
            full_action_name = "{}.{}.{}.{}".format(
                namespace,
                category,
                subcategory,
                action,
            )
        else:
            assert len(tid) == 3
            namespace, category, action = tid
            subcategory = None
            func_name = "{}_{}".format(category, action.replace("-", "_"))
            full_action_name = "{}.{}.{}".format(namespace, category, action)

        # Lock the moulinette for the namespace
        with MoulinetteLock(namespace, timeout):
            start = time()
            try:
                mod = __import__(
                    "{}.{}".format(namespace, category),
                    globals=globals(),
                    level=0,
                    fromlist=[func_name],
                )
                logger.debug(
                    "loading python module %s took %.3fs",
                    "{}.{}".format(namespace, category),
                    time() - start,
                )
                func = getattr(mod, func_name)
            except (AttributeError, ImportError) as e:
                import traceback

                traceback.print_exc()
                error_message = "unable to load function {}.{} because: {}".format(
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
                start = time()
                try:
                    return func(**arguments)
                finally:
                    stop = time()
                    logger.debug("action [%s] executed in %.3fs", log_id, stop - start)

    # Private methods

    def _construct_parser(self, actionsmap, top_parser):
        """
        Construct the parser with the actions map

        Keyword arguments:
            - actionsmap -- A dictionnary of categories/actions/arguments list
            - top_parser -- A BaseActionsMapParser-derived instance to use for
                parsing the actions map

        Returns:
            An interface relevant's parser object

        """

        logger.debug("building parser...")
        start = time()

        interface_type = top_parser.interface

        # If loading from cache, extra were already checked when cache was
        # loaded ? Not sure about this ... old code is a bit mysterious...
        validate_extra = not self.from_cache

        # namespace, actionsmap is a tuple where:
        #
        # * namespace define the top "name", for us it will always be
        #   "yunohost" and there well be only this one
        # * actionsmap is the actual actionsmap that we care about

        # Retrieve global parameters
        _global = actionsmap.pop("_global", {})

        self.namespace = _global["namespace"]
        self.cookie_name = _global["cookie_name"]
        self.default_authentication = _global["authentication"][
            interface_type
        ]

        if top_parser.has_global_parser():
            top_parser.add_global_arguments(_global["arguments"])

        # category_name is stuff like "user", "domain", "hooks"...
        # category_values is the values of this category (like actions)
        for category_name, category_values in actionsmap.items():

            actions = category_values.pop("actions", {})
            subcategories = category_values.pop("subcategories", {})

            # Get category parser
            category_parser = top_parser.add_category_parser(
                category_name, **category_values
            )

            # action_name is like "list" of "domain list"
            # action_options are the values
            for action_name, action_options in actions.items():
                arguments = action_options.pop("arguments", {})
                authentication = action_options.pop("authentication", {})
                tid = (self.namespace, category_name, action_name)

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

                action_parser.authentication = self.default_authentication
                if interface_type in authentication:
                    action_parser.authentication = authentication[interface_type]

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
                    authentication = action_options.pop("authentication", {})
                    tid = (self.namespace, category_name, subcategory_name, action_name)

                    try:
                        # Get action parser
                        action_parser = subcategory_parser.add_action_parser(
                            action_name, tid, **action_options
                        )
                    except AttributeError:
                        # No parser for the action
                        continue

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

                    action_parser.authentication = self.default_authentication
                    if interface_type in authentication:
                        action_parser.authentication = authentication[
                            interface_type
                        ]

        logger.debug("building parser took %.3fs", time() - start)
        return top_parser
