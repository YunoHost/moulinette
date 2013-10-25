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

""" yunohost_hook.py

    Manage hooks
"""
import os
import sys
import re
import json
from yunohost import YunoHostError, YunoHostLDAP, win_msg, colorize

hook_folder = '/user/share/yunohost/hooks/'

def hook_add(action, file):
    """
    Store hook script to fs

    Keyword argument:
        action -- Action folder to store into
        file -- Script file to store

    """
    try: os.listdir(hook_folder + action)
    except OSError: os.makedirs(hook_folder + action)
    
    os.system('cp '+ file +' '+ hook_folder + action)
    

def hook_callback(action):
    """
    Execute all scripts binded to an action

    Keyword argument:
        action -- Action name

    """
    with YunoHostLDAP() as yldap:
        try: os.listdir(hook_folder + action)
        except OSError: os.makedirs(hook_folder + action)

        for hook in os.listdir(hook_folder + action):
            hook_exec(file=hook_folder + action +'/'+ hook)


def hook_check(file):
    """
    Parse the script file and get arguments

    Keyword argument:
        file -- Script to check

    """

    with open(file, 'r') as conf:
        script_lines = conf.readlines()

    in_block = False
    json_string = ""
    for line in script_lines:
        if re.search(r'^#### json"', line):
            in_block = True
        if in_block and re.search(r'^####', line):
            in_block = False
        elif re.search(r'^##[^#;]', line):
            json_string = json_string + line[2:]

    if json_string == "":
        return {}
    else:
        return json.loads(json_string)['arguments']

def hook_exec(file, args=None):
    """
    Execute hook from a file with arguments

    Keyword argument:
        file -- Script to execute
        args -- Arguments to pass to the script

    """
    with YunoHostLDAP() as yldap:
        required_args = hook_check(file)
        if args is None:
            args = {}

        arg_list = []
        for arg in required_args:
            if arg['name'] in args:
                if 'choices' in arg and args[arg['name']] not in arg['choices'].split('|'):
                    raise YunoHostError(22, _("Invalid choice") + ': ' + args[arg['name']])
                arg_list.append(args[arg['name']])
            else:
                if 'default' in arg:
                    arg_list.append(arg['default'])
                elif os.isatty(1) and 'ask' in arg:
                    arg_list.append(raw_input(colorize(arg['ask']['en'] + ': ', 'cyan'))) #TODO: I18n
                else:
                    raise YunoHostError(22, _("Missing arguments") + ': ' + arg_name)

        file_path = "./"
        if "/" in file and file[0:2] != file_path:
            file_path = os.path.dirname(file)
            file = file.replace(file_path +"/", "")
        return os.system('su - admin -c "cd \\"'+ file_path +'\\" && bash \\"'+ file +'\\" '+ ' '.join(arg_list) +'"') #TODO: Allow python script
