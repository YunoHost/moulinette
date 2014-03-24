# -*- coding: utf-8 -*-

import errno
from bottle import run, request, response, Bottle, HTTPResponse
from json import dumps as json_encode

from moulinette.core import MoulinetteError, clean_session
from moulinette.helpers import YunoHostError, YunoHostLDAP

# API helpers ----------------------------------------------------------

import os
import binascii

def random20():
    return binascii.hexlify(os.urandom(20)).decode('ascii')


# HTTP Responses -------------------------------------------------------

class HTTPOKResponse(HTTPResponse):
    def __init__(self, output=''):
        super(HTTPOKResponse, self).__init__(output, 200)

class HTTPBadRequestResponse(HTTPResponse):
    def __init__(self, output=''):
        super(HTTPBadRequestResponse, self).__init__(output, 400)

class HTTPUnauthorizedResponse(HTTPResponse):
    def __init__(self, output=''):
        super(HTTPUnauthorizedResponse, self).__init__(output, 401)

class HTTPErrorResponse(HTTPResponse):
    def __init__(self, output=''):
        super(HTTPErrorResponse, self).__init__(output, 500)


# API moulinette interface ---------------------------------------------

class _ActionsMapPlugin(object):
    """Actions map Bottle Plugin

    Process relevant action for the request using the actions map and
    manage authentication.

    Keyword arguments:
        - actionsmap -- An ActionsMap instance

    """
    name = 'actionsmap'
    api = 2

    def __init__(self, actionsmap):
        # Connect signals to handlers
        actionsmap.connect('authenticate', self._do_authenticate)

        self.actionsmap = actionsmap
        # TODO: Save and load secrets?
        self.secrets = {}

    def setup(self, app):
        """Setup plugin on the application

        Add routes according to the actions map to the application.

        Keyword arguments:
            - app -- The application instance

        """
        ## Login wrapper
        def _login(callback):
            def wrapper():
                kwargs = {}
                try:
                    kwargs['password'] = request.POST['password']
                except KeyError:
                    raise HTTPBadRequestResponse(_("Missing password parameter"))
                try:
                    kwargs['profile'] = request.POST['profile']
                except KeyError:
                    pass
                return callback(**kwargs)
            return wrapper

        ## Logout wrapper
        def _logout(callback):
            def wrapper():
                kwargs = {}
                try:
                    kwargs['profile'] = request.POST.get('profile')
                except KeyError:
                    pass
                return callback(**kwargs)
            return wrapper

        # Append authentication routes
        app.route('/login', name='login', method='POST',
                  callback=self.login, skip=['actionsmap'], apply=_login)
        app.route('/logout', name='logout', method='GET',
                  callback=self.logout, skip=['actionsmap'], apply=_logout)

        # Append routes from the actions map
        for (m, p) in self.actionsmap.parser.routes:
            app.route(p, method=m, callback=self.process)

    def apply(self, callback, context):
        """Apply plugin to the route callback

        Install a wrapper which replace callback and process the
        relevant action for the route.

        Keyword arguments:
            callback -- The route callback
            context -- An instance of Route

        """
        def wrapper(*args, **kwargs):
            # Bring arguments together
            params = kwargs
            for a in args:
                params[a] = True
            for k, v in request.params.items():
                params[k] = v

            # Process the action
            return callback((request.method, context.rule), params)
        return wrapper


    ## Routes callbacks

    def login(self, password, profile='default'):
        """Log in to an authenticator profile

        Attempt to authenticate to a given authenticator profile and
        register it with the current session - a new one will be created
        if needed.

        Keyword arguments:
            - password -- A clear text password
            - profile -- The authenticator profile name to log in

        """
        # Retrieve session values
        s_id = request.get_cookie('session.id') or random20()
        try:
            s_secret = self.secrets[s_id]
        except KeyError:
            s_hashes = {}
        else:
            s_hashes = request.get_cookie('session.hashes',
                                          secret=s_secret) or {}
        s_hash = random20()

        try:
            # Attempt to authenticate
            auth = self.actionsmap.get_authenticator(profile)
            auth(password, token=(s_id, s_hash))
        except MoulinetteError as e:
            if len(s_hashes) > 0:
                try: self.logout(profile)
                except: pass
            if e.errno == errno.EACCES:
                raise HTTPUnauthorizedResponse(e.strerror)
            raise HTTPErrorResponse(e.strerror)
        else:
            # Update dicts with new values
            s_hashes[profile] = s_hash
            self.secrets[s_id] = s_secret = random20()

            response.set_cookie('session.id', s_id, secure=True)
            response.set_cookie('session.hashes', s_hashes, secure=True,
                                secret=s_secret)
            raise HTTPOKResponse()

    def logout(self, profile=None):
        """Log out from an authenticator profile

        Attempt to unregister a given profile - or all by default - from
        the current session.

        Keyword arguments:
            - profile -- The authenticator profile name to log out

        """
        s_id = request.get_cookie('session.id')
        try:
            del self.secrets[s_id]
        except KeyError:
            raise HTTPUnauthorizedResponse(_("You are not logged in"))
        else:
            # TODO: Clean the session for profile only
            # Delete cookie and clean the session
            response.set_cookie('session.hashes', '', max_age=-1)
            clean_session(s_id)
        raise HTTPOKResponse()

    def process(self, _route, arguments={}):
        """Process the relevant action for the route

        Call the actions map in order to process the relevant action for
        the route with the given arguments and process the returned
        value.

        Keyword arguments:
            - _route -- The action route as a 2-tuple (method, path)
            - arguments -- A dict of arguments for the route

        """
        try:
            ret = self.actionsmap.process(arguments, route=_route)
        except MoulinetteError as e:
            raise HTTPErrorResponse(e.strerror)
        else:
            return ret


    ## Signals handlers

    def _do_authenticate(self, authenticator, help):
        """Process the authentication

        Handle the actionsmap._AMapSignals.authenticate signal.

        """
        s_id = request.get_cookie('session.id')
        try:
            s_secret = self.secrets[s_id]
            s_hash = request.get_cookie('session.hashes',
                                        secret=s_secret)[authenticator.name]
        except KeyError:
            if authenticator.name == 'default':
                msg = _("Needing authentication")
            else:
                msg = _("Needing authentication to profile '%s'") % authenticator.name
            raise HTTPUnauthorizedResponse(msg)
        else:
            return authenticator(token=(s_id, s_hash))


class MoulinetteAPI(object):
    """Moulinette  Application Programming Interface

    Initialize a HTTP server which serves the API to process moulinette
    actions.

    Keyword arguments:
        - actionsmap -- The relevant ActionsMap instance
        - routes -- A dict of additional routes to add in the form of
            {(method, path): callback}

    """
    def __init__(self, actionsmap, routes={}):
        # TODO: Return OK to 'OPTIONS' xhr requests (l173)
        app = Bottle(autojson=False)

        ## Wrapper which sets proper header
        def apiheader(callback):
            def wrapper(*args, **kwargs):
                response.content_type = 'application/json'
                response.set_header('Access-Control-Allow-Origin', '*')
                return json_encode(callback(*args, **kwargs))
            return wrapper

        # Install plugins
        app.install(apiheader)
        app.install(_ActionsMapPlugin(actionsmap))

        # Append default routes
        app.route(['/api', '/api/<category:re:[a-z]+>'], method='GET',
                  callback=self.doc, skip=['actionsmap'])

        # Append additional routes
        # TODO: Add optional authentication to those routes?
        for (m, p), c in routes.items():
            app.route(p, method=m, callback=c, skip=['actionsmap'])

        self._app = app

    def run(self, _port):
        """Run the moulinette

        Start a server instance on the given port to serve moulinette
        actions.

        Keyword arguments:
            - _port -- Port number to run on

        """
        try:
            run(self._app, port=_port)
        except IOError as e:
            if e.args[0] == errno.EADDRINUSE:
                raise MoulinetteError(errno.EADDRINUSE, _("A server is already running"))
            raise


    ## Routes handlers

    def doc(self, category=None):
        """
        Get API documentation for a category (all by default)

        Keyword argument:
            category -- Name of the category

        """
        if category is None:
            with open('%s/../doc/resources.json' % pkg.datadir) as f:
                return f.read()

        try:
            with open('%s/../doc/%s.json' % (pkg.datadir, category)) as f:
                return f.read()
        except IOError:
            return None
