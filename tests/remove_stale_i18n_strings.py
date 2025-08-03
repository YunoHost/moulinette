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

import json
import glob
from collections import OrderedDict

locale_folder = "locales/"
locale_files = glob.glob(locale_folder + "*.json")
locale_files = [filename.split("/")[-1] for filename in locale_files]
locale_files.remove("en.json")

reference = json.loads(open(locale_folder + "en.json").read())

for locale_file in locale_files:
    print(locale_file)
    this_locale = json.loads(
        open(locale_folder + locale_file).read(), object_pairs_hook=OrderedDict
    )
    this_locale_fixed = {k: v for k, v in this_locale.items() if k in reference}

    json.dump(
        this_locale_fixed,
        open(locale_folder + locale_file, "w"),
        indent=4,
        ensure_ascii=False,
    )
