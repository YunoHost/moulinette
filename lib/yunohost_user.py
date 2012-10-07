# -*- coding: utf-8 -*-

import ldap
import ldap.modlist as modlist
import yunohost_ldap

# Initialize LDAP
yldap = yunohost_ldap.YunoHostLDAP()

def user_list(args):
    result = yldap.search('ou=users,dc=gavoty,dc=org', attrs=['mail', 'dn', 'cn'])
    print(result)
