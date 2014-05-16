# -*- coding: utf-8 -*-

import os
import re
import errno
import binascii
import argparse
from json import dumps as json_encode
from bottle import run, request, response, Bottle, HTTPResponse

from moulinette.core import MoulinetteError, clean_session
from moulinette.interfaces import (BaseActionsMapParser, BaseInterface)

# API helpers ----------------------------------------------------------

def random_ascii(length=20):
    """Return a random ascii string"""
    return binascii.hexlify(os.urandom(length)).decode('ascii')

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

    def parse_args(self, args={}, namespace=None):
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
                    # TODO: Review this fix
                    if value:
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

        return self._parser.parse_args(arg_strings, namespace)

    def _error(self, message):
        # TODO: Raise a proper exception
        raise MoulinetteError(1, message)

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
        msignals.set_handler('authenticate', self._do_authenticate)

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
                    raise HTTPBadRequestResponse("Missing password parameter")
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
        try:
            # Attempt to retrieve and set locale
            m18n.set_locale(request.params.pop('locale'))
        except:
            pass

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
        s_id = request.get_cookie('session.id') or random_ascii()
        try:
            s_secret = self.secrets[s_id]
        except KeyError:
            s_hashes = {}
        else:
            s_hashes = request.get_cookie('session.hashes',
                                          secret=s_secret) or {}
        s_hash = random_ascii()

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
            self.secrets[s_id] = s_secret = random_ascii()

            response.set_cookie('session.id', s_id, secure=True)
            response.set_cookie('session.hashes', s_hashes, secure=True,
                                secret=s_secret)
            return m18n.g('logged_in')

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
            raise HTTPUnauthorizedResponse(m18n.g('not_logged_in'))
        else:
            # TODO: Clean the session for profile only
            # Delete cookie and clean the session
            response.set_cookie('session.hashes', '', max_age=-1)
            clean_session(s_id)
        return m18n.g('logged_out')

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

        Handle the core.MoulinetteSignals.authenticate signal.

        """
        s_id = request.get_cookie('session.id')
        try:
            s_secret = self.secrets[s_id]
            s_hash = request.get_cookie('session.hashes',
                                        secret=s_secret)[authenticator.name]
        except KeyError:
            if authenticator.name == 'default':
                msg = m18n.g('authentication_required')
            else:
                msg = m18n.g('authentication_profile_required') % authenticator.name
            raise HTTPUnauthorizedResponse(msg)
        else:
            return authenticator(token=(s_id, s_hash))


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


# API Classes Implementation -------------------------------------------

class ActionsMapParser(BaseActionsMapParser):
    """Actions map's Parser for the API

    Provide actions map parsing methods for a CLI usage. The parser for
    the arguments is represented by a argparse.ArgumentParser object.

    """
    def __init__(self, parent=None):
        super(ActionsMapParser, self).__init__(parent)

        self._parsers = {} # dict({(method, path): _HTTPArgumentParser})

    @property
    def routes(self):
        """Get current routes"""
        return self._parsers.keys()


    ## Implement virtual properties

    interface = 'api'


    ## Implement virtual methods

    @staticmethod
    def format_arg_names(name, full):
        if name[0] != '-':
            return [name]
        if full:
            return [full.replace('--', '@', 1)]
        if name.startswith('--'):
            return [name.replace('--', '@', 1)]
        return [name.replace('-', '@', 1)]

    def add_global_parser(self, **kwargs):
        raise AttributeError("global arguments are not managed")

    def add_category_parser(self, name, **kwargs):
        return self

    def add_action_parser(self, name, tid, api=None, **kwargs):
        """Add a parser for an action

        Keyword arguments:
            - api -- The action route (e.g. 'GET /' )

        Returns:
            A new _HTTPArgumentParser object for the route

        """
        try:
            # Validate action route
            m = re.match('(GET|POST|PUT|DELETE) (/\S+)', api)
        except TypeError:
            raise AttributeError("the action '%s' doesn't provide api access" % name)
        if not m:
            # TODO: Log error
            raise ValueError("the action '%s' doesn't provide api access" % name)

        # Check if a parser already exists for the route
        key = (m.group(1), m.group(2))
        if key in self.routes:
            raise AttributeError("a parser for '%s' already exists" % key)

        # Create and append parser
        parser = _HTTPArgumentParser()
        self._parsers[key] = (tid, parser)

        # Return the created parser
        return parser

    def parse_args(self, args, route, **kwargs):
        """Parse arguments

        Keyword arguments:
            - route -- The action route as a 2-tuple (method, path)

        """
        try:
            # Retrieve the tid and the parser for the route
            tid, parser = self._parsers[route]
        except KeyError:
            raise MoulinetteError(errno.EINVAL, "No parser found for route '%s'" % route)
        ret = argparse.Namespace()

        
        if not self.get_conf(tid, 'lock'):
            os.environ['BYPASS_LOCK'] = 'yes'

        # Perform authentication if needed
        if self.get_conf(tid, 'authenticate'):
            # TODO: Clean this hard fix and find a way to set an authenticator
            # to use for the api only
            # auth_conf, klass = self.get_conf(tid, 'authenticator')
            auth_conf, klass = self.get_global_conf('authenticator', 'default')

            # TODO: Catch errors
            auth = msignals.authenticate(klass(), **auth_conf)
            if not auth.is_authenticated:
                # TODO: Set proper error code
                raise MoulinetteError(errno.EACCES, m18n.g('authentication_required_long'))
            if self.get_conf(tid, 'argument_auth') and \
               self.get_conf(tid, 'authenticate') == 'all':
                ret.auth = auth

        return parser.parse_args(args, ret)


class Interface(BaseInterface):
    """Application Programming Interface for the moulinette

    Initialize a HTTP server which serves the API connected to a given
    actions map.

    Keyword arguments:
        - actionsmap -- The ActionsMap instance to connect to
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
#        app.route(['/api', '/api/<category:re:[a-z]+>'], method='GET',
#                  callback=self.doc, skip=['actionsmap'])

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
                raise MoulinetteError(errno.EADDRINUSE,
                                      m18n.g('server_already_running'))
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
