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


def prependlines(text, prepend):
    """Prepend a string to each line of a text"""
    lines = text.splitlines(True)
    return "%s%s" % (prepend, prepend.join(lines))


# Randomize ------------------------------------------------------------


def random_ascii(length=20):
    """Return a random ascii string"""
    return binascii.hexlify(os.urandom(length)).decode("ascii")
