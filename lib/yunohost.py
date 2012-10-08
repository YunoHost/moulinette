# -*- coding: utf-8 -*-

import os
import sys
import ldap
import ldap.modlist as modlist
import re
import getpass


def colorize(astr, color):
    color_dict = {
        'red'   : '31',
        'green' : '32',
        'yellow': '33',
        'cyan'  : '34',
        'purple': '35'
    }
    return "\033["+ color_dict[color] +"m\033[1m" + astr + "\033[m" 

def win_msg(astr):
    if os.isatty(1):
        print('\n' + colorize(_("Success: "), 'green') + astr + '\n')

def str_to_func(astr):
    """
    Call a function from a string name
    
    Keyword arguments:
        astr -- Name of function to call
    
    Returns: 
        Function

    """
    module, _, function = astr.rpartition('.')
    if module:
        __import__(module)
        mod = sys.modules[module]
    else:
        mod = sys.modules['__main__']  # default module
    
    try:
        func = getattr(mod, function)
    except NameError:
         raise YunoHostError(168, _('Function is not defined'))
    else:
        return func


class YunoHostError(Exception):
    """ Custom exception """
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


class YunoHostLDAP:
    """ Specific LDAP functions for YunoHost """

    def __init__(self):
        """ Connect to LDAP base """

        self.conn = ldap.initialize('ldap://localhost:389')
        self.base = 'dc=yunohost,dc=org'
        self.pwd = getpass.getpass(_('LDAP Admin Password: '))
        try:
            self.conn.simple_bind_s('cn=admin,' + self.base, self.pwd)
        except ldap.INVALID_CREDENTIALS:
            raise YunoHostError(13, _('Invalid credentials'))

    def disconnect(self):
        """ Unbind from LDAP """

        try:
            self.conn.unbind_s()
        except:
            raise YunoHostError(169, _('An error occured during disconnection'))
        else:
            return True

    def search(self, base=None, filter='(objectClass=*)', attrs=['dn']):
        """ Search in LDAP base """

        if not base:
            base = self.base

        try:
            result = self.conn.search_s(base, ldap.SCOPE_SUBTREE, filter, attrs)
        except:
            raise YunoHostError(169, _('An error occured during LDAP search'))

        if result:
            result_list = []
            for dn, entry in result:
                if 'dn' in attrs:
                    entry['dn'] = [dn]
                result_list.append(entry)
            return result_list       
        else:
            return False

    def add(self, rdn, attr_dict):
        """ Add LDAP entry """

        dn = rdn + ',' + self.base
        ldif = modlist.addModlist(attr_dict)

        try:
            self.conn.add_s(dn, ldif)
        except:
            raise YunoHostError(169, _('An error occured during LDAP entry creation'))
        else:
            return True


    def validate(self, regex_dict):
        for attr, pattern in regex_dict.items():
            if re.match(pattern, attr):
                continue
            else:
                raise YunoHostError(22, _('Invalid attribute') + ' ' + attr)
        return True

    def validate_uniqueness(self, value_dict):
        for attr, value in value_dict.items():
            if not self.search(filter=attr + '=' + value):
                continue
            else:
                raise YunoHostError(17, _('Attribute already exists') + ' "' + attr + '=' + value + '"')
        return True

