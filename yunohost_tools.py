# -*- coding: utf-8 -*-

import yaml

def tools_init(args, connections): 
    yldap = connections['ldap']
    
    with open('ldap_scheme.yml') as f: 
        ldap_map = yaml.load(f)

    for rdn, attr_dict in ldap_map['parents'].items():
        yldap.add(rdn, attr_dict)

    for rdn, attr_dict in ldap_map['childs'].items():
        yldap.add(rdn, attr_dict)

    admin_dict = {
        'cn': 'admin',
        'uid': 'admin',
        'description': 'LDAP Administrator',
        'gidNumber': '1007',
        'uidNumber': '1007',
        'homeDirectory': '/home/admin',
        'loginShell': '/bin/bash',
        'objectClass': ['organizationalRole', 'posixAccount', 'simpleSecurityObject']
    }

    yldap.update('cn=admin', admin_dict)

    return { 'Success' : _("LDAP successfully initialized") }
