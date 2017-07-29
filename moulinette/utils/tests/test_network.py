
# General python lib
import pytest
import requests
import requests_mock

# Moulinette specific
from moulinette.core import MoulinetteError
from moulinette.utils.network import download_text, download_json

# We define a dummy context with test folders and files

TEST_URL = "https://some.test.url/yolo.txt"


def setup_function(function):

    pass


def teardown_function(function):

    pass

###############################################################################
#   Test download                                                             #
###############################################################################


def test_download():

    with requests_mock.Mocker() as m:
        m.register_uri("GET", TEST_URL, text='some text')

        fetched_text = download_text(TEST_URL)

    assert fetched_text == "some text"


def test_download_badurl():

    with pytest.raises(MoulinetteError):
        download_text(TEST_URL)


def test_download_404():

    with requests_mock.Mocker() as m:
        m.register_uri("GET", TEST_URL, status_code=404)

        with pytest.raises(MoulinetteError):
            download_text(TEST_URL)


def test_download_sslerror():

    with requests_mock.Mocker() as m:
        m.register_uri("GET", TEST_URL, exc=requests.exceptions.SSLError)

        with pytest.raises(MoulinetteError):
            download_text(TEST_URL)


def test_download_timeout():

    with requests_mock.Mocker() as m:
        m.register_uri("GET", TEST_URL, exc=requests.exceptions.ConnectTimeout)

        with pytest.raises(MoulinetteError):
            download_text(TEST_URL)


def test_download_json():

    with requests_mock.Mocker() as m:
        m.register_uri("GET", TEST_URL, text='{ "foo":"bar" }')

        fetched_json = download_json(TEST_URL)

    assert "foo" in fetched_json.keys()
    assert fetched_json["foo"] == "bar"


def test_download_json_badjson():

    with requests_mock.Mocker() as m:
        m.register_uri("GET", TEST_URL, text='{ not json lol }')

        with pytest.raises(MoulinetteError):
            download_json(TEST_URL)
