import json

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
    import requests  # lazy loading this module for performance reasons

    # Assumptions
    assert isinstance(url, str)

    # Download file
    try:
        r = requests.get(url, timeout=timeout)
    # SSL exceptions
    except requests.exceptions.SSLError:
        raise MoulinetteError("download_ssl_error", url=url)
    # Invalid URL
    except requests.exceptions.ConnectionError:
        raise MoulinetteError("invalid_url", url=url)
    # Timeout exceptions
    except requests.exceptions.Timeout:
        raise MoulinetteError("download_timeout", url=url)
    # Unknown stuff
    except Exception as e:
        raise MoulinetteError("download_unknown_error", url=url, error=str(e))
    # Assume error if status code is not 200 (OK)
    if expected_status_code is not None and r.status_code != expected_status_code:
        raise MoulinetteError(
            "download_bad_status_code", url=url, code=str(r.status_code)
        )

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
    except ValueError as e:
        raise MoulinetteError("corrupted_json", ressource=url, error=e)

    return loaded_json
