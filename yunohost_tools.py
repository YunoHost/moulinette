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

""" yunohost_tools.py

    Specific tools
"""
import os
import sys
import yaml
import re
import getpass
import subprocess
import requests
import json
from yunohost import YunoHostError, YunoHostLDAP, validate, colorize, get_required_args, win_msg
from yunohost_domain import domain_add
from yunohost_dyndns import dyndns_subscribe

def tools_ldapinit(password=None):
    """
    YunoHost LDAP initialization


    """
    with YunoHostLDAP() as yldap:

        with open('ldap_scheme.yml') as f:
            ldap_map = yaml.load(f)

        for rdn, attr_dict in ldap_map['parents'].items():
            yldap.add(rdn, attr_dict)

        for rdn, attr_dict in ldap_map['children'].items():
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

    os.system('rm /etc/smbldap-tools/smbldap_bind.conf')
    with open('/etc/smbldap-tools/smbldap_bind.conf', 'w') as f:
        lines = [
            'masterDN="cn=admin,dc=yunohost,dc=org"',
            'slaveDN="cn=admin,dc=yunohost,dc=org"',
            'masterPw="yunohost"',
            'slavePw="yunohost"'
        ]

        for line in lines:
            f.write(line +'\n')

    os.system('chmod 600 /etc/smbldap-tools/smbldap_bind.conf')
    os.system('smbpasswd -w yunohost')
    sid = subprocess.check_output(['net', 'getlocalsid', 'YUNOHOST']).strip().split(':')[1][1:]
    os.system('echo \'SID="'+ sid +'"\' >> /etc/smbldap-tools/smbldap.conf')
    if password is not None:
        os.system('echo "'+ password +'\n'+ password +'" | smbldap-populate')

    win_msg(_("LDAP has been successfully initialized"))


def tools_adminpw(old_password, new_password):
    """
    Change admin password

    Keyword argument:
        old_password
        new_password

    """
    # Validate password length
    if len(new_password) < 4:
        raise YunoHostError(22, _("Password is too short"))

    result  = os.system('ldappasswd -h localhost -D cn=admin,dc=yunohost,dc=org -w "'+ old_password +'" -a "'+ old_password +'" -s "' + new_password + '"')
    result2 = os.system('smbpasswd -w "'+ new_password + '"')

    os.system('rm /etc/smbldap-tools/smbldap_bind.conf')
    with open('/etc/smbldap-tools/smbldap_bind.conf', 'w') as f:
        lines = [
            'masterDN="cn=admin,dc=yunohost,dc=org"',
            'slaveDN="cn=admin,dc=yunohost,dc=org"',
            'masterPw="'+ new_password +'"',
            'slavePw="'+ new_password +'"'
        ]

        for line in lines:
            f.write(line +'\n')

    os.system('chmod 600 /etc/smbldap-tools/smbldap_bind.conf')

    if result == result2 == 0:
        win_msg(_("Admin password has been changed"))
    else:
        raise YunoHostError(22, _("Invalid password"))


def tools_maindomain(old_domain, new_domain, dyndns=False):
    """
    Main domain change tool

    Keyword argument:
        old_domain
        new_domain

    """

    if not old_domain:
        with open('/etc/yunohost/current_host', 'r') as f:
            old_domain = f.readline().rstrip()

    validate(r'^([a-zA-Z0-9]{1}([a-zA-Z0-9\-]*[a-zA-Z0-9])*)(\.[a-zA-Z0-9]{1}([a-zA-Z0-9\-]*[a-zA-Z0-9])*)*(\.[a-zA-Z]{1}([a-zA-Z0-9\-]*[a-zA-Z0-9])*)$', old_domain)

    config_files = [
        '/etc/postfix/main.cf',
        '/etc/metronome/metronome.cfg.lua',
        '/etc/dovecot/dovecot.conf',
        '/etc/lemonldap-ng/lemonldap-ng.ini',
        '/etc/hosts',
        '/usr/share/yunohost/yunohost-config/others/startup',
        '/home/backup.tahoe/tahoe.cfg'
    ]

    config_dir = []

    for dir in config_dir:
        for file in os.listdir(dir):
            config_files.append(dir + '/' + file)

    for file in config_files:
        with open(file, "r") as sources:
            lines = sources.readlines()
        with open(file, "w") as sources:
            for line in lines:
                sources.write(re.sub(r''+ old_domain +'', new_domain, line))

    domain_add([new_domain], raw=False, main=True)

    lemon_conf_lines = [
        "$tmp->{'domain'} = '"+ new_domain +"';", # Replace Lemon domain
        "$tmp->{'ldapBase'} = 'dc=yunohost,dc=org';", # Set ldap basedn
        "$tmp->{'portal'} = 'https://"+ new_domain +"/sso/';", # Set SSO url
        "$tmp->{'locationRules'}->{'"+ new_domain +"'}->{'(?#0ynh_admin)^/ynh-admin/'} = '$uid eq \"admin\"';",
        "$tmp->{'locationRules'}->{'"+ new_domain +"'}->{'(?#0ynh_user)^/ynh-user/'} = '$uid ne \"admin\"';"
    ]

    if old_domain is not 'yunohost.org':
        lemon_conf_lines.extend([
            "delete $tmp->{'locationRules'}->{'"+ old_domain +"'}->{'(?#0ynh_admin)^/ynh-admin/'};",
            "delete $tmp->{'locationRules'}->{'"+ old_domain +"'}->{'(?#0ynh_user)^/ynh-user/'};"
        ])

    with open('/tmp/tmplemonconf','w') as lemon_conf:
        for line in lemon_conf_lines:
            lemon_conf.write(line + '\n')

    os.system('rm /etc/yunohost/apache/domains/' + old_domain + '.d/*.fixed.conf') # remove SSO apache conf dir from old domain conf (fail if postinstall)
    os.system('rm /etc/ssl/private/yunohost_key.pem')
    os.system('rm /etc/ssl/certs/yunohost_crt.pem')

    command_list = [
        'cp /etc/yunohost/apache/templates/sso.fixed.conf   /etc/yunohost/apache/domains/' + new_domain + '.d/sso.fixed.conf', # add SSO apache conf dir to new domain conf
        'cp /etc/yunohost/apache/templates/admin.fixed.conf /etc/yunohost/apache/domains/' + new_domain + '.d/admin.fixed.conf',
        'cp /etc/yunohost/apache/templates/user.fixed.conf  /etc/yunohost/apache/domains/' + new_domain + '.d/user.fixed.conf',
        '/usr/share/lemonldap-ng/bin/lmYnhMoulinette',
        '/etc/init.d/hostname.sh',
        'cp    /etc/yunohost/certs/'+ new_domain +'/key.pem /etc/metronome/certs/yunohost_key.pem',
        'chown metronome: /etc/metronome/certs/yunohost_key.pem',
        'ln -s /etc/yunohost/certs/'+ new_domain +'/key.pem /etc/ssl/private/yunohost_key.pem',
        'ln -s /etc/yunohost/certs/'+ new_domain +'/crt.pem /etc/ssl/certs/yunohost_crt.pem',
        'echo '+ new_domain +' > /etc/yunohost/current_host',
        'service apache2 restart',
        'service metronome restart',
        'service postfix restart',
        'service dovecot restart',
        'service tahoe-lafs stop',
        'service tahoe-lafs start'
    ]

    for command in command_list:
        if os.system(command) != 0:
            raise YunoHostError(17, _("There were a problem during domain changing"))

    if dyndns: dyndns_subscribe(domain=new_domain)
    elif len(new_domain.split('.')) >= 3:
        r = requests.get('http://dyndns.yunohost.org/domains')
        dyndomains = json.loads(r.text)
        dyndomain  = '.'.join(new_domain.split('.')[1:])
        if dyndomain in dyndomains:
            dyndns_subscribe(domain=new_domain)

    win_msg(_("Main domain has been successfully changed"))


def tools_postinstall(domain, password, dyndns=False):
    """
    YunoHost post-install

    Keyword argument:
        dyndns -- Subscribe domain to a DynDNS service
        domain -- YunoHost main domain
        password -- YunoHost admin password

    """
    with YunoHostLDAP(password='yunohost') as yldap:
        try:
            with open('/etc/yunohost/installed') as f: pass
        except IOError:
            print('Installing YunoHost')
        else:
            raise YunoHostError(17, _("YunoHost is already installed"))

        # Create required folders
        folders_to_create = [
            '/etc/yunohost/apps',
            '/etc/yunohost/certs',
            '/var/cache/yunohost/repo'
        ]

        for folder in folders_to_create:
            try: os.listdir(folder)
            except OSError: os.makedirs(folder)

        # Create SSL CA
        ssl_dir = '/usr/share/yunohost/yunohost-config/ssl/yunoCA'
        command_list = [
            'echo "01" > '+ ssl_dir +'/serial',
            'rm '+ ssl_dir +'/index.txt',
            'touch '+ ssl_dir +'/index.txt',
            'openssl req -x509 -new -config '+ ssl_dir +'/openssl.cnf -days 3650 -out '+ ssl_dir +'/ca/cacert.pem -keyout '+ ssl_dir +'/ca/cakey.pem -nodes -batch',
            'cp '+ ssl_dir +'/ca/cacert.pem /etc/ssl/certs/ca-yunohost_crt.pem',
            'update-ca-certificates'
        ]

        for command in command_list:
            if os.system(command) != 0:
                raise YunoHostError(17, _("There were a problem during CA creation"))

        # Initialize YunoHost LDAP base
        tools_ldapinit(password)

        # New domain config
        tools_maindomain(old_domain='yunohost.org', new_domain=domain, dyndns=dyndns)

        # Change LDAP admin password
        tools_adminpw(old_password='yunohost', new_password=password)

        os.system('touch /etc/yunohost/installed')
        os.system('service samba restart')

    win_msg(_("YunoHost has been successfully configured"))
