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


def reformat(lang, transformations):
    locale = open(f"locales/{lang}.json").read()
    for pattern, replace in transformations.items():
        locale = re.compile(pattern).sub(replace, locale)

    open(f"locales/{lang}.json", "w").write(locale)


######################################################

godamn_spaces_of_hell = [
    "\u00a0",
    "\u2000",
    "\u2001",
    "\u2002",
    "\u2003",
    "\u2004",
    "\u2005",
    "\u2006",
    "\u2007",
    "\u2008",
    "\u2009",
    "\u200a",
    # "\u202f",
    # "\u202F",
    "\u3000",
]

transformations = {s: " " for s in godamn_spaces_of_hell}
transformations.update(
    {
        "…": "...",
    }
)


reformat("en", transformations)

######################################################

transformations.update(
    {
        "courriel": "email",
        "e-mail": "email",
        "Courriel": "Email",
        "E-mail": "Email",
        "« ": "'",
        "«": "'",
        " »": "'",
        "»": "'",
        "’": "'",
        # r"$(\w{1,2})'|( \w{1,2})'": r"\1\2’",
    }
)

reformat("fr", transformations)
