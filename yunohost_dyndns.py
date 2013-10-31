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

""" yunohost_dyndns.py

    Subscribe and Update DynDNS Hosts
"""
import os
import sys
import requests
import json
import glob
import base64
from yunohost import YunoHostError, YunoHostLDAP, validate, colorize, win_msg

def dyndns_subscribe(subscribe_host="dyndns.yunohost.org", domain=None, key=None):
    """
    Subscribe to a DynDNS service

    Keyword argument:
        domain -- Full domain to subscribe with
        subscribe_host -- Dynette HTTP API to subscribe to
        key -- Public DNS key

    """
    if domain is None:
        with open('/etc/yunohost/current_host', 'r') as f:
            domain = f.readline().rstrip()

    if key is None:
        if len(glob.glob('/etc/yunohost/dyndns/*.key')) == 0:
            os.makedirs('/etc/yunohost/dyndns')
            print(_("DNS key is being generated, it may take a while..."))
            os.system('cd /etc/yunohost/dyndns && dnssec-keygen -a hmac-md5 -b 128 -n USER '+ domain)
            os.system('chmod 600 /etc/yunohost/dyndns/*.key /etc/yunohost/dyndns/*.private')

        key_file = glob.glob('/etc/yunohost/dyndns/*.key')[0]
        with open(key_file) as f:
            key = f.readline().strip().split(' ')[-1]

    # Verify if domain is available
    if requests.get('http://'+ subscribe_host +'/test/'+ domain).status_code != 200:
        raise YunoHostError(17, _("Domain is already taken"))

    # Send subscription
    r = requests.post('http://'+ subscribe_host +'/key/'+ base64.b64encode(key), data={ 'subdomain': domain })
    if r.status_code != 201:
        try:    error = json.loads(r.text)['error']
        except: error = "Server error"
        raise YunoHostError(1, _("An error occured during DynDNS registration: "+ error))

    win_msg(_("Subscribed to DynDNS"))

    dyndns_installcron()


def dyndns_update(dyn_host="dynhost.yunohost.org", domain=None, key=None, ip=None):
    """
    Update IP on DynDNS platform

    Keyword argument:
        dyn_host -- Dynette DNS server to inform
        domain -- Full domain to subscribe with
        ip -- IP address to send
        key -- Public DNS key

    """
    if domain is None:
        with open('/etc/yunohost/current_host', 'r') as f:
            domain = f.readline().rstrip()

    if ip is None:
        new_ip = requests.get('http://ip.yunohost.org').text
    else:
        new_ip = ip

    try:
        with open('/etc/yunohost/dyndns/old_ip', 'r') as f:
            old_ip = f.readline().rstrip()
    except IOError:
        old_ip = '0.0.0.0'

    if old_ip != new_ip:
        host = domain.split('.')[1:]
        host = '.'.join(host)
        lines = [
            'server '+ dyn_host,
            'zone '+ host,
            'update delete '+ domain +'. A',
            'update delete '+ domain +'. MX',
            'update delete '+ domain +'. TXT',
            'update delete pubsub.'+ domain +'. A',
            'update delete muc.'+ domain +'. A',
            'update delete vjud.'+ domain +'. A',
            'update delete _xmpp-client._tcp.'+ domain +'. SRV',
            'update delete _xmpp-server._tcp.'+ domain +'. SRV',
            'update add '+ domain +'. 1800 A '+ new_ip,
            'update add '+ domain +'. 14400 MX 5 '+ domain +'.',
            'update add '+ domain +'. 14400 TXT "v=spf1 a mx -all"',
            'update add pubsub.'+ domain +'. 1800 A '+ new_ip,
            'update add muc.'+ domain +'. 1800 A '+ new_ip,
            'update add vjud.'+ domain +'. 1800 A '+ new_ip,
            'update add _xmpp-client._tcp.'+ domain +'. 14400 SRV 0 5 5222 '+ domain +'.',
            'update add _xmpp-server._tcp.'+ domain +'. 14400 SRV 0 5 5269 '+ domain +'.',
            'show',
            'send'
        ]
        with open('/etc/yunohost/dyndns/zone', 'w') as zone:
            for line in lines:
                zone.write(line + '\n')

        if key is None:
            private_key_file = glob.glob('/etc/yunohost/dyndns/*.private')[0]
        else:
            private_key_file = key
        if os.system('/usr/bin/nsupdate -k '+ private_key_file +' /etc/yunohost/dyndns/zone') == 0:
            win_msg(_("IP successfully updated"))
            with open('/etc/yunohost/dyndns/old_ip', 'w') as f:
                f.write(new_ip)
        else:
            raise YunoHostError(1, _("An error occured during DynDNS update"))


def dyndns_installcron():
    """
    Install IP update cron


    """
    os.system("touch /etc/cron.d/yunohost-dyndns")
    os.system("echo '*/30 * * * * root yunohost dyndns update --no-ldap >> /dev/null' >/etc/cron.d/yunohost-dyndns")
    win_msg(_("DynDNS cron installed"))


def dyndns_removecron():
    """
    Remove IP update cron


    """
    try:
        os.remove("/etc/cron.d/yunohost-dyndns")
    except:
        raise YunoHostError(167,_("DynDNS cron was not installed!"))

    win_msg(_("DynDNS cron removed"))
