import os
import errno
import shutil
from pwd import getpwnam

from moulinette.core import MoulinetteError


# Files & directories --------------------------------------------------

def mkdir(path, mode=0777, parents=False, uid=None, gid=None, force=False):
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
        raise OSError(errno.EEXIST, m18n.g('folder_exists', path=path))

    if parents:
        # Create parents directories as needed
        head, tail = os.path.split(path)
        if not tail:
            head, tail = path.split(head)
        if head and tail and not os.path.exists(head):
            try:
                mkdir(head, mode, parents, uid, gid, force)
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise
            if tail == os.curdir:
                return

    # Create directory and set permissions
    os.mkdir(path, mode)
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
    if isinstance(uid, basestring):
        try:
            uid = getpwnam(uid).pw_uid
        except KeyError:
            raise MoulinetteError(errno.EINVAL,
                                  m18n.g('unknown_user', user=uid))
    elif uid is None:
        uid = -1
    if isinstance(gid, basestring):
        try:
            gid = getpwnam(gid).gr_gid
        except KeyError:
            raise MoulinetteError(errno.EINVAL,
                                  m18n.g('unknown_group', group=gid))
    elif gid is None:
        gid = -1

    os.chown(path, uid, gid)
    if recursive and os.path.isdir(path):
        for root, dirs, files in os.walk(path):
            for d in dirs:
                os.chown(os.path.join(root, d), uid, gid)
            for f in files:
                os.chown(os.path.join(root, f), uid, gid)


def chmod(path, mode, fmode=None, recursive=False):
    """Change the mode of a path

    Keyword arguments:
        - mode -- Numeric path mode to set
        - fmode -- Numeric file mode to set in case of a recursive directory
        - recursive -- Operate on path recursively

    """
    os.chmod(path, mode)
    if recursive and os.path.isdir(path):
        if fmode is None:
            fmode = mode
        for root, dirs, files in os.walk(path):
            for d in dirs:
                os.chmod(path, mode)
            for f in files:
                os.chmod(path, fmode)


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
