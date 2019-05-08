import threading
import time
import string
import os
import random, copy, subprocess
import json, math
from functools import wraps

# must import logger after initlogging, ugly
from utils.log import logger

# grpc
from concurrent import futures
import grpc
from protos.rpc_pb2 import *
from protos.rpc_pb2_grpc import MasterServicer, add_MasterServicer_to_server, WorkerStub
from utils.nettools import netcontrol
from utils import env

def ip_to_int(addr):
    [a, b, c, d] = addr.split('.')
    return (int(a)<<24) + (int(b)<<16) + (int(c)<<8) + int(d)

def int_to_ip(num):
    return str((num>>24)&255)+"."+str((num>>16)&255)+"."+str((num>>8)&255)+"."+str(num&255)

class Task():
    def __init__(self, task_id, username, at_same_time, priority, max_size, task_infos):
        self.id = task_id
        self.username = username
        self.status = WAITING
        self.failed_reason = ""
        # if all the vnodes must be started at the same time
        self.at_same_time = at_same_time
        # priority the bigger the better
        # self.priority the smaller the better
        self.priority = int(time.time()) / 60 / 60 - priority
        self.task_base_ip = None
        self.ips = None
        self.max_size = max_size

        self.subtask_list = [SubTask(
                idx = index,
                root_task = self,
                vnode_info = task_info['vnode_info'],
                command_info = task_info['command_info'],
                max_retry_count = task_info['max_retry_count']
            ) for (index, task_info) in enumerate(task_infos)]

    def get_billing(self):
        billing_beans = 0
        running_time = 0
        cpu_price = 1 / 3600.0  # /core*s
        mem_price = 1 / 3600.0 # /GB*s
        disk_price = 1 / 3600.0 # /GB*s
        gpu_price = 100 / 3600.0 # /core*s
        for subtask in self.subtask_list:
            tmp_time = subtask.running_time
            cpu_beans = subtask.vnode_info.vnode.instance.cpu * tmp_time * cpu_price
            mem_beans = subtask.vnode_info.vnode.instance.memory / 1024.0 * tmp_time * mem_price
            disk_beans = subtask.vnode_info.vnode.instance.disk / 1024.0 * tmp_time * disk_price
            gpu_beans = subtask.vnode_info.vnode.instance.gpu * tmp_time * gpu_price
            logger.info("subtask:%s running_time=%f beans for: cpu=%f mem_beans=%f disk_beans=%f gpu_beans=%f"
                        %(self.id, tmp_time, cpu_beans, mem_beans, disk_beans, gpu_beans ))
            beans = math.ceil(cpu_beans + mem_beans + disk_beans + gpu_beans)
            running_time += tmp_time
            billing_beans += beans
        return running_time, billing_beans

    def __lt__(self, other):
        return self.priority < other.priority

    def gen_ips_from_base(self,base_ip):
        if self.task_base_ip == None:
            return
        self.ips = []
        for i in range(self.max_size):
            self.ips.append(int_to_ip(base_ip + self.task_base_ip + i + 2))

    def gen_hosts(self):
        username = self.username
        taskid = self.id
        logger.info("Generate hosts for user(%s) task(%s) base_ip(%s)"%(username,taskid,str(self.task_base_ip)))
        fspath = env.getenv('FS_PREFIX')
        if not os.path.isdir("%s/global/users/%s" % (fspath,username)):
            path = env.getenv('DOCKLET_LIB')
            subprocess.call([path+"/master/userinit.sh", username])
            logger.info("user %s directory not found, create it" % username)

        hosts_file = open("%s/global/users/%s/hosts/%s.hosts" % (fspath,username,"batch-"+taskid),"w")
        hosts_file.write("127.0.0.1 localhost\n")
        i = 0
        for ip in self.ips:
            hosts_file.write(ip+" batch-"+str(i)+"\n")
            i += 1
        hosts_file.close()

class SubTask():
    def __init__(self, idx, root_task, vnode_info, command_info, max_retry_count):
        self.root_task = root_task
        self.vnode_info = vnode_info
        self.vnode_info.vnodeid = idx
        self.command_info = command_info
        if self.command_info != None:
            self.command_info.vnodeid = idx
        self.max_retry_count = max_retry_count
        self.vnode_started = False
        self.task_started = False
        self.start_at = 0
        self.end_at = 0
        self.running_time = 0
        self.status = WAITING
        self.status_reason = ''
        self.try_count = 0
        self.worker = None
        self.lock = threading.Lock()

    def waiting_for_retry(self,reason=""):
        self.try_count += 1
        self.status = WAITING if self.try_count <= self.max_retry_count else FAILED
        if self.status == FAILED:
            self.root_task.status = FAILED
            self.failed_reason = reason
            self.root_task.failed_reason = reason

class TaskReporter(MasterServicer):

    def __init__(self, taskmgr):
        self.taskmgr = taskmgr

    def report(self, request, context):
        for task_report in request.taskmsgs:
            self.taskmgr.on_task_report(task_report)
        return Reply(status=Reply.ACCEPTED, message='')


class TaskMgr(threading.Thread):

    # load task information from etcd
    # initial a task queue and task schedueler
    # taskmgr: a taskmgr instance
    def __init__(self, nodemgr, monitor_fetcher, master_ip, scheduler_interval=2, external_logger=None):
        threading.Thread.__init__(self)
        self.thread_stop = False
        self.jobmgr = None
        self.master_ip = master_ip
        self.task_queue = []
        self.lazy_append_list = []
        self.lazy_delete_list = []
        self.lazy_stop_list = []
        self.task_queue_lock = threading.Lock()
        self.stop_lock = threading.Lock()
        self.add_lock = threading.Lock()
        #self.user_containers = {}

        self.scheduler_interval = scheduler_interval
        self.logger = logger

        self.master_port = env.getenv('BATCH_MASTER_PORT')
        self.worker_port = env.getenv('BATCH_WORKER_PORT')

        # nodes
        self.nodemgr = nodemgr
        self.monitor_fetcher = monitor_fetcher
        self.cpu_usage = {}
        self.gpu_usage = {}
        # self.all_nodes = None
        # self.last_nodes_info_update_time = 0
        # self.nodes_info_update_interval = 30 # (s)

        self.network_lock = threading.Lock()
        batch_net = env.getenv('BATCH_NET')
        self.batch_cidr = int(batch_net.split('/')[1])
        batch_net = batch_net.split('/')[0]
        task_cidr = int(env.getenv('BATCH_TASK_CIDR'))
        task_cidr = min(task_cidr,31-self.batch_cidr)
        self.task_cidr = max(task_cidr,2)
        self.base_ip = ip_to_int(batch_net)
        self.free_nets = []
        for i in range(0, (1 << (32-self.batch_cidr)) - 1, (1 << self.task_cidr)):
            self.free_nets.append(i)
        #self.logger.info("Free nets addresses pool %s" % str(self.free_nets))
        self.logger.info("Each Batch Net CIDR:%s"%(str(self.task_cidr)))

    def data_lock(lockname):
        def lock(f):
            @wraps(f)
            def new_f(self, *args, **kwargs):
                lockobj = getattr(self,lockname)
                lockobj.acquire()
                try:
                    result = f(self, *args, **kwargs)
                except Exception as err:
                    lockobj.release()
                    raise err
                lockobj.release()
                return result
            return new_f
        return lock

    def subtask_lock(f):
        @wraps(f)
        def new_f(self, subtask, *args, **kwargs):
            subtask.lock.acquire()
            try:
                result = f(self, subtask, *args, **kwargs)
            except Exception as err:
                subtask.lock.release()
                raise err
            subtask.lock.release()
            return result
        return new_f

    def run(self):
        self.serve()
        while not self.thread_stop:
            self.sort_out_task_queue()
            task, sub_task_list = self.task_scheduler()
            if task is not None and sub_task_list is not None:
                self.task_processor(task, sub_task_list)
            else:
                time.sleep(self.scheduler_interval)

    def serve(self):
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        add_MasterServicer_to_server(TaskReporter(self), self.server)
        self.server.add_insecure_port('[::]:' + self.master_port)
        self.server.start()
        self.logger.info('[taskmgr_rpc] start rpc server')

    def stop(self):
        self.thread_stop = True
        self.server.stop(0)
        self.logger.info('[taskmgr_rpc] stop rpc server')

    @data_lock('task_queue_lock')
    @data_lock('add_lock')
    @data_lock('stop_lock')
    def sort_out_task_queue(self):

        for task in self.task_queue:
            if task.id in self.lazy_stop_list:
                self.stop_remove_task(task)
                self.lazy_delete_list.append(task)
                running_time, billing = task.get_billing()
                self.logger.info('task %s stopped, running_time:%s billing:%d'%(task.id, str(running_time), billing))
                running_time = math.ceil(running_time)
                self.jobmgr.report(task.username, task.id,'stopped',running_time=running_time,billing=billing)

        while self.lazy_delete_list:
            task = self.lazy_delete_list.pop(0)
            try:
                self.task_queue.remove(task)
            except Exception as err:
                self.logger.warning(str(err))

        new_append_list = []
        for task in self.lazy_append_list:
            if task.id in self.lazy_stop_list:
                self.jobmgr.report(task.username, task.id, 'stopped')
            else:
                new_append_list.append(task)

        self.lazy_append_list = new_append_list
        self.lazy_stop_list.clear()
        if self.lazy_append_list:
            self.task_queue.extend(self.lazy_append_list)
            self.lazy_append_list.clear()
            self.task_queue = sorted(self.task_queue, key=lambda x: x.priority)

    def start_vnode(self, subtask):
        try:
            self.logger.info('[task_processor] Starting vnode for task [%s] vnode [%d]' % (subtask.vnode_info.taskid, subtask.vnode_info.vnodeid))
            channel = grpc.insecure_channel('%s:%s' % (subtask.worker, self.worker_port))
            stub = WorkerStub(channel)
            response = stub.start_vnode(subtask.vnode_info)
            if response.status != Reply.ACCEPTED:
                raise Exception(response.message)
        except Exception as e:
            self.logger.error('[task_processor] rpc error message: %s' % e)
            subtask.status_reason = str(e)
            return [False, e]
        subtask.vnode_started = True
        subtask.start_at = time.time()
        self.cpu_usage[subtask.worker] += subtask.vnode_info.vnode.instance.cpu
        self.gpu_usage[subtask.worker] += subtask.vnode_info.vnode.instance.gpu
        return [True, '']

    @subtask_lock
    def stop_vnode(self, subtask):
        if not subtask.vnode_started:
            return [True, ""]
        try:
            self.logger.info('[task_processor] Stopping vnode for task [%s] vnode [%d]' % (subtask.vnode_info.taskid, subtask.vnode_info.vnodeid))
            channel = grpc.insecure_channel('%s:%s' % (subtask.worker, self.worker_port))
            stub = WorkerStub(channel)
            response = stub.stop_vnode(subtask.vnode_info)
            if response.status != Reply.ACCEPTED:
                raise Exception(response.message)
        except Exception as e:
            self.logger.error('[task_processor] rpc error message: %s' % e)
            subtask.status_reason = str(e)
            return [False, e]
        subtask.vnode_started = False
        subtask.end_at = time.time()
        subtask.running_time += subtask.end_at - subtask.start_at
        self.cpu_usage[subtask.worker] -= subtask.vnode_info.vnode.instance.cpu
        self.gpu_usage[subtask.worker] -= subtask.vnode_info.vnode.instance.gpu
        return [True, '']

    def start_subtask(self, subtask):
        try:
            self.logger.info('[task_processor] Starting task [%s] vnode [%d]' % (subtask.vnode_info.taskid, subtask.vnode_info.vnodeid))
            channel = grpc.insecure_channel('%s:%s' % (subtask.worker, self.worker_port))
            stub = WorkerStub(channel)
            response = stub.start_task(subtask.command_info)
            if response.status != Reply.ACCEPTED:
                raise Exception(response.message)
        except Exception as e:
            self.logger.error('[task_processor] rpc error message: %s' % e)
            subtask.status_reason = str(e)
            return [False, e]
        subtask.task_started = True
        return [True, '']

    def stop_subtask(self, subtask):
        try:
            self.logger.info('[task_processor] Stopping task [%s] vnode [%d]' % (subtask.vnode_info.taskid, subtask.vnode_info.vnodeid))
            channel = grpc.insecure_channel('%s:%s' % (subtask.worker, self.worker_port))
            stub = WorkerStub(channel)
            response = stub.stop_task(subtask.command_info)
            if response.status != Reply.ACCEPTED:
                raise Exception(response.message)
        except Exception as e:
            self.logger.error('[task_processor] rpc error message: %s' % e)
            subtask.status = FAILED
            subtask.status_reason = str(e)
            return [False, e]
        subtask.task_started = False
        return [True, '']

    @data_lock('network_lock')
    def acquire_task_ips(self, task):
        self.logger.info("[acquire_task_ips] user(%s) task(%s) net(%s)" % (task.username, task.id, str(task.task_base_ip)))
        if task.task_base_ip == None:
            task.task_base_ip = self.free_nets.pop(0)
        return task.task_base_ip

    @data_lock('network_lock')
    def release_task_ips(self, task):
        self.logger.info("[release_task_ips] user(%s) task(%s) net(%s)" % (task.username, task.id, str(task.task_base_ip)))
        if task.task_base_ip == None:
            return
        self.free_nets.append(task.task_base_ip)
        task.task_base_ip = None
        #self.logger.error('[release task_net] %s' % str(e))

    def setup_tasknet(self, task, workers=None):
        taskid = task.id
        username = task.username
        brname = "docklet-batch-%s-%s"%(username, taskid)
        gwname = taskid
        if task.task_base_ip == None:
            return [False, "task.task_base_ip is None!"]
        gatewayip = int_to_ip(self.base_ip + task.task_base_ip + 1)
        gatewayipcidr = gatewayip + "/" + str(32-self.task_cidr)
        netcontrol.new_bridge(brname)
        netcontrol.setup_gw(brname,gwname,gatewayipcidr,0,0)

        for wip in workers:
            if wip != self.master_ip:
                netcontrol.setup_gre(brname,wip)
        return [True, gatewayip]

    def remove_tasknet(self, task):
        taskid = task.id
        username = task.username
        brname = "docklet-batch-%s-%s"%(username, taskid)
        netcontrol.del_bridge(brname)

    def task_processor(self, task, sub_task_list):
        task.status = RUNNING
        self.jobmgr.report(task.username, task.id, 'running')

        # properties for transactio

        self.acquire_task_ips(task)
        task.gen_ips_from_base(self.base_ip)
        task.gen_hosts()
        #need to create hosts
        [success, gwip] = self.setup_tasknet(task, [sub_task.worker for sub_task in sub_task_list])
        if not success:
            self.release_task_ips(task)
            return [False, gwip]

        placed_workers = []

        start_all_vnode_success = True
        # start vc
        for sub_task in sub_task_list:
            vnode_info = sub_task.vnode_info
            vnode_info.vnode.hostname = "batch-" + str(vnode_info.vnodeid % task.max_size)
            if sub_task.vnode_started:
                continue

            username = sub_task.root_task.username
            #container_name = task.info.username + '-batch-' + task.info.id + '-' + str(instance_id) + '-' + task.info.token
            #if not username in self.user_containers.keys():
                #self.user_containers[username] = []
            #self.user_containers[username].append(container_name)
            ipaddr = task.ips[vnode_info.vnodeid % task.max_size] + "/" + str(32-self.task_cidr)
            brname = "docklet-batch-%s-%s" % (username, sub_task.root_task.id)
            networkinfo = Network(ipaddr=ipaddr, gateway=gwip, masterip=self.master_ip, brname=brname)
            vnode_info.vnode.network.CopyFrom(networkinfo)

            placed_workers.append(sub_task.worker)
            [success, msg] = self.start_vnode(sub_task)
            if not success:
                sub_task.waiting_for_retry("Fail to start vnode.")
                if sub_task.status == WAITING:
                    self.jobmgr.report(task.username, task.id, 'retrying', "Fail to start vnode.")
                sub_task.worker = None
                start_all_vnode_success = False

        if not start_all_vnode_success:
            return

        # start tasks
        for sub_task in sub_task_list:
            task_info = sub_task.command_info
            if task_info is None or sub_task.status == RUNNING:
                sub_task.status = RUNNING
                continue
            task_info.token = ''.join(random.sample(string.ascii_letters + string.digits, 8))

            [success, msg] = self.start_subtask(sub_task)
            if success:
                sub_task.status = RUNNING
            else:
                sub_task.waiting_for_retry("Fail to start task.")
                if sub_task.status == WAITING:
                    self.jobmgr.report(task.username, task.id, 'retrying', "Fail to start task.")

    def clear_sub_tasks(self, sub_task_list):
        for sub_task in sub_task_list:
            self.clear_sub_task(sub_task)

    def clear_sub_task(self, sub_task):
        if sub_task.task_started:
            self.stop_subtask(sub_task)
            #pass
        if sub_task.vnode_started:
            self.stop_vnode(sub_task)
            #pass

    @data_lock('stop_lock')
    def lazy_stop_task(self, taskid):
        self.lazy_stop_list.append(taskid)

    def stop_remove_task(self, task):
        if task is None:
            return
        self.logger.info("[taskmgr] stop and remove task(%s)"%task.id)
        self.clear_sub_tasks(task.subtask_list)
        self.release_task_ips(task)
        self.remove_tasknet(task)

    def check_task_completed(self, task):
        if task.status == RUNNING or task.status == WAITING:
            for sub_task in task.subtask_list:
                if sub_task.command_info != None and (sub_task.status == RUNNING or sub_task.status == WAITING):
                    return False
        self.logger.info('task %s finished, status %d, subtasks: %s' % (task.id, task.status, str([sub_task.status for sub_task in task.subtask_list])))
        self.stop_remove_task(task)
        self.lazy_delete_list.append(task)
        running_time, billing = task.get_billing()
        self.logger.info('task %s running_time:%s billing:%d'%(task.id, str(running_time), billing))
        running_time = math.ceil(running_time)
        if task.status == FAILED:
            self.jobmgr.report(task.username,task.id,"failed",task.failed_reason,task.subtask_list[0].max_retry_count+1, running_time, billing)
        else:
            self.jobmgr.report(task.username,task.id,'finished',running_time=running_time,billing=billing)
        return True

    # this method is called when worker send heart-beat rpc request
    def on_task_report(self, report):
        self.logger.info('[on_task_report] receive task report: id %s-%d, status %d' % (report.taskid, report.vnodeid, report.subTaskStatus))
        task = self.get_task(report.taskid)
        if task == None:
            self.logger.error('[on_task_report] task not found')
            return

        sub_task = task.subtask_list[report.vnodeid]
        if sub_task.command_info.token != report.token:
            self.logger.warning('[on_task_report] wrong token, %s %s' % (sub_task.command_info.token, report.token))
            return
        username = task.username
        # container_name = username + '-batch-' + task.info.id + '-' + str(report.instanceid) + '-' + report.token
        # self.user_containers[username].remove(container_name)

        if sub_task.status != RUNNING:
            self.logger.error('[on_task_report] receive task report when vnode is not running')

        #sub_task.status = report.subTaskStatus
        sub_task.status_reason = report.errmsg
        sub_task.task_started = False

        if report.subTaskStatus == FAILED or report.subTaskStatus == TIMEOUT:
            self.clear_sub_task(sub_task)
            sub_task.waiting_for_retry(report.errmsg)
            self.logger.info('task %s report failed, status %d, subtasks: %s' % (task.id, task.status, str([sub_task.status for sub_task in task.subtask_list])))
            if sub_task.status == WAITING:
                self.jobmgr.report(task.username, task.id, 'retrying', report.errmsg)
        elif report.subTaskStatus == OUTPUTERROR:
            self.clear_sub_task(sub_task)
            sub_task.status = FAILED
            task.status = FAILED
            task.failed_reason = report.errmsg
        elif report.subTaskStatus == COMPLETED:
            sub_task.status = report.subTaskStatus
            self.clear_sub_task(sub_task)

    # return task, workers
    def task_scheduler(self):
        # simple FIFO with priority
        self.logger.info('[task_scheduler] scheduling... (%d tasks remains)' % len(self.task_queue))

        for task in self.task_queue:
            if task in self.lazy_delete_list or task.id in self.lazy_stop_list:
                continue
            self.logger.info('task %s sub_tasks %s' % (task.id, str([sub_task.status for sub_task in task.subtask_list])))
            if self.check_task_completed(task):
                continue
            self.logger.info('schedule task %s sub_tasks %s' % (task.id, str([sub_task.status for sub_task in task.subtask_list])))

            if task.at_same_time:
                # parallel tasks
                if not self.has_waiting(task.subtask_list):
                    continue
                workers = self.find_proper_workers(task.subtask_list)
                if len(workers) == 0:
                    return None, None
                else:
                    for i in range(len(workers)):
                        task.subtask_list[i].worker = workers[i]
                    return task, task.subtask_list
            else:
                # traditional tasks
                has_waiting = False
                for sub_task in task.subtask_list:
                    if sub_task.status == WAITING:
                        has_waiting = True
                        workers = self.find_proper_workers([sub_task])
                        if len(workers) > 0:
                            sub_task.worker = workers[0]
                            return task, [sub_task]
                if has_waiting:
                    return None, None

        return None, None

    def has_waiting(self, sub_task_list):
        for sub_task in sub_task_list:
            if sub_task.status == WAITING:
                return True
        return False

    def find_proper_workers(self, sub_task_list, all_res=False):
        nodes = self.get_all_nodes()
        if nodes is None or len(nodes) == 0:
            self.logger.warning('[task_scheduler] running nodes not found')
            return None

        proper_workers = []
        has_waiting = False
        for sub_task in sub_task_list:
            if sub_task.status == WAITING:
                has_waiting = True
            if sub_task.worker is not None and sub_task.vnode_started:
                proper_workers.append(sub_task.worker)
                continue
            needs = sub_task.vnode_info.vnode.instance
            self.logger.info('sub_task %s-%d' %(sub_task.root_task.id, sub_task.vnode_info.vnodeid))
            self.logger.info(str(needs))
            #logger.info(needs)
            proper_worker = None
            for worker_ip, worker_info in nodes:
                self.logger.info('worker ip' + worker_ip)
                self.logger.info('cpu usage: ' + str(self.get_cpu_usage(worker_ip)))
                self.logger.info('gpu usage: ' + str(self.get_gpu_usage(worker_ip)))
                self.logger.info('worker_info: ' + str(worker_info))
                #logger.info(worker_info)
                #logger.info(self.get_cpu_usage(worker_ip))
                if needs.cpu + (not all_res) * self.get_cpu_usage(worker_ip) > worker_info['cpu']:
                    continue
                elif needs.memory > worker_info['memory']:
                    continue
                elif needs.disk > worker_info['disk']:
                    continue
                # try not to assign non-gpu task to a worker with gpu
                #if needs['gpu'] == 0 and worker_info['gpu'] > 0:
                    #continue
                elif needs.gpu + (not all_res) * self.get_gpu_usage(worker_ip) > worker_info['gpu']:
                    continue
                else:
                    worker_info['cpu'] -= needs.cpu
                    worker_info['memory'] -= needs.memory
                    worker_info['gpu'] -= needs.gpu
                    worker_info['disk'] -= needs.disk
                    proper_worker = worker_ip
                    break
            if proper_worker is not None:
                proper_workers.append(proper_worker)
            else:
                return []
        if has_waiting:
            return proper_workers
        else:
            return []

    def get_all_nodes(self):
        # cache running nodes
        # if self.all_nodes is not None and time.time() - self.last_nodes_info_update_time < self.nodes_info_update_interval:
        #     return self.all_nodes
        # get running nodes
        node_ips = self.nodemgr.get_batch_nodeips()
        all_nodes = [(node_ip, self.get_worker_resource_info(node_ip)) for node_ip in node_ips]
        return all_nodes

    def is_alive(self, worker):
        nodes = self.nodemgr.get_batch_nodeips()
        return worker in nodes

    def get_worker_resource_info(self, worker_ip):
        fetcher = self.monitor_fetcher(worker_ip)
        worker_info = fetcher.info
        info = {}
        info['cpu'] = len(worker_info['cpuconfig'])
        info['memory'] = (worker_info['meminfo']['buffers'] + worker_info['meminfo']['cached'] + worker_info['meminfo']['free']) / 1024 # (Mb)
        info['disk'] = sum([disk['free'] for disk in worker_info['diskinfo']]) / 1024 / 1024 # (Mb)
        info['gpu'] = len(worker_info['gpuinfo'])
        return info

    def get_cpu_usage(self, worker_ip):
        try:
            return self.cpu_usage[worker_ip]
        except:
            self.cpu_usage[worker_ip] = 0
            return 0


    def get_gpu_usage(self, worker_ip):
        try:
            return self.gpu_usage[worker_ip]
        except:
            self.gpu_usage[worker_ip] = 0
            return 0

    # save the task information into database
    # called when jobmgr assign task to taskmgr
    @data_lock('add_lock')
    def add_task(self, username, taskid, json_task, task_priority=1):
        # decode json string to object defined in grpc
        self.logger.info('[taskmgr add_task] receive task %s' % taskid)

        image_dict = {
            "private": Image.PRIVATE,
            "base": Image.BASE,
            "public": Image.PUBLIC
        }
        max_size = (1 << self.task_cidr) - 2
        if int(json_task['vnodeCount']) > max_size:
            # tell jobmgr
            self.jobmgr.report(username,taskid,"failed","vnodeCount exceed limits.")
            return False
        task = Task(
            task_id = taskid,
            username = username,
            # all vnode must be started at the same time
            at_same_time = 'atSameTime' in json_task.keys(),
            priority = task_priority,
            max_size = (1 << self.task_cidr) - 2,
            task_infos = [{
                'max_retry_count': int(json_task['retryCount']),
                'vnode_info': VNodeInfo(
                    taskid = taskid,
                    username = username,
                    vnode = VNode(
                        image = Image(
                            name = json_task['image'].split('_')[0], #json_task['cluster']['image']['name'],
                            type = image_dict[json_task['image'].split('_')[2]], #json_task['cluster']['image']['type'],
                            owner = username if not json_task['image'].split('_')[1] else json_task['image'].split('_')[1]), #json_task['cluster']['image']['owner']),
                        instance = Instance(
                            cpu = int(json_task['cpuSetting']),
                            memory = int(json_task['memorySetting']),
                            disk = int(json_task['diskSetting']),
                            gpu = int(json_task['gpuSetting'])),
                        mount = [Mount(
                                    provider = json_task['mapping'][mapping_key]['mappingProvider'],
                                    localPath = json_task['mapping'][mapping_key]['mappingMountpath'],
                                    remotePath = json_task['mapping'][mapping_key]['mappingBucketName'],
                                    accessKey = json_task['mapping'][mapping_key]['mappingAccessKey'],
                                    secretKey = json_task['mapping'][mapping_key]['mappingSecretKey'],
                                    other = json_task['mapping'][mapping_key]['mappingEndpoint']
                                    )
                                for mapping_key in json_task['mapping']] if 'mapping' in json_task else []
                        ),
                ),
                'command_info': TaskInfo(
                    taskid = taskid,
                    username = username,
                    parameters = Parameters(
                        command = Command(
                            commandLine = json_task['command'],
                            packagePath = json_task['srcAddr'],
                            envVars = {}),
                        stderrRedirectPath = json_task.get('stdErrRedPth',""),
                        stdoutRedirectPath = json_task.get('stdOutRedPth',"")),
                    timeout = int(json_task['expTime'])
                # commands are executed in all vnodes / only excuted in the first vnode
                # if in traditional mode, commands will be executed in all vnodes
                ) if (json_task['runon'] == 'all' or vnode_index == 0) else None
            } for vnode_index in range(int(json_task['vnodeCount']))])

        if task.at_same_time:
            workers = self.find_proper_workers(task.subtask_list, all_res=True)
            if len(workers) == 0:
                task.status = FAILED
                # tell jobmgr
                self.jobmgr.report(username,taskid,"failed","Resources needs exceed limits")
                return False
        else:
            for sub_task in task.subtask_list:
                workers = self.find_proper_workers([sub_task], all_res=True)
                if len(workers) == 0:
                    task.status = FAILED
                    # tell jobmgr
                    self.jobmgr.report(username,taskid,"failed","Resources needs exceed limits")
                    return False
        self.lazy_append_list.append(task)
        return True


    @data_lock('task_queue_lock')
    def get_task_list(self):
        return self.task_queue.copy()


    @data_lock('task_queue_lock')
    def get_task(self, taskid):
        for task in self.task_queue:
            if task.id == taskid:
                return task
        return None


    def set_jobmgr(self, jobmgr):
        self.jobmgr = jobmgr


    # get names of all the batch containers of the user
    def get_user_batch_containers(self,username):
        return []
        # if not username in self.user_containers.keys():
        #     return []
        # else:
        #     return self.user_containers[username]
