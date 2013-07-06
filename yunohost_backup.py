# -*- coding: utf-8 -*-

""" License

    Copyright (C) 2013 YunoHost

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published
    by the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program; if not, see http://www.gnu.org/licenses

"""

""" yunohost_backup.py
"""
import os
import sys
import json
import yaml
import glob
from yunohost import YunoHostError, YunoHostLDAP, validate, colorize, win_msg

def backup_init(helper=False):
    """
    Init Tahoe-LAFS configuration

    Keyword arguments:
        helper -- Create a helper node rather than a "helped" one

    Returns:
        Win | Fail

    """
    pass
