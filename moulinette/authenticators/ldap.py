# -*- coding: utf-8 -*-

# TODO: Use Python3 to remove this fix!
from __future__ import absolute_import
import os
import logging
import ldap
import ldap.sasl
import time
import ldap.modlist as modlist

from moulinette import m18n
from moulinette.core import (
    MoulinetteError,
    MoulinetteAuthenticationError,
    MoulinetteLdapIsDownError,
)
from moulinette.authenticators import BaseAuthenticator

logger = logging.getLogger("moulinette.authenticator.ldap")

# LDAP Class Implementation --------------------------------------------


class Authenticator(BaseAuthenticator):

    """LDAP Authenticator

    Initialize a LDAP connexion for the given arguments. It attempts to
    authenticate a user if 'user_rdn' is given - by associating user_rdn
    and base_dn - and provides extra methods to manage opened connexion.

    Keyword arguments:
        - uri -- The LDAP server URI
        - base_dn -- The base dn
        - user_rdn -- The user rdn to authenticate

    """

    def __init__(self, name, vendor, parameters, extra):
        self.uri = parameters["uri"]
        self.basedn = parameters["base_dn"]
        self.userdn = parameters["user_rdn"]
        self.extra = extra
        self.sasldn = "cn=external,cn=auth"
        self.adminuser = "admin"
        self.admindn = "cn=%s,dc=yunohost,dc=org" % self.adminuser
        self.admindn = "cn=%s,dc=yunohost,dc=org" % self.adminuser
        logger.debug(
            "initialize authenticator '%s' with: uri='%s', "
            "base_dn='%s', user_rdn='%s'",
            name,
            self._get_uri(),
            self.basedn,
            self.userdn,
        )
        super(Authenticator, self).__init__(name, vendor, parameters, extra)

        if self.userdn and self.sasldn in self.userdn:
            self.authenticate(None)
        else:
            self.con = None

    def __del__(self):
        """Disconnect and free ressources"""
        if hasattr(self, "con") and self.con:
            self.con.unbind_s()

    # Implement virtual properties

    vendor = "ldap"

    # Implement virtual methods

    def authenticate(self, password=None):
        def _reconnect():
            con = ldap.ldapobject.ReconnectLDAPObject(
                self._get_uri(), retry_max=10, retry_delay=0.5
            )
            if self.userdn:
                if self.sasldn in self.userdn:
                    con.sasl_non_interactive_bind_s("EXTERNAL")
                else:
                    con.simple_bind_s(self.userdn, password)
            else:
                con.simple_bind_s()

            return con

        try:
            con = _reconnect()
        except ldap.INVALID_CREDENTIALS:
            raise MoulinetteAuthenticationError("invalid_password")
        except ldap.SERVER_DOWN:
            # ldap is down, attempt to restart it before really failing
            logger.warning(m18n.g("ldap_server_is_down_restart_it"))
            os.system("systemctl restart slapd")
            time.sleep(10)  # waits 10 secondes so we are sure that slapd has restarted

            try:
                con = _reconnect()
            except ldap.SERVER_DOWN:
                raise MoulinetteLdapIsDownError("ldap_server_down")

        # Check that we are indeed logged in with the right identity
        try:
            # whoami_s return dn:..., then delete these 3 characters
            who = con.whoami_s()[3:]
        except Exception as e:
            logger.warning("Error during ldap authentication process: %s", e)
            raise
        else:
            # FIXME: During SASL bind whoami from the test server return the admindn while userdn is returned normally :
            if not (who == self.admindn or who == self.userdn):
                raise MoulinetteError("Not logged in with the expected userdn ?!")
            else:
                self.con = con

    # Additional LDAP methods
    # TODO: Review these methods

    def search(self, base=None, filter="(objectClass=*)", attrs=["dn"]):
        """Search in LDAP base

        Perform an LDAP search operation with given arguments and return
        results as a list.

        Keyword arguments:
            - base -- The dn to search into
            - filter -- A string representation of the filter to apply
            - attrs -- A list of attributes to fetch

        Returns:
            A list of all results

        """
        if not base:
            base = self.basedn

        try:
            result = self.con.search_s(base, ldap.SCOPE_SUBTREE, filter, attrs)
        except Exception as e:
            raise MoulinetteError(
                "error during LDAP search operation with: base='%s', "
                "filter='%s', attrs=%s and exception %s" % (base, filter, attrs, e),
                raw_msg=True,
            )

        result_list = []
        if not attrs or "dn" not in attrs:
            result_list = [entry for dn, entry in result]
        else:
            for dn, entry in result:
                entry["dn"] = [dn]
                result_list.append(entry)

        def decode(value):
            if isinstance(value, bytes):
                value = value.decode("utf-8")
            return value

        # result_list is for example :
        # [{'virtualdomain': [b'test.com']}, {'virtualdomain': [b'yolo.test']},
        for stuff in result_list:
            if isinstance(stuff, dict):
                for key, values in stuff.items():
                    stuff[key] = [decode(v) for v in values]

        return result_list

    def add(self, rdn, attr_dict):
        """
        Add LDAP entry

        Keyword arguments:
            rdn         -- DN without domain
            attr_dict   -- Dictionnary of attributes/values to add

        Returns:
            Boolean | MoulinetteError

        """
        dn = rdn + "," + self.basedn
        ldif = modlist.addModlist(attr_dict)
        for i, (k, v) in enumerate(ldif):
            if isinstance(v, list):
                v = [a.encode("utf-8") for a in v]
            elif isinstance(v, str):
                v = [v.encode("utf-8")]
            ldif[i] = (k, v)

        try:
            self.con.add_s(dn, ldif)
        except Exception as e:
            raise MoulinetteError(
                "error during LDAP add operation with: rdn='%s', "
                "attr_dict=%s and exception %s" % (rdn, attr_dict, e),
                raw_msg=True,
            )
        else:
            return True

    def remove(self, rdn):
        """
        Remove LDAP entry

        Keyword arguments:
            rdn         -- DN without domain

        Returns:
            Boolean | MoulinetteError

        """
        dn = rdn + "," + self.basedn
        try:
            self.con.delete_s(dn)
        except Exception as e:
            raise MoulinetteError(
                "error during LDAP delete operation with: rdn='%s' and exception %s"
                % (rdn, e),
                raw_msg=True,
            )
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
            Boolean | MoulinetteError

        """
        dn = rdn + "," + self.basedn
        actual_entry = self.search(base=dn, attrs=None)
        ldif = modlist.modifyModlist(actual_entry[0], attr_dict, ignore_oldexistent=1)

        if ldif == []:
            logger.debug("Nothing to update in LDAP")
            return True

        try:
            if new_rdn:
                self.con.rename_s(dn, new_rdn)
                new_base = dn.split(",", 1)[1]
                dn = new_rdn + "," + new_base

            for i, (a, k, vs) in enumerate(ldif):
                if isinstance(vs, list):
                    vs = [v.encode("utf-8") for v in vs]
                elif isinstance(vs, str):
                    vs = [vs.encode("utf-8")]
                ldif[i] = (a, k, vs)

            self.con.modify_ext_s(dn, ldif)
        except Exception as e:
            raise MoulinetteError(
                "error during LDAP update operation with: rdn='%s', "
                "attr_dict=%s, new_rdn=%s and exception: %s"
                % (rdn, attr_dict, new_rdn, e),
                raw_msg=True,
            )
        else:
            return True

    def validate_uniqueness(self, value_dict):
        """
        Check uniqueness of values

        Keyword arguments:
            value_dict -- Dictionnary of attributes/values to check

        Returns:
            Boolean | MoulinetteError

        """
        attr_found = self.get_conflict(value_dict)
        if attr_found:
            logger.info(
                "attribute '%s' with value '%s' is not unique",
                attr_found[0],
                attr_found[1],
            )
            raise MoulinetteError(
                "ldap_attribute_already_exists",
                attribute=attr_found[0],
                value=attr_found[1],
            )
        return True

    def get_conflict(self, value_dict, base_dn=None):
        """
        Check uniqueness of values

        Keyword arguments:
            value_dict -- Dictionnary of attributes/values to check

        Returns:
            None | tuple with Fist conflict attribute name and value

        """
        for attr, value in value_dict.items():
            if not self.search(base=base_dn, filter=attr + "=" + value):
                continue
            else:
                return (attr, value)
        return None

    def _get_uri(self):
        return self.uri
