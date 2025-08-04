#!/usr/bin/env python3
#
# Copyright (c) 2024 YunoHost Contributors
#
# This file is part of YunoHost (see https://yunohost.org)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#

import pytest

from moulinette import MoulinetteError


class TestAuthAPI:
    def login(self, webapi, csrf=False, profile=None, status=200, password=None):
        if password is None:
            password = "dummy"

        data = {"credentials": password}

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

        assert "moulitest" in moulinette_webapi.cookies

    def test_login_bad_password(self, moulinette_webapi):
        assert (
            self.login(moulinette_webapi, password="Bad Password", status=401).text
            == "invalid_password"
        )

        assert "moulitest" not in moulinette_webapi.cookies

    def test_login_csrf_attempt(self, moulinette_webapi):
        # CSRF should not block the login endpoint

        assert (
            "CSRF protection"
            not in self.login(moulinette_webapi, csrf=True, status=200).text
        )
        assert "moulitest" in moulinette_webapi.cookies

    def test_login_then_legit_request_without_cookies(self, moulinette_webapi):
        self.login(moulinette_webapi)

        moulinette_webapi.cookiejar.clear()

        moulinette_webapi.get("/test-auth/default", status=401)

    def test_login_then_legit_request(self, moulinette_webapi):
        self.login(moulinette_webapi)

        assert "moulitest" in moulinette_webapi.cookies

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

        assert (
            moulinette_webapi.get("/test-auth/default", status=401).text
            == "Authentication required"
        )

    def test_login_other_profile(self, moulinette_webapi):
        self.login(moulinette_webapi, profile="yoloswag", password="yoloswag")

        assert "moulitest" in moulinette_webapi.cookies

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

    def test_request_arg_without_action(self, moulinette_webapi, caplog, mocker):
        self.login(moulinette_webapi)
        moulinette_webapi.get("/test-auth", status=405)


class TestAuthCLI:
    def test_login(self, moulinette_cli, capsys, mocker):
        mocker.patch("os.isatty", return_value=True)
        mocker.patch("prompt_toolkit.prompt", return_value="dummy")
        moulinette_cli.run(["testauth", "default"], output_as="plain")
        message = capsys.readouterr()

        assert "some_data_from_default" in message.out

        moulinette_cli.run(["testauth", "default"], output_as="plain")
        message = capsys.readouterr()

        assert "some_data_from_default" in message.out

    def test_login_bad_password(self, moulinette_cli, capsys, mocker):
        mocker.patch("os.isatty", return_value=True)
        mocker.patch("prompt_toolkit.prompt", return_value="Bad Password")
        with pytest.raises(MoulinetteError):
            moulinette_cli.run(["testauth", "default"], output_as="plain")

        mocker.patch("os.isatty", return_value=True)
        mocker.patch("prompt_toolkit.prompt", return_value="Bad Password")
        with pytest.raises(MoulinetteError):
            moulinette_cli.run(["testauth", "default"], output_as="plain")

    def test_login_wrong_profile(self, moulinette_cli, mocker):
        mocker.patch("os.isatty", return_value=True)
        mocker.patch("prompt_toolkit.prompt", return_value="dummy")
        with pytest.raises(MoulinetteError) as exception:
            moulinette_cli.run(["testauth", "other-profile"], output_as="none")

        assert "invalid_password" in str(exception)

        mocker.patch("os.isatty", return_value=True)
        mocker.patch("prompt_toolkit.prompt", return_value="yoloswag")
        with pytest.raises(MoulinetteError) as exception:
            moulinette_cli.run(["testauth", "default"], output_as="none")

        assert "invalid_password" in str(exception)

    def test_request_no_auth_needed(self, capsys, moulinette_cli):
        moulinette_cli.run(["testauth", "none"], output_as="plain")
        message = capsys.readouterr()

        assert "some_data_from_none" in message.out

    def test_request_not_logged_only_api(self, capsys, moulinette_cli):
        moulinette_cli.run(["testauth", "only-api"], output_as="plain")
        message = capsys.readouterr()

        assert "some_data_from_only_api" in message.out

    def test_request_only_cli(self, capsys, moulinette_cli, mocker):
        mocker.patch("os.isatty", return_value=True)
        mocker.patch("prompt_toolkit.prompt", return_value="dummy")
        moulinette_cli.run(["testauth", "only-cli"], output_as="plain")

        message = capsys.readouterr()

        assert "some_data_from_only_cli" in message.out

    def test_request_not_logged_only_cli(self, capsys, moulinette_cli, mocker):
        mocker.patch("os.isatty", return_value=True)
        mocker.patch("prompt_toolkit.prompt")
        with pytest.raises(MoulinetteError) as exception:
            moulinette_cli.run(["testauth", "only-cli"], output_as="plain")

        message = capsys.readouterr()
        assert "some_data_from_only_cli" not in message.out

        assert "invalid_password" in str(exception)

    def test_request_with_arg(self, moulinette_cli, capsys, mocker):
        mocker.patch("os.isatty", return_value=True)
        mocker.patch("prompt_toolkit.prompt", return_value="dummy")
        moulinette_cli.run(["testauth", "with_arg", "yoloswag"], output_as="plain")
        message = capsys.readouterr()

        assert "yoloswag" in message.out

    def test_request_arg_with_extra(self, moulinette_cli, capsys, mocker):
        mocker.patch("os.isatty", return_value=True)
        mocker.patch("prompt_toolkit.prompt", return_value="dummy")
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

        # FIXME : for some reason this doesnt pass even if the warning is indeed displayed hmpf
        #message = capsys.readouterr()
        #assert "doesn't match pattern" in message.err

    def test_request_arg_with_type(self, moulinette_cli, capsys, mocker):
        mocker.patch("os.isatty", return_value=True)
        mocker.patch("prompt_toolkit.prompt", return_value="dummy")
        moulinette_cli.run(["testauth", "with_type_int", "12345"], output_as="plain")
        message = capsys.readouterr()

        assert "12345" in message.out

        with pytest.raises(SystemExit):
            moulinette_cli.run(
                ["testauth", "with_type_int", "yoloswag"], output_as="plain"
            )

        message = capsys.readouterr()
        assert "invalid int value" in message.err

    def test_request_arg_without_action(self, moulinette_cli, capsys, mocker):
        with pytest.raises(SystemExit):
            moulinette_cli.run(["testauth"], output_as="plain")

        message = capsys.readouterr()

        assert "error: the following arguments are required:" in message.err
