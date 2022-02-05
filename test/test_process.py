import os
from subprocess import CalledProcessError

import mock
import pytest

from moulinette.utils.process import run_commands
from moulinette.utils.process import call_async_output
from moulinette.utils.process import check_output


def test_run_shell_command_list(test_file):
    assert os.path.exists(str(test_file))
    run_commands(["rm -f %s" % str(test_file)])
    assert not os.path.exists(str(test_file))


def test_run_shell_bad_cmd():
    with pytest.raises(CalledProcessError):
        run_commands(["yolo swag"])


def test_run_shell_bad_cmd_with_callback():
    def callback(a, b, c):
        assert isinstance(a, int)
        assert isinstance(b, str)
        # assert isinstance(c, str)
        return True

    assert run_commands(["yolo swag", "yolo swag", "yolo swag"], callback=callback) == 3

    def callback(a, b, c):
        assert isinstance(a, int)
        assert isinstance(b, str)
        # assert isinstance(c, str)
        return False

    assert run_commands(["yolo swag", "yolo swag"], callback=callback) == 1

    def callback(a, b, c):
        assert isinstance(a, int)
        assert isinstance(b, str)
        assert isinstance(c, tuple)
        return True

    run_commands(["yolo swag"], separate_stderr=True, callback=callback)


def test_run_shell_bad_callback():
    callback = 1
    with pytest.raises(ValueError):
        run_commands(["ls"], callback=callback)


def test_run_shell_kwargs():
    with pytest.raises(ValueError):
        run_commands([""], stdout="None")

    with pytest.raises(ValueError):
        run_commands([""], stderr="None")

    run_commands(["ls"], cwd="/tmp")

    with pytest.raises(OSError):
        run_commands(["ls"], cwd="/yoloswag")


def test_call_async_output(test_file):

    mock_callback_stdout = mock.Mock()
    mock_callback_stderr = mock.Mock()

    def stdout_callback(a):
        mock_callback_stdout(a)

    def stderr_callback(a):
        mock_callback_stderr(a)

    callbacks = (lambda l: stdout_callback(l), lambda l: stderr_callback(l))

    call_async_output(["cat", str(test_file)], callbacks)

    calls = [mock.call("foo"), mock.call("bar")]
    mock_callback_stdout.assert_has_calls(calls)
    mock_callback_stderr.assert_not_called()

    mock_callback_stdout.reset_mock()
    mock_callback_stderr.reset_mock()

    with pytest.raises(TypeError):
        call_async_output(["cat", str(test_file)], 1)

    mock_callback_stdout.assert_not_called()
    mock_callback_stderr.assert_not_called()

    mock_callback_stdout.reset_mock()
    mock_callback_stderr.reset_mock()

    def callback_stdout(a):
        mock_callback_stdout(a)

    def callback_stderr(a):
        mock_callback_stderr(a)

    callback = (callback_stdout, callback_stderr)
    call_async_output(["cat", str(test_file)], callback)
    calls = [mock.call("foo"), mock.call("bar")]
    mock_callback_stdout.assert_has_calls(calls)
    mock_callback_stderr.assert_not_called()
    mock_callback_stdout.reset_mock()
    mock_callback_stderr.reset_mock()

    env_var = {"LANG": "C"}
    call_async_output(["cat", "doesntexists"], callback, env=env_var)
    calls = [mock.call("cat: doesntexists: No such file or directory")]
    mock_callback_stdout.assert_not_called()
    mock_callback_stderr.assert_has_calls(calls)


def test_call_async_output_kwargs(test_file, mocker):

    mock_callback_stdout = mock.Mock()
    mock_callback_stdinfo = mock.Mock()
    mock_callback_stderr = mock.Mock()

    def stdinfo_callback(a):
        mock_callback_stdinfo(a)

    def stdout_callback(a):
        mock_callback_stdout(a)

    def stderr_callback(a):
        mock_callback_stderr(a)

    callbacks = (
        lambda l: stdout_callback(l),
        lambda l: stderr_callback(l),
        lambda l: stdinfo_callback(l),
    )

    with pytest.raises(ValueError):
        call_async_output(["cat", str(test_file)], callbacks, stdout=None)
    mock_callback_stdout.assert_not_called()
    mock_callback_stdinfo.assert_not_called()
    mock_callback_stderr.assert_not_called()

    mock_callback_stdout.reset_mock()
    mock_callback_stdinfo.reset_mock()
    mock_callback_stderr.reset_mock()

    with pytest.raises(ValueError):
        call_async_output(["cat", str(test_file)], callbacks, stderr=None)
    mock_callback_stdout.assert_not_called()
    mock_callback_stdinfo.assert_not_called()
    mock_callback_stderr.assert_not_called()

    mock_callback_stdout.reset_mock()
    mock_callback_stdinfo.reset_mock()
    mock_callback_stderr.reset_mock()

    with pytest.raises(TypeError):
        call_async_output(["cat", str(test_file)], callbacks, stdinfo=None)
    mock_callback_stdout.assert_not_called()
    mock_callback_stdinfo.assert_not_called()
    mock_callback_stderr.assert_not_called()

    mock_callback_stdout.reset_mock()
    mock_callback_stdinfo.reset_mock()
    mock_callback_stderr.reset_mock()

    dirname = os.path.dirname(str(test_file))
    os.mkdir(os.path.join(dirname, "testcwd"))
    call_async_output(
        ["cat", str(test_file)], callbacks, cwd=os.path.join(dirname, "testcwd")
    )
    calls = [mock.call("foo"), mock.call("bar")]
    mock_callback_stdout.assert_has_calls(calls)
    mock_callback_stdinfo.assert_not_called()
    mock_callback_stderr.assert_not_called()


def test_check_output(test_file):
    assert check_output(["cat", str(test_file)], shell=False) == "foo\nbar"

    assert check_output("cat %s" % str(test_file)) == "foo\nbar"
