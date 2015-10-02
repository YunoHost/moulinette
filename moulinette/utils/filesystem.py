import os
import shutil
from pwd import getpwnam
from grp import getgrnam


# Files & directories --------------------------------------------------

def mkdir(path, mode=0777, parents=False, uid=None, gid=None, force=False):
    """Create a directory with optional features

    Create a directory and optionaly set its permissions to mode and its
    owner and/or group. If path refers to an existing path, nothing is done
    unless force is True.

    Keyword arguments:
        - path -- The directory to create
        - mode -- Directory mode to set in octal
        - parents -- Make parent directories as needed
        - uid -- Numeric uid or user name
        - gid -- Numeric gid or group name
        - force -- Force directory creation and owning even if the path exists

    """
    if os.path.exists(path) and not force:
        return
    if parents:
        os.makedirs(path, mode)
    else:
        os.mkdir(path, mode)
    try:
        chown(path, uid, gid)
    except:
        pass


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
    if isinstance(uid, basestring):
        uid = getpwnam(uid).pw_uid
    elif uid is None:
        uid = -1
    if isinstance(gid, basestring):
        gid = getpwnam(gid).gr_gid
    elif gid is None:
        gid = -1

    os.chown(path, uid, gid)
    if recursive and os.path.isdir(path):
        for root, dirs, files in os.walk(path):
            for d in dirs:
                os.chown(os.path.join(root, d), uid, gid)
            for f in files:
                os.chown(os.path.join(root, f), uid, gid)


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
        except OSError:
            if not force:
                raise
