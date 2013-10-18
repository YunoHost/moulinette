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

""" yunohost_app.py

    Manage apps
"""
import os
import sys
import json
import shutil
import stat
import yaml
import time
from yunohost import YunoHostError, YunoHostLDAP, win_msg, random_password, is_true
from yunohost_domain import domain_list, domain_add
from yunohost_user import user_info
from yunohost_hook import hook_exec

repo_path        = '/var/cache/yunohost/repo'
apps_path        = '/usr/share/yunohost/apps'
apps_setting_path= '/etc/yunohost/apps/'
install_tmp      = '/tmp/yunohost/install'
app_tmp_folder   = install_tmp + '/from_file'

def app_listlists():
    """
    List fetched lists


    """
    list_list = []
    try:
        for filename in os.listdir(repo_path):
            if '.json' in filename:
                list_list.append(filename[:len(filename)-5])
    except OSError:
        raise YunoHostError(1, _("No list found"))

    return { 'Lists' : list_list }


def app_fetchlist(url=None, name=None):
    """
    Fetch application list from app server

    Keyword argument:
        url -- URL of remote JSON list (default http://app.yunohost.org/list.json)
        name -- Name of the list (default yunohost)

    """
    # Create app path if not exists
    try: os.listdir(repo_path)
    except OSError: os.makedirs(repo_path)

    if not url:
        url = 'http://app.yunohost.org/list.json'
        name = 'yunohost'
    else:
        if not name: raise YunoHostError(22, _("You must indicate a name for your custom list"))

    if os.system('wget "'+ url +'" -O "'+ repo_path +'/'+ name +'.json"') != 0:
        raise YunoHostError(1, _("List server connection failed"))

    win_msg(_("List successfully fetched"))


def app_removelist(name):
    """
    Remove list from the repositories

    Keyword argument:
        name -- Name of the list to remove

    """
    try:
        os.remove(repo_path +'/'+ name + '.json')
    except OSError:
        raise YunoHostError(22, _("Unknown list"))

    win_msg(_("List successfully removed"))


def app_list(offset=None, limit=None, filter=None, raw=False):
    """
    List apps

    Keyword argument:
        limit -- Maximum number of app fetched
        offset -- Starting number for app fetching
        filter -- Name filter of app_id or app_name
        raw -- Return the full app_dict

    """
    # TODO: List installed applications

    if offset: offset = int(offset)
    else: offset = 0
    if limit: limit = int(limit)
    else: limit = 1000

    applists = os.listdir(repo_path)
    app_dict  = {}
    if raw:
        list_dict = {}
    else:
        list_dict=[]

    if not applists: app_fetchlist()

    for applist in applists:
        if '.json' in applist:
            with open(repo_path +'/'+ applist) as json_list:
                app_dict.update(json.loads(str(json_list.read())))

    if len(app_dict) > (0 + offset) and limit > 0:
        sorted_app_dict = {}
        for sorted_keys in sorted(app_dict.keys())[offset:]:
            sorted_app_dict[sorted_keys] = app_dict[sorted_keys]

        i = 0
        for app_id, app_info in sorted_app_dict.items():
            if i < limit:
                if (filter and ((filter in app_id) or (filter in app_info['manifest']['name']))) or not filter:
                    #TODO: make _is_installed
                    installed = _is_installed(app_id)

                    if raw:
                        app_info['installed'] = installed
                        list_dict[app_id] = app_info
                    else:
                        list_dict.append({
                            'ID': app_id,
                            'Name': app_info['manifest']['name'],
                            'Description': app_info['manifest']['description'],
                            'Installed': installed
                        })
                    i += 1
            else:
               break
    if not raw:
        list_dict = { 'Apps': list_dict }
    return list_dict


def app_info(app, raw=False):
    """
    Get app informations

    Keyword argument:
        app -- App ID
        raw -- Return the full app_dict

    """
    try:
        app_info = app_list(filter=app, limit=1, raw=True)[app]
    except YunoHostError:
        app_info = {}

    if raw:
        return app_info
    else:
        return [
            ('Name', app_info['manifest']['name']),
            ('Version', app_info['manifest']['version']),
            ('Description', app_info['manifest']['description']),
            #TODO: Add more infos
        ]


def app_map(app=None, raw=False):
    """
    List apps by domain

    Keyword argument:
        app -- Specific app to map
        raw -- Return complete dict

    """

    result = {}

    for app_id in os.listdir(apps_setting_path):
        if app and (app != app_id):
            continue

        with open(apps_setting_path + app_id +'/settings.yml') as f:
            app_settings = yaml.load(f)

        if 'domain' not in app_settings:
            continue

        if raw:
            if app_settings['domain'] not in result:
                result[app_settings['domain']] = {}
            result[app_settings['domain']][app_settings['path']] = {
                    'label': app_settings['label'],
                    'id': app_settings['id'],
                    'instance': app_settings['instance']
            }
        else:
            result['https://'+app_settings['domain']+app_settings['path']] = app_settings['label']

    return result


def app_upgrade(app, url=None, file=None):
    """
    Upgrade app

    Keyword argument:
        url -- Git url to fetch for upgrade
        app -- App(s) to upgrade (default all)
        file -- Folder or tarball for upgrade

    """
    with YunoHostLDAP() as yldap:
        try:
            app_list()
        except YunoHostError:
            raise YunoHostError(1, _("No app to upgrade"))

        upgraded_apps = []

        # If no app is specified, upgrade all apps
        if not app:
            app = os.listdir(apps_setting_path)

        for app_id in app:
            installed = _is_installed(app_id)
            if not installed:
                raise YunoHostError(1, app_id + _(" is not installed"))

            if app_id in upgraded_apps:
                continue

            #TODO: fix that (and check for instance number)
            current_app_dict = app_info(app_id, instance=number, raw=True)
            new_app_dict     = app_info(app_id, raw=True)

            if file:
                manifest = _extract_app_from_file(file)
            elif url:
                manifest = _fetch_app_from_git(url)
            elif (new_app_dict['lastUpdate'] > current_app_dict['lastUpdate']) or ('update_time' not in current_app_dict['settings'] and (new_app_dict['lastUpdate'] > current_app_dict['settings']['install_time'])) or ('update_time' in current_app_dict['settings'] and (new_app_dict['lastUpdate'] > current_app_dict['settings']['update_time'])):
                manifest = _fetch_app_from_git(app_id)
            else:
                continue

            app_setting_path = apps_setting_path +'/'+ app_id

            # Execute App upgrade script
            if hook_exec(app_setting_path+ '/scripts/upgrade') != 0:
                #TODO: display fail messages from script
                pass
            else:
                app_setting(app_id, 'update_time', int(time.time()))

            # Move scripts and manifest to the right place
            os.system('mv "'+ app_tmp_folder +'/manifest.json" "'+ app_tmp_folder +'/scripts" '+ app_setting_path)

            # So much win
            upgraded_apps.append(app_id)
            win_msg(app_id + _(" upgraded successfully"))

        if not upgraded_apps:
            raise YunoHostError(1, _("No app to upgrade"))

        win_msg(_("Upgrade complete"))


def app_install(app, label=None):
    """
    Install apps

    Keyword argument:
        app -- App ID to install
        label

    """
    #TODO: Create tool for ssowat
    #TODO: Create tool for nginx (check path availability & stuff)

    with YunoHostLDAP() as yldap:

        # Fetch or extract sources
        try: os.listdir(install_tmp)
        except OSError: os.makedirs(install_tmp)

        if app in app_list(raw=True) or ('@' in app) or ('http://' in app) or ('https://' in app):
            manifest = _fetch_app_from_git(app)
        else:
            manifest = _extract_app_from_file(app)

        # Check ID
        if 'id' not in manifest or '__' in manifest['id']:
            raise YunoHostError(22, _("App id is invalid"))

        app_id = manifest['id']

        # Check if app can be forked
        instance_number = _installed_instance_number(app_id, last=True) + 1
        if instance_number > 1 :
            if 'multi_instance' not in manifest or not is_true(manifest['multi_instance']):
                raise YunoHostError(1, _("App is already installed"))

            forked_app_id = app_id + '__' + instance_number

            # Replace app_id with the new one in scripts
            for file in os.listdir(app_tmp_folder +'/scripts'):
                #TODO: add hooks directory to the list
                #TODO: do it with sed ?
                with open(file, "r") as sources:
                    lines = sources.readlines()
                with open(file, "w") as sources:
                    for line in lines:
                        sources.write(re.sub(r''+ app_id +'', app_id_forked, line))

            # Change app_id for the rest of the process
            app_id = app_id_forked

        # Prepare App settings
        app_setting_path = apps_setting_path +'/'+ app_id

        #TMP: Remove old settings
        if os.path.exists(app_setting_path): shutil.rmtree(app_setting_path)
        os.makedirs(app_setting_path)
        os.system('touch '+ app_setting_path +'/settings.yml')

        app_setting(app_id, 'id', app_id)
        app_setting(app_id, 'install_time', int(time.time()))

        if label:
            app_setting(app_id, 'label', label)
        else:
            app_setting(app_id, 'label', manifest['name'])

        # Move scripts and manifest to the right place
        os.system('mv "'+ app_tmp_folder +'/manifest.json" "'+ app_tmp_folder +'/scripts" '+ app_setting_path)

        # Execute App install script
        if hook_exec(app_setting_path+ '/scripts/install') != 0:
            #TODO: display script fail messages
            shutil.rmtree(app_setting_path)

        win_msg(_("Installation complete"))


def app_remove(app):
    """
    Remove app

    Keyword argument:
        app -- App(s) to delete

    """

    if not _is_installed(app):
        raise YunoHostError(22, _("App is not installed"))

    #TODO: display fail messages from script
    if hook_exec(apps_setting_path +'/'+ app + '/scripts/remove') != 0:
        pass

    if os.path.exists(app_setting_path): shutil.rmtree(app_setting_path)

    win_msg(_("App removed: ")+ app)


def app_addaccess(apps, users):
    """
    Grant access right to users (everyone by default)

    Keyword argument:
        users
        apps

    """
    #TODO: Adapt to SSOwat
    if not isinstance(users, list): users = [users]
    if not isinstance(apps, list): apps = [apps]

    for app in apps:
        if not _is_installed(app):
            raise YunoHostError(22, _("App is not installed"))

        with open(apps_setting_path + app +'/settings.yml') as f:
            app_settings = yaml.load(f)

        if 'mode' in app_settings and app_settings['mode'] == 'private':
            if 'allowed_users' in app_settings:
                new_users = app_settings['allowed_users']
            else:
                new_users = ''

            for allowed_user in users:
                if allowed_user not in new_users.split(','):
                    try:
                        user_info(allowed_user)
                    except YunoHostError:
                        continue
                    new_users = new_users +','+ allowed_user

            app_settings['allowed_users'] = new_users.strip()
            with open(apps_setting_path + app +'/settings.yml', 'w') as f:
                yaml.safe_dump(app_settings, f, default_flow_style=False)
                win_msg(_("App setting file updated"))

    #TODO: Regenerate SSOwat conf


def app_removeaccess(apps, users):
    """
    Revoke access right to users (everyone by default)

    Keyword argument:
        users
        apps

    """
    #TODO: Remove access
    if not isinstance(users, list): users = [users]
    if not isinstance(apps, list): apps = [apps]

    for app in apps:
        new_users = ''

        if not _is_installed(app):
            raise YunoHostError(22, _("App is not installed"))

        with open(apps_setting_path + app +'/settings.yml') as f:
            app_settings = yaml.load(f)

        if 'mode' in app_settings and app_settings['mode'] == 'private':
            if 'allowed_users' in app_settings:
                for allowed_user in app_settings['allowed_users'].split(','):
                    if allowed_user not in users:
                        new_users = new_users +','+ allowed_user

                app_settings['allowed_users'] = new_users.strip()
                with open(apps_setting_path + app +'/settings.yml', 'w') as f:
                    yaml.safe_dump(app_settings, f, default_flow_style=False)
                    win_msg(_("App setting file updated"))

    #TODO: Regenerate SSOwat conf


def app_setting(app, key, value=None):
    """

    """
    settings_file = apps_setting_path + app +'/settings.yml'

    with open(settings_file) as f:
        app_settings = yaml.load(f)

    if app_settings is None:
        app_settings = {}
    if value is not None:
        if value == '' and key in app_settings:
            del app_settings[key]
        else:
            app_settings[key] = value
    elif key in app_settings:
        return app_settings[key]

    with open(settings_file, 'w') as f:
        yaml.safe_dump(app_settings, f, default_flow_style=False)
    
    return True
        

def _extract_app_from_file(path):
    """
    Unzip or untar application tarball in app_tmp_folder, or copy it from a directory

    Keyword arguments:
        path -- Path of the tarball or directory

    Returns:
        Dict manifest

    """
    if os.path.exists(app_tmp_folder): shutil.rmtree(app_tmp_folder)
    os.makedirs(app_tmp_folder)

    if ".zip" in path:
        extract_result = os.system('cd '+ os.getcwd() +' && unzip '+ path +' -d '+ app_tmp_folder)
    elif ".tar" in path:
        extract_result = os.system('cd '+ os.getcwd() +' && tar -xf '+ path +' -C '+ app_tmp_folder)
    elif (path[:1] == '/' and os.path.exists(path)) or (os.system('cd '+ os.getcwd() +'/'+ path) == 0):
        shutil.rmtree(app_tmp_folder)
        if path[len(path)-1:] != '/':
            path = path + '/'
        extract_result = os.system('cd '+ os.getcwd() +' && cp -a "'+ path +'" '+ app_tmp_folder)
    else:
        extract_result = 1

    if extract_result != 0:
        raise YunoHostError(22, _("Invalid install file"))

    try:
        with open(app_tmp_folder + '/manifest.json') as json_manifest:
            manifest = json.loads(str(json_manifest.read()))
            manifest['lastUpdate'] = int(time.time())
    except IOError:
        raise YunoHostError(1, _("Invalid App file"))

    win_msg(_("Sources extracted"))

    return manifest


def _fetch_app_from_git(app):
    """
    Unzip or untar application tarball in app_tmp_folder

    Keyword arguments:
        app -- App_id or git repo URL

    Returns:
        Dict manifest

    """
    global app_tmp_folder

    if ('@' in app) or ('http://' in app) or ('https://' in app):
        git_result   = os.system('git clone '+ app +' '+ app_tmp_folder)
        git_result_2 = 0
        try:
            with open(app_tmp_folder + '/manifest.json') as json_manifest:
                manifest = json.loads(str(json_manifest.read()))
                manifest['lastUpdate'] = int(time.time())
        except IOError:
            raise YunoHostError(1, _("Invalid App manifest"))

    else:
        app_tmp_folder = install_tmp +'/'+ app
        if os.path.exists(app_tmp_folder): shutil.rmtree(app_tmp_folder)

        app_dict = app_list(raw=True)

        if app in app_dict:
            app_info = app_dict[app]
            app_info['manifest']['lastUpdate'] = app_info['lastUpdate']
            manifest = app_info['manifest']
        else:
            raise YunoHostError(22, _("App doesn't exists"))

        git_result   = os.system('git clone '+ app_info['git']['url'] +' -b '+ app_info['git']['branch'] +' '+ app_tmp_folder)
        git_result_2 = os.system('cd '+ app_tmp_folder +' && git reset --hard '+ str(app_info['git']['revision']))

    if not git_result == git_result_2 == 0:
        raise YunoHostError(22, _("Sources fetching failed"))

    win_msg(_("Repository fetched"))

    return manifest


def _installed_instance_number(app, last=False):
    """
    Check if application is installed and return instance number

    Keyword arguments:
        app -- id of App to check
        last -- Return only last instance number

    Returns:
        Number of last installed instance | List or instances

    """
    if last:
        number = 0
        try:
            installed_apps = os.listdir(apps_setting_path)
        except OSError:
            os.makedirs(apps_setting_path)
            return 0

        for installed_app in installed_apps:
            if '__' in installed_app:
                if app == installed_app[:installed_app.index('__')]:
                    if int(installed_app[installed_app.index('__') + 2:]) > number:
                        number = int(installed_app[installed_app.index('__') + 2:])
            else:
                if _is_installed(app):
                    number = 1

        return number

    else:
        instance_number_list = []
        instances_dict = app_map(app=app, raw=True)
        for key, domain in instances_dict.items():
            for key, path in domain.items():
                instance_number_list.append(path['instance'])

        return sorted(instance_number_list)


def _is_installed(app):
    """
    Check if application is installed

    Keyword arguments:
        app -- id of App to check

    Returns:
        Boolean

    """
    try:
        installed_apps = os.listdir(apps_setting_path)
    except OSError:
        os.makedirs(apps_setting_path)
        return False

    for installed_app in installed_apps:
        if app == installed_app:
            return True
        else:
            continue

    return False

