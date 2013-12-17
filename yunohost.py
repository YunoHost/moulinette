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
    YunoHost core classes & functions
"""

__credits__ = """
    Copyright (C) 2012 YunoHost

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
__author__  = 'Kload <kload@kload.fr>'
__version__ = '2.0-beta3'

import os
import sys
try:
    import ldap
except ImportError:
    sys.stderr.write('Error: Yunohost CLI Require LDAP lib\n')
    sys.stderr.write('apt-get install python-ldap\n')
    sys.exit(1)
import ldap.modlist as modlist
import yaml
import json
import re
import getpass
import random
import string
import argparse
import gettext
import getpass
if not __debug__:
    import traceback

win = []

def random_password(length=8):
    char_set = string.ascii_uppercase + string.digits + string.ascii_lowercase
    return ''.join(random.sample(char_set,length))

def colorize(astr, color):
    """
    Print with style ;)

    Keyword arguments:
        astr    -- String to colorize
        color   -- Name of the color

    """
    color_dict = {
        'red'   : '31',
        'green' : '32',
        'yellow': '33',
        'cyan'  : '34',
        'purple': '35'
    }
    return "\033["+ color_dict[color] +"m\033[1m" + astr + "\033[m"

def pretty_print_dict(d, depth=0):
    for k,v in sorted(d.items(), key=lambda x: x[0]):
        k = colorize(str(k), 'purple')
        if isinstance(v, list) and len(v) == 1:
            v = v[0]
        if isinstance(v, dict):
            print(("  ") * depth + ("%s: " % str(k)))
            pretty_print_dict(v, depth+1)
        elif isinstance(v, list):
            print(("  ") * depth + ("%s: " % str(k)))
            for key, value in enumerate(v):
                if isinstance(value, tuple):
                    pretty_print_dict({value[0]: value[1]}, depth+1)
                elif isinstance(value, dict):
                    pretty_print_dict({key: value}, depth+1)
                else:
                    print(("  ") * (depth+1) + "- " +str(value))
        else:
            print(("  ") * depth + "%s: %s" % (str(k), str(v)))

def is_true(arg):
    true_list = ['yes', 'Yes', 'true', 'True' ]
    for string in true_list:
        if arg == string:
            return True

    return False

def win_msg(astr):
    """
    Display a success message if isatty

    Keyword arguments:
        astr -- Win message to display

    """
    global win
    if os.isatty(1):
        print('\n' + colorize(_("Success: "), 'green') + astr + '\n')

    win.append(astr)


def str_to_func(astr):
    """
    Call a function from a string name

    Keyword arguments:
        astr -- Name of function to call

    Returns:
        Function

    """
    try:
        module, _, function = astr.rpartition('.')
        if module:
            __import__(module)
            mod = sys.modules[module]
        else:
            mod = sys.modules['__main__']  # default module

        func = getattr(mod, function)
    except (AttributeError, ImportError):
        #raise YunoHostError(168, _('Function is not defined'))
        return None
    else:
        return func


def validate(pattern, array):
    """
    Validate attributes with a pattern

    Keyword arguments:
        pattern -- Regex to match with the strings
        array -- List of strings to check

    Returns:
        Boolean | YunoHostError

    """
    if array is None:
        return True
    if isinstance(array, str):
        array = [array]
    for string in array:
        if re.match(pattern, string):
            pass
        else:
            raise YunoHostError(22, _('Invalid attribute') + ' ' + string)
        return True

def get_required_args(args, required_args, password=False):
    """
    Input missing values or raise Exception

    Keyword arguments:
       args -- Available arguments
       required_args -- Dictionary of required arguments and input phrase
       password -- True|False Hidden password double-input needed

    Returns:
        args

    """
    try:
        for arg, phrase in required_args.items():
            if not args[arg] and arg != 'password':
                if os.isatty(1):
                    args[arg] = raw_input(colorize(phrase + ': ', 'cyan'))
                else:
                    raise Exception #TODO: fix
        # Password
        if 'password' in required_args and password:
            if not args['password']:
                if os.isatty(1):
                    args['password'] = getpass.getpass(colorize(required_args['password'] + ': ', 'cyan'))
                    pwd2 = getpass.getpass(colorize('Retype ' + required_args['password'][0].lower() + required_args['password'][1:] + ': ', 'cyan'))
                    if args['password'] != pwd2:
                        raise YunoHostError(22, _("Passwords doesn't match"))
                else:
                    raise YunoHostError(22, _("Missing arguments"))
    except KeyboardInterrupt, EOFError:
        raise YunoHostError(125, _("Interrupted"))

    return args


def display_error(error, json_print=False):
    """
    Nice error displaying

    """
    if not __debug__ :
        traceback.print_exc()
    if os.isatty(1) and not json_print:
        print('\n' + colorize(_("Error: "), 'red') + error.message)
    else:
        print(json.dumps({ error.code : error.message }))


class YunoHostError(Exception):
    """
    Custom exception

    Keyword arguments:
        code    -- Integer error code
        message -- Error message to display

    """
    def __init__(self, code, message):
        code_dict = {
            1   : _('Fail'),
            13  : _('Permission denied'),
            17  : _('Already exists'),
            22  : _('Invalid arguments'),
            87  : _('Too many users'),
            111 : _('Connection refused'),
            122 : _('Quota exceeded'),
            125 : _('Operation canceled'),
            167 : _('Not found'),
            168 : _('Undefined'),
            169 : _('LDAP operation error')
        }
        self.code = code
        self.message = message
        if code_dict[code]:
            self.desc = code_dict[code]
        else:
            self.desc = code


class Singleton(object):
    instances = {}
    def __new__(cls, *args, **kwargs):
        if cls not in cls.instances:
            cls.instances[cls] = super(Singleton, cls).__new__(cls, *args, **kwargs)
        return cls.instances[cls]


class YunoHostLDAP(Singleton):
    """ Specific LDAP functions for YunoHost """
    pwd = False
    connected = False
    conn = ldap.initialize('ldap://localhost:389')
    base = 'dc=yunohost,dc=org'
    level = 0

    def __enter__(self):
        return self

    def __init__(self, password=False, anonymous=False):
        """
        Connect to LDAP base

        Initialize to localhost, base yunohost.org, prompt for password

        """
        if anonymous:
           self.conn.simple_bind_s()
           self.connected = True
        elif self.connected and not password:
           pass
        else:
            if password:
                self.pwd = password
            elif self.pwd:
                pass
            else:
                try:
                    with open('/etc/yunohost/passwd') as f:
                        self.pwd = f.read()
                except IOError:
                    need_password = True
                    while need_password:
                        try:
                            self.pwd = getpass.getpass(colorize(_('Admin Password: '), 'yellow'))
                            self.conn.simple_bind_s('cn=admin,' + self.base, self.pwd)
                        except KeyboardInterrupt, EOFError:
                            raise YunoHostError(125, _("Interrupted"))
                        except ldap.INVALID_CREDENTIALS:
                            print(_('Invalid password... Try again'))
                        else:
                            need_password = False

            try:
                self.conn.simple_bind_s('cn=admin,' + self.base, self.pwd)
                self.connected = True
            except ldap.INVALID_CREDENTIALS:
                raise YunoHostError(13, _('Invalid credentials'))

        self.level = self.level+1

    def __exit__(self, type, value, traceback):
        self.level = self.level-1
        if self.level == 0:
            try: self.disconnect()
            except: pass

    def disconnect(self):
        """
        Unbind from LDAP

        Returns
            Boolean | YunoHostError

        """
        try:
            self.connected = False
            self.pwd = False
            self.conn.unbind_s()
        except:
            raise YunoHostError(169, _('An error occured during disconnection'))
        else:
            return True


    def search(self, base=None, filter='(objectClass=*)', attrs=['dn']):
        """
        Search in LDAP base

        Keyword arguments:
            base    -- Base to search into
            filter  -- LDAP filter
            attrs   -- Array of attributes to fetch

        Returns:
            Boolean | Dict

        """
        if not base:
            base = self.base

        try:
            result = self.conn.search_s(base, ldap.SCOPE_SUBTREE, filter, attrs)
        except:
            raise YunoHostError(169, _('An error occured during LDAP search'))

        if result:
            result_list = []
            for dn, entry in result:
                if attrs != None:
                    if 'dn' in attrs:
                        entry['dn'] = [dn]
                result_list.append(entry)
            return result_list
        else:
            return False


    def add(self, rdn, attr_dict):
        """
        Add LDAP entry

        Keyword arguments:
            rdn         -- DN without domain
            attr_dict   -- Dictionnary of attributes/values to add

        Returns:
            Boolean | YunoHostError

        """
        dn = rdn + ',' + self.base
        ldif = modlist.addModlist(attr_dict)

        try:
            self.conn.add_s(dn, ldif)
        except:
            raise YunoHostError(169, _('An error occured during LDAP entry creation'))
        else:
            return True

    def remove(self, rdn):
        """
        Remove LDAP entry

        Keyword arguments:
            rdn         -- DN without domain

        Returns:
            Boolean | YunoHostError

        """
        dn = rdn + ',' + self.base
        try:
            self.conn.delete_s(dn)
        except:
            raise YunoHostError(169, _('An error occured during LDAP entry deletion'))
        else:
            return True


    def update(self, rdn, attr_dict, new_rdn=False):
        """
        Modify LDAP entry

        Keyword arguments:
            rdn         -- DN without domain
            attr_dict   -- Dictionnary of attributes/values to add
            new_rdn     -- New RDN for modification

        Returns:
            Boolean | YunoHostError

        """
        dn = rdn + ',' + self.base
        actual_entry = self.search(base=dn, attrs=None)
        ldif = modlist.modifyModlist(actual_entry[0], attr_dict, ignore_oldexistent=1)

        try:
            if new_rdn:
                self.conn.rename_s(dn, new_rdn)
                dn = new_rdn + ',' + self.base

            self.conn.modify_ext_s(dn, ldif)
        except:
            raise YunoHostError(169, _('An error occured during LDAP entry update'))
        else:
            return True


    def validate_uniqueness(self, value_dict):
        """
        Check uniqueness of values

        Keyword arguments:
            value_dict -- Dictionnary of attributes/values to check

        Returns:
            Boolean | YunoHostError

        """
        for attr, value in value_dict.items():
            if not self.search(filter=attr + '=' + value):
                continue
            else:
                raise YunoHostError(17, _('Attribute already exists') + ' "' + attr + '=' + value + '"')
        return True


def parse_dict(action_map):
    """
    Turn action dictionnary to parser, subparsers and arguments

    Keyword arguments:
        action_map -- Multi-level dictionnary of categories/actions/arguments list

    Returns:
        Namespace of args

    """
    # Intialize parsers
    parsers = subparsers_category = subparsers_action = {}
    parsers['general'] = argparse.ArgumentParser()
    subparsers = parsers['general'].add_subparsers()
    new_args = []
    patterns = {}

    # Add general arguments
    for arg_name, arg_params in action_map['general_arguments'].items():
        if 'version' in arg_params:
            v = arg_params['version']
            arg_params['version'] = v.replace('%version%', __version__)
        if 'full' in arg_params:
            arg_names = [arg_name, arg_params['full']]
            arg_fullname = arg_params['full']
            del arg_params['full']
        else: arg_names = [arg_name]
        parsers['general'].add_argument(*arg_names, **arg_params)

    del action_map['general_arguments']

    # Split categories into subparsers
    for category, category_params in action_map.items():
        if 'category_help' not in category_params: category_params['category_help'] = ''
        subparsers_category[category] = subparsers.add_parser(category, help=category_params['category_help'])
        subparsers_action[category] = subparsers_category[category].add_subparsers()
        # Split actions
        if 'actions' in category_params:
            for action, action_params in category_params['actions'].items():
                if 'action_help' not in action_params: action_params['action_help'] = ''
                parsers[category + '_' + action] = subparsers_action[category].add_parser(action, help=action_params['action_help'])
                # Set the action s related function
                parsers[category + '_' + action].set_defaults(
                    func=str_to_func('yunohost_' + category + '.'
                                     + category + '_' + action.replace('-', '_')))
                # Add arguments
                if 'arguments' in action_params:
                    for arg_name, arg_params in action_params['arguments'].items():
                        arg_fullname = False

                        if 'password' in arg_params:
                            if arg_params['password']: is_password = True
                            del arg_params['password']
                        else: is_password = False

                        if 'full' in arg_params:
                            arg_names = [arg_name, arg_params['full']]
                            arg_fullname = arg_params['full']
                            del arg_params['full']
                        else: arg_names = [arg_name]

                        if 'ask' in arg_params:
                            require_input = True
                            if '-h' in sys.argv or '--help' in sys.argv:
                                require_input = False
                            if (category != sys.argv[1]) or (action != sys.argv[2]):
                                require_input = False
                            for name in arg_names:
                                if name in sys.argv[2:]: require_input = False

                            if require_input:
                                if is_password:
                                    if os.isatty(1):
                                        pwd1 = getpass.getpass(colorize(arg_params['ask'] + ': ', 'cyan'))
                                        pwd2 = getpass.getpass(colorize('Retype ' + arg_params['ask'][0].lower() + arg_params['ask'][1:] + ': ', 'cyan'))
                                        if pwd1 != pwd2:
                                            raise YunoHostError(22, _("Passwords don't match"))
                                            sys.exit(1)
                                    else:
                                        raise YunoHostError(22, _("Missing arguments") + ': ' + arg_name)
                                    if arg_name[0] == '-': arg_extend = [arg_name, pwd1]
                                    else: arg_extend = [pwd1]
                                else:
                                    if os.isatty(1):
                                        arg_value = raw_input(colorize(arg_params['ask'] + ': ', 'cyan'))
                                    else:
                                        raise YunoHostError(22, _("Missing arguments") + ': ' + arg_name)
                                    if arg_name[0] == '-': arg_extend = [arg_name, arg_value]
                                    else: arg_extend = [arg_value]
                                new_args.extend(arg_extend)
                            del arg_params['ask']

                        if 'pattern' in arg_params:
                            if (category == sys.argv[1]) and (action == sys.argv[2]):
                                if 'dest' in arg_params: name = arg_params['dest']
                                elif arg_fullname: name = arg_fullname[2:]
                                else: name = arg_name
                                name = name.replace('-', '_')
                                patterns[name] = arg_params['pattern']
                            del arg_params['pattern']

                        parsers[category + '_' + action].add_argument(*arg_names, **arg_params)

    args = parsers['general'].parse_args(sys.argv.extend(new_args))
    args_dict = vars(args)
    for key, value in patterns.items():
        validate(value, args_dict[key])

    return args
