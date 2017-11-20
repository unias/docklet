#!/usr/bin/python3

'''
Monitor for Docklet
Description:Monitor system for docklet will collect data on resources usages and status of vnode
            and phyiscal machines. And master can fetch these data and then show them on the web page.
            Besides, Monitor will also bill the vnodes according to their resources usage amount.

Design:Monitor mainly consists of three parts: Collectors, Master_Collector and Fetchers.
       1.Collectors will collect data every two seconds on each worker. And 'Container_Collector' will
       collect data of containers(vnodes), while 'Collector' will collect data of physical machines.
       2.'Master_Collector' only runs on Master. It fetches the data on workers every two seconds by rpc
       and stores them in the memory of Master.
       3.Fetchers are classes that Master will use them to fetch specific data in the memory and then show
       them on the web. 'Container_Fetcher' is the class to fetch the containers data in 'monitor_vnodes',
       while 'Fetcher' is the class to fetch the data of physical machines in 'monitor_hosts'.
'''


import subprocess,re,os,etcdlib,psutil,math,sys
import time,threading,json,traceback,platform
import env
import lxc
import xmlrpc.client
from datetime import datetime

from model import db,VNode,History
from log import logger
from httplib2 import Http
from urllib.parse import urlencode
from httprest import post_to_user

# billing parameters
a_cpu = 500         # seconds
b_mem = 2000000     # MB
c_disk = 4000       # MB

# major dict to store the monitoring data
# only use on Master
# monitor_hosts: use workers' ip addresses as first key.
# second key: cpuinfo,diskinfo,meminfo,osinfo,cpuconfig,running,containers,containerslist
# 1.cpuinfo stores the cpu usages data, and it has keys: user,system,idle,iowait
# 2.diskinfo stores the disks usages data, and it has keys: device,mountpoint,total,used,free,percent
# 3.meminfo stores the memory usages data, and it has keys: total,used,free,buffers,cached,percent
# 4.osinfo stores the information of operating system,
# and it has keys: platform,system,node,release,version,machine,processor
# 5.cpuconfig stores the information of processors, and it is a list, each element of list is a dict
# which stores the information of a processor, each element has key: processor,model name,
# core id, cpu MHz, cache size, physical id.
# 6.running indicates the status of worker,and it has two values: True, False.
# 7.containers store the amount of containers on the worker.
# 8.containers store a list which consists of the names of containers on the worker.
monitor_hosts = {}

# monitor_vnodes: use the owners' names of vnodes(containers) as first key.
# use the names of vnodes(containers) as second key.
# third key: cpu_use,mem_use,disk_use,basic_info,quota
# 1.cpu_use has keys: val,unit,hostpercent
# 2.mem_use has keys: val,unit,usedp
# 3.disk_use has keys: device,mountpoint,total,used,free,percent
# 4.basic_info has keys: Name,State,PID,IP,RunningTime,billing,billing_this_hour
# 5.quota has keys: cpu,memeory
monitor_vnodes = {}

# major dict to store the monitoring data on Worker
# only use on Worker
# workerinfo: only store the data collected on current Worker,
# has the first keys same as the second keys in monitor_hosts.
workerinfo = {}

# workercinfo: only store the data collected on current Worker,
# use the names of vnodes(containers) as second key.
# has the second keys same as the third keys in monitor_vnodes.
workercinfo = {}

# only use on worker
containerpids = []
pid2name = {}
G_masterip = ""

# only use on worker
laststopcpuval = {}
laststopruntime = {}
lastbillingtime = {}
# increment has keys: lastcputime,memincrement.
# record the cpu val at last billing time and accumulate the memory usages during this billing hour.
increment = {}

# send http request to master
def request_master(url,data):
    global G_masterip
    header = {'Content-Type':'application/x-www-form-urlencoded'}
    http = Http()
    [resp,content] = http.request("http://"+G_masterip+url,"POST",urlencode(data),headers = header)
    logger.info("response from master:"+content.decode('utf-8'))

# The class is to collect data of containers on each worker
class Container_Collector(threading.Thread):

    def __init__(self,test=False):
        global laststopcpuval
        global workercinfo
        threading.Thread.__init__(self)
        self.thread_stop = False
        self.interval = 2
        self.billingtime = 3600     # billing interval
        self.test = test
        self.cpu_last = {}
        self.cpu_quota = {}
        self.mem_quota = {}
        self.cores_num = int(subprocess.getoutput("grep processor /proc/cpuinfo | wc -l"))
        containers = self.list_container()
        for container in containers:    # recovery
            if not container == '':
                try:
                    vnode = VNode.query.get(container)
                    laststopcpuval[container] = vnode.laststopcpuval
                    laststopruntime[container] = vnode.laststopruntime
                    workercinfo[container] = {}
                    workercinfo[container]['basic_info'] = {}
                    workercinfo[container]['basic_info']['billing'] = vnode.billing
                    workercinfo[container]['basic_info']['RunningTime'] = vnode.laststopruntime
                except:
                    laststopcpuval[container] = 0
                    laststopruntime[container] = 0
        return

    # list containers on this worker
    def list_container(self):
        output = subprocess.check_output(["sudo lxc-ls"],shell=True)
        output = output.decode('utf-8')
        containers = re.split('\s+',output)
        return containers

    # get running time of a process, return seconds
    def get_proc_etime(self,pid):
        fmt = subprocess.getoutput("ps -A -opid,etime | grep '^ *%d ' | awk '{print $NF}'" % pid).strip()
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

    # compute the billing val this running hour
    # if isreal is True, it will also make users' beans decrease to pay for the bill.
    # return the billing value in this running hour
    @classmethod
    def billing_increment(cls,vnode_name,isreal=True):
        global increment
        global workercinfo
        global G_masterip
        global a_cpu
        global b_mem
        global c_disk
        cpu_val = '0'
        if vnode_name not in workercinfo.keys():
            return 0
        if 'cpu_use' in workercinfo[vnode_name].keys():
            cpu_val = workercinfo[vnode_name]['cpu_use']['val']
        if vnode_name not in increment.keys():
            increment[vnode_name] = {}
            increment[vnode_name]['lastcputime'] = cpu_val
            increment[vnode_name]['memincrement'] = 0
        # compute cpu used time during this running hour
        cpu_increment = float(cpu_val) - float(increment[vnode_name]['lastcputime'])
        #logger.info("billing:"+str(cpu_increment)+" "+str(increment[container_name]['lastcputime']))
        if cpu_increment == 0.0:
            avemem = 0
        else:
            # avemem = (average memory used) * (cpu used time)
            avemem = cpu_increment*float(increment[vnode_name]['memincrement'])/1800.0
        if 'disk_use' in workercinfo[vnode_name].keys():
            disk_quota = workercinfo[vnode_name]['disk_use']['total']
        else:
            disk_quota = 0
        # get ports
        ports_count = count_port_mapping(vnode_name)
        # billing value = cpu used/a + memory used/b + disk quota/c + ports
        billingval = math.ceil(cpu_increment/a_cpu + avemem/b_mem + float(disk_quota)/1024.0/1024.0/c_disk + ports_count)
        if billingval > 100:
            # report outsize billing value
            logger.info("Huge Billingval for "+vnode_name+". cpu_increment:"+str(cpu_increment)+" avemem:"+str(avemem)+" disk:"+str(disk_quota)+"\n")
        if not isreal:
            # only compute
            return math.ceil(billingval)
        # initialize increment for next billing
        increment[vnode_name]['lastcputime'] = cpu_val
        increment[vnode_name]['memincrement'] = 0
        if 'basic_info' not in workercinfo[vnode_name].keys():
            workercinfo[vnode_name]['basic_info'] = {}
            workercinfo[vnode_name]['basic_info']['billing'] = 0
            workercinfo[vnode_name]['basic_info']['RunningTime'] = 0
        # update monitoring data
        nowbillingval = workercinfo[vnode_name]['basic_info']['billing']
        nowbillingval += billingval
        workercinfo[vnode_name]['basic_info']['billing'] = nowbillingval
        # update vnodes' tables in database
        try:
            vnode = VNode.query.get(vnode_name)
            vnode.billing = nowbillingval
        except Exception as err:
            vnode = VNode(vnode_name)
            vnode.billing = nowbillingval
            db.session.add(vnode)
            logger.warning(err)
        try:
            db.session.commit()
        except Exception as err:
            db.session.rollback()
            logger.warning(traceback.format_exc())
            logger.warning(err)
            raise
        # update users' tables in database
        owner_name = get_owner(vnode_name)
        auth_key = env.getenv('AUTH_KEY')
        data = {"owner_name":owner_name,"billing":billingval, "auth_key":auth_key}
        request_master("/billing/beans/",data)
        return billingval

    # the main function to collect monitoring data of a container
    def collect_containerinfo(self,container_name):
        global workerinfo
        global workercinfo
        global increment
        global lastbillingtime
        global containerpids
        global pid2name
        global laststopcpuval
        global laststopruntime
        # collect basic information, such as running time,state,pid,ip,name
        container = lxc.Container(container_name)
        basic_info = {}
        basic_exist = 'basic_info' in workercinfo[container_name].keys()
        if basic_exist:
            basic_info = workercinfo[container_name]['basic_info']
        else:
            basic_info['RunningTime'] = 0
            basic_info['billing'] = 0
        if 'billing_this_hour' not in basic_info.keys():
            basic_info['billing_this_hour'] = 0
        basic_info['Name'] = container_name
        basic_info['State'] = container.state
        #if basic_exist:
         #   logger.info(workercinfo[container_name]['basic_info'])
        if(container.state == 'STOPPED'):
            workercinfo[container_name]['basic_info'] = basic_info
            #logger.info(basic_info)
            return False
        container_pid_str = str(container.init_pid)
        if not container_pid_str in containerpids:
            containerpids.append(container_pid_str)
            pid2name[container_pid_str] = container_name
        running_time = self.get_proc_etime(container.init_pid)
        running_time += laststopruntime[container_name]
        basic_info['PID'] = container_pid_str
        basic_info['IP'] = container.get_ips()[0]
        basic_info['RunningTime'] = running_time
        workercinfo[container_name]['basic_info'] = basic_info

        # deal with cpu used value
        cpu_val = float("%.2f" % (float(container.get_cgroup_item("cpuacct.usage")) / 1000000000))
        cpu_unit = "seconds"
        if not container_name in self.cpu_last.keys():
            # read quota from config of container
            confpath = "/var/lib/lxc/%s/config"%(container_name)
            if os.path.exists(confpath):
                confile = open(confpath,'r')
                res = confile.read()
                lines = re.split('\n',res)
                for line in lines:
                    words = re.split('=',line)
                    key = words[0].strip()
                    if key == "lxc.cgroup.memory.limit_in_bytes":
                        # get memory quota, change unit to KB
                        self.mem_quota[container_name] = float(words[1].strip().strip("M"))*1000000/1024
                    elif key == "lxc.cgroup.cpu.cfs_quota_us":
                        # get cpu quota, change unit to cores
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
        # compute cpu used percent
        cpu_use = {}
        lastval = 0
        try:
            lastval = laststopcpuval[container_name]
        except:
            logger.warning(traceback.format_exc())
        cpu_val += lastval
        cpu_use['val'] = cpu_val
        cpu_use['unit'] = cpu_unit
        cpu_usedp = (float(cpu_val)-float(self.cpu_last[container_name]))/(self.cpu_quota[container_name]*self.interval*1.05)
        cpu_use['hostpercent'] = (float(cpu_val)-float(self.cpu_last[container_name]))/(self.cores_num*self.interval*1.05)
        if(cpu_usedp > 1 or cpu_usedp < 0):
            cpu_usedp = 1
        cpu_use['usedp'] = cpu_usedp
        self.cpu_last[container_name] = cpu_val;
        workercinfo[container_name]['cpu_use'] = cpu_use

        if container_name not in increment.keys():
            # initialize increment
            increment[container_name] = {}
            increment[container_name]['lastcputime'] = cpu_val
            increment[container_name]['memincrement'] = 0

        # deal with memory used data
        memory = float(container.get_cgroup_item("memory.usage_in_bytes"))
        increment[container_name]['memincrement'] += memory / 1024 / 1024

        mem_val = memory / 1024
        mem_unit = 'KiB'
        if mem_val > 1024:
            mem_val /= 1024
            mem_unit = 'MiB'
        if mem_val > 1024:
            mem_val /= 1024
            mem_unit = 'GiB'

        mem_use = {}
        mem_use['val'] = float("%.2f" % mem_val)
        mem_use['unit'] = mem_unit
        mem_use['usedp'] = memory / 1024 / self.mem_quota[container_name]
        workercinfo[container_name]['mem_use'] = mem_use
        # compute billing value during this running hour up to now
        workercinfo[container_name]['basic_info']['billing_this_hour'] = self.billing_increment(container_name,False)


        if not container_name in lastbillingtime.keys():
            lastbillingtime[container_name] = int(running_time/self.billingtime)
        lasttime = lastbillingtime[container_name]
        #logger.info(lasttime)
        # process real billing if running time reach an hour
        if not int(running_time/self.billingtime) == lasttime:
            #logger.info("billing:"+str(float(cpu_val)))
            lastbillingtime[container_name] = int(running_time/self.billingtime)
            self.billing_increment(container_name)
        #print(output)
        #print(parts)
        return True

    # run function in the thread
    def run(self):
        global workercinfo
        global workerinfo
        cnt = 0
        while not self.thread_stop:
            containers = self.list_container()
            countR = 0
            conlist = []
            for container in containers:
                # collect data of each container
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
                # update containers list on the worker each 5 times
                workerinfo['containerslist'] = conlist
            cnt = (cnt+1)%5
            if self.test:
                break
        return

    def stop(self):
        self.thread_stop = True

# the class is to colect monitoring data of the worker
class Collector(threading.Thread):

    def __init__(self,test=False):
        global workerinfo
        threading.Thread.__init__(self)
        self.thread_stop = False
        self.interval = 1
        self.test=test
        workerinfo['concpupercent'] = {}
        return

    # collect memory used information
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

    # collect cpu used information and processors information
    def collect_cpuinfo(self):
        cpuinfo = psutil.cpu_times_percent(interval=1,percpu=False)
        cpuset = {}
        cpuset['user'] = cpuinfo.user
        cpuset['system'] = cpuinfo.system
        cpuset['idle'] = cpuinfo.idle
        cpuset['iowait'] = cpuinfo.iowait
        # get processors information from /proc/cpuinfo
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

    # collect disk used information
    def collect_diskinfo(self):
        global workercinfo
        parts = psutil.disk_partitions()
        setval = []
        devices = {}
        for part in parts:
            # deal with each partition
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
                        # the mountpoint indicate that the data is the disk used information of a container
                        names = re.split('/',part.mountpoint)
                        container = names[len(names)-1]
                        if not container in workercinfo.keys():
                            workercinfo[container] = {}
                        workercinfo[container]['disk_use'] = diskval
                    setval.append(diskval)  # make a list
                except Exception as err:
                    logger.warning(traceback.format_exc())
                    logger.warning(err)
        #print(output)
        #print(diskparts)
        return setval

    # collect operating system information
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

    # run function in the thread
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
            #time.sleep(self.interval)
            if self.test:
                break
            #   print(self.etcdser.getkey('/meminfo/total'))
        return

    def stop(self):
        self.thread_stop = True

# the function used by rpc to fetch data from worker
def workerFetchInfo(master_ip):
    global workerinfo
    global workercinfo
    global G_masterip
    # tell the worker the ip address of the master
    G_masterip = master_ip
    return str([workerinfo, workercinfo])

# get owner name of a container
def get_owner(container_name):
    names = container_name.split('-')
    return names[0]

def count_port_mapping(vnode_name):
    user = get_owner(vnode_name)
    fspath = env.getenv("FS_PREFIX")
    if not os.path.exists(fspath+"/global/users/"+user+"/clusters"):
        return 0
    clusters = os.listdir(fspath+"/global/users/"+user+"/clusters")
    ports_count = 0
    for cluster in clusters:
        clusterpath = fspath + "/global/users/" + get_owner(vnode_name) + "/clusters/" + cluster
        if not os.path.isfile(clusterpath):
            return 0
        infofile = open(clusterpath, 'r')
        info = json.loads(infofile.read())
        ports_count += len([mapping for mapping in info['port_mapping'] if mapping['node_name'] == vnode_name])
    return ports_count

# the thread to collect data from each worker and store them in monitor_hosts and monitor_vnodes
class Master_Collector(threading.Thread):

    def __init__(self,nodemgr,master_ip):
        threading.Thread.__init__(self)
        self.thread_stop = False
        self.nodemgr = nodemgr
        self.master_ip = master_ip
        return

    def run(self):
        global monitor_hosts
        global monitor_vnodes
        while not self.thread_stop:
            for worker in monitor_hosts.keys():
                monitor_hosts[worker]['running'] = False
            workers = self.nodemgr.get_nodeips()
            for worker in workers:
                try:
                    ip = worker
                    workerrpc = xmlrpc.client.ServerProxy("http://%s:%s" % (worker, env.getenv("WORKER_PORT")))
                    # fetch data
                    info = list(eval(workerrpc.workerFetchInfo(self.master_ip)))
                    #logger.info(info[0])
                    # store data in monitor_hosts and monitor_vnodes
                    monitor_hosts[ip] = info[0]
                    for container in info[1].keys():
                        owner = get_owner(container)
                        if not owner in monitor_vnodes.keys():
                            monitor_vnodes[owner] = {}
                        monitor_vnodes[owner][container] = info[1][container]
                except Exception as err:
                    logger.warning(traceback.format_exc())
                    logger.warning(err)
            time.sleep(2)
            #logger.info(History.query.all())
            #logger.info(VNode.query.all())
        return

    def stop(self):
        self.thread_stop = True
        return

# master use this class to fetch specific data of containers(vnodes)
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

# Master use this class to fetch specific data of physical machines(hosts)
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

    def get_concpuinfo(self):
        try:
            res = self.info['concpupercent']
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

# To record data when the status of containers change
class History_Manager:

    def __init__(self):
        try:
            VNode.query.all()
            History.query.all()
        except:
            db.create_all(bind='__all__')

    def getAll(self):
        return History.query.all()

    # log to the database, it will record runnint time, cpu time, billing val and action
    # action may be 'Create', 'Stop', 'Start', 'Recover', 'Delete'
    def log(self,vnode_name,action):
        global workercinfo
        global laststopcpuval
        res = VNode.query.filter_by(name=vnode_name).first()
        if res is None:
            vnode = VNode(vnode_name)
            vnode.histories = []
            db.session.add(vnode)
            db.session.commit()
        vnode = VNode.query.get(vnode_name)
        billing = 0
        cputime = 0
        runtime = 0
        owner = get_owner(vnode_name)
        try:
            billing = int(workercinfo[vnode_name]['basic_info']['billing'])
        except:
            billing = 0
        try:
            cputime = float(workercinfo[vnode_name]['cpu_use']['val'])
        except:
            cputime = 0.0
        try:
            runtime = float(workercinfo[vnode_name]['basic_info']['RunningTime'])
        except Exception as err:
            #print(traceback.format_exc())
            runtime = 0
        history = History(action,runtime,cputime,billing)
        vnode.histories.append(history)
        if action == 'Stop' or action == 'Create':
            laststopcpuval[vnode_name] = cputime
            vnode.laststopcpuval = cputime
            laststopruntime[vnode_name] = runtime
            vnode.laststopruntime = runtime
        db.session.add(history)
        db.session.commit()

    def getHistory(self,vnode_name):
        vnode = VNode.query.filter_by(name=vnode_name).first()
        if vnode is None:
            return []
        else:
            res = History.query.filter_by(vnode=vnode_name).all()
            return list(eval(str(res)))

    # get all created containers(including those have been deleted) of a owner
    def getCreatedVNodes(self,owner):
        vnodes = VNode.query.filter(VNode.name.startswith(owner)).all()
        res = []
        for vnode in vnodes:
            tmp = {"name":vnode.name,"billing":vnode.billing}
            res.append(tmp)
        return res
