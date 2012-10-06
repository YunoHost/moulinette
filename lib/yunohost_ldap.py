# -*- coding: utf-8 -*-

import ldap

conn = ldap.initialize('ldap://localhost:389')
conn.simple_bind_s("cn=admin,dc=yunohost,dc=org","secret")
