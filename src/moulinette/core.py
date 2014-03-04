# -*- coding: utf-8 -*-

import os
import sys
import gettext
from .helpers import colorize

class Package(object):
    """Package representation and easy access

    Initialize directories and variables for the package and give them
    easy access.

    Keyword arguments:
        - prefix -- The installation prefix
        - libdir -- The library directory; usually, this would be
                    prefix + '/lib' (or '/lib64') when installed
        - cachedir -- The cache directory; usually, this would be
                      '/var/cache' when installed
        - destdir -- The destination prefix only if it's an installation

    'prefix' and 'libdir' arguments should be empty in order to run
    package from source.

    """
    def __init__(self, prefix, libdir, cachedir, destdir=None):
        if not prefix and not libdir:
            # Running from source directory
            basedir = os.path.abspath(os.path.dirname(sys.argv[0]) +'/../')
            self._datadir = os.path.join(basedir, 'data')
            self._libdir = os.path.join(basedir, 'src')
            self._cachedir = cachedir
        else:
            self._datadir = os.path.join(prefix, 'share/moulinette')
            self._libdir = os.path.join(libdir, 'moulinette')
            self._cachedir = os.path.join(cachedir, 'moulinette')

            # Append library path to python's path
            sys.path.append(self._libdir)
        self._destdir = destdir or None


    ## Easy access to directories and files

    def datadir(self, subdir=None, **kwargs):
        """Return the path to a data directory"""
        return self.get_dir(self._datadir, subdir, **kwargs)

    def datafile(self, filename, **kwargs):
        """Return the path to a data file"""
        return self.get_file(self._datadir, filename, **kwargs)

    def libdir(self, subdir=None, **kwargs):
        """Return the path to a lib directory"""
        return self.get_dir(self._libdir, subdir, **kwargs)

    def libfile(self, filename, **kwargs):
        """Return the path to a lib file"""
        return self.get_file(self._libdir, filename, **kwargs)

    def cachedir(self, subdir=None, **kwargs):
        """Return the path to a cache directory"""
        return self.get_dir(self._cachedir, subdir, **kwargs)

    def cachefile(self, filename, **kwargs):
        """Return the path to a cache file"""
        return self.get_file(self._cachedir, filename, **kwargs)


    ## Standard methods

    def get_dir(self, basedir, subdir=None, make_dir=False):
        """Get a directory path

        Return a path composed by a base directory and an optional
        subdirectory. The path will be created if needed.

        Keyword arguments:
            - basedir -- The base directory
            - subdir -- An optional subdirectory
            - make_dir -- True if it should create needed directory

        """
        # Retrieve path
        path = basedir
        if self._destdir:
            path = os.path.join(self._destdir, path)
        if subdir:
            path = os.path.join(path, subdir)

        # Create directory
        if make_dir and not os.path.isdir(path):
            os.makedirs(path)
        return path

    def get_file(self, basedir, filename, **kwargs):
        """Get a file path

        Return the path of the filename in the specified directory. This
        directory will be created if needed.

        Keyword arguments:
            - basedir -- The base directory of the file
            - filename -- The filename or a path relative to basedir
            - **kwargs -- Additional arguments for Package.get_dir

        """
        # Check for a directory in filename
        subdir = os.path.dirname(filename) or None
        if subdir:
            filename = os.path.basename(filename)

        # Get directory path
        dirpath = self.get_dir(basedir, subdir, **kwargs)
        return os.path.join(dirpath, filename)


class MoulinetteError(Exception):
    """Moulinette base exception

    Keyword arguments:
        - code -- Integer error code
        - message -- Error message to display

    """
    def __init__(self, code, message):
        self.code = code
        self.message = message

        errorcode_desc = {
            1   : _('Fail'),
            13  : _('Permission denied'),
            17  : _('Already exists'),
            22  : _('Invalid arguments'),
            87  : _('Too many users'),
            111 : _('Connection refused'),
            122 : _('Quota exceeded'),
            125 : _('Operation canceled'),
            167 : _('Not found'),
            168 : _('Undefined'),
            169 : _('LDAP operation error')
        }
        if code in errorcode_desc:
            self.desc = errorcode_desc[code]
        else:
            self.desc = _('Error %s' % code)

    def __str__(self, colorized=False):
        desc = self.desc
        if colorized:
            desc = colorize(self.desc, 'red')
        return _('%s: %s' % (desc, self.message))

    def colorize(self):
        return self.__str__(colorized=True)
