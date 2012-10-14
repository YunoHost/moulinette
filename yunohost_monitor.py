# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import psutil
from datetime import datetime, timedelta
from psutil._compat import print_

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
        print_(templ % (part.mountpoint,
                        bytes2human(usage.used),
                        bytes2human(usage.total),
                        bytes2human(usage.free),
                        int(usage.percent)))

def check_cpu():
    print psutil.cpu_percent(interval=1)


def check_memory():
    print getattr(psutil.phymem_usage(), "percent")
    print getattr(psutil.virtmem_usage(), "percent")

def ifconfig():
    output = subprocess.Popen(['ifconfig'], stdout=subprocess.PIPE).communicate()[0]
    if 'HWaddr' in output:
        mac = output[(output.find('HWaddr')+7):(output.find('HWaddr')+24)]
        ip = output[(output.find('Bcast')-15):(output.find('inet')+22)]
        print 'MAC: ' + mac + ' IP: ' +ip
    else:
        print 'MAC NOT FOUND!'

def uptime():
    uptime = datetime.now() - datetime.fromtimestamp(psutil.BOOT_TIME)
    print "Uptime: %s" % (str(uptime).split('.')[0])

def monitor_info(args, connections):
    if args['memory'] == True:
       check_memory()
    elif args['cpu'] == True:
       check_cpu()
    elif args['disk'] == True:
       check_disk()
    elif args['ifconfig'] == True:
       ifconfig() 
    elif args['uptime'] == True:
       uptime()
