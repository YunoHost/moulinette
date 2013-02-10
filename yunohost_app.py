# -*- coding: utf-8 -*-

import os
import sys
import json
from urllib import urlopen, urlretrieve
from yunohost import YunoHostError, YunoHostLDAP

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

    if url: list_url = url
    else: list_url = 'http://fapp.yunohost.org/app/list/raw'

    # Get list
    try: info_fetch = urlopen(list_url)
    except IOError: info_fetch = False
    finally:
        if info_fetch and (info_fetch.code == 200): urlretrieve(list_url, app_path + str(infos['lastUpdate']) + '.json')
        else: raise YunoHostError(1, _("List server connection failed"))

    return True


def app_list(args):
    info_dict = json.loads(str(info_fetch.read()))
    pass
