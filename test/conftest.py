"""Pytest fixtures for testing."""

from multiprocessing import Process
import time
import json
import os
import shutil
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
        if key not in self._translations[self.default_locale].keys():
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
    tty_level = 'INFO'

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
            'api': {
                'level': level,
                'class': 'moulinette.interfaces.api.APIQueueHandler',
            },
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


@pytest.fixture(scope='session')
def moulinette_webapi(moulinette, tmp_path_factory):
    namespace = "test"
    tmp_data = str(tmp_path_factory.mktemp("data"))
    tmp_locales = str(tmp_path_factory.mktemp("data"))
    os.environ['MOULINETTE_DATA_DIR'] = tmp_data
    os.environ['MOULINETTE_LIB_DIR'] = tmp_locales
    shutil.copytree("./data/actionsmap", "%s/actionsmap" % tmp_data)
    shutil.copytree("./locales", "%s/%s/locales" % (tmp_locales, namespace))

    api_thread = Process(target=moulinette.api,
                         args=([namespace],),
                         kwargs={"host": "localhost", "port": 12342, "use_websocket": False})
    api_thread.start()
    time.sleep(0.5)
    assert api_thread.is_alive()
    yield "http://localhost:12342"
    api_thread.terminate()


@pytest.fixture
def test_file(tmp_path):
    test_text = 'foo\nbar\n'
    test_file = tmp_path / 'test.txt'
    test_file.write_bytes(test_text)
    return test_file


@pytest.fixture
def test_json(tmp_path):
    test_json = json.dumps({'foo': 'bar'})
    test_file = tmp_path / 'test.json'
    test_file.write_bytes(test_json)
    return test_file


@pytest.fixture
def user():
    return os.getlogin()


@pytest.fixture
def test_url():
    return 'https://some.test.url/yolo.txt'
