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
declare you command with requiring authentication in the :ref:`actionsmap` this way:

::

    configuration:
        authenticate: all


Here is a complete example:

::

    somecommand:
        category_help: ..
        actions:

            ### somecommand_stuff()
            list:
                action_help: ...
                api: GET /...
                configuration:
                    authenticate: all

This will prompt the user for a password in CLI.

If you only need to **read** LDAP (and not modify it, for example by listing
domains), then you prevent the need for a password by using the
`ldap-anonymous` authenticator this way:

::

    configuration:
        authenticate: all
        authenticator: ldap-anonymous
