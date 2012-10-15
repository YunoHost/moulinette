# -*- coding: utf-8 -*-

import os
import sys
import ldap
import crypt
import random
import string
import getpass
from yunohost import YunoHostError, win_msg, colorize, validate

def user_list(args, connections): # TODO : fix
    print(args)


def user_create(args, connections):
    """
    Add user to LDAP

    Keyword argument:
        args -- Dictionnary of values (can be empty)

    Returns:
        Boolean
    """
    yldap = connections['ldap']
    required_args = ['username', 'mail', 'firstname', 'lastname']

    # Input missing values
    try:
        for arg in required_args:
            if not args[arg]:
                if os.isatty(1):
                    args[arg] = raw_input(colorize(arg.capitalize()+': ', 'cyan'))
                else:
                    raise Exception
        # Password
        if not args['password']:
            if os.isatty(1):
                args['password'] = getpass.getpass(colorize('Password: ', 'cyan'))
                pwd2 = getpass.getpass(colorize('Retype password:', 'cyan'))
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

    # Validate values TODO: validate other values
    validate({
        args['username']    : r'^[a-z0-9_]+$', 
        args['mail']        : r'^[\w.-]+@[\w.-]+\.[a-zA-Z]{2,6}$'
    })

    yldap.validate_uniqueness({
        'uid'       : args['username'],
        'cn'        : fullname,
        'mail'      : args['mail'],
        'mailalias' : args['mail']
    })

    #TODO: check if mail belongs to a domain

    if yldap.add(rdn, attr_dict):
        win_msg(_("User successfully created"))
        #TODO: Send a welcome mail to user
        return { _("Fullname") : fullname, _("Username") : args['username'], _("Mail") : args['mail'] }
    else:
        raise YunoHostError(169, _('An error occured during user creation'))
