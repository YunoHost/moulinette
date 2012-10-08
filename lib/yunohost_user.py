# -*- coding: utf-8 -*-

import os
import sys
import ldap
import crypt
import random
import string
import getpass
from yunohost import YunoHostError, YunoHostLDAP, win_msg

# Initialize LDAP
yldap = YunoHostLDAP()

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
                if os.isatty(1):
                    args[arg] = raw_input(arg.capitalize()+': ')
                else:
                    raise Exception
        # Password
        if not args['password']:
            if os.isatty(1):
                args['password'] = getpass.getpass()
                pwd2 = getpass.getpass('Retype password:')
                if args['password'] != pwd2:
                    raise YunoHostError(22, _("Passwords doesn't match"))
            else:
                raise YunoHostError(22, _("Missing arguments"))
    except KeyboardInterrupt, EOFError:
        raise YunoHostError(125, _("Interrupted, user not created"))

    # Manage values
    fullname = args['firstname'] + ' ' + args['lastname']
    rdn = 'cn=' + fullname + ',ou=users'
    char_set = string.ascii_uppercase + string.digits
    salt = ''.join(random.sample(char_set,8))
    salt = '$1$' + salt + '$'
    pwd = '{CRYPT}' + crypt.crypt(str(args['password']), salt)
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
        win_msg(_("User successfully created"))
        return attr_dict
    else:
        raise YunoHostError(169, _('An error occured during user creation'))
