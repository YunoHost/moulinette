# -*- coding: utf-8 -*-

import ldap
import ldap.modlist as modlist
import yunohost_ldap as yldap

def user_list(args):
    result = yldap.conn.search_s('ou=users,dc=gavoty,dc=org',ldap.SCOPE_SUBTREE,'(cn=*)',['cn','mail'])
    for dn,entry in result:
	print entry['mail'][0]
