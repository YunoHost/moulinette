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
import json
import glob
import pytest

# List all locale files (except en.json being the ref)
locale_folder = "locales/"
locale_files = glob.glob(locale_folder + "*.json")
locale_files = [filename.split("/")[-1] for filename in locale_files]
locale_files.remove("en.json")

reference = json.loads(open(locale_folder + "en.json").read())


def find_inconsistencies(locale_file):
    this_locale = json.loads(open(locale_folder + locale_file).read())

    # We iterate over all keys/string in en.json
    for key, string in reference.items():
        # Ignore check if there's no translation yet for this key
        if key not in this_locale:
            continue

        # Then we check that every "{stuff}" (for python's .format())
        # should also be in the translated string, otherwise the .format
        # will trigger an exception!
        subkeys_in_ref = {k[0] for k in re.findall(r"{(\w+)(:\w)?}", string)}
        subkeys_in_this_locale = {
            k[0] for k in re.findall(r"{(\w+)(:\w)?}", this_locale[key])
        }

        if any(k not in subkeys_in_ref for k in subkeys_in_this_locale):
            yield """\n
==========================
Format inconsistency for string {key} in {locale_file}:"
en.json   -> {string}
{locale_file}   -> {translated_string}
""".format(
                key=key,
                string=string.encode("utf-8"),
                locale_file=locale_file,
                translated_string=this_locale[key].encode("utf-8"),
            )


@pytest.mark.parametrize("locale_file", locale_files)
def test_translation_format_consistency(locale_file):
    inconsistencies = list(find_inconsistencies(locale_file))
    if inconsistencies:
        raise Exception("".join(inconsistencies))
