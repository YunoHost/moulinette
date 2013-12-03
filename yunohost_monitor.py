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

    Monitoring functions
"""
import os
import re
import json
import yaml
import psutil
import subprocess
import xmlrpclib
from urllib import urlopen
from datetime import datetime, timedelta
from yunohost import YunoHostError, win_msg, colorize, validate, get_required_args

glances_uri = 'http://127.0.0.1:61209'

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
    with open('process.yml', 'r') as f:
        processes = yaml.load(f)

    result = {}
    for process, commands in processes.items():
        if commands['status'] == 'service':
            cmd = "service " + process + " status"
        else:
            cmd = commands['status']

        if os.system(cmd + " > /dev/null 2>&1") == 0:
            result.update({ process : _('Running') })
        else:
            result.update({ process : _('Down') })

    return { 'Status' : result }


def monitor_disk(units=None, mountpoint=None, human_readable=False):
    """
    Monitor disk space and usage

    Keyword argument:
        units -- Unit(s) to monitor
        mountpoint -- Device mountpoint
        human_readable -- Print sizes in human readable format

    """
    glances = _get_glances_api()
    result_dname = None
    result = {}

    if units is None:
        units = ['io', 'filesystem']

    # Get mounted block devices
    devices = {}
    output = subprocess.check_output('lsblk -o NAME,MOUNTPOINT -l -n'.split())
    for d in output.split('\n'):
        m = re.search(r'([a-z]+[0-9]+)[ ]+(\/\S*)', d) # Extract device name (1) and its mountpoint (2)
        if m and (mountpoint is None or m.group(2) == mountpoint):
            (dn, dm) = (m.group(1), m.group(2))
            devices[dn] = dm
            result[dn] = {} if len(units) > 1 else []
            result_dname = dn if mountpoint is not None else None
    if len(devices) == 0:
        raise YunoHostError(1, _("Unknown mountpoint '%s'") % mountpoint)

    # Retrieve monitoring for unit(s)
    for u in units:
        if u == 'io':
            for d in json.loads(glances.getDiskIO()):
                dname = d['disk_name']
                if dname in devices.keys():
                    del d['disk_name']
                    if len(units) > 1:
                        result[dname][u] = d
                    else:
                        d['mnt_point'] = devices[dname]
                        result[dname] = d
        elif u == 'filesystem':
            for d in json.loads(glances.getFs()):
                dmount = d['mnt_point']
                for (dn, dm) in devices.items():
                    # TODO: Show non-block filesystems?
                    if dm != dmount:
                        continue
                    del d['device_name']
                    if human_readable:
                        for i in ['used', 'avail', 'size']:
                            d[i] = _binary_to_human(d[i]) + 'B'
                    if len(units) > 1:
                        result[dn][u] = d
                    else:
                        result[dn] = d
        else:
            raise YunoHostError(1, _("Unknown unit '%s'") % u)

    if result_dname is not None:
        return result[result_dname]
    return result


def monitor_network(units=None, human_readable=False):
    """
    Monitor network interfaces

    Keyword argument:
        units -- Unit(s) to monitor
        human_readable -- Print sizes in human readable format

    """
    glances = _get_glances_api()
    result = {}

    if units is None:
        units = ['usage', 'infos']

    # Get network devices and their addresses
    devices = {}
    output = subprocess.check_output('ip addr show'.split())
    for d in re.split('^(?:[0-9]+: )', output, flags=re.MULTILINE):
        d = re.sub('\n[ ]+', ' % ', d)          # Replace new lines by %
        m = re.match('([a-z]+[0-9]?): (.*)', d) # Extract device name (1) and its addresses (2)
        if m:
            devices[m.group(1)] = m.group(2)

    # Retrieve monitoring for unit(s)
    for u in units:
        if u == 'usage':
            result[u] = {}
            for i in json.loads(glances.getNetwork()):
                iname = i['interface_name']
                if iname in devices.keys():
                    del i['interface_name']
                    if human_readable:
                        for k in i.keys():
                            if k != 'time_since_update':
                                i[k] = _binary_to_human(i[k]) + 'B'
                    result[u][iname] = i
        elif u == 'infos':
            try:
                p_ip = str(urlopen('http://ip.yunohost.org').read())
            except:
                raise YunoHostError(1, _("Public IP resolution failed"))

            l_ip = None
            for name, addrs in devices.items():
                if name == 'lo':
                    continue
                if len(devices) == 2:
                    l_ip = _extract_inet(addrs)
                else:
                    if l_ip is None:
                        l_ip = {}
                    l_ip[name] = _extract_inet(addrs)

            result[u] = {
                'public_ip': p_ip,
                'local_ip': l_ip,
                'gateway': 'TODO'
            }
        else:
            raise YunoHostError(1, _("Unknown unit '%s'") % u)

    if len(units) == 1:
        return result[units[0]]
    return result


def monitor_system(units=None, human_readable=False):
    """
    Monitor system informations and usage

    Keyword argument:
        units -- Unit(s) to monitor
        human_readable -- Print sizes in human readable format

    """
    glances = _get_glances_api()
    result = {}

    if units is None:
        units = ['memory', 'cpu', 'process', 'uptime', 'infos']

    # Retrieve monitoring for unit(s)
    for u in units:
        if u == 'memory':
            ram = json.loads(glances.getMem())
            swap = json.loads(glances.getMemSwap())
            if human_readable:
                for i in ram.keys():
                    if i != 'percent':
                        ram[i] = _binary_to_human(ram[i]) + 'B'
                for i in swap.keys():
                    if i != 'percent':
                        swap[i] = _binary_to_human(swap[i]) + 'B'
            result[u] = {
                'ram': ram,
                'swap': swap
            }
        elif u == 'cpu':
            result[u] = {
                'load': json.loads(glances.getLoad()),
                'usage': json.loads(glances.getCpu())
            }
        elif u == 'process':
            result[u] = json.loads(glances.getProcessCount())
        elif u == 'uptime':
            result[u] = (str(datetime.now() - datetime.fromtimestamp(psutil.BOOT_TIME)).split('.')[0])
        elif u == 'infos':
            result[u] = json.loads(glances.getSystem())
        else:
            raise YunoHostError(1, _("Unknown unit '%s'") % u)

    if len(units) == 1 and type(result[units[0]]) is not str:
        return result[units[0]]
    return result


def monitor_process(enable=None, disable=None, start=None, stop=None, check=False, info=False):
    """
    Check Process

    Keyword argument:
        info -- Process info
        disable -- Disable process
        enable -- Enable process
        start -- Start process
        check -- Check process
        stop -- Stop process

    """
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


def _get_glances_api():
    """
    Retrieve Glances API running on the local server

    """
    try:
        p = xmlrpclib.ServerProxy(glances_uri)
        p.system.methodHelp('getAll')
    except (xmlrpclib.ProtocolError, IOError):
        # TODO: Try to start Glances service
        raise YunoHostError(1, _("Connection to Glances server failed"))

    return p


def _extract_inet(string):
    """
    Extract IP address (v4 or v6) from a string

    Keyword argument:
        string -- String to search in

    """
    # TODO: Return IPv4 and IPv6?
    ip4_prog = re.compile('((25[0-5]|2[0-4]\d|[0-1]?\d?\d)(\.(25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3}/[0-9]{1,2})')
    ip6_prog = re.compile('((?:[0-9A-Fa-f]{1,4}(?::[0-9A-Fa-f]{1,4})*)?)::((?:[0-9A-Fa-f]{1,4}(?::[0-9A-Fa-f]{1,4})*)?/[0-9]{1,2})')

    m = ip4_prog.search(string)
    if m:
        return m.group(1)

    m = ip6_prog.search(string)
    if m:
        return m.group(1)

    return None


def _binary_to_human(n, customary=False):
    """
    Convert bytes or bits into human readable format with binary prefix

    Keyword argument:
        n -- Number to convert
        customary -- Use customary symbol instead of IEC standard

    """
    symbols = ('Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi', 'Yi')
    if customary:
        symbols = ('K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
    prefix = {}
    for i, s in enumerate(symbols):
        prefix[s] = 1 << (i+1)*10
    for s in reversed(symbols):
        if n >= prefix[s]:
            value = float(n) / prefix[s]
            return '%.1f%s' % (value, s)
    return "%s" % n
