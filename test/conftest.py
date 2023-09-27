"""Pytest fixtures for testing."""

import sys
import toml
import yaml
import json
import os

import shutil
import pytest


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


def logging_configuration(moulinette):
    """Configure logging to use the custom logger."""
    handlers = {"tty", "api"}
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
        "filters": {},
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
    import moulinette.core
    from moulinette.utils.log import configure_logging

    # Can't call the namespace just 'test' because
    # that would lead to some "import test" not importing the right stuff
    namespace = "moulitest"
    tmp_dir = str(tmp_path_factory.mktemp(namespace))
    shutil.copy("./test/actionsmap/moulitest.yml", f"{tmp_dir}/moulitest.yml")
    shutil.copytree("./test/src", f"{tmp_dir}/lib/{namespace}/")
    shutil.copytree("./test/locales", f"{tmp_dir}/locales")
    sys.path.insert(0, f"{tmp_dir}/lib")

    patch_translate(moulinette)
    patch_lock(moulinette)

    configure_logging(logging_configuration(moulinette))
    moulinette.m18n.set_locales_dir(f"{tmp_dir}/locales")

    # Dirty hack to pass this path to Api() and Cli() init later
    moulinette._actionsmap_path = f"{tmp_dir}/moulitest.yml"

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

    return TestApp(Api(routes={}, actionsmap=moulinette._actionsmap_path)._app)


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

    cli = Cli(top_parser=parser, actionsmap=moulinette._actionsmap_path)
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
def user():
    return os.getlogin()


@pytest.fixture
def test_url():
    return "https://some.test.url/yolo.txt"
