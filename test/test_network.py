import pytest
import requests
import requests_mock

from moulinette.core import MoulinetteError
from moulinette.utils.network import download_json, download_text


def test_download(test_url):
    with requests_mock.Mocker() as mock:
        mock.register_uri("GET", test_url, text="some text")
        fetched_text = download_text(test_url)
    assert fetched_text == "some text"


def test_download_bad_url():
    with pytest.raises(MoulinetteError):
        download_text("Nowhere")


def test_download_404(test_url):
    with requests_mock.Mocker() as mock:
        mock.register_uri("GET", test_url, status_code=404)
        with pytest.raises(MoulinetteError):
            download_text(test_url)


def test_download_ssl_error(test_url):
    with requests_mock.Mocker() as mock:
        exception = requests.exceptions.SSLError
        mock.register_uri("GET", test_url, exc=exception)
        with pytest.raises(MoulinetteError):
            download_text(test_url)


def test_download_timeout(test_url):
    with requests_mock.Mocker() as mock:
        exception = requests.exceptions.ConnectTimeout
        mock.register_uri("GET", test_url, exc=exception)
        with pytest.raises(MoulinetteError):
            download_text(test_url)


def test_download_json(test_url):
    with requests_mock.Mocker() as mock:
        mock.register_uri("GET", test_url, text='{"foo":"bar"}')
        fetched_json = download_json(test_url)
    assert "foo" in fetched_json.keys()
    assert fetched_json["foo"] == "bar"


def test_download_json_bad_json(test_url):
    with requests_mock.Mocker() as mock:
        mock.register_uri("GET", test_url, text="notjsonlol")
        with pytest.raises(MoulinetteError):
            download_json(test_url)
