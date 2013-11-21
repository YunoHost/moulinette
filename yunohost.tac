# -*- mode: python -*-
import os
import sys
import gettext
import ldap
import yaml
import json

sys.path.append('/usr/share/pyshared')

from twisted.python.log import ILogObserver, FileLogObserver, startLogging, msg
from twisted.python.logfile import DailyLogFile
from twisted.web.server import Site, http
from twisted.internet import reactor
from twisted.application import internet,service
from txrestapi.resource import APIResource
from yunohost import YunoHostError, YunoHostLDAP, str_to_func, colorize, pretty_print_dict, display_error, validate, win, parse_dict
import yunohost

if not __debug__:
    import traceback

gettext.install('YunoHost')

dev = False
installed = True
action_dict = {}
api = APIResource()

def http_exec(request, **kwargs):
    global installed

    request.setHeader('Access-Control-Allow-Origin', '*') # Allow cross-domain requests
    request.setHeader('Content-Type', 'application/json') # Return JSON anyway

    # Return OK to 'OPTIONS' xhr requests
    if request.method == 'OPTIONS':
        request.setResponseCode(200, 'OK')
        request.setHeader('Access-Control-Allow-Headers', 'Authorization, Content-Type')
        request.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        return ''

    # Simple HTTP auth
    elif installed:
        authorized = request.getUser() == 'admin'
        pwd = request.getPassword()
        if dev and 'api_key' in request.args:
            pwd = request.args['api_key'][0]
            authorized = True
        if authorized:
            try: YunoHostLDAP(password=pwd)
            except YunoHostError: authorized = False
        if not authorized:
            request.setResponseCode(401, 'Unauthorized')
            request.setHeader('Access-Control-Allow-Origin', '*')
            request.setHeader('www-authenticate', 'Basic realm="Restricted Area"')
            return 'Unauthorized'

    path = request.path
    if request.method == 'PUT':
        given_args = http.parse_qs(request.content.read(), 1)
    else:
        given_args = request.args
    if kwargs:
       for k, v in kwargs.iteritems():
           dynamic_key = path.split('/')[-1]
           path = path.replace(dynamic_key, '{'+ k +'}')
           given_args[k] = [v]

    #msg(given_args)
    # Sanitize arguments
    dict = action_dict[request.method +' '+ path]
    if 'arguments' in dict: possible_args = dict['arguments']
    else: possible_args = {}
    for arg, params in possible_args.items():
        sanitized_key = arg.replace('-', '_')
        if sanitized_key is not arg:
            possible_args[sanitized_key] = possible_args[arg]
            del possible_args[arg]
            arg = sanitized_key
        if arg[0] == '_':
            if 'nargs' not in params:
                possible_args[arg]['nargs'] = '*'
            if 'full' in params:
                new_key = params['full'][2:]
            else:
                new_key = arg[2:]
            new_key = new_key.replace('-', '_')
	    possible_args[new_key] = possible_args[arg]
            del possible_args[arg]

    try:

        # Validate arguments
        validated_args = {}
        for key, value in given_args.items():
           if key in possible_args:
               # Validate args
               if 'pattern' in possible_args[key]:
                   validate(possible_args[key]['pattern'], value)
               if 'nargs' not in possible_args[key] or ('nargs' != '*' and 'nargs' != '+'):
                   value = value[0]
               if 'choices' in possible_args[key] and value not in possible_args[key]['choices']:
                   raise YunoHostError(22, _('Invalid argument') + ' ' + value)
               if 'action' in possible_args[key] and possible_args[key]['action'] == 'store_true':
                   yes = ['true', 'True', 'yes', 'Yes']
                   value = value in yes
               validated_args[key] = value

        func = str_to_func(dict['function'])
        if func is None:
            raise YunoHostError(168, _('Function not yet implemented : ') + dict['function'].split('.')[1])

        # Execute requested function
        try:
            with open('/var/run/yunohost.pid', 'r'):
                raise YunoHostError(1, _("A YunoHost command is already running"))
        except IOError:
            if dict['function'].split('.')[1] != 'tools_postinstall':
                with open('/var/run/yunohost.pid', 'w') as f:
                    f.write('ldap')
                    os.system('chmod 400 /var/run/yunohost.pid')
            with open('/etc/yunohost/passwd', 'w') as f:
                f.write(request.getPassword())
                os.system('chmod 400 /etc/yunohost/passwd')
            try:
                result = func(**validated_args)
            except KeyboardInterrupt, EOFError:
                raise YunoHostError(125, _("Interrupted"))
            finally:
                try:
                    os.remove('/etc/yunohost/passwd')
                    os.remove('/var/run/yunohost.pid')
                except: pass
        if result is None:
            result = {}
        if len(yunohost.win) > 0:
            result['win'] = yunohost.win
            yunohost.win = []

        # Build response
        if request.method == 'POST':
            request.setResponseCode(201, 'Created')
            if not installed:
                installed = True
        elif request.method == 'DELETE':
            request.setResponseCode(204, 'No Content')
        else:
            request.setResponseCode(200, 'OK')

    except YunoHostError, error:

        # Set response code with function's raised code
        server_errors = [1, 111, 168, 169]
        client_errors = [13, 17, 22, 87, 122, 125, 167]
        if error.code in client_errors:
            request.setResponseCode(400, 'Bad Request')
        else:
            request.setResponseCode(500, 'Internal Server Error')

        result = { 'error' : error.message }

    return json.dumps(result)

def api_doc(request):
    request.setHeader('Access-Control-Allow-Origin', '*') # Allow cross-domain requests
    request.setHeader('Content-Type', 'application/json') # Return JSON anyway

    # Return OK to 'OPTIONS' xhr requests
    if request.method == 'OPTIONS':
        request.setResponseCode(200, 'OK')
        request.setHeader('Access-Control-Allow-Headers', 'Authorization')
        return ''

    if request.path == '/api':
        with open('doc/resources.json') as f:
            return f.read()

    category = request.path.split('/')[2]
    try:
        with open('doc/'+ category +'.json') as f:
            return f.read()
    except IOError:
        return ''

def favicon(request):
    request.setHeader('Access-Control-Allow-Origin', '*') # Allow cross-domain requests
    request.setResponseCode(404, 'Not Found')
    return ''

def is_installed(request):
    request.setHeader('Access-Control-Allow-Origin', '*') # Allow cross-domain requests
    request.setResponseCode(200, 'OK')
    return json.dumps({ 'installed': installed })

def main():
    global action_dict
    global api
    global installed

    # Generate API doc
    os.system('python ./generate_api_doc.py')

    # Register API doc service
    api.register('ALL', '/api', api_doc)

    # favicon.ico error
    api.register('ALL', '/favicon.ico', favicon)

    # Load & parse yaml file
    with open('action_map.yml') as f:
        action_map = yaml.load(f)

    # Register only postinstall action if YunoHost isn't completely set up
    try:
        with open('/etc/yunohost/installed') as f: pass
    except IOError:
        installed = False
        api.register('POST', '/postinstall', http_exec)
        api.register('OPTIONS', '/postinstall', http_exec)
        action_dict['POST /postinstall'] = {
            'function'  : 'yunohost_tools.tools_postinstall',
            'help'      : 'Execute post-install',
            'arguments' : action_map['tools']['actions']['postinstall']['arguments']
        }
    else:
        del action_map['general_arguments']
        for category, category_params in action_map.items():
            api.register('ALL', '/api/'+ category, api_doc)
            for action, action_params in category_params['actions'].items():
                if 'action_help' not in action_params:
                    action_params['action_help'] = ''
                if 'api' not in action_params:
                    action_params['api'] = 'GET /'+ category +'/'+ action
                method, path = action_params['api'].split(' ')
                # Register route
                if '{' in path:
                    path = path.replace('{', '(?P<').replace('}', '>[^/]+)')
                api.register(method, path, http_exec)
                api.register('OPTIONS', path, http_exec)
                action_dict[action_params['api']] = {
                    'function': 'yunohost_'+ category +'.'+ category +'_'+ action,
                    'help'    : action_params['action_help']
                }
                if 'arguments' in action_params:
                    action_dict[action_params['api']]['arguments'] = action_params['arguments']

    api.register('ALL', '/installed', is_installed)



if __name__ == '__main__':
    if '--dev' in sys.argv:
        dev = True
        startLogging(sys.stdout)
    else:
        startLogging(open('/var/log/yunohost.log', 'a+')) # Log actions to file
    main()
    reactor.listenTCP(6787, Site(api, timeout=None))
    reactor.run()
else:
    application = service.Application("YunoHost API")
    logfile = DailyLogFile("yunohost.log", "/var/log")
    application.setComponent(ILogObserver, FileLogObserver(logfile).emit)
    main()
    internet.TCPServer(6787, Site(api, timeout=None)).setServiceParent(application)
