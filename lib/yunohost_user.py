# -*- coding: utf-8 -*-

import sys
import ldap
import ldap.modlist as modlist
import yunohost_ldap
import yunohost_messages as msg
import getpass

# Initialize LDAP
yldap = yunohost_ldap.YunoHostLDAP()

def user_list(args): # TODO : fix
    result = yldap.search()
    print(result)


def user_add(args):
    required_args = ['username', 'mail', 'firstname', 'lastname']

    try:
        for arg in required_args:
            if not args[arg]:
                args[arg] = raw_input(arg.capitalize()+': ')
    
        if not args['password']:
            args['password'] = getpass.getpass()
            pwd2 = getpass.getpass('Retype password:')
            if args['password'] != pwd2:
                print(msg.error + _("Passwords doesn't match"))
                sys.exit(1)
    except KeyboardInterrupt, EOFError:
        print("\n" + msg.interrupt + _("User not created"))
        sys.exit(1)


    print(args)

