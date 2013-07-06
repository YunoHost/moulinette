#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" License

    Copyright (C) 2013 YunoHost

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

"""
    Generate function header documentation
"""
import os
import sys
import yaml

def main():
    """

    """
    with open('action_map.yml') as f:
        action_map = yaml.load(f)

    resources = {}

    del action_map['general_arguments']
    for category, category_params in action_map.items():
        if 'category_help' not in category_params: category_params['category_help'] = ''

        with open('yunohost_'+ category, 'r') as f:
            lines = f.readlines()
        with open('yunohost_'+ category, 'w') as f:
            in_block = False
            for line in lines:
                if re.search(r'^""" yunohost_'+ category, line):
                    in_block = True
                if in_block:
                    if re.search(r'^"""', line):
                        in_block = False
                        f.write('\n')
                        f.write(category_params['category_help'] +'\n')
                        f.write('"""' +'\n')
                else:
                    f.write(line)

        for action, action_params in category_params['actions'].items():
            if 'action_help' not in action_params:
                action_params['action_help'] = ''

            help_lines = [
                '    """',
                '    '+ action_params['action_help'],
                ''
            ]

            if 'arguments' in action_params:
                help_lines.append('    Keyword argument:')
                for arg_name, arg_params in action_params['arguments'].items():
                    if 'help' in arg_params:
                        help = ' -- '+ arg_params['help']
                    else:
                        help = ''
                    name = arg_name.replace('-', '_')
                    if name[0] == '_':
                        required = False
                        if 'full' in arg_params:
                            name = arg_params['full'][2:]
                        else:
                            name = name[2:]
                        name = name.replace('-', '_')

                    help_lines.append('        '+ name + help)

            help_lines.append('    """')
            help_lines.append('')

            with open('yunohost_'+ category, 'r') as f:
                lines = f.readlines()
            with open('yunohost_'+ category, 'w') as f:
                in_block = False
                first_quotes = True
                for line in lines:
                    if re.search(r'^def '+ category +'_'+ action, line):
                        in_block = True
                    if in_block:
                        if re.search(r'^    """', line):
                            if first_quotes:
                                first_quotes = False
                            else:
                                in_block = False
                                for help_line in help_lines:
                                    f.write(help_line +'\n')
                    else:
                        f.write(line)


if __name__ == '__main__':
    sys.exit(main())
