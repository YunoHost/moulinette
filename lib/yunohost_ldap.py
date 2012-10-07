# -*- coding: utf-8 -*-

import sys
import ldap
import ldap.modlist as modlist
import re
import getpass
import yunohost_messages as msg

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
            print(msg.error + _('Wrong credentials'))
            sys.exit(msg.ECONNREFUSED)

    def disconnect(self):
        """ Unbind from LDAP """

        try:
            self.conn.unbind_s()
        except:
            print(msg.error + _('A problem occured during LDAP unbind'))
            return False
        else:
            return True

    def search(self, base=None, filter='(objectClass=*)', attrs=['dn']):
        """ Search in LDAP base """

        if not base:
            base = self.base

        try:
            result = self.conn.search_s(base, ldap.SCOPE_SUBTREE, filter, attrs)
        except:
            print(msg.error + _('An error occured during LDAP search'))
            return False
        
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
            print(msg.error + _('An error occured during LDAP entry creation'))
            return False 
        else:
            return True


    def validate(self, regex_dict):
        for attr, pattern in regex_dict.items():
            if re.match(pattern, attr):
                continue
            else:
                print(msg.error + _('Invalid value') + ' "' + attr + '"')
                sys.exit(msg.EINVAL)
        return True

    def validate_uniqueness(self, value_dict):
        for attr, value in value_dict.items():
            if not self.search(filter=attr + '=' + value):
                continue
            else:
                print(msg.error + _('Attribute already exists') + ' "' + attr + '=' + value + '"')
                sys.exit(msg.EEXIST)
        return True

