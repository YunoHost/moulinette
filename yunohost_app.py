# -*- coding: utf-8 -*-

import os
import sys
import json
from urllib import urlopen, urlretrieve
from yunohost import YunoHostError, YunoHostLDAP

def app_updatelist(args):
    """
    Fetch application list

    Keyword arguments:
        args['url'] -- Custom list URL

    Returns:
        True | YunoHostError

    """
    app_path = '/var/cache/yunohost/apps/'

    # Create app path if not exists
    try: os.listdir(app_path)
    except OSError: os.makedirs(app_path)

    if args['url']: list_url = args['url']
    else: list_url = 'http://fapp.yunohost.org/app/list/raw'

    # Get list
    try: info_fetch = urlopen(list_url)
    except IOError: info_fetch = False
    finally:
        if info_fetch and (info_fetch.code == 200): info_dict = json.loads(str(info_fetch.read()))
        else: raise YunoHostError(1, _("List server connection failed"))
    
    # Fetch manifests and icons
    for appid, infos in info_dict.items():
        if appid not in os.listdir(app_path):
            os.mkdir(app_path + appid)
        if str(infos['lastUpdate']) not in os.listdir(app_path + appid):
            os.rmdir(app_path + appid)
            os.mkdir(app_path + appid)

            try: manifest_fetch = urlopen(infos['manifest'])
            except IOError: manifest_fetch = False
            finally: 
                if manifest_fetch and (manifest_fetch.code == 200): urlretrieve(infos['manifest'], app_path + appid + '/' + str(infos['lastUpdate']))
                else: raise YunoHostError(1, appid + _(" manifest download failed"))

            try: icon_fetch = urlopen(infos['icon'])
            except IOError: icon_fetch = False
            finally: 
                if icon_fetch and (icon_fetch.code == 200): urlretrieve(infos['icon'], app_path + appid + '/icon.png')
                else: raise YunoHostError(1, appid + _(" icon download failed"))

    return True


def app_list(args):
    pass
