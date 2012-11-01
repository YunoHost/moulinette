# -*- coding: utf-8 -*-

import os
import sys
import subprocess
from urllib import urlopen
try:
    import psutil
except ImportError:
    sys.stderr.write('Error: Yunohost CLI Require psutil\n')
    sys.stderr.write('apt-get install python-psutil\n')
    sys.exit(1)
try:
    import netifaces
except ImportError:
    sys.stderr.write('Error: Yunohost CLI Require netifaces\n')
    sys.stderr.write('apt-get install python-netifaces\n')
    sys.exit(1)
from datetime import datetime, timedelta
from yunohost import YunoHostError, win_msg, colorize, validate, get_required_args

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

def check_disk():
    templ = "%s,%s/%s,%s,%s"
    for part in psutil.disk_partitions(all=False):
        usage = psutil.disk_usage(part.mountpoint)
    return { _("Partition") : (part.mountpoint, bytes2human(usage.used), bytes2human(usage.total), bytes2human(usage.free), int(usage.percent)) }

def check_cpu():
     return { _("CPU") : psutil.cpu_percent(interval=3) }

def check_memory():
    mem = getattr(psutil.phymem_usage(), "percent")
    swap = getattr(psutil.virtmem_usage(), "percent")
    return { _("Memory") : mem, _("Swap") : swap }

def ifconfig():
    listinterfaces = netifaces.interfaces()[1:]
    for interface in listinterfaces:
        try:
            for link in netifaces.ifaddresses(interface)[netifaces.AF_INET]:
                ip = link['addr']
                for link in netifaces.ifaddresses(interface)[netifaces.AF_LINK]:
                    mac = link['addr']
        except:
            pass
    return { _('IP') : ip, _('MAC') : mac }

def uptime():
    uptime = (str(datetime.now() - datetime.fromtimestamp(psutil.BOOT_TIME)).split('.')[0])
    return { _("Uptime") : uptime }

def public():
    try:
        ip = str(urlopen('http://ip.yunohost.org').read())
    except:
        raise YunoHostError(1, "No connection" )
    return { _("Public IP"): ip }

def processcount():
    processcount = {'total': 0, 'running': 0, 'sleeping': 0}
    process_all = [proc for proc in psutil.process_iter()]
    for proc in process_all:
        try:
            if not proc.is_running():
                try:
                    process_all.remove(proc)
                except Exception:
                    pass
        except psutil.error.NoSuchProcess:
            try:
                self.process_all.remove(proc)
            except Exception:
                pass
        else:
            try:
                processcount[str(proc.status)] += 1
            except psutil.error.NoSuchProcess:
                pass
            except KeyError:
                processcount[str(proc.status)] = 1
            finally:
                processcount['total'] += 1
            try:
                process.append(self.__get_process_stats__(proc))
            except Exception:
                pass
    return { _("Total") : str(processcount['total']), _("Running") :  str(processcount['running']),  _("Sleeping") :  str(processcount['sleeping']) }

def process_enable(args):
    output = subprocess.Popen(['update-rc.d', args, 'defaults'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    if output.wait() == 0:
        resultat = process_start(args)
        return resultat
    else:
        raise YunoHostError(1, _('Enable ' + agrs + ' failure'))

def process_disable(args):
    output = subprocess.Popen(['update-rc.d', args, 'remove'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    if output.wait() == 0:
        resultat = process_stop(args)
        return resultat
    else:
        raise YunoHostError(1, _('Disable ' + agrs + ' failure'))

def process_start(args):
    output = subprocess.Popen(['service', args, 'start'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    if output.wait() == 0:
        return { args.title() + " "  + _('Start') : "OK" }
    else:
        raise YunoHostError(1, _('Start ' + args + ' failure'))

def process_stop(args):
    output = subprocess.Popen(['service', args, 'stop'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    if output.wait() == 0:
        return { args.title() + " "  + _('Stop') : "OK" }
    else:
        raise YunoHostError(1, _('Stop ' + args + ' failure'))

def process_check(args):
    ip = public()['Public IP']
    output = os.system('/usr/lib/nagios/plugins/check_tcp -H localhost -p' + args  + ' > /dev/null')
    if output == 0:
        output = os.system('/usr/lib/nagios/plugins/check_tcp -H ' + ip + ' -p' + args  + ' > /dev/null')
        if output == 0:
            return { _("Port") + " " + args : _("is open") }
        else:
            raise YunoHostError(1, "Port " + args + " is closed in your box" )
    else:
        raise YunoHostError(1, args + " is closed" )


def monitor_info(args):
    if args['memory']:
       resultat = check_memory()
       return resultat
    elif args['cpu']:
        resultat = check_cpu()
        return resultat
    elif args['disk']:
       resultat = check_disk()
       return resultat
    elif args['ifconfig']:
       resultat = ifconfig()
       return resultat
    elif args['uptime']:
       resultat = uptime()
       return resultat
    elif args['public']:
       resultat = public()
       return resultat

def monitor_process(args):
    if args['enable']:
        resultat = process_enable(args['enable'])
        return resultat
    elif args['disable']:
        resultat = process_disable(args['disable'])
        return resultat
    elif args['start']:
        resultat = process_start(args['start'])
        return resultat
    elif args['stop']:
        resultat = process_stop(args['stop'])
        return resultat
    elif args['check']:
        resultat = process_check(args['check'])
        return resultat
    elif args['info']:
        resultat = processcount()
        return resultat
