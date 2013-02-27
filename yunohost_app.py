# -*- coding: utf-8 -*-

import os
import sys
import json
import shutil
import stat
import yaml
import time
from yunohost import YunoHostError, YunoHostLDAP, win_msg, random_password
from yunohost_domain import domain_list, domain_add

repo_path        = '/var/cache/yunohost/repo'
apps_path        = '/usr/share/yunohost/apps'
apps_setting_path= '/etc/yunohost/apps/'
install_tmp      = '/tmp/yunohost/install'
app_tmp_folder   = install_tmp + '/from_file'

def app_listlists():
    """
    List fetched lists

    Returns:
        Dict of lists

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
    Fetch application list

    Keyword arguments:
        url -- Custom list URL
        name -- Name of the app list

    Returns:
        True | YunoHostError

    """
    # Create app path if not exists
    try: os.listdir(repo_path)
    except OSError: os.makedirs(repo_path)

    if not url:
        url = 'http://fapp.yunohost.org/app/list/raw'
        name = "fapp"
    else:
        if not name: raise YunoHostError(22, _("You must indicate a name for your custom list"))

    if os.system('wget "'+ url +'" -O "'+ repo_path +'/'+ name +'.json"') != 0:
        raise YunoHostError(1, _("List server connection failed"))

    win_msg(_("List successfully fetched"))


def app_removelist(name):
    """
    Remove specified application list

    Keyword arguments:
        name -- Name of the list to remove

    """
    try:
        os.remove(repo_path +'/'+ name + '.json')
    except OSError:
        raise YunoHostError(22, _("Unknown list"))

    win_msg(_("List successfully removed"))


def app_list(offset=None, limit=None, filter=None, raw=False):
    """
    List available applications

    Keyword arguments:
        offset -- App to begin with
        limit -- Number of apps to list
        filter -- Name filter
        raw -- Return the full app_dict

    Returns:
        Dict of apps

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
        i = 0 + offset
        sorted_app_dict = {}
        for sorted_keys in sorted(app_dict.keys())[i:]:
            if i <= limit:
                sorted_app_dict[sorted_keys] = app_dict[sorted_keys]
                i += 1
        for app_id, app_info in sorted_app_dict.items():
            if (filter and ((filter in app_id) or (filter in app_info['manifest']['name']))) or not filter:
                instance_number = _installed_instance_number(app_id)
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

    return list_dict

def app_install(app, domain, path='/', label=None, public=False, protected=True):
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
    is_webapp = False

    with YunoHostLDAP() as yldap:
        try: os.listdir(install_tmp)
        except OSError: os.makedirs(install_tmp)

        # Check if install from file or git
        if "." in app:
            manifest = _extract_app_tarball(app)
        else:
            manifest = _fetch_app_from_git(app)

        if '__' in manifest['yunohost']['uid']:
            raise YunoHostError(22, _("App uid is invalid"))

        instance_number = _installed_instance_number(manifest['yunohost']['uid']) + 1
        if instance_number > 1:
            if not ('multi_instance' in manifest['yunohost'] and (manifest['yunohost']['multi_instance'] == 'yes' or manifest['yunohost']['multi_instance'] == 'true')):
                raise YunoHostError(1, _("App is already installed"))

        unique_app_id = manifest['yunohost']['uid'] +'__'+ str(instance_number)
        script_var_dict = { 'APP_DIR': app_tmp_folder }

        if 'dependencies' in manifest: _install_app_dependencies(manifest['dependencies'])

        if 'webapp' in manifest['yunohost']:

            is_webapp = True

            if 'db' in manifest['yunohost']['webapp']:
                db_user = unique_app_id
                db_pwd  = random_password()
                script_var_dict['DB_USER'] = db_user
                script_var_dict['DB_PWD']  = db_pwd
                script_var_dict['DB_NAME'] = db_user

                _init_app_db(db_user, db_pwd, manifest['yunohost']['webapp']['db'])

        if 'script_path' in manifest['yunohost']:
            _exec_app_script(step='install', path=app_tmp_folder +'/'+ manifest['yunohost']['script_path'], var_dict=script_var_dict, app_type=manifest['type'])

        if is_webapp:
            # Handle domain if ain't already created
            try:
                domain_list(filter="virtualdomain="+ domain)
            except YunoHostError:
                domain_add([domain], web=True)



        #  Copy files to the right place
        try: os.listdir(apps_path)
        except OSError: os.makedirs(apps_path)

        app_final_path = apps_path +'/'+ unique_app_id

        # TMP: Remove old application
        if os.path.exists(app_final_path): shutil.rmtree(app_final_path)

        os.system('cp -a "'+ app_tmp_folder +'" "'+ app_final_path +'"')
        os.system('chown -R www-data: "'+ app_final_path +'"')
        shutil.rmtree(app_final_path + manifest['yunohost']['script_path'])

        app_setting_path = apps_setting_path +'/'+ unique_app_id

        # TMP: Remove old settings
        if os.path.exists(app_setting_path): shutil.rmtree(app_setting_path)
        os.makedirs(app_setting_path)

        if is_webapp:
            yaml_dict = {
                'uid' : manifest['yunohost']['uid'],
                'instance' : instance_number,
                'last_update': manifest['lastUpdate'],
                'install_time': int(time.time()),
                'name': manifest['name'],
                'public': public,
                'protected': protected,
                'domain': domain,
                'path': path,
            }

            if 'db' in manifest['yunohost']['webapp']:
                yaml_dict['db_pwd'] = db_pwd
                yaml_dict['db_user'] = db_user
            if label: yaml_dict['label'] = label
            else: yaml_dict['label'] = manifest['name']

            with open(app_setting_path +'/app_setting.yml', 'w') as f:
                yaml.safe_dump(yaml_dict, f, default_flow_style=False)
                win_msg(_("App setting file created"))

        if 'script_path' in manifest['yunohost']:
            os.system('cp -a "'+ app_tmp_folder +'/'+ manifest['yunohost']['script_path'] +'" '+ app_setting_path)
            shutil.rmtree(app_tmp_folder)

        if os.system('chmod 400 -R '+ app_setting_path) == 0:
            win_msg(_("Installation complete"))
        else:
            raise YunoHostError(22, _("Error during permission setting"))


def _extract_app_tarball(path):
    """
    Unzip or untar application tarball in app_tmp_folder

    Keyword arguments:
        path -- Path of the tarball

    Returns:
        Dict manifest

    """
    if os.path.exists(app_tmp_folder): shutil.rmtree(app_tmp_folder)
    os.makedirs(app_tmp_folder)
    if ".zip" in path:
        extract_result = os.system('cd '+ os.getcwd()  +' && unzip '+ path +' -d '+ app_tmp_folder)
    elif ".tar" in path:
        extract_result = os.system('cd '+ os.getcwd() +' && tar -C '+ app_tmp_folder +' -xf '+ path)
    else:
        extract_result = 1

    if extract_result != 0:
        raise YunoHostError(22, _("Invalid install file"))

    with open(app_tmp_folder + '/manifest.webapp') as json_manifest:
        manifest = json.loads(str(json_manifest.read()))
        manifest['lastUpdate'] = int(time.time())

    win_msg(_("Tarball extracted"))

    return manifest


def _fetch_app_from_git(app):
    """
    Unzip or untar application tarball in app_tmp_folder

    Keyword arguments:
        app -- Path of the tarball

    Returns:
        Dict manifest

    """
    global app_tmp_folder

    app_tmp_folder = install_tmp +'/'+ app
    if os.path.exists(app_tmp_folder): shutil.rmtree(app_tmp_folder)

    app_dict = app_list(raw=True)

    if app in app_dict:
        app_info = app_dict[app]
        app_info['manifest']['lastUpdate'] = app_info['lastUpdate']
    else:
        raise YunoHostError(22, _("App doesn't exists"))

    git_result   = os.system('git clone '+ app_info['git']['url'] +' -b '+ app_info['git']['branch'] +' '+ app_tmp_folder)
    git_result_2 = os.system('cd '+ app_tmp_folder +' && git reset --hard '+ str(app_info['git']['revision']))

    if not git_result == git_result_2 == 0:
        raise YunoHostError(22, _("Sources fetching failed"))

    win_msg(_("Repository fetched"))

    return app_info['manifest']


def _install_app_dependencies(dep_dict):
    """
    Install debian, npm, gem, pip and pear dependencies of the app

    Keyword arguments:
        dep_dict -- Dict of dependencies from the manifest

    """
    if ('debian' in dep_dict) and (len(dep_dict['debian']) > 0):
        #os.system('apt-get update')
        if os.system('apt-get install "'+ '" "'.join(dep_dict['debian']) +'"') != 0:
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
    if 'has_mysql_db' in db_dict and ((db_dict['has_mysql_db'] == 'true') or (db_dict['has_mysql_db'] == 'yes')):
        mysql_root_pwd = open('/etc/yunohost/mysql', 'rb').read().rstrip()
        mysql_command = 'mysql -u root -p'+ mysql_root_pwd +' -e "CREATE DATABASE '+ db_user +' ; GRANT ALL PRIVILEGES ON '+ db_user +'.* TO \''+ db_user +'\'@localhost IDENTIFIED BY \''+ db_pwd +'\';"'
        if os.system(mysql_command) != 0:
            raise YunoHostError(1, _("MySQL DB creation failed"))
        if 'mysql_init_script' in db_dict:
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


def _installed_instance_number(app):
    """
    Check if application is installed and return instance number

    Keyword arguments:
        app -- uid of App to check

    Returns:
        Number of installed instance

    """
    number = 0
    installed_apps = os.listdir(apps_setting_path)
    for installed_app in installed_apps:
        if '__' in installed_app:
            if app == installed_app[:installed_app.index('__')]:
                if int(installed_app[installed_app.index('__') + 2:]) > number:
                    number = int(installed_app[installed_app.index('__') + 2:])

    return number
