# -*- coding: utf-8 -*-

import os
import sys
try:
    import yaml
except ImportError:
    sys.stderr.write('Error: Yunohost CLI Require yaml lib\n')
    sys.stderr.write('apt-get install python-yaml\n')
    sys.exit(1)
from yunohost import YunoHostError, win_msg



def firewall_allow(protocol=None,port=None,ipv6=None):
    """
    Allow port in iptables

    Keyword arguments:
        protocol -- Protocol used
        port    -- Port to open
        ipv6    -- Boolean ipv6

    Return
        Dict

    """

    if int(port)<65536 and int(port)>0:
        if protocol == "Both":
            update_yml(port,'tcp','a',ipv6)
            update_yml(port,'udp','a',ipv6) 

        else:
            update_yml(port,protocol,'a',ipv6)

        win_msg(_("Port successfully openned"))

    else:
        raise YunoHostError(22,_("Port not between 1 and 65535 : ")+port)

    return firewall_reload()



def firewall_disallow(protocol=None,port=None,ipv6=None):
    """
    Disallow port in iptables

    Keyword arguments:
        protocol -- Protocol used
        port    -- Port to open
        ipv6    -- Boolean ipv6

    Return
        Dict

    """

    if protocol == "Both":  
        update_yml(port,'tcp','r',ipv6)
        update_yml(port,'udp','r',ipv6)
    else:
        update_yml(port,protocol,'r',ipv6)
    win_msg(_("Port successfully closed"))

    return firewall_reload()



def firewall_list():
    """
    Allow port in iptables

    Keyword arguments:
        None

    Return
        Dict

    """
    with open ('firewall.yml') as f:
        firewall = yaml.load(f)
    return firewall



def firewall_reload():
    '''
    Reload iptables configuration

    Keyword arguments:
    None

    Return
        Dict
    '''
    with open('firewall.yml','r') as f:
        firewall = yaml.load(f)

    os.system ("iptables -P INPUT ACCEPT")
    os.system ("iptables -F")
    os.system ("iptables -X")
    if '22' not in firewall['ipv4']['TCP']:
        update_yml('22','TCP','a',False)


    os.system ("ip6tables -P INPUT ACCEPT")
    os.system ("ip6tables -F")
    os.system ("ip6tables -X")
    if '22' not in firewall['ipv6']['TCP']:
        update_yml('22','TCP','a',True)

    for i,port in enumerate (firewall['ipv4']['TCP']):
        os.system ("iptables -A INPUT -p tcp -i eth0 --dport "+ str(port) +" -j ACCEPT")


    for i,port in enumerate (firewall['ipv4']['UDP']):
        os.system ("iptables -A INPUT -p udp -i eth0 --dport "+ str(port) +" -j ACCEPT")


    for i,port in enumerate (firewall['ipv6']['TCP']):
        os.system ("ip6tables -A INPUT -p tcp -i eth0 --dport "+ str(port) +" -j ACCEPT")


    for i,port in enumerate (firewall['ipv6']['UDP']):
        os.system ("ip6tables -A INPUT -p udp -i eth0 --dport "+ str(port) +" -j ACCEPT")


    os.system ("iptables -P INPUT DROP")
    os.system ("ip6tables -P INPUT DROP")

    win_msg(_("Firewall successfully reloaded"))

    return firewall_list()



def update_yml(port=None,protocol=None,mode=None,ipv6=None):
    """
    Update firewall.yml
    Keyword arguments:
        protocol -- Protocol used
        port -- Port to open
        mode -- a=append r=remove
        ipv6 -- Boolean ipv6

    Return
        None
    """
    if ipv6:
        ip = 'ipv6'
    else:
        ip = 'ipv4'

    with open('firewall.yml','r') as f:
        firewall = yaml.load(f)

    if mode == 'a':
        if port not in firewall[ip][protocol]:
            firewall[ip][protocol].append(port)

        else:
            raise YunoHostError(22,_("Port already openned :")+port)

    else:
        if port in firewall[ip][protocol]:
            firewall[ip][protocol].remove(port)

        else:
            raise YunoHostError(22,_("Port already closed :")+port)

    firewall[ip][protocol].sort(key=int)

    os.system("mv firewall.yml firewall.yml.old")

    with open('firewall.yml','w') as f:
        yaml.dump(firewall,f)
