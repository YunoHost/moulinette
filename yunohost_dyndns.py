# -*- coding: utf-8 -*-

import os
import sys
import requests
from yunohost import YunoHostError, YunoHostLDAP, validate, colorize, win_msg

def dyndns_subscribe(subscribe_host="dyndns.yunohost.org", domain=None, key=None):
    """
    Subscribe to a DynDNS service

    Keyword arguments:
        subscribe_host -- Dynette HTTP API to subscribe to
        domain         -- Full domain to subscribe with
        key            -- Public DNS key

    Returns:
        Win | Fail

    """
    if domain is None:
        with open('/etc/yunohost/current_host', 'r') as f:
            domain = f.readline().rstrip()

    if key is None:
        try:
            with open('/etc/yunohost/dyndns/01.key') as f:
                key = f.readline().strip().split(' ')[-1]
        except IOError:
            os.makedirs('/etc/yunohost/dyndns')
            os.system('cd /etc/yunohost/dyndns && dnssec-keygen -a hmac-md5 -b 128 -n USER '+ domain +' && mv *.key 01.key && *.private 01.private')
            os.system('chmod 600 /etc/yunohost/dyndns/01.key /etc/yunohost/dyndns/01.private')
            with open('/etc/yunohost/dyndns/01.key') as f:
                key = f.readline().strip().split(' ')[-1]

    # Verify if domain is available
    if requests.get('https://'+ subscribe_host +'/test/'+ domain).status_code != 200:
        raise YunoHostError(17, _("Domain is already taken"))

    # Send subscription
    if requests.post('https://'+ subscribe_host +'/key/'+ key, data={ 'subdomain': domain }).status_code != 201:
        raise YunoHostError(1, _("An error occured during DynDNS registration"))

    win_msg(_("Subscribed to DynDNS"))

    dyndns_installcron()


def dyndns_update(dyn_host="dynhost.yunohost.org", domain=None, key=None, ip=None):
    """
    Update IP on DNS platform

    Keyword arguments:
        dyn_host -- Dynette DNS server to inform
        domain   -- Full domain to update
        key      -- Public DNS key
        ip       -- IP to send

    Returns:
        Win | Fail

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
            'update add '+ domain +'. 14400 A '+ new_ip,
            'update add '+ domain +'. 14400 MX 5 '+ domain +'.',
            'update add '+ domain +'. 14400 TXT "v=spf1 a mx a:'+ domain +'. ?all"',
            'update add pubsub.'+ domain +'. 14400 A '+ new_ip,
            'update add muc.'+ domain +'. 14400 A '+ new_ip,
            'update add vjud.'+ domain +'. 14400 A '+ new_ip,
            'update add _xmpp-client._tcp.'+ domain +'. 14400 SRV 0 5 5222 '+ domain +'.',
            'update add _xmpp-server._tcp.'+ domain +'. 14400 SRV 0 5 5269 '+ domain +'.',
            'show',
            'send'
        ]
        with open('/etc/yunohost/dyndns/zone', 'w') as zone:
            for line in zone_lines:
                zone.write(line + '\n')

        with open('/etc/yunohost/dyndns/old_ip', 'w') as f:
            f.write(new_ip)

        if os.system('/usr/bin/nsupdate -k /etc/yunohost/dyndns/01.private /etc/yunohost/dyndns/zone') == 0:
            win_msg(_("IP successfully updated"))
        else:
            raise YunoHostError(1, _("An error occured during DynDNS update"))


def dyndns_installcron()
    """
    Install IP update cron

    Returns:
        Win

    """
    os.system("touch /etc/cron.d/yunohost-dyndns")
    os.system("echo '*/30 * * * * root yunohost dyndns update -u >>/dev/null' >/etc/cron.d/yunohost-firewall")
    win_msg(_("DynDNS cron installed"))


def dyndns_removecron()
    """
    Remove IP update cron

    Returns:
        Win | Fail

    """
    try:
        os.remove("/etc/cron.d/yunohost-dyndns")
    except:
        raise YunoHostError(167,_("DynDNS cron was not installed!"))

    win_msg(_("DynDNS cron removed"))
