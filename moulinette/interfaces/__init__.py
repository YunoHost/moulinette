# -*- coding: utf-8 -*-

import errno
import logging

from moulinette.core import (init_authenticator, MoulinetteError)

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
    interface = None


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

    def add_action_parser(self, name, tid, **kwargs):
        """Add a parser for an action

        Create a new action and return an argument parser for it.

        Keyword arguments:
            - name -- The action name
            - tid -- The tuple identifier of the action

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
            elif ifaces == False:
                conf['authenticate'] = False
            elif isinstance(ifaces, list):
                # Store only if authentication is needed
                conf['authenticate'] = True if self.interface in ifaces else False
            else:
                # TODO: Log error instead and tell valid values
                raise MoulinetteError(errno.EINVAL, "Invalid value '%r' for configuration 'authenticate'" % ifaces)

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
                    raise MoulinetteError(errno.EINVAL, "Undefined authenticator '%s' in global configuration" % auth)
            elif is_global and isinstance(auth, dict):
                if len(auth) == 0:
                    logging.warning('no authenticator defined in global configuration')
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
                                            { 'help': auth_conf.get('help', None) },
                                            auth_conf.get('parameters', {}))
                    conf['authenticator'] = auths
            else:
                # TODO: Log error instead and tell valid values
                raise MoulinetteError(errno.EINVAL, "Invalid value '%r' for configuration 'authenticator'" % auth)

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
                raise MoulinetteError(errno.EINVAL, "Invalid value '%r' for configuration 'argument_auth'" % arg_auth)

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
        raise NotImplementedError("derived class '%s' must override this method" % \
                                      self.__class__.__name__)
