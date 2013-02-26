# -*- coding: utf-8 -*-

import os
import sys
import json
import shutil
import stat
from yunohost import YunoHostError, YunoHostLDAP, win_msg, random_password
from yunohost_domain import domain_list, domain_add

repo_path        = '/var/cache/yunohost/repo'
apps_path        = '/usr/share/yunohost/apps'
install_tmp      = '/tmp/yunohost/install'
app_tmp_folder   = install_tmp + '/from_file'
a2_template_path = '/etc/yunohost/apache/templates'
a2_app_conf_path = '/etc/yunohost/apache/domains'
lemon_tmp_conf   = '/tmp/tmplemonconf'

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
                if raw:
                    list_dict[app_id] = app_info
                else:
                    list_dict[app_id] = {
                        'Name': app_info['manifest']['name'],
                        'Version': app_info['manifest']['version'],
                        'Description': app_info['manifest']['description']
                    }

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
    # TODO: Check if the app is already installed

    with YunoHostLDAP() as yldap:
        try: os.listdir(install_tmp)
        except OSError: os.makedirs(install_tmp)

        # Check if install from file or git
        if "." in app:
            manifest = _extract_app_tarball(app)
        else:
            manifest = _fetch_app_from_git(app)

        # TODO: Check if exists another instance

        script_var_dict = { 'APP_DIR': app_tmp_folder }

        if 'dependencies' in manifest: _install_app_dependencies(manifest['dependencies'])

        if 'webapp' in manifest['yunohost']:
            if 'db' in manifest['yunohost']['webapp']:
                db_user = manifest['yunohost']['uid'] # TODO: app.instance
                db_pwd  = random_password()
                script_var_dict['DB_USER'] = db_user
                script_var_dict['DB_PWD']  = db_pwd
                script_var_dict['DB_NAME'] = db_user

                _init_app_db(db_user, db_pwd, manifest['yunohost']['webapp']['db'])

            # Handle domain if ain't already created
            try:
                domain_list(filter="virtualdomain="+ domain)
            except YunoHostError:
                domain_add([domain])

            _apache_config(domain)
            _lemon_config(domain)

        if 'script_path' in manifest['yunohost']:
            _exec_app_script(step='install', path=app_tmp_folder +'/'+ manifest['yunohost']['script_path'], var_dict=script_var_dict, app_type=manifest['type'])

        #  Copy files to the right place
        try: os.listdir(apps_path)
        except OSError: os.makedirs(apps_path)

        app_final_path = apps_path +'/'+ manifest['yunohost']['uid']
        # TMP: Remove old application
        if os.path.exists(app_final_path): shutil.rmtree(app_final_path)
        os.system('cp -a "'+ app_tmp_folder +'" "'+ app_final_path +'"')
        os.system('chown -R www-data: "'+ app_final_path +'"')
        shutil.rmtree(app_final_path + manifest['yunohost']['script_path'])

        # TODO: Create appsettings and chmod it

        # TODO: Remove scripts folder and /tmp files


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


def _apache_config(domain):
    """
    Fill Apache configuration templates

    Keyword arguments:
        domain -- Domain to configure Apache around

    """
    # TMP: remove old conf
    if os.path.exists(a2_app_conf_path +'/'+ domain +'.conf'): os.remove(a2_app_conf_path +'/'+ domain +'.conf')
    if os.path.exists(a2_app_conf_path +'/'+ domain +'.d/'): shutil.rmtree(a2_app_conf_path +'/'+ domain +'.d/')

    try: os.listdir(a2_app_conf_path +'/'+ domain +'.d/')
    except OSError: os.makedirs(a2_app_conf_path +'/'+ domain +'.d/')

    with open(a2_app_conf_path +'/'+ domain +'.conf', 'a') as a2_conf:
        for line in open(a2_template_path +'/template.conf.tmp'):
            line = line.replace('[domain]',domain)
            a2_conf.write(line)

    os.system('cp "'+ a2_template_path + '/fixed.sso.conf" "'+ a2_app_conf_path +'/'+ domain +'.d/"')

    if os.system('service apache2 reload') == 0:
        win_msg(_("Apache configured"))
    else:
        raise YunoHostError(1, _("An error occured during Apache configuration"))

def _lemon_config(domain):
    """
    Configure LemonLDAP

    Keyword arguments:
        domain -- Domain to configure LemonLDAP around

    """
    if os.path.exists(lemon_tmp_conf): os.remove(lemon_tmp_conf)

    lemon_conf_lines = [
       "$tmp->{'exportedHeaders'}->{'"+ domain +"'}->{'Auth-User'} = '$uid';",
       "$tmp->{'exportedHeaders'}->{'"+ domain +"'}->{'Remote-User'} = '$uid';",
       "$tmp->{'exportedHeaders'}->{'"+ domain +"'}->{'Desc'} = '$description';",
       "$tmp->{'exportedHeaders'}->{'"+ domain +"'}->{'Email'} = '$uid';",
       "$tmp->{'exportedHeaders'}->{'"+ domain +"'}->{'Name'} = '$cn';",
       "$tmp->{'exportedHeaders'}->{'"+ domain +"'}->{'Authorization'} = '\"Basic \".encode_base64(\"$uid:$_password\")';",
       "$tmp->{'vhostOptions'}->{'"+ domain +"'}->{'vhostMaintenance'} = 0;",
       "$tmp->{'vhostOptions'}->{'"+ domain +"'}->{'vhostPort'} = -1;",
       "$tmp->{'vhostOptions'}->{'"+ domain +"'}->{'vhostHttps'} = -1;",
       "$tmp->{'locationRules'}->{'"+ domain +"'}->{'default'} = 'accept';",
       "$tmp->{'locationRules'}->{'"+ domain +"'}->{'(?#logout)^/logout'} = 'logout_app_sso https://"+ domain +"/';",
    ]

    with open(lemon_tmp_conf,'a') as lemon_conf:
        for line in lemon_conf_lines:
            lemon_conf.write(line + '\n')

    if os.system('/usr/share/lemonldap-ng/bin/lmYnhMoulinette') == 0:
        win_msg(_("LemonLDAP configured"))
    else:
        raise YunoHostError(1, _("An error occured during LemonLDAP configuration"))
