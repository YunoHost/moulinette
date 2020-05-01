import os
import pytest

from moulinette import MoulinetteError
from moulinette import m18n


class TestAuthAPI:
    def login(self, webapi, csrf=False, profile=None, status=200, password="default"):
        data = {"password": password}
        if profile:
            data["profile"] = profile

        return webapi.post(
            "/login",
            data,
            status=status,
            headers=None if csrf else {"X-Requested-With": ""},
        )

    def test_request_no_auth_needed(self, moulinette_webapi):
        assert (
            moulinette_webapi.get("/test-auth/none", status=200).text
            == '"some_data_from_none"'
        )

    def test_request_no_auth_needed_subcategories(self, moulinette_webapi):
        assert (
            moulinette_webapi.get("/test-auth/subcat/none", status=200).text
            == '"some_data_from_subcat_none"'
        )

    def test_request_with_auth_but_not_logged(self, moulinette_webapi):
        assert (
            moulinette_webapi.get("/test-auth/default", status=401).text
            == "Authentication required"
        )

    def test_request_with_auth_subcategories_but_not_logged(self, moulinette_webapi):
        assert (
            moulinette_webapi.get("/test-auth/subcat/default", status=401).text
            == "Authentication required"
        )

    def test_request_not_logged_only_api(self, moulinette_webapi):
        assert (
            moulinette_webapi.get("/test-auth/only-api", status=401).text
            == "Authentication required"
        )

    def test_request_only_api(self, moulinette_webapi):
        self.login(moulinette_webapi)
        assert (
            moulinette_webapi.get("/test-auth/only-api", status=200).text
            == '"some_data_from_only_api"'
        )

    def test_request_not_logged_only_cli(self, moulinette_webapi):
        assert (
            moulinette_webapi.get("/test-auth/only-cli", status=200).text
            == '"some_data_from_only_cli"'
        )

    def test_login(self, moulinette_webapi):
        assert self.login(moulinette_webapi).text == "Logged in"

        assert "session.id" in moulinette_webapi.cookies
        assert "session.tokens" in moulinette_webapi.cookies

        cache_session_default = os.environ["MOULINETTE_CACHE_DIR"] + "/session/default/"
        assert moulinette_webapi.cookies["session.id"] + ".asc" in os.listdir(
            cache_session_default
        )

    def test_login_bad_password(self, moulinette_webapi):
        assert (
            self.login(moulinette_webapi, password="Bad Password", status=401).text
            == "Invalid password"
        )

        assert "session.id" not in moulinette_webapi.cookies
        assert "session.tokens" not in moulinette_webapi.cookies

    def test_login_csrf_attempt(self, moulinette_webapi):
        # C.f.
        # https://security.stackexchange.com/a/58308
        # https://stackoverflow.com/a/22533680

        assert (
            "CSRF protection"
            in self.login(moulinette_webapi, csrf=True, status=403).text
        )
        assert not any(c.name == "session.id" for c in moulinette_webapi.cookiejar)
        assert not any(c.name == "session.tokens" for c in moulinette_webapi.cookiejar)

    def test_login_then_legit_request_without_cookies(self, moulinette_webapi):
        self.login(moulinette_webapi)

        moulinette_webapi.cookiejar.clear()

        moulinette_webapi.get("/test-auth/default", status=401)

    def test_login_then_legit_request(self, moulinette_webapi):
        self.login(moulinette_webapi)

        assert (
            moulinette_webapi.get("/test-auth/default", status=200).text
            == '"some_data_from_default"'
        )

        assert (
            moulinette_webapi.get("/test-auth/subcat/default", status=200).text
            == '"some_data_from_subcat_default"'
        )

    def test_login_then_logout(self, moulinette_webapi):
        self.login(moulinette_webapi)

        moulinette_webapi.get("/logout", status=200)

        cache_session_default = os.environ["MOULINETTE_CACHE_DIR"] + "/session/default/"
        assert not moulinette_webapi.cookies["session.id"] + ".asc" in os.listdir(
            cache_session_default
        )

        assert (
            moulinette_webapi.get("/test-auth/default", status=401).text
            == "Authentication required"
        )

    def test_login_other_profile(self, moulinette_webapi):
        self.login(moulinette_webapi, profile="yoloswag", password="yoloswag")

        assert "session.id" in moulinette_webapi.cookies
        assert "session.tokens" in moulinette_webapi.cookies

        cache_session_default = (
            os.environ["MOULINETTE_CACHE_DIR"] + "/session/yoloswag/"
        )
        assert moulinette_webapi.cookies["session.id"] + ".asc" in os.listdir(
            cache_session_default
        )

    def test_login_wrong_profile(self, moulinette_webapi):
        self.login(moulinette_webapi)

        assert (
            moulinette_webapi.get("/test-auth/other-profile", status=401).text
            == "Authentication required"
        )

        moulinette_webapi.get("/logout", status=200)

        self.login(moulinette_webapi, profile="yoloswag", password="yoloswag")

        assert (
            moulinette_webapi.get("/test-auth/default", status=401).text
            == "Authentication required"
        )

    def test_login_ldap(self, moulinette_webapi, ldap_server, mocker):
        mocker.patch(
            "moulinette.authenticators.ldap.Authenticator._get_uri",
            return_value=ldap_server.uri,
        )
        self.login(moulinette_webapi, profile="ldap", password="yunohost")

        assert (
            moulinette_webapi.get("/test-auth/ldap", status=200).text
            == '"some_data_from_ldap"'
        )

    def test_request_with_arg(self, moulinette_webapi, capsys):
        self.login(moulinette_webapi)

        assert (
            moulinette_webapi.get("/test-auth/with_arg/yoloswag", status=200).text
            == '"yoloswag"'
        )

    def test_request_arg_with_extra(self, moulinette_webapi, caplog, mocker):
        self.login(moulinette_webapi)

        assert (
            moulinette_webapi.get(
                "/test-auth/with_extra_str_only/YoLoSwAg", status=200
            ).text
            == '"YoLoSwAg"'
        )

        error = "error_message"
        mocker.patch("moulinette.Moulinette18n.n", return_value=error)

        moulinette_webapi.get("/test-auth/with_extra_str_only/12345", status=400)

        assert any("doesn't match pattern" in message for message in caplog.messages)

    def test_request_arg_with_type(self, moulinette_webapi, caplog, mocker):
        self.login(moulinette_webapi)

        assert (
            moulinette_webapi.get("/test-auth/with_type_int/12345", status=200).text
            == "12345"
        )

        error = "error_message"
        mocker.patch("moulinette.Moulinette18n.g", return_value=error)
        moulinette_webapi.get("/test-auth/with_type_int/yoloswag", status=400)


class TestAuthCLI:
    def test_login(self, moulinette_cli, capsys, mocker):
        mocker.patch("getpass.getpass", return_value="default")
        moulinette_cli.run(["testauth", "default"], output_as="plain")
        message = capsys.readouterr()

        assert "some_data_from_default" in message.out

        moulinette_cli.run(["testauth", "default"], output_as="plain")
        message = capsys.readouterr()

        assert "some_data_from_default" in message.out

    def test_login_bad_password(self, moulinette_cli, capsys, mocker):
        mocker.patch("getpass.getpass", return_value="Bad Password")
        with pytest.raises(MoulinetteError):
            moulinette_cli.run(["testauth", "default"], output_as="plain")

        mocker.patch("getpass.getpass", return_value="Bad Password")
        with pytest.raises(MoulinetteError):
            moulinette_cli.run(["testauth", "default"], output_as="plain")

    def test_login_wrong_profile(self, moulinette_cli, mocker):
        mocker.patch("getpass.getpass", return_value="default")
        with pytest.raises(MoulinetteError) as exception:
            moulinette_cli.run(["testauth", "other-profile"], output_as="none")

        translation = m18n.g("invalid_password")
        expected_msg = translation.format()
        assert expected_msg in str(exception)

        mocker.patch("getpass.getpass", return_value="yoloswag")
        with pytest.raises(MoulinetteError) as exception:
            moulinette_cli.run(["testauth", "default"], output_as="none")

        expected_msg = translation.format()
        assert expected_msg in str(exception)

    def test_request_no_auth_needed(self, capsys, moulinette_cli):
        moulinette_cli.run(["testauth", "none"], output_as="plain")
        message = capsys.readouterr()

        assert "some_data_from_none" in message.out

    def test_request_not_logged_only_api(self, capsys, moulinette_cli):
        moulinette_cli.run(["testauth", "only-api"], output_as="plain")
        message = capsys.readouterr()

        assert "some_data_from_only_api" in message.out

    def test_request_only_cli(self, capsys, moulinette_cli, mocker):
        mocker.patch("getpass.getpass", return_value="default")
        moulinette_cli.run(["testauth", "only-cli"], output_as="plain")

        message = capsys.readouterr()

        assert "some_data_from_only_cli" in message.out

    def test_request_not_logged_only_cli(self, capsys, moulinette_cli, mocker):
        mocker.patch("getpass.getpass")
        with pytest.raises(MoulinetteError) as exception:
            moulinette_cli.run(["testauth", "only-cli"], output_as="plain")

        message = capsys.readouterr()
        assert "some_data_from_only_cli" not in message.out

        translation = m18n.g("invalid_password")
        expected_msg = translation.format()
        assert expected_msg in str(exception)

    def test_request_with_callback(self, moulinette_cli, capsys, mocker):
        mocker.patch("getpass.getpass", return_value="default")
        moulinette_cli.run(["--version"], output_as="plain")
        message = capsys.readouterr()

        assert "666" in message.out

        moulinette_cli.run(["-v"], output_as="plain")
        message = capsys.readouterr()

        assert "666" in message.out

        with pytest.raises(MoulinetteError):
            moulinette_cli.run(["--wersion"], output_as="plain")
        message = capsys.readouterr()

        assert "cannot get value from callback method" in message.err

    def test_request_with_arg(self, moulinette_cli, capsys, mocker):
        mocker.patch("getpass.getpass", return_value="default")
        moulinette_cli.run(["testauth", "with_arg", "yoloswag"], output_as="plain")
        message = capsys.readouterr()

        assert "yoloswag" in message.out

    def test_request_arg_with_extra(self, moulinette_cli, capsys, mocker):
        mocker.patch("getpass.getpass", return_value="default")
        moulinette_cli.run(
            ["testauth", "with_extra_str_only", "YoLoSwAg"], output_as="plain"
        )
        message = capsys.readouterr()

        assert "YoLoSwAg" in message.out

        error = "error_message"
        mocker.patch("moulinette.Moulinette18n.n", return_value=error)
        with pytest.raises(MoulinetteError):
            moulinette_cli.run(
                ["testauth", "with_extra_str_only", "12345"], output_as="plain"
            )

        message = capsys.readouterr()
        assert "doesn't match pattern" in message.err

    def test_request_arg_with_type(self, moulinette_cli, capsys, mocker):
        mocker.patch("getpass.getpass", return_value="default")
        moulinette_cli.run(["testauth", "with_type_int", "12345"], output_as="plain")
        message = capsys.readouterr()

        assert "12345" in message.out

        mocker.patch("sys.exit")
        with pytest.raises(MoulinetteError):
            moulinette_cli.run(
                ["testauth", "with_type_int", "yoloswag"], output_as="plain"
            )

        message = capsys.readouterr()
        assert "invalid int value" in message.err
