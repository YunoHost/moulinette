# -*- coding: utf-8 -*-

__title__ = 'moulinette'
__version__ = '0.1'
__author__ = ['Kload',
              'jlebleu',
              'titoko',
              'beudbeud',
              'npze']
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
__all__ = [
    'init', 'api', 'cli',
    'init_interface', 'MoulinetteError',
]

from moulinette.core import init_interface, MoulinetteError


## Package functions

def init(**kwargs):
    """Package initialization

    Initialize directories and global variables. It must be called
    before any of package method is used - even the easy access
    functions.

    Keyword arguments:
        - **kwargs -- See core.Package

    At the end, the global variable 'pkg' will contain a Package
    instance. See core.Package for available methods and variables.

    """
    import sys
    import __builtin__
    from moulinette.core import (
        Package, Moulinette18n, MoulinetteSignals
    )
    __builtin__.__dict__['pkg'] = Package(**kwargs)
    __builtin__.__dict__['m18n'] = Moulinette18n(pkg)
    __builtin__.__dict__['msignals'] = MoulinetteSignals()
    __builtin__.__dict__['msettings'] = dict()

    # Add library directory to python path
    sys.path.insert(0, pkg.libdir)


## Easy access to interfaces

def api(namespaces, host='localhost', port=80, routes={},
        use_websocket=True, use_cache=True):
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
    moulinette = init_interface('api',
                                kwargs={'routes': routes},
                                actionsmap={'namespaces': namespaces,
                                            'use_cache': use_cache})
    moulinette.run(host, port, use_websocket)

def cli(namespaces, args, print_json=False, use_cache=True):
    """Command line interface

    Execute an action with the moulinette from the CLI and print its
    result in a readable format.

    Keyword arguments:
        - namespaces -- The list of namespaces to use
        - args -- A list of argument strings
        - print_json -- True to print result as a JSON encoded string
        - use_cache -- False if it should parse the actions map file
            instead of using the cached one

    """
    from moulinette.interfaces.cli import colorize

    try:
        moulinette = init_interface('cli',
                                    actionsmap={'namespaces': namespaces,
                                                'use_cache': use_cache})
        moulinette.run(args, print_json)
    except MoulinetteError as e:
        print(u'%s %s' % (colorize(m18n.g('error'), 'red'), e.strerror))
        return e.errno
    return 0
