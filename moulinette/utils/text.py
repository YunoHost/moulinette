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

import os
import re
import mmap
import binascii

# Pattern searching ----------------------------------------------------


def search(pattern, text, count=0, flags=0):
    """Search for pattern in a text

    Scan through text looking for all locations where the regular
    expression pattern matches, and return them as a list of strings.

    The optional argument count is the maximum number of pattern
    occurences to return; count must be an integer. If omitted or zero,
    all occurences will be returned. If it's a negative number, occurences
    to return will be counted backward. If only one occurence is
    requested, it will be returned as a string.

    The expression's behaviour can be modified by specifying a flags value.
    Refer to the re module documentation for available variables.

    """
    match = re.findall(pattern, text, flags)
    if not match:
        return None
    if not count:
        return match

    # Limit result depending on count value
    limit = min(len(match), abs(count))
    if count < 0:
        match = match[-limit:]
    else:
        match = match[:limit]
    if abs(count) == 1:
        return match[0]
    return match


def searchf(pattern, path, count=0, flags=re.MULTILINE):
    """Search for pattern in a file

    Map the file with given path to memory and search for pattern in it
    content by using the search function.

    """
    with open(path, "rb+") as f:
        data = mmap.mmap(f.fileno(), 0)
        match = search(pattern, data.read().decode(), count, flags)
        data.close()
    return match


# Text formatting ------------------------------------------------------


def prependlines(text: str, prepend: str) -> str:
    """Prepend a string to each line of a text"""
    lines = text.splitlines(True)
    return "{}{}".format(prepend, prepend.join(lines))


# Randomize ------------------------------------------------------------


def random_ascii(length: int = 40) -> str:
    """Return a random ascii string"""
    return binascii.hexlify(os.urandom(length)).decode("ascii")[:length]
