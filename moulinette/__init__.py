# -*- coding: utf-8 -*-

from rich import traceback
from rich.table import Table as RichTable, box
from rich.console import Console
from rich.style import Style

from moulinette.core import (
    MoulinetteError,
    MoulinetteSignals,
    Moulinette18n,
)
from moulinette.globals import init_moulinette_env

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
__all__ = [
    "init",
    "api",
    "cli",
    "m18n",
    "msignals",
    "env",
    "init_interface",
    "MoulinetteError",
]


msignals = MoulinetteSignals()
msettings = dict()
m18n = Moulinette18n()

console = Console()

# pretty traceback using rich
traceback.install(show_locals=True, extra_lines=6)


# nice helper function for common usecase
def _format_exception():
    with console.capture() as capture:
        console.print_exception()

    return capture.get()


console.format_exception = _format_exception


class Table:
    def __init__(self, data, columns=None, title=None, row_function=None):
        self.data = data
        self.columns = columns
        self.title = title
        self.row_function = row_function

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    def print(self):
        if not self.data:
            return

        assert len(self.data.keys()) == 1, self.data

        table = RichTable(show_header=True)
        table_name = list(self.data.keys())[0]
        table.title = f"[bold]{self.title if self.title else table_name}[/]"
        table.title_style = Style(color="white", bgcolor=None)
        table.row_styles = ["none", "dim"]
        table.box = box.SIMPLE_HEAD
        table.border_style = "bright_yellow"

        self._fill_table(table, table_name)

        console.print(table)

    def _fill_table(self, table, table_name):
        if len(self.data[table_name]) == 0:
            return

        if self.columns is None:
            self.columns = sorted(self.data[table_name][0].keys())

        for column in self.columns:
            if isinstance(column, dict):
                pass
            else:
                table.add_column(column.replace("_", " ").title())

        for row in self.data[table_name]:
            values = []
            for column in self.columns:
                values.append(row.get(column, ""))

            if self.row_function is not None:
                # this function is responsible for adding the row
                self.row_function(table=table, columns=self.columns, row=row, values=values)
            else:
                table.add_row(*values)


class TableForDict(Table):
    key = object()  # this is a flag value to say "key of the dictionary"

    def _fill_table(self, table, table_name):
        if len(self.data[table_name]) == 0:
            return

        if self.columns is None:
            an_item = list(self.data[table_name].keys())[0]
            self.columns = [self.key] + sorted(self.data[table_name][an_item].keys())

        for column in self.columns:
            if isinstance(column, dict):
                header = column.get("header", "")
                table.add_column(str(header))
            else:
                if column == self.key:
                    table.add_column()
                else:
                    table.add_column(column.replace("_", " ").title())

        for key, values in self.data[table_name].items():
            row_values = [key]
            for column in self.columns:
                if isinstance(column, dict):
                    column = column["key"]

                if column != self.key:
                    row_values.append(str(values.get(column, "")))

            if self.row_function is not None:
                # this function is responsible for adding the row
                self.row_function(table=table, columns=self.columns, row=(key, values),
                                  values=row_values)
            else:
                table.add_row(*row_values)


# Package functions


def init(logging_config=None, **kwargs):
    """Package initialization

    Initialize directories and global variables. It must be called
    before any of package method is used - even the easy access
    functions.

    Keyword arguments:
        - logging_config -- A dict containing logging configuration to load
        - **kwargs -- See core.Package

    At the end, the global variable 'pkg' will contain a Package
    instance. See core.Package for available methods and variables.

    """
    import sys
    from moulinette.utils.log import configure_logging

    configure_logging(logging_config)

    # Add library directory to python path
    sys.path.insert(0, init_moulinette_env()["LIB_DIR"])


# Easy access to interfaces
def api(host="localhost", port=80, routes={}):
    """Web server (API) interface

    Run a HTTP server with the moulinette for an API usage.

    Keyword arguments:
        - host -- Server address to bind to
        - port -- Server port to bind to
        - routes -- A dict of additional routes to add in the form of
            {(method, uri): callback}

    """
    from moulinette.interfaces.api import Interface as Api

    try:
        Api(routes=routes).run(host, port)
    except MoulinetteError as e:
        import logging

        logging.getLogger("moulinette").error(e.strerror)
        return 1
    except KeyboardInterrupt:
        import logging

        logging.getLogger("moulinette").info(m18n.g("operation_interrupted"))
    return 0


def cli(args, top_parser, output_as=None, timeout=None):
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

    try:
        load_only_category = args[0] if args and not args[0].startswith("-") else None
        Cli(top_parser=top_parser, load_only_category=load_only_category).run(
            args, output_as=output_as, timeout=timeout
        )
    except MoulinetteError as e:
        import logging

        logging.getLogger("moulinette").error(e.strerror)
        return 1
    return 0


def env():
    """Initialise moulinette specific configuration."""
    return init_moulinette_env()
