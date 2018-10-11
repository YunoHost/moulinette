# -*- coding: utf-8 -*-

import os
import re
import errno
import logging
import argparse
from json import dumps as json_encode

from gevent import sleep
from gevent.queue import Queue
from geventwebsocket import WebSocketError

from bottle import run, request, response, Bottle, HTTPResponse

from moulinette.core import MoulinetteError, clean_session
from moulinette.interfaces import (
    BaseActionsMapParser, BaseInterface, ExtendedArgumentParser,
)
from moulinette.utils import log
from moulinette.utils.serialize import JSONExtendedEncoder
from moulinette.utils.text import random_ascii

logger = log.getLogger('moulinette.interface.api')


# API helpers ----------------------------------------------------------

class LogQueues(dict):
    """Map of session id to queue."""
    pass


class APIQueueHandler(logging.Handler):
    """
    A handler class which store logging records into a queue, to be used
    and retrieved from the API.
    """

    def __init__(self):
        logging.Handler.__init__(self)
        self.queues = LogQueues()

    def emit(self, record):
        sid = request.get_cookie('session.id')
        try:
            queue = self.queues[sid]
        except KeyError:
            # Session is not initialized, abandon.
            return
        else:
            # Put the message as a 2-tuple in the queue
            queue.put_nowait((record.levelname.lower(), record.getMessage()))
            # Put the current greenlet to sleep for 0 second in order to
            # populate the new message in the queue
            sleep(0)


class _HTTPArgumentParser(object):
    """Argument parser for HTTP requests

    Object for parsing HTTP requests into Python objects. It is based
    on ExtendedArgumentParser class and implements some of its methods.

    """

    def __init__(self):
        # Initialize the ArgumentParser object
        self._parser = ExtendedArgumentParser(usage='',
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

        # Append an argument to the current one
        def append(arg_strings, value, option_string=None):
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
            elif isinstance(value, list):
                if option_string is not None:
                    arg_strings.append(option_string)
                for v in value:
                    if isinstance(v, str):
                        arg_strings.append(v)
                    else:
                        logger.warning("unsupported argument value type %r "
                                       "in %s for option string %s", v, value,
                                       option_string)
            else:
                logger.warning("unsupported argument type %r for option "
                               "string %s", value, option_string)

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

    def dequeue_callbacks(self, *args, **kwargs):
        return self._parser.dequeue_callbacks(*args, **kwargs)

    def _error(self, message):
        # TODO: Raise a proper exception
        raise MoulinetteError(1, message)


class _ActionsMapPlugin(object):
    """Actions map Bottle Plugin

    Process relevant action for the request using the actions map and
    manage authentication.

    Keyword arguments:
        - actionsmap -- An ActionsMap instance
        - use_websocket -- If true, install a WebSocket on /messages in order
            to serve messages coming from the 'display' signal

    """
    name = 'actionsmap'
    api = 2

    def __init__(self, actionsmap, use_websocket, log_queues={}):
        # Connect signals to handlers
        msignals.set_handler('authenticate', self._do_authenticate)
        if use_websocket:
            msignals.set_handler('display', self._do_display)

        self.actionsmap = actionsmap
        self.use_websocket = use_websocket
        self.log_queues = log_queues
        # TODO: Save and load secrets?
        self.secrets = {}

    def setup(self, app):
        """Setup plugin on the application

        Add routes according to the actions map to the application.

        Keyword arguments:
            - app -- The application instance

        """
        # Login wrapper
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

        # Logout wrapper
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

        # Append messages route
        if self.use_websocket:
            app.route('/messages', name='messages',
                      callback=self.messages, skip=['actionsmap'])

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
        def _format(value):
            if isinstance(value, list) and len(value) == 1:
                return value[0]
            return value

        def wrapper(*args, **kwargs):
            params = kwargs
            # Format boolean params
            for a in args:
                params[a] = True
            # Append other request params
            for k, v in request.params.dict.items():
                v = _format(v)
                try:
                    curr_v = params[k]
                except KeyError:
                    params[k] = v
                else:
                    # Append param value to the list
                    if not isinstance(curr_v, list):
                        curr_v = [curr_v]
                    if isinstance(v, list):
                        for i in v:
                            curr_v.append(i)
                    else:
                        curr_v.append(v)
                    params[k] = curr_v

            # Process the action
            return callback((request.method, context.rule), params)
        return wrapper

    # Routes callbacks

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
                try:
                    self.logout(profile)
                except:
                    pass
            raise error_to_response(e)
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

    def messages(self):
        """Listen to the messages WebSocket stream

        Retrieve the WebSocket stream and send to it each messages displayed by
        the core.MoulinetteSignals.display signal. They are JSON encoded as a
        dict { style: message }.

        """
        s_id = request.get_cookie('session.id')
        try:
            queue = self.log_queues[s_id]
        except KeyError:
            # Create a new queue for the session
            queue = Queue()
            self.log_queues[s_id] = queue

        wsock = request.environ.get('wsgi.websocket')
        if not wsock:
            raise HTTPErrorResponse(m18n.g('websocket_request_expected'))

        while True:
            item = queue.get()
            try:
                # Retrieve the message
                style, message = item
            except TypeError:
                if item == StopIteration:
                    # Delete the current queue and break
                    del self.log_queues[s_id]
                    break
                logger.exception("invalid item in the messages queue: %r", item)
            else:
                try:
                    # Send the message
                    wsock.send(json_encode({style: message}))
                except WebSocketError:
                    break
            sleep(0)

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
            ret = self.actionsmap.process(arguments, timeout=30, route=_route)
        except MoulinetteError as e:
            raise error_to_response(e)
        else:
            return format_for_response(ret)
        finally:
            # Close opened WebSocket by putting StopIteration in the queue
            try:
                queue = self.log_queues[request.get_cookie('session.id')]
            except KeyError:
                pass
            else:
                queue.put(StopIteration)

    # Signals handlers

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
                msg = m18n.g('authentication_profile_required',
                             profile=authenticator.name)
            raise HTTPUnauthorizedResponse(msg)
        else:
            return authenticator(token=(s_id, s_hash))

    def _do_display(self, message, style):
        """Display a message

        Handle the core.MoulinetteSignals.display signal.

        """
        s_id = request.get_cookie('session.id')
        try:
            queue = self.log_queues[s_id]
        except KeyError:
            return

        # Put the message as a 2-tuple in the queue
        queue.put_nowait((style, message))

        # Put the current greenlet to sleep for 0 second in order to
        # populate the new message in the queue
        sleep(0)


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


class HTTPForbiddenResponse(HTTPResponse):

    def __init__(self, output=''):
        super(HTTPForbiddenResponse, self).__init__(output, 403)


class HTTPErrorResponse(HTTPResponse):

    def __init__(self, output=''):
        super(HTTPErrorResponse, self).__init__(output, 500)


def error_to_response(error):
    """Convert a MoulinetteError to relevant HTTP response."""
    if error.errno == errno.EPERM:
        return HTTPForbiddenResponse(error.strerror)
    elif error.errno == errno.EACCES:
        return HTTPUnauthorizedResponse(error.strerror)
    # Client-side error
    elif error.errno in [errno.ENOENT, errno.ESRCH, errno.ENXIO, errno.EEXIST,
            errno.ENODEV, errno.EINVAL, errno.ENOPKG, errno.EDESTADDRREQ]:
        return HTTPBadRequestResponse(error.strerror)
    # Server-side error
    elif error.errno in [errno.EIO, errno.EBUSY, errno.ENODATA, errno.EINTR,
            errno.ENETUNREACH]:
        return HTTPErrorResponse(error.strerror)
    else:
        logger.debug('unknown relevant response for error [%s] %s',
                     error.errno, error.strerror)
        return HTTPErrorResponse(error.strerror)


def format_for_response(content):
    """Format the resulted content of a request for the HTTP response."""
    if request.method == 'POST':
        response.status = 201  # Created
    elif request.method == 'GET':
        response.status = 200  # Ok
    else:
        # Return empty string if no content
        if content is None or len(content) == 0:
            response.status = 204  # No Content
            return ''
        response.status = 200

    # Return JSON-style response
    response.content_type = 'application/json'
    return json_encode(content, cls=JSONExtendedEncoder)


# API Classes Implementation -------------------------------------------

class ActionsMapParser(BaseActionsMapParser):
    """Actions map's Parser for the API

    Provide actions map parsing methods for a CLI usage. The parser for
    the arguments is represented by a ExtendedArgumentParser object.

    """

    def __init__(self, parent=None, **kwargs):
        super(ActionsMapParser, self).__init__(parent)

        self._parsers = {}  # dict({(method, path): _HTTPArgumentParser})
        self._route_re = re.compile(r'(GET|POST|PUT|DELETE) (/\S+)')

    @property
    def routes(self):
        """Get current routes"""
        return self._parsers.keys()

    # Implement virtual properties

    interface = 'api'

    # Implement virtual methods

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
        keys = []
        try:
            # Extract action route
            keys.append(self._extract_route(api))
        except TypeError:
            if isinstance(api, list):
                # Iterate over action routes
                for r in api:
                    try:
                        keys.append(self._extract_route(r))
                    except ValueError as e:
                        logger.warning("cannot add api route '%s' for "
                                       "action %s: %s", r, tid, e)
                        continue
                if len(keys) == 0:
                    raise ValueError("no valid api route found")
            else:
                raise AttributeError("no api route for action '%s'" % name)

        # Create and append parser
        parser = _HTTPArgumentParser()
        for k in keys:
            self._parsers[k] = (tid, parser)

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
            logger.error("no argument parser found for route '%s'", route)
            raise MoulinetteError(errno.EINVAL, m18n.g('error_see_log'))
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
                raise MoulinetteError(errno.EACCES, m18n.g('authentication_required_long'))
            if self.get_conf(tid, 'argument_auth') and \
               self.get_conf(tid, 'authenticate') == 'all':
                ret.auth = auth

        # TODO: Catch errors?
        ret = parser.parse_args(args, ret)
        parser.dequeue_callbacks(ret)
        return ret

    # Private methods

    def _extract_route(self, string):
        """Extract action route from a string

        Extract, validate and return an action route as a 2-tuple (method, path)
        from a string.

        Keyword arguments:
            - string -- An action route string (e.g. 'GET /')

        """
        m = self._route_re.match(string)
        if not m:
            raise ValueError("invalid route string '%s'" % string)

        key = (m.group(1), m.group(2))
        if key in self.routes:
            raise ValueError("route '%s' already defined" % string)

        return key


class Interface(BaseInterface):
    """Application Programming Interface for the moulinette

    Initialize a HTTP server which serves the API connected to a given
    actions map.

    Keyword arguments:
        - actionsmap -- The ActionsMap instance to connect to
        - routes -- A dict of additional routes to add in the form of
            {(method, path): callback}
        - use_websocket -- Serve via WSGI to handle asynchronous responses
        - log_queues -- A LogQueues object or None to retrieve it from
            registered logging handlers

    """

    def __init__(self, actionsmap, routes={}, use_websocket=True,
                 log_queues=None):
        self.use_websocket = use_websocket

        # Attempt to retrieve log queues from an APIQueueHandler
        if log_queues is None:
            handler = log.getHandlersByClass(APIQueueHandler, limit=1)
            if handler:
                log_queues = handler.queues

        # TODO: Return OK to 'OPTIONS' xhr requests (l173)
        app = Bottle(autojson=True)

        # Attempt to retrieve and set locale
        def api18n(callback):
            try:
                locale = request.params.pop('locale')
            except KeyError:
                locale = m18n.default_locale
            m18n.set_locale(locale)
            return callback

        # Install plugins
        app.install(api18n)
        app.install(_ActionsMapPlugin(actionsmap, use_websocket, log_queues))

        # Append default routes
#        app.route(['/api', '/api/<category:re:[a-z]+>'], method='GET',
#                  callback=self.doc, skip=['actionsmap'])

        # Append additional routes
        # TODO: Add optional authentication to those routes?
        for (m, p), c in routes.items():
            app.route(p, method=m, callback=c, skip=['actionsmap'])

        self._app = app

    def run(self, host='localhost', port=80):
        """Run the moulinette

        Start a server instance on the given port to serve moulinette
        actions.

        Keyword arguments:
            - host -- Server address to bind to
            - port -- Server port to bind to

        """
        logger.debug("starting the server instance in %s:%d with websocket=%s",
                     host, port, self.use_websocket)

        try:
            if self.use_websocket:
                from gevent.pywsgi import WSGIServer
                from geventwebsocket.handler import WebSocketHandler

                server = WSGIServer((host, port), self._app,
                                    handler_class=WebSocketHandler)
                server.serve_forever()
            else:
                run(self._app, host=host, port=port)
        except IOError as e:
            logger.exception("unable to start the server instance on %s:%d",
                             host, port)
            if e.args[0] == errno.EADDRINUSE:
                raise MoulinetteError(errno.EADDRINUSE,
                                      m18n.g('server_already_running'))
            raise MoulinetteError(errno.EIO, m18n.g('error_see_log'))

    # Routes handlers

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
