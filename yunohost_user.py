# -*- coding: utf-8 -*-

""" License

    Copyright (C) 2013 YunoHost

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published
    by the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program; if not, see http://www.gnu.org/licenses

"""

""" yunohost_user.py

    Manage users
"""
import os
import sys
import ldap
import crypt
import random
import string
import getpass
from yunohost import YunoHostError, YunoHostLDAP, win_msg, colorize, validate, get_required_args
from yunohost_domain import domain_list
from yunohost_hook import hook_callback

def user_list(fields=None, filter=None, limit=None, offset=None):
    """
    List users

    Keyword argument:
        filter -- LDAP filter used to search
        offset -- Starting number for user fetching
        limit -- Maximum number of user fetched
        fields -- fields to fetch

    """
    with YunoHostLDAP() as yldap:
        user_attrs = ['uid', 'mail', 'cn', 'maildrop']
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
                    if user['uid'][0] == 'root' or user['uid'][0] == 'nobody':
                        continue
                    entry = {
                        'Username': user['uid'][0],
                        'Fullname': user['cn'][0],
                    }
                    if 'mail' in user.keys():
                        entry['Mail'] = user['mail'][0]

                    result_list.append(entry)
                    i += 1

    return { 'Users' : result_list }


def user_create(username, firstname, lastname, mail, password):
    """
    Create user

    Keyword argument:
        firstname
        lastname
        username -- Must be unique
        mail -- Main mail address must be unique
        password

    """
    with YunoHostLDAP() as yldap:
        # Validate password length
        if len(password) < 4:
            raise YunoHostError(22, _("Password is too short"))

        yldap.validate_uniqueness({
            'uid'       : username,
            'mail'      : mail
        })

        if mail[mail.find('@')+1:] not in domain_list()['Domains']:
            raise YunoHostError(22, _("Domain not found : ")+ mail[mail.find('@')+1:])

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
            'maildrop'      : username,
            'userPassword'  : pwd,
            'gidNumber'     : uid,
            'uidNumber'     : uid,
            'homeDirectory' : '/home/' + username,
            'loginShell'    : '/bin/false'
 
        }

        if yldap.add(rdn, attr_dict):
            os.system("su - " + username + " -c ''")
            #TODO: Send a welcome mail to user
            win_msg(_("User successfully created"))
            hook_callback('post_user_create', [username, mail, password, firstname, lastname])

            return { _("Fullname") : fullname, _("Username") : username, _("Mail") : mail }
        else:
            raise YunoHostError(169, _("An error occured during user creation"))


def user_delete(users, purge=False):
    """
    Delete user

    Keyword argument:
        users -- Username of users to delete
        purge

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

        os.system('yunohost app ssowatconf > /dev/null 2>&1')
        win_msg(_("User(s) successfully deleted"))
    return result


def user_update(username, firstname=None, lastname=None, mail=None, change_password=None, add_mailforward=None, remove_mailforward=None, add_mailalias=None, remove_mailalias=None):
    """
    Update user informations

    Keyword argument:
        lastname
        mail
        firstname
        add_mailalias -- Mail aliases to add
        remove_mailforward -- Mailforward addresses to remove
        username -- Username of user to update
        add_mailforward -- Mailforward addresses to add
        change_password -- New password to set
        remove_mailalias -- Mail aliases to remove

    """
    with YunoHostLDAP() as yldap:
        attrs_to_fetch = ['givenName', 'sn', 'mail', 'maildrop']
        new_attr_dict = {}
        domains = domain_list()['Domains']

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
            yldap.validate_uniqueness({ 'mail': mail })
            if mail[mail.find('@')+1:] not in domains:
                raise YunoHostError(22, _("Domain not found : ")+ mail[mail.find('@')+1:])
            del user['mail'][0]
            new_attr_dict['mail'] = [mail] + user['mail']

        if add_mailalias:
            if not isinstance(add_mailalias, list):
                add_mailalias = [ add_mailalias ]
            for mail in add_mailalias:
                yldap.validate_uniqueness({ 'mail': mail })
                if mail[mail.find('@')+1:] not in domains:
                    raise YunoHostError(22, _("Domain not found : ")+ mail[mail.find('@')+1:])
                user['mail'].append(mail)
            new_attr_dict['mail'] = user['mail']

        if remove_mailalias:
            if not isinstance(remove_mailalias, list):
                remove_mailalias = [ remove_mailalias ]
            for mail in remove_mailalias:
                if len(user['mail']) > 1 and mail in user['mail'][1:]:
                    user['mail'].remove(mail)
                else:
                    raise YunoHostError(22, _("Invalid mail alias : ") + mail)
            new_attr_dict['mail'] = user['mail']

        if add_mailforward:
            if not isinstance(add_mailforward, list):
                add_mailforward = [ add_mailforward ]
            for mail in add_mailforward:
		if mail in user['maildrop'][1:]:
		    continue
                user['maildrop'].append(mail)
            new_attr_dict['maildrop'] = user['maildrop']

        if remove_mailforward:
            if not isinstance(remove_mailforward, list):
                remove_mailforward = [ remove_mailforward ]
            for mail in remove_mailforward:
                if len(user['maildrop']) > 1 and mail in user['maildrop'][1:]:
                    user['maildrop'].remove(mail)
                else:
                    raise YunoHostError(22, _("Invalid mail forward : ") + mail)
            new_attr_dict['maildrop'] = user['maildrop']

        if yldap.update('uid=' + username + ',ou=users', new_attr_dict):
           win_msg(_("User successfully updated"))
           return user_info(username)
        else:
           raise YunoHostError(169, _("An error occured during user update"))



def user_info(username):
    """
    Get user informations

    Keyword argument:
        username -- Username or mail to get informations

    """
    with YunoHostLDAP() as yldap:
        user_attrs = ['cn', 'mail', 'uid', 'maildrop', 'givenName', 'sn']

        if len(username.split('@')) is 2:
            filter = 'mail='+ username
        else:
            filter = 'uid='+ username

        result = yldap.search('ou=users,dc=yunohost,dc=org', filter, user_attrs)

        if result:
            user = result[0]
        else:
            raise YunoHostError(22, _("Unknown user/mail : ") + username)

        result_dict = {
            'Username': user['uid'][0],
            'Fullname': user['cn'][0],
            'Firstname': user['givenName'][0],
            'Lastname': user['sn'][0],
            'Mail': user['mail'][0]
        }

        if len(user['mail']) > 1:
            result_dict['Mail Aliases'] = user['mail'][1:]

        if len(user['maildrop']) > 1:
            result_dict['Mail Forward'] = user['maildrop'][1:]

        if result:
            return result_dict
        else:
            raise YunoHostError(167, _("No user found"))

