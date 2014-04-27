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

""" yunohost_firewall.py

    Manage firewall rules
"""
import os
import sys
import yaml
try:
    import miniupnpc
except ImportError:
    sys.stderr.write('Error: Yunohost CLI Require miniupnpc lib\n')
    sys.exit(1)

from moulinette.core import MoulinetteError


def firewall_allow(port=None, protocol='TCP', ipv6=False, no_upnp=False):
    """
    Allow connection port/protocol

    Keyword argument:
        port -- Port to open
        protocol -- Protocol associated with port
        ipv6 -- ipv6
        no_upnp -- Do not request for uPnP

    """
    port = int(port)
    ipv  = "ipv4"
    protocols = [protocol]

    firewall = firewall_list(raw=True)

    upnp = not no_upnp and firewall['uPnP']['enabled']

    if ipv6:
        ipv = "ipv6"

    if protocol == "Both":
        protocols = ['UDP', 'TCP']

    for protocol in protocols:
        if upnp and port not in firewall['uPnP'][protocol]:
            firewall['uPnP'][protocol].append(port)
        if port not in firewall[ipv][protocol]:
            firewall[ipv][protocol].append(port)
        else:
            msignals.display(_("Port already openned: %d" % port), 'warning')

    with open('/etc/yunohost/firewall.yml', 'w') as f:
        yaml.safe_dump(firewall, f, default_flow_style=False)

    return firewall_reload()


def firewall_disallow(port=None, protocol='TCP', ipv6=False):
    """
    Allow connection port/protocol

    Keyword argument:
        port -- Port to open
        protocol -- Protocol associated with port
        ipv6 -- ipv6

    """
    port = int(port)
    ipv  = "ipv4"
    protocols = [protocol]

    firewall = firewall_list(raw=True)

    if ipv6:
        ipv = "ipv6"

    if protocol == "Both":
        protocols = ['UDP', 'TCP']

    for protocol in protocols:
        if port in firewall['uPnP']['ports'][protocol]:
            firewall['uPnP']['ports'][protocol].remove(port)
        if port in firewall[ipv][protocol]:
            firewall[ipv][protocol].remove(port)
        else:
            msignals.display(_("Port already closed: %d" % port), 'warning')

    with open('/etc/yunohost/firewall.yml', 'w') as f:
        yaml.safe_dump(firewall, f, default_flow_style=False)

    return firewall_reload()


def firewall_list(raw=False):
    """
    List all firewall rules

    Keyword argument:
        raw -- Return the complete YAML dict

    """
    with open('/etc/yunohost/firewall.yml') as f:
        firewall = yaml.load(f)

    if raw:
        return firewall
    else:
        return firewall['ipv4']


def firewall_reload():
    """
    Reload all firewall rules


    """
    from yunohost.hook import hook_callback

    firewall = firewall_list(raw=True)
    upnp = firewall['uPnP']['enabled']

    # IPv4
    os.system("iptables -P INPUT ACCEPT")
    if upnp:
        try:
            upnpc = miniupnpc.UPnP()
            upnpc.discoverdelay = 200
            if upnpc.discover() == 1:
                upnpc.selectigd()
                for port in firewall['uPnP']['TCP']:
                    upnpc.addportmapping(port, 'TCP', upnpc.lanaddr, port, 'yunohost firewall : port %d' % port, '')
                for port in firewall['uPnP']['UDP']:
                    upnpc.addportmapping(port, 'UDP', upnpc.lanaddr, port, 'yunohost firewall : port %d' % port, '')
            else:
                raise MoulinetteError(1, _("No uPnP device found"))
        except:
            msignals.display(_("An error occured during uPnP port openning"), 'warning')

    os.system("iptables -F")
    os.system("iptables -X")
    os.system("iptables -A INPUT -m state --state ESTABLISHED -j ACCEPT")

    if 22 not in firewall['ipv4']['TCP']:
        firewall_allow(22)

    # Loop
    for port in firewall['ipv4']['TCP']:
        os.system("iptables -A INPUT -p TCP --dport %d -j ACCEPT" % port)
    for port in firewall['ipv4']['UDP']:
        os.system("iptables -A INPUT -p UDP --dport %d -j ACCEPT" % port)

    hook_callback('post_iptable_rules', [upnp, ipv6])

    os.system("iptables -A INPUT -i lo -j ACCEPT")
    os.system("iptables -A INPUT -p icmp -j ACCEPT")
    os.system("iptables -P INPUT DROP")

    # IPv6
    if os.path.exists("/proc/net/if_inet6"):
        os.system("ip6tables -P INPUT ACCEPT")
        os.system("ip6tables -F")
        os.system("ip6tables -X")
        os.system("ip6tables -A INPUT -m state --state ESTABLISHED -j ACCEPT")

        if 22 not in firewall['ipv6']['TCP']:
            firewall_allow(22, ipv6=True)

        # Loop v6
        for port in firewall['ipv6']['TCP']:
            os.system("ip6tables -A INPUT -p TCP --dport %d -j ACCEPT" % port)
        for port in firewall['ipv6']['UDP']:
            os.system("ip6tables -A INPUT -p UDP --dport %d -j ACCEPT" % port)
    
        os.system("ip6tables -A INPUT -i lo -j ACCEPT")
        os.system("ip6tables -A INPUT -p icmpv6 -j ACCEPT")
        os.system("ip6tables -P INPUT DROP")

    os.system("service fail2ban restart")
    msignals.display(_("Firewall successfully reloaded"), 'success')

    return firewall_list()


def firewall_upnp(action='enable'):
    """
    Add upnp cron and enable


    """

    with open('/etc/yunohost/firewall.yml', 'r') as f:
        firewall = yaml.load(f)

    firewall['UPNP']['cron'] = True

    os.system("touch /etc/cron.d/yunohost-firewall")
    os.system("echo '*/50 * * * * root yunohost firewall reload -u --no-ldap >>/dev/null'>/etc/cron.d/yunohost-firewall")
    msignals.display(_("UPNP cron installed"), 'success')

    os.system("mv /etc/yunohost/firewall.yml /etc/yunohost/firewall.yml.old")

    with open('/etc/yunohost/firewall.yml', 'w') as f:
        yaml.dump(firewall, f)


def firewall_removeupnp():
    """
    Remove upnp cron


    """
    with open('/etc/yunohost/firewall.yml', 'r') as f:
        firewall = yaml.load(f)

    firewall['UPNP']['cron'] = False

    try:
        os.remove("/etc/cron.d/yunohost-firewall")
    except:
        raise MoulinetteError(167, _("UPNP cron was not installed!"))

    msignals.display(_("UPNP cron removed"), 'success')

    os.system("mv /etc/yunohost/firewall.yml /etc/yunohost/firewall.yml.old")

    with open('/etc/yunohost/firewall.yml', 'w') as f:
        yaml.dump(firewall, f)


def firewall_checkupnp():
    """
    check if UPNP is install or not (0 yes 1 no)


    """
    with open('/etc/yunohost/firewall.yml', 'r') as f:
        firewall = yaml.load(f)

        if firewall['UPNP']['cron']:
            msignals.display(_("UPNP is activated"), 'success')
        else:
            raise MoulinetteError(167, _("UPNP not activated!"))


def firewall_stop():
    """
    Stop iptables and ip6tables


    """

    os.system("iptables -P INPUT ACCEPT")
    os.system("iptables -F")
    os.system("iptables -X")

    os.system("ip6tables -P INPUT ACCEPT")
    os.system("ip6tables -F")
    os.system("ip6tables -X")
    if(os.path.exists("/etc/cron.d/yunohost-firewall")):
        firewall_removeupnp()
