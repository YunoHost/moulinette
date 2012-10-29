# -*- coding: utf-8 -*-

import os
import sys
from yunohost import YunoHostError, win_msg, colorize, validate, get_required_args

def domain_list(args, connections):
    """
    List YunoHost domains

    Keyword argument:
        args -- Dictionnary of values (can be empty)
        connections -- LDAP connection

    Returns:
        Dict
    """
    yldap = connections['ldap']
    result_dict = {}
    if args['offset']: offset = int(args['offset'])
    else: offset = 0
    if args['limit']: limit = int(args['limit'])
    else: limit = 1000
    if args['filter']: filter = args['filter']
    else: filter = 'virtualdomain=*'

    result = yldap.search('ou=domains,dc=yunohost,dc=org', filter, attrs=['virtualdomain'])
    
    if result and len(result) > (0 + offset) and limit > 0:
        i = 0 + offset
        for domain in result[i:]:
            if i < limit:
                result_dict[str(i)] = domain['virtualdomain']
                i += 1
    else:
        raise YunoHostError(167, _("No domain found"))

    return result_dict


def domain_add(args, connections):
    """
    Add one or more domains

    Keyword argument:
        args -- Dictionnary of values (can be empty)
        connections -- LDAP connection

    Returns:
        Dict
    """
    yldap = connections['ldap']
    attr_dict = { 'objectClass' : ['mailDomain', 'top'] }
    result = []

    args = get_required_args(args, { 'domain' : _('New domain') })
    if not isinstance(args['domain'], list):
        args['domain'] = [ args['domain'] ]
    
    for domain in args['domain']: 
        validate({ domain : r'^([a-zA-Z0-9]{1}([a-zA-Z0-9\-]*[a-zA-Z0-9])*)(\.[a-zA-Z0-9]{1}([a-zA-Z0-9\-]*[a-zA-Z0-9])*)*(\.[a-zA-Z]{1}([a-zA-Z0-9\-]*[a-zA-Z0-9])*)$' })
        yldap.validate_uniqueness({ 'virtualdomain' : domain })
        attr_dict['virtualdomain'] = domain
        if yldap.add('virtualdomain=' + domain + ',ou=domains', attr_dict):
            result.append(domain)
            continue
        else:
            raise YunoHostError(169, _("An error occured during domain creation"))

    win_msg(_("Domain(s) successfully created"))

    return { 'Domains' : result } 


