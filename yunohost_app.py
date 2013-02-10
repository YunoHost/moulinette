# -*- coding: utf-8 -*-

import os
import sys
import json
from urllib import urlopen, urlretrieve
from yunohost import YunoHostError, YunoHostLDAP, win_msg

def app_updatelist(url=None):
    """
    Fetch application list

    Keyword arguments:
        url -- Custom list URL

    Returns:
        True | YunoHostError

    """
    app_path = '/var/cache/yunohost/apps/'

    # Create app path if not exists
    try: os.listdir(app_path)
    except OSError: os.makedirs(app_path)

    if not url: url = 'http://fapp.yunohost.org/app/list/raw'

    # Get list
    try: fetch = urlopen(url)
    except IOError: fetch = False
    finally:
        if fetch and (fetch.code == 200): urlretrieve(url, app_path + 'list.json')
        else: raise YunoHostError(1, _("List server connection failed"))

    win_msg(_("List updated successfully"))


def app_list(filter=None, fields=None, offset=None, limit=None):
    with open('/var/cache/yunohost/apps/list.json') as json_list:
        app_dict = json.loads(str(json_list.read()))

    list_dict = {}

    for app_id, app_info in app_dict.items():
        list_dict[app_id] = { 
            'Name': app_info['manifest']['name'],
            'Version': app_info['manifest']['version'],
            'Description': app_info['manifest']['description']
        }

    return list_dict
