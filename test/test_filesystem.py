import os

import pytest

from moulinette import m18n
from moulinette.core import MoulinetteError
from moulinette.utils.filesystem import (append_to_file, read_file, read_json,
                                         rm, write_to_file, write_to_json)


def test_read_file(test_file):
    content = read_file(str(test_file))
    assert content == 'foo\nbar\n'


def test_read_file_missing_file():
    bad_file = 'doesnt-exist'

    with pytest.raises(MoulinetteError) as exception:
        read_file(bad_file)

    translation = m18n.g('file_not_exist')
    expected_msg = translation.format(path=bad_file)
    assert expected_msg in str(exception)


def test_read_file_cannot_read_ioerror(test_file, mocker):
    error = 'foobar'

    with mocker.patch('__builtin__.open', side_effect=IOError(error)):
        with pytest.raises(MoulinetteError) as exception:
            read_file(str(test_file))

    translation = m18n.g('cannot_open_file')
    expected_msg = translation.format(file=str(test_file), error=error)
    assert expected_msg in str(exception)


def test_read_json(test_json):
    content = read_json(str(test_json))
    assert 'foo' in content.keys()
    assert content['foo'] == 'bar'


def test_read_json_cannot_read(test_json, mocker):
    error = 'foobar'

    with mocker.patch('json.loads', side_effect=ValueError(error)):
        with pytest.raises(MoulinetteError) as exception:
            read_json(str(test_json))

    translation = m18n.g('corrupted_json')
    expected_msg = translation.format(ressource=str(test_json), error=error)
    assert expected_msg in str(exception)


def test_write_to_existing_file(test_file):
    write_to_file(str(test_file), 'yolo\nswag')
    assert read_file(str(test_file)) == 'yolo\nswag'


def test_write_to_new_file(tmp_path):
    new_file = tmp_path / 'newfile.txt'

    write_to_file(str(new_file), 'yolo\nswag')

    assert os.path.exists(str(new_file))
    assert read_file(str(new_file)) == 'yolo\nswag'


def test_write_to_existing_file_bad_perms(test_file, mocker):
    error = 'foobar'

    with mocker.patch('__builtin__.open', side_effect=IOError(error)):
        with pytest.raises(MoulinetteError) as exception:
            write_to_file(str(test_file), 'yolo\nswag')

    translation = m18n.g('cannot_write_file')
    expected_msg = translation.format(file=str(test_file), error=error)
    assert expected_msg in str(exception)


def test_write_cannot_write_folder(tmp_path):
    with pytest.raises(AssertionError):
        write_to_file(str(tmp_path), 'yolo\nswag')


def test_write_cannot_write_to_non_existant_folder():
    with pytest.raises(AssertionError):
        write_to_file('/toto/test', 'yolo\nswag')


def test_write_to_file_with_a_list(test_file):
    write_to_file(str(test_file), ['yolo', 'swag'])
    assert read_file(str(test_file)) == 'yolo\nswag'


def test_append_to_existing_file(test_file):
    append_to_file(str(test_file), 'yolo\nswag')
    assert read_file(str(test_file)) == 'foo\nbar\nyolo\nswag'


def test_append_to_new_file(tmp_path):
    new_file = tmp_path / 'newfile.txt'

    append_to_file(str(new_file), 'yolo\nswag')

    assert os.path.exists(str(new_file))
    assert read_file(str(new_file)) == 'yolo\nswag'


def text_write_dict_to_json(tmp_path):
    new_file = tmp_path / 'newfile.json'

    dummy_dict = {'foo': 42, 'bar': ['a', 'b', 'c']}
    write_to_json(str(new_file), dummy_dict)
    _json = read_json(str(new_file))

    assert 'foo' in _json.keys()
    assert 'bar' in _json.keys()

    assert _json['foo'] == 42
    assert _json['bar'] == ['a', 'b', 'c']


def text_write_list_to_json(tmp_path):
    new_file = tmp_path / 'newfile.json'

    dummy_list = ['foo', 'bar', 'baz']
    write_to_json(str(new_file), dummy_list)

    _json = read_json(str(new_file))
    assert _json == ['foo', 'bar', 'baz']


def test_write_to_json_bad_perms(test_json, mocker):
    error = 'foobar'

    with mocker.patch('__builtin__.open', side_effect=IOError(error)):
        with pytest.raises(MoulinetteError) as exception:
            write_to_json(str(test_json), {'a': 1})

    translation = m18n.g('cannot_write_file')
    expected_msg = translation.format(file=str(test_json), error=error)
    assert expected_msg in str(exception)


def test_write_json_cannot_write_to_non_existant_folder():
    with pytest.raises(AssertionError):
        write_to_json('/toto/test.json', ['a', 'b'])


def test_remove_file(test_file):
    assert os.path.exists(str(test_file))
    rm(str(test_file))
    assert not os.path.exists(str(test_file))


def test_remove_file_bad_perms(test_file, mocker):
    error = 'foobar'

    with mocker.patch('os.remove', side_effect=OSError(error)):
        with pytest.raises(MoulinetteError) as exception:
            rm(str(test_file))

    translation = m18n.g('error_removing')
    expected_msg = translation.format(path=str(test_file), error=error)
    assert expected_msg in str(exception)


def test_remove_directory(tmp_path):
    test_dir = tmp_path / "foo"
    test_dir.mkdir()

    assert os.path.exists(str(test_dir))
    rm(str(test_dir), recursive=True)
    assert not os.path.exists(str(test_dir))
