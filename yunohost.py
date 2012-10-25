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
if not __debug__:
    import traceback


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
        if isinstance(v, list) and len(v) == 1:
            v = v[0]
        if isinstance(v, dict):
            print(("  ") * depth + ("%s: " % k))
            pretty_print_dict(v, depth+1)
        elif isinstance(v, list):
            print(("  ") * depth + ("%s: " % k))
            for value in v:
                print(("  ") * (depth+1) + "- " + value)
        else:
            print(("  ") * depth + "%s: %s" % (k, v))
            
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


def validate(pattern, array):
    """ 
    Validate attributes with a pattern 
    
    Keyword arguments:
        pattern -- Regex to match with the strings
        array -- List of strings to check

    Returns:
        Boolean | YunoHostError

    """
    if isinstance(array, str):
        array = [array]
    for string in array:
        if re.match(pattern, string):
            pass
        else:
            raise YunoHostError(22, _('Invalid attribute') + ' ' + string)
        return True

def get_required_args(args, required_args, password=False):
    """ 
    Input missing values or raise Exception
    
    Keyword arguments:
       args -- Available arguments
       required_args -- Dictionary of required arguments and input phrase
       password -- True|False Hidden password double-input needed

    Returns:
        args

    """
    try:
        for arg, phrase in required_args.items():
            if not args[arg] and arg != 'password':
                if os.isatty(1):
                    args[arg] = raw_input(colorize(phrase + ': ', 'cyan'))
                else:
                    raise Exception #FIX
        # Password
        if 'password' in required_args and password: 
            if not args['password']:
                if os.isatty(1):
                    args['password'] = getpass.getpass(colorize(required_args['password'] + ': ', 'cyan'))
                    pwd2 = getpass.getpass(colorize('Retype ' + required_args['password'][0].lower() + required_args['password'][1:] + ': ', 'cyan'))
                    if args['password'] != pwd2:
                        raise YunoHostError(22, _("Passwords doesn't match"))
                else:
                    raise YunoHostError(22, _("Missing arguments"))
    except KeyboardInterrupt, EOFError:
        raise YunoHostError(125, _("Interrupted"))

    return args


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

def singleton(cls):
    instances = {}
    def get_instance():
        if cls not in instances:
            instances[cls] = cls()
        return instances[cls]
    return get_instance

@singleton
class YunoHostLDAP(object):
    """ Specific LDAP functions for YunoHost """

    def __enter__(self, password=False):
        self.__init__(password)
        return self

    def __init__(self, password=False):
        """ 
        Connect to LDAP base 
        
        Initialize to localhost, base yunohost.org, prompt for password

        """
        self.conn = ldap.initialize('ldap://localhost:389')
        self.base = 'dc=yunohost,dc=org'
        if password:
            self.pwd = password
        else:
            try:
                self.pwd = getpass.getpass(colorize(_('Admin Password: '), 'yellow'))
            except KeyboardInterrupt, EOFError:
                raise YunoHostError(125, _("Interrupted"))
        try:
            self.conn.simple_bind_s('cn=admin,' + self.base, self.pwd)
        except ldap.INVALID_CREDENTIALS:
            raise YunoHostError(13, _('Invalid credentials'))

    def __exit__(self, type, value, traceback):
        self.disconnect()

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
                if attrs != None:
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

    def remove(self, rdn):
        """ 
        Remove LDAP entry 
        
        Keyword arguments:
            rdn         -- DN without domain

        Returns:
            Boolean | YunoHostError

        """
        dn = rdn + ',' + self.base
        try:
            self.conn.delete_s(dn)
        except:
            raise YunoHostError(169, _('An error occured during LDAP entry deletion'))
        else:
            return True


    def update(self, rdn, attr_dict, new_rdn=False):
        """ 
        Modify LDAP entry 
        
        Keyword arguments:
            rdn         -- DN without domain
            attr_dict   -- Dictionnary of attributes/values to add
            new_rdn     -- New RDN for modification

        Returns:
            Boolean | YunoHostError

        """
        dn = rdn + ',' + self.base
        actual_entry = self.search(base=dn, attrs=None)
        ldif = modlist.modifyModlist(actual_entry[0], attr_dict, ignore_oldexistent=1)

        try:
            if new_rdn:
                self.conn.rename_s(dn, new_rdn)
                dn = new_rdn + ',' + self.base

            self.conn.modify_ext_s(dn, ldif)
        except:
            raise YunoHostError(169, _('An error occured during LDAP entry update'))
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
