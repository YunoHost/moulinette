=================================================
Common LDAP operation (for YunoHost but not only)
=================================================

Moulinette is deeply integrated with LDAP which is used for a series of things
like:

* storing users
* storing domains (for users emails)
* SSO

This page document how to uses it on a programming side in YunoHost.

Getting access to LDAP in a command
===================================

To get access to LDAP you need to authenticate against it, for that you need to
declare your command with requiring authentication in the :ref:`actionsmap` this way:

::

    configuration:
        authenticate: all


Here is a complete example:

::

    somecommand:
        category_help: ..
        actions:

            ### somecommand_stuff()
            stuff:
                action_help: ...
                api: GET /...
                configuration:
                    authenticate: all

This will prompt the user for a password in CLI.

If you only need to **read** LDAP (and not modify it, for example by listing
domains), then you prevent the need for a password by using the
:file:`ldap-anonymous` authenticator this way:

::

    configuration:
        authenticate: all
        authenticator: ldap-anonymous


Once you have declared your command like that, your python function will
received the :file:`auth` object as first argument, it will be used to talk to
LDAP, so you need to declare your function this way:

::

    def somecommand_stuff(auth, ...):
        ...

auth in the moulinette code
---------------------------

The :file:`auth` object is an instance of :file:`moulinette.authenticators.ldap.Authenticator` class.

Here its docstring:

.. autoclass:: moulinette.authenticators.ldap.Authenticator

Reading from LDAP
=================

Reading data from LDAP is done using the :file:`auth` object received as first
argument of the python function. To see how to get this object read the
previous section.

The API looks like this:

::

    auth.search(ldap_path, ldap_query)

This will return a list of dictionary with strings as keys and list as values.

You can also specify a list of attributes you want to access from LDAP using a list of string (on only one string apparently):

::

    auth.search(ldap_path, ldap_query, ['first_attribute', 'another_attribute'])

For example, if we request the user :file:`alice` with its :file:`homeDirectory`, this would look like this:

::

    auth.search('ou=users,dc=yunohost,dc=org', '(&(objectclass=person)(uid=alice))', ['homeDirectory', 'another_attribute'])

And as a result we will get:

::

    [{'homeDirectory': ['/home/alice']}]

Notice that even for a single result we get a **list** of result and that every
value in the dictionary is also a **list** of values. This is not really convenient and it would be better to have a real ORM, but for now we are stuck with that.

Apparently if we don't specify the list of attributes it seems that we get all attributes (need to be confirmed).

Here is the method docstring:

.. automethod:: moulinette.authenticators.ldap.Authenticator.search

Users LDAP schema
-----------------

According to :file:`ldapvi` this is the user schema (on YunoHost 2.7):

::

    # path: uid=the_unix_username,ou=users,dc=yunohost,dc=org
    uid: the_unix_username
    objectClass: mailAccount
    objectClass: inetOrgPerson
    objectClass: posixAccount
    loginShell: /bin/false
    uidNumber: 80833
    maildrop: the_unix_username  # why?
    cn: first_name last_name
    displayName: first_name last_name
    mailuserquota: some_value
    gidNumber: 80833
    sn: last_name
    homeDirectory: /home/the_unix_username
    mail: the_unix_username@domain.com
    # if the user is the admin he will also have the following mails
    mail: root@domain.com
    mail: admin@domain.com
    mail: webmaster@domain.com
    mail: postmaster@domain.com
    givenName: first_name

The admin user is a special case that looks like this:

::

    # path: cn=admin,dc=yunohost,dc=org
    gidNumber: 1007
    cn: admin
    homeDirectory: /home/admin
    objectClass: organizationalRole
    objectClass: posixAccount
    objectClass: simpleSecurityObject
    loginShell: /bin/bash
    description: LDAP Administrator
    uidNumber: 1007
    uid: admin

Other user related schemas:

::


    # path: cn=admins,ou=groups,dc=yunohost,dc=org
    objectClass: posixGroup
    objectClass: top
    memberUid: admin
    gidNumber: 4001
    cn: admins

    # path: cn=sftpusers,ou=groups,dc=yunohost,dc=org
    objectClass: posixGroup
    objectClass: top
    gidNumber: 4002
    cn: sftpusers
    memberUid: admin
    memberUid: alice
    # and all other users

    # path: cn=admin,ou=sudo,dc=yunohost,dc=org
    # this entry seems to specify which unix user is a sudoer
    cn: admin
    sudoCommand: ALL
    sudoUser: admin
    objectClass: sudoRole
    objectClass: top
    sudoOption: !authenticate
    sudoHost: ALL

Reading users from LDAP
-----------------------

The user schema is located at this path: :file:`ou=users,dc=yunohost,dc=org`

According to already existing code, the queries we uses are:

* :file:`'(&(objectclass=person)(!(uid=root))(!(uid=nobody)))'` to get all users (not that I've never encountered users with :file:`root` or :file:`nobody` uid in the ldap database, those might be there for historical reason)
* :file:`'(&(objectclass=person)(uid=%s))' % username` to access one user data

This give us the 2 following python calls:

::

    # all users
    auth.search('ou=users,dc=yunohost,dc=org', '(&(objectclass=person)(!(uid=root))(!(uid=nobody)))')

    # one user
    auth.search('ou=users,dc=yunohost,dc=org', '(&(objectclass=person)(uid=some_username))')


Apparently we could also access one user using the following path (and not query): :file:`uid=user_username,ou=users,dc=yunohost,dc=org` but I haven't test it.

If you want specific attributes look at the general documentation on how to read from LDAP a bit above of this section.

Updating LDAP data
==================

Update a user from LDAP looks like a simplified version of searching. The syntax is the following one:

::

    auth.update(exact_path_to_object, {'attribute_to_modify': 'new_value', 'another_attribute_to_modify': 'another_value', ...})

For example this will update a user :file:`loginShell`:

::

    auth.update('uid=some_username,ou=users', {'loginShell': '/bin/bash'})

I don't know how this call behave if it fails and what it returns.

Here is the method docstring:

.. automethod:: moulinette.authenticators.ldap.Authenticator.update

Updating a user in LDAP
-------------------------

This is done this way:

::

    auth.update('uid=some_username,ou=users', {'attribute': 'new_value', ...})

Refer to the user schema to know which attributes you can modify.

Validate uniqueness
===================

There is a method to validate the uniquess of some entry that is used during
user creation. I haven't used it and I'm not sure on how it work.

Here is how it's used (I don't understand why a path is not provided):

::

    # Validate uniqueness of username and mail in LDAP
    auth.validate_uniqueness({
        'uid': username,
        'mail': mail
    })

And here is its docstring:

.. automethod:: moulinette.authenticators.ldap.Authenticator.update
