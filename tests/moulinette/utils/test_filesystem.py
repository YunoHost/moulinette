# encoding: utf-8

"""
Testing moulinette utils filesystem


WARNING These tests have been written based on the actual implementation and
thus are dependant on this implementation. This is fragile but allow for a
first instroduction of tests before doing refactorings.
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


########################################################################
# Test file remove
########################################################################

#
# Removing a file

@mock.patch('os.remove')
def test_rm_remove_file_if_it_exists(remove):
    filename = 'file.txt'

    filesystem.rm(filename)

    remove.assert_called_with(filename)


@mock.patch('os.remove')
def test_rm_cannot_remove_non_existing_file(remove):
    filename = 'do_not_exist.txt'
    remove.side_effect = FileNotFoundError()

    with pytest.raises(MoulinetteError):
        filesystem.rm(filename)


@mock.patch('os.remove')
def test_rm_cannot_remove_file_without_permission(remove):
    filename = 'not_mine.txt'
    remove.side_effect = PermissionError()

    with pytest.raises(MoulinetteError):
        filesystem.rm(filename)


@mock.patch('os.remove')
def test_rm_cannot_remove_folder(remove):
    filename = './folder'
    remove.side_effect = IsADirectoryError()

    with pytest.raises(MoulinetteError):
        filesystem.rm(filename)

#
# Removing a folder

@mock.patch('os.path.isdir')
@mock.patch('shutil.rmtree')
def test_rm_remove_folder_if_it_exists(rmtree, isdir):
    isdir.return_value = True
    foldername = 'folder'

    filesystem.rm(foldername, recursive=True)

    rmtree.assert_called_with(foldername, ignore_errors=False)


@mock.patch('os.path.isdir')
@mock.patch('os.remove')
def test_rm_cannot_remove_non_existing_folder(remove, isdir):
    isdir.return_value = False
    foldername = 'do_not_exist'
    remove.side_effect = FileNotFoundError()

    with pytest.raises(MoulinetteError):
        filesystem.rm(foldername, recursive=True)


@mock.patch('os.path.isdir')
@mock.patch('shutil.rmtree')
def test_rm_cannot_remove_folder_without_permission(rmtree, isdir):
    isdir.return_value = True
    foldername = 'not_mine'
    rmtree.side_effect = PermissionError()

    with pytest.raises(MoulinetteError):
        filesystem.rm(foldername, recursive=True)


########################################################################
# Changing permissions
########################################################################

#
# changing file permissions

@mock.patch('os.chmod')
def test_chmod_update_file_permissions(chmod):
    filename = 'file.txt'
    mode = '0644'

    filesystem.chmod(filename, mode)

    chmod.assert_called_with(filename, mode)


@mock.patch('os.chmod')
def test_chmod_cannot_update_file_without_permission(chmod):
    filename = 'file.txt'
    mode = '0644'
    chmod.side_effect = PermissionError

    with pytest.raises(MoulinetteError):
        filesystem.chmod(filename, mode)


@mock.patch('os.chmod')
def test_chmod_cannot_update_non_existant_file(chmod):
    filename = 'file.txt'
    mode = '0644'
    chmod.side_effect = FileNotFoundError

    with pytest.raises(MoulinetteError):
        filesystem.chmod(filename, mode)

#
# changing folder permissions

@mock.patch('os.walk')
@mock.patch('os.path.isdir')
@mock.patch('os.chmod')
def test_chmod_recursive_update_folder_permissions(chmod, isdir, walk):
    foldername = 'folder'
    mode = '0644'
    isdir.return_value = True  # foldername is a folder
    walk.return_value = [(foldername, ['subfolder'], ['file.txt'])]

    filesystem.chmod(foldername, mode, recursive=True)

    calls = [mock.call('folder', mode),
             mock.call('folder/subfolder', mode),
             mock.call('folder/file.txt', mode)]

    chmod.assert_has_calls(calls)


@mock.patch('os.walk')
@mock.patch('os.path.isdir')
@mock.patch('os.chmod')
def test_chmod_recursive_update_folder_permissions_with_fmode(chmod, isdir, walk):
    foldername = 'folder'
    mode = '0755'
    fmode = '0644'
    isdir.return_value = True  # foldername is a folder
    walk.return_value = [(foldername, ['subfolder'], ['file.txt'])]

    filesystem.chmod(foldername, mode, fmode=fmode, recursive=True)

    calls = [mock.call('folder', mode),
             mock.call('folder/subfolder', mode),
             mock.call('folder/file.txt', fmode)]

    chmod.assert_has_calls(calls)


# eof
