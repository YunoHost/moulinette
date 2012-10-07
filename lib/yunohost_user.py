# -*- coding: utf-8 -*-

import sys
import ldap
import yunohost_ldap
import yunohost_messages as msg
import crypt
import random
import string
import getpass

# Initialize LDAP
yldap = yunohost_ldap.YunoHostLDAP()

def user_list(args): # TODO : fix
    result = yldap.search()
    print(result)


def user_add(args):
    """
    Add user to LDAP

    Keyword argument:
        args -- Dictionnary of values (can be empty)

    Returns:
        Boolean
    """
    required_args = ['username', 'mail', 'firstname', 'lastname']

    # Input missing values
    try:
        for arg in required_args:
            if not args[arg]:
                args[arg] = raw_input(arg.capitalize()+': ')
    
        if not args['password']:
            args['password'] = getpass.getpass()
            pwd2 = getpass.getpass('Retype password:')
            if args['password'] != pwd2:
                print(msg.error + _("Passwords doesn't match"))
                sys.exit(msg.EINVAL)
    except KeyboardInterrupt, EOFError:
        print("\n" + msg.interrupt + _("User not created"))
        sys.exit(msg.ECANCELED)

    # Manage values
    fullname = args['firstname'] + ' ' + args['lastname']
    rdn = 'cn=' + fullname + ',ou=users'
    char_set = string.ascii_uppercase + string.digits
    salt = ''.join(random.sample(char_set,8))
    salt = '$1$' + salt + '$'
    pwd = "{CRYPT}" + crypt.crypt(str(args['password']), salt)
    attr_dict = {
        'objectClass'   : ['mailAccount', 'inetOrgPerson'],
        'givenName'     : args['firstname'],
        'sn'            : args['lastname'],
        'displayName'   : fullname,
        'cn'            : fullname,
        'uid'           : args['username'],
        'mail'          : args['mail'],
        'userPassword'  : pwd
    }

    # Validate values
    yldap.validate({
        args['username']    : r'^[a-z0-9_]+$', 
        args['mail']        : r'^[\w.-]+@[\w.-]+\.[a-zA-Z]{2,6}$'
    })

    yldap.validate_uniqueness({
        'uid'       : args['username'],
        'cn'        : fullname,
        'mail'      : args['mail'],
        'mailalias' : args['mail']
    })

    if yldap.add(rdn, attr_dict):
        print('\n ' + msg.success + _('User successfully created') + '\n')
        for attr, value in attr_dict.items():
            if attr != 'objectClass':
                print('\033[35m\033[1m ' + attr + ': \033[m' + value)
        return True
    else:
        print(msg.error + _('An error occured during user creation'))
        return False
