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
from yunohost import YunoHostError, YunoHostLDAP, win_msg, random_password, lvl, is_true, lemon_configuration
from yunohost_domain import domain_list, domain_add
from yunohost_user import user_info

repo_path        = '/var/cache/yunohost/repo'
apps_path        = '/usr/share/yunohost/apps'
apps_setting_path= '/etc/yunohost/apps/'
a2_settings_path = '/etc/yunohost/apache/domains'
a2_template_path = '/etc/yunohost/apache/templates'
install_tmp      = '/tmp/yunohost/install'
app_tmp_folder   = install_tmp + '/from_file'
lemon_tmp_conf   = '/tmp/tmplemonconf'

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
        url -- URL of remote JSON list (default http://fapp.yunohost.org/app/list/raw)
        name -- Name of the list (default fapp)

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
    list_dict = {}

    if not applists: app_fetchlist()

    for applist in applists:
        if '.json' in applist:
            with open(repo_path +'/'+ applist) as json_list:
                app_dict.update(json.loads(str(json_list.read())))

    if len(app_dict) > (0 + offset) and limit > 0:
        sorted_app_dict = {}
        for sorted_keys in sorted(app_dict.keys())[i:]:
            sorted_app_dict[sorted_keys] = app_dict[sorted_keys]

        i = 0
        for app_id, app_info in sorted_app_dict.items():
            if i < limit:
        	    if (filter and ((filter in app_id) or (filter in app_info['manifest']['name']))) or not filter:
                    instance_number = len(_installed_instance_number(app_id))
                    if instance_number > 1:
                        installed_txt = 'Yes ('+ str(instance_number) +' times)'
                    elif instance_number == 1:
                        installed_txt = 'Yes'
                    else:
                        installed_txt = 'No'

                if raw:
                    list_dict[app_id] = app_info
                else:
                    list_dict[app_id] = [
                        ('Name', app_info['manifest']['name']),
                        ('Version', app_info['manifest']['version']),
                        ('Description', app_info['manifest']['description']),
                        ('Installed', installed_txt)
                    ]
                i += 1
            else:
                break

    return list_dict


def app_info(app, instance=None, raw=False):
    """
    Get app informations

    Keyword argument:
        app -- App ID
        instance -- App instance number
        raw -- Return the full app_dict

    """
    try:
        app_info = app_list(filter=app, limit=1, raw=True)[app]
    except YunoHostError:
        app_info = {}

    # If installed
    instance_number = len(_installed_instance_number(app))
    if instance_number > 0 and instance:
        unique_app_id = app +'__'+ instance
        with open(apps_setting_path + unique_app_id+ '/manifest.webapp') as json_manifest:
            app_info['manifest'] = json.loads(str(json_manifest.read()))
        with open(apps_setting_path + unique_app_id +'/app_settings.yml') as f:
            app_info['settings'] = yaml.load(f)

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

    for unique_app_id in os.listdir(apps_setting_path):
        if app and (app != unique_app_id) and (app != unique_app_id[:unique_app_id.find('__')]):
            continue

        with open(apps_setting_path + unique_app_id +'/app_settings.yml') as f:
            app_settings = yaml.load(f)

        if raw:
            if app_settings['domain'] not in result:
                result[app_settings['domain']] = {}
            result[app_settings['domain']][app_settings['path']] = {
                    'label': app_settings['label'],
                    'uid': app_settings['uid'],
                    'instance': app_settings['instance'],
                    'mode': app_settings['mode'],
            }
        else:
            result['https://'+app_settings['domain']+app_settings['path']] = app_settings['label']

    return result


def app_upgrade(app, instance=[], url=None, file=None):
    """
    Upgrade app

    Keyword argument:
        url -- Git url to fetch for upgrade
        app -- App(s) to upgrade (default all)
        file -- Folder or tarball for upgrade
        instance -- App instance number to upgrade

    """
    with YunoHostLDAP() as yldap:
        try:
            app_list()
        except YunoHostError:
            raise YunoHostError(1, _("No app to upgrade"))

        upgraded_apps = []
        if not app:
            unique_app_id_list = os.listdir(apps_setting_path)
            for unique_app_id in unique_app_id_list:
                app_id = unique_app_id[:unique_app_id.find('__')]
                if app_id not in app:
                    app.append(app_id)

        for app_id in app:
            instance_number = _installed_instance_number(app_id)
            if instance_number == 0:
                raise YunoHostError(1, app_id + _(" is not installed"))
            elif not instance:
                instance = range(1, instance_number + 1)

            for number in instance:
                if int(number) > instance_number:
                    continue
                number = str(number)
                unique_app_id = app_id +'__'+ number
                if unique_app_id in upgraded_apps:
                    raise YunoHostError(1, _("Conflict, multiple upgrades of the same app: ")+ app_id +' (instance n°'+ number +')')

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

                is_web = lvl(manifest, 'yunohost', 'webapp')

                app_final_path = apps_path +'/'+ unique_app_id
                script_var_dict = {
                    'APP_DIR': app_tmp_folder,
                    'APP_FINAL_DIR': app_final_path,
                    'APP_ID': unique_app_id
                }

                if is_web:
                    script_var_dict.update({
                        'APP_DOMAIN': current_app_dict['settings']['domain'],
                        'APP_PATH': current_app_dict['settings']['path']
                    })


                #########################################
                # Install dependencies                  #
                #########################################

                if lvl(manifest, 'dependencies'):
                    _install_app_dependencies(manifest['dependencies'])


                #########################################
                # DB Vars                               #
                #########################################

                if lvl(manifest, 'yunohost', 'webapp', 'db'):
                    script_var_dict.update({
                        'DB_USER': current_app_dict['settings']['db_user'],
                        'DB_PWD': current_app_dict['settings']['db_pwd'],
                        'DB_NAME': current_app_dict['settings']['db_user']
                    })

                #########################################
                # Execute App install script            #
                #########################################

                if lvl(manifest, 'yunohost', 'script_path'):
                    _exec_app_script(step='upgrade', path=app_tmp_folder +'/'+ manifest['yunohost']['script_path'], var_dict=script_var_dict, app_type=manifest['type'])

                #########################################
                # Copy files to the right final place   #
                #########################################

                # TMP: Remove old application
                # if os.path.exists(app_final_path): shutil.rmtree(app_final_path)

                os.system('cp -a "'+ app_tmp_folder +'" "'+ app_final_path +'"')

                if is_web:
                    if manifest['type'] != 'privileged' and manifest['type'] != 'certified':
                        os.system('chown -R www-data: "'+ app_final_path +'"')
                    os.system('service apache2 reload')
                shutil.rmtree(app_final_path + manifest['yunohost']['script_path'])


                #########################################
                # Write App settings                    #
                #########################################

                app_setting_path = apps_setting_path +'/'+ unique_app_id

                current_app_dict['settings']['update_time'] = int(time.time())

                with open(app_setting_path +'/app_settings.yml', 'w') as f:
                    yaml.safe_dump(current_app_dict['settings'], f, default_flow_style=False)
                    win_msg(_("App setting file updated"))

                if lvl(manifest, 'yunohost', 'script_path'):
                    os.system('cp -a "'+ app_tmp_folder +'/'+ manifest['yunohost']['script_path'] +'" '+ app_setting_path)

                shutil.rmtree(app_tmp_folder)
                os.system('mv "'+ app_final_path +'/manifest.webapp" '+ app_setting_path)

                if os.system('chmod 400 -R '+ app_setting_path) != 0:
                    raise YunoHostError(22, _("Error during permission setting"))


                #########################################
                # So much win                           #
                #########################################

                upgraded_apps.append(unique_app_id)
                win_msg(app_id + _(" upgraded successfully"))

        if not upgraded_apps:
            raise YunoHostError(1, _("No app to upgrade"))

        win_msg(_("Upgrade complete"))


def app_install(app, domain, path='/', label=None, mode='private'):
    """
    Install apps

    Keyword argument:
        mode -- level of privacy of the app (public|protected|private)
        domain
        app -- App to install
        path
        label

    """
    # TODO: Virer la règle "default" lemon
    # TODO: check path and url_to_(un)protect pattern

    with YunoHostLDAP() as yldap:


        ##########################################
        # Check if App location is available     #
        ##########################################

        if path[len(path)-1:] != '/':
            path = path + '/'

        apps_map = app_map()

        if lvl(apps_map, domain, path):
            raise YunoHostError(1, _("An app is already installed on this location"))

        if lvl(apps_map, domain):
            for app_path, v in apps_map[domain].items():
                if app_path in path and app_path.count('/') < path.count('/'):
                    raise YunoHostError(1, _("Unable to install app at this location"))


        ##########################################
        # Fetch or extract sources               #
        ##########################################

        try: os.listdir(install_tmp)
        except OSError: os.makedirs(install_tmp)

        if app in app_list(raw=True) or ('@' in app) or ('http://' in app) or ('https://' in app):
            manifest = _fetch_app_from_git(app)
        else:
            manifest = _extract_app_from_file(app)

        if path != '/' and lvl(manifest, 'yunohost', 'webapp', 'domain_root_only') and is_true(manifest['yunohost']['domain_root_only']):
            raise YunoHostError(1, _("App must be installed to domain root"))


        #########################################
        # Define App ID & path                  #
        #########################################

        if not lvl(manifest, 'yunohost', 'uid') or '__' in manifest['yunohost']['uid']:
            raise YunoHostError(22, _("App uid is invalid"))

        is_web = lvl(manifest, 'yunohost', 'webapp')

        instance_number = _installed_instance_number(manifest['yunohost']['uid'], last=True) + 1
        if instance_number > 1:
            if not lvl(manifest, 'yunohost', 'multi_instance') or not is_true(manifest['yunohost']['multi_instance']):
                raise YunoHostError(1, _("App is already installed"))


        unique_app_id = manifest['yunohost']['uid'] +'__'+ str(instance_number)
        app_final_path = apps_path +'/'+ unique_app_id
        script_var_dict = {
            'APP_DIR': app_tmp_folder,
            'APP_FINAL_DIR': app_final_path,
            'APP_ID': unique_app_id
        }

        if is_web:
            script_var_dict.update({
                'APP_DOMAIN': domain,
                'APP_PATH': path
            })


        #########################################
        # Install dependencies                  #
        #########################################

        if lvl(manifest, 'dependencies'):
            _install_app_dependencies(manifest['dependencies'])


        #########################################
        # Create and init DB                    #
        #########################################

        if lvl(manifest, 'yunohost', 'webapp', 'db'):
            db_user = random_password(10)
            db_pwd  = random_password(12)
            script_var_dict.update({
                'DB_USER': db_user,
                'DB_PWD': db_pwd,
                'DB_NAME': db_user
            })

            _init_app_db(db_user, db_pwd, manifest['yunohost']['webapp']['db'])


        #########################################
        # Execute App install script            #
        #########################################

        if lvl(manifest, 'yunohost', 'script_path'):
            _exec_app_script(step='install', path=app_tmp_folder +'/'+ manifest['yunohost']['script_path'], var_dict=script_var_dict, app_type=manifest['type'])


        #########################################
        # Specifically configure lemon & apache #
        #########################################

        if is_web:
            domain_add([domain])


            #############
            # LemonLDAP #
            #############

            if mode == 'private':
                lemon_mode = 'accept'
            elif mode == 'protected' and lvl(manifest, 'yunohost', 'webapp', 'access_control', 'can_be_protected') and is_true(manifest['yunohost']['webapp']['access_control']['can_be_protected']):
                lemon_mode = 'unprotect'
            elif mode == 'public' and lvl(manifest, 'yunohost', 'webapp', 'access_control', 'can_be_public') and is_true(manifest['yunohost']['webapp']['access_control']['can_be_public']):
                lemon_mode = 'skip'
            else:
                raise YunoHostError(22, _("Invalid privacy mode"))

            lemon_configuration({
                ('locationRules', domain, '(?#'+ unique_app_id +'Z)^'+ path ): lemon_mode
            })

            ##########
            # Apache #
            ##########
			
            if lvl(manifest,'yunohost','webapp','custom_apache_conf'):
                os.system('mv '+app_tmp_folder+'/'+manifest['yunohost']['webapp']['custom_apache_conf']+' '+a2_settings_path +'/'+ domain +'.d/'+ unique_app_id +'.app.conf')
            else:
                a2_conf_lines = [ 'Alias '+ path +' '+ app_final_path + manifest['launch_path'] ]
                if path != '/':
                    a2_conf_lines.append('Alias '+ path[:len(path)-1] +' '+ app_final_path + manifest['launch_path'])

                a2_conf_lines.append('<Directory '+ app_final_path +'>')

                if lvl(manifest, 'yunohost', 'webapp', 'language') and manifest['yunohost']['webapp']['language'] == 'php':
                    for line in open(a2_template_path +'/php.conf'): a2_conf_lines.append(line.rstrip())

                a2_conf_lines.append('</Directory>')

                with open(a2_settings_path +'/'+ domain +'.d/'+ unique_app_id +'.app.conf', 'w') as a2_conf:
                    for line in a2_conf_lines:
                        a2_conf.write(line + '\n')		


        #########################################
        # Copy files to the right final place   #
        #########################################

        try: os.listdir(apps_path)
        except OSError: os.makedirs(apps_path)

        # TMP: Remove old application
        # if os.path.exists(app_final_path): shutil.rmtree(app_final_path)

        os.system('cp -a "'+ app_tmp_folder +'" "'+ app_final_path +'"')

        if is_web:
            if manifest['type'] != 'privileged' and manifest['type'] != 'certified':
                os.system('chown -R www-data: "'+ app_final_path +'"')
            os.system('service apache2 reload')
        shutil.rmtree(app_final_path + manifest['yunohost']['script_path'])


        #########################################
        # Write App settings                    #
        #########################################

        app_setting_path = apps_setting_path +'/'+ unique_app_id

        # TMP: Remove old settings
        if os.path.exists(app_setting_path): shutil.rmtree(app_setting_path)
        os.makedirs(app_setting_path)

        yaml_dict = {
            'uid': manifest['yunohost']['uid'],
            'instance' : instance_number,
            'install_time': int(time.time()),
            'mode': mode,
        }
        if is_web:
            yaml_dict.update({
                'domain': domain,
                'path': path,
            })

            if lvl(manifest, 'yunohost', 'webapp', 'db'):
                yaml_dict.update({
                    'db_pwd': db_pwd,
                    'db_user': db_user
                })
            if label: yaml_dict['label'] = label
            else: yaml_dict['label'] = manifest['name']

        with open(app_setting_path +'/app_settings.yml', 'w') as f:
            yaml.safe_dump(yaml_dict, f, default_flow_style=False)
            win_msg(_("App setting file created"))

        if lvl(manifest, 'yunohost', 'script_path'):
            os.system('cp -a "'+ app_tmp_folder +'/'+ manifest['yunohost']['script_path'] +'" '+ app_setting_path)

        shutil.rmtree(app_tmp_folder)
        os.system('mv "'+ app_final_path +'/manifest.webapp" '+ app_setting_path)

        if os.system('chmod 400 -R '+ app_setting_path) != 0:
            raise YunoHostError(22, _("Error during permission setting"))


        #########################################
        # So much win                           #
        #########################################

        win_msg(_("Installation complete"))


def app_remove(app, instance=[]):
    """
    Remove app

    Keyword argument:
        app -- App(s) to delete
        instance -- App instance number to delete

    """
    lemon_conf_lines = {}

    if not instance:
        instance = _installed_instance_number(app)

    for number in instance:
        number = str(number)
        unique_app_id = app +'__'+ number
        app_final_path = apps_path +'/'+ unique_app_id
        app_dict = app_info(app, instance=number, raw=True)
        app_settings = app_dict['settings']
        manifest = app_dict['manifest']
        is_web = lvl(manifest, 'yunohost', 'webapp')
        has_db = lvl(manifest, 'yunohost', 'webapp', 'db')

        script_var_dict = {
            'APP_DIR': apps_path +'/'+ unique_app_id,
            'APP_ID': unique_app_id
        }

        if lvl(manifest, 'dependencies'):
            #TODO: _remove_app_dependencies(manifest['dependencies'])
            pass

        if lvl(manifest, 'yunohost', 'script_path'):
            _exec_app_script(step='remove', path=app_tmp_folder +'/'+ manifest['yunohost']['script_path'], var_dict=script_var_dict, app_type=manifest['type'])

        if is_web:
            with open(lemon_tmp_conf, 'w') as lemon_conf:
                hash = "$tmp->{'locationRules'}->{'"+ app_settings['domain'] +"'}"
                lemon_conf.write("foreach my $key (keys %{ "+ hash +" }) { delete "+ hash +"{$key} if $key =~ /"+ app_settings['uid'] +"/; }" + '\n')

            os.system('/usr/share/lemonldap-ng/bin/lmYnhMoulinette')
            try:
                os.remove(a2_settings_path +'/'+ app_settings['domain'] +'.d/'+ unique_app_id +'.app.conf')
            except OSError:
                pass

        if has_db:
            mysql_root_pwd = open('/etc/yunohost/mysql').read().rstrip()
            mysql_command = 'mysql -u root -p'+ mysql_root_pwd +' -e "REVOKE ALL PRIVILEGES ON '+ app_settings['db_user'] +'.* FROM \''+ app_settings['db_user'] +'\'@localhost ; DROP USER \''+ app_settings['db_user'] +'\'@localhost; DROP DATABASE '+ app_settings['db_user'] +' ;"'
            os.system(mysql_command)

        try:
            shutil.rmtree(apps_setting_path +'/'+ unique_app_id)
            shutil.rmtree(apps_path +'/'+ unique_app_id)
        except OSError:
            pass

        win_msg(_("App removed: ")+ unique_app_id)

    if is_web:
        lemon_configuration(lemon_conf_lines)


def app_addaccess(apps, users):
    """
    Grant access right to users (everyone by default)

    Keyword argument:
        users
        apps

    """
    if not isinstance(users, list): users = [users]
    if not isinstance(apps, list): apps = [apps]

    installed_apps = os.listdir(apps_setting_path)

    lemon_conf_lines = {}

    for installed_app in installed_apps:
        for app in apps:
            if '__' not in app:
                app = app + '__1'

            if app == installed_app:
                with open(apps_setting_path + installed_app +'/app_settings.yml') as f:
                    app_settings = yaml.load(f)

                if app_settings['mode'] == 'private':
                    if 'allowed_users' in app_settings:
                        new_users = app_settings['allowed_users']
                    else:
                        new_users = ''

                    for allowed_user in users:
                        if allowed_user not in new_users.split(' '):
                            try:
                                user_info(allowed_user)
                            except YunoHostError:
                                continue
                            new_users = new_users +' '+ allowed_user

                    app_settings['allowed_users'] = new_users.strip()
                    with open(apps_setting_path + installed_app +'/app_settings.yml', 'w') as f:
                        yaml.safe_dump(app_settings, f, default_flow_style=False)
                        win_msg(_("App setting file updated"))

                    lemon_conf_lines[('locationRules', app_settings['domain'], '(?#'+ installed_app +'Z)^'+ app_settings['path'] )] = 'grep( /^$uid$/, qw('+ new_users.strip() +'))'

    lemon_configuration(lemon_conf_lines)


def app_removeaccess(apps, users):
    """
    Revoke access right to users (everyone by default)

    Keyword argument:
        users
        apps

    """
    if not isinstance(users, list): users = [users]
    if not isinstance(apps, list): apps = [apps]

    installed_apps = os.listdir(apps_setting_path)

    lemon_conf_lines = {}

    for installed_app in installed_apps:
        for app in apps:
            new_users = ''
            if '__' not in app:
                app = app + '__1'

            if app == installed_app:
                with open(apps_setting_path + installed_app +'/app_settings.yml') as f:
                    app_settings = yaml.load(f)

                if app_settings['mode'] == 'private':
                    if 'allowed_users' in app_settings:
                        for allowed_user in app_settings['allowed_users'].split(' '):
                            if allowed_user not in users:
                                new_users = new_users +' '+ allowed_user

                        app_settings['allowed_users'] = new_users.strip()
                        with open(apps_setting_path + installed_app +'/app_settings.yml', 'w') as f:
                            yaml.safe_dump(app_settings, f, default_flow_style=False)
                            win_msg(_("App setting file updated"))

                        lemon_conf_lines[('locationRules', app_settings['domain'], '(?#'+ installed_app +'Z)^'+ app_settings['path'] )] = 'grep( /^$uid$/, qw('+ new_users.strip() +'))'

    lemon_configuration(lemon_conf_lines)


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
        with open(app_tmp_folder + '/manifest.webapp') as json_manifest:
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
            with open(app_tmp_folder + '/manifest.webapp') as json_manifest:
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


def _install_app_dependencies(dep_dict):
    """
    Install debian, npm, gem, pip and pear dependencies of the app

    Keyword arguments:
        dep_dict -- Dict of dependencies from the manifest

    """
    if ('debian' in dep_dict) and (len(dep_dict['debian']) > 0):
        #os.system('apt-get update')
        if os.system('apt-get install -y "'+ '" "'.join(dep_dict['debian']) +'"') != 0:
            raise YunoHostError(1, _("Dependency installation failed: ") + dependency)

    # TODO: Install npm, pip, gem and pear dependencies

    win_msg(_("Dependencies installed"))


def _init_app_db(db_user, db_pwd, db_dict):
    """
    Create database and initialize it with optionnal attached script

    Keyword arguments:
        db_user -- Name of the DB user (also used as database name)
        db_pwd -- Password for the user
        db_dict -- Dict of DB parameters from the manifest

    """
    # Need MySQL DB ?
    if lvl(db_dict, 'has_mysql_db') and is_true(db_dict['has_mysql_db']):
        mysql_root_pwd = open('/etc/yunohost/mysql').read().rstrip()
        mysql_command = 'mysql -u root -p'+ mysql_root_pwd +' -e "CREATE DATABASE '+ db_user +' ; GRANT ALL PRIVILEGES ON '+ db_user +'.* TO \''+ db_user +'\'@localhost IDENTIFIED BY \''+ db_pwd +'\';"'
        if os.system(mysql_command) != 0:
            raise YunoHostError(1, _("MySQL DB creation failed"))
        if lvl(db_dict, 'mysql_init_script'):
            if os.system('mysql -u '+ db_user +' -p'+ db_pwd +' '+ db_user +' < '+ app_tmp_folder + db_dict['mysql_init_script'] +' ;') != 0:
                raise YunoHostError(1, _("MySQL DB init failed"))

    # TODO: PgSQL/MongoDB ?

    win_msg(_("Database initiliazed"))


def _exec_app_script(step, path, var_dict, app_type):
    """
    Execute step user script

    Keyword arguments:
        step -- Name of the script to call regarding the current step (e.g. install|upgrade|remove|etc.)
        path -- Absolute path of the script's directory
        var_dict -- Dictionnary of environnement variable to pass to the script
        app_type -- Decides whether to execute as root or as yunohost-app user (e.g. web|privileged|certified)

    """
    scripts = [ step, step +'.sh', step +'.py' ]

    for script in scripts:
        script_path = path +'/'+ script
        if os.path.exists(script_path):
            st = os.stat(script_path)
            os.chmod(script_path, st.st_mode | stat.S_IEXEC)

            if app_type == 'privileged' or app_type == 'certified':
                user = 'root'
            else:
                user = 'yunohost-app'
                os.system('chown -R '+ user +': '+ app_tmp_folder)

            env_vars = ''
            for key, value in var_dict.items():
                env_vars = env_vars + key + "='"+ value +"' "

            command = 'su - '+ user +' -c "'+ env_vars +' sh '+ path +'/'+ script +'"'
            if os.system(command) == 0:
                win_msg(_("Script executed: ") + script)
            else:
                raise YunoHostError(1, _("Script execution failed: ") + script)

            break


def _installed_instance_number(app, last=False):
    """
    Check if application is installed and return instance number

    Keyword arguments:
        app -- uid of App to check
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

        return number

    else:
        instance_number_list = []
        instances_dict = app_map(app=app, raw=True)
        for key, domain in instances_dict.items():
            for key, path in domain.items():
                instance_number_list.append(path['instance'])

        return sorted(instance_number_list)

