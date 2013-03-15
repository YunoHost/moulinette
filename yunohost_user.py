# -*- coding: utf-8 -*-

import os
import sys
import ldap
import crypt
import random
import string
import getpass
from yunohost import YunoHostError, YunoHostLDAP, win_msg, colorize, validate, get_required_args

def user_list(fields=None, filter=None, limit=None, offset=None):
    """
    List YunoHost users from LDAP

    Keyword argument:
        fields -- Fields to fetch
        filter -- LDAP filter to use
        limit  -- Number of user to fetch
        offset -- User number to begin with

    Returns:
        Dict
    """
    with YunoHostLDAP() as yldap:
        user_attrs = ['uid', 'mail', 'cn', 'mailalias']
        attrs = []
        result_list = []
        if offset: offset = int(offset)
        else: offset = 0
        if limit: limit = int(limit)
        else: limit = 1000
        if not filter: filter = 'uid=*'
        if fields:
            for attr in fields.items():
                if attr in user_attrs:
                    attrs.append(attr)
                    continue
                else:
                    raise YunoHostError(22, _("Invalid field : ") + attr)
        else:
            attrs = user_attrs

        result = yldap.search('ou=users,dc=yunohost,dc=org', filter, attrs)

        if result and len(result) > (0 + offset) and limit > 0:
            i = 0 + offset
            for user in result[i:]:
                if i - offset < limit:
                    entry = {
                        'Username': user['uid'][0],
                        'Fullname': user['cn'][0],
                        'Mail': user['mail'][0]
                    }
                    if len(user['mail']) > 1:
                        entry['Mail Forward'] = user['mail'][1:]
                    if 'mailalias' in user:
                        entry['Mail Aliases'] = user['mailalias']

                    result_list.append(entry)
                    i += 1
        else:
            raise YunoHostError(167, _("No user found"))

    return { 'Users' : result_list }


def user_create(username, firstname, lastname, mail, password):
    """
    Add user to LDAP

    Keyword argument:
        username
        firstname
        lastname
        password

    Returns:
        Dict
    """
    with YunoHostLDAP() as yldap:
        # Validate password length
        if len(password) < 4:
            raise YunoHostError(22, _("Password is too short"))

        yldap.validate_uniqueness({
            'uid'       : username,
            'mail'      : mail,
            'mailalias' : mail
        })

        # Check if unix user already exists (doesn't work)
        #if not os.system("getent passwd " + username):
        #    raise YunoHostError(17, _("Username not available"))

        #TODO: check if mail belongs to a domain

        # Get random UID/GID
        uid_check = gid_check = 0
        while uid_check == 0 and gid_check == 0:
            uid = str(random.randint(200, 99999))
            uid_check = os.system("getent passwd " + uid)
            gid_check = os.system("getent group " + uid)

        # Adapt values for LDAP
        fullname = firstname + ' ' + lastname
        rdn = 'uid=' + username + ',ou=users'
        char_set = string.ascii_uppercase + string.digits
        salt = ''.join(random.sample(char_set,8))
        salt = '$1$' + salt + '$'
        pwd = '{CRYPT}' + crypt.crypt(str(password), salt)
        attr_dict = {
            'objectClass'   : ['mailAccount', 'inetOrgPerson', 'posixAccount'],
            'givenName'     : firstname,
            'sn'            : lastname,
            'displayName'   : fullname,
            'cn'            : fullname,
            'uid'           : username,
            'mail'          : mail,
            'userPassword'  : pwd,
            'gidNumber'     : uid,
            'uidNumber'     : uid,
            'homeDirectory' : '/home/' + username,
            'loginShell'    : '/bin/false'
        }

        if yldap.add(rdn, attr_dict):
            # Create user /home directory by switching user
            os.system("su - " + username + " -c ''")
            #TODO: Send a welcome mail to user
            win_msg(_("User successfully created"))
            return { _("Fullname") : fullname, _("Username") : username, _("Mail") : mail }
        else:
            raise YunoHostError(169, _("An error occured during user creation"))


def user_delete(users, purge=None):
    """
    Remove user from LDAP

    Keyword argument:
        users -- List of users to delete or single user
        purge -- Whether or not purge /home/user directory

    Returns:
        Dict
    """
    with YunoHostLDAP() as yldap:
        result = { 'Users' : [] }

        if not isinstance(users, list):
            users = [ users ]

        for user in users:
            if yldap.remove('uid=' + user+ ',ou=users'):
                if purge:
                    os.system('rm -rf /home/' + user)
                result['Users'].append(user)
                continue
            else:
                raise YunoHostError(169, _("An error occured during user deletion"))

        win_msg(_("User(s) successfully deleted"))
    return result


def user_update(username, firstname=None, lastname=None, mail=None, change_password=None,
        add_mailforward=None, remove_mailforward=None,
        add_mailalias=None, remove_mailalias=None):
    """
    Update user informations

    Keyword argument:
        username -- Username to update
        firstname
        lastname
        mail
        change_password -- New password
        add_mailforward
        remove_mailforward
        add_mailalias
        remove_mailalias

    Returns:
        Dict
    """
    with YunoHostLDAP() as yldap:
        attrs_to_fetch = ['givenName', 'sn', 'mail', 'mailAlias']
        new_attr_dict = {}

        # Populate user informations
        result = yldap.search(base='ou=users,dc=yunohost,dc=org', filter='uid=' + username, attrs=attrs_to_fetch)
        if not result:
            raise YunoHostError(167, _("No user found"))
        user = result[0]

        # Get modifications from arguments
        if firstname:
            new_attr_dict['givenName'] = firstname # TODO: Validate
            new_attr_dict['cn'] = new_attr_dict['displayName'] = firstname + ' ' + user['sn'][0]

        if lastname:
            new_attr_dict['sn'] = lastname # TODO: Validate
            new_attr_dict['cn'] = new_attr_dict['displayName'] = user['givenName'][0] + ' ' + lastname

        if lastname and firstname:
            new_attr_dict['cn'] = new_attr_dict['displayName'] = firstname + ' ' + lastname

        if change_password:
            char_set = string.ascii_uppercase + string.digits
            salt = ''.join(random.sample(char_set,8))
            salt = '$1$' + salt + '$'
            new_attr_dict['userPassword'] = '{CRYPT}' + crypt.crypt(str(change_password), salt)

        if mail:
            yldap.validate_uniqueness({
                'mail'      : mail,
                'mailalias' : mail
            })
            del user['mail'][0]
            new_attr_dict['mail'] = [mail] + user['mail']

        if add_mailforward:
            if not isinstance(add_mailforward, list):
                add_mailforward = [ add_mailforward ]
            for mail in add_mailforward:
                yldap.validate_uniqueness({
                    'mail'      : mail,
                    'mailalias' : mail
                })
                user['mail'].append(mail)
            new_attr_dict['mail'] = user['mail']

        if remove_mailforward:
            if not isinstance(remove_mailforward, list):
                remove_mailforward = [ remove_mailforward ]
            for mail in remove_mailforward:
                if len(user['mail']) > 1 and mail in user['mail'][1:]:
                    user['mail'].remove(mail)
                else:
                    raise YunoHostError(22, _("Invalid mail forward : ") + mail)
            new_attr_dict['mail'] = user['mail']

        if add_mailalias:
            if not isinstance(add_mailalias, list):
                add_mailalias = [ add_mailalias ]
            for mail in add_mailalias:
                yldap.validate_uniqueness({
                    'mail'      : mail,
                    'mailalias' : mail
                })
                if 'mailalias' in user:
                    user['mailalias'].append(mail)
                else:
                    user['mailalias'] = [ mail ]
            new_attr_dict['mailalias'] = user['mailalias']

        if remove_mailalias:
            if not isinstance(remove_mailalias, list):
                remove_mailalias = [ remove_mailalias ]
            for mail in remove_mailalias:
                if 'mailalias' in user and mail in user['mailalias']:
                    user['mailalias'].remove(mail)
                else:
                    raise YunoHostError(22, _("Invalid mail alias : ") + mail)
            new_attr_dict['mailalias'] = user['mailalias']

        if yldap.update('uid=' + username + ',ou=users', new_attr_dict):
           win_msg(_("User successfully updated"))
           return user_info(username)
        else:
           raise YunoHostError(169, _("An error occured during user update"))



def user_info(user_or_mail):
    """
    Fetch user informations from LDAP

    Keyword argument:
        username
        mail

    Returns:
        Dict
    """
    with YunoHostLDAP() as yldap:
        user_attrs = ['cn', 'mail', 'uid', 'mailAlias']

        if len(user_or_mail.split('@')) is 2:
            filter = '(|(mail='+ user_or_mail +')(mailalias='+ user_or_mail +'))'
        else:
            filter = 'uid='+ user_or_mail

        result = yldap.search('ou=users,dc=yunohost,dc=org', filter, user_attrs)

        if result:
            user = result[0]
        else:
            raise YunoHostError(22, _("Unknown user/mail"))

        result_dict = {
            'Username': user['uid'],
            'Fullname': user['cn'],
            'Mail': user['mail'][0]
        }

        if len(user['mail']) > 1:
            result_dict['Mail Forward'] = user['mail'][1:]

        if 'mailalias' in user:
            result_dict['Mail Aliases'] = user['mailalias']

        if result:
            return result_dict
        else:
            raise YunoHostError(167, _("No user found"))

