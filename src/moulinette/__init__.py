# -*- coding: utf-8 -*-

__title__ = 'moulinette'
__version__ = '695'
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


## Fast access functions

def api(port, routes={}, use_cache=True):
    """
    Run a HTTP server with the moulinette for an API usage.

    Keyword arguments:

        - port -- Port to run on

        - routes -- A dict of additional routes to add in the form of
            {(method, uri): callback}

        - use_cache -- False if it should parse the actions map file
            instead of using the cached one

    """
    from bottle import run
    from core.actionsmap import ActionsMap
    from core.api import MoulinetteAPI

    amap = ActionsMap(ActionsMap.IFACE_API, use_cache=use_cache)
    moulinette = MoulinetteAPI(amap, routes)

    run(moulinette.app, port=port)

def cli(args, use_cache=True):
    """
    Execute an action with the moulinette from the CLI and print its
    result in a readable format.

    Keyword arguments:

        - args -- A list of argument strings

        - use_cache -- False if it should parse the actions map file
            instead of using the cached one

    """
    import os
    from core.actionsmap import ActionsMap
    from core.helpers import YunoHostError, pretty_print_dict

    lock_file = '/var/run/moulinette.lock'

    # Check the lock
    if os.path.isfile(lock_file):
        raise YunoHostError(1, _("The moulinette is already running"))

    # Create a lock
    with open(lock_file, 'w') as f: pass
    os.system('chmod 400 '+ lock_file)

    try:
        amap = ActionsMap(ActionsMap.IFACE_CLI, use_cache=use_cache)
        pretty_print_dict(amap.process(args))
    except KeyboardInterrupt, EOFError:
        raise YunoHostError(125, _("Interrupted"))
    finally:
        # Remove the lock
        os.remove(lock_file)
