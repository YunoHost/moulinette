# -*- coding: utf-8 -*-

import re
import errno
import logging
import argparse
from json import dumps as json_encode

from gevent import sleep
from gevent.queue import Queue
from geventwebsocket import WebSocketError

from bottle import request, response, Bottle, HTTPResponse
from bottle import abort

from moulinette import msignals, m18n, env
from moulinette.actionsmap import ActionsMap
from moulinette.core import MoulinetteError
from moulinette.interfaces import (
    BaseActionsMapParser,
    BaseInterface,
    ExtendedArgumentParser,
)
from moulinette.utils import log
from moulinette.utils.serialize import JSONExtendedEncoder
from moulinette.utils.text import random_ascii

logger = log.getLogger("moulinette.interface.api")


# API helpers ----------------------------------------------------------

CSRF_TYPES = set(
    ["text/plain", "application/x-www-form-urlencoded", "multipart/form-data"]
)


def is_csrf():
    """Checks is this is a CSRF request."""

    if request.method != "POST":
        return False
    if request.content_type is None:
        return True
    content_type = request.content_type.lower().split(";")[0]
    if content_type not in CSRF_TYPES:
        return False

    return request.headers.get("X-Requested-With") is None


# Protection against CSRF
def filter_csrf(callback):
    def wrapper(*args, **kwargs):
        if is_csrf():
            abort(403, "CSRF protection")
        else:
            return callback(*args, **kwargs)

    return wrapper


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
        sid = request.get_cookie("session.id")
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
        self._parser = ExtendedArgumentParser(
            usage="", prefix_chars="@", add_help=False
        )
        self._parser.error = self._error

        self._positional = []  # list(arg_name)
        self._optional = {}  # dict({arg_name: option_strings})

    def set_defaults(self, **kwargs):
        return self._parser.set_defaults(**kwargs)

    def get_default(self, dest):
        return self._parser.get_default(dest)

    def add_arguments(
        self, arguments, extraparser, format_arg_names=None, validate_extra=True
    ):
        for argument_name, argument_options in arguments.items():
            # will adapt arguments name for cli or api context
            names = format_arg_names(
                str(argument_name), argument_options.pop("full", None)
            )

            if "type" in argument_options:
                argument_options["type"] = eval(argument_options["type"])

            if "extra" in argument_options:
                extra = argument_options.pop("extra")
                argument_dest = self.add_argument(*names, **argument_options).dest
                extraparser.add_argument(
                    self.get_default("_tid"), argument_dest, extra, validate_extra
                )
                continue

            self.add_argument(*names, **argument_options)

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
                        logger.warning(
                            "unsupported argument value type %r "
                            "in %s for option string %s",
                            v,
                            value,
                            option_string,
                        )
            else:
                logger.warning(
                    "unsupported argument type %r for option " "string %s",
                    value,
                    option_string,
                )

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
        raise MoulinetteError(message, raw_msg=True)


class _ActionsMapPlugin(object):

    """Actions map Bottle Plugin

    Process relevant action for the request using the actions map and
    manage authentication.

    Keyword arguments:
        - actionsmap -- An ActionsMap instance

    """

    name = "actionsmap"
    api = 2

    def __init__(self, actionsmap, log_queues={}):
        # Connect signals to handlers
        msignals.set_handler("authenticate", self._do_authenticate)
        msignals.set_handler("display", self._do_display)

        self.actionsmap = actionsmap
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
                    kwargs["password"] = request.POST["password"]
                except KeyError:
                    raise HTTPBadRequestResponse("Missing password parameter")

                kwargs["profile"] = request.POST.get("profile", "default")
                return callback(**kwargs)

            return wrapper

        # Logout wrapper
        def _logout(callback):
            def wrapper():
                kwargs = {}
                kwargs["profile"] = request.POST.get("profile", "default")
                return callback(**kwargs)

            return wrapper

        # Append authentication routes
        app.route(
            "/login",
            name="login",
            method="POST",
            callback=self.login,
            skip=["actionsmap"],
            apply=_login,
        )
        app.route(
            "/logout",
            name="logout",
            method="GET",
            callback=self.logout,
            skip=["actionsmap"],
            apply=_logout,
        )

        # Append messages route
        app.route(
            "/messages",
            name="messages",
            callback=self.messages,
            skip=["actionsmap"],
        )

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
                if k not in params.keys():
                    params[k] = v
                else:
                    curr_v = params[k]
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

    def login(self, password, profile):
        """Log in to an authenticator profile

        Attempt to authenticate to a given authenticator profile and
        register it with the current session - a new one will be created
        if needed.

        Keyword arguments:
            - password -- A clear text password
            - profile -- The authenticator profile name to log in

        """
        # Retrieve session values
        try:
            s_id = request.get_cookie("session.id") or random_ascii()
        except:
            # Super rare case where there are super weird cookie / cache issue
            # Previous line throws a CookieError that creates a 500 error ...
            # So let's catch it and just use a fresh ID then...
            s_id = random_ascii()

        try:
            s_secret = self.secrets[s_id]
        except KeyError:
            s_tokens = {}
        else:
            try:
                s_tokens = request.get_cookie("session.tokens", secret=s_secret) or {}
            except:
                # Same as for session.id a few lines before
                s_tokens = {}
        s_new_token = random_ascii()

        try:
            # Attempt to authenticate
            authenticator = self.actionsmap.get_authenticator_for_profile(profile)
            authenticator(password, token=(s_id, s_new_token))
        except MoulinetteError as e:
            if len(s_tokens) > 0:
                try:
                    self.logout(profile)
                except:
                    pass
            raise HTTPUnauthorizedResponse(e.strerror)
        else:
            # Update dicts with new values
            s_tokens[profile] = s_new_token
            self.secrets[s_id] = s_secret = random_ascii()

            response.set_cookie("session.id", s_id, secure=True)
            response.set_cookie(
                "session.tokens", s_tokens, secure=True, secret=s_secret
            )
            return m18n.g("logged_in")

    def logout(self, profile):
        """Log out from an authenticator profile

        Attempt to unregister a given profile - or all by default - from
        the current session.

        Keyword arguments:
            - profile -- The authenticator profile name to log out

        """
        s_id = request.get_cookie("session.id")
        # We check that there's a (signed) session.hash available
        # for additional security ?
        # (An attacker could not craft such signed hashed ? (FIXME : need to make sure of this))
        try:
            s_secret = self.secrets[s_id]
        except KeyError:
            s_secret = {}
        if profile not in request.get_cookie(
            "session.tokens", secret=s_secret, default={}
        ):
            raise HTTPUnauthorizedResponse(m18n.g("not_logged_in"))
        else:
            del self.secrets[s_id]
            authenticator = self.actionsmap.get_authenticator_for_profile(profile)
            authenticator._clean_session(s_id)
            # TODO: Clean the session for profile only
            # Delete cookie and clean the session
            response.set_cookie("session.tokens", "", max_age=-1)
        return m18n.g("logged_out")

    def messages(self):
        """Listen to the messages WebSocket stream

        Retrieve the WebSocket stream and send to it each messages displayed by
        the core.MoulinetteSignals.display signal. They are JSON encoded as a
        dict { style: message }.

        """
        s_id = request.get_cookie("session.id")
        try:
            queue = self.log_queues[s_id]
        except KeyError:
            # Create a new queue for the session
            queue = Queue()
            self.log_queues[s_id] = queue

        wsock = request.environ.get("wsgi.websocket")
        if not wsock:
            raise HTTPErrorResponse(m18n.g("websocket_request_expected"))

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
            raise HTTPBadRequestResponse(e)
        except Exception as e:
            if isinstance(e, HTTPResponse):
                raise e
            import traceback

            tb = traceback.format_exc()
            logs = {"route": _route, "arguments": arguments, "traceback": tb}
            return HTTPErrorResponse(json_encode(logs))
        else:
            return format_for_response(ret)
        finally:
            # Close opened WebSocket by putting StopIteration in the queue
            try:
                queue = self.log_queues[request.get_cookie("session.id")]
            except KeyError:
                pass
            else:
                queue.put(StopIteration)

    # Signals handlers

    def _do_authenticate(self, authenticator):
        """Process the authentication

        Handle the core.MoulinetteSignals.authenticate signal.

        """
        s_id = request.get_cookie("session.id")
        try:
            s_secret = self.secrets[s_id]
            s_token = request.get_cookie("session.tokens", secret=s_secret, default={})[
                authenticator.name
            ]
        except KeyError:
            msg = m18n.g("authentication_required")
            raise HTTPUnauthorizedResponse(msg)
        else:
            return authenticator(token=(s_id, s_token))

    def _do_display(self, message, style):
        """Display a message

        Handle the core.MoulinetteSignals.display signal.

        """
        s_id = request.get_cookie("session.id")
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
    def __init__(self, output=""):
        super(HTTPOKResponse, self).__init__(output, 200)


class HTTPBadRequestResponse(HTTPResponse):
    def __init__(self, error=""):

        if isinstance(error, MoulinetteError):
            content = error.content()
            if isinstance(content, dict):
                super(HTTPBadRequestResponse, self).__init__(
                    json_encode(content),
                    400,
                    headers={"Content-type": "application/json"},
                )
            else:
                super(HTTPBadRequestResponse, self).__init__(content, 400)
        else:
            super(HTTPBadRequestResponse, self).__init__(error, 400)


class HTTPUnauthorizedResponse(HTTPResponse):
    def __init__(self, output=""):
        super(HTTPUnauthorizedResponse, self).__init__(output, 401)


class HTTPErrorResponse(HTTPResponse):
    def __init__(self, output=""):
        super(HTTPErrorResponse, self).__init__(output, 500)


def format_for_response(content):
    """Format the resulted content of a request for the HTTP response."""
    if request.method == "POST":
        response.status = 201  # Created
    elif request.method == "GET":
        response.status = 200  # Ok
    else:
        # Return empty string if no content
        if content is None or len(content) == 0:
            response.status = 204  # No Content
            return ""
        response.status = 200

    if isinstance(content, HTTPResponse):
        return content

    # Return JSON-style response
    response.content_type = "application/json"
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
        self._route_re = re.compile(r"(GET|POST|PUT|DELETE) (/\S+)")

    @property
    def routes(self):
        """Get current routes"""
        return self._parsers.keys()

    # Implement virtual properties

    interface = "api"

    # Implement virtual methods

    @staticmethod
    def format_arg_names(name, full):
        if name[0] != "-":
            return [name]
        if full:
            return [full.replace("--", "@", 1)]
        if name.startswith("--"):
            return [name.replace("--", "@", 1)]
        return [name.replace("-", "@", 1)]

    def add_category_parser(self, name, **kwargs):
        return self

    def add_subcategory_parser(self, name, **kwargs):
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
                        logger.warning(
                            "cannot add api route '%s' for " "action %s: %s", r, tid, e
                        )
                        continue
                if len(keys) == 0:
                    raise ValueError("no valid api route found")
            else:
                return None

        # Create and append parser
        parser = _HTTPArgumentParser()
        for k in keys:
            self._parsers[k] = (tid, parser)

        # Return the created parser
        return parser

    def auth_required(self, args, **kwargs):
        try:
            # Retrieve the tid for the route
            tid, _ = self._parsers[kwargs.get("route")]
        except KeyError as e:
            error_message = "no argument parser found for route '%s': %s" % (
                kwargs.get("route"),
                e,
            )
            logger.error(error_message)
            raise MoulinetteError(error_message, raw_msg=True)

        if self.get_conf(tid, "authenticate"):
            authenticator = self.get_conf(tid, "authenticator")

            # If several authenticator, use the default one
            if isinstance(authenticator, dict):
                if "default" in authenticator:
                    authenticator = "default"
                else:
                    # TODO which one should we use?
                    pass
            return authenticator
        else:
            return False

    def parse_args(self, args, route, **kwargs):
        """Parse arguments

        Keyword arguments:
            - route -- The action route as a 2-tuple (method, path)

        """
        try:
            # Retrieve the parser for the route
            _, parser = self._parsers[route]
        except KeyError as e:
            error_message = "no argument parser found for route '%s': %s" % (route, e)
            logger.error(error_message)
            raise MoulinetteError(error_message, raw_msg=True)
        ret = argparse.Namespace()

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
        - routes -- A dict of additional routes to add in the form of
            {(method, path): callback}
        - log_queues -- A LogQueues object or None to retrieve it from
            registered logging handlers

    """

    def __init__(self, routes={}, log_queues=None):

        actionsmap = ActionsMap(ActionsMapParser())

        # Attempt to retrieve log queues from an APIQueueHandler
        if log_queues is None:
            handler = log.getHandlersByClass(APIQueueHandler, limit=1)
            if handler:
                log_queues = handler.queues

        # TODO: Return OK to 'OPTIONS' xhr requests (l173)
        app = Bottle(autojson=True)

        # Wrapper which sets proper header
        def apiheader(callback):
            def wrapper(*args, **kwargs):
                response.set_header("Access-Control-Allow-Origin", "*")
                return callback(*args, **kwargs)

            return wrapper

        # Attempt to retrieve and set locale
        def api18n(callback):
            def wrapper(*args, **kwargs):
                try:
                    locale = request.params.pop("locale")
                except KeyError:
                    locale = m18n.default_locale
                m18n.set_locale(locale)
                return callback(*args, **kwargs)

            return wrapper

        # Install plugins
        app.install(filter_csrf)
        app.install(apiheader)
        app.install(api18n)
        app.install(_ActionsMapPlugin(actionsmap, log_queues))

        # Append default routes
        #        app.route(['/api', '/api/<category:re:[a-z]+>'], method='GET',
        #                  callback=self.doc, skip=['actionsmap'])

        # Append additional routes
        # TODO: Add optional authentication to those routes?
        for (m, p), c in routes.items():
            app.route(p, method=m, callback=c, skip=["actionsmap"])

        self._app = app

    def run(self, host="localhost", port=80):
        """Run the moulinette

        Start a server instance on the given port to serve moulinette
        actions.

        Keyword arguments:
            - host -- Server address to bind to
            - port -- Server port to bind to

        """
        logger.debug(
            "starting the server instance in %s:%d",
            host,
            port,
        )

        try:
            from gevent.pywsgi import WSGIServer
            from geventwebsocket.handler import WebSocketHandler

            server = WSGIServer((host, port), self._app, handler_class=WebSocketHandler)
            server.serve_forever()
        except IOError as e:
            error_message = "unable to start the server instance on %s:%d: %s" % (
                host,
                port,
                e,
            )
            logger.exception(error_message)
            if e.args[0] == errno.EADDRINUSE:
                raise MoulinetteError("server_already_running")
            raise MoulinetteError(error_message)

    # Routes handlers

    def doc(self, category=None):
        """
        Get API documentation for a category (all by default)

        Keyword argument:
            category -- Name of the category

        """
        DATA_DIR = env()["DATA_DIR"]

        if category is None:
            with open("%s/../doc/resources.json" % DATA_DIR) as f:
                return f.read()

        try:
            with open("%s/../doc/%s.json" % (DATA_DIR, category)) as f:
                return f.read()
        except IOError:
            return None
