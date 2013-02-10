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


def app_list(offset=None, limit=None):
    """
    List available applications

    Keyword arguments:
        offset -- App to begin with
        limit -- Number of apps to list 

    Returns:
        Dict of apps

    """

    # TODO: List installed applications
    # TODO: Implement fields to fetch

    if offset: offset = int(offset)
    else: offset = 0
    if limit: limit = int(limit)
    else: limit = 1000
    with open('/var/cache/yunohost/apps/list.json') as json_list:
        app_dict = json.loads(str(json_list.read()))

    list_dict = {}

    if len(app_dict) > (0 + offset) and limit > 0:
        i = 0 + offset
        sorted_app_dict = {} 
        for sorted_keys in sorted(app_dict.keys())[i:]:
            if i <= limit:
                sorted_app_dict[sorted_keys] = app_dict[sorted_keys]
                i += 1
        for app_id, app_info in sorted_app_dict.items():
            list_dict[app_id] = { 
                'Name': app_info['manifest']['name'],
                'Version': app_info['manifest']['version'],
                'Description': app_info['manifest']['description']
            }

    return list_dict
