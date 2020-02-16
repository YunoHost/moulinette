#!/usr/bin/env python

import os
import sys
from setuptools import setup, find_packages


LOCALES_DIR = os.environ.get("MOULINETTE_LOCALES_DIR", "/usr/share/moulinette/locale")

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
      packages=find_packages(exclude=['test']),
      data_files=[(LOCALES_DIR, locale_files)],
      python_requires='>=3.7',
      install_requires=[
          'argcomplete',
          'psutil',
          'pytz',
          'pyyaml',
          'toml',
          'python-ldap',
          'gevent-websocket',
          'bottle',
      ],
      tests_require=[
          'pytest',
          'pytest-cov',
          'pytest-env',
          'pytest-mock',
          'requests',
          'requests-mock',
          'webtest'
      ],
      )
