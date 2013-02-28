# -*- coding: utf-8 -*-

import os
import sys
import datetime
import re
import shutil
from urllib import urlopen
from yunohost import YunoHostError, YunoHostLDAP, win_msg, colorize, validate, get_required_args

a2_template_path = '/etc/yunohost/apache/templates'
a2_app_conf_path = '/etc/yunohost/apache/domains'
lemon_tmp_conf   = '/tmp/tmplemonconf'

def domain_list(filter=None, limit=None, offset=None):
    """
    List YunoHost domains

    Keyword argument:
        filter -- LDAP filter to search with
        limit
        offset

    Returns:
        Dict
    """
    with YunoHostLDAP() as yldap:
        result_list = []
        if offset: offset = int(offset)
        else: offset = 0
        if limit: limit = int(limit)
        else: limit = 1000
        if not filter: filter = 'virtualdomain=*'

        result = yldap.search('ou=domains,dc=yunohost,dc=org', filter, attrs=['virtualdomain'])

        if result and len(result) > (0 + offset) and limit > 0:
            i = 0 + offset
            for domain in result[i:]:
                if i <= limit:
                    result_list.append(domain['virtualdomain'][0])
                    i += 1
        else:
            raise YunoHostError(167, _("No domain found"))

        return { 'Domains': result_list }


def domain_add(domains, web=False):
    """
    Add one or more domains

    Keyword argument:
        domains -- List of domains to add
        web -- Configure Apache and LemonLDAP for the domain too

    Returns:
        Dict
    """
    with YunoHostLDAP() as yldap:
        attr_dict = { 'objectClass' : ['mailDomain', 'top'] }
        ip = str(urlopen('http://ip.yunohost.org').read())
        now = datetime.datetime.now()
        timestamp = str(now.year) + str(now.month) + str(now.day)
        result = []

        if not isinstance(domains, list):
            domains = [ domains ]

        for domain in domains:
            try:
                yldap.validate_uniqueness({ 'virtualdomain' : domain })
            except YunoHostError:
                if web:
                    _apache_config(domain)
                    _lemon_config(domain)

                    win_msg(_("Web config created"))
                    break
                else:
                    raise YunoHostError(17, _("Domain already created"))


            attr_dict['virtualdomain'] = domain

            try:
                with open('/var/lib/bind/'+ domain +'.zone') as f: pass
            except IOError as e:
                zone_lines = [
                 '$TTL    38400',
                 domain +'.      IN   SOA   ns.'+ domain +'. root.'+ domain +'. '+ timestamp +' 10800 3600 604800 38400',
                 domain +'.      IN   NS    ns.'+ domain +'.',
                 domain +'.      IN   A     '+ ip,
                 domain +'.      IN   MX    5 mail.'+ domain +'.',
                 domain +'.      IN   TXT   "v=spf1 a mx a:'+ domain +' ?all"',
                 'mail.'+ domain +'. IN   A     '+ ip,
                 'ns.'+ domain +'.   IN   A     '+ ip,
                 'root.'+ domain +'. IN   A     '+ ip
                ]
                with open('/var/lib/bind/' + domain + '.zone', 'w') as zone:
                    for line in zone_lines:
                        zone.write(line + '\n')
            else:
                raise YunoHostError(17, _("Zone file already exists for ") + domain)

            conf_lines = [
                'zone "'+ domain +'" {',
                '    type master;',
                '    file "/var/lib/bind/'+ domain +'.zone";',
                '    allow-transfer {',
                '        127.0.0.1;',
                '        localnets;',
                '    };',
                '};'
            ]
            with open('/etc/bind/named.conf.local', 'a') as conf:
                for line in conf_lines:
                        conf.write(line + '\n')

            if web:
                _apache_config(domain)
                _lemon_config(domain)

            if yldap.add('virtualdomain=' + domain + ',ou=domains', attr_dict):
                result.append(domain)
                continue
            else:
                raise YunoHostError(169, _("An error occured during domain creation"))

        win_msg(_("Domain(s) successfully created"))

        return { 'Domains' : result }


def domain_remove(domains):
    """
    Remove domain from LDAP

    Keyword argument:
        domains -- List of domains to remove

    Returns:
        Dict
    """
    with YunoHostLDAP() as yldap:
        result = []

        if not isinstance(domains, list):
            domains = [ domains ]

        for domain in domains:
            if yldap.remove('virtualdomain=' + domain + ',ou=domains'):
                try:
                    os.remove('/var/lib/bind/'+ domain +'.zone')
                except:
                    pass
                with open('/etc/bind/named.conf.local', 'r') as conf:
                    conf_lines = conf.readlines()
                with open('/etc/bind/named.conf.local', 'w') as conf:
                    in_block = False
                    for line in conf_lines:
                        if re.search(r'^zone "'+ domain, line):
                            in_block = True
                        if in_block:
                            if re.search(r'^};$', line):
                                in_block = False
                        else:
                            conf.write(line)
                result.append(domain)
                continue
            else:
                raise YunoHostError(169, _("An error occured during domain deletion"))

        win_msg(_("Domain(s) successfully deleted"))

        return { 'Domains' : result }


def _apache_config(domain):
    """
    Fill Apache configuration templates

    Keyword arguments:
        domain -- Domain to configure Apache around

    """
    try: os.listdir(a2_app_conf_path +'/'+ domain +'.d/')
    except OSError: os.makedirs(a2_app_conf_path +'/'+ domain +'.d/')

    with open(a2_app_conf_path +'/'+ domain +'.conf', 'w') as a2_conf:
        for line in open(a2_template_path +'/template.conf.tmp'):
            line = line.replace('[domain]',domain)
            a2_conf.write(line)

    if os.system('service apache2 reload') == 0:
        win_msg(_("Apache configured"))
    else:
        raise YunoHostError(1, _("An error occured during Apache configuration"))


def _lemon_config(domain):
    """
    Configure LemonLDAP

    Keyword arguments:
        domain -- Domain to configure LemonLDAP around

    """
    if os.path.exists(lemon_tmp_conf): os.remove(lemon_tmp_conf)

    lemon_conf_lines = [
       "$tmp->{'exportedHeaders'}->{'"+ domain +"'}->{'Auth-User'} = '$uid';",
       "$tmp->{'exportedHeaders'}->{'"+ domain +"'}->{'Remote-User'} = '$uid';",
       "$tmp->{'exportedHeaders'}->{'"+ domain +"'}->{'Desc'} = '$description';",
       "$tmp->{'exportedHeaders'}->{'"+ domain +"'}->{'Email'} = '$mail';",
       "$tmp->{'exportedHeaders'}->{'"+ domain +"'}->{'Name'} = '$cn';",
       "$tmp->{'exportedHeaders'}->{'"+ domain +"'}->{'Authorization'} = '\"Basic \".encode_base64(\"$uid:$_password\")';",
       "$tmp->{'vhostOptions'}->{'"+ domain +"'}->{'vhostMaintenance'} = 0;",
       "$tmp->{'vhostOptions'}->{'"+ domain +"'}->{'vhostPort'} = -1;",
       "$tmp->{'vhostOptions'}->{'"+ domain +"'}->{'vhostHttps'} = -1;",
       "$tmp->{'locationRules'}->{'"+ domain +"'}->{'default'} = 'accept';",
       "$tmp->{'locationRules'}->{'"+ domain +"'}->{'(?#logout)^/logout'} = 'logout_app_sso https://"+ domain +"/';",
    ]

    with open(lemon_tmp_conf,'a') as lemon_conf:
        for line in lemon_conf_lines:
            lemon_conf.write(line + '\n')

    if os.system('/usr/share/lemonldap-ng/bin/lmYnhMoulinette') == 0:
        win_msg(_("LemonLDAP configured"))
    else:
        raise YunoHostError(1, _("An error occured during LemonLDAP configuration"))



