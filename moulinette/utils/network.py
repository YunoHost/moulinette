import errno
import requests
import json

import moulinette
from moulinette.core import MoulinetteError


def download_text(url, timeout=30):
    """
    Download text from a url and returns the raw text

    Keyword argument:
        url -- The url to download the data from
        timeout -- Number of seconds allowed for download to effectively start
        before giving up
    """
    # Assumptions
    assert isinstance(url, str)

    # Download file
    try:
        r = requests.get(url, timeout=timeout)
    # Invalid URL
    except requests.exceptions.ConnectionError:
        raise MoulinetteError(errno.EBADE,
                              moulinette.m18n.g('invalid_url', url=url))
    # SSL exceptions
    except requests.exceptions.SSLError:
        raise MoulinetteError(errno.EBADE,
                              moulinette.m18n.g('download_ssl_error', url=url))
    # Timeout exceptions
    except requests.exceptions.Timeout:
        raise MoulinetteError(errno.ETIME,
                              moulinette.m18n.g('download_timeout', url=url))
    # Unknown stuff
    except Exception as e:
        raise MoulinetteError(errno.ECONNRESET,
                              moulinette.m18n.g('download_unknown_error',
                                     url=url, error=str(e)))
    # Assume error if status code is not 200 (OK)
    if r.status_code != 200:
        raise MoulinetteError(errno.EBADE,
                              moulinette.m18n.g('download_bad_status_code',
                                     url=url, code=str(r.status_code)))

    return r.text


def download_json(url, timeout=30):

    # Fetch the data
    text = download_text(url, timeout)

    # Try to load json to check if it's syntaxically correct
    try:
        loaded_json = json.loads(text)
    except ValueError:
        raise MoulinetteError(errno.EINVAL,
                              moulinette.m18n.g('corrupted_json', ressource=url))

    return loaded_json
