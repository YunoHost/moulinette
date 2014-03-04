# -*- coding: utf-8 -*-

class BaseParser(object):
    """Actions map's base Parser

    Each interfaces must implement a parser class derived from this
    class. It is used to parse the main parts of the actions map (i.e.
    general arguments, categories and actions).

    """

    ## Optional variables
    # Each parser classes can overwrite these variables.

    """Either it will parse general arguments, or not"""
    parse_general = True

    """Either it will parse categories, or not"""
    parse_category = True

    """Either it will parse actions, or not"""
    parse_action = True


    ## Virtual methods
    # Each parser classes can implement these methods.

    @staticmethod
    def format_arg_name(name, full):
        """Format argument name

        Format agument name depending on its 'full' parameters and return
        a list to use it as option string for the argument parser.

        Keyword arguments:
            - name -- The argument name
            - full -- The argument's 'full' parameter

        Returns:
            A list of option strings

        """
        raise NotImplementedError("derived class '%s' must override this method" % \
                                    self.__class__.__name__)

    def add_general_parser(self, **kwargs):
        """Add a parser for general arguments

        Create and return an argument parser for general arguments.

        Returns:
            An ArgumentParser based object

        """
        if not self.parse_general:
            msg = "doesn't parse general arguments"
        else:
            msg = "must override this method"
        raise NotImplementedError("derived class '%s' %s" % \
                                    (self.__class__.__name__, msg))

    def add_category_parser(self, name, **kwargs):
        """Add a parser for a category

        Create a new category and return a parser for it.

        Keyword arguments:
            - name -- The category name

        Returns:
            A BaseParser based object

        """
        if not self.parse_categories:
            msg = "doesn't parse categories"
        else:
            msg = "must override this method"
        raise NotImplementedError("derived class '%s' %s" % \
                                    (self.__class__.__name__, msg))

    def add_action_parser(self, name, **kwargs):
        """Add a parser for an action

        Create a new action and return an argument parser for it.

        Keyword arguments:
            - name -- The action name

        Returns:
            An ArgumentParser based object

        """
        if not self.parse_general:
            msg = "doesn't parse actions"
        else:
            msg = "must override this method"
        raise NotImplementedError("derived class '%s' %s" % \
                                    (self.__class__.__name__, msg))

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
