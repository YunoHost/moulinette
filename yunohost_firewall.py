# -*- coding: utf-8 -*-

import os
import sys
try:
    import yaml
except ImportError:
    sys.stderr.write('Error: Yunohost CLI Require yaml lib\n')
    sys.stderr.write('apt-get install python-yaml\n')
    sys.exit(1)

def firewall_allow(protocol=None,port=None):
    if protocol == "Both":
    chaineTCP="iptables -A INPUT -p tcp -i eth0 --dport "+ port +" -j ACCEPT"
	chaineUDP="iptables -A INPUT -p udp -i eth0 --dport "+ port +" -j ACCEPT"
	append_port(port,'tcp')
	append_port(port,'udp')
	os.system(chaineTCP)
	os.system(chaineUDP)

    else:
        chaine="iptables -A INPUT -p "+ protocol +" -i eth0 --dport "+ port +" -j ACCEPT"
        append_port(port,protocol)
        os.system(chaine)

def firewall_disallow(protocol=None,port=None):
    if protocol == "Both":
        chaineTCP="iptables -A INPUT -p tcp -i eth0 --dport "+ port +" -j REJECT"
        chaineUDP="iptables -A INPUT -p udp -i eth0 --dport "+ port +" -j REJECT"
        remove_port(port,'tcp')
        remove_port(port,'udp')
        os.system(chaineTCP)
        os.system(chaineUDP)
    else:
        chaine="iptables -A INPUT -p "+ protocol +" -i eth0 --dport "+ port +" -j REJECT"
        os.system(chaine)
        remove_port(port,protocol)
        os.system(chaine)

def firewall_list():
    '''
	Parse and display firwall.yml
	'''
    with open ('firewall.yml') as f:
                firewall = yaml.load(f)
                listPortTCP=firewall['ipv4']['TCP']
                listPortUDP=firewall['ipv4']['UDP']
                print("Port TCP OPEN :")
        for i,port in enumerate (listPortTCP):
                print("-"+str(port))
        print("Port UDP OPEN :")
        for i,port in enumerate (listPortUDP):
                print("-"+str(port))
	f.close()
        
def firewall_reload():
    '''
	Clear filter IPTABLE's table
	Allow SSH
	Parse firewall.yml extract the list of port allowed
	Allow all port in the list
	Prohibit the rest
	'''
    os.system("iptables -P INPUT ACCEPT")
    os.system ("iptables -F")
    os.system ("iptables -X")
    os.system ("iptables -A INPUT -p tcp -i eth0 --dport 22 -j ACCEPT")
    with open('firewall.yml','r') as f:
        firewall = yaml.load(f)
    listPortTCP=firewall['ipv4']["TCP"]
    listPortUDP=firewall['ipv4']["UDP"]
    for i,port in enumerate (listPortTCP):
        os.system ("iptables -A INPUT -p tcp -i eth0 --dport "+ str(port) +" -j ACCEPT")
    for i,port in enumerate (listPortUDP):
        os.system ("iptables -A INPUT -p udp -i eth0 --dport "+ str(port) +" -j ACCEPT")
        os.system ("iptables -P INPUT DROP")

def append_port(port=None,protocol=None):
    '''
	Append port in firewall.yml
	'''
    with open('firewall.yml','r') as f:
        firewall = yaml.load(f)
		if port not in firewall['ipv4'][protocol]:
			firewall['ipv4'][protocol].append(int(port))
			firewall['ipv4'][protocol].sort()
        f.close
    os.system("mv firewall.yml firewall.yml.old")
    with open('firewall.yml','w') as f:
        yaml.dump(firewall,f)
        f.close


def remove_port(port=None,protocol=None):
    '''
	Remove port from firewall.yml
	'''
    with open('firewall.yml','r') as f:
        firewall = yaml.load(f)
        if port in firewall['ipv4'][protocol]:
			firewall['ipv4'][protocol].remove(int(port))
			firewall['ipv4'][protocol].sort()
        f.close
    os.system("mv firewall.yml firewall.yml.old")
    with open('firewall.yml','w') as f:
        yaml.dump(firewall,f)
        f.close
