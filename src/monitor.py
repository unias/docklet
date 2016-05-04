#!/usr/bin/python3

import subprocess,re,os,etcdlib,psutil
import time,threading,json,traceback,platform

from log import logger

class Container_Collector(threading.Thread):

    def __init__(self,etcdaddr,cluster_name,host,test=False):
        threading.Thread.__init__(self)
        self.thread_stop = False
        self.host = host
        self.etcdser = etcdlib.Client(etcdaddr,"/%s/monitor" % (cluster_name))
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

    def collect_containerinfo(self,container_name):
        output = subprocess.check_output("sudo lxc-info -n %s" % (container_name),shell=True)
        output = output.decode('utf-8')
        parts = re.split('\n',output)
        info = {}
        basic_info = {}
        for part in parts:
            if not part == '':
                key_val = re.split(':',part)
                key = key_val[0]
                val = key_val[1]
                info[key] = val.lstrip()
        basic_info['Name'] = info['Name']
        basic_info['State'] = info['State']
        if(info['State'] == 'STOPPED'):
            self.etcdser.setkey('/vnodes/%s/basic_info'%(container_name), basic_info)
            return False
        basic_info['PID'] = info['PID']
        basic_info['IP'] = info['IP']
        self.etcdser.setkey('/vnodes/%s/basic_info'%(container_name), basic_info)

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
                self.etcdser.setkey('/vnodes/%s/quota'%(container_name),quota)
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
        self.etcdser.setkey('/vnodes/%s/cpu_use'%(container_name), cpu_use)

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
        self.etcdser.setkey('/vnodes/%s/mem_use'%(container_name), mem_use)
        #print(output)
        #print(parts)
        return True

    def run(self):
        cnt = 0
        while not self.thread_stop:
            containers = self.list_container()
            countR = 0
            conlist = []
            for container in containers:
                if not container == '':
                    conlist.append(container)
                    try:
                        if(self.collect_containerinfo(container)):
                            countR += 1
                    except Exception as err:
                        logger.warning(traceback.format_exc())
                        logger.warning(err)
            containers_num = len(containers)-1
            concnt = {}
            concnt['total'] = containers_num
            concnt['running'] = countR
            self.etcdser.setkey('/hosts/%s/containers'%(self.host), concnt)
            time.sleep(self.interval)
            if cnt == 0:
                self.etcdser.setkey('/hosts/%s/containerslist'%(self.host), conlist)
            cnt = (cnt+1)%5
            if self.test:
                break
        return

    def stop(self):
        self.thread_stop = True


class Collector(threading.Thread):

    def __init__(self,etcdaddr,cluster_name,host,test=False):
        threading.Thread.__init__(self)
        self.host = host
        self.thread_stop = False
        self.etcdser = etcdlib.Client(etcdaddr,"/%s/monitor/hosts/%s" % (cluster_name,host))
        self.vetcdser = etcdlib.Client(etcdaddr,"/%s/monitor/vnodes" % (cluster_name))
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
        self.etcdser.setkey('/meminfo',memdict)
        #print(output)
        #print(memparts)
        return

    def collect_cpuinfo(self):
        cpuinfo = psutil.cpu_times_percent(interval=1,percpu=False)
        cpuset = {}
        cpuset['user'] = cpuinfo.user
        cpuset['system'] = cpuinfo.system
        cpuset['idle'] = cpuinfo.idle
        cpuset['iowait'] = cpuinfo.iowait
        self.etcdser.setkey('/cpuinfo',cpuset)
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
        self.etcdser.setkey('/cpuconfig',info)
        return

    def collect_diskinfo(self):
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
                        self.vetcdser.setkey('/%s/disk_use'%(container), diskval)
                    setval.append(diskval)
                except Exception as err:
                    logger.warning(traceback.format_exc())
                    logger.warning(err)
        self.etcdser.setkey('/diskinfo', setval)
        #print(output)
        #print(diskparts)
        return

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
        self.etcdser.setkey('/osinfo',osinfo)
        return

    def run(self):
        self.collect_osinfo()
        while not self.thread_stop:
            self.collect_meminfo()
            self.collect_cpuinfo()
            self.collect_diskinfo()
            self.etcdser.setkey('/running','True',6)
            time.sleep(self.interval)
            if self.test:
                break
            #   print(self.etcdser.getkey('/meminfo/total'))
        return

    def stop(self):
        self.thread_stop = True

class Container_Fetcher:
    def __init__(self,etcdaddr,cluster_name):
        self.etcdser = etcdlib.Client(etcdaddr,"/%s/monitor/vnodes" % (cluster_name))
        return

    def get_cpu_use(self,container_name):
        res = {}
        [ret, ans] = self.etcdser.getkey('/%s/cpu_use'%(container_name))
        if ret == True :
            res = dict(eval(ans))
            [ret,quota] = self.etcdser.getkey('/%s/quota'%(container_name))
            if ret == False:
                res['quota'] = {'cpu':0}
                logger.warning(quota)
            res['quota'] = dict(eval(quota))
            return res
        else:
            logger.warning(ans)
            return res

    def get_mem_use(self,container_name):
        res = {}
        [ret, ans] = self.etcdser.getkey('/%s/mem_use'%(container_name))
        if ret == True :
            res = dict(eval(ans))
            [ret,quota] = self.etcdser.getkey('/%s/quota'%(container_name))
            if ret == False:
                res['quota'] = {'memory':0}
                logger.warning(quota)
            res['quota'] = dict(eval(quota))
            return res
        else:
            logger.warning(ans)
            return res

    def get_disk_use(self,container_name):
        res = {}
        [ret, ans] = self.etcdser.getkey('/%s/disk_use'%(container_name))
        if ret == True :
            res = dict(eval(ans))
        else:
            logger.warning(ans)
        return res

    def get_basic_info(self,container_name):
        res = self.etcdser.getkey("/%s/basic_info"%(container_name))
        if res[0] == False:
            return {}
        res = dict(eval(res[1]))
        return res

class Fetcher:

    def __init__(self,etcdaddr,cluster_name,host):
        self.etcdser = etcdlib.Client(etcdaddr,"/%s/monitor/hosts/%s" % (cluster_name,host))
        return

    #def get_clcnt(self):
    #   return DockletMonitor.clcnt

    #def get_nodecnt(self):
    #   return DockletMonitor.nodecnt

    #def get_meminfo(self):
    #   return self.get_meminfo_('172.31.0.1')

    def get_meminfo(self):
        res = {}
        [ret, ans] = self.etcdser.getkey('/meminfo')
        if ret == True :
            res = dict(eval(ans))
            return res
        else:
            logger.warning(ans)
            return res

    def get_cpuinfo(self):
        res = {}
        [ret, ans] = self.etcdser.getkey('/cpuinfo')
        if ret == True :
            res = dict(eval(ans))
            return res
        else:
            logger.warning(ans)
            return res

    def get_cpuconfig(self):
        res = {}
        [ret, ans] = self.etcdser.getkey('/cpuconfig')
        if ret == True :
            res = list(eval(ans))
            return res
        else:
            logger.warning(ans)
            return res

    def get_diskinfo(self):
        res = []
        [ret, ans] = self.etcdser.getkey('/diskinfo')
        if ret == True :
            res = list(eval(ans))
            return res
        else:
            logger.warning(ans)
            return res

    def get_osinfo(self):
        res = {}
        [ret, ans] = self.etcdser.getkey('/osinfo')
        if ret == True:
            res = dict(eval(ans))
            return res
        else:
            logger.warning(ans)
            return res

    def get_containers(self):
        res = {}
        [ret, ans] = self.etcdser.getkey('/containers')
        if ret == True:
            res = dict(eval(ans))
            return res
        else:
            logger.warning(ans)
            return res

    def get_status(self):
        isexist = self.etcdser.getkey('/running')[0]
        if(isexist):
            return 'RUNNING'
        else:
            return 'STOPPED'

    def get_containerslist(self):
        res = list(eval(self.etcdser.getkey('/containerslist')[1]))
        return res
