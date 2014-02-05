# -*- coding: utf-8 -*-

# TODO: Remove permanent debug values
import os

# Path for the the web sessions
session_path = '/var/cache/yunohost/session'

# Path of the actions map definition(s)
actionsmap_path =  os.path.dirname(__file__) +'/../../etc/actionsmap'

# Path for the actions map cache
actionsmap_cache_path = '/var/cache/yunohost/actionsmap'

# Path of the doc in json format
doc_json_path = os.path.dirname(__file__) +'/../../doc'
