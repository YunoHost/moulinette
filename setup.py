#!/usr/bin/env python
import os
import sys

from distutils.core import setup

from moulinette.globals import LOCALES_DIR


# Extend installation
locale_files = []

if "install" in sys.argv:
    # Evaluate locale files
    for f in os.listdir('locales'):
        if f.endswith('.json'):
            locale_files.append('locales/%s' % f)


setup(name='Moulinette',
      version='2.0.0',
      description='Prototype interfaces quickly and easily',
      author='Yunohost Team',
      author_email='yunohost@yunohost.org',
      url='http://yunohost.org',
      license='AGPL',
      packages=[
          'moulinette',
          'moulinette.authenticators',
          'moulinette.interfaces',
          'moulinette.utils',
      ],
      data_files=[(LOCALES_DIR, locale_files)],
      tests_require=["pytest", "webtest"],
      )
