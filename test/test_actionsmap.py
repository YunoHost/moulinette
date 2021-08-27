import pytest

from moulinette.actionsmap import (
    CommentParameter,
    AskParameter,
    PasswordParameter,
    PatternParameter,
    RequiredParameter,
    ExtraArgumentParser,
    ActionsMap,
)

from moulinette.core import MoulinetteError
from moulinette import m18n, Moulinette


@pytest.fixture
def iface():
    class DummyInterface:
        def prompt():
            pass

    return DummyInterface()


def test_comment_parameter_bad_bool_value(iface, caplog):
    comment = CommentParameter(iface)
    assert comment.validate(True, "a") == "a"
    assert any("expecting a non-empty string" in message for message in caplog.messages)


def test_comment_parameter_bad_empty_string(iface, caplog):
    comment = CommentParameter(iface)
    assert comment.validate("", "a") == "a"
    assert any("expecting a non-empty string" in message for message in caplog.messages)


def test_comment_parameter_bad_type(iface):
    comment = CommentParameter(iface)
    with pytest.raises(TypeError):
        comment.validate({}, "b")


def test_ask_parameter_str_value(iface, caplog):
    ask = AskParameter(iface)
    assert ask.validate("a", "a") == "a"
    assert not len(caplog.messages)


def test_ask_parameter_bad_bool_value(iface, caplog):
    ask = AskParameter(iface)
    assert ask.validate(True, "a") == "a"
    assert any("expecting a non-empty string" in message for message in caplog.messages)


def test_ask_parameter_bad_empty_string(iface, caplog):
    ask = AskParameter(iface)
    assert ask.validate("", "a") == "a"
    assert any("expecting a non-empty string" in message for message in caplog.messages)


def test_ask_parameter_bad_type(iface):
    ask = AskParameter(iface)
    with pytest.raises(TypeError):
        ask.validate({}, "b")


def test_ask_parameter(iface, mocker):
    ask = AskParameter(iface)
    arg = ask("foobar", "a", "a")
    assert arg == "a"

    from moulinette.core import Moulinette18n

    Moulinette._interface = iface
    mocker.patch.object(Moulinette18n, "n", return_value="awesome_test")
    mocker.patch.object(iface, "prompt", return_value="awesome_test")
    arg = ask("foobar", "a", None)
    assert arg == "awesome_test"


def test_password_parameter(iface, mocker):
    ask = PasswordParameter(iface)
    arg = ask("foobar", "a", "a")
    assert arg == "a"

    from moulinette.core import Moulinette18n

    Moulinette._interface = iface
    mocker.patch.object(Moulinette18n, "n", return_value="awesome_test")
    mocker.patch.object(iface, "prompt", return_value="awesome_test")
    arg = ask("foobar", "a", None)
    assert arg == "awesome_test"


def test_pattern_parameter_bad_str_value(iface, caplog):
    pattern = PatternParameter(iface)
    assert pattern.validate("", "a") == ["", "pattern_not_match"]
    assert any("expecting a list" in message for message in caplog.messages)


@pytest.mark.parametrize(
    "iface", [[], ["pattern_alone"], ["pattern", "message", "extra stuff"]]
)
def test_pattern_parameter_bad_list_len(iface):
    pattern = PatternParameter(iface)
    with pytest.raises(TypeError):
        pattern.validate(iface, "a")


def test_pattern_parameter(iface, caplog, mocker):
    pattern = PatternParameter(iface)
    arg = pattern(["foo", "foobar"], "foo_name", "foo_value")
    assert arg == "foo_value"

    error = "error_message"
    mocker.patch("moulinette.Moulinette18n.n", return_value=error)
    with pytest.raises(MoulinetteError) as exception:
        pattern(["foo", "message"], "foo_name", "not_match")

    translation = m18n.g("invalid_argument", argument="foo_name", error=error)
    expected_msg = translation.format(argument="foo_name", error=error)
    assert expected_msg in str(exception)
    assert any("doesn't match pattern" in message for message in caplog.messages)


def test_required_paremeter(iface):
    required = RequiredParameter(iface)
    arg = required(True, "a", "a")
    assert arg == "a"

    assert required.validate(True, "a")
    assert not required.validate(False, "a")


def test_required_paremeter_bad_type(iface):
    required = RequiredParameter(iface)

    with pytest.raises(TypeError):
        required.validate("a", "a")

    with pytest.raises(TypeError):
        required.validate(1, "a")

    with pytest.raises(TypeError):
        required.validate([], "a")

    with pytest.raises(TypeError):
        required.validate({}, "a")


def test_required_paremeter_missing_value(iface, caplog):
    required = RequiredParameter(iface)
    with pytest.raises(MoulinetteError) as exception:
        required(True, "a", "")

    translation = m18n.g("argument_required", argument="a")
    expected_msg = translation.format(argument="a")
    assert expected_msg in str(exception)
    assert any("is required" in message for message in caplog.messages)


def test_actions_map_unknown_authenticator(monkeypatch, tmp_path):

    from moulinette.interfaces.api import ActionsMapParser

    amap = ActionsMap(ActionsMapParser())

    with pytest.raises(MoulinetteError) as exception:
        amap.get_authenticator("unknown")
    assert "No module named" in str(exception)


def test_extra_argument_parser_add_argument(iface):
    extra_argument_parse = ExtraArgumentParser(iface)
    extra_argument_parse.add_argument("Test", "foo", {"ask": "lol"})
    assert "Test" in extra_argument_parse._extra_params
    assert "foo" in extra_argument_parse._extra_params["Test"]
    assert "ask" in extra_argument_parse._extra_params["Test"]["foo"]
    assert extra_argument_parse._extra_params["Test"]["foo"]["ask"] == "lol"

    extra_argument_parse = ExtraArgumentParser(iface)
    extra_argument_parse.add_argument("_global", "foo", {"ask": "lol"})
    assert "_global" in extra_argument_parse._extra_params
    assert "foo" in extra_argument_parse._extra_params["_global"]
    assert "ask" in extra_argument_parse._extra_params["_global"]["foo"]
    assert extra_argument_parse._extra_params["_global"]["foo"]["ask"] == "lol"


def test_extra_argument_parser_add_argument_bad_arg(iface):
    extra_argument_parse = ExtraArgumentParser(iface)
    with pytest.raises(MoulinetteError) as exception:
        extra_argument_parse.add_argument("_global", "foo", {"ask": 1})

    expected_msg = "unable to validate extra parameter '%s' for argument '%s': %s" % (
        "ask",
        "foo",
        "parameter value must be a string, got 1",
    )
    assert expected_msg in str(exception)

    extra_argument_parse = ExtraArgumentParser(iface)
    extra_argument_parse.add_argument("_global", "foo", {"error": 1})

    assert "_global" in extra_argument_parse._extra_params
    assert "foo" in extra_argument_parse._extra_params["_global"]
    assert not len(extra_argument_parse._extra_params["_global"]["foo"])


def test_extra_argument_parser_parse_args(iface, mocker):
    extra_argument_parse = ExtraArgumentParser(iface)
    extra_argument_parse.add_argument("_global", "foo", {"ask": "lol"})
    extra_argument_parse.add_argument("_global", "foo2", {"ask": "lol2"})
    extra_argument_parse.add_argument(
        "_global", "bar", {"password": "lul", "ask": "lul"}
    )

    args = extra_argument_parse.parse_args(
        "_global", {"foo": 1, "foo2": ["a", "b", {"foobar": True}], "bar": "rab"}
    )

    assert "foo" in args
    assert args["foo"] == 1

    assert "foo2" in args
    assert args["foo2"] == ["a", "b", {"foobar": True}]

    assert "bar" in args
    assert args["bar"] == "rab"


def test_actions_map_api():
    from moulinette.interfaces.api import ActionsMapParser

    parser = ActionsMapParser()
    amap = ActionsMap(parser)

    assert amap.main_namespace == "moulitest"
    assert amap.default_authentication == "dummy"
    assert ("GET", "/test-auth/default") in amap.parser.routes
    assert ("POST", "/test-auth/subcat/post") in amap.parser.routes

    assert parser.auth_method(None, ("GET", "/test-auth/default")) == "dummy"
    assert parser.auth_method(None, ("GET", "/test-auth/only-api")) == "dummy"
    assert parser.auth_method(None, ("GET", "/test-auth/only-cli")) is None


def test_actions_map_import_error(mocker):
    from moulinette.interfaces.api import ActionsMapParser

    amap = ActionsMap(ActionsMapParser())

    from moulinette.core import MoulinetteLock

    mocker.patch.object(MoulinetteLock, "_is_son_of", return_value=False)

    orig_import = __import__

    def import_mock(name, globals={}, locals={}, fromlist=[], level=-1):
        if name == "moulitest.testauth":
            mocker.stopall()
            raise ImportError("Yoloswag")
        return orig_import(name, globals, locals, fromlist, level)

    mocker.patch("builtins.__import__", side_effect=import_mock)
    with pytest.raises(MoulinetteError) as exception:
        amap.process({}, timeout=30, route=("GET", "/test-auth/none"))

    expected_msg = "unable to load function % s.%s because: %s" % (
        "moulitest",
        "testauth_none",
        "Yoloswag",
    )
    assert expected_msg in str(exception)


def test_actions_map_cli():
    from moulinette.interfaces.cli import ActionsMapParser
    import argparse

    top_parser = argparse.ArgumentParser(add_help=False)
    top_parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Log and print debug messages",
    )

    parser = ActionsMapParser(top_parser=top_parser)
    amap = ActionsMap(parser)

    assert amap.main_namespace == "moulitest"
    assert amap.default_authentication == "dummy"
    assert "testauth" in amap.parser._subparsers.choices
    assert "none" in amap.parser._subparsers.choices["testauth"]._actions[1].choices
    assert "subcat" in amap.parser._subparsers.choices["testauth"]._actions[1].choices
    assert (
        "default"
        in amap.parser._subparsers.choices["testauth"]
        ._actions[1]
        .choices["subcat"]
        ._actions[1]
        .choices
    )

    assert parser.auth_method(["testauth", "default"]) == "dummy"
    assert parser.auth_method(["testauth", "only-api"]) is None
    assert parser.auth_method(["testauth", "only-cli"]) == "dummy"
