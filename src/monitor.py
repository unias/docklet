#!/usr/bin/python3

import subprocess,re,os,etcdlib,psutil
import time,threading,json,traceback,platform

from log import logger

monitor_hosts = {}
monitor_vnodes = {}

workerinfo = {}
workercinfo = {}

class Container_Collector(threading.Thread):

    def __init__(self,test=False):
        threading.Thread.__init__(self)
        self.thread_stop = False
        self.interval = 2
        self.test = test
        self.cpu_last = {}
        self.cpu_quota = {}
        self.mem_quota = {}
        self.cores_num = int(subprocess.getoutput("grep processor /proc/cpuinfo | wc -l"))
        return

    def list_container(self):
        output = subprocess.check_output(["sudo lxc-ls"],shell=True)
        output = output.decode('utf-8')
        containers = re.split('\s+',output)
        return containers

    def get_proc_etime(self,pid):
        fmt = subprocess.getoutput("ps -A -opid,etime | grep '^ *%d' | awk '{print $NF}'" % pid).strip()
        if fmt == '':
            return -1
        parts = fmt.split('-')
        days = int(parts[0]) if len(parts) == 2 else 0
        fmt = parts[-1]
        parts = fmt.split(':')
        hours = int(parts[0]) if len(parts) == 3 else 0
        parts = parts[len(parts)-2:]
        minutes = int(parts[0])
        seconds = int(parts[1])
        return ((days * 24 + hours) * 60 + minutes) * 60 + seconds

    def collect_containerinfo(self,container_name):
        global workercinfo
        output = subprocess.check_output("sudo lxc-info -n %s" % (container_name),shell=True)
        output = output.decode('utf-8')
        parts = re.split('\n',output)
        info = {}
        basic_info = {}
        basic_exist = 'basic_info' in workercinfo[container_name].keys()
        if basic_exist:
            basic_info = workercinfo[container_name]['basic_info']
        for part in parts:
            if not part == '':
                key_val = re.split(':',part)
                key = key_val[0]
                val = key_val[1]
                info[key] = val.lstrip()
        basic_info['Name'] = info['Name']
        basic_info['State'] = info['State']
        #if basic_exist:
         #   logger.info(workercinfo[container_name]['basic_info'])
        if(info['State'] == 'STOPPED'):
            if not 'RunningTime' in basic_info.keys():
                basic_info['RunningTime'] = 0
                basic_info['LastTime'] = 0
            workercinfo[container_name]['basic_info'] = basic_info
            logger.info(basic_info)
            return False
        running_time = self.get_proc_etime(int(info['PID']))
        if basic_exist and 'PID' in workercinfo[container_name]['basic_info'].keys():
            last_time = workercinfo[container_name]['basic_info']['LastTime']
            if not info['PID'] == workercinfo[container_name]['basic_info']['PID']:
                last_time = workercinfo[container_name]['basic_info']['RunningTime']
        else:
            last_time = 0
        basic_info['LastTime'] = last_time
        running_time += last_time
        basic_info['PID'] = info['PID']
        basic_info['IP'] = info['IP']
        basic_info['RunningTime'] = running_time
        workercinfo[container_name]['basic_info'] = basic_info

        cpu_parts = re.split(' +',info['CPU use'])
        cpu_val = cpu_parts[0].strip()
        cpu_unit = cpu_parts[1].strip()
        if not container_name in self.cpu_last.keys():
            confpath = "/var/lib/lxc/%s/config"%(container_name)
            if os.path.exists(confpath):
                confile = open(confpath,'r')
                res = confile.read()
                lines = re.split('\n',res)
                for line in lines:
                    words = re.split('=',line)
                    key = words[0].strip()
                    if key == "lxc.cgroup.memory.limit_in_bytes":
                        self.mem_quota[container_name] = float(words[1].strip().strip("M"))*1000000/1024
                    elif key == "lxc.cgroup.cpu.cfs_quota_us":
                        tmp = int(words[1].strip())
                        if tmp < 0:
                            self.cpu_quota[container_name] = self.cores_num
                        else:
                            self.cpu_quota[container_name] = tmp/100000.0
                quota = {'cpu':self.cpu_quota[container_name],'memory':self.mem_quota[container_name]}
                #logger.info(quota)
                workercinfo[container_name]['quota'] = quota
            else:
                logger.error("Cant't find config file %s"%(confpath))
                return False
            self.cpu_last[container_name] = 0 
        cpu_use = {}
        cpu_use['val'] = cpu_val
        cpu_use['unit'] = cpu_unit
        cpu_usedp = (float(cpu_val)-float(self.cpu_last[container_name]))/(self.cpu_quota[container_name]*self.interval*1.3)
        if(cpu_usedp > 1 or cpu_usedp < 0):
            cpu_usedp = 1
        cpu_use['usedp'] = cpu_usedp
        self.cpu_last[container_name] = cpu_val;
        workercinfo[container_name]['cpu_use'] = cpu_use

        mem_parts = re.split(' +',info['Memory use'])
        mem_val = mem_parts[0].strip()
        mem_unit = mem_parts[1].strip()
        mem_use = {}
        mem_use['val'] = mem_val
        mem_use['unit'] = mem_unit
        if(mem_unit == "MiB"):
            mem_val = float(mem_val) * 1024
        elif (mem_unit == "GiB"):
            mem_val = float(mem_val) * 1024 * 1024
        mem_usedp = float(mem_val) / self.mem_quota[container_name]
        mem_use['usedp'] = mem_usedp
        workercinfo[container_name]['mem_use'] = mem_use
        #print(output)
        #print(parts)
        return True

    def run(self):
        global workercinfo
        global workerinfo
        cnt = 0
        while not self.thread_stop:
            containers = self.list_container()
            countR = 0
            conlist = []
            for container in containers:
                if not container == '':
                    conlist.append(container)
                    if not container in workercinfo.keys():
                        workercinfo[container] = {}
                    try:
                        success= self.collect_containerinfo(container)
                        if(success):
                            countR += 1
                    except Exception as err:
                        logger.warning(traceback.format_exc())
                        logger.warning(err)
            containers_num = len(containers)-1
            concnt = {}
            concnt['total'] = containers_num
            concnt['running'] = countR
            workerinfo['containers'] = concnt
            time.sleep(self.interval)
            if cnt == 0:
                workerinfo['containerslist'] = conlist
            cnt = (cnt+1)%5
            if self.test:
                break
        return

    def stop(self):
        self.thread_stop = True


class Collector(threading.Thread):

    def __init__(self,test=False):
        threading.Thread.__init__(self)
        self.thread_stop = False
        self.interval = 1
        self.test=test
        return

    def collect_meminfo(self):
        meminfo = psutil.virtual_memory()
        memdict = {}
        memdict['total'] = meminfo.total/1024
        memdict['used'] = meminfo.used/1024
        memdict['free'] = meminfo.free/1024
        memdict['buffers'] = meminfo.buffers/1024
        memdict['cached'] = meminfo.cached/1024
        memdict['percent'] = meminfo.percent
        #print(output)
        #print(memparts)
        return memdict

    def collect_cpuinfo(self):
        cpuinfo = psutil.cpu_times_percent(interval=1,percpu=False)
        cpuset = {}
        cpuset['user'] = cpuinfo.user
        cpuset['system'] = cpuinfo.system
        cpuset['idle'] = cpuinfo.idle
        cpuset['iowait'] = cpuinfo.iowait
        output = subprocess.check_output(["cat /proc/cpuinfo"],shell=True)
        output = output.decode('utf-8')
        parts = output.split('\n')
        info = []
        idx = -1
        for part in parts:
            if not part == '':
                key_val = re.split(':',part)
                key = key_val[0].rstrip()
                if key == 'processor':
                    info.append({})
                    idx += 1
                val = key_val[1].lstrip()
                if key=='processor' or key=='model name' or key=='core id' or key=='cpu MHz' or key=='cache size' or key=='physical id':
                    info[idx][key] = val
        return [cpuset, info]

    def collect_diskinfo(self):
        global workercinfo
        parts = psutil.disk_partitions()
        setval = []
        devices = {}
        for part in parts:
            if not part.device in devices:
                devices[part.device] = 1
                diskval = {}
                diskval['device'] = part.device
                diskval['mountpoint'] = part.mountpoint
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    diskval['total'] = usage.total
                    diskval['used'] = usage.used
                    diskval['free'] = usage.free
                    diskval['percent'] = usage.percent
                    if(part.mountpoint.startswith('/opt/docklet/local/volume')):
                        names = re.split('/',part.mountpoint)
                        container = names[len(names)-1]
                        if not container in workercinfo.keys():
                            workercinfo[container] = {}
                        workercinfo[container]['disk_use'] = diskval 
                    setval.append(diskval)
                except Exception as err:
                    logger.warning(traceback.format_exc())
                    logger.warning(err)
        #print(output)
        #print(diskparts)
        return setval

    def collect_osinfo(self):
        uname = platform.uname()
        osinfo = {}
        osinfo['platform'] = platform.platform()
        osinfo['system'] = uname.system
        osinfo['node'] = uname.node
        osinfo['release'] = uname.release
        osinfo['version'] = uname.version
        osinfo['machine'] = uname.machine
        osinfo['processor'] = uname.processor
        return osinfo

    def run(self):
        global workerinfo
        workerinfo['osinfo'] = self.collect_osinfo()
        while not self.thread_stop:
            workerinfo['meminfo'] = self.collect_meminfo()
            [cpuinfo,cpuconfig] = self.collect_cpuinfo()
            workerinfo['cpuinfo'] = cpuinfo
            workerinfo['cpuconfig'] = cpuconfig
            workerinfo['diskinfo'] = self.collect_diskinfo()
            workerinfo['running'] = True
            time.sleep(self.interval)
            if self.test:
                break
            #   print(self.etcdser.getkey('/meminfo/total'))
        return

    def stop(self):
        self.thread_stop = True

def workerFetchInfo():
    global workerinfo
    global workercinfo
    return str([workerinfo, workercinfo])

def get_owner(container_name):
    names = container_name.split('-')
    return names[0]

class Master_Collector(threading.Thread):

    def __init__(self,nodemgr):
        threading.Thread.__init__(self)
        self.thread_stop = False
        self.nodemgr = nodemgr
        return

    def run(self):
        global monitor_hosts
        global monitor_vnodes
        while not self.thread_stop:
            for worker in monitor_hosts.keys():
                monitor_hosts[worker]['running'] = False
            workers = self.nodemgr.get_rpcs()
            for worker in workers:
                try:
                    ip = self.nodemgr.rpc_to_ip(worker)
                    info = list(eval(worker.workerFetchInfo()))
                    #logger.info(info[1])
                    monitor_hosts[ip] = info[0]
                    for container in info[1].keys():
                        owner = get_owner(container)
                        if not owner in monitor_vnodes.keys():
                            monitor_vnodes[owner] = {}
                        monitor_vnodes[owner][container] = info[1][container]
                except Exception as err:
                    logger.warning(traceback.format_exc())
                    logger.warning(err)
            time.sleep(2000)
        return

    def stop(self):
        self.thread_stop = True
        return

class Container_Fetcher:
    def __init__(self,container_name):
        self.owner = get_owner(container_name)
        self.con_id = container_name
        return

    def get_cpu_use(self):
        global monitor_vnodes
        try:
            res = monitor_vnodes[self.owner][self.con_id]['cpu_use']
            res['quota'] = monitor_vnodes[self.owner][self.con_id]['quota']
        except Exception as err:
            logger.warning(traceback.format_exc())
            logger.warning(err)
            res = {}
        return res

    def get_mem_use(self):
        global monitor_vnodes
        try:
            res = monitor_vnodes[self.owner][self.con_id]['mem_use']
            res['quota'] = monitor_vnodes[self.owner][self.con_id]['quota']
        except Exception as err:
            logger.warning(traceback.format_exc())
            logger.warning(err)
            res = {}
        return res

    def get_disk_use(self):
        global monitor_vnodes
        try:
            res = monitor_vnodes[self.owner][self.con_id]['disk_use']
        except Exception as err:
            logger.warning(traceback.format_exc())
            logger.warning(err)
            res = {}
        return res

    def get_basic_info(self):
        global monitor_vnodes
        try:
            res = monitor_vnodes[self.owner][self.con_id]['basic_info']
        except Exception as err:
            logger.warning(traceback.format_exc())
            logger.warning(err)
            res = {}
        return res

class Fetcher:

    def __init__(self,host):
        global monitor_hosts
        self.info = monitor_hosts[host]
        return

    #def get_clcnt(self):
    #   return DockletMonitor.clcnt

    #def get_nodecnt(self):
    #   return DockletMonitor.nodecnt

    #def get_meminfo(self):
    #   return self.get_meminfo_('172.31.0.1')

    def get_meminfo(self):
        try:
            res = self.info['meminfo']
        except Exception as err:
            logger.warning(traceback.format_exc())
            logger.warning(err)
            res = {}
        return res

    def get_cpuinfo(self):
        try:
            res = self.info['cpuinfo']
        except Exception as err:
            logger.warning(traceback.format_exc())
            logger.warning(err)
            res = {}
        return res

    def get_cpuconfig(self):
        try:
            res = self.info['cpuconfig']
        except Exception as err:
            logger.warning(traceback.format_exc())
            logger.warning(err)
            res = {}
        return res

    def get_diskinfo(self):
        try:
            res = self.info['diskinfo']
        except Exception as err:
            logger.warning(traceback.format_exc())
            logger.warning(err)
            res = {}
        return res

    def get_osinfo(self):
        try:
            res = self.info['osinfo']
        except Exception as err:
            logger.warning(traceback.format_exc())
            logger.warning(err)
            res = {}
        return res

    def get_containers(self):
        try:
            res = self.info['containers']
        except Exception as err:
            logger.warning(traceback.format_exc())
            logger.warning(err)
            res = {}
        return res

    def get_status(self):
        try:
            isexist = self.info['running']
        except Exception as err:
            logger.warning(traceback.format_exc())
            logger.warning(err)
            isexist = False
        if(isexist):
            return 'RUNNING'
        else:
            return 'STOPPED'

    def get_containerslist(self):
        try:
            res = self.info['containerslist']
        except Exception as err:
            logger.warning(traceback.format_exc())
            logger.warning(err)
            res = {}
        return res
