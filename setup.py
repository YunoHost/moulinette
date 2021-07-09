#!/usr/bin/env python

import os
import sys
from setuptools import setup, find_packages
from moulinette import init_moulinette_env


LOCALES_DIR = init_moulinette_env()['LOCALES_DIR']

# Extend installation
locale_files = []

if "install" in sys.argv:
    # Evaluate locale files
    for f in os.listdir('locales'):
        if f.endswith('.json'):
            locale_files.append('locales/%s' % f)

install_deps = [
    'argcomplete',
    'psutil',
    'pytz',
    'pyyaml',
    'toml',
    'gevent-websocket',
    'bottle',
]

test_deps = [
    'pytest',
    'pytest-cov',
    'pytest-env',
    'pytest-mock',
    'requests',
    'requests-mock',
    'webtest'
]
extras = {
    'install': install_deps,
    'tests': test_deps,
}


setup(name='Moulinette',
      version='2.0.0',
      description='Prototype interfaces quickly and easily',
      author='Yunohost Team',
      author_email='yunohost@yunohost.org',
      url='http://yunohost.org',
      license='AGPL',
      packages=find_packages(exclude=['test']),
      data_files=[(LOCALES_DIR, locale_files)],
      python_requires='>=3.7.*,  <3.8',
      install_requires=install_deps,
      tests_require=test_deps,
      extras_require=extras,
      )
