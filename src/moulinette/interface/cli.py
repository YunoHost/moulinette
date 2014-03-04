# -*- coding: utf-8 -*-

import argparse
from . import BaseParser

## CLI arguments Parser

class CLIParser(BaseParser):
    """Actions map's CLI Parser

    """
    def __init__(self, parser=None):
        self._parser = parser or argparse.ArgumentParser()
        self._subparsers = self._parser.add_subparsers()

    @staticmethod
    def format_arg_name(name, full):
        if name[0] == '-' and full:
            return [name, full]
        return [name]

    def add_general_parser(self, **kwargs):
        return self._parser

    def add_category_parser(self, name, category_help=None, **kwargs):
        parser = self._subparsers.add_parser(name, help=category_help)
        return CLIParser(parser)

    def add_action_parser(self, name, action_help, **kwargs):
        return self._subparsers.add_parser(name, help=action_help)

    def parse_args(self, args, **kwargs):
        return self._parser.parse_args(args)

actionsmap_parser = CLIParser
