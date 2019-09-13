# -*- coding: utf-8 -*-

from moulinette.core import (
    init_interface,
    MoulinetteError,
    MoulinetteSignals,
    Moulinette18n,
)
from moulinette.globals import init_moulinette_env

__title__ = 'moulinette'
__version__ = '0.1'
__author__ = ['Kload', 'jlebleu', 'titoko', 'beudbeud', 'npze']
__license__ = 'AGPL 3.0'
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
__all__ = ['init', 'api', 'cli', 'm18n', 'env', 'init_interface', 'MoulinetteError']


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
    sys.path.insert(0, init_moulinette_env()['LIB_DIR'])


# Easy access to interfaces


def api(
    namespaces, host='localhost', port=80, routes={}, use_websocket=True, use_cache=True
):
    """Web server (API) interface

    Run a HTTP server with the moulinette for an API usage.

    Keyword arguments:
        - namespaces -- The list of namespaces to use
        - host -- Server address to bind to
        - port -- Server port to bind to
        - routes -- A dict of additional routes to add in the form of
            {(method, uri): callback}
        - use_websocket -- Serve via WSGI to handle asynchronous responses
        - use_cache -- False if it should parse the actions map file
            instead of using the cached one

    """
    try:
        moulinette = init_interface(
            'api',
            kwargs={'routes': routes, 'use_websocket': use_websocket},
            actionsmap={'namespaces': namespaces, 'use_cache': use_cache},
        )
        moulinette.run(host, port)
    except MoulinetteError as e:
        import logging

        logging.getLogger(namespaces[0]).error(e.strerror)
        return e.errno if hasattr(e, "errno") else 1
    except KeyboardInterrupt:
        import logging

        logging.getLogger(namespaces[0]).info(m18n.g('operation_interrupted'))
    return 0


def cli(
    namespaces,
    args,
    use_cache=True,
    output_as=None,
    password=None,
    timeout=None,
    parser_kwargs={},
):
    """Command line interface

    Execute an action with the moulinette from the CLI and print its
    result in a readable format.

    Keyword arguments:
        - namespaces -- The list of namespaces to use
        - args -- A list of argument strings
        - use_cache -- False if it should parse the actions map file
            instead of using the cached one
        - output_as -- Output result in another format, see
            moulinette.interfaces.cli.Interface for possible values
        - password -- The password to use in case of authentication
        - parser_kwargs -- A dict of arguments to pass to the parser
            class at construction

    """
    try:
        moulinette = init_interface(
            'cli',
            actionsmap={
                'namespaces': namespaces,
                'use_cache': use_cache,
                'parser_kwargs': parser_kwargs,
            },
        )
        moulinette.run(args, output_as=output_as, password=password, timeout=timeout)
    except MoulinetteError as e:
        import logging

        logging.getLogger(namespaces[0]).error(e.strerror)
        return 1
    return 0


def env():
    """Initialise moulinette specific configuration."""
    return init_moulinette_env()
