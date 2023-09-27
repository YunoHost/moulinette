#!/usr/bin/env python

import os
import sys
import subprocess

from setuptools import setup, find_packages

version = (
    subprocess.check_output(
        "head debian/changelog  -n1 | awk '{print $2}' | tr -d '()'", shell=True
    )
    .decode()
    .strip()
)

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
    "prompt-toolkit>=3.0",
    "pygments",
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
    data_files=[("/usr/share/moulinette/locales", locale_files)],
    python_requires=">=3.11.0,<3.12",
    install_requires=install_deps,
    tests_require=test_deps,
    extras_require=extras,
)
