#!/usr/bin/env python
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

"""
    Generate JSON specification files API
"""
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

    resource_list = {
        'apiVersion': '0.1',
        'swaggerVersion': '1.1',
        'basePath': 'http://'+ domain + ':6767',
        'apis': []
    }

    resources = {}

    del action_map['general_arguments']
    for category, category_params in action_map.items():
        if 'category_help' not in category_params: category_params['category_help'] = ''
        resource_path = '/api/'+ category
        resource_list['apis'].append({
            'path': resource_path,
            'description': category_params['category_help']
        })
        resources[category] = {
            'apiVersion': '0.1',
            'swaggerVersion': '1.1',
            'basePath': 'http://'+ domain + ':6767',
            'apis': []
        }

        resources[category]['resourcePath'] = resource_path

        registered_paths = {}

        for action, action_params in category_params['actions'].items():
            if 'action_help' not in action_params:
                action_params['action_help'] = ''
            if 'api' not in action_params:
                action_params['api'] = 'GET /'+ category +'/'+ action

            method, path = action_params['api'].split(' ')
            key_param = ''
            if '{' in path:
                key_param = path[path.find("{")+1:path.find("}")]

            notes = ''
            if str_to_func('yunohost_'+ category +'.'+ category +'_'+ action) is None:
                notes = 'Not yet implemented'

            operation = {
                'httpMethod': method,
                'nickname': category +'_'+ action,
                'summary': action_params['action_help'],
                'notes': notes,
                'errorResponses': []
            }

            if 'arguments' in action_params:
                operation['parameters'] = []
                for arg_name, arg_params in action_params['arguments'].items():
                    if 'help' not in arg_params:
                        arg_params['help'] = ''
                    param_type = 'query'
                    allow_multiple = False
                    required = True
                    allowable_values = None
                    name = arg_name.replace('-', '_')
                    if name[0] == '_':
                        required = False
                        if 'full' in arg_params:
                            name = arg_params['full'][2:]
                        else:
                            name = name[2:]
                        name = name.replace('-', '_')

                    if 'nargs' in arg_params:
                        if arg_params['nargs'] == '*':
                            allow_multiple = True
                            required = False
                        if arg_params['nargs'] == '+':
                            allow_multiple = False
                            required = True
                    else:
                        allow_multiple = False
                    if 'choices' in arg_params:
                        allowable_values = {
                            'valueType': 'LIST',
                            'values': arg_params['choices']
                        }
                    if 'action' in arg_params and arg_params['action'] == 'store_true':
                        allowable_values = {
                            'valueType': 'LIST',
                            'values': ['true', 'false']
                        }

                    if name == key_param:
                        param_type = 'path'
                        required = True
                        allow_multiple = False

                    parameters = {
                        'paramType': param_type,
                        'name': name,
                        'description': arg_params['help'],
                        'dataType': 'string',
                        'required': required,
                        'allowMultiple': allow_multiple
                    }
                    if allowable_values is not None:
                        parameters['allowableValues'] = allowable_values

                    operation['parameters'].append(parameters)


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


    for category, api_dict in resources.items():
        with open(os.getcwd() +'/doc/'+ category +'.json', 'w') as f:
              json.dump(api_dict, f)

    with open(os.getcwd() +'/doc/resources.json', 'w') as f:
        json.dump(resource_list, f)
    

if __name__ == '__main__':
    sys.exit(main())
