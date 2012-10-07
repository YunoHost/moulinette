# -*- coding: utf-8 -*-

import sys
import ldap
import getpass

class YunoHostLDAP:
    """ Specific LDAP functions for YunoHost """

    def __init__(self):
        """ Connect to LDAP base """

        self.conn = ldap.initialize('ldap://localhost:389')
        self.base = 'dc=yunohost,dc=org'
        self.pwd = getpass.getpass()
        try:
            self.conn.simple_bind_s('cn=admin,' + self.base, self.pwd)
        except ldap.INVALID_CREDENTIALS:
            print(_('Error: Wrong credentials'))
            sys.exit(1)

    def disconnect(self):
        """ Unbind from LDAP """

        try:
            self.conn.unbind_s()
        except:
            print(_('Error: A problem occured on LDAP unbind'))
            return False
        else:
            return True

    def search(self, base, filter='(objectClass=*)', attrs=['dn']):
        """ Search in LDAP base """

        try:
            result = self.conn.search_s(base, ldap.SCOPE_ONELEVEL, filter, attrs)
        except Exception:
            print(_('Error: An error occured on LDAP search'))
            return False
        
        if result:
            result_list = []
            for dn, entry in result:
                if 'dn' in attrs:
                    entry['dn'] = [dn]
                result_list.append(entry)
            return result_list       
        else:
            print(_('No result found')) 
            return False
