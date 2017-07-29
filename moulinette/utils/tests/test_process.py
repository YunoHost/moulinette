# General python lib
import os
import pwd
import pytest

# Moulinette specific
from subprocess import CalledProcessError
from moulinette.utils.process import run_commands

# We define a dummy context with test folders and files

TMP_TEST_DIR = "/tmp/test_iohelpers"
TMP_TEST_FILE = "%s/foofile" % TMP_TEST_DIR
NON_ROOT_USER = "admin"
NON_ROOT_GROUP = "mail"


def setup_function(function):

    os.system("rm -rf %s" % TMP_TEST_DIR)
    os.system("mkdir %s" % TMP_TEST_DIR)
    os.system("echo 'foo\nbar' > %s" % TMP_TEST_FILE)
    os.system("chmod 700 %s" % TMP_TEST_FILE)


def teardown_function(function):

    os.seteuid(0)
    os.system("rm -rf /tmp/test_iohelpers/")


# Helper to try stuff as non-root
def switch_to_non_root_user():

    nonrootuser = pwd.getpwnam(NON_ROOT_USER).pw_uid
    os.seteuid(nonrootuser)

###############################################################################
#   Test run shell commands                                                   #
###############################################################################


def test_run_shell_command_list():

    commands = ["rm -f %s" % TMP_TEST_FILE]

    assert os.path.exists(TMP_TEST_FILE)
    run_commands(commands)
    assert not os.path.exists(TMP_TEST_FILE)


def test_run_shell_badcommand():

    commands = ["yolo swag"]

    with pytest.raises(CalledProcessError):
        run_commands(commands)


def test_run_shell_command_badpermissions():

    commands = ["rm -f %s" % TMP_TEST_FILE]

    switch_to_non_root_user()
    with pytest.raises(CalledProcessError):
        run_commands(commands)
