import time, threading
import master.monitor

from utils.log import initlogging, logger
initlogging("docklet-jobmgr")

class JobMgr(object):

    # user: username
    # job: a json string
    # user submit a new job, add this job to queue and database
    # call add_task to add task information
    def add_job(self, user, job):
        pass

    # user: username
    # list a user's all job
    def list_jobs(self,user):
        pass

    # user: username
    # jobid: the id of job
    # get the information of a job, including the status, json description and other informationa
    # call get_task to get the task information
    def get_job(self, user, jobid):
        pass

    # job: a json string
    # this is a thread to process a job
    def job_processor(self, job):
        # according the DAG of job, add task to taskmanager
        # wait for all task completed and exit
        pass

    # this is a thread to schedule the jobs
    def job_scheduler(self):
        # choose a job from queue, create a job processor for it
        pass

    # load job information from etcd
    # initial a job queue and job schedueler
    def __init__(self, taskmgr):
        pass
