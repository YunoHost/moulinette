# -*- coding: utf-8 -*-

import os
import sys
import miniupnpc

try:
    import yaml
except ImportError:
    sys.stderr.write('Error: Yunohost CLI Require yaml lib\n')
    sys.stderr.write('apt-get install python-yaml\n')
    sys.exit(1)
from yunohost import YunoHostError, win_msg



def firewall_allow(protocol=None,port=None,ipv6=None,upnp=None):
    """
    Allow port in iptables

    Keyword arguments:
        protocol -- Protocol used
        port    -- Port to open
        ipv6    -- Boolean ipv6
        upnp    --Boolean upnp
    
    Return
        Dict

    """
    port=int(port)
    if port<65536 and port>0:
        if protocol == "Both":
            update_yml(port,'TCP','a',ipv6)
            update_yml(port,'UDP','a',ipv6) 

        else:
            update_yml(port,protocol,'a',ipv6)

        win_msg(_("Port successfully openned"))

    else:
        raise YunoHostError(22,_("Port not between 1 and 65535 : ")+str(port))

    return firewall_reload(upnp)



def firewall_disallow(protocol=None,port=None,ipv6=None,upnp=None):
    """
    Disallow port in iptables

    Keyword arguments:
        protocol -- Protocol used
        port    -- Port to open
        ipv6    -- Boolean ipv6
        upnp    --Boolan upnp

    Return
        Dict

    """

    port=int(port)
    if protocol == "Both":  
        update_yml(port,'TCP','r',ipv6)
        update_yml(port,'UDP','r',ipv6)
    else:
        update_yml(port,protocol,'r',ipv6)
    win_msg(_("Port successfully closed"))

    return firewall_reload(upnp)



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



def firewall_reload(upnp=None):
    '''
    Reload iptables configuration

    Keyword arguments:
        upnp    --Boolean upnp

    Return
        Dict
    '''
    with open('firewall.yml','r') as f:
        firewall = yaml.load(f)

    os.system ("iptables -P INPUT ACCEPT")
    os.system ("iptables -F")
    os.system ("iptables -X")
    if 22 not in firewall['ipv4']['TCP']:
        update_yml(22,'TCP','a',False)


    os.system ("ip6tables -P INPUT ACCEPT")
    os.system ("ip6tables -F")
    os.system ("ip6tables -X")
    if upnp:
        upnp=miniupnpc.UPnP()
        upnp.discoverdelay=200
        nbigd= upnp.discover()
        if nbigd:
            try:
                upnp.selectigd()
            except:
                raise YunoHostError(167,_("No upnp devices found"))
        else:
            raise YunoHostError(22,_("Can't connect to the igd device"))
        igd=True
        # list the redirections :
        i = 0
        for i in (0,100):
            p = upnp.getgenericportmapping(i)
            if p==None:
                break
            port=p[0]
            proto=p[1]
            upnp.deleteportmapping(port,proto);
            i += 1

    print("plop")
    if 22 not in firewall['ipv6']['TCP']:
        update_yml(22,'TCP','a',True)

    for i,port in enumerate (firewall['ipv4']['TCP']):
        os.system ("iptables -A INPUT -p tcp -i eth0 --dport "+ str(port) +" -j ACCEPT")
        if upnp:
            add_portmapping(port,'TCP',upnp)
        


    for i,port in enumerate (firewall['ipv4']['UDP']):
        os.system ("iptables -A INPUT -p udp -i eth0 --dport "+ str(port) +" -j ACCEPT")
        if upnp:
            add_portmapping(port,'UDP',upnp)


    for i,port in enumerate (firewall['ipv6']['TCP']):
        os.system ("ip6tables -A INPUT -p tcp -i eth0 --dport "+ str(port) +" -j ACCEPT")
        if upnp:
            add_portmapping(port,'TCP',upnp)
        


    for i,port in enumerate (firewall['ipv6']['UDP']):
        os.system ("ip6tables -A INPUT -p udp -i eth0 --dport "+ str(port) +" -j ACCEPT")
        if upnp:
            add_portmapping(port,'UDP',upnp)


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
            raise YunoHostError(22,_("Port already openned :")+str(port))

    else:
        if port in firewall[ip][protocol]:
            firewall[ip][protocol].remove(port)

        else:
            raise YunoHostError(22,_("Port already closed :")+str(port))

    firewall[ip][protocol].sort()

    os.system("mv firewall.yml firewall.yml.old")

    with open('firewall.yml','w') as f:
        yaml.dump(firewall,f)

def add_portmapping(port=None,protocol=None,upnp=None):
    """
    Send a port mapping rules to igd device
    Keyword arguments:
        protocol -- Protocol used
        port -- Port to open

    Return
        None
    """
    upnp.addportmapping(port,protocol,upnp.lanaddr,port,'UPnP IGD Tester port %u' % port, '')

