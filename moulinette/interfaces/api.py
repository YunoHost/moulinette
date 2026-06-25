#!/usr/bin/env python3
#
# Copyright (c) 2024 YunoHost Contributors
#
# This file is part of YunoHost (see https://yunohost.org)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#

import os
import sys
import re
import errno
import logging
import argparse

from json import dumps as json_encode
from tempfile import mkdtemp
from shutil import rmtree
from pathlib import Path

from bottle import redirect, request, response, Bottle, HTTPResponse, FileUpload
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

logger = logging.getLogger("moulinette.interface.api")


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


def best_locale_match_from_accept_language_header() -> str:
    # Werkzeug, Flask and Babel have utils for this but we use neither of them
    # so let's implement a homemade helper for this ...

    # In particular, this helper covers the ynh-portal case, because the front
    # doesn't provide a "locale" header info like the yunohost-admin front does

    def code_to_code_tuple(code: str) -> tuple[str, str | None]:
        # "fr"          -> ("fr",  None)
        # "zh_Hans"     -> ("zh", "hans")
        # "foo-bar_baz" -> ("foo", "bar-baz")
        code = code.replace("_", "-").lower()
        lang, spec = code.split("-", 1) if "-" in code else (code, None)
        return lang, spec

    def parse_accept_language(header: str) -> list[tuple[str, str | None]]:
        # Transform the accept-language header, for example "fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3"
        # Into: [('fr', None), ('fr', 'fr'), ('en', 'us'), ('en', None)]
        if not header:
            return []

        result = []
        for part in header.strip().replace(" ", "").split(","):
            # (I admit this regex bit is from ChatGPT :grimacing:)
            m = re.match(r"^\s*([A-Za-z0-9\-\_]+)\s*(?:;\s*q=([0-9.]+))?\s*$", part)
            if not m:
                continue
            result.append(code_to_code_tuple(m.group(1)))

        return result

    prefered_languages_raw = request.get_header("Accept-Language")
    prefered_languages = parse_accept_language(prefered_languages_raw)

    locales_dir = Path(m18n.translator.locale_dir)
    supported_locales_codes = {
        p.name[: -len(".json")] for p in locales_dir.glob("*.json")
    }
    # supported_locales looks like
    # { ... 'en', 'fr', 'it', 'ar', 'nb_NO', 'pt_BR', 'te', 'zh_Hans', ... }
    # but we convert those to code tuples to make it easier to compare with the prefered languages
    supported_locales_map = {
        code_to_code_tuple(code): code for code in supported_locales_codes
    }

    for lang, suffix in prefered_languages:
        # First check for exact matches
        if (lang, suffix) in supported_locales_map:
            return supported_locales_map[(lang, suffix)]

        # Then check for stuff like "fr-FR", fallback to just "fr"
        if suffix is not None and (lang, None) in supported_locales_map:
            return supported_locales_map[(lang, None)]

        # Then check for stuff like "zh_whatever", fallback to the first "zh" we find, such as "zh_Hans"
        matches = [
            code_tuple
            for code_tuple in supported_locales_map.keys()
            if code_tuple[0] == lang
        ]
        if matches:
            return supported_locales_map[matches[0]]

    return m18n.default_locale


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
                # ==== SPACE DIRTY_HACK =====
                # In order to avoid option injection by starting a value with @
                # we add a starting space on all string values, like that argparse
                # do not interpret it as an option...
                # The space is removed in a post-treatment
                # see https://github.com/python/cpython/issues/138950
                arg_strings.append(f" {UPLOAD_DIR}/{value.filename}")
            elif isinstance(value, str):
                # Same space dirty hack as above
                protected_value = f" {value}"
                if option_string is not None:
                    arg_strings.append(option_string)
                    # TODO: Review this fix
                    # FIXME What if value is an empty string ?
                    if value:
                        arg_strings.append(protected_value)
                else:
                    arg_strings.append(protected_value)
            elif isinstance(value, list):
                if option_string is not None:
                    arg_strings.append(option_string)
                for v in value:
                    if isinstance(v, str):
                        # Same space dirty hack as above

                        protected_value = f" {v}"
                        arg_strings.append(protected_value)
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

        # Post-treatment of the dirty hack describe above
        parsed_args = self._parser.parse_args(arg_strings, namespace)
        for option_string, value in vars(parsed_args).items():
            if isinstance(value, str) and option_string not in ["loginShell", "_tid"]:
                # We remove the starting space we have added on all values...
                setattr(parsed_args, option_string, value[1:])
        return parsed_args

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

    def __init__(self, actionsmap):
        self.actionsmap = actionsmap

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

        app.route(
            "/sse",
            name="sse",
            callback=self.sse,
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
            profile = request.json.get(
                "profile", self.actionsmap.default_authentication
            )
        else:
            if "credentials" in request.params:
                credentials = request.params["credentials"]
            elif "username" in request.params and "password" in request.params:
                credentials = (
                    request.params["username"] + ":" + request.params["password"]
                )
            else:
                raise HTTPResponse("Missing credentials parameter", 400)

            profile = request.params.get(
                "profile", self.actionsmap.default_authentication
            )

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
            referer = request.get_header("Referer")
            if "referer_redirect" in request.params and referer:
                redirect(referer)
            else:
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
            referer = request.get_header("Referer")
            if "referer_redirect" in request.params and referer:
                redirect(referer)
            else:
                return m18n.g("logged_out")

    def sse(self):

        profile = request.params.get("profile", self.actionsmap.default_authentication)
        authenticator = self.actionsmap.get_authenticator(profile)

        # Hardcoded yunohost stuff for the SSE stream to not require authentication when postinstall isnt done yet...
        if os.path.exists("/etc/yunohost/installed"):
            try:
                authenticator.get_session_cookie()
            except MoulinetteAuthenticationError:
                raise HTTPResponse(m18n.g("not_logged_in"), 401)

        response.content_type = "text/event-stream"
        response.cache_control = "no-cache"
        response.headers["X-Accel-Buffering"] = "no"

        from yunohost.utils.sse import sse_stream

        yield from sse_stream()

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
            print(tb, file=sys.stderr)
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

    def display(self, message, style="info"):
        pass

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
        self._route_re = re.compile(r"(GET|POST|PUT|DELETE|QUERY) (/\S+)")

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
    """

    type = "api"

    def __init__(self, routes={}, actionsmap=None, allowed_cors_origins=[]):
        actionsmap = ActionsMap(actionsmap, ActionsMapParser())

        self.allowed_cors_origins = allowed_cors_origins

        # TODO: Return OK to 'OPTIONS' xhr requests (l173)
        app = Bottle(autojson=True)

        def cors(callback):
            def wrapper(*args, **kwargs):
                try:
                    r = callback(*args, **kwargs)
                except HTTPResponse as e:
                    r = e

                origin = request.headers.environ.get("HTTP_ORIGIN", "")
                if origin and origin in self.allowed_cors_origins:
                    resp = r if isinstance(r, HTTPResponse) else response
                    resp.headers["Access-Control-Allow-Origin"] = origin
                    resp.headers["Access-Control-Allow-Methods"] = (
                        "GET, HEAD, POST, PUT, OPTIONS, DELETE, QUERY"
                    )
                    resp.headers["Access-Control-Allow-Headers"] = (
                        "Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token"
                    )
                    resp.headers["Access-Control-Allow-Credentials"] = "true"

                return r

            return wrapper

        # Attempt to retrieve and set locale
        def api18n(callback):
            def wrapper(*args, **kwargs):
                try:
                    locale = request.get_header("locale")
                except Exception:
                    locale = None

                if not locale:
                    try:
                        locale = best_locale_match_from_accept_language_header()
                    except Exception:
                        locale = None

                locale = locale or m18n.default_locale
                m18n.set_locale(locale)
                return callback(*args, **kwargs)

            return wrapper

        # Install plugins
        app.install(filter_csrf)
        app.install(cors)
        app.install(api18n)
        actionsmapplugin = _ActionsMapPlugin(actionsmap)
        app.install(actionsmapplugin)

        self.authenticate = actionsmapplugin.authenticate
        self.display = actionsmapplugin.display
        self.prompt = actionsmapplugin.prompt

        def handle_options():
            return HTTPResponse("", 204)

        app.route(
            "/<:re:.*>", method="OPTIONS", callback=handle_options, skip=["actionsmap"]
        )

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
            from gevent import monkey

            monkey.patch_all()
            from bottle import GeventServer

            GeventServer(host, port).run(self._app)
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
