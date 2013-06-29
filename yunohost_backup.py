# -*- coding: utf-8 -*-

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
