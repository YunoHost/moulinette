# -*- coding: utf-8 -*-

import getpass
import re
import logging

from .. import MoulinetteError
from ..helpers import colorize

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


## Extra parameters definitions

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

        # Ask for the argument value
        ret = raw_input(colorize(message + ': ', 'cyan'))
        return ret

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

        # Ask for the password
        pwd1 = getpass.getpass(colorize(message + ': ', 'cyan'))
        pwd2 = getpass.getpass(colorize('Retype ' + message + ': ', 'cyan'))
        if pwd1 != pwd2:
            raise MoulinetteError(22, _("Passwords don't match"))
        return pwd1

class PatternParameter(_ExtraParameter):
    """
    Check if the argument value match a pattern.

    The value of this parameter corresponds to a list of the pattern and
    the message to display if it doesn't match.

    """
    name = 'pattern'

    def __call__(self, arguments, arg_name, arg_value):
        pattern = arguments[0]
        message = arguments[1]

        if arg_value is not None and not re.match(pattern, arg_value):
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
