# -*- mode: python -*-
import os
import sys
import gettext
import ldap
import yaml
import json
from twisted.python import log
from twisted.web.server import Site
from twisted.web.resource import IResource
from twisted.web.guard import HTTPAuthSessionWrapper, BasicCredentialFactory
from twisted.internet import reactor, defer
from twisted.cred.portal import IRealm, Portal
from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import IUsernamePassword
from twisted.cred.error import UnauthorizedLogin
from zope.interface import implements
from txrestapi.resource import APIResource
from yunohost import YunoHostError, YunoHostLDAP, str_to_func, colorize, pretty_print_dict, display_error, validate, win, parse_dict

if not __debug__:
    import traceback

gettext.install('YunoHost')

class LDAPHTTPAuth():
    implements (ICredentialsChecker)

    credentialInterfaces = IUsernamePassword,

    def requestAvatarId(self, credentials):
        try:
            if credentials.username != "admin":
                raise YunoHostError(22, _("Invalid username") + ': ' + credentials.username)
            YunoHostLDAP(password=credentials.password)
            return credentials.username

        except Exception as e:
            return defer.fail(UnauthorizedLogin())


class SimpleRealm(object):
    implements(IRealm)

    _api = None

    def __init__(self, api):
        self._api = api

    def requestAvatar(self, avatarId, mind, *interfaces):
        if IResource in interfaces:
            return IResource, self._api, lambda: None
        raise NotImplementedError()

action_dict = {}

def http_exec(request):
    global win
    dict = action_dict[request.method+' '+request.path]
    if 'arguments' in dict: args = dict['arguments']
    else: args = {}
    for arg, params in args.items():
        sanitized_key = arg.replace('-', '_')
        if sanitized_key is not arg:
            args[sanitized_key] = args[arg]
            del args[arg]
            arg = sanitized_key
        if arg[0] == '_':
            if 'nargs' not in params:
                args[arg]['nargs'] = '*'
            if 'full' in params:
                new_key = params['full'][2:]
            else:
                new_key = arg[2:]
	    args[new_key] = args[arg]
            del args[arg]

    try:
        validated_args = {}
        for key, value in request.args.items():
           if key in args:
               # Validate args
               if 'pattern' in args[key]: validate(args[key]['pattern'], value)
               if 'nargs' not in args[key] or ('nargs' != '*' and 'nargs' != '+'): value = value[0]
               if 'action' in args[key] and args[key]['action'] == 'store_true':
                   yes = ['true', 'True', 'yes', 'Yes']
                   value = value in yes 
               validated_args[key] = value

        func = str_to_func(dict['function'])
        with YunoHostLDAP(password=request.getPassword()):
            result = func(**validated_args)
        if result is None:
            result = {}
        if win:
            result['win'] = win
            win = []
        if request.method == 'POST':
            request.setResponseCode(201, 'Created')
        elif request.method == 'DELETE':
            request.setResponseCode(204, 'No Content')
        else:
            request.setResponseCode(200, 'OK')
         
    except YunoHostError, error:
        server_errors = [1, 111, 169]
        client_errors = [13, 17, 22, 87, 122, 125, 167, 168]
        if error.code in client_errors:
            request.setResponseCode(400, 'Bad Request')
        else:
            request.setResponseCode(500, 'Internal Server Error')
            result = { 'error' : error.message }

    request.setHeader('Content-Type', 'application/json')
    return json.dumps(result)


def main():
    global action_dict
    log.startLogging(sys.stdout)
    api = APIResource()

    with open('action_map.yml') as f:
        action_map = yaml.load(f)

    del action_map['general_arguments']
    for category, category_params in action_map.items():
        for action, action_params in category_params['actions'].items():
            if 'help' not in action_params:
                action_params['help'] = ''
            if 'api' not in action_params:
                action_params['api'] = 'GET /'+ category +'/'+ action
            method, path = action_params['api'].split(' ')
            api.register(method, path, http_exec)
            action_dict[action_params['api']] = {
                'function': 'yunohost_'+ category +'.'+ category +'_'+ action,
                'help'    : action_params['help']
            }
            if 'arguments' in action_params: 
                action_dict[action_params['api']]['arguments'] = action_params['arguments']
                
    ldap_auth = LDAPHTTPAuth()
    credentialFactory = BasicCredentialFactory("Restricted Area")
    resource = HTTPAuthSessionWrapper(Portal(SimpleRealm(api), [ldap_auth]), [credentialFactory])
    try:
        with open('/etc/yunohost/installed') as f: pass
    except IOError:
        resource = APIResource()
        resource.register('POST', '/postinstall', http_exec)
    reactor.listenTCP(6767, Site(resource, timeout=None))
    reactor.run()


if __name__ == '__main__':
    main()
