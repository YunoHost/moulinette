#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import yaml
import json
import requests
from yunohost import str_to_func

def main():
    """

    """
    with open('action_map.yml') as f:
        action_map = yaml.load(f)

    try:
        with open('/etc/yunohost/current_host', 'r') as f:
            domain = f.readline().rstrip()
    except IOError:
        domain = requests.get('http://ip.yunohost.org').text

    with open('action_map.yml') as f:
        action_map = yaml.load(f)

    base_info = {
        'apiVersion': '0.1',
        'swaggerVersion': '1.1',
        'basePath': 'http://'+ domain + ':6767',
        'apis': []
    }

    resource_list = base_info
    resources = {}

    del action_map['general_arguments']
    for category, category_params in action_map.items():
        if 'category_help' not in category_params: category_params['category_help'] = ''
        resource_path = '/'+ category
        resource_list['apis'].append({
            'path': resource_path,
            'description': category_params['category_help']
        })
        resources[category] = base_info
        resources[category]['resourcePath'] = resource_path

        registered_paths = {}

        for action, action_params in category_params['actions'].items():
            if 'action_help' not in action_params:
                action_params['action_help'] = ''
            if 'api' not in action_params:
                action_params['api'] = 'GET /'+ category +'/'+ action

            method, path = action_params['api'].split(' ')
            path = path.replace('(?P<', '{').replace('>[^/]+)', '}')
            key_param = ''
            if '{' in path:
                key_param = path[path.find("{")+1:path.find("}")]

            notes = ''
            if str_to_func('yunohost_'+ category +'.'+ category +'_'+ action) is None:
                notes = 'Not yet implemented'

            operation = {
                'httpMethod': method,
                'nickname': category +'_'+ action,
                'responseClass': 'container',
                'summary': action_params['action_help'],
                'notes': notes,
                'parameters': [],
                'errorResponses': []
            }

            if 'arguments' in action_params:
                for arg_name, arg_params in action_params['arguments'].items():
                    if 'help' not in arg_params:
                        arg_params['help'] = ''
                    param_type = 'query'
                    allow_multiple = False
                    required = True
                    allowable_values = {}
                    name = arg_name.replace('-', '_')
                    if name[0] == '-':
                        required = False
                        if 'nargs' not in arg_params:
                            allow_multiple = False
                        if 'full' in arg_params:
                            name = arg_params['full'][2:]
                        else:
                            name = arg_params[2:]
                    name = name.replace('-', '_')

                    if name == key_param:
                        param_type = 'path'
                        required = True
                        allow_multiple = False

                    if 'nargs' in arg_params:
                        if arg_params['nargs'] == '*':
                            allow_multiple = True
                            required = False
                        if arg_params['nargs'] == '+':
                            allow_multiple = False
                            required = True
                    if 'choices' in arg_params:
                        allowable_values = {
                            'valueType': 'LIST',
                            'values': arg_params['choices']
                        }
                    if 'action' in arg_params and arg_params['action'] == 'store_true':
                        allowable_values = {
                            'valueType': 'LIST',
                            'values': ['true', 'True', 'yes', 'Yes']
                        }

                    operation['parameters'].append({
                        'paramType': param_type,
                        'name': name,
                        'description': arg_params['help'],
                        'dataType': 'string',
                        'required': required,
                        'allowableValues': allowable_values,
                        'allowMultiple': allow_multiple
                    })


            if path in registered_paths:
                resources[category]['apis'][registered_paths[path]]['operations'].append(operation)
                resources[category]['apis'][registered_paths[path]]['description'] = ''
            else:
                registered_paths[path] = len(resources[category]['apis'])
                resources[category]['apis'].append({
                    'path': path,
                    'description': action_params['action_help'],
                    'operations': [operation]
                })


    #for category, api_dict in resources.items():
    #    with open(os.getcwd() +'/doc/'+ category +'.json', 'w') as f:
    #          json.dump(api_dict, f)

    #with open(os.getcwd() +'/doc/resources.json', 'w') as f:
    #    json.dump(resource_list, f)
    #

    print resource_list

if __name__ == '__main__':
    sys.exit(main())
