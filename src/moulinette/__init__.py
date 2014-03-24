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
    'MoulinetteError',
]

from moulinette.core import MoulinetteError


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
    from moulinette.core import Package, install_i18n
    __builtin__.__dict__['pkg'] = Package(**kwargs)

    # Initialize internationalization
    install_i18n()

    # Add library directory to python path
    sys.path.insert(0, pkg.libdir)


## Easy access to interfaces

def api(namespaces, port, routes={}, use_cache=True):
    """Web server (API) interface

    Run a HTTP server with the moulinette for an API usage.

    Keyword arguments:
        - namespaces -- The list of namespaces to use
        - port -- Port number to run on
        - routes -- A dict of additional routes to add in the form of
            {(method, uri): callback}
        - use_cache -- False if it should parse the actions map file
            instead of using the cached one

    """
    from moulinette.actionsmap import ActionsMap
    from moulinette.interface.api import MoulinetteAPI

    amap = ActionsMap('api', namespaces, use_cache)
    moulinette = MoulinetteAPI(amap, routes)

    moulinette.run(port)

def cli(namespaces, args, use_cache=True):
    """Command line interface

    Execute an action with the moulinette from the CLI and print its
    result in a readable format.

    Keyword arguments:
        - namespaces -- The list of namespaces to use
        - args -- A list of argument strings
        - use_cache -- False if it should parse the actions map file
            instead of using the cached one

    """
    from moulinette.actionsmap import ActionsMap
    from moulinette.interface.cli import MoulinetteCLI, colorize

    try:
        amap = ActionsMap('cli', namespaces, use_cache)
        moulinette = MoulinetteCLI(amap)

        moulinette.run(args)
    except MoulinetteError as e:
        print(_('%s: %s' % (colorize(_('Error'), 'red'), e.strerror)))
        return e.errno
    return 0
