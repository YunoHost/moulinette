# -*- coding: utf-8 -*-

import os
import sys
try:
    import yaml
except ImportError:
    sys.stderr.write('Error: Yunohost CLI Require yaml lib\n')
    sys.stderr.write('apt-get install python-yaml\n')
    sys.exit(1)



def firewall_allow(protocol=None,port=None,ipv6=None):
    if ipv6 == True:
        ip = 'ipv6'
        iptables="ip6tables"
    else:
        ip = 'ipv4'
        iptables="iptables"

    if protocol == "Both":
        TCP_rule = iptables+" -A INPUT -p tcp -i eth0 --dport "+ port +" -j ACCEPT"       
        UDP_rule = iptables+" -A INPUT -p udp -i eth0 --dport "+ port +" -j ACCEPT"
        
        update_yml(port,'tcp','a',ip)
        update_yml(port,'udp','a',ip)
        
        os.system(TCP_rule)
        os.system(UDP_rule)

    else:
        rule = iptables+" -A INPUT -p "+ protocol +" -i eth0 --dport "+ port +" -j ACCEPT"
        update_yml(port,protocol,'a',ip)
        os.system(rule)



def firewall_disallow(protocol=None,port=None,ipv6=None):

    if ipv6 == True:
        ip = 'ipv6'
        iptables="ip6tables"
    else:
        ip = 'ipv4'
        iptables="ip6tables"

    if protocol == "Both":
        TCP_rule = iptables+" -A INPUT -p tcp -i eth0 --dport "+ port +" -j REJECT"
        UDP_rule = iptables+" -A INPUT -p udp -i eth0 --dport "+ port +" -j REJECT"
        
        update_yml(port,'tcp','r',ip)
        update_yml(port,'udp','r',ip)
        
        os.system(TCP_rule)
        os.system(UDP_rule)
        
    else:
        rule = iptables+" -A INPUT -p "+ protocol +" -i eth0 --dport "+ port +" -j REJECT"
        update_yml(port,protocol,'r',ip)
        os.system(rule)



def firewall_list():
    '''
    Parse and display firwall.yml
    '''
    with open ('firewall.yml') as f:
        firewall = yaml.load(f)
    return firewall



def firewall_reload():
    '''
    Clear filter IPTABLE's table
    Allow SSH
    Parse firewall.yml extract the list of port allowed
    Allow all port in the list
    Prohibit the rest
    '''
    with open('firewall.yml','r') as f:
        firewall = yaml.load(f)

    os.system ("iptables -P INPUT ACCEPT")
    os.system ("iptables -F")
    os.system ("iptables -X")
    os.system ("iptables -A INPUT -p tcp -i eth0 --dport 22 -j ACCEPT")
    update_yml('22','TCP','a',False)


    os.system ("ip6tables -P INPUT ACCEPT")
    os.system ("ip6tables -F")
    os.system ("ip6tables -X")
    os.system ("ip6tables -A INPUT -p tcp -i eth0 --dport 22 -j ACCEPT")
    update_yml('22','TCP','a',True)

    for i,port in enumerate (firewall['ipv4']['TCP']):
        os.system ("iptables -A INPUT -p tcp -i eth0 --dport "+ str(port) +" -j ACCEPT")
        print("Port "+str(port)+" on protocol TCP  with ipv4 Open")

    for i,port in enumerate (firewall['ipv4']['UDP']):
        os.system ("iptables -A INPUT -p udp -i eth0 --dport "+ str(port) +" -j ACCEPT")
        print("Port "+str(port)+" on protocol UDP  with ipv4 Open")

    for i,port in enumerate (firewall['ipv6']['TCP']):
        os.system ("ip6tables -A INPUT -p tcp -i eth0 --dport "+ str(port) +" -j ACCEPT")
        print("Port "+str(port)+" on protocol TCP  with ipv6 Open")

    for i,port in enumerate (firewall['ipv6']['UDP']):
        os.system ("ip6tables -A INPUT -p udp -i eth0 --dport "+ str(port) +" -j ACCEPT")
        print("Port "+str(port)+" on protocol UDP  with ipv6 Open")

    os.system ("iptables -P INPUT DROP")
    os.system ("ip6tables -P INPUT DROP")



def update_yml(port=None,protocol=None,mode=None,ip=None):
    '''
    Append port in firewall.yml
    '''
    
    with open('firewall.yml','r') as f:
        firewall = yaml.load(f)
    if mode == 'a':
        if int(port) not in firewall[ip][protocol]:
            firewall[ip][protocol].append(int(port))
            print("Port "+port+" on protocol "+protocol+" with "+ip+" Open")
        else:
            print("Port already open")
    else:
        if int(port) in firewall[ip][protocol]:
            firewall[ip][protocol].remove(int(port))
            print("Port "+port+" on protocol "+protocol+" with "+ip+" Close")
        else:
            print("Port already close")
    firewall[ip][protocol].sort()

    os.system("mv firewall.yml firewall.yml.old")
    with open('firewall.yml','w') as f:
        yaml.dump(firewall,f)
        



