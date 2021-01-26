import os
from subprocess import CalledProcessError

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
    def stdout_callback(a):
        assert a == "foo" or a == "bar"

    def stderr_callback(a):
        assert False  # we shouldn't reach this line

    callbacks = (lambda l: stdout_callback(l), lambda l: stderr_callback(l))

    call_async_output(["cat", str(test_file)], callbacks)

    with pytest.raises(TypeError):
        call_async_output(["cat", str(test_file)], 1)

    def callbackA(a):
        assert a == "foo" or a == "bar"

    def callbackB(a):
        assert "cat: doesntexists" in a

    callback = (callbackA, callbackB)
    call_async_output(["cat", str(test_file)], callback)
    call_async_output(["cat", "doesntexists"], callback)


def test_call_async_output_kwargs(test_file, mocker):
    def stdinfo_callback(a):
        assert False  # we shouldn't reach this line

    def stdout_callback(a):
        assert a == "foo" or a == "bar"

    def stderr_callback(a):
        assert False  # we shouldn't reach this line

    callbacks = (
        lambda l: stdout_callback(l),
        lambda l: stderr_callback(l),
        lambda l: stdinfo_callback(l),
    )

    with pytest.raises(ValueError):
        call_async_output(["cat", str(test_file)], callbacks, stdout=None)
    with pytest.raises(ValueError):
        call_async_output(["cat", str(test_file)], callbacks, stderr=None)
    with pytest.raises(TypeError):
        call_async_output(["cat", str(test_file)], callbacks, stdinfo=None)

    dirname = os.path.dirname(str(test_file))
    os.mkdir(os.path.join(dirname, "testcwd"))
    call_async_output(
        ["cat", str(test_file)], callbacks, cwd=os.path.join(dirname, "testcwd")
    )


def test_check_output(test_file):
    assert check_output(["cat", str(test_file)], shell=False) == "foo\nbar"

    assert check_output("cat %s" % str(test_file)) == "foo\nbar"
