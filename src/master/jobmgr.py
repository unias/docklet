import time, threading, random, string, os, traceback, requests
import master.monitor
import subprocess,json
from functools import wraps
from datetime import datetime

from utils.log import initlogging, logger
from utils.model import db, Batchjob, Batchtask
from utils import env

def db_commit():
    try:
        db.session.commit()
    except Exception as err:
        db.session.rollback()
        logger.error(traceback.format_exc())
        raise

class BatchJob(object):
    def __init__(self, jobid, user, job_info, old_job_db=None):
        if old_job_db is None:
            self.job_db = Batchjob(jobid,user,job_info['jobName'],int(job_info['jobPriority']))
        else:
            self.job_db = old_job_db
            self.job_db.clear()
            job_info = {}
            job_info['jobName'] = self.job_db.name
            job_info['jobPriority'] = self.job_db.priority
            all_tasks = self.job_db.tasks.all()
            job_info['tasks'] = {}
            for t in all_tasks:
                job_info['tasks'][t.idx] = json.loads(t.config)
        self.user = user
        #self.raw_job_info = job_info
        self.job_id = jobid
        self.job_name = job_info['jobName']
        self.job_priority = int(job_info['jobPriority'])
        self.lock = threading.Lock()
        self.tasks = {}
        self.dependency_out = {}
        self.tasks_cnt = {'pending':0, 'scheduling':0, 'running':0, 'retrying':0, 'failed':0, 'finished':0, 'stopped':0}

        #init self.tasks & self.dependency_out & self.tasks_cnt
        logger.debug("Init BatchJob user:%s job_name:%s create_time:%s" % (self.job_db.username, self.job_db.name, str(self.job_db.create_time)))
        raw_tasks = job_info["tasks"]
        self.tasks_cnt['pending'] = len(raw_tasks.keys())
        for task_idx in raw_tasks.keys():
            task_info = raw_tasks[task_idx]
            if old_job_db is None:
                task_db = Batchtask(jobid+"_"+task_idx, task_idx, task_info)
                self.job_db.tasks.append(task_db)
            else:
                task_db = Batchtask.query.get(jobid+"_"+task_idx)
                task_db.clear()
            self.tasks[task_idx] = {}
            self.tasks[task_idx]['id'] = jobid+"_"+task_idx
            self.tasks[task_idx]['config'] = task_info
            self.tasks[task_idx]['db'] = task_db
            self.tasks[task_idx]['status'] = 'pending'
            self.tasks[task_idx]['dependency'] = []
            dependency = task_info['dependency'].strip().replace(' ', '').split(',')
            if len(dependency) == 1 and dependency[0] == '':
                continue
            for d in dependency:
                if not d in raw_tasks.keys():
                    raise ValueError('task %s is not defined in the dependency of task %s' % (d, task_idx))
                self.tasks[task_idx]['dependency'].append(d)
                if not d in self.dependency_out.keys():
                    self.dependency_out[d] = []
                self.dependency_out[d].append(task_idx)

        if old_job_db is None:
            db.session.add(self.job_db)
        db_commit()

        self.log_status()
        logger.debug("BatchJob(id:%s) dependency_out: %s" % (self.job_db.id, json.dumps(self.dependency_out, indent=3)))

    def data_lock(f):
        @wraps(f)
        def new_f(self, *args, **kwargs):
            self.lock.acquire()
            try:
                result = f(self, *args, **kwargs)
            except Exception as err:
                self.lock.release()
                raise err
            self.lock.release()
            return result
        return new_f

    # return the tasks without dependencies
    @data_lock
    def get_tasks_no_dependency(self,update_status=False):
        logger.debug("Get tasks without dependencies of BatchJob(id:%s)" % self.job_db.id)
        ret_tasks = []
        for task_idx in self.tasks.keys():
            if (self.tasks[task_idx]['status'] == 'pending' and
                len(self.tasks[task_idx]['dependency']) == 0):
                if update_status:
                    self.tasks_cnt['pending'] -= 1
                    self.tasks_cnt['scheduling'] += 1
                    self.tasks[task_idx]['db'] = Batchtask.query.get(self.tasks[task_idx]['id'])
                    self.tasks[task_idx]['db'].status = 'scheduling'
                    self.tasks[task_idx]['status'] = 'scheduling'
                task_name = self.tasks[task_idx]['db'].id
                ret_tasks.append([task_name, self.tasks[task_idx]['config'], self.job_priority])
        self.log_status()
        db_commit()
        return ret_tasks

    @data_lock
    def stop_job(self):
        self.job_db = Batchjob.query.get(self.job_id)
        self.job_db.status = 'stopping'
        db_commit()

    # update status of this job based
    def _update_job_status(self):
        allcnt = len(self.tasks.keys())
        if self.tasks_cnt['failed'] != 0:
            self.job_db.status = 'failed'
            self.job_db.end_time = datetime.now()
        elif self.tasks_cnt['finished'] == allcnt:
            self.job_db.status = 'done'
            self.job_db.end_time = datetime.now()
        elif self.job_db.status == 'stopping':
            if self.tasks_cnt['running'] == 0 and self.tasks_cnt['scheduling'] == 0 and self.tasks_cnt['retrying'] == 0:
                self.job_db.status = 'stopped'
                self.job_db.end_time = datetime.now()
        elif self.tasks_cnt['running'] != 0 or self.tasks_cnt['retrying'] != 0:
            self.job_db.status = 'running'
        else:
            self.job_db.status = 'pending'
        db_commit()

    # start run a task, update status
    @data_lock
    def update_task_running(self, task_idx):
        logger.debug("Update status of task(idx:%s) of BatchJob(id:%s) running." % (task_idx, self.job_id))
        old_status = self.tasks[task_idx]['status']
        if old_status == 'stopping':
            logger.info("Task(idx:%s) of BatchJob(id:%s) has been stopped."% (task_idx, self.job_id))
            return
        self.tasks_cnt[old_status] -= 1
        self.tasks[task_idx]['status'] = 'running'
        self.tasks[task_idx]['db'] = Batchtask.query.get(self.tasks[task_idx]['id'])
        self.tasks[task_idx]['db'].status = 'running'
        self.tasks[task_idx]['db'].start_time = datetime.now()
        self.tasks_cnt['running'] += 1
        self.job_db = Batchjob.query.get(self.job_id)
        self._update_job_status()
        self.log_status()

    # a task has finished, update dependency and return tasks without dependencies
    @data_lock
    def finish_task(self, task_idx, running_time, billing):
        if task_idx not in self.tasks.keys():
            logger.error('Task_idx %s not in job. user:%s job_name:%s job_id:%s'%(task_idx, self.user, self.job_name, self.job_id))
            return []
        logger.debug("Task(idx:%s) of BatchJob(id:%s) has finished(running_time=%d,billing=%d). Update dependency..." % (task_idx, self.job_id, running_time, billing))
        old_status = self.tasks[task_idx]['status']
        if old_status == 'stopping':
            logger.info("Task(idx:%s) of BatchJob(id:%s) has been stopped."% (task_idx, self.job_id))
            return
        self.tasks_cnt[old_status] -= 1
        self.tasks[task_idx]['status'] = 'finished'
        self.tasks[task_idx]['db'] = Batchtask.query.get(self.tasks[task_idx]['id'])
        self.tasks[task_idx]['db'].status = 'finished'
        self.tasks[task_idx]['db'].tried_times += 1
        self.tasks[task_idx]['db'].running_time = running_time
        self.tasks[task_idx]['db'].end_time = datetime.now()
        self.tasks[task_idx]['db'].billing = billing
        self.tasks[task_idx]['db'].failed_reason = ""
        self.job_db = Batchjob.query.get(self.job_id)
        self.job_db.billing += billing
        self.tasks_cnt['finished'] += 1

        if task_idx not in self.dependency_out.keys():
            self._update_job_status()
            self.log_status()
            return []
        ret_tasks = []
        for out_idx in self.dependency_out[task_idx]:
            try:
                self.tasks[out_idx]['dependency'].remove(task_idx)
            except Exception as err:
                logger.warning(traceback.format_exc())
                continue
            if (self.tasks[out_idx]['status'] == 'pending' and
                len(self.tasks[out_idx]['dependency']) == 0):
                self.tasks_cnt['pending'] -= 1
                self.tasks_cnt['scheduling'] += 1
                self.tasks[out_idx]['status'] = 'scheduling'
                self.tasks[out_idx]['db'] = Batchtask.query.get(self.tasks[out_idx]['id'])
                self.tasks[out_idx]['db'].status = 'scheduling'
                task_name = self.job_id + '_' + out_idx
                ret_tasks.append([task_name, self.tasks[out_idx]['config'], self.job_priority])
        self._update_job_status()
        self.log_status()
        return ret_tasks

    # update retrying status of task
    @data_lock
    def update_task_retrying(self, task_idx, reason, tried_times):
        logger.debug("Update status of task(idx:%s) of BatchJob(id:%s) retrying. reason:%s tried_times:%d" % (task_idx, self.job_id, reason, int(tried_times)))
        old_status = self.tasks[task_idx]['status']
        if old_status == 'stopping':
            logger.info("Task(idx:%s) of BatchJob(id:%s) has been stopped."% (task_idx, self.job_id))
            return
        self.tasks_cnt[old_status] -= 1
        self.tasks_cnt['retrying'] += 1
        self.tasks[task_idx]['db'] = Batchtask.query.get(self.tasks[task_idx]['id'])
        self.tasks[task_idx]['db'].status = 'retrying'
        self.tasks[task_idx]['db'].failed_reason = reason
        self.tasks[task_idx]['db'].tried_times += 1
        self.tasks[task_idx]['status'] = 'retrying'
        self.job_db = Batchjob.query.get(self.job_id)
        self._update_job_status()
        self.log_status()

    # update failed status of task
    @data_lock
    def update_task_failed(self, task_idx, reason, tried_times, running_time, billing):
        logger.debug("Update status of task(idx:%s) of BatchJob(id:%s) failed. reason:%s tried_times:%d" % (task_idx, self.job_id, reason, int(tried_times)))
        old_status = self.tasks[task_idx]['status']
        self.tasks_cnt[old_status] -= 1
        self.tasks_cnt['failed'] += 1
        self.tasks[task_idx]['status'] = 'failed'
        self.tasks[task_idx]['db'] = Batchtask.query.get(self.tasks[task_idx]['id'])
        self.tasks[task_idx]['db'].status = 'failed'
        self.tasks[task_idx]['db'].failed_reason = reason
        self.tasks[task_idx]['db'].tried_times += 1
        self.tasks[task_idx]['db'].end_time = datetime.now()
        self.tasks[task_idx]['db'].running_time = running_time
        self.tasks[task_idx]['db'].billing = billing
        self.job_db = Batchjob.query.get(self.job_id)
        self.job_db.billing += billing
        self._update_job_status()
        self.log_status()

    @data_lock
    def update_task_stopped(self, task_idx, running_time, billing):
        logger.debug("Update status of task(idx:%s) of BatchJob(id:%s) stopped.running_time:%d billing:%d" % (task_idx, self.job_id, int(running_time), billing))
        old_status = self.tasks[task_idx]['status']
        if old_status == 'failed' or old_status == 'finished' or old_status == 'stopped':
            logger.info("task(idx:%s) of BatchJob(id:%s) has been done."%(task_idx, self.job_id))
            return False
        self.tasks_cnt[old_status] -= 1
        self.tasks_cnt['stopped'] += 1
        self.tasks[task_idx]['status'] = 'stopped'
        self.tasks[task_idx]['db'] = Batchtask.query.get(self.tasks[task_idx]['id'])
        self.tasks[task_idx]['db'].status = 'stopped'
        self.tasks[task_idx]['db'].end_time = datetime.now()
        self.tasks[task_idx]['db'].running_time = running_time
        self.tasks[task_idx]['db'].billing = billing
        self.job_db = Batchjob.query.get(self.job_id)
        self.job_db.billing += billing
        self._update_job_status()
        self.log_status()
        return True

    # print status for debuging
    def log_status(self):
        task_copy = {}
        for task_idx in self.tasks.keys():
            task_copy[task_idx] = {}
            task_copy[task_idx]['status'] = self.tasks[task_idx]['status']
            task_copy[task_idx]['dependency'] = self.tasks[task_idx]['dependency']
        logger.debug("BatchJob(id:%s) tasks status: %s" % (self.job_id, json.dumps(task_copy, indent=3)))
        logger.debug("BatchJob(id:%s)  tasks_cnt: %s" % (self.job_id, self.tasks_cnt))
        logger.debug("BatchJob(id:%s)  job_status: %s" %(self.job_id, self.job_db.status))


class JobMgr():
    # load job information from etcd
    # initial a job queue and job schedueler
    def __init__(self, taskmgr):
        logger.info("Init jobmgr...")
        try:
            Batchjob.query.all()
        except:
            db.create_all(bind='__all__')
        self.job_map = {}
        self.taskmgr = taskmgr
        self.fspath = env.getenv('FS_PREFIX')
        self.lock = threading.Lock()
        self.userpoint = "http://" + env.getenv('USER_IP') + ":" + str(env.getenv('USER_PORT'))
        self.auth_key = env.getenv('AUTH_KEY')

        self.recover_jobs()

    def recover_jobs(self):
        logger.info("Rerun the unfailed and unfinished jobs...")
        try:
            rejobs = Batchjob.query.filter(~Batchjob.status.in_(['done','failed','stopped']))
            rejobs = rejobs.order_by(Batchjob.create_time).all()
            for rejob in rejobs:
                logger.info("Rerun job: "+rejob.id)
                logger.debug(str(rejob))
                job = BatchJob(rejob.id, rejob.username, None, rejob)
                self.job_map[job.job_id] = job
                self.process_job(job)
        except Exception as err:
            logger.error(traceback.format_exc())

    def charge_beans(self,username,billing):
        logger.debug("Charge user(%s) for %d beans"%(username, billing))
        data = {"owner_name":username,"billing":billing, "auth_key":self.auth_key}
        url = "/billing/beans/"
        return requests.post(self.userpoint+url,data=data).json()

    def add_lock(f):
        @wraps(f)
        def new_f(self, *args, **kwargs):
            self.lock.acquire()
            try:
                result = f(self, *args, **kwargs)
            except Exception as err:
                self.lock.release()
                raise err
            self.lock.release()
            return result
        return new_f

    @add_lock
    def create_job(self, user, job_info):
        jobid = self.gen_jobid()
        job = BatchJob(jobid, user, job_info)
        return job

    # user: username
    # job_info: a json string
    # user submit a new job, add this job to queue and database
    def add_job(self, user, job_info):
        try:
            job = self.create_job(user, job_info)
            self.job_map[job.job_id] = job
            self.process_job(job)
        except ValueError as err:
            logger.error(err)
            return [False, err.args[0]]
        except Exception as err:
            logger.error(traceback.format_exc())
            #logger.error(err)
            return [False, err.args[0]]
        return [True, "add batch job success"]

    # user: username
    # jobid: the id of job
    def stop_job(self, user, job_id):
        logger.info("[jobmgr] stop job(id:%s) user(%s)"%(job_id, user))
        if job_id not in self.job_map.keys():
            return [False,"Job id %s does not exists! Maybe it has been finished."%job_id]
        try:
            job = self.job_map[job_id]
            if job.job_db.status == 'done' or job.job_db.status == 'failed':
                return [True,""]
            if job.user != user and user != 'root':
                raise Exception("Wrong User.")
            for task_idx in job.tasks.keys():
                taskid = job_id + '_' + task_idx
                self.taskmgr.lazy_stop_task(taskid)
            job.stop_job()
        except Exception as err:
            logger.error(traceback.format_exc())
            #logger.error(err)
            return [False, err.args[0]]
        return [True,""]

    # user: username
    # list a user's all job
    def list_jobs(self,user):
        alljobs = Batchjob.query.filter_by(username=user).all()
        res = []
        for job in alljobs:
            jobdata = json.loads(str(job))
            tasks = job.tasks.all()
            jobdata['tasks'] = [t.idx for t in tasks]
            tasks_vnodeCount = {}
            for t in tasks:
                tasks_vnodeCount[t.idx] = int(json.loads(t.config)['vnodeCount'])
            jobdata['tasks_vnodeCount'] = tasks_vnodeCount
            res.append(jobdata)
        return res

    # list all users' jobs
    def list_all_jobs(self):
        alljobs = Batchjob.query.all()
        res = []
        for job in alljobs:
            jobdata = json.loads(str(job))
            tasks = job.tasks.all()
            jobdata['tasks'] = [t.idx for t in tasks]
            tasks_vnodeCount = {}
            for t in tasks:
                tasks_vnodeCount[t.idx] = int(json.loads(t.config)['vnodeCount'])
            jobdata['tasks_vnodeCount'] = tasks_vnodeCount
            res.append(jobdata)
        return res

    # user: username
    # jobid: the id of job
    # get the information of a job, including the status, json description and other information
    def get_job(self, user, job_id):
        job = Batchjob.query.get(job_id)
        if job is None:
            return [False, "Jobid(%s) does not exist."%job_id]
        if job.username != user and user != 'root':
            return [False, "Wrong User!"]
        jobdata = json.loads(str(job))
        tasks = job.tasks.order_by(Batchtask.idx).all()
        tasksdata = [json.loads(str(t)) for t in tasks]

        for i in range(len(tasksdata)):
            if tasksdata[i]['status'] == 'scheduling':
                order = self.taskmgr.get_task_order(tasksdata[i]['id'])
                tasksdata[i]['order'] = order
        jobdata['tasks'] = tasksdata

        return [True, jobdata]

    # check if a job exists
    def is_job_exist(self, job_id):
        return Batchjob.query.get(job_id) != None

    # generate a random job id
    def gen_jobid(self):
        datestr = datetime.now().strftime("%y%m%d")
        job_id = datestr+''.join(random.sample(string.ascii_letters + string.digits, 3))
        while self.is_job_exist(job_id):
            job_id = datestr+''.join(random.sample(string.ascii_letters + string.digits, 3))
        return job_id

    # add tasks into taskmgr's queue
    def add_task_taskmgr(self, user, tasks):
        for task_name, task_info, task_priority in tasks:
            if not task_info:
                logger.error("task_info does not exist! task_name(%s)" % task_name)
                return False
            else:
                logger.debug("Add task(name:%s) with priority(%s) to taskmgr's queue." % (task_name, task_priority) )
                self.taskmgr.add_task(user, task_name, task_info, task_priority)
        return True

    # to process a job, add tasks without dependencies of the job into taskmgr
    def process_job(self, job):
        tasks = job.get_tasks_no_dependency(True)
        return self.add_task_taskmgr(job.user, tasks)

    # report task status from taskmgr when running, failed and finished
    # task_name: job_id + '_' + task_idx
    # status: 'running', 'finished', 'retrying', 'failed', 'stopped'
    # reason: reason for failure or retrying, such as "FAILED", "TIMEOUT", "OUTPUTERROR"
    # tried_times: how many times the task has been tried.
    def report(self, user, task_name, status, reason="", tried_times=1, running_time=0, billing=0):
        split_task_name = task_name.split('_')
        if len(split_task_name) != 2:
            logger.error("[jobmgr report]Illegal task_name(%s) report from taskmgr" % task_name)
            return
        if billing > 0 and (status == 'failed' or status == 'finished'):
            self.charge_beans(user, billing)
        job_id, task_idx = split_task_name
        if job_id not in self.job_map.keys():
            logger.error("[jobmgr report]jobid(%s) does not exist. task_name(%s)" % (job_id,task_name))
            #update data in db
            taskdb = Batchtask.query.get(task_name)
            if (taskdb is None or taskdb.status == 'finished' or
               taskdb.status == 'failed' or taskdb.status == 'stopped'):
                return
            taskdb.status = status
            if status == 'failed':
                taskdb.failed_reason = reason
            if status == 'failed' or status == 'stopped' or status == 'finished':
                taskdb.end_time = datetime.now()
            if billing > 0:
                taskdb.running_time = running_time
                taskdb.billing = billing
            db_commit()
            return
        job  = self.job_map[job_id]
        if status == "running":
            #logger.debug(str(job.job_db))
            job.update_task_running(task_idx)
            #logger.debug(str(job.job_db))
        elif status == "finished":
            #logger.debug(str(job.job_db))
            next_tasks = job.finish_task(task_idx, running_time, billing)
            ret = self.add_task_taskmgr(user, next_tasks)
            #logger.debug(str(job.job_db))
        elif status == "retrying":
            job.update_task_retrying(task_idx, reason, tried_times)
        elif status == "failed":
            job.update_task_failed(task_idx, reason, tried_times, running_time, billing)
        elif status == "stopped":
            if job.update_task_stopped(task_idx, running_time, billing) and billing > 0:
                self.charge_beans(user, billing)
        if job.job_db.status == 'done' or job.job_db.status == 'failed' or job.job_db.status == 'stopped':
            del self.job_map[job_id]

    # Get Batch job stdout or stderr from its file
    def get_output(self, username, jobid, taskid, vnodeid, issue):
        filename = jobid + "_" + taskid + "_" + vnodeid + "_" + issue + ".txt"
        fpath = "%s/global/users/%s/data/batch_%s/%s" % (self.fspath,username,jobid,filename)
        logger.info("Get output from:%s" % fpath)
        try:
            ret = subprocess.run('tail -n 100 ' + fpath,stdout=subprocess.PIPE,stderr=subprocess.STDOUT, shell=True)
            if ret.returncode != 0:
                raise IOError(ret.stdout.decode(encoding="utf-8"))
        except Exception as err:
            logger.error(traceback.format_exc())
            return ""
        else:
            return ret.stdout.decode(encoding="utf-8")
