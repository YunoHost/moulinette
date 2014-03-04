# -*- coding: utf-8 -*-

import re
import argparse
import os.path
from bottle import Bottle, request, response, HTTPResponse
from beaker.middleware import SessionMiddleware

from . import BaseParser
from .. import MoulinetteError
from ..helpers import YunoHostError, YunoHostLDAP

## API arguments Parser

class _HTTPArgumentParser(object):
    """Argument parser for HTTP requests

    Object for parsing HTTP requests into Python objects. It is based
    on argparse.ArgumentParser class and implements some of its methods.

    """
    def __init__(self):
        # Initialize the ArgumentParser object
        self._parser = argparse.ArgumentParser(usage='',
                                               prefix_chars='@',
                                               add_help=False)
        self._parser.error = self._error

        self._positional = []   # list(arg_name)
        self._optional = {}     # dict({arg_name: option_strings})

    def set_defaults(self, **kwargs):
        return self._parser.set_defaults(**kwargs)

    def get_default(self, dest):
        return self._parser.get_default(dest)

    def add_argument(self, *args, **kwargs):
        action = self._parser.add_argument(*args, **kwargs)

        # Append newly created action
        if len(action.option_strings) == 0:
            self._positional.append(action.dest)
        else:
            self._optional[action.dest] = action.option_strings

        return action

    def parse_args(self, args):
        arg_strings = []

        ## Append an argument to the current one
        def append(arg_strings, value, option_string=None):
            # TODO: Process list arguments
            if isinstance(value, bool):
                # Append the option string only
                if option_string is not None:
                    arg_strings.append(option_string)
            elif isinstance(value, str):
                if option_string is not None:
                    arg_strings.append(option_string)
                    arg_strings.append(value)
                else:
                    arg_strings.append(value)

            return arg_strings

        # Iterate over positional arguments
        for dest in self._positional:
            if dest in args:
                arg_strings = append(arg_strings, args[dest])

        # Iterate over optional arguments
        for dest, opt in self._optional.items():
            if dest in args:
                arg_strings = append(arg_strings, args[dest], opt[0])
        return self._parser.parse_args(arg_strings)

    def _error(self, message):
        # TODO: Raise a proper exception
        raise MoulinetteError(1, message)

class APIParser(BaseParser):
    """Actions map's API Parser

    """
    parse_category = False
    parse_general = False

    def __init__(self):
        self._parsers = {}   # dict({(method, path): _HTTPArgumentParser})

    @property
    def routes(self):
        """Get current routes"""
        return self._parsers.keys()

    
    ## Implement virtual methods

    @staticmethod
    def format_arg_name(name, full):
        if name[0] != '-':
            return [name]
        if full:
            return [full.replace('--', '@', 1)]
        if name.startswith('--'):
            return [name.replace('--', '@', 1)]
        return [name.replace('-', '@', 1)]

    def add_action_parser(self, name, api=None, **kwargs):
        """Add a parser for an action

        Keyword arguments:
            - api -- The action route (e.g. 'GET /' )

        Returns:
            A new _HTTPArgumentParser object for the route

        """
        if not api:
            return None

        # Validate action route
        m = re.match('(GET|POST|PUT|DELETE) (/\S+)', api)
        if not m:
            return None

        # Check if a parser already exists for the route
        key = (m.group(1), m.group(2))
        if key in self.routes:
            raise ValueError("A parser for '%s' already exists" % key)

        # Create and append parser
        parser = _HTTPArgumentParser()
        self._parsers[key] = parser

        # Return the created parser
        return parser

    def parse_args(self, args, route, **kwargs):
        """Parse arguments

        Keyword arguments:
            - route -- The action route (e.g. 'GET /' )

        """
        # Retrieve the parser for the route
        if route not in self.routes:
            raise MoulinetteError(22, "No parser for '%s %s' found" % key)

        return self._parsers[route].parse_args(args)

actionsmap_parser = APIParser


## API moulinette interface

class _APIAuthPlugin(object):
    """
    Manage the authentication for the API access.

    """
    name = 'apiauth'
    api = 2

    def __init__(self):
        # TODO: Add options (e.g. session type, content type, ...)
        pass

    @property
    def app(self):
        """Get Bottle application with session integration"""
        if hasattr(self, '_app'):
            return self._app
        raise Exception(_("The APIAuth Plugin is not installed yet."))

    def setup(self, app):
        """
        Setup the plugin and install the session into the app

        Keyword argument:
            app -- The associated application object

        """
        app.route('/login', name='login', method='POST', callback=self.login)
        app.route('/logout', name='logout', method='GET', callback=self.logout)

        session_opts = {
            'session.type': 'file',
            'session.cookie_expires': True,
            'session.data_dir': pkg.cachedir('session', make_dir=True),
            'session.secure': True
        }
        self._app = SessionMiddleware(app, session_opts)

    def apply(self, callback, context):
        """
        Check authentication before executing the route callback

        Keyword argument:
            callback -- The route callback
            context -- An instance of Route

        """
        # Check the authentication
        if self._is_authenticated:
            if context.name == 'login':
                self.logout()
            else:
                return callback

        # Process login route
        if context.name == 'login':
            password = request.POST.get('password', None)
            if password is not None and self.login(password):
                raise HTTPResponse(status=200)
            else:
                raise HTTPResponse(_("Wrong password"), 401)

        # Deny access to the requested route
        raise HTTPResponse(_("Unauthorized"), 401)

    def login(self, password):
        """
        Attempt to log in with the given password

        Keyword argument:
            password -- Cleartext password

        """
        try: YunoHostLDAP(password=password)
        except YunoHostError:
            return False
        else:
            session = self._beaker_session
            session['authenticated'] = True
            session.save()
            return True
        return False

    def logout(self):
        """
        Log out and delete the session

        """
        # TODO: Delete the cached session file
        session = self._beaker_session
        session.delete()


    ## Private methods

    @property
    def _beaker_session(self):
        """Get Beaker session"""
        return request.environ.get('beaker.session')

    @property
    def _is_authenticated(self):
        """Check authentication"""
        # TODO: Clear the session path on password changing to avoid invalid access
        if 'authenticated' in self._beaker_session:
            return True
        return False

class _ActionsMapPlugin(object):
    """
    Process action for the request using the actions map.

    """
    name = 'actionsmap'
    api = 2

    def __init__(self, actionsmap):
        self.actionsmap = actionsmap

    def setup(self, app):
        pass

    def apply(self, callback, context):
        """
        Process the relevant action for the request

        Keyword argument:
            callback -- The route callback
            context -- An instance of Route

        """
        method = request.method
        uri = context.rule

        def wrapper(*args, **kwargs):
            # Bring arguments together
            params = kwargs
            for a in args:
                params[a] = True
            for k, v in request.params.items():
                params[k] = v

            # Process the action
            return self.actionsmap.process(params, route=(method, uri))
        return wrapper


class MoulinetteAPI(object):
    """
    Initialize a HTTP server which serves the API to access to the
    moulinette actions.

    Keyword arguments:
        - actionsmap -- The relevant ActionsMap instance
        - routes -- A dict of additional routes to add in the form of
            {(method, path): callback}

    """

    def __init__(self, actionsmap, routes={}):
        # Initialize app and default routes
        # TODO: Return OK to 'OPTIONS' xhr requests (l173)
        app = Bottle()
        app.route(['/api', '/api/<category:re:[a-z]+>'], method='GET',
                  callback=self.doc, skip=['apiauth'])

        # Append routes from the actions map
        amap = _ActionsMapPlugin(actionsmap)
        for (m, p) in actionsmap.parser.routes:
            app.route(p, method=m, callback=self._error, apply=amap)

        # Append additional routes
        # TODO: Add an option to skip auth for the route
        for (m, p), c in routes.items():
            app.route(p, method=m, callback=c)

        # Define and install a plugin which sets proper header
        def apiheader(callback):
            def wrapper(*args, **kwargs):
                response.content_type = 'application/json'
                response.set_header('Access-Control-Allow-Origin', '*')
                return callback(*args, **kwargs)
            return wrapper
        app.install(apiheader)

        # Install authentication plugin
        apiauth = _APIAuthPlugin()
        app.install(apiauth)

        self._app = apiauth.app

    @property
    def app(self):
        """Get Bottle application"""
        return self._app

    def doc(self, category=None):
        """
        Get API documentation for a category (all by default)

        Keyword argument:
            category -- Name of the category

        """
        if category is None:
            with open(pkg.datafile('doc/resources.json')) as f:
                return f.read()

        try:
            with open(pkg.datafile('doc/%s.json' % category)) as f:
                return f.read()
        except IOError:
            return 'unknown'

    def _error(self, *args, **kwargs):
        # TODO: Raise or return an error
        print('error')
