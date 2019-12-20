import os
import yaml
import toml
import errno
import shutil
import json
import grp

from pwd import getpwnam
from collections import OrderedDict

from moulinette import m18n
from moulinette.core import MoulinetteError

# Files & directories --------------------------------------------------


def read_file(file_path):
    """
    Read a regular text file

    Keyword argument:
        file_path -- Path to the text file
    """
    assert isinstance(file_path, str), (
        "Error: file_path '%s' should be a string but is of type '%s' instead"
        % (file_path, type(file_path))
    )

    # Check file exists
    if not os.path.isfile(file_path):
        raise MoulinetteError("file_not_exist", path=file_path)

    # Open file and read content
    try:
        with open(file_path, "r") as f:
            file_content = f.read()
    except IOError as e:
        raise MoulinetteError("cannot_open_file", file=file_path, error=str(e))
    except Exception as e:
        raise MoulinetteError(
            "unknown_error_reading_file", file=file_path, error=str(e)
        )

    return file_content


def read_json(file_path):
    """
    Read a json file

    Keyword argument:
        file_path -- Path to the json file
    """

    # Read file
    file_content = read_file(file_path)

    # Try to load json to check if it's syntaxically correct
    try:
        loaded_json = json.loads(file_content)
    except ValueError as e:
        raise MoulinetteError("corrupted_json", ressource=file_path, error=str(e))

    return loaded_json


def read_yaml(file_path):
    """
    Safely read a yaml file

    Keyword argument:
        file_path -- Path to the yaml file
    """

    # Read file
    file_content = read_file(file_path)

    # Try to load yaml to check if it's syntaxically correct
    try:
        loaded_yaml = yaml.safe_load(file_content)
    except Exception as e:
        raise MoulinetteError("corrupted_yaml", ressource=file_path, error=str(e))

    return loaded_yaml


def read_toml(file_path):
    """
    Safely read a toml file

    Keyword argument:
        file_path -- Path to the toml file
    """

    # Read file
    file_content = read_file(file_path)

    # Try to load toml to check if it's syntactically correct
    try:
        loaded_toml = toml.loads(file_content, _dict=OrderedDict)
    except Exception as e:
        raise MoulinetteError(
            errno.EINVAL, m18n.g("corrupted_toml", ressource=file_path, error=str(e))
        )

    return loaded_toml


def read_ldif(file_path, filtred_entries=[]):
    """
    Safely read a LDIF file and create struct in the same style than
    what return the auth objet with the seach method
    The main difference with the auth object is that this function return a 2-tuples
    with the "dn" and the LDAP entry.

    Keyword argument:
        file_path       -- Path to the ldif file
        filtred_entries -- The entries to don't include in the result
    """
    from ldif import LDIFRecordList

    class LDIFPar(LDIFRecordList):
        def handle(self, dn, entry):
            for e in filtred_entries:
                if e in entry:
                    entry.pop(e)
            self.all_records.append((dn, entry))

    # Open file and read content
    try:
        with open(file_path, "r") as f:
            parser = LDIFPar(f)
            parser.parse()
    except IOError as e:
        raise MoulinetteError("cannot_open_file", file=file_path, error=str(e))
    except Exception as e:
        raise MoulinetteError(
            "unknown_error_reading_file", file=file_path, error=str(e)
        )

    return parser.all_records


def write_to_file(file_path, data, file_mode="w"):
    """
    Write a single string or a list of string to a text file.
    The text file will be overwritten by default.

    Keyword argument:
        file_path -- Path to the output file
        data -- The data to write (must be a string or list of string)
        file_mode -- Mode used when writing the file. Option meant to be used
        by append_to_file to avoid duplicating the code of this function.
    """
    assert isinstance(data, str) or isinstance(data, list), (
        "Error: data '%s' should be either a string or a list but is of type '%s'"
        % (data, type(data))
    )
    assert not os.path.isdir(file_path), (
        "Error: file_path '%s' point to a dir, it should be a file" % file_path
    )
    assert os.path.isdir(os.path.dirname(file_path)), (
        "Error: the path ('%s') base dir ('%s') is not a dir"
        % (file_path, os.path.dirname(file_path))
    )

    # If data is a list, check elements are strings and build a single string
    if not isinstance(data, str):
        for element in data:
            assert isinstance(element, str), (
                "Error: element '%s' should be a string but is of type '%s' instead"
                % (element, type(element))
            )
        data = "\n".join(data)

    try:
        with open(file_path, file_mode) as f:
            f.write(data)
    except IOError as e:
        raise MoulinetteError("cannot_write_file", file=file_path, error=str(e))
    except Exception as e:
        raise MoulinetteError("error_writing_file", file=file_path, error=str(e))


def append_to_file(file_path, data):
    """
    Append a single string or a list of string to a text file.

    Keyword argument:
        file_path -- Path to the output file
        data -- The data to write (must be a string or list of string)
    """

    write_to_file(file_path, data, file_mode="a")


def write_to_json(file_path, data):
    """
    Write a dictionnary or a list to a json file

    Keyword argument:
        file_path -- Path to the output json file
        data -- The data to write (must be a dict or a list)
    """

    # Assumptions
    assert isinstance(file_path, str), (
        "Error: file_path '%s' should be a string but is of type '%s' instead"
        % (file_path, type(file_path))
    )
    assert isinstance(data, dict) or isinstance(data, list), (
        "Error: data '%s' should be a dict or a list but is of type '%s' instead"
        % (data, type(data))
    )
    assert not os.path.isdir(file_path), (
        "Error: file_path '%s' point to a dir, it should be a file" % file_path
    )
    assert os.path.isdir(os.path.dirname(file_path)), (
        "Error: the path ('%s') base dir ('%s') is not a dir"
        % (file_path, os.path.dirname(file_path))
    )

    # Write dict to file
    try:
        with open(file_path, "w") as f:
            json.dump(data, f)
    except IOError as e:
        raise MoulinetteError("cannot_write_file", file=file_path, error=str(e))
    except Exception as e:
        raise MoulinetteError("error_writing_file", file=file_path, error=str(e))


def write_to_yaml(file_path, data):
    """
    Write a dictionnary or a list to a yaml file

    Keyword argument:
        file_path -- Path to the output yaml file
        data -- The data to write (must be a dict or a list)
    """
    # Assumptions
    assert isinstance(file_path, str)
    assert isinstance(data, dict) or isinstance(data, list)
    assert not os.path.isdir(file_path)
    assert os.path.isdir(os.path.dirname(file_path))

    # Write dict to file
    try:
        with open(file_path, "w") as f:
            yaml.safe_dump(data, f, default_flow_style=False)
    except IOError as e:
        raise MoulinetteError("cannot_write_file", file=file_path, error=str(e))
    except Exception as e:
        raise MoulinetteError("error_writing_file", file=file_path, error=str(e))


def mkdir(path, mode=0o777, parents=False, uid=None, gid=None, force=False):
    """Create a directory with optional features

    Create a directory and optionaly set its permissions to mode and its
    owner and/or group. If path refers to an existing path, nothing is done
    unless force is True.

    Keyword arguments:
        - path -- The directory to create
        - mode -- Numeric path mode to set
        - parents -- Make parent directories as needed
        - uid -- Numeric uid or user name
        - gid -- Numeric gid or group name
        - force -- Force directory creation and owning even if the path exists

    """
    if os.path.exists(path) and not force:
        raise OSError(errno.EEXIST, m18n.g("folder_exists", path=path))

    if parents:
        # Create parents directories as needed
        head, tail = os.path.split(path)
        if not tail:
            head, tail = os.path.split(head)
        if head and tail and not os.path.exists(head):
            try:
                mkdir(head, mode, parents, uid, gid, force)
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise
            if tail == os.curdir:
                return

    # Create directory and set permissions
    try:
        os.mkdir(path, mode)
    except OSError:
        # mimic Python3.2+ os.makedirs exist_ok behaviour
        if not force or not os.path.isdir(path):
            raise

    if uid is not None or gid is not None:
        chown(path, uid, gid)


def chown(path, uid=None, gid=None, recursive=False):
    """Change the owner and/or group of a path

    Keyword arguments:
        - uid -- Numeric uid or user name
        - gid -- Numeric gid or group name
        - recursive -- Operate on path recursively

    """
    if uid is None and gid is None:
        raise ValueError("either uid or gid argument is required")

    # Retrieve uid/gid
    if isinstance(uid, str):
        try:
            uid = getpwnam(uid).pw_uid
        except KeyError:
            raise MoulinetteError("unknown_user", user=uid)
    elif uid is None:
        uid = -1
    if isinstance(gid, str):
        try:
            gid = grp.getgrnam(gid).gr_gid
        except KeyError:
            raise MoulinetteError("unknown_group", group=gid)
    elif gid is None:
        gid = -1

    try:
        os.chown(path, uid, gid)
        if recursive and os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                for d in dirs:
                    os.chown(os.path.join(root, d), uid, gid)
                for f in files:
                    os.chown(os.path.join(root, f), uid, gid)
    except Exception as e:
        raise MoulinetteError(
            "error_changing_file_permissions", path=path, error=str(e)
        )


def chmod(path, mode, fmode=None, recursive=False):
    """Change the mode of a path

    Keyword arguments:
        - mode -- Numeric path mode to set
        - fmode -- Numeric file mode to set in case of a recursive directory
        - recursive -- Operate on path recursively

    """

    try:
        os.chmod(path, mode)
        if recursive and os.path.isdir(path):
            if fmode is None:
                fmode = mode
            for root, dirs, files in os.walk(path):
                for d in dirs:
                    os.chmod(os.path.join(root, d), mode)
                for f in files:
                    os.chmod(os.path.join(root, f), fmode)
    except Exception as e:
        raise MoulinetteError(
            "error_changing_file_permissions", path=path, error=str(e)
        )


def rm(path, recursive=False, force=False):
    """Remove a file or directory

    Keyword arguments:
        - path -- The path to remove
        - recursive -- Remove directories and their contents recursively
        - force -- Ignore nonexistent files

    """
    if recursive and os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=force)
    else:
        try:
            os.remove(path)
        except OSError as e:
            if not force:
                raise MoulinetteError("error_removing", path=path, error=str(e))
