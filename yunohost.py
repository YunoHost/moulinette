# -*- coding: utf-8 -*-

import os
import sys
try:
    import ldap
except ImportError:
    sys.stderr.write('Error: Yunohost CLI Require LDAP lib\n')
    sys.stderr.write('apt-get install python-ldap\n')
    sys.exit(1)
import ldap.modlist as modlist
import json
import re
import getpass


def colorize(astr, color):
    """ 
    Print with style ;) 
    
    Keyword arguments:
        astr    -- String to colorize
        color   -- Name of the color

    """
    color_dict = {
        'red'   : '31',
        'green' : '32',
        'yellow': '33',
        'cyan'  : '34',
        'purple': '35'
    }
    return "\033["+ color_dict[color] +"m\033[1m" + astr + "\033[m" 

def pretty_print_dict(d, depth=0):
    for k,v in sorted(d.items(), key=lambda x: x[0]):
        k = colorize(k, 'purple')
        if isinstance(v, dict):
            print(("  ")*depth + ("%s: " % k))
            pretty_print_dict(v, depth+1)
        if isinstance(v, list):
            print(("  ")*depth + ("%s: " % k))
            for value in v:
                print(("  ")*(depth+1) + "- " + value)
        else:
            print(("  ")*depth + "%s: %s" % (k, v))
            
def win_msg(astr):
    """ 
    Display a success message if isatty 
    
    Keyword arguments:
        astr -- Win message to display

    """
    if os.isatty(1):
        print('\n' + colorize(_("Success: "), 'green') + astr + '\n')


def str_to_func(astr):
    """
    Call a function from a string name
    
    Keyword arguments:
        astr -- Name of function to call
    
    Returns: 
        Function

    """
    try:
        module, _, function = astr.rpartition('.')
        if module:
            __import__(module)
            mod = sys.modules[module]
        else:
            mod = sys.modules['__main__']  # default module
    
        func = getattr(mod, function)
    except (AttributeError, ImportError):
        #raise YunoHostError(168, _('Function is not defined'))
        return None
    else:
        return func


def validate(regex_dict):
    """ 
    Validate attributes with a pattern 
    
    Keyword arguments:
        regex_dict -- Dictionnary of values/pattern to check

    Returns:
        Boolean | YunoHostError

    """
    for attr, pattern in regex_dict.items():
        if re.match(pattern, attr):
            continue
        else:
            raise YunoHostError(22, _('Invalid attribute') + ' ' + attr)
    return True


def display_error(error):
    """
    Nice error displaying

    """
    if not __debug__ :
        traceback.print_exc()
    if os.isatty(1):
        print('\n' + colorize(_("Error: "), 'red') + error.message)
    else:
        print(json.dumps({ 'error' : error.message }))


def connect_services(action_map):
    """
    Connect to different services needed by the action

    Keyword arguments:
        action_map -- Map of actions

    Returns:
        Dict -- openned connections or error code

    """
    action_dict = action_map[sys.argv[1]]['actions'][sys.argv[2]]
    connections = {}
    required_connections = []

    if 'connections' in action_dict:
        required_connections = action_dict['connections']
    
    try:
        # Connect to different services if the action is requiring it
        if 'ldap' in required_connections:
            connections['ldap'] = YunoHostLDAP()
        if 'firewall' in required_connections:
            connections['firewall'] = open('/etc/init.d/iptables', 'w')
        # TODO: Add other services connections
    except YunoHostError, error:
        display_error(error)
        sys.exit(error.code)
    else:
        return connections
        

def disconnect_services(connections):
    """
    Disconnect openned connections

    Keyword arguments:
        connections -- Dictionnary of openned connections

    Returns:
        Boolean

    """
    try:
        if 'ldap' in connections:
            connections['ldap'].disconnect()
        if 'firewall' in connections:
            connections['firewall'].close()
        # TODO: Add other services deconnections 
    except YunoHostError, error:
        display_error(error)
        sys.exit(error.code)
    else:
        return True


class YunoHostError(Exception):
    """
    Custom exception
    
    Keyword arguments:
        code    -- Integer error code
        message -- Error message to display

    """
    def __init__(self, code, message):
        code_dict = {
            1   : _('Fail'),
            13  : _('Permission denied'),
            17  : _('Already exists'),
            22  : _('Invalid arguments'),
            87  : _('Too many users'),
            111 : _('Connection refused'),
            122 : _('Quota exceeded'),
            125 : _('Operation canceled'),
            167 : _('Not found'),
            168 : _('Undefined'),
            169 : _('LDAP operation error')
        }
        self.code = code
        self.message = message
        if code_dict[code]:
            self.desc = code_dict[code]
        else:
            self.desc = code


class YunoHostLDAP:
    """ Specific LDAP functions for YunoHost """

    def __init__(self):
        """ 
        Connect to LDAP base 
        
        Initialize to localhost, base yunohost.org, prompt for password

        """
        self.conn = ldap.initialize('ldap://localhost:389')
        self.base = 'dc=gavoty,dc=org'
        self.pwd = getpass.getpass(colorize(_('LDAP Admin Password: '), 'yellow'))
        try:
            self.conn.simple_bind_s('cn=admin,' + self.base, self.pwd)
        except ldap.INVALID_CREDENTIALS:
            raise YunoHostError(13, _('Invalid credentials'))


    def disconnect(self):
        """ 
        Unbind from LDAP 
        
        Returns
            Boolean | YunoHostError

        """
        try:
            self.conn.unbind_s()
        except:
            raise YunoHostError(169, _('An error occured during disconnection'))
        else:
            return True


    def search(self, base=None, filter='(objectClass=*)', attrs=['dn']):
        """  
        Search in LDAP base 
        
        Keyword arguments:
            base    -- Base to search into
            filter  -- LDAP filter
            attrs   -- Array of attributes to fetch

        Returns:
            Boolean | Dict

        """
        if not base:
            base = self.base

        try:
            result = self.conn.search_s(base, ldap.SCOPE_SUBTREE, filter, attrs)
        except:
            raise YunoHostError(169, _('An error occured during LDAP search'))

        if result:
            result_list = []
            for dn, entry in result:
                if 'dn' in attrs:
                    entry['dn'] = [dn]
                result_list.append(entry)
            return result_list       
        else:
            return False


    def add(self, rdn, attr_dict):
        """ 
        Add LDAP entry 
        
        Keyword arguments:
            rdn         -- DN without domain
            attr_dict   -- Dictionnary of attributes/values to add

        Returns:
            Boolean | YunoHostError

        """
        dn = rdn + ',' + self.base
        ldif = modlist.addModlist(attr_dict)

        try:
            self.conn.add_s(dn, ldif)
        except:
            raise YunoHostError(169, _('An error occured during LDAP entry creation'))
        else:
            return True


    def validate_uniqueness(self, value_dict):
        """ 
        Check uniqueness of values 
        
        Keyword arguments:
            value_dict -- Dictionnary of attributes/values to check

        Returns:
            Boolean | YunoHostError

        """
        for attr, value in value_dict.items():
            if not self.search(filter=attr + '=' + value):
                continue
            else:
                raise YunoHostError(17, _('Attribute already exists') + ' "' + attr + '=' + value + '"')
        return True
