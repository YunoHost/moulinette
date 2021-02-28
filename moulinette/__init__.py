# -*- coding: utf-8 -*-

from moulinette.core import (
    MoulinetteError,
    MoulinetteSignals,
    Moulinette18n,
)
from moulinette.globals import init_moulinette_env

__title__ = "moulinette"
__author__ = ["Yunohost Contributors"]
__license__ = "AGPL 3.0"
__credits__ = """
    Copyright (C) 2014 YUNOHOST.ORG

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published
    by the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program; if not, see http://www.gnu.org/licenses
    """
__all__ = [
    "init",
    "api",
    "cli",
    "m18n",
    "msignals",
    "env",
    "init_interface",
    "MoulinetteError",
]


msignals = MoulinetteSignals()
msettings = dict()
m18n = Moulinette18n()


# Package functions


def init(logging_config=None, **kwargs):
    """Package initialization

    Initialize directories and global variables. It must be called
    before any of package method is used - even the easy access
    functions.

    Keyword arguments:
        - logging_config -- A dict containing logging configuration to load
        - **kwargs -- See core.Package

    At the end, the global variable 'pkg' will contain a Package
    instance. See core.Package for available methods and variables.

    """
    import sys
    from moulinette.utils.log import configure_logging

    configure_logging(logging_config)

    # Add library directory to python path
    sys.path.insert(0, init_moulinette_env()["LIB_DIR"])


# Easy access to interfaces
def api(host="localhost", port=80, routes={}):
    """Web server (API) interface

    Run a HTTP server with the moulinette for an API usage.

    Keyword arguments:
        - host -- Server address to bind to
        - port -- Server port to bind to
        - routes -- A dict of additional routes to add in the form of
            {(method, uri): callback}

    """
    from moulinette.interfaces.api import Interface as Api

    try:
        Api(routes=routes).run(host, port)
    except MoulinetteError as e:
        import logging

        logging.getLogger("moulinette").error(e.strerror)
        return 1
    except KeyboardInterrupt:
        import logging

        logging.getLogger("moulinette").info(m18n.g("operation_interrupted"))
    return 0


def cli(args, top_parser, output_as=None, timeout=None):
    """Command line interface

    Execute an action with the moulinette from the CLI and print its
    result in a readable format.

    Keyword arguments:
        - args -- A list of argument strings
        - output_as -- Output result in another format, see
            moulinette.interfaces.cli.Interface for possible values
        - top_parser -- The top parser used to build the ActionsMapParser

    """
    from moulinette.interfaces.cli import Interface as Cli

    try:
        load_only_category = args[0] if args and not args[0].startswith("-") else None
        Cli(top_parser=top_parser, load_only_category=load_only_category).run(
            args, output_as=output_as, timeout=timeout
        )
    except MoulinetteError as e:
        import logging

        logging.getLogger("moulinette").error(e.strerror)
        return 1
    return 0


def env():
    """Initialise moulinette specific configuration."""
    return init_moulinette_env()
