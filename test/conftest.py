"""Pytest fixtures for testing."""

import json
import os

import pytest


def patch_init(moulinette):
    """Configure moulinette to use the YunoHost namespace."""
    old_init = moulinette.core.Moulinette18n.__init__

    def monkey_path_i18n_init(self, package, default_locale='en'):
        old_init(self, package, default_locale)
        self.load_namespace('moulinette')

    moulinette.core.Moulinette18n.__init__ = monkey_path_i18n_init


def patch_translate(moulinette):
    """Configure translator to raise errors when there are missing keys."""
    old_translate = moulinette.core.Translator.translate

    def new_translate(self, key, *args, **kwargs):
        if key not in list(self._translations[self.default_locale].keys()):
            message = 'Unable to retrieve key %s for default locale!' % key
            raise KeyError(message)

        return old_translate(self, key, *args, **kwargs)

    moulinette.core.Translator.translate = new_translate

    def new_m18nn(self, key, *args, **kwargs):
        return self._global.translate(key, *args, **kwargs)

    moulinette.core.Moulinette18n.g = new_m18nn


def patch_logging(moulinette):
    """Configure logging to use the custom logger."""
    handlers = set(['tty'])
    root_handlers = set(handlers)

    level = 'INFO'
    tty_level = 'SUCCESS'

    logging = {
        'version': 1,
        'disable_existing_loggers': True,
        'formatters': {
            'tty-debug': {
                'format': '%(relativeCreated)-4d %(fmessage)s'
            },
            'precise': {
                'format': '%(asctime)-15s %(levelname)-8s %(name)s %(funcName)s - %(fmessage)s'  # noqa
            },
        },
        'filters': {
            'action': {
                '()': 'moulinette.utils.log.ActionFilter',
            },
        },
        'handlers': {
            'tty': {
                'level': tty_level,
                'class': 'moulinette.interfaces.cli.TTYHandler',
                'formatter': '',
            },
        },
        'loggers': {
            'moulinette': {
                'level': level,
                'handlers': [],
                'propagate': True,
            },
            'moulinette.interface': {
                'level': level,
                'handlers': handlers,
                'propagate': False,
            },
        },
        'root': {
            'level': level,
            'handlers': root_handlers,
        },
    }

    moulinette.init(
        logging_config=logging,
        _from_source=False
    )


@pytest.fixture(scope='session', autouse=True)
def moulinette():
    import moulinette

    patch_init(moulinette)
    patch_translate(moulinette)
    patch_logging(moulinette)

    return moulinette


@pytest.fixture
def test_file(tmp_path):
    test_text = 'foo\nbar\n'
    test_file = tmp_path / 'test.txt'
    test_file.write_text(test_text)
    return test_file


@pytest.fixture
def test_json(tmp_path):
    test_json = json.dumps({'foo': 'bar'})
    test_file = tmp_path / 'test.json'
    test_file.write_text(test_json)
    return test_file


@pytest.fixture
def user():
    return os.getlogin()


@pytest.fixture
def test_url():
    return 'https://some.test.url/yolo.txt'
