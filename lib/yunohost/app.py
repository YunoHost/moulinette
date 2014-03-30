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
import logging
logging.warning('the module yunohost.app has not been revisited and updated yet')

import os
import sys
import json
import shutil
import stat
import yaml
import time
import re
import socket
import urlparse
from domain import domain_list, domain_add
from user import user_info, user_list
from hook import hook_exec, hook_add, hook_remove

from moulinette.helpers import YunoHostError, YunoHostLDAP, win_msg, random_password, is_true, validate

repo_path        = '/var/cache/yunohost/repo'
apps_path        = '/usr/share/yunohost/apps'
apps_setting_path= '/etc/yunohost/apps/'
install_tmp      = '/var/cache/yunohost'
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
        name -- Name of the list (default yunohost)
        url -- URL of remote JSON list (default http://app.yunohost.org/list.json)

    """
    # Create app path if not exists
    try: os.listdir(repo_path)
    except OSError: os.makedirs(repo_path)

    if url is None:
        url = 'http://app.yunohost.org/list.json'
        name = 'yunohost'
    else:
        if name is None: raise YunoHostError(22, _("You must indicate a name for your custom list"))

    list_file = repo_path +'/'+ name +'.json'
    if os.system('wget "'+ url +'" -O "'+ list_file +'.tmp"') != 0:
        os.remove(list_file +'.tmp')
        raise YunoHostError(1, _("List server connection failed"))

    # Rename fetched temp list
    os.rename(list_file +'.tmp', list_file)

    os.system("touch /etc/cron.d/yunohost-applist-"+ name)
    os.system("echo '00 00 * * * root yunohost app fetchlist -u "+ url +" -n "+ name +" --no-ldap > /dev/null 2>&1' >/etc/cron.d/yunohost-applist-"+ name)

    win_msg(_("List successfully fetched"))


def app_removelist(name):
    """
    Remove list from the repositories

    Keyword argument:
        name -- Name of the list to remove

    """
    try:
        os.remove(repo_path +'/'+ name + '.json')
        os.remove("/etc/cron.d/yunohost-applist-"+ name)
    except OSError:
        raise YunoHostError(22, _("Unknown list"))

    win_msg(_("List successfully removed"))


def app_list(offset=None, limit=None, filter=None, raw=False):
    """
    List apps

    Keyword argument:
        filter -- Name filter of app_id or app_name
        offset -- Starting number for app fetching
        limit -- Maximum number of app fetched
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

    if not applists:
        app_fetchlist()
        applists = os.listdir(repo_path)

    for applist in applists:
        if '.json' in applist:
            with open(repo_path +'/'+ applist) as json_list:
                app_dict.update(json.loads(str(json_list.read())))

    for app in os.listdir(apps_setting_path):
        if app not in app_dict:
            # Look for forks
            if '__' in app:
                original_app = app[:app.index('__')]
                if original_app in app_dict:
                    app_dict[app] = app_dict[original_app]
                    continue
            with open( apps_setting_path + app +'/manifest.json') as json_manifest:
                app_dict[app] = {"manifest":json.loads(str(json_manifest.read()))}
            app_dict[app]['manifest']['orphan']=True

    if len(app_dict) > (0 + offset) and limit > 0:
        sorted_app_dict = {}
        for sorted_keys in sorted(app_dict.keys())[offset:]:
            sorted_app_dict[sorted_keys] = app_dict[sorted_keys]

        i = 0
        for app_id, app_info in sorted_app_dict.items():
            if i < limit:
                if (filter and ((filter in app_id) or (filter in app_info['manifest']['name']))) or not filter:
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
    Get app info

    Keyword argument:
        app -- Specific app ID
        raw -- Return the full app_dict

    """
    try:
        app_info = app_list(filter=app, raw=True)[app]
    except:
        app_info = {}

    if _is_installed(app):
        with open(apps_setting_path + app +'/settings.yml') as f:
            app_info['settings'] = yaml.load(f)

        if raw:
            return app_info
        else:
            return {
                'Name': app_info['manifest']['name'],
                'Description': app_info['manifest']['description']['en'],
                #TODO: Add more infos
            }


def app_map(app=None, raw=False, user=None):
    """
    List apps by domain

    Keyword argument:
        user -- Allowed app map for a user
        raw -- Return complete dict
        app -- Specific app to map

    """

    result = {}

    for app_id in os.listdir(apps_setting_path):
        if app and (app != app_id):
            continue

        if user is not None:
            app_dict = app_info(app=app_id, raw=True)
            if ('mode' not in app_dict['settings']) or ('mode' in app_dict['settings'] and app_dict['settings']['mode'] == 'private'):
                if 'allowed_users' in app_dict['settings'] and user not in app_dict['settings']['allowed_users'].split(','):
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
                    'id': app_settings['id']
            }
        else:
            result[app_settings['domain']+app_settings['path']] = app_settings['label']

    return result


def app_upgrade(app, url=None, file=None):
    """
    Upgrade app

    Keyword argument:
        file -- Folder or tarball for upgrade
        app -- App(s) to upgrade (default all)
        url -- Git url to fetch for upgrade

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
        elif not isinstance(app, list):
            app = [ app ]

        for app_id in app:
            installed = _is_installed(app_id)
            if not installed:
                raise YunoHostError(1, app_id + _(" is not installed"))

            if app_id in upgraded_apps:
                continue

            if '__' in app_id:
                original_app_id = app_id[:app_id.index('__')]
            else:
                original_app_id = app_id

            current_app_dict = app_info(app_id,  raw=True)
            new_app_dict     = app_info(original_app_id, raw=True)

            if file:
                manifest = _extract_app_from_file(file)
            elif url:
                manifest = _fetch_app_from_git(url)
            elif 'lastUpdate' not in new_app_dict or 'git' not in new_app_dict:
                raise YunoHostError(22, app_id + _(" is a custom app, please provide an URL manually in order to upgrade it"))
            elif (new_app_dict['lastUpdate'] > current_app_dict['lastUpdate']) \
                  or ('update_time' not in current_app_dict['settings'] \
                       and (new_app_dict['lastUpdate'] > current_app_dict['settings']['install_time'])) \
                  or ('update_time' in current_app_dict['settings'] \
                       and (new_app_dict['lastUpdate'] > current_app_dict['settings']['update_time'])):
                manifest = _fetch_app_from_git(app_id)
            else:
                continue

            # Check min version
            if 'min_version' in manifest and __version__ < manifest['min_version']:
                raise YunoHostError(1, _("%s requires a more recent version of the moulinette") % app_id)

            app_setting_path = apps_setting_path +'/'+ app_id

            if original_app_id != app_id:
                # Replace original_app_id with the forked one in scripts
                for file in os.listdir(app_tmp_folder +'/scripts'):
                    #TODO: add hooks directory to the list
                    #TODO: do it with sed ?
                    if file[:1] != '.':
                        with open(app_tmp_folder +'/scripts/'+ file, "r") as sources:
                            lines = sources.readlines()
                        with open(app_tmp_folder +'/scripts/'+ file, "w") as sources:
                            for line in lines:
                                sources.write(re.sub(r''+ original_app_id +'', app_id, line))

                if 'hooks' in os.listdir(app_tmp_folder):
                    for file in os.listdir(app_tmp_folder +'/hooks'):
                        #TODO: do it with sed ?
                        if file[:1] != '.':
                            with open(app_tmp_folder +'/hooks/'+ file, "r") as sources:
                                lines = sources.readlines()
                            with open(app_tmp_folder +'/hooks/'+ file, "w") as sources:
                                for line in lines:
                                    sources.write(re.sub(r''+ original_app_id +'', app_id, line))

            # Add hooks
            if 'hooks' in os.listdir(app_tmp_folder):
                for file in os.listdir(app_tmp_folder +'/hooks'):
                    hook_add(app_id, app_tmp_folder +'/hooks/'+ file)

            # Execute App upgrade script
            os.system('chown -hR admin: '+ install_tmp)
            if hook_exec(app_tmp_folder +'/scripts/upgrade') != 0:
                #TODO: display fail messages from script
                pass
            else:
                app_setting(app_id, 'update_time', int(time.time()))

            # Replace scripts and manifest
            os.system('rm -rf "'+ app_setting_path +'/scripts" "'+ app_setting_path +'/manifest.json"')
            os.system('mv "'+ app_tmp_folder +'/manifest.json" "'+ app_tmp_folder +'/scripts" '+ app_setting_path)

            # So much win
            upgraded_apps.append(app_id)
            win_msg(app_id + _(" upgraded successfully"))

        if not upgraded_apps:
            raise YunoHostError(1, _("No app to upgrade"))

        win_msg(_("Upgrade complete"))


def app_install(app, label=None, args=None):
    """
    Install apps

    Keyword argument:
        label
        app -- App to install
        args -- Serialize arguments of installation

    """
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

        # Check min version
        if 'min_version' in manifest and __version__ < manifest['min_version']:
            raise YunoHostError(1, _("%s requires a more recent version of the moulinette") % app_id)

        # Check if app can be forked
        instance_number = _installed_instance_number(app_id, last=True) + 1
        if instance_number > 1 :
            if 'multi_instance' not in manifest or not is_true(manifest['multi_instance']):
                raise YunoHostError(1, _("App is already installed"))

            app_id_forked = app_id + '__' + str(instance_number)

            # Replace app_id with the new one in scripts
            for file in os.listdir(app_tmp_folder +'/scripts'):
                #TODO: do it with sed ?
                if file[:1] != '.':
                    with open(app_tmp_folder +'/scripts/'+ file, "r") as sources:
                        lines = sources.readlines()
                    with open(app_tmp_folder +'/scripts/'+ file, "w") as sources:
                        for line in lines:
                            sources.write(re.sub(r''+ app_id +'', app_id_forked, line))

            if 'hooks' in os.listdir(app_tmp_folder):
                for file in os.listdir(app_tmp_folder +'/hooks'):
                    #TODO: do it with sed ?
                    if file[:1] != '.':
                        with open(app_tmp_folder +'/hooks/'+ file, "r") as sources:
                            lines = sources.readlines()
                        with open(app_tmp_folder +'/hooks/'+ file, "w") as sources:
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

        # Add hooks
        if 'hooks' in os.listdir(app_tmp_folder):
            for file in os.listdir(app_tmp_folder +'/hooks'):
                hook_add(app_id, app_tmp_folder +'/hooks/'+ file)

        app_setting(app_id, 'id', app_id)
        app_setting(app_id, 'install_time', int(time.time()))

        if label:
            app_setting(app_id, 'label', label)
        else:
            app_setting(app_id, 'label', manifest['name'])

        os.system('chown -R admin: '+ app_tmp_folder)

        try:
            if args is None:
                args = ''
            args_dict = dict(urlparse.parse_qsl(args))
        except:
            args_dict = {}

        # Execute App install script
        os.system('chown -hR admin: '+ install_tmp)
        # Move scripts and manifest to the right place
        os.system('cp '+ app_tmp_folder +'/manifest.json ' + app_setting_path)
        os.system('cp -R ' + app_tmp_folder +'/scripts '+ app_setting_path)
        try:
            if hook_exec(app_tmp_folder + '/scripts/install', args_dict) == 0:
                shutil.rmtree(app_tmp_folder)
                os.system('chmod -R 400 '+ app_setting_path)
                os.system('chown -R root: '+ app_setting_path)
                os.system('chown -R admin: '+ app_setting_path +'/scripts')
                app_ssowatconf()
                win_msg(_("Installation complete"))
            else:
                #TODO: display script fail messages
                hook_remove(app_id)
                shutil.rmtree(app_setting_path)
                shutil.rmtree(app_tmp_folder)
                raise YunoHostError(1, _("Installation failed"))
        except KeyboardInterrupt, EOFError:
            hook_remove(app_id)
            shutil.rmtree(app_setting_path)
            shutil.rmtree(app_tmp_folder)
            raise YunoHostError(125, _("Interrupted"))


def app_remove(app):
    """
    Remove app

    Keyword argument:
        app -- App(s) to delete

    """

    if not _is_installed(app):
        raise YunoHostError(22, _("App is not installed"))

    app_setting_path = apps_setting_path + app

    #TODO: display fail messages from script
    try:
        shutil.rmtree('/tmp/yunohost_remove')
    except: pass

    os.system('cp -a '+ app_setting_path + ' /tmp/yunohost_remove && chown -hR admin: /tmp/yunohost_remove')
    os.system('chown -R admin: /tmp/yunohost_remove')
    os.system('chmod -R u+rX /tmp/yunohost_remove')

    if hook_exec('/tmp/yunohost_remove/scripts/remove') != 0:
        pass

    if os.path.exists(app_setting_path): shutil.rmtree(app_setting_path)
    shutil.rmtree('/tmp/yunohost_remove')
    hook_remove(app)
    app_ssowatconf()
    win_msg(_("App removed: ")+ app)


def app_addaccess(apps, users):
    """
    Grant access right to users (everyone by default)

    Keyword argument:
        users
        apps

    """
    if not users:
        users = []
        for user in user_list()['users']:
            users.append(user['username'])

    if not isinstance(users, list): users = [users]
    if not isinstance(apps, list): apps = [apps]

    for app in apps:
        if not _is_installed(app):
            raise YunoHostError(22, _("App is not installed"))

        with open(apps_setting_path + app +'/settings.yml') as f:
            app_settings = yaml.load(f)

        if 'mode' not in app_settings:
            app_setting(app, 'mode', 'private')
            app_settings['mode'] = 'private'

        if app_settings['mode'] == 'private':
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
                    if new_users == '':
                        new_users = allowed_user
                    else:
                        new_users = new_users +','+ allowed_user

            app_setting(app, 'allowed_users', new_users.strip())

    app_ssowatconf()

    return { 'allowed_users': new_users.split(',') }


def app_removeaccess(apps, users):
    """
    Revoke access right to users (everyone by default)

    Keyword argument:
        users
        apps

    """
    remove_all = False
    if not users:
        remove_all = True
    if not isinstance(users, list): users = [users]
    if not isinstance(apps, list): apps = [apps]
    for app in apps:
        new_users = ''

        if not _is_installed(app):
            raise YunoHostError(22, _("App is not installed"))

        with open(apps_setting_path + app +'/settings.yml') as f:
            app_settings = yaml.load(f)

        if 'skipped_uris' not in app_settings or app_settings['skipped_uris'] != '/':
            if remove_all:
                new_users = ''
            elif 'allowed_users' in app_settings:
                for allowed_user in app_settings['allowed_users'].split(','):
                    if allowed_user not in users:
                        if new_users == '':
                            new_users = allowed_user
                        else:
                            new_users = new_users +','+ allowed_user
            else:
                new_users=''
                for user in user_list()['users']:
                    if user['username'] not in users:
                        if new_users == '':
                            new_users = user['username']
                        new_users=new_users+','+user['username']

            app_setting(app, 'allowed_users', new_users.strip())

    app_ssowatconf()

    return { 'allowed_users': new_users.split(',') }


def app_clearaccess(apps):
    """
    Reset access rights for the app

    Keyword argument:
        apps

    """
    if not isinstance(apps, list): apps = [apps]

    for app in apps:
        if not _is_installed(app):
            raise YunoHostError(22, _("App is not installed"))

        with open(apps_setting_path + app +'/settings.yml') as f:
            app_settings = yaml.load(f)

        if 'mode' in app_settings:
            app_setting(app, 'mode', delete=True)

        if 'allowed_users' in app_settings:
            app_setting(app, 'allowed_users', delete=True)

    app_ssowatconf()


def app_setting(app, key, value=None, delete=False):
    """
    Set or get an app setting value

    Keyword argument:
        value -- Value to set
        app -- App ID
        key -- Key to get/set
        delete -- Delete the key

    """
    settings_file = apps_setting_path + app +'/settings.yml'

    try:
        with open(settings_file) as f:
            app_settings = yaml.load(f)
    except IOError:
        # Do not fail if setting file is not there
        app_settings = {}

    if value is None and not delete:
        # Get the value
        if app_settings is not None and key in app_settings:
            print(app_settings[key])
    else:
        # Set the value
        if app_settings is None:
            app_settings = {}
        if delete and key in app_settings:
            del app_settings[key]
        else:
            app_settings[key] = value

        with open(settings_file, 'w') as f:
            yaml.safe_dump(app_settings, f, default_flow_style=False)


def app_service(service, status=None, log=None, runlevel=None, remove=False):
    """
    Add or remove a YunoHost monitored service

    Keyword argument:
        service -- Service to add/remove
        status -- Custom status command
        log -- Absolute path to log file to display
        runlevel -- Runlevel priority of the service
        remove -- Remove service

    """
    service_file = '/etc/yunohost/services.yml'

    try:
        with open(service_file) as f:
            services = yaml.load(f)
    except IOError:
        # Do not fail if service file is not there
        services = {}

    if remove and service in services:
        del services[service]
    else:
        if status is None:
            services[service] = { 'status': 'service' }
        else:
            services[service] = { 'status': status }

    if log is not None:
        services[service]['log'] = log

    if runlevel is not None:
        services[service]['runlevel'] = runlevel

    with open(service_file, 'w') as f:
        yaml.safe_dump(services, f, default_flow_style=False)


def app_checkport(port):
    """
    Check availability of a local port

    Keyword argument:
        port -- Port to check

    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(("localhost", int(port)))
        s.close()
    except socket.error:
        win_msg(_("Port available: ")+ str(port))
    else:
        raise YunoHostError(22, _("Port not available"))



def app_checkurl(url, app=None):
    """
    Check availability of a web path

    Keyword argument:
        url -- Url to check
        app -- Write domain & path to app settings for further checks

    """
    if "https://" == url[:8]:
        url = url[8:]
    elif "http://" == url[:7]:
        url = url[7:]

    if url[-1:] != '/':
        url = url + '/'

    domain = url[:url.index('/')]
    path = url[url.index('/'):]

    if path[-1:] != '/':
        path = path + '/'

    apps_map = app_map(raw=True)
    validate(r'^([a-zA-Z0-9]{1}([a-zA-Z0-9\-]*[a-zA-Z0-9])*)(\.[a-zA-Z0-9]{1}([a-zA-Z0-9\-]*[a-zA-Z0-9])*)*(\.[a-zA-Z]{1}([a-zA-Z0-9\-]*[a-zA-Z0-9])*)$', domain)

    if domain not in domain_list(YunoHostLDAP())['domains']:
        raise YunoHostError(22, _("Domain doesn't exists"))

    if domain in apps_map:
        if path in apps_map[domain]:
            raise YunoHostError(1, _("An app is already installed on this location"))
        for app_path, v in apps_map[domain].items():
            if app_path in path and app_path.count('/') < path.count('/'):
                raise YunoHostError(1, _("Unable to install app at this location"))

    if app is not None:
        app_setting(app, 'domain', value=domain)
        app_setting(app, 'path', value=path)


def app_initdb(user, password=None, db=None, sql=None):
    """
    Create database and initialize it with optionnal attached script

    Keyword argument:
        db -- DB name (user unless set)
        user -- Name of the DB user
        password -- Password of the DB (generated unless set)
        sql -- Initial SQL file

    """
    if db is None:
        db = user

    return_pwd = False
    if password is None:
        password = random_password(12)
        return_pwd = True
        print(password)

    mysql_root_pwd = open('/etc/yunohost/mysql').read().rstrip()
    mysql_command = 'mysql -u root -p'+ mysql_root_pwd +' -e "CREATE DATABASE '+ db +' ; GRANT ALL PRIVILEGES ON '+ db +'.* TO \''+ user +'\'@localhost IDENTIFIED BY \''+ password +'\';"'
    if os.system(mysql_command) != 0:
        raise YunoHostError(1, _("MySQL DB creation failed"))
    if sql is not None:
        if os.system('mysql -u '+ user +' -p'+ password +' '+ db +' < '+ sql) != 0:
            raise YunoHostError(1, _("MySQL DB init failed"))

    if not return_pwd:
        win_msg(_("Database initiliazed"))


def app_ssowatconf():
    """
    Regenerate SSOwat configuration file


    """

    with open('/etc/yunohost/current_host', 'r') as f:
        main_domain = f.readline().rstrip()

    domains = domain_list(YunoHostLDAP())['domains']

    users = {}
    for user in user_list()['users']:
        users[user['username']] = app_map(user=user['username'])

    skipped_urls = []
    skipped_regex = []
    unprotected_urls = []
    unprotected_regex = []
    protected_urls = []
    protected_regex = []

    apps = {}
    for app in app_list()['Apps']:
        if _is_installed(app['ID']):
            with open(apps_setting_path + app['ID'] +'/settings.yml') as f:
                app_settings = yaml.load(f)
                if 'skipped_uris' in app_settings:
                    for item in app_settings['skipped_uris'].split(','):
                        if item[-1:] == '/':
                            item = item[:-1]
                        skipped_urls.append(app_settings['domain'] + app_settings['path'][:-1] + item)
                if 'skipped_regex' in app_settings:
                    for item in app_settings['skipped_regex'].split(','):
                        skipped_regex.append(item)
                if 'unprotected_uris' in app_settings:
                    for item in app_settings['unprotected_uris'].split(','):
                        if item[-1:] == '/':
                            item = item[:-1]
                        unprotected_urls.append(app_settings['domain'] + app_settings['path'][:-1] + item)
                if 'unprotected_regex' in app_settings:
                    for item in app_settings['unprotected_regex'].split(','):
                        unprotected_regex.append(item)
                if 'protected_uris' in app_settings:
                    for item in app_settings['protected_uris'].split(','):
                        if item[-1:] == '/':
                            item = item[:-1]
                        protected_urls.append(app_settings['domain'] + app_settings['path'][:-1] + item)
                if 'protected_regex' in app_settings:
                    for item in app_settings['protected_regex'].split(','):
                        protected_regex.append(item)

    for domain in domains:
        skipped_urls.extend([domain +'/ynhadmin', domain +'/ynhapi'])

    with open('/etc/ssowat/conf.json') as f:
        conf_dict = json.load(f)

    if not 'portal_domain' in conf_dict:
        conf_dict['portal_domain'] = main_domain
    if not 'portal_path' in conf_dict:
        conf_dict['portal_path'] = '/ynhsso/'
    if not 'portal_port' in conf_dict:
        conf_dict['portal_port'] = '443'
    if not 'portal_scheme' in conf_dict:
        conf_dict['portal_scheme'] = 'https'
    if not 'additional_headers' in conf_dict:
        conf_dict['additional_headers'] = {
            'Auth-User': 'uid',
            'Remote-User': 'uid',
            'Name': 'cn',
            'Email': 'mail'
        }
    conf_dict['domains'] = domains
    conf_dict['skipped_urls'] = skipped_urls
    conf_dict['unprotected_urls'] = unprotected_urls
    conf_dict['protected_urls'] = protected_urls
    conf_dict['skipped_regex'] = skipped_regex
    conf_dict['unprotected_regex'] = unprotected_regex
    conf_dict['protected_regex'] = protected_regex
    conf_dict['users'] = users

    with open('/etc/ssowat/conf.json', 'wb') as f:
        json.dump(conf_dict, f)

    win_msg(_('SSOwat configuration generated'))


def _extract_app_from_file(path, remove=False):
    """
    Unzip or untar application tarball in app_tmp_folder, or copy it from a directory

    Keyword arguments:
        path -- Path of the tarball or directory
        remove -- Remove the tarball after extraction

    Returns:
        Dict manifest

    """
    global app_tmp_folder

    print(_('Extracting...'))

    if os.path.exists(app_tmp_folder): shutil.rmtree(app_tmp_folder)
    os.makedirs(app_tmp_folder)

    if ".zip" in path:
        extract_result = os.system('cd '+ os.getcwd() +' && unzip '+ path +' -d '+ app_tmp_folder +' > /dev/null 2>&1')
        if remove: os.remove(path)
    elif ".tar" in path:
        extract_result = os.system('cd '+ os.getcwd() +' && tar -xf '+ path +' -C '+ app_tmp_folder +' > /dev/null 2>&1')
        if remove: os.remove(path)
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
        if len(os.listdir(app_tmp_folder)) == 1:
            for folder in os.listdir(app_tmp_folder):
                app_tmp_folder = app_tmp_folder +'/'+ folder
        with open(app_tmp_folder + '/manifest.json') as json_manifest:
            manifest = json.loads(str(json_manifest.read()))
            manifest['lastUpdate'] = int(time.time())
    except IOError:
        raise YunoHostError(1, _("Invalid App file"))

    print(_('OK'))

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

    print(_('Downloading...'))

    if ('@' in app) or ('http://' in app) or ('https://' in app):
        if "github.com" in app:
            url = app.replace("git@github.com:", "https://github.com/")
            if ".git" in url[-4:]: url = url[:-4]
            if "/" in url [-1:]: url = url[:-1]
            url = url + "/archive/master.zip"
            if os.system('wget "'+ url +'" -O "'+ app_tmp_folder +'.zip" > /dev/null 2>&1') == 0:
                return _extract_app_from_file(app_tmp_folder +'.zip', remove=True)

        git_result   = os.system('git clone '+ app +' '+ app_tmp_folder)
        git_result_2 = 0
        try:
            with open(app_tmp_folder + '/manifest.json') as json_manifest:
                manifest = json.loads(str(json_manifest.read()))
                manifest['lastUpdate'] = int(time.time())
        except IOError:
            raise YunoHostError(1, _("Invalid App manifest"))

    else:
        app_dict = app_list(raw=True)

        if app in app_dict:
            app_info = app_dict[app]
            app_info['manifest']['lastUpdate'] = app_info['lastUpdate']
            manifest = app_info['manifest']
        else:
            raise YunoHostError(22, _("App doesn't exists"))

        if "github.com" in app_info['git']['url']:
            url = app_info['git']['url'].replace("git@github.com:", "https://github.com/")
            if ".git" in url[-4:]: url = url[:-4]
            if "/" in url [-1:]: url = url[:-1]
            url = url + "/archive/"+ str(app_info['git']['revision']) + ".zip"
            if os.system('wget "'+ url +'" -O "'+ app_tmp_folder +'.zip" > /dev/null 2>&1') == 0:
                return _extract_app_from_file(app_tmp_folder +'.zip', remove=True)

        app_tmp_folder = install_tmp +'/'+ app
        if os.path.exists(app_tmp_folder): shutil.rmtree(app_tmp_folder)

        git_result   = os.system('git clone '+ app_info['git']['url'] +' -b '+ app_info['git']['branch'] +' '+ app_tmp_folder)
        git_result_2 = os.system('cd '+ app_tmp_folder +' && git reset --hard '+ str(app_info['git']['revision']))

    if not git_result == git_result_2 == 0:
        raise YunoHostError(22, _("Sources fetching failed"))

    print(_('OK'))

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
            if number == 0 and app == installed_app:
                number = 1
            elif '__' in installed_app:
                if app == installed_app[:installed_app.index('__')]:
                    if int(installed_app[installed_app.index('__') + 2:]) > number:
                        number = int(installed_app[installed_app.index('__') + 2:])

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

