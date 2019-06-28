import os
from subprocess import CalledProcessError

import pytest

from moulinette.utils.process import run_commands


def test_run_shell_command_list(test_file):
    assert os.path.exists(str(test_file))
    run_commands(['rm -f %s' % str(test_file)])
    assert not os.path.exists(str(test_file))


def test_run_shell_bad_cmd():
    with pytest.raises(CalledProcessError):
        run_commands(['yolo swag'])
