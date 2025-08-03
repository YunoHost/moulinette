#!/usr/bin/env python3
#
# Copyright (c) 2024 YunoHost Contributors
#
# This file is part of YunoHost (see https://yunohost.org)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#

import re
import glob
import json


###############################################################################
#   Find used keys in python code                                             #
###############################################################################


def find_expected_string_keys():
    # Try to find :
    #    m18n.g(   "foo"
    #    MoulinetteError("foo"
    #    # i18n: "some_key"
    p1 = re.compile(r"m18n\.g\(\s*[\"\'](\w+)[\"\']")
    p2 = re.compile(r"Moulinette[a-zA-Z]+\(\s*[\'\"](\w+)[\'\"]")
    p3 = re.compile(r"# i18n: [\'\"]?(\w+)[\'\"]?")

    python_files = glob.glob("moulinette/*.py")
    python_files.extend(glob.glob("moulinette/*/*.py"))

    for python_file in python_files:
        content = open(python_file).read()
        for m in p1.findall(content):
            if m.endswith("_"):
                continue
            yield m
        for m in p2.findall(content):
            if m.endswith("_"):
                continue
            yield m
        for m in p3.findall(content):
            if m.endswith("_"):
                continue
            yield m


###############################################################################
#   Load en locale json keys                                                  #
###############################################################################


def keys_defined_for_en():
    return json.loads(open("locales/en.json").read()).keys()


###############################################################################
#   Compare keys used and keys defined                                        #
###############################################################################


expected_string_keys = set(find_expected_string_keys())
keys_defined = set(keys_defined_for_en())


def test_undefined_i18n_keys():
    undefined_keys = expected_string_keys.difference(keys_defined)
    undefined_keys = sorted(undefined_keys)

    if undefined_keys:
        raise Exception(
            "Those i18n keys should be defined in en.json:\n"
            "    - " + "\n    - ".join(undefined_keys)
        )


def test_unused_i18n_keys():
    unused_keys = keys_defined.difference(expected_string_keys)
    unused_keys = sorted(unused_keys)

    if unused_keys:
        raise Exception(
            "Those i18n keys appears unused:\n" "    - " + "\n    - ".join(unused_keys)
        )
