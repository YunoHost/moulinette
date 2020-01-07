import pytest
import os

from moulinette.authenticators import ldap as m_ldap
from moulinette import m18n
from moulinette.core import MoulinetteError


class TestLDAP:
    def setup_method(self):
        self.ldap_conf = {
            "vendor": "ldap",
            "name": "as-root",
            "parameters": {"base_dn": "dc=yunohost,dc=org"},
            "extra": {},
        }

    def test_authenticate_simple_bind_with_admin(self, ldap_server):
        self.ldap_conf["parameters"]["uri"] = ldap_server.uri
        self.ldap_conf["parameters"]["user_rdn"] = "cn=admin,dc=yunohost,dc=org"
        ldap_interface = m_ldap.Authenticator(**self.ldap_conf)
        ldap_interface.authenticate(password="yunohost")

        assert ldap_interface.con

    def test_authenticate_simple_bind_with_wrong_user(self, ldap_server):
        self.ldap_conf["parameters"]["uri"] = ldap_server.uri
        self.ldap_conf["parameters"]["user_rdn"] = "cn=yoloswag,dc=yunohost,dc=org"
        ldap_interface = m_ldap.Authenticator(**self.ldap_conf)
        with pytest.raises(MoulinetteError) as exception:
            ldap_interface.authenticate(password="yunohost")

        translation = m18n.g("invalid_password")
        expected_msg = translation.format()
        assert expected_msg in str(exception)
        assert ldap_interface.con is None

    def test_authenticate_simple_bind_with_rdn_wrong_password(self, ldap_server):
        self.ldap_conf["parameters"]["uri"] = ldap_server.uri
        self.ldap_conf["parameters"]["user_rdn"] = "cn=admin,dc=yunohost,dc=org"
        ldap_interface = m_ldap.Authenticator(**self.ldap_conf)
        with pytest.raises(MoulinetteError) as exception:
            ldap_interface.authenticate(password="bad_password_lul")

        translation = m18n.g("invalid_password")
        expected_msg = translation.format()
        assert expected_msg in str(exception)

        assert ldap_interface.con is None

    def test_authenticate_simple_bind_anonymous(self, ldap_server):
        self.ldap_conf["parameters"]["uri"] = ldap_server.uri
        self.ldap_conf["parameters"]["user_rdn"] = ""
        ldap_interface = m_ldap.Authenticator(**self.ldap_conf)
        ldap_interface.authenticate()

        assert ldap_interface.con

    def test_authenticate_sasl_non_interactive_bind(self, ldap_server):
        self.ldap_conf["parameters"]["uri"] = ldap_server.uri
        self.ldap_conf["parameters"]["user_rdn"] = (
            "gidNumber=%s+uidNumber=%s,cn=peercred,cn=external,cn=auth"
            % (os.getgid(), os.getuid())
        )
        ldap_interface = m_ldap.Authenticator(**self.ldap_conf)

        assert ldap_interface.con

    def test_authenticate_server_down(self, ldap_server):
        self.ldap_conf["parameters"]["uri"] = ldap_server.uri
        self.ldap_conf["parameters"]["user_rdn"] = "cn=admin,dc=yunohost,dc=org"
        ldap_server.stop()
        ldap_interface = m_ldap.Authenticator(**self.ldap_conf)
        with pytest.raises(MoulinetteError) as exception:
            ldap_interface.authenticate(password="yunohost")

        translation = m18n.g("ldap_server_down")
        expected_msg = translation.format()
        assert expected_msg in str(exception)

        assert ldap_interface.con is None

    def create_ldap_interface(self, user_rdn, password=None):
        self.ldap_conf["parameters"]["user_rdn"] = user_rdn
        ldap_interface = m_ldap.Authenticator(**self.ldap_conf)
        if not ldap_interface.con:
            ldap_interface.authenticate(password=password)
        return ldap_interface

    def test_admin_read(self, ldap_server):
        self.ldap_conf["parameters"]["uri"] = ldap_server.uri
        ldap_interface = self.create_ldap_interface(
            "cn=admin,dc=yunohost,dc=org", "yunohost"
        )

        admin_info = ldap_interface.search("cn=admin,dc=yunohost,dc=org", attrs=None)[0]
        assert "cn" in admin_info
        assert admin_info["cn"] == ["admin"]
        assert "description" in admin_info
        assert admin_info["description"] == ["LDAP Administrator"]
        assert "userPassword" in admin_info
        assert admin_info["userPassword"][0].startswith("{CRYPT}$6$")

        admin_info = ldap_interface.search(
            "cn=admin,dc=yunohost,dc=org", attrs=["userPassword"]
        )[0]
        assert admin_info.keys() == ["userPassword"]
        assert admin_info["userPassword"][0].startswith("{CRYPT}$6$")

    def test_sasl_read(self, ldap_server):
        self.ldap_conf["parameters"]["uri"] = ldap_server.uri
        ldap_interface = self.create_ldap_interface(
            "gidNumber=%s+uidNumber=%s,cn=peercred,cn=external,cn=auth"
            % (os.getgid(), os.getuid())
        )

        admin_info = ldap_interface.search("cn=admin,dc=yunohost,dc=org", attrs=None)[0]
        assert "cn" in admin_info
        assert admin_info["cn"] == ["admin"]
        assert "description" in admin_info
        assert admin_info["description"] == ["LDAP Administrator"]
        assert "userPassword" in admin_info
        assert admin_info["userPassword"][0].startswith("{CRYPT}$6$")

        admin_info = ldap_interface.search(
            "cn=admin,dc=yunohost,dc=org", attrs=["userPassword"]
        )[0]
        assert admin_info.keys() == ["userPassword"]
        assert admin_info["userPassword"][0].startswith("{CRYPT}$6$")

    def test_anonymous_read(self, ldap_server):
        self.ldap_conf["parameters"]["uri"] = ldap_server.uri
        ldap_interface = self.create_ldap_interface("")

        admin_info = ldap_interface.search("cn=admin,dc=yunohost,dc=org", attrs=None)[0]
        assert "cn" in admin_info
        assert admin_info["cn"] == ["admin"]
        assert "description" in admin_info
        assert admin_info["description"] == ["LDAP Administrator"]
        assert "userPassword" not in admin_info

        admin_info = ldap_interface.search(
            "cn=admin,dc=yunohost,dc=org", attrs=["userPassword"]
        )[0]
        assert not admin_info

    def add_new_user(self, ldap_interface):
        new_user = "new_user"
        attr_dict = {
            "objectClass": ["inetOrgPerson", "posixAccount"],
            "sn": new_user,
            "cn": new_user,
            "userPassword": new_user,
            "gidNumber": "666",
            "uidNumber": "666",
            "homeDirectory": "/home/" + new_user,
        }
        ldap_interface.add("uid=%s,ou=users" % new_user, attr_dict)

        # Check if we can login as the new user
        assert self.create_ldap_interface(
            "uid=%s,ou=users,dc=yunohost,dc=org" % new_user, new_user
        ).con

        return ldap_interface.search(
            "uid=%s,ou=users,dc=yunohost,dc=org" % new_user, attrs=None
        )[0]

    def test_admin_add(self, ldap_server):
        self.ldap_conf["parameters"]["uri"] = ldap_server.uri
        ldap_interface = self.create_ldap_interface(
            "cn=admin,dc=yunohost,dc=org", "yunohost"
        )

        new_user_info = self.add_new_user(ldap_interface)
        assert "cn" in new_user_info
        assert new_user_info["cn"] == ["new_user"]
        assert "sn" in new_user_info
        assert new_user_info["sn"] == ["new_user"]
        assert "uid" in new_user_info
        assert new_user_info["uid"] == ["new_user"]
        assert "objectClass" in new_user_info
        assert "inetOrgPerson" in new_user_info["objectClass"]
        assert "posixAccount" in new_user_info["objectClass"]

    def test_sasl_add(self, ldap_server):
        self.ldap_conf["parameters"]["uri"] = ldap_server.uri
        ldap_interface = self.create_ldap_interface(
            "gidNumber=%s+uidNumber=%s,cn=peercred,cn=external,cn=auth"
            % (os.getgid(), os.getuid())
        )

        new_user_info = self.add_new_user(ldap_interface)
        assert "cn" in new_user_info
        assert new_user_info["cn"] == ["new_user"]
        assert "sn" in new_user_info
        assert new_user_info["sn"] == ["new_user"]
        assert "uid" in new_user_info
        assert new_user_info["uid"] == ["new_user"]
        assert "objectClass" in new_user_info
        assert "inetOrgPerson" in new_user_info["objectClass"]
        assert "posixAccount" in new_user_info["objectClass"]

    def test_anonymous_add(self, ldap_server):
        self.ldap_conf["parameters"]["uri"] = ldap_server.uri
        ldap_interface = self.create_ldap_interface("")

        with pytest.raises(MoulinetteError) as exception:
            self.add_new_user(ldap_interface)

        translation = m18n.g("ldap_operation_error", action="add")
        expected_msg = translation.format(action="add")
        assert expected_msg in str(exception)

    def remove_new_user(self, ldap_interface):
        new_user_info = self.add_new_user(
            self.create_ldap_interface(
                "gidNumber=%s+uidNumber=%s,cn=peercred,cn=external,cn=auth"
                % (os.getgid(), os.getuid()),
                "yunohost",
            )
        )

        uid = new_user_info["uid"][0]
        ldap_interface.remove("uid=%s,ou=users" % uid)

        with pytest.raises(MoulinetteError) as exception:
            ldap_interface.search(
                "uid=%s,ou=users,dc=yunohost,dc=org" % uid, attrs=None
            )

        translation = m18n.g("ldap_operation_error", action="search")
        expected_msg = translation.format(action="search")
        assert expected_msg in str(exception)

    def test_admin_remove(self, ldap_server):
        self.ldap_conf["parameters"]["uri"] = ldap_server.uri
        ldap_interface = self.create_ldap_interface(
            "cn=admin,dc=yunohost,dc=org", "yunohost"
        )

        self.remove_new_user(ldap_interface)

    def test_sasl_remove(self, ldap_server):
        self.ldap_conf["parameters"]["uri"] = ldap_server.uri
        ldap_interface = self.create_ldap_interface(
            "gidNumber=%s+uidNumber=%s,cn=peercred,cn=external,cn=auth"
            % (os.getgid(), os.getuid())
        )

        self.remove_new_user(ldap_interface)

    def test_anonymous_remove(self, ldap_server):
        self.ldap_conf["parameters"]["uri"] = ldap_server.uri
        ldap_interface = self.create_ldap_interface("")

        with pytest.raises(MoulinetteError) as exception:
            self.remove_new_user(ldap_interface)

        translation = m18n.g("ldap_operation_error", action="remove")
        expected_msg = translation.format(action="remove")
        assert expected_msg in str(exception)

    def update_new_user(self, ldap_interface, new_rdn=False):
        new_user_info = self.add_new_user(
            self.create_ldap_interface(
                "gidNumber=%s+uidNumber=%s,cn=peercred,cn=external,cn=auth"
                % (os.getgid(), os.getuid()),
                "yunohost",
            )
        )

        uid = new_user_info["uid"][0]
        new_user_info["uidNumber"] = "555"
        new_user_info["gidNumber"] = "555"
        new_another_user_uid = "new_another_user"
        if new_rdn:
            new_rdn = "uid=%s" % new_another_user_uid
        ldap_interface.update("uid=%s,ou=users" % uid, new_user_info, new_rdn)

        if new_rdn:
            uid = new_another_user_uid
        return ldap_interface.search(
            "uid=%s,ou=users,dc=yunohost,dc=org" % uid, attrs=None
        )[0]

    def test_admin_update(self, ldap_server):
        self.ldap_conf["parameters"]["uri"] = ldap_server.uri
        ldap_interface = self.create_ldap_interface(
            "cn=admin,dc=yunohost,dc=org", "yunohost"
        )

        new_user_info = self.update_new_user(ldap_interface)
        assert new_user_info["uid"] == ["new_user"]
        assert new_user_info["uidNumber"] == ["555"]
        assert new_user_info["gidNumber"] == ["555"]

    def test_admin_update_new_rdn(self, ldap_server):
        self.ldap_conf["parameters"]["uri"] = ldap_server.uri
        ldap_interface = self.create_ldap_interface(
            "cn=admin,dc=yunohost,dc=org", "yunohost"
        )

        new_user_info = self.update_new_user(ldap_interface, True)
        assert new_user_info["uid"] == ["new_another_user"]
        assert new_user_info["uidNumber"] == ["555"]
        assert new_user_info["gidNumber"] == ["555"]

    def test_sasl_update(self, ldap_server):
        self.ldap_conf["parameters"]["uri"] = ldap_server.uri
        ldap_interface = self.create_ldap_interface(
            "gidNumber=%s+uidNumber=%s,cn=peercred,cn=external,cn=auth"
            % (os.getgid(), os.getuid())
        )

        new_user_info = self.update_new_user(ldap_interface)
        assert new_user_info["uid"] == ["new_user"]
        assert new_user_info["uidNumber"] == ["555"]
        assert new_user_info["gidNumber"] == ["555"]

    def test_sasl_update_new_rdn(self, ldap_server):
        self.ldap_conf["parameters"]["uri"] = ldap_server.uri
        ldap_interface = self.create_ldap_interface(
            "cn=admin,dc=yunohost,dc=org", "yunohost"
        )

        new_user_info = self.update_new_user(ldap_interface, True)
        assert new_user_info["uid"] == ["new_another_user"]
        assert new_user_info["uidNumber"] == ["555"]
        assert new_user_info["gidNumber"] == ["555"]

    def test_anonymous_update(self, ldap_server):
        self.ldap_conf["parameters"]["uri"] = ldap_server.uri
        ldap_interface = self.create_ldap_interface("")

        with pytest.raises(MoulinetteError) as exception:
            self.update_new_user(ldap_interface)

        translation = m18n.g("ldap_operation_error", action="update")
        expected_msg = translation.format(action="update")
        assert expected_msg in str(exception)

    def test_anonymous_update_new_rdn(self, ldap_server):
        self.ldap_conf["parameters"]["uri"] = ldap_server.uri
        ldap_interface = self.create_ldap_interface("")

        with pytest.raises(MoulinetteError) as exception:
            self.update_new_user(ldap_interface, True)

        translation = m18n.g("ldap_operation_error", action="update")
        expected_msg = translation.format(action="update")
        assert expected_msg in str(exception)

    def test_get_conflict(self, ldap_server):
        self.ldap_conf["parameters"]["uri"] = ldap_server.uri
        ldap_interface = self.create_ldap_interface(
            "cn=admin,dc=yunohost,dc=org", "yunohost"
        )
        self.add_new_user(ldap_interface)

        conflict = ldap_interface.get_conflict({"uid": "new_user"})
        assert conflict == ("uid", "new_user")

        conflict = ldap_interface.get_conflict(
            {"uid": "new_user"}, base_dn="ou=users,dc=yunohost,dc=org"
        )
        assert conflict == ("uid", "new_user")

        conflict = ldap_interface.get_conflict({"uid": "not_a_user"})
        assert not conflict

    def test_validate_uniqueness(self, ldap_server):
        self.ldap_conf["parameters"]["uri"] = ldap_server.uri
        ldap_interface = self.create_ldap_interface(
            "cn=admin,dc=yunohost,dc=org", "yunohost"
        )
        self.add_new_user(ldap_interface)

        with pytest.raises(MoulinetteError) as exception:
            ldap_interface.validate_uniqueness({"uid": "new_user"})

        translation = m18n.g(
            "ldap_attribute_already_exists", attribute="uid", value="new_user"
        )
        expected_msg = translation.format(attribute="uid", value="new_user")
        assert expected_msg in str(exception)

        assert ldap_interface.validate_uniqueness({"uid": "not_a_user"})
