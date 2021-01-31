"""Pytest fixtures for testing."""

import toml
import yaml
import json
import os
import shutil
import pytest

from .src.ldap_server import LDAPServer


def patch_init(moulinette):
    """Configure moulinette to use the YunoHost namespace."""
    old_init = moulinette.core.Moulinette18n.__init__

    def monkey_path_i18n_init(self, package, default_locale="en"):
        old_init(self, package, default_locale)
        self.load_namespace("moulinette")

    moulinette.core.Moulinette18n.__init__ = monkey_path_i18n_init


def patch_translate(moulinette):
    """Configure translator to raise errors when there are missing keys."""
    old_translate = moulinette.core.Translator.translate

    def new_translate(self, key, *args, **kwargs):
        if key not in self._translations[self.default_locale].keys():
            message = "Unable to retrieve key '%s' for default locale!" % key
            raise KeyError(message)

        return old_translate(self, key, *args, **kwargs)

    moulinette.core.Translator.translate = new_translate

    def new_m18nn(self, key, *args, **kwargs):
        return self._global.translate(key, *args, **kwargs)

    moulinette.core.Moulinette18n.g = new_m18nn


def patch_logging(moulinette):
    """Configure logging to use the custom logger."""
    handlers = set(["tty", "api"])
    root_handlers = set(handlers)

    level = "INFO"
    tty_level = "INFO"

    return {
        "version": 1,
        "disable_existing_loggers": True,
        "formatters": {
            "tty-debug": {"format": "%(relativeCreated)-4d %(fmessage)s"},
            "precise": {
                "format": "%(asctime)-15s %(levelname)-8s %(name)s %(funcName)s - %(fmessage)s"  # noqa
            },
        },
        "filters": {"action": {"()": "moulinette.utils.log.ActionFilter"}},
        "handlers": {
            "api": {
                "level": level,
                "class": "moulinette.interfaces.api.APIQueueHandler",
            },
            "tty": {
                "level": tty_level,
                "class": "moulinette.interfaces.cli.TTYHandler",
                "formatter": "",
            },
        },
        "loggers": {
            "moulinette": {"level": level, "handlers": [], "propagate": True},
            "moulinette.interface": {
                "level": level,
                "handlers": handlers,
                "propagate": False,
            },
        },
        "root": {"level": level, "handlers": root_handlers},
    }


def patch_lock(moulinette):
    moulinette.core.MoulinetteLock.base_lockfile = "moulinette_%s.lock"


@pytest.fixture(scope="session", autouse=True)
def moulinette(tmp_path_factory):
    import moulinette

    # Can't call the namespace just 'test' because
    # that would lead to some "import test" not importing the right stuff
    namespace = "moulitest"
    tmp_cache = str(tmp_path_factory.mktemp("cache"))
    tmp_data = str(tmp_path_factory.mktemp("data"))
    tmp_lib = str(tmp_path_factory.mktemp("lib"))
    os.environ["MOULINETTE_CACHE_DIR"] = tmp_cache
    os.environ["MOULINETTE_DATA_DIR"] = tmp_data
    os.environ["MOULINETTE_LIB_DIR"] = tmp_lib
    shutil.copytree("./test/actionsmap", "%s/actionsmap" % tmp_data)
    shutil.copytree("./test/src", "%s/%s" % (tmp_lib, namespace))
    shutil.copytree("./test/locales", "%s/%s/locales" % (tmp_lib, namespace))

    patch_init(moulinette)
    patch_translate(moulinette)
    patch_lock(moulinette)
    logging = patch_logging(moulinette)

    moulinette.init(logging_config=logging, _from_source=False)

    return moulinette


@pytest.fixture
def moulinette_webapi(moulinette):

    from webtest import TestApp
    from webtest.app import CookiePolicy

    # Dirty hack needed, otherwise cookies ain't reused between request .. not
    # sure why :|
    def return_true(self, cookie, request):
        return True

    CookiePolicy.return_ok_secure = return_true

    from moulinette.interfaces.api import Interface as Api

    return TestApp(Api(routes={})._app)


@pytest.fixture
def moulinette_cli(moulinette, mocker):
    import argparse

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Log and print debug messages",
    )
    mocker.patch("os.isatty", return_value=True)
    from moulinette.interfaces.cli import Interface as Cli

    cli = Cli(top_parser=parser)
    mocker.stopall()

    return cli


@pytest.fixture
def test_file(tmp_path):
    test_text = "foo\nbar\n"
    test_file = tmp_path / "test.txt"
    test_file.write_bytes(test_text.encode())
    return test_file


@pytest.fixture
def test_json(tmp_path):
    test_json = json.dumps({"foo": "bar"})
    test_file = tmp_path / "test.json"
    test_file.write_bytes(test_json.encode())
    return test_file


@pytest.fixture
def test_yaml(tmp_path):
    test_yaml = yaml.dump({"foo": "bar"})
    test_file = tmp_path / "test.txt"
    test_file.write_bytes(test_yaml.encode())
    return test_file


@pytest.fixture
def test_toml(tmp_path):
    test_toml = toml.dumps({"foo": "bar"})
    test_file = tmp_path / "test.txt"
    test_file.write_bytes(test_toml.encode())
    return test_file


@pytest.fixture
def test_ldif(tmp_path):
    test_file = tmp_path / "test.txt"
    from ldif import LDIFWriter

    writer = LDIFWriter(open(str(test_file), "w"))

    writer.unparse(
        "mail=alice@example.com",
        {
            "cn": ["Alice Alison".encode("utf-8")],
            "mail": ["alice@example.com".encode("utf-8")],
            "objectclass": ["top".encode("utf-8"), "person".encode("utf-8")],
        },
    )

    return test_file


@pytest.fixture
def user():
    return os.getlogin()


@pytest.fixture
def test_url():
    return "https://some.test.url/yolo.txt"


@pytest.fixture
def ldap_server():
    server = LDAPServer()
    server.start()
    yield server
    server.stop()
