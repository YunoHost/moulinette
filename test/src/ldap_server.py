try:
    from . import slapdtest
except ImportError:
    from . import old_slapdtest as slapdtest
import os
from moulinette.authenticators import ldap as m_ldap

HERE = os.path.abspath(os.path.dirname(__file__))


class LDAPServer:
    def __init__(self):
        self.server_default = slapdtest.SlapdObject()
        with open(os.path.join(HERE, "..", "ldap_files", "slapd.conf.template")) as f:
            SLAPD_CONF_TEMPLATE = f.read()
        self.server_default.slapd_conf_template = SLAPD_CONF_TEMPLATE
        self.server_default.suffix = "dc=yunohost,dc=org"
        self.server_default.root_cn = "admin"
        self.server_default.SCHEMADIR = os.path.join(HERE, "..", "ldap_files", "schema")
        self.server_default.openldap_schema_files = [
            "core.schema",
            "cosine.schema",
            "nis.schema",
            "inetorgperson.schema",
            "sudo.schema",
            "yunohost.schema",
            "mailserver.schema",
        ]
        self.server = None
        self.uri = ""

    def start(self):
        self.server = self.server_default
        self.server.start()
        self.uri = self.server.ldapi_uri
        with open(os.path.join(HERE, "..", "ldap_files", "tests.ldif")) as fp:
            ldif = fp.read().decode("utf-8")
        self.server.ldapadd(ldif)
        self.tools_ldapinit()

    def stop(self):
        if self.server:
            self.server.stop()

    def __del__(self):
        if self.server:
            self.server.stop()

    def tools_ldapinit(self):
        """
        YunoHost LDAP initialization


        """
        import yaml

        with open(os.path.join(HERE, "..", "ldap_files", "ldap_scheme.yml")) as f:
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
            "cn": ["admin"],
            "uid": ["admin"],
            "description": ["LDAP Administrator"],
            "gidNumber": ["1007"],
            "uidNumber": ["1007"],
            "homeDirectory": ["/home/admin"],
            "loginShell": ["/bin/bash"],
            "objectClass": [
                "organizationalRole",
                "posixAccount",
                "simpleSecurityObject",
            ],
            "userPassword": ["yunohost"],
        }

        ldap_interface.update("cn=admin", admin_dict)
