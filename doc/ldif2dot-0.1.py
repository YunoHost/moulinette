#!/usr/bin/python
# A simple script to convert an LDIF file to DOT format for drawing graphs.
# Copyright 2009 Marcin Owsiany <marcin@owsiany.pl>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""A simple script to convert an LDIF file to DOT format for drawing graphs.

So far it only supports the most basic form of entry records: "attrdesc: value".
In particular line continuations, BASE64 or other encodings, change records,
include statements, etc...  are not supported.

Example usage, assuming your DIT's base is dc=nodomain:

ldapsearch -x -b 'dc=nodomain' | \\
  ldif2dot | \\
  dot -o nodomain.png -Nshape=box -Tpng /dev/stdin

"""


import sys


class Element:
    """Represents an LDIF entry."""

    def __init__(self):
        """Initializes an object."""
        self.attributes = []

    def __repr__(self):
        """Returns a basic state dump."""
        return "Element" + str(self.index) + str(self.attributes)

    def add(self, line):
        """Adds a line of input to the object.

        Args:
         - line: a string with trailing newline stripped

        Returns: True if this object is ready for processing (i.e. a separator
        line was passed). Otherwise returns False. Behaviour is undefined if
        this method is called after a previous invocation has returned True.
        """

        def _valid(line):
            return line and not line.startswith("#")

        def _interesting(line):
            return line != "objectClass: top"

        if self.is_valid() and not _valid(line):
            return True
        if _valid(line) and _interesting(line):
            self.attributes.append(line)
        return False

    def is_valid(self):
        """Indicates whether a valid entry has been read."""
        return len(self.attributes) != 0 and self.attributes[0].startswith("dn: ")

    def dn(self):
        """Returns the DN for this entry."""
        if self.attributes[0].startswith("dn: "):
            return self.attributes[0][4:]
        else:
            return None

    def edge(self, dnmap):
        """Returns a text represenation of a grapsh edge.

        Finds its parent in provided dnmap (dictionary mapping dn names to
        Element objects) and returns a string which declares a DOT edge, or an
        empty string, if no parent was found.
        """
        dn_components = self.dn().split(",")
        for i in range(1, len(dn_components) + 1):
            parent = ",".join(dn_components[i:])
            if parent in dnmap:
                return "  n%d->n%d\n" % (dnmap[parent].index, self.index)
        return ""

    def dot(self, dnmap):
        """Returns a text representation of the node and perhaps its parent edge.

        Args:
         - dnmap: dictionary mapping dn names to Element objects
        """

        def _format(attributes):
            result = [TITLE_ENTRY_TEMPALTE % attributes[0]]

            for attribute in attributes[1:]:
                result.append(ENTRY_TEMPALTE % attribute)

            return result

        return TABLE_TEMPLATE % (
            self.index,
            "\n    ".join(_format(self.attributes)),
            self.edge(dnmap),
        )


class Converter:
    """An LDIF to DOT converter."""

    def __init__(self):
        """Initializes the object."""
        self.elements = []
        self.dnmap = {}

    def _append(self, e):
        """Adds an element to internal list and map.

        First sets it up with an index in the list, for node naming.
        """
        index = len(self.elements)
        e.index = index
        self.elements.append(e)
        self.dnmap[e.dn()] = e

    def parse(self, file, name):
        """Reads the given file into memory.

        Args:
         - file: an object which yields text lines on iteration.
         - name: a name for the graph

        Returns a string containing the graph in DOT format.
        """
        e = Element()
        for line in file:
            line = line.rstrip()
            if e.add(line):
                self._append(e)
                e = Element()
        if e.is_valid():
            self._append(e)
        return BASE_TEMPLATE % (
            name,
            "".join([e.dot(self.dnmap) for e in self.elements]),
        )


BASE_TEMPLATE = """\
strict digraph "%s" {
  rankdir=LR

  fontname = "Helvetica"
  fontsize = 10
  splines  = true

  node [
    fontname = "Helvetica"
    fontsize = 10
    shape = "plaintext"
  ]

  edge [
    fontname = "Helvetica"
    fontsize = 10
  ]

%s}
"""

TABLE_TEMPLATE = """\n
  n%d [label=<
    <TABLE BGCOLOR="palegoldenrod" BORDER="0" CELLBORDER="0" CELLSPACING="0">
    %s
    </TABLE>
  >]
%s
"""

TITLE_ENTRY_TEMPALTE = """\
    <TR><TD CELLPADDING="4" ALIGN="CENTER" BGCOLOR="olivedrab4">
    <FONT FACE="Helvetica Bold" COLOR="white">
    %s
    </FONT></TD></TR>\
"""

ENTRY_TEMPALTE = """\
    <TR><TD BORDER="0" ALIGN="LEFT">
    <FONT FACE="Helvetica Bold">%s</FONT>
    </TD></TR>\
"""


if __name__ == "__main__":
    if len(sys.argv) > 2:
        raise "Expected at most one argument."
    elif len(sys.argv) == 2:
        name = sys.argv[1]
        file = open(sys.argv[1], "r")
    else:
        name = "<stdin>"
        file = sys.stdin
    print(Converter().parse(file, name))
