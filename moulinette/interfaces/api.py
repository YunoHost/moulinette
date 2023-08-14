# -*- coding: utf-8 -*-

import re
import errno
import logging
import argparse

from json import dumps as json_encode
from tempfile import mkdtemp
from shutil import rmtree

from gevent import sleep
from gevent.queue import Queue
from geventwebsocket import WebSocketError

from bottle import request, response, Bottle, HTTPResponse, FileUpload
from bottle import abort

from moulinette import m18n, Moulinette
from moulinette.actionsmap import ActionsMap
from moulinette.core import (
    MoulinetteError,
    MoulinetteValidationError,
    MoulinetteAuthenticationError,
)
from moulinette.interfaces import (
    BaseActionsMapParser,
    ExtendedArgumentParser,
    JSONExtendedEncoder,
)
from moulinette.utils import log

logger = log.getLogger("moulinette.interface.api")


# API helpers ----------------------------------------------------------
# We define a global variable to manage in a dirty way the upload...
UPLOAD_DIR = None

CSRF_TYPES = {"text/plain", "application/x-www-form-urlencoded", "multipart/form-data"}


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

    """Map of session ids to queue."""

    pass


class APIQueueHandler(logging.Handler):

    """
    A handler class which store logging records into a queue, to be used
    and retrieved from the API.
    """

    def __init__(self):
        logging.Handler.__init__(self)
        self.queues = LogQueues()
        # actionsmap is actually set during the interface's init ...
        self.actionsmap = None

    def emit(self, record):
        # Prevent triggering this function while moulinette
        # is being initialized with --debug
        if not self.actionsmap or len(request.cookies) == 0:
            return

        profile = request.params.get("profile", self.actionsmap.default_authentication)
        authenticator = self.actionsmap.get_authenticator(profile)

        s_id = authenticator.get_session_cookie(raise_if_no_session_exists=False)["id"]
        try:
            queue = self.queues[s_id]
        except KeyError:
            # Session is not initialized, abandon.
            return
        else:
            # Put the message as a 2-tuple in the queue
            queue.put_nowait((record.levelname.lower(), record.getMessage()))
            # Put the current greenlet to sleep for 0 second in order to
            # populate the new message in the queue
            sleep(0)


class _HTTPArgumentParser:

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
        self._upload_dir = None

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
            self._positional.append(action)
        else:
            self._optional[action.dest] = action

        return action

    def parse_args(self, args={}, namespace=None):
        arg_strings = []

        # Append an argument to the current one
        def append(arg_strings, value, action):
            option_string = None
            if len(action.option_strings) > 0:
                option_string = action.option_strings[0]

            if isinstance(value, bool) or isinstance(action.const, bool):
                # Append the option string only
                if option_string is not None and value != 0:
                    arg_strings.append(option_string)
            elif isinstance(value, FileUpload) and (
                isinstance(action.type, argparse.FileType) or action.type == open
            ):
                # Upload the file in a temp directory
                global UPLOAD_DIR
                if UPLOAD_DIR is None:
                    UPLOAD_DIR = mkdtemp(prefix="moulinette_upload_")
                value.save(UPLOAD_DIR)
                if option_string is not None:
                    arg_strings.append(option_string)
                arg_strings.append(UPLOAD_DIR + "/" + value.filename)
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
        for action in self._positional:
            if action.dest in args:
                arg_strings = append(arg_strings, args[action.dest], action)

        # Iterate over optional arguments
        for dest, action in self._optional.items():
            if dest in args:
                arg_strings = append(arg_strings, args[dest], action)

        return self._parser.parse_args(arg_strings, namespace)

    def _error(self, message):
        raise MoulinetteValidationError(message, raw_msg=True)


class _ActionsMapPlugin:
    """Actions map Bottle Plugin

    Process relevant action for the request using the actions map and
    manage authentication.

    Keyword arguments:
        - actionsmap -- An ActionsMap instance

    """

    name = "actionsmap"
    api = 2

    def __init__(self, actionsmap, log_queues={}):
        self.actionsmap = actionsmap
        self.log_queues = log_queues

    def setup(self, app):
        """Setup plugin on the application

        Add routes according to the actions map to the application.

        Keyword arguments:
            - app -- The application instance

        """

        # Append authentication routes
        app.route(
            "/login",
            name="login",
            method="POST",
            callback=self.login,
            skip=[filter_csrf, "actionsmap"],
        )
        app.route(
            "/logout",
            name="logout",
            method="GET",
            callback=self.logout,
            # No need to bypass CSRF here because filter allows GET requests
            skip=["actionsmap"],
        )

        # Append messages route
        app.route(
            "/messages",
            name="messages",
            callback=self.messages,
            skip=["actionsmap"],
        )

        # Append routes from the actions map
        for m, p in self.actionsmap.parser.routes:
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
            if request.get_header("Content-Type") == "application/json":
                return callback((request.method, context.rule), request.json)

            params = kwargs
            # Format boolean params
            for a in args:
                params[a] = True

            # Append other request params
            req_params = list(request.params.dict.items())
            # TODO test special chars in filename
            req_params += list(request.files.dict.items())
            for k, v in req_params:
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

    def login(self):
        """Log in to an authenticator

        Attempt to authenticate to the default authenticator and
        register it with the current session - a new one will be created
        if needed.

        """

        if request.get_header("Content-Type") == "application/json":
            if "credentials" not in request.json:
                raise HTTPResponse("Missing credentials parameter", 400)
            credentials = request.json["credentials"]
            profile = request.json.get("profile", self.actionsmap.default_authentication)
        else:
            if "credentials" in request.params:
                credentials = request.params["credentials"]
            elif "username" in request.params and "password" in request.params:
                credentials = request.params["username"] + ":" + request.params["password"]
            else:
                raise HTTPResponse("Missing credentials parameter", 400)

            profile = request.params.get("profile", self.actionsmap.default_authentication)

        authenticator = self.actionsmap.get_authenticator(profile)

        try:
            auth_infos = authenticator.authenticate_credentials(credentials)
        except MoulinetteError as e:
            try:
                self.logout()
            except Exception:
                pass
            raise HTTPResponse(e.strerror, 401)
        else:
            authenticator.set_session_cookie(auth_infos)
            return m18n.g("logged_in")

    # This is called before each time a route is going to be processed
    def authenticate(self, authenticator):
        try:
            session_infos = authenticator.get_session_cookie()
        except Exception:
            authenticator.delete_session_cookie()
            msg = m18n.g("authentication_required")
            raise HTTPResponse(msg, 401)

        return session_infos

    def logout(self):
        profile = request.params.get("profile", self.actionsmap.default_authentication)
        authenticator = self.actionsmap.get_authenticator(profile)

        try:
            authenticator.get_session_cookie()
        except Exception:
            raise HTTPResponse(m18n.g("not_logged_in"), 401)
        else:
            # Delete cookie and clean the session
            authenticator.delete_session_cookie()
            return m18n.g("logged_out")

    def messages(self):
        """Listen to the messages WebSocket stream

        Retrieve the WebSocket stream and send to it each messages displayed by
        the display method. They are JSON encoded as a dict { style: message }.
        """

        profile = request.params.get("profile", self.actionsmap.default_authentication)
        authenticator = self.actionsmap.get_authenticator(profile)

        s_id = authenticator.get_session_cookie()["id"]
        try:
            queue = self.log_queues[s_id]
        except KeyError:
            # Create a new queue for the session
            queue = Queue()
            self.log_queues[s_id] = queue

        wsock = request.environ.get("wsgi.websocket")
        if not wsock:
            raise HTTPResponse(m18n.g("websocket_request_expected"), 500)

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
            raise moulinette_error_to_http_response(e)
        except Exception as e:
            if isinstance(e, HTTPResponse):
                raise e
            import traceback

            tb = traceback.format_exc()
            logs = {"route": _route, "arguments": arguments, "traceback": tb}
            return HTTPResponse(json_encode(logs), 500)
        else:
            return format_for_response(ret)
        finally:
            # Clean upload directory
            # FIXME do that in a better way
            global UPLOAD_DIR
            if UPLOAD_DIR is not None:
                rmtree(UPLOAD_DIR, True)
                UPLOAD_DIR = None

            # Close opened WebSocket by putting StopIteration in the queue
            profile = request.params.get(
                "profile", self.actionsmap.default_authentication
            )
            authenticator = self.actionsmap.get_authenticator(profile)
            try:
                s_id = authenticator.get_session_cookie()["id"]
                queue = self.log_queues[s_id]
            except MoulinetteAuthenticationError:
                pass
            except KeyError:
                pass
            else:
                queue.put(StopIteration)

    def display(self, message, style="info"):
        profile = request.params.get("profile", self.actionsmap.default_authentication)
        authenticator = self.actionsmap.get_authenticator(profile)
        s_id = authenticator.get_session_cookie(raise_if_no_session_exists=False)["id"]

        try:
            queue = self.log_queues[s_id]
        except KeyError:
            return

        # Put the message as a 2-tuple in the queue
        queue.put_nowait((style, message))

        # Put the current greenlet to sleep for 0 second in order to
        # populate the new message in the queue
        sleep(0)

    def prompt(self, *args, **kwargs):
        raise NotImplementedError("Prompt is not implemented for this interface")


# HTTP Responses -------------------------------------------------------


def moulinette_error_to_http_response(error):
    content = error.content()
    if isinstance(content, dict):
        return HTTPResponse(
            json_encode(content),
            error.http_code,
            headers={"Content-type": "application/json"},
        )
    else:
        return HTTPResponse(content, error.http_code)


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

    def auth_method(self, _, route):
        try:
            # Retrieve the tid for the route
            _, parser = self._parsers[route]
        except KeyError as e:
            error_message = "no argument parser found for route '{}': {}".format(
                route, e
            )
            logger.error(error_message)
            raise MoulinetteValidationError(error_message, raw_msg=True)

        return parser.authentication

    def want_to_take_lock(self, _, route):
        _, parser = self._parsers[route]

        return getattr(parser, "want_to_take_lock", True)

    def parse_args(self, args, **kwargs):
        """Parse arguments

        Keyword arguments:
            - route -- The action route as a 2-tuple (method, path)

        """
        route = kwargs["route"]
        try:
            # Retrieve the parser for the route
            _, parser = self._parsers[route]
        except KeyError as e:
            error_message = "no argument parser found for route '{}': {}".format(
                route, e
            )
            logger.error(error_message)
            raise MoulinetteValidationError(error_message, raw_msg=True)
        ret = argparse.Namespace()

        # TODO: Catch errors?
        ret = parser.parse_args(args, ret)
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


class Interface:

    """Application Programming Interface for the moulinette

    Initialize a HTTP server which serves the API connected to a given
    actions map.

    Keyword arguments:
        - routes -- A dict of additional routes to add in the form of
            {(method, path): callback}
        - log_queues -- A LogQueues object or None to retrieve it from
            registered logging handlers

    """

    type = "api"

    def __init__(self, routes={}, actionsmap=None, allowed_cors_origins=[]):
        actionsmap = ActionsMap(actionsmap, ActionsMapParser())

        self.allowed_cors_origins = allowed_cors_origins

        # Attempt to retrieve log queues from an APIQueueHandler
        handler = log.getHandlersByClass(APIQueueHandler, limit=1)
        if handler:
            log_queues = handler.queues
            handler.actionsmap = actionsmap

        # TODO: Return OK to 'OPTIONS' xhr requests (l173)
        app = Bottle(autojson=True)

        def cors(callback):
            def wrapper(*args, **kwargs):
                r = callback(*args, **kwargs)
                origin = request.headers.environ.get("HTTP_ORIGIN", "")
                if origin and origin in self.allowed_cors_origins:
                    resp = r if isinstance(r, HTTPResponse) else response
                    resp.headers['Access-Control-Allow-Origin'] = origin
                    resp.headers['Access-Control-Allow-Methods'] = 'GET, HEAD, POST, PUT, OPTIONS, DELETE'
                    resp.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token'
                    resp.headers['Access-Control-Allow-Credentials'] = 'true'

                return r

            return wrapper

        # Attempt to retrieve and set locale
        def api18n(callback):
            def wrapper(*args, **kwargs):
                try:
                    locale = request.params.pop("locale")
                except (KeyError, ValueError):
                    locale = m18n.default_locale
                m18n.set_locale(locale)
                return callback(*args, **kwargs)

            return wrapper

        # Install plugins
        app.install(filter_csrf)
        app.install(cors)
        app.install(api18n)
        actionsmapplugin = _ActionsMapPlugin(actionsmap, log_queues)
        app.install(actionsmapplugin)

        self.authenticate = actionsmapplugin.authenticate
        self.display = actionsmapplugin.display
        self.prompt = actionsmapplugin.prompt

        def handle_options():
            return HTTPResponse("", 204)

        app.route('/<:re:.*>', method="OPTIONS",
                  callback=handle_options, skip=["actionsmap"])

        # Append additional routes
        # TODO: Add optional authentication to those routes?
        for (m, p), c in routes.items():
            app.route(p, method=m, callback=c, skip=["actionsmap"])

        self._app = app

        Moulinette._interface = self

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
