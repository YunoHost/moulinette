# -*- coding: utf-8 -*-

from moulinette.core import (
    MoulinetteError,
    Moulinette18n,
)

__title__ = "moulinette"
__author__ = ["Yunohost Contributors"]
__license__ = "AGPL 3.0"
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
__all__ = ["init", "api", "cli", "m18n", "MoulinetteError", "Moulinette"]


m18n = Moulinette18n()


class classproperty:
    def __init__(self, f):
        self.f = f

    def __get__(self, obj, owner):
        return self.f(owner)


class Moulinette:
    _interface = None

    def prompt(*args, **kwargs):
        return Moulinette.interface.prompt(*args, **kwargs)

    def display(*args, **kwargs):
        return Moulinette.interface.display(*args, **kwargs)

    @classproperty
    def interface(cls):
        return cls._interface


# Easy access to interfaces
def api(host="localhost", port=80, routes={}, actionsmap=None, locales_dir=None, allowed_cors_origins=[]):
    """Web server (API) interface

    Run a HTTP server with the moulinette for an API usage.

    Keyword arguments:
        - host -- Server address to bind to
        - port -- Server port to bind to
        - routes -- A dict of additional routes to add in the form of
            {(method, uri): callback}

    """
    from moulinette.interfaces.api import Interface as Api

    m18n.set_locales_dir(locales_dir)

    try:
        Api(
            routes=routes,
            actionsmap=actionsmap,
            allowed_cors_origins=allowed_cors_origins,
        ).run(host, port)
    except MoulinetteError as e:
        import logging

        logging.getLogger("moulinette").error(e.strerror)
        return 1
    except KeyboardInterrupt:
        import logging

        logging.getLogger("moulinette").info(m18n.g("operation_interrupted"))
    return 0


def cli(
    args, top_parser, output_as=None, timeout=None, actionsmap=None, locales_dir=None
):
    """Command line interface

    Execute an action with the moulinette from the CLI and print its
    result in a readable format.

    Keyword arguments:
        - args -- A list of argument strings
        - output_as -- Output result in another format, see
            moulinette.interfaces.cli.Interface for possible values
        - top_parser -- The top parser used to build the ActionsMapParser

    """
    from moulinette.interfaces.cli import Interface as Cli

    m18n.set_locales_dir(locales_dir)

    try:
        load_only_category = args[0] if args and not args[0].startswith("-") else None
        Cli(
            top_parser=top_parser,
            load_only_category=load_only_category,
            actionsmap=actionsmap,
        ).run(args, output_as=output_as, timeout=timeout)
    except MoulinetteError as e:
        import logging

        logging.getLogger("moulinette").error(e.strerror)
        return 1
    return 0
