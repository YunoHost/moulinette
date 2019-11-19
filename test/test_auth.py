import os
import requests


def login(webapi, cookies=None, csrf=False, profile=None):

    data = {"password": "Yoloswag"}
    if profile:
        data["profile"] = profile

    return requests.post(webapi + "/login",
                         cookies=cookies,
                         data=data,
                         headers=None if csrf else {"X-Requested-With": ""})


def test_request_no_auth_needed(moulinette_webapi):

    r = requests.get(moulinette_webapi + "/test-auth/none")

    assert r.status_code == 200
    assert r.text == '"some_data_from_none"'


def test_request_with_auth_but_not_logged(monkeypatch, tmp_path, moulinette_webapi):

    r = requests.get(moulinette_webapi + "/test-auth/default")

    assert r.status_code == 401
    assert r.text == "Authentication required"


def test_login(monkeypatch, moulinette_webapi):

    r = login(moulinette_webapi)

    assert r.status_code == 200
    assert r.text == "Logged in"
    assert "session.id" in r.cookies
    assert "session.tokens" in r.cookies

    cache_session_default = os.environ['MOULINETTE_CACHE_DIR'] + "/session/default/"
    assert r.cookies["session.id"] + ".asc" in os.listdir(cache_session_default)


def test_login_csrf_attempt(moulinette_webapi):

    # C.f.
    # https://security.stackexchange.com/a/58308
    # https://stackoverflow.com/a/22533680

    r = login(moulinette_webapi, csrf=True)

    assert r.status_code == 403
    assert "session.id" not in r.cookies
    assert "session.tokens" not in r.cookies
    assert "CSRF protection" in r.text


def test_login_then_legit_request_without_cookies(moulinette_webapi):

    login(moulinette_webapi)

    r = requests.get(moulinette_webapi + "/test-auth/default")

    assert r.status_code == 401
    assert r.text == "Authentication required"


def test_login_then_legit_request(moulinette_webapi):

    r_login = login(moulinette_webapi)

    r = requests.get(moulinette_webapi + "/test-auth/default",
                     cookies={"session.id": r_login.cookies["session.id"],
                              "session.tokens": r_login.cookies["session.tokens"], })

    assert r.status_code == 200
    assert r.text == '"some_data_from_default"'


def test_login_then_logout(moulinette_webapi):

    r_login = login(moulinette_webapi)

    r = requests.get(moulinette_webapi + "/logout",
                     cookies={"session.id": r_login.cookies["session.id"],
                              "session.tokens": r_login.cookies["session.tokens"], })

    assert r.status_code == 200
    cache_session_default = os.environ['MOULINETTE_CACHE_DIR'] + "/session/default/"
    assert not r_login.cookies["session.id"] + ".asc" in os.listdir(cache_session_default)

    r = requests.get(moulinette_webapi + "/test-auth/default",
                     cookies={"session.id": r_login.cookies["session.id"],
                              "session.tokens": r_login.cookies["session.tokens"], })

    assert r.status_code == 401
    assert r.text == "Authentication required"
