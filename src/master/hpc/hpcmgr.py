import threading, time, math, os

from utils import env
from utils.log import logger
from utils.lvmtool import sys_run

from master.hpc import hpccontroller

class HpcTask():
    def __init__(self, task_id, username, task_info, priority):
        self.id = task_id
        self.username = username
        self.task_info = task_info
        self.command = task_info['command']
        self.executable_file_path = os.path.join(task_info['execAddr'], self.command.split()[0]) if 'execAddr' in task_info else ''
        self.input_data_path = task_info['dataAddr'] if 'dataAddr' in task_info else ''
        self.working_directory = task_info['workingDir']
        self.nodes_count = int(task_info['vnodeCount'])
        self.runlog = task_info['runlog'] if 'runlog' in task_info else ''
        self.priority = int(time.time()) / 60 / 60 - priority
        self.status = 'pending'
        self.order = -1 # scheduling order of the task

        self.start_at = 0
        self.end_at = 0
        self.running_time = 0
        self.billing = 0

        # hpc info
        self.hpc_job_id = None


    def mark_start(self):
        if self.start_at == 0:
            self.start_at = time.time()


    def mark_stop(self):
        if self.start_at != 0:
            self.end_at = time.time()
            self.running_time = self.end_at - self.start_at
            self.billing = self.get_billing()


    def get_billing(self):
        hpc_price = 10 / 3600.0
        billing = self.running_time * self.nodes_count * hpc_price
        return math.ceil(billing)


class HpcMgr(threading.Thread):
    def __init__(self, max_parallels_tasks=10, scheduler_interval=5, external_logger=None):
        threading.Thread.__init__(self)
        self.thread_stop = False

        self.jobmgr = None
        self.task_queue = []
        self.running_tasks = []
        self.lazy_append_list = []
        self.lazy_delete_list = []
        self.lazy_stop_list = []

        self.max_parallels_tasks = max_parallels_tasks
        self.scheduler_interval = scheduler_interval

        self.fspath = env.getenv("FS_PREFIX")

        if external_logger == None:
            self.logger = logger
        else:
            self.logger = external_logger

    
    def set_jobmgr(self, jobmgr):
        self.jobmgr = jobmgr


    def run(self):
        while not self.thread_stop:
            try:
                hpccontroller.connect_ssh()
                break
            except Exception:
                self.logger.error('[hpcmgr] Authentication failed')
                time.sleep(self.scheduler_interval)
        while not self.thread_stop:
            if self.running_tasks:
                self.check_running_tasks_status()
            # self.logger.debug('[hpcmgr] scheduling... task_queue(%d) running_tasks(%d) lazy_append(%d)' % (len(self.task_queue), len(self.running_tasks), len(self.lazy_append_list)))
            self.sort_out_task_queue()

            if len(self.running_tasks) < self.max_parallels_tasks:
                for task in self.task_queue:
                    if task in self.running_tasks:
                        continue
                    if self.execute_task(task):
                        self.running_tasks.append(task)
                        if len(self.running_tasks) >= self.max_parallels_tasks:
                            break

            time.sleep(self.scheduler_interval)
        hpccontroller.disconnect_ssh()


    def stop(self):
        self.thread_stop = True
        self.logger.info('[hpcmgr] stop hpcmgr')


    def check_running_tasks_status(self):
        self.logger.info('[hpcmgr] checking running tasks status')
        succ, hpc_job_map = hpccontroller.check_recent_tasks()
        if not succ:
            return
        for task in self.running_tasks:
            if task.hpc_job_id not in hpc_job_map:
                continue
            status = hpc_job_map[task.hpc_job_id]['status']
            self.logger.info('[hpcmgr] task %s (hpc job id: %s) status: %s' % (task.id, task.hpc_job_id, status))
            if status == 'STARTING' or status == 'RUN':
                task.status = 'running'
                task.mark_start()
                self.jobmgr.report(task.username, task.id, 'running', 'running')
            elif status == 'DONE':
                task.status = 'finished'
                task.mark_stop()
                # self.download_runlog(task)
                self.download_output(task)
                self.jobmgr.report(task.username, task.id, 'finished', 'finished', running_time=task.running_time, billing=task.billing)
                self.lazy_delete_list.append(task)
            elif status == 'EXIT':
                task.status = 'failed'
                task.mark_stop()
                # self.download_runlog(task)
                self.jobmgr.report(task.username, task.id, 'failed', "Task failed", running_time=task.running_time, billing=task.billing)
                self.lazy_delete_list.append(task)

    
    def report_uploading_progress(self, task, msg, uploaded, total):
        self.jobmgr.report(task.username, task.id, 'running', '%s: %.2f%%' % (type, uploaded * 100.0/ total))

    # def write_hpc_output(self, task, msg):
    #     self.logger.info('[hpcmgr] writing runlog for task %s' % task.id)
    #     if task.runlog and task.runlog.startswith('~/nfs'):
    #         runlog = task.runlog.replace('{jobid}', task.id.split('_')[0])
    #         runlog = runlog.replace('~/nfs', '%s/global/users/%s/data' % (self.fspath, task.username))
    #         sys_run('mkdir -p %s' % runlog)
    #         runlog = os.path.join(runlog, '%s_%s_0_runlog.txt' % (task.id.split('_')[0], task.id.split('_')[1]))
    #         cmd = 'echo %s >> %s' % (msg, runlog)
    #         # sys_run(cmd)
    #         with open(runlog, "w") as f:
    #             f.writelines(msg)
    #         self.logger.debug('[hpcmgr] writing runlog for task %s: %s' % (task.id, cmd))
    #         # return hpccontroller.download_data(task.username, '#/%s/runlog' % task.id, runlog, mode=644, callback=lambda x, y: self.report_uploading_progress(task, 'Downloading runlog', x, y))
    #         return True

    def download_output(self,task):
        self.logger.info('[hpcmgr] downloading output for task %s' % task.id)
        # if task.runlog and task.runlog.startswith('~/nfs'):
        if task.runlog and task.runlog.startswith('/home/export/online3'):
            remote_output_path = task.runlog
            sys_run('mkdir -p %s/global/users/%s/data/batch_%s' % (self.fspath, task.username,task.id.split('_')[0]))
            local_output_path = '~/nfs/batch_%s' % task.id.split('_')[0]
            local_output_path = local_output_path.replace('~/nfs','%s/global/users/%s/data' % (self.fspath, task.username))
            return hpccontroller.download(remote_output_path, local_output_path, mode=644, callback=lambda x, y: self.report_uploading_progress(task, 'Downloading runlog', x, y))


    def download_runlog(self, task):
        self.logger.info('[hpcmgr] downloading runlog for task %s' % task.id)
        if task.runlog and task.runlog.startswith('~/nfs'):
            runlog = task.runlog.replace('{jobid}', task.id.split('_')[0])
            sys_run('mkdir -p %s' % runlog.replace('~/nfs', '%s/global/users/%s/data' % (self.fspath, task.username)))
            runlog = os.path.join(runlog, '%s_%s_0_runlog.txt' % (task.id.split('_')[0], task.id.split('_')[1]))
            return hpccontroller.download_data(task.username, '#/%s/runlog' % task.id, runlog, mode=644, callback=lambda x, y: self.report_uploading_progress(task, 'Downloading runlog', x, y))

    
    def prepare_file_system(self, task):
        self.logger.info('[hpcmgr] preparing file system for task %s' % task.id)
        # if task.executable_file_path:
        #     succ, msg = hpccontroller.upload_data(task.username, task.executable_file_path, task.working_directory, mode=755, callback=lambda x, y: self.report_uploading_progress(task, 'Uploading program', x, y))
        #     if not succ:
        #         return False, msg
        # if task.input_data_path:
        #     hpccontroller.upload_data(task.username, task.input_data_path, task.working_directory, mode=644, callback=lambda x, y: self.report_uploading_progress(task, 'Uploading data', x, y))
        #     if not succ:
        #         return False, msg
        return True, ''


    def execute_task(self, task):
        self.logger.info('[hpcmgr] execute task %s' % task.id)
        succ, msg = self.prepare_file_system(task)
        if not succ:
            logger.error('[hpcmgr] execute task failed: %s' % msg)
            task.status = 'failed'
            task.mark_stop()
            self.jobmgr.report(task.username, task.id, 'failed', msg)
            self.lazy_delete_list.append(task)
            return False

        # hpccontroller.hpc_exec('mkdir -p ~/online1/batch/%s' % task.id)
        # succ, ret = hpccontroller.submit_task_x86(
        #     task.command,
        #     task.username,
        #     task.working_directory,
        #     runlog='~/online1/batch/%s/runlog' % task.id,
        #     process_count=task.nodes_count)
        succ, ret = hpccontroller.submit_task(task.command,task.working_directory)
        if succ:
            task.hpc_job_id = ret
            return True
        else:
            logger.error('[hpcmgr] execute task failed: %s' % ret)
            task.status = 'failed'
            task.mark_stop()
            self.jobmgr.report(task.username, task.id, 'failed', ret)
            self.lazy_delete_list.append(task)
            return False

    
    def stop_task(self, task):
        self.logger.info('[hpcmgr] stop task %s' % task.id)
        if task.status == 'running':
            hpccontroller.kill_task_x86(task.hpc_job_id)
            task.status = 'stopped'
            task.mark_stop()
            return True
        return False


    def sort_out_task_queue(self):

        for task in self.running_tasks:
            if task.id in self.lazy_stop_list and self.stop_task(task):
                self.lazy_delete_list.append(task)
                self.logger.info('[hpcmgr] task %s stopped, running_time:%s billing:%d'%(task.id, str(task.running_time), task.billing))
                self.jobmgr.report(task.username, task.id,'stopped',running_time=task.running_time,billing=task.billing)

        while self.lazy_delete_list:
            task = self.lazy_delete_list.pop(0)
            try:
                self.task_queue.remove(task)
                self.running_tasks.remove(task)
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

    
    def add_task(self, username, taskid, json_task, task_priority=1):
        task = HpcTask(taskid, username, json_task, task_priority)
        self.logger.info('[hpcmgr] add task %s' % task.id)
        self.lazy_append_list.append(task)

    
    def lazy_stop_task(self, taskid):
        self.lazy_stop_list.append(taskid)
    

    def get_task_order(self, taskid):
        return 0