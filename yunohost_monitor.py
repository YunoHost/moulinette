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

""" yunohost_monitor.py
"""
import xmlrpclib
import json
import psutil
from urllib import urlopen
from datetime import datetime, timedelta
from yunohost import YunoHostError, win_msg, colorize, validate, get_required_args

s = xmlrpclib.ServerProxy('http://127.0.0.1:61209')

def bytes2human(n):
    symbols = ('K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
    prefix = {}
    for i, s in enumerate(symbols):
        prefix[s] = 1 << (i+1)*10
    for s in reversed(symbols):
        if n >= prefix[s]:
            value = float(n) / prefix[s]
            return '%.1f%s' % (value, s)
    return "%sB" % n

def process_enable(args):
    output = subprocess.Popen(['update-rc.d', args, 'defaults'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    if output.wait() == 0:
        return process_start(args)
        return resultat
    else:
        raise YunoHostError(1, 'Enable : ' + args.title() + " " + _("failure"))

def process_disable(args):
    output = subprocess.Popen(['update-rc.d', args, 'remove'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    if output.wait() == 0:
        return process_stop(args)
        return resultat
    else:
        raise YunoHostError(1, 'Disable : ' + args.title() + " " + _("failure"))

def process_start(args):
    output = subprocess.Popen(['service', args, 'start'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    if output.wait() == 0:
        return { 'Start' : args.title() }
    else:
        raise YunoHostError(1, 'Start : ' + args.title() + " " + _("failure"))

def process_stop(args):
    output = subprocess.Popen(['service', args, 'stop'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    if output.wait() == 0:
        return { 'Stop' : args.title() }
    else:
        raise YunoHostError(1, 'Stop : ' + args.title() + " " + _("failure"))

def process_check(args):
    ip = public()['Public IP']
    output = os.system('/usr/lib/nagios/plugins/check_tcp -H localhost -p' + args  + ' > /dev/null')
    if output == 0:
        output = os.system('/usr/lib/nagios/plugins/check_tcp -H ' + ip + ' -p' + args  + ' > /dev/null')
        if output == 0:
            return { 'Port' : args + " " + _("is open") }
        else:
            return { 'Warning' : args + " " + _("is closed in your box") }
    else:
        raise YunoHostError(1, args + " " + _("is closed") )


def monitor_info(memory=False, cpu=False, disk=False, ifconfig=False, uptime=False, public=False):

    if memory:
        return json.loads(s.getMem())

    elif cpu:
        return json.loads(s.getLoad())

    elif ifconfig:
        # TODO: c'est pas ifconfig ça ;)
        result = {}
        for k, fs in enumerate(json.loads(s.getNetwork())):
            interface = fs['interface_name']
            del fs['interface_name']
            result[interface] = fs
        return result

    elif disk:
        result = {}
        for k, fs in enumerate(json.loads(s.getFs())):
            if fs['fs_type'] != 'tmpfs' and fs['fs_type'] != 'rpc_pipefs':
                mnt_point = str(fs['mnt_point'])
                del fs['mnt_point']
                result[mnt_point] = fs
        return result

    elif uptime:
        uptime_value = (str(datetime.now() - datetime.fromtimestamp(psutil.BOOT_TIME)).split('.')[0])
        return { 'Uptime' : uptime_value }

    elif public:
        try:
            ip = str(urlopen('http://ip.yunohost.org').read())
        except:
            raise YunoHostError(1, _("No connection") )
        return { 'Public IP' : ip }

    else:
        raise YunoHostError(1, _('No arguments provided'))

def monitor_process(enable=None, disable=None, start=None, stop=None, check=None, info=False):
    if enable:
        return process_enable(enable)
    elif disable:
        return process_disable(disable)
    elif start:
        return process_start(start)
    elif stop:
        return process_stop(stop)
    elif check:
        return process_check(check)
    elif info:
        return json.loads(s.getProcessCount())
