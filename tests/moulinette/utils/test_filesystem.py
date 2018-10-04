# encoding: utf-8

"""
Testing moulinette utils filesystem
"""

import mock
import pytest

# Moulinette specific
from moulinette.core import MoulinetteError
from moulinette.utils import filesystem



########################################################################
# Test reading a file
########################################################################

#
# reading a text file

@mock.patch('os.path.isfile')
def test_read_file_raise_error_for_non_existant_file(isfile):
    isfile.return_value = False  # the file does not exist

    with pytest.raises(MoulinetteError):
        filesystem.read_file('non_existent_file.txt')


@mock.patch('os.path.isfile')
@mock.patch('builtins.open')
def test_read_file_raise_error_for_non_openable_file(open, isfile):
    isfile.return_value = True  # the file exists
    open.side_effect = IOError()  # it cannot be opened

    with pytest.raises(MoulinetteError):
        filesystem.read_file('non_openable_file.txt')


@mock.patch('os.path.isfile')
@mock.patch('builtins.open')
def test_read_file_raise_error_for_non_readable_file(open, isfile):
    isfile.return_value = True  # the file exists
    open.side_effect = Exception()  # it cannot be read

    with pytest.raises(MoulinetteError):
        filesystem.read_file('non_openable_file.txt')


@mock.patch('os.path.isfile')
@mock.patch('builtins.open')
def test_read_file_return_file_content(open, isfile):
    isfile.return_value = True  # the file exists
    file_content = 'file content'
    open.return_value = fake_open_for_read(file_content)  # can be open with content

    content = filesystem.read_file('fake_file.txt')

    assert content == file_content, 'read_file returned expected content'


#
# reading a json file

@mock.patch('os.path.isfile')
@mock.patch('builtins.open')
def test_read_json_return_file_content_as_json(open, isfile):
    isfile.return_value = True
    file_content = '{"foo": "abc", "bar": 42}'
    open.return_value = fake_open_for_read(file_content)

    content = filesystem.read_json('fake_file.json')

    json_content = {'foo': 'abc', 'bar': 42}
    assert content == json_content, 'read_json returned expected content'


@mock.patch('os.path.isfile')
@mock.patch('builtins.open')
def test_read_json_raise_error_on_bad_content(open, isfile):
    isfile.return_value = True
    file_content = '{"foo", "abc", "bar": 42]'
    open.return_value = fake_open_for_read(file_content)

    with pytest.raises(MoulinetteError):
        content = filesystem.read_json('bad_file.json')


#
# reading a yaml file

@mock.patch('os.path.isfile')
@mock.patch('builtins.open')
def test_read_yaml_return_file_content_as_yaml(open, isfile):
    isfile.return_value = True
    file_content = 'foo:\n- abc\n- 42'
    open.return_value = fake_open_for_read(file_content)

    content = filesystem.read_yaml('fake_file.yaml')

    yaml_content = {'foo': ['abc', 42]}
    assert content == yaml_content, 'read_yaml returned expected content'


@mock.patch('os.path.isfile')
@mock.patch('builtins.open')
def test_read_yaml_raise_error_on_bad_content(open, isfile):
    isfile.return_value = True
    file_content = 'foo, bar-\n t:'
    open.return_value = fake_open_for_read(file_content)

    with pytest.raises(MoulinetteError):
        content = filesystem.read_yaml('bad_file.yaml')


########################################################################
# Test writing a file
########################################################################

#
# writing a text file

@mock.patch('os.path.isdir')
@mock.patch('builtins.open')
def test_write_to_file_update_file_content(open, isdir):
    # WARNING order is dependant on actual implementation
    isdir.side_effect = [False, True]
    open.return_value, fake_file = fake_open_for_write()
    content = 'some content\n'

    filesystem.write_to_file('fake/file.txt', content)

    fake_file.write.assert_called_with(content)


@mock.patch('os.path.isdir')
@mock.patch('builtins.open')
def test_write_to_file_raise_error_for_folder_used_as_file(open, isdir):
    # WARNING order is dependant on actual implementation
    isdir.side_effect = [True, True]
    content = 'some content\n'

    with pytest.raises(AssertionError):
        filesystem.write_to_file('folder/file/', content)


@mock.patch('os.path.isdir')
@mock.patch('builtins.open')
def test_write_to_file_raise_error_for_improper_path(open, isdir):
    # WARNING order is dependant on actual implementation
    isdir.side_effect = [False, False]
    content = 'some content\n'

    with pytest.raises(AssertionError):
        filesystem.write_to_file('non/existant/path/file.txt', content)


@mock.patch('os.path.isdir')
@mock.patch('builtins.open')
def test_write_to_file_raise_error_when_file_cannot_be_opened(open, isdir):
    # WARNING order is dependant on actual implementation
    isdir.side_effect = [False, True]
    open.side_effect = IOError()  # it cannot be opened
    content = 'some content\n'

    with pytest.raises(MoulinetteError):
        filesystem.write_to_file('bad/path/file.txt', content)


@mock.patch('os.path.isdir')
@mock.patch('builtins.open')
def test_write_to_file_raise_error_when_file_cannot_be_written(open, isdir):
    # WARNING order is dependant on actual implementation
    isdir.side_effect = [False, True]
    # FIXME it could be write that raises Exception
    open.side_effect = Exception()  # it cannot be written
    content = 'some content\n'

    with pytest.raises(MoulinetteError):
        filesystem.write_to_file('non_writable_file.txt', content)


#
# writing to a json file

@mock.patch('os.path.isdir')
@mock.patch('builtins.open')
def test_write_to_json_update_file_content_from_dict(open, isdir):
    # WARNING order is dependant on actual implementation of write_to_file
    isdir.side_effect = [False, True]
    open.return_value, fake_file = fake_open_for_write()
    file_content = '{"foo": "abc", "bar": 42}'
    json_content = {'foo': 'abc', 'bar': 42}

    filesystem.write_to_json('fake/file.json', json_content)

    fake_file.write.assert_called_with(file_content)

@mock.patch('os.path.isdir')
@mock.patch('builtins.open')
def test_write_to_json_update_file_content_from_list(open, isdir):
    # WARNING order is dependant on actual implementation of write_to_file
    isdir.side_effect = [False, True]
    open.return_value, fake_file = fake_open_for_write()
    file_content = '["foo", "abc", "bar", 42]'
    json_content = ['foo', 'abc', 'bar', 42]

    filesystem.write_to_json('fake/file.json', json_content)

    fake_file.write.assert_called_with(file_content)


@mock.patch('os.path.isdir')
@mock.patch('builtins.open')
def test_write_to_json_raise_error_for_bad_content(open, isdir):
    # WARNING order is dependant on actual implementation of write_to_file
    isdir.side_effect = [False, True]
    open.return_value, fake_file = fake_open_for_write()
    json_content = 'foo'

    with pytest.raises(AssertionError):
        filesystem.write_to_json('fake/file.json', json_content)


########################################################################
# Helper functions
########################################################################

def fake_open_for_read(content):
    """Return a mock for opening a file to be read with given content

    This helper function is for mocking open() when used in a context manager.

        @mock.patch('builtins.open')
        def test(open):
            open.return_value = fake_open_for_read('content')
            function_using_open('filename.txt')
            ...

        def function_using_open(filename):
            with open(filename, 'r') as f:
                content = f.read()
    """
    fake_file = mock.Mock(read=mock.Mock(return_value=content))
    # open is used as a context manager
    # - so we fake __enter__ to return the fake file
    # - so we fake __exit__ to do nothing
    return mock.Mock(
        __enter__=mock.Mock(return_value=fake_file),
        __exit__=mock.Mock())


def fake_open_for_write():
    """Return a mock for opening a file to be writen to as well as the fake file

    This helper function is for mocking open() when used in a context manager.

        @mock.patch('builtins.open')
        def test(open):
            open.return_value, fake_file = fake_open_for_write()
            function_using_open('filename.txt', 'content')
            fake_file.write.assert_called('content')

        def function_using_open(filename, content):
            with open(filename, 'w') as f:
                content = f.write(content)
    """
    fake_file = mock.Mock(write=mock.Mock())
    # open is used as a context manager
    # - so we fake __enter__ to return the fake file
    # - so we fake __exit__ to do nothing
    return (mock.Mock(
                __enter__=mock.Mock(return_value=fake_file),
                __exit__=mock.Mock()),
            fake_file)


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
