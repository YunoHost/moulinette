# encoding: utf-8

"""
Testing moulinette utils filesystem
"""

import mock
import pytest

# Moulinette specific
from moulinette.core import MoulinetteError
from moulinette.utils import filesystem



###############################################################################
# Test reading a file
###############################################################################

@mock.patch('os.path.isfile')
def test_read_file_raise_error_for_non_existant_file(isfile):
    isfile.return_value = False
    with pytest.raises(MoulinetteError):
        filesystem.read_file('non existent file')


@mock.patch('builtins.open')
def test_read_file_raise_error_for_file_with_bad_permission(open):
    open.side_effect = IOError()
    with pytest.raises(MoulinetteError):
        filesystem.read_file('non openable file')


@mock.patch('os.path.isfile')
@mock.patch('builtins.open')
def test_read_file_return_file_content(open, isfile):
    isfile.return_value = True
    file_content = 'file content'
    open.return_value = fake_open(file_content)

    content = filesystem.read_file('fake_file.txt')

    assert content == file_content, 'read_file returned expected content'


def fake_open(content):
    """Return a mock for opening a file with given content

    This function is for mocking open() when used in a context manager.
    """
    fake_file = mock.Mock(read=mock.Mock(return_value=content))
    # open is used as a context manager so we fake __enter__ to return the file
    return mock.Mock(__enter__=mock.Mock(return_value=fake_file), __exit__=mock.Mock())


#def test_read_json():
#
#    content = read_json(TMP_TEST_JSON)
#    assert "foo" in list(content.keys())
#    assert content["foo"] == "bar"
#
#
#def test_read_json_badjson():
#
#    os.system("echo '{ not valid json lol }' > %s" % TMP_TEST_JSON)
#
#    with pytest.raises(MoulinetteError):
#        read_json(TMP_TEST_JSON)
#
#
################################################################################
##   Test file write                                                           #
################################################################################
#
#
#def test_write_to_existing_file():
#
#    assert os.path.exists(TMP_TEST_FILE)
#    write_to_file(TMP_TEST_FILE, "yolo\nswag")
#    assert read_file(TMP_TEST_FILE) == "yolo\nswag"
#
#
#def test_write_to_new_file():
#
#    new_file = "%s/barfile" % TMP_TEST_DIR
#    assert not os.path.exists(new_file)
#    write_to_file(new_file, "yolo\nswag")
#    assert os.path.exists(new_file)
#    assert read_file(new_file) == "yolo\nswag"
#
#
#def test_write_to_existing_file_badpermissions():
#
#    assert os.path.exists(TMP_TEST_FILE)
#    switch_to_non_root_user()
#    with pytest.raises(MoulinetteError):
#        write_to_file(TMP_TEST_FILE, "yolo\nswag")
#
#
#def test_write_to_new_file_badpermissions():
#
#    switch_to_non_root_user()
#    new_file = "%s/barfile" % TMP_TEST_DIR
#    assert not os.path.exists(new_file)
#    with pytest.raises(MoulinetteError):
#        write_to_file(new_file, "yolo\nswag")
#
#
#def test_write_to_folder():
#
#    with pytest.raises(AssertionError):
#        write_to_file(TMP_TEST_DIR, "yolo\nswag")
#
#
#def test_write_inside_nonexistent_folder():
#
#    with pytest.raises(AssertionError):
#        write_to_file("/toto/test", "yolo\nswag")
#
#
#def test_write_to_file_with_a_list():
#
#    assert os.path.exists(TMP_TEST_FILE)
#    write_to_file(TMP_TEST_FILE, ["yolo", "swag"])
#    assert read_file(TMP_TEST_FILE) == "yolo\nswag"
#
#
#def test_append_to_existing_file():
#
#    assert os.path.exists(TMP_TEST_FILE)
#    append_to_file(TMP_TEST_FILE, "yolo\nswag")
#    assert read_file(TMP_TEST_FILE) == "foo\nbar\nyolo\nswag"
#
#
#def test_append_to_new_file():
#
#    new_file = "%s/barfile" % TMP_TEST_DIR
#    assert not os.path.exists(new_file)
#    append_to_file(new_file, "yolo\nswag")
#    assert os.path.exists(new_file)
#    assert read_file(new_file) == "yolo\nswag"
#
#
#def text_write_dict_to_json():
#
#    dummy_dict = {"foo": 42, "bar": ["a", "b", "c"]}
#    write_to_json(TMP_TEST_FILE, dummy_dict)
#    j = read_json(TMP_TEST_FILE)
#    assert "foo" in list(j.keys())
#    assert "bar" in list(j.keys())
#    assert j["foo"] == 42
#    assert j["bar"] == ["a", "b", "c"]
#    assert read_file(TMP_TEST_FILE) == "foo\nbar\nyolo\nswag"
#
#
#def text_write_list_to_json():
#
#    dummy_list = ["foo", "bar", "baz"]
#    write_to_json(TMP_TEST_FILE, dummy_list)
#    j = read_json(TMP_TEST_FILE)
#    assert j == ["foo", "bar", "baz"]
#
#
#def test_write_to_json_badpermissions():
#
#    switch_to_non_root_user()
#    dummy_dict = {"foo": 42, "bar": ["a", "b", "c"]}
#    with pytest.raises(MoulinetteError):
#        write_to_json(TMP_TEST_FILE, dummy_dict)
#
#
#def test_write_json_inside_nonexistent_folder():
#
#    with pytest.raises(AssertionError):
#        write_to_file("/toto/test.json", ["a", "b"])
#
#
################################################################################
##   Test file remove                                                          #
################################################################################
#
#
#def test_remove_file():
#
#    rm(TMP_TEST_FILE)
#    assert not os.path.exists(TMP_TEST_FILE)
#
#
#def test_remove_file_badpermissions():
#
#    switch_to_non_root_user()
#    with pytest.raises(MoulinetteError):
#        rm(TMP_TEST_FILE)
#
#
#def test_remove_directory():
#
#    rm(TMP_TEST_DIR, recursive=True)
#    assert not os.path.exists(TMP_TEST_DIR)
#
#
################################################################################
##   Test permission change                                                    #
################################################################################
#
#
#def get_permissions(file_path):
#    from stat import ST_MODE
#    return (pwd.getpwuid(os.stat(file_path).st_uid).pw_name,
#            pwd.getpwuid(os.stat(file_path).st_gid).pw_name,
#            oct(os.stat(file_path)[ST_MODE])[-3:])
#
#
## FIXME - should split the test of chown / chmod as independent tests
#def set_permissions(f, owner, group, perms):
#    chown(f, owner, group)
#    chmod(f, perms)
#
#
#def test_setpermissions_file():
#
#    # Check we're at the default permissions
#    assert get_permissions(TMP_TEST_FILE) == ("root", "root", "700")
#
#    # Change the permissions
#    set_permissions(TMP_TEST_FILE, NON_ROOT_USER, NON_ROOT_GROUP, 0o111)
#
#    # Check the permissions got changed
#    assert get_permissions(TMP_TEST_FILE) == (NON_ROOT_USER, NON_ROOT_GROUP, "111")
#
#    # Change the permissions again
#    set_permissions(TMP_TEST_FILE, "root", "root", 0o777)
#
#    # Check the permissions got changed
#    assert get_permissions(TMP_TEST_FILE) == ("root", "root", "777")
#
#
#def test_setpermissions_directory():
#
#    # Check we're at the default permissions
#    assert get_permissions(TMP_TEST_DIR) == ("root", "root", "755")
#
#    # Change the permissions
#    set_permissions(TMP_TEST_DIR, NON_ROOT_USER, NON_ROOT_GROUP, 0o111)
#
#    # Check the permissions got changed
#    assert get_permissions(TMP_TEST_DIR) == (NON_ROOT_USER, NON_ROOT_GROUP, "111")
#
#    # Change the permissions again
#    set_permissions(TMP_TEST_DIR, "root", "root", 0o777)
#
#    # Check the permissions got changed
#    assert get_permissions(TMP_TEST_DIR) == ("root", "root", "777")
#
#
#def test_setpermissions_permissiondenied():
#
#    switch_to_non_root_user()
#
#    with pytest.raises(MoulinetteError):
#        set_permissions(TMP_TEST_FILE, NON_ROOT_USER, NON_ROOT_GROUP, 0o111)
#
#
#def test_setpermissions_badfile():
#
#    with pytest.raises(MoulinetteError):
#        set_permissions("/foo/bar/yolo", NON_ROOT_USER, NON_ROOT_GROUP, 0o111)
#
#
#def test_setpermissions_baduser():
#
#    with pytest.raises(MoulinetteError):
#        set_permissions(TMP_TEST_FILE, "foo", NON_ROOT_GROUP, 0o111)
#
#
#def test_setpermissions_badgroup():
#
#    with pytest.raises(MoulinetteError):
#        set_permissions(TMP_TEST_FILE, NON_ROOT_USER, "foo", 0o111)
