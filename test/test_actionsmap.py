import pytest

from moulinette.actionsmap import (
    CommentParameter,
    AskParameter,
    PatternParameter,
    RequiredParameter,
    ActionsMap,
)
from moulinette.interfaces import BaseActionsMapParser
from moulinette.core import MoulinetteError


@pytest.fixture
def iface():
    return 'iface'


def test_comment_parameter_bad_bool_value(iface, caplog):
    comment = CommentParameter(iface)
    assert comment.validate(True, 'a') == 'a'
    assert any('expecting a non-empty string' in message for message in caplog.messages)


def test_comment_parameter_bad_empty_string(iface, caplog):
    comment = CommentParameter(iface)
    assert comment.validate('', 'a') == 'a'
    assert any('expecting a non-empty string' in message for message in caplog.messages)


def test_comment_parameter_bad_type(iface):
    comment = CommentParameter(iface)
    with pytest.raises(TypeError):
        comment.validate({}, 'b')


def test_ask_parameter_bad_bool_value(iface, caplog):
    ask = AskParameter(iface)
    assert ask.validate(True, 'a') == 'a'
    assert any('expecting a non-empty string' in message for message in caplog.messages)


def test_ask_parameter_bad_empty_string(iface, caplog):
    ask = AskParameter(iface)
    assert ask.validate('', 'a') == 'a'
    assert any('expecting a non-empty string' in message for message in caplog.messages)


def test_ask_parameter_bad_type(iface):
    ask = AskParameter(iface)
    with pytest.raises(TypeError):
        ask.validate({}, 'b')


def test_pattern_parameter_bad_str_value(iface, caplog):
    pattern = PatternParameter(iface)
    assert pattern.validate('', 'a') == ['', 'pattern_not_match']
    assert any('expecting a list' in message for message in caplog.messages)


@pytest.mark.parametrize(
    'iface', [[], ['pattern_alone'], ['pattern', 'message', 'extra stuff']]
)
def test_pattern_parameter_bad_list_len(iface):
    pattern = PatternParameter(iface)
    with pytest.raises(TypeError):
        pattern.validate(iface, 'a')


def test_required_paremeter_missing_value(iface):
    required = RequiredParameter(iface)
    with pytest.raises(MoulinetteError) as exception:
        required(True, 'a', '')
    assert 'is required' in str(exception)


def test_actions_map_unknown_authenticator(monkeypatch, tmp_path):
    monkeypatch.setenv('MOULINETTE_DATA_DIR', str(tmp_path))
    actionsmap_dir = actionsmap_dir = tmp_path / 'actionsmap'
    actionsmap_dir.mkdir()

    amap = ActionsMap(BaseActionsMapParser)
    with pytest.raises(ValueError) as exception:
        amap.get_authenticator(profile='unknown')
    assert 'Unknown authenticator' in str(exception)
