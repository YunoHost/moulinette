# -*- coding: utf-8 -*-

import os

from moulinette.globals import init_moulinette_env


def get_cachedir(subdir='', make_dir=True):
    """Get the path to a cache directory

    Return the path to the cache directory from an optional
    subdirectory and create it if needed.

    Keyword arguments:
        - subdir -- A cache subdirectory
        - make_dir -- False to not make directory if it not exists

    """
    CACHE_DIR = init_moulinette_env()['CACHE_DIR']

    path = os.path.join(CACHE_DIR, subdir)

    if make_dir and not os.path.isdir(path):
        os.makedirs(path)
    return path


def open_cachefile(filename, mode='r', **kwargs):
    """Open a cache file and return a stream

    Attempt to open in 'mode' the cache file 'filename' from the
    default cache directory and in the subdirectory 'subdir' if
    given. Directories are created if needed and a stream is
    returned if the file can be written.

    Keyword arguments:
        - filename -- The cache filename
        - mode -- The mode in which the file is opened
        - **kwargs -- Optional arguments for get_cachedir

    """
    # Set make_dir if not given
    kwargs['make_dir'] = kwargs.get('make_dir', True if mode[0] == 'w' else False)
    cache_dir = get_cachedir(**kwargs)
    file_path = os.path.join(cache_dir, filename)
    return open(file_path, mode)
