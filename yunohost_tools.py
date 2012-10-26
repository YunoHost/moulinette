# -*- coding: utf-8 -*-

import os
import sys
import yaml
import re
from yunohost import validate, colorize, get_required_args

def tools_ldapinit(args, connections): 
    yldap = connections['ldap']

    # TODO: Check if LDAP is already initialized
    
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

    return { 'Success' : _("LDAP has been successfully initialized") }

def tools_adminpw(args, connections): #FIX
    # Validate password length
    if len(args['new']) < 4:
        raise YunoHostError(22, _("Password is too short"))
    print args

def tools_maindomain(args): #FIX
    validate({ args['new'] : r'^([a-zA-Z0-9]{1}([a-zA-Z0-9\-]*[a-zA-Z0-9])*)(\.[a-zA-Z0-9]{1}([a-zA-Z0-9\-]*[a-zA-Z0-9])*)*(\.[a-zA-Z]{1}([a-zA-Z0-9\-]*[a-zA-Z0-9])*)$' })

    config_files = [
        '/etc/postfix/main.cf',
        '/etc/mailname',
        '/etc/ejabberd/ejabberd.cfg',
        '/etc/lemonldap-ng/lemonldap-ng.ini',
        '/etc/hosts',
    ]

    config_dir = [
        '/var/lib/lemonldap-ng/conf',
        '/etc/apache2/sites-available',
    ]

    for dir in config_dir:
        for file in os.listdir(dir):
            config_files.append(dir + '/' + file)

    for file in config_files:
        with open(file, "r") as sources:
            lines = sources.readlines()
        with open(file, "w") as sources:
            for line in lines:
                sources.write(re.sub(r'yunohost.org', args['domain'], line))

    os.system('/etc/init.d/hostname.sh')
    # TODO: Regenerate certificate
    return { 'Success' : _("YunoHost main domain has been successfully configured") }

def tools_postinstall(args, connections):

    args = get_required_args(args, {'domain' : _('Domain name'), 'password' : _('Admin new password') }, True)

    # Initialize YunoHost LDAP base
    #tools_ldapinit(None, connections)

    # Change LDAP admin password
    #tools_adminpw({ 'old' : 'yunohost', 'new' : args['password']})

    # New domain config
    #tools_maindomain({ 'old' : 'yunohost.org', 'new' : args['domain']})
    
    return { 'Success' : _("YunoHost has been successfully configured") }
