# -*- coding: utf-8 -*-

import os
import sys
import json
from urllib import urlopen, urlretrieve
from yunohost import YunoHostError, YunoHostLDAP, win_msg
from yunohost_domain import domain_list, domain_add

def app_fetchlist(url=None, name=None):
    """
    Fetch application list

    Keyword arguments:
        url -- Custom list URL
        name -- Name of the app list

    Returns:
        True | YunoHostError

    """
    repo_path = '/var/cache/yunohost/repo/'

    # Create app path if not exists
    try: os.listdir(repo_path)
    except OSError: os.makedirs(repo_path)

    if not url:
        url = 'http://fapp.yunohost.org/app/list/raw'
        name = "fapp"
    else:
        if not name: raise YunoHostError(22, _("You must indicate a name for your custom list"))

    if os.system('wget "'+ url +'" -O "'+ repo_path + name +'.json"') != 0:
        raise YunoHostError(1, _("List server connection failed"))

    win_msg(_("List successfully fetched"))


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

    repo_path = '/var/cache/yunohost/repo/'
    applists = os.listdir(repo_path)
    app_dict  = {}
    list_dict = {}

    if not applists: app_fetchlist()

    for applist in applists:
        if '.json' in applist:
            with open(repo_path + applist) as json_list:
                app_dict.update(json.loads(str(json_list.read())))


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

def app_install(app, domain=None, path=None, label=None, public=False, protected=True):
    """
    Install selected app

    Keyword arguments:
        app -- AppID to install (or filename)
        domain -- Web domain for the app
        path -- Subpath of the domain
        label -- User defined name for the app
        public -- Allow app public access
        protected -- App is protected by the SSO

    Returns:
        Win | Fail

    """

    # TODO: Check if the app is already installed

    # Fetch | Extract sources

    install_tmp = '/tmp/yunohost/install'
    try: os.listdir(install_tmp)
    except OSError: os.makedirs(install_tmp)


    if "." in app:
        install_from_file = True
        app_tmp_folder = install_tmp + '/from_file'
        os.makedirs(app_tmp_folder)
        if ".zip" in app:
            extract_result = os.system('cd '+ os.getcwd()  +' && unzip '+ app +' -d '+ app_tmp_folder)
        elif ".tar" in app:
            extract_result = os.system('cd '+ os.getcwd() +' && tar -C '+ app_tmp_folder +' -xf '+ app)
        else:
            extract_result = 1

        if extract_result != 0:
            raise YunoHostError(22, _("Invalid install file"))

        with open(app_tmp_folder + '/manifest.webapp') as json_manifest:
            manifest = json.loads(str(json_manifest.read()))

    else:
        install_from_file = False
        app_tmp_folder = install_tmp +'/'+ app
        with open('/var/cache/yunohost/apps/list.json') as json_list:
            app_dict = json.loads(str(json_list.read()))

        if app in app_dict:
            app_info = app_dict[app]
            manifest = app_info['manifest']
        else:
            raise YunoHostError(22, _("App doesn't exists"))

        git_result   = os.system('git clone '+ app_info['git']['url'] +' -b '+ app_info['git']['branch'] +' '+ app_tmp_folder)
        git_result_2 = os.system('cd '+ app_tmp_folder +' && git reset --hard '+ str(app_info['git']['revision']))

        if not git_result == git_result_2 == 0:
            raise YunoHostError(22, _("Sources fetching failed"))

    # TODO: Check if exists another instance

    try:
        domain_list(filter="virtualdomain="+ domain)
    except YunoHostError:
        domain_add([domain])


    # TODO: Install dependencies

    for dependency in manifest['dependencies']['debian']:
        print dependency

    # TODO: Exec install script

    # TODO: Check if MYSQL DB is needed and create it, then init DB if needed

    # TODO: Copy files to the right place

    # TODO: Exec postinstall script

    # TODO: Create appsettings

    # TODO: Configure apache/lemon with NPZE's scripts

    # TODO: Remove scripts folder



