# -*- coding: utf-8 -*-

import os.path
from bottle import Bottle, request, response, HTTPResponse
from beaker.middleware import SessionMiddleware

from ..config import session_path, doc_json_path
from helpers import YunoHostError, YunoHostLDAP


## Bottle Plugins

class APIAuthPlugin(object):
    """
    Manage the authentication for the API access.

    """
    name = 'apiauth'
    api = 2

    def __init__(self):
        # TODO: Add options (e.g. session type, content type, ...)
        if not os.path.isdir(session_path):
            os.makedirs(session_path)

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
            'session.data_dir': session_path,
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

class ActionsMapPlugin(object):
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


## Main class

class MoulinetteAPI(object):
    """
    Initialize a HTTP server which serves the API to access to the
    moulinette actions.

    Keyword arguments:

        - actionsmap -- The relevant ActionsMap instance

        - routes -- A dict of additional routes to add in the form of
            {(method, uri): callback}

    """

    def __init__(self, actionsmap, routes={}):
        # Initialize app and default routes
        # TODO: Return OK to 'OPTIONS' xhr requests (l173)
        app = Bottle()
        app.route(['/api', '/api/<category:re:[a-z]+>'], method='GET',
                  callback=self.doc, skip=['apiauth'])

        # Append routes from the actions map
        amap = ActionsMapPlugin(actionsmap)
        for (m, u) in actionsmap.parser.routes:
            app.route(u, method=m, callback=self._error, apply=amap)

        # Append additional routes
        # TODO: Add an option to skip auth for the route
        for (m, u), c in routes.items():
            app.route(u, method=m, callback=c)

        # Define and install a plugin which sets proper header
        def apiheader(callback):
            def wrapper(*args, **kwargs):
                response.content_type = 'application/json'
                response.set_header('Access-Control-Allow-Origin', '*')
                return callback(*args, **kwargs)
            return wrapper
        app.install(apiheader)

        # Install authentication plugin
        apiauth = APIAuthPlugin()
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
            with open(doc_json_path +'/resources.json') as f:
                return f.read()

        try:
            with open(doc_json_path +'/'+ category +'.json') as f:
                return f.read()
        except IOError:
            return 'unknown'

    def _error(self, *args, **kwargs):
        # TODO: Raise or return an error
        print('error')
