import threading, time, traceback
from utils import env
from utils.log import logger
from httplib2 import Http
from urllib.parse import urlencode

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

# get owner name of a container
def get_owner(container_name):
    names = container_name.split('-')
    return names[0]

# the thread to collect data from each worker and store them in monitor_hosts and monitor_vnodes
class Master_Collector(threading.Thread):

    def __init__(self,nodemgr,master_ip):
        threading.Thread.__init__(self)
        self.thread_stop = False
        self.nodemgr = nodemgr
        self.master_ip = master_ip
        self.net_lastbillings = {}
        self.bytes_per_beans = 1000000000
        return

    def net_billings(self, username, now_bytes_total):
        global monitor_vnodes
        if not username in self.net_lastbillings.keys():
            self.net_lastbillings[username] = 0
        elif int(now_bytes_total/self.bytes_per_beans) < self.net_lastbillings[username]:
            self.net_lastbillings[username] = 0
        diff = int(now_bytes_total/self.bytes_per_beans) - self.net_lastbillings[username]
        if diff > 0:
            auth_key = env.getenv('AUTH_KEY')
            data = {"owner_name":username,"billing":diff, "auth_key":auth_key}
            header = {'Content-Type':'application/x-www-form-urlencoded'}
            http = Http()
            [resp,content] = http.request("http://"+self.master_ip+"/billing/beans/","POST",urlencode(data),headers = header)
            logger.info("response from master:"+content.decode('utf-8'))
        self.net_lastbillings[username] += diff
        monitor_vnodes[username]['net_stats']['net_billings'] = self.net_lastbillings[username]

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
                    workerrpc = self.nodemgr.ip_to_rpc(worker)
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
                    for user in info[2].keys():
                        if not user in monitor_vnodes.keys():
                            continue
                        else:
                            monitor_vnodes[user]['net_stats'] = info[2][user]
                            self.net_billings(user, info[2][user]['bytes_total'])
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

    def get_info(self):
        res = {}
        res['cpu_use'] = self.get_cpu_use()
        res['mem_use'] = self.get_mem_use()
        res['disk_use'] = self.get_disk_use()
        res['net_stats'] = self.get_net_stats()
        res['basic_info'] = self.get_basic_info()
        return res

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

    def get_net_stats(self):
        global monitor_vnodes
        try:
            res = monitor_vnodes[self.owner][self.con_id]['net_stats']
        except Exception as err:
            logger.warning(traceback.format_exc())
            logger.warning(err)
            res = {}
        return res

    # get users' net_stats
    @staticmethod
    def get_user_net_stats(owner):
        global monitor_vnodes
        try:
            res = monitor_vnodes[owner]['net_stats']
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

    def get_gpuinfo(self):
        try:
            res = self.info['gpuinfo']
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
