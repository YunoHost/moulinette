import os


def login(webapi, csrf=False, profile=None, status=200):

    data = {"password": "Yoloswag"}
    if profile:
        data["profile"] = profile

    return webapi.post("/login", data,
                       status=status,
                       headers=None if csrf else {"X-Requested-With": ""})


def test_request_no_auth_needed(moulinette_webapi):

    assert moulinette_webapi.get("/test-auth/none", status=200).text == '"some_data_from_none"'


def test_request_with_auth_but_not_logged(moulinette_webapi):

    assert moulinette_webapi.get("/test-auth/default", status=401).text == "Authentication required"


def test_login(moulinette_webapi):

    assert login(moulinette_webapi).text == "Logged in"

    assert "session.id" in moulinette_webapi.cookies
    assert "session.tokens" in moulinette_webapi.cookies

    cache_session_default = os.environ['MOULINETTE_CACHE_DIR'] + "/session/default/"
    assert moulinette_webapi.cookies["session.id"] + ".asc" in os.listdir(cache_session_default)


def test_login_csrf_attempt(moulinette_webapi):

    # C.f.
    # https://security.stackexchange.com/a/58308
    # https://stackoverflow.com/a/22533680

    assert "CSRF protection" in login(moulinette_webapi, csrf=True, status=403).text
    assert not any(c.name == "session.id" for c in moulinette_webapi.cookiejar)
    assert not any(c.name == "session.tokens" for c in moulinette_webapi.cookiejar)


def test_login_then_legit_request_without_cookies(moulinette_webapi):

    login(moulinette_webapi)

    moulinette_webapi.cookiejar.clear()

    moulinette_webapi.get("/test-auth/default", status=401)


def test_login_then_legit_request(moulinette_webapi):

    login(moulinette_webapi)

    assert moulinette_webapi.get("/test-auth/default", status=200).text == '"some_data_from_default"'


def test_login_then_logout(moulinette_webapi):

    login(moulinette_webapi)

    moulinette_webapi.get("/logout", status=200)

    cache_session_default = os.environ['MOULINETTE_CACHE_DIR'] + "/session/default/"
    assert not moulinette_webapi.cookies["session.id"] + ".asc" in os.listdir(cache_session_default)

    assert moulinette_webapi.get("/test-auth/default", status=401).text == "Authentication required"
