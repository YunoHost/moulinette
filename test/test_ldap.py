import pytest

try:
    import slapdtest
except ImportError:
    import old_slapdtest as slapdtest
import os

from moulinette.authenticators import ldap as m_ldap
from moulinette import m18n
from moulinette.core import MoulinetteError

HERE = os.path.abspath(os.path.dirname(__file__))


class TestLDAP:

    server = None
    server_default = None

    @classmethod
    def setup_class(cls):
        cls.server_default = slapdtest.SlapdObject()
        with open(os.path.join(HERE, "ldap_files", "slapd.conf.template")) as f:
            SLAPD_CONF_TEMPLATE = f.read()
        cls.server_default.slapd_conf_template = SLAPD_CONF_TEMPLATE
        cls.server_default.suffix = "dc=yunohost,dc=org"
        cls.server_default.root_cn = "admin"
        cls.server_default.SCHEMADIR = os.path.join(HERE, "ldap_files", "schema")
        cls.server_default.openldap_schema_files = [
            "core.schema",
            "cosine.schema",
            "nis.schema",
            "inetorgperson.schema",
            "sudo.schema",
            "yunohost.schema",
            "mailserver.schema",
        ]

    def tools_ldapinit(self):
        """
        YunoHost LDAP initialization


        """
        import yaml

        with open(os.path.join(HERE, "ldap_files", "ldap_scheme.yml")) as f:
            ldap_map = yaml.load(f)

        def _get_ldap_interface():
            conf = {
                "vendor": "ldap",
                "name": "as-root",
                "parameters": {
                    "uri": self.server.ldapi_uri,
                    "base_dn": "dc=yunohost,dc=org",
                    "user_rdn": "gidNumber=%s+uidNumber=%s,cn=peercred,cn=external,cn=auth"
                    % (os.getgid(), os.getuid()),
                },
                "extra": {},
            }

            _ldap_interface = m_ldap.Authenticator(**conf)

            return _ldap_interface

        ldap_interface = _get_ldap_interface()

        for rdn, attr_dict in ldap_map["parents"].items():
            ldap_interface.add(rdn, attr_dict)

        for rdn, attr_dict in ldap_map["children"].items():
            ldap_interface.add(rdn, attr_dict)

        for rdn, attr_dict in ldap_map["depends_children"].items():
            ldap_interface.add(rdn, attr_dict)

        admin_dict = {
            "cn": "admin",
            "uid": "admin",
            "description": "LDAP Administrator",
            "gidNumber": "1007",
            "uidNumber": "1007",
            "homeDirectory": "/home/admin",
            "loginShell": "/bin/bash",
            "objectClass": [
                "organizationalRole",
                "posixAccount",
                "simpleSecurityObject",
            ],
            "userPassword": "yunohost",
        }

        ldap_interface.update("cn=admin", admin_dict)

    @classmethod
    def teardown_class(cls):
        pass

    def setup_method(self):
        self.server = self.server_default
        self.server.start()
        with open(os.path.join(HERE, "ldap_files", "tests.ldif")) as fp:
            ldif = fp.read().decode("utf-8")
        self.server.ldapadd(ldif)
        self.tools_ldapinit()
        self.ldap_conf = {
            "vendor": "ldap",
            "name": "as-root",
            "parameters": {
                "uri": self.server.ldapi_uri,
                "base_dn": "dc=yunohost,dc=org",
            },
            "extra": {},
        }

    def teardown_method(self):
        self.server.stop()

    def test_authenticate_simple_bind_with_rdn(self):
        self.ldap_conf["parameters"]["user_rdn"] = "cn=admin,dc=yunohost,dc=org"
        ldap_interface = m_ldap.Authenticator(**self.ldap_conf)
        ldap_interface.authenticate(password="yunohost")

    def test_authenticate_simple_bind_with_rdn_wrong_password(self):
        self.ldap_conf["parameters"]["user_rdn"] = "cn=admin,dc=yunohost,dc=org"
        ldap_interface = m_ldap.Authenticator(**self.ldap_conf)
        with pytest.raises(MoulinetteError) as exception:
            ldap_interface.authenticate(password="bad_password_lul")

        translation = m18n.g("invalid_password")
        expected_msg = translation.format()
        assert expected_msg in str(exception)

    def test_authenticate_simple_bind_without_rdn(self):
        self.ldap_conf["parameters"]["user_rdn"] = ""
        ldap_interface = m_ldap.Authenticator(**self.ldap_conf)
        ldap_interface.authenticate()

    def test_authenticate_sasl_non_interactive_bind(self):
        self.ldap_conf["parameters"]["user_rdn"] = (
            "gidNumber=%s+uidNumber=%s,cn=peercred,cn=external,cn=auth"
            % (os.getgid(), os.getuid()),
        )
        m_ldap.Authenticator(**self.ldap_conf)

    def test_authenticate_server_down(self):
        self.ldap_conf["parameters"]["user_rdn"] = "cn=admin,dc=yunohost,dc=org"
        self.server.stop()
        ldap_interface = m_ldap.Authenticator(**self.ldap_conf)
        with pytest.raises(MoulinetteError) as exception:
            ldap_interface.authenticate(password="yunohost")

        translation = m18n.g("ldap_server_down")
        expected_msg = translation.format()
        assert expected_msg in str(exception)
