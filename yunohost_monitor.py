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
import re
import json
import time
import psutil
import calendar
import subprocess
import xmlrpclib
import os.path
import cPickle as pickle
from urllib import urlopen
from datetime import datetime, timedelta
from yunohost import YunoHostError

glances_uri = 'http://127.0.0.1:61209'
stats_path  = '/var/lib/yunohost/stats'

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
        m = re.search(r'([a-z]+[0-9]*)[ ]+(\/\S*)', d) # Extract device name (1) and its mountpoint (2)
        if m and (mountpoint is None or m.group(2) == mountpoint):
            (dn, dm) = (m.group(1), m.group(2))
            devices[dn] = dm
            result[dn] = {} if len(units) > 1 else []
            result_dname = dn if mountpoint is not None else None
    if len(devices) == 0:
        if mountpoint is None:
            raise YunoHostError(1, _("No mounted block device found"))
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
            for dname in devices.keys():
                if len(units) > 1 and u not in result[dname]:
                    result[dname][u] = 'not-available'
                elif len(result[dname]) == 0:
                    result[dname] = 'not-available'
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

            gateway = None
            output = subprocess.check_output('ip route show'.split())
            m = re.search('default via (.*) dev ([a-z]+[0-9]?)', output)
            if m:
                gateway = _extract_inet(m.group(1), True)

            result[u] = {
                'public_ip': p_ip,
                'local_ip': l_ip,
                'gateway': gateway
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


def monitor_updatestats(period):
    """
    Update monitored statistics

    Keyword argument:
        period -- Time period to update (day, week, month)

    """
    if period not in ['day', 'week', 'month']:
        raise YunoHostError(22, _("Invalid period"))

    stats = _retrieve_stats(period)
    if not stats:
        stats = { 'disk': {}, 'network': {}, 'system': {}, 'timestamp': [] }

    monitor = None
    # Get monitored stats
    if period == 'day':
        monitor = _monitor_all('day')
    else:
        t = stats['timestamp']
        p = 'day' if period == 'week' else 'week'
        if len(t) > 0:
            monitor = _monitor_all(p, t[len(t) - 1])
        else:
            monitor = _monitor_all(p, 0)
    if not monitor:
        raise YunoHostError(1, _("No monitored statistics to update"))

    stats['timestamp'].append(time.time())

    # Append disk stats
    for dname, units in monitor['disk'].items():
        disk = {}
        # Retrieve current stats for disk name
        if dname in stats['disk'].keys():
            disk = stats['disk'][dname]

        for unit, values in units.items():
            # Continue if unit doesn't contain stats
            if not isinstance(values, dict):
                continue

            # Retrieve current stats for unit and append new ones
            curr = disk[unit] if unit in disk.keys() else {}
            if unit == 'io':
                disk[unit] = _append_to_stats(curr, values, 'time_since_update')
            elif unit == 'filesystem':
                disk[unit] = _append_to_stats(curr, values, ['fs_type', 'mnt_point'])
        stats['disk'][dname] = disk

    # Append network stats
    net_usage = {}
    for iname, values in monitor['network']['usage'].items():
        # Continue if units doesn't contain stats
        if not isinstance(values, dict):
            continue

        # Retrieve current stats and append new ones
        curr = {}
        if 'usage' in stats['network'] and iname in stats['network']['usage']:
            curr = stats['network']['usage'][iname]
        net_usage[iname] = _append_to_stats(curr, values, 'time_since_update')
    stats['network'] = { 'usage': net_usage, 'infos': monitor['network']['infos'] }

    # Append system stats
    for unit, values in monitor['system'].items():
        # Continue if units doesn't contain stats
        if not isinstance(values, dict):
            continue

        # Set static infos unit
        if unit == 'infos':
            stats['system'][unit] = values
            continue

        # Retrieve current stats and append new ones
        curr = stats['system'][unit] if unit in stats['system'].keys() else {}
        stats['system'][unit] = _append_to_stats(curr, values)

    _save_stats(stats, period)


def monitor_showstats(period, date=None):
    """
    Show monitored statistics

    Keyword argument:
        period -- Time period to show (day, week, month)

    """
    if period not in ['day', 'week', 'month']:
        raise YunoHostError(22, _("Invalid period"))

    result = _retrieve_stats(period, date)
    if result is False:
        raise YunoHostError(167, _("Stats file not found"))
    elif result is None:
        raise YunoHostError(1, _("No available stats for the given period"))
    return result


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


def _extract_inet(string, skip_netmask=False):
    """
    Extract IP address (v4 or v6) from a string

    Keyword argument:
        string -- String to search in

    """
    # TODO: Return IPv4 and IPv6 when available
    ip4 = '((25[0-5]|2[0-4]\d|[0-1]?\d?\d)(\.(25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3}'
    ip6 = '((?:[0-9A-Fa-f]{1,4}(?::[0-9A-Fa-f]{1,4})*)?)::((?:[0-9A-Fa-f]{1,4}(?::[0-9A-Fa-f]{1,4})*)?'
    ip4 += '/[0-9]{1,2})' if not skip_netmask else ')'
    ip6 += '/[0-9]{1,2})' if not skip_netmask else ')'

    ip4_prog = re.compile(ip4)
    ip6_prog = re.compile(ip6)

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


def _retrieve_stats(period, date=None):
    """
    Retrieve statistics from pickle file

    Keyword argument:
        period -- Time period to retrieve (day, week, month)
        date -- Date of stats to retrieve

    """
    pkl_file = None

    # Retrieve pickle file
    if date is not None:
        timestamp = calendar.timegm(date)
        pkl_file = '%s/%d_%s.pkl' % (stats_path, timestamp, period)
    else:
        pkl_file = '%s/%s.pkl' % (stats_path, period)
    if not os.path.isfile(pkl_file):
        return False

    # Read file and process its content
    with open(pkl_file, 'r') as f:
        result = pickle.load(f)
    if not isinstance(result, dict):
        return None
    return result


def _save_stats(stats, period, date=None):
    """
    Save statistics to pickle file

    Keyword argument:
        stats -- Stats dict to save
        period -- Time period of stats (day, week, month)
        date -- Date of stats

    """
    pkl_file = None

    # Set pickle file name
    if date is not None:
        timestamp = calendar.timegm(date)
        pkl_file = '%s/%d_%s.pkl' % (stats_path, timestamp, period)
    else:
        pkl_file = '%s/%s.pkl' % (stats_path, period)
    if not os.path.isdir(stats_path):
        os.makedirs(stats_path)

    # Limit stats
    if date is None:
        t = stats['timestamp']
        limit = { 'day': 86400, 'week': 604800, 'month': 2419200 }
        if (t[len(t) - 1] - t[0]) > limit[period]:
            begin = t[len(t) - 1] - limit[period]
            stats = _filter_stats(stats, begin)

    # Write file content
    with open(pkl_file, 'w') as f:
        pickle.dump(stats, f)
    return True


def _monitor_all(period=None, since=None):
    """
    Monitor all units (disk, network and system) for the given period
    If since is None, real-time monitoring is returned. Otherwise, the
    mean of stats since this timestamp is calculated and returned.

    Keyword argument:
        period -- Time period to monitor (day, week, month)
        since -- Timestamp of the stats beginning

    """
    result = { 'disk': {}, 'network': {}, 'system': {} }

    # Real-time stats
    if period == 'day' and since is None:
        result['disk'] = monitor_disk()
        result['network'] = monitor_network()
        result['system'] = monitor_system()
        return result

    # Retrieve stats and calculate mean
    stats = _retrieve_stats(period)
    if not stats:
        return None
    stats = _filter_stats(stats, since)
    if not stats:
        return None
    result = _calculate_stats_mean(stats)

    return result


def _filter_stats(stats, t_begin=None, t_end=None):
    """
    Filter statistics by beginning and/or ending timestamp

    Keyword argument:
        stats -- Dict stats to filter
        t_begin -- Beginning timestamp
        t_end -- Ending timestamp

    """
    if t_begin is None and t_end is None:
        return stats

    i_begin = i_end = None
    # Look for indexes of timestamp interval
    for i, t in enumerate(stats['timestamp']):
        if t_begin and i_begin is None and t >= t_begin:
            i_begin = i
        if t_end and i != 0 and i_end is None and t > t_end:
            i_end = i
    # Check indexes
    if i_begin is None:
        if t_begin and t_begin > stats['timestamp'][0]:
            return None
        i_begin = 0
    if i_end is None:
        if t_end and t_end < stats['timestamp'][0]:
            return None
        i_end = len(stats['timestamp'])
    if i_begin == 0 and i_end == len(stats['timestamp']):
        return stats

    # Filter function
    def _filter(s, i, j):
        for k, v in s.items():
            if isinstance(v, dict):
                s[k] = _filter(v, i, j)
            elif isinstance(v, list):
                s[k] = v[i:j]
        return s

    stats = _filter(stats, i_begin, i_end)
    return stats


def _calculate_stats_mean(stats):
    """
    Calculate the weighted mean for each statistic

    Keyword argument:
        stats -- Stats dict to process

    """
    timestamp = stats['timestamp']
    t_sum = sum(timestamp)
    del stats['timestamp']

    # Weighted mean function
    def _mean(s, t, ts):
        for k, v in s.items():
            if isinstance(v, dict):
                s[k] = _mean(v, t, ts)
            elif isinstance(v, list):
                nums = [ float(x * t[i]) for i, x in enumerate(v) ]
                s[k] = sum(nums) / float(ts)
        return s

    stats = _mean(stats, timestamp, t_sum)
    return stats


def _append_to_stats(stats, monitor, statics=[]):
    """
    Append monitored statistics to current statistics

    Keyword argument:
        stats -- Current stats dict
        monitor -- Monitored statistics
        statics -- List of stats static keys

    """
    if isinstance(statics, str):
        statics = [statics]

    # Appending function
    def _append(s, m, st):
        for k, v in m.items():
            if k in st:
                s[k] = v
            elif isinstance(v, dict):
                if k not in s:
                    s[k] = {}
                s[k] = _append(s[k], v, st)
            else:
                if k not in s:
                    s[k] = []
                if isinstance(v, list):
                    s[k].extend(v)
                else:
                    s[k].append(v)
        return s

    stats = _append(stats, monitor, statics)
    return stats
