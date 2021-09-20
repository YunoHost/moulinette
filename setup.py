#!/usr/bin/env python

import os
import sys
import subprocess

from setuptools import setup, find_packages
from moulinette import env

version = subprocess.check_output("head debian/changelog  -n1 | awk '{print $2}' | tr -d '()'", shell=True).decode().strip()

LOCALES_DIR = env["LOCALES_DIR"]

# Extend installation
locale_files = []

if "install" in sys.argv:
    # Evaluate locale files
    for f in os.listdir("locales"):
        if f.endswith(".json"):
            locale_files.append("locales/%s" % f)

install_deps = [
    "psutil",
    "pytz",
    "pyyaml",
    "toml",
    "gevent-websocket",
    "bottle",
]

test_deps = [
    "pytest",
    "pytest-cov",
    "pytest-env",
    "pytest-mock",
    "mock",
    "requests",
    "requests-mock",
    "webtest",
]

extras = {
    "install": install_deps,
    "tests": test_deps,
}

setup(
    name="Moulinette",
    version=version,
    description="Prototype interfaces quickly and easily",
    author="Yunohost Team",
    author_email="yunohost@yunohost.org",
    url="https://yunohost.org",
    license="AGPL",
    packages=find_packages(exclude=["test"]),
    data_files=[(LOCALES_DIR, locale_files)],
    python_requires=">=3.7.*,  <3.8",
    install_requires=install_deps,
    tests_require=test_deps,
    extras_require=extras,
)
