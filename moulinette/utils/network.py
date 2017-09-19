import errno
import requests
import json

from moulinette import m18n
from moulinette.core import MoulinetteError


def download_text(url, timeout=30, expected_status_code=200):
    """
    Download text from a url and returns the raw text

    Keyword argument:
        url -- The url to download the data from
        timeout -- Number of seconds allowed for download to effectively start
        before giving up
        expected_status_code -- Status code expected from the request. Can be
        None to ignore the status code.
    """
    # Assumptions
    assert isinstance(url, str)

    # Download file
    try:
        r = requests.get(url, timeout=timeout)
    # Invalid URL
    except requests.exceptions.ConnectionError:
        raise MoulinetteError(errno.EBADE,
                              m18n.g('invalid_url', url=url))
    # SSL exceptions
    except requests.exceptions.SSLError:
        raise MoulinetteError(errno.EBADE,
                              m18n.g('download_ssl_error', url=url))
    # Timeout exceptions
    except requests.exceptions.Timeout:
        raise MoulinetteError(errno.ETIME,
                              m18n.g('download_timeout', url=url))
    # Unknown stuff
    except Exception as e:
        raise MoulinetteError(errno.ECONNRESET,
                              m18n.g('download_unknown_error',
                                     url=url, error=str(e)))
    # Assume error if status code is not 200 (OK)
    if expected_status_code is not None \
       and r.status_code != expected_status_code:
        raise MoulinetteError(errno.EBADE,
                              m18n.g('download_bad_status_code',
                                     url=url, code=str(r.status_code)))

    return r.text


def download_json(url, timeout=30, expected_status_code=200):
    """
    Download json from a url and returns the loaded json object

    Keyword argument:
        url -- The url to download the data from
        timeout -- Number of seconds allowed for download to effectively start
        before giving up
    """
    # Fetch the data
    text = download_text(url, timeout, expected_status_code)

    # Try to load json to check if it's syntaxically correct
    try:
        loaded_json = json.loads(text)
    except ValueError:
        raise MoulinetteError(errno.EINVAL,
                              m18n.g('corrupted_json', ressource=url))

    return loaded_json
