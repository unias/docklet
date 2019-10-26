from flask import session, redirect, request
from webViews.view import normalView
from webViews.log import logger
from webViews.checkname import checkname
from webViews.dockletrequest import dockletRequest
from utils import env
import json

class batchJobListView(normalView):
    template_path = "batch/batch_list.html"

    @classmethod
    def get(self):
        masterips = dockletRequest.post_to_all()
        job_list = {}
        for ipname in masterips:
            ip = ipname.split("@")[0]
            result = dockletRequest.post("/batch/job/list/",{},ip)
            job_list[ip] = result.get("data")
            logger.debug("job_list[%s]: %s" % (ip,job_list[ip]))
        if True:
            return self.render(self.template_path, masterips=masterips, job_list=job_list)
        else:
            return self.error()

class createBatchJobView(normalView):
    template_path = "batch/batch_create.html"

    @classmethod
    def get(self):
        masterips = dockletRequest.post_to_all()
        images = {}
        for master in masterips:
            images[master.split("@")[0]] = dockletRequest.post("/image/list/",{},master.split("@")[0]).get("images")
        logger.info(images)

        data = {
            "user": session['username'],
        }
        allresult = dockletRequest.post_to_all('/monitor/listphynodes/', data)
        allmachines = {}
        for master in allresult:
            allmachines[master.split("@")[0]] = []
            iplist = allresult[master].get('monitor').get('allnodes')
            for ip in iplist:
                result = dockletRequest.post('/monitor/hosts/%s/gpuinfo/'%(ip), data, master.split("@")[0])
                gpuinfo = result.get('monitor').get('gpuinfo')
                allmachines[master.split("@")[0]].append(gpuinfo)

        pending_gpu_tasks = {}
        for master in masterips:
            pending_gpu_tasks[master.split("@")[0]] = dockletRequest.post("/monitor/pending_gpu_tasks/",{},master.split("@")[0]).get("monitor").get("pending_tasks")

        return self.render(self.template_path, masterips=masterips, images=images, allmachines=allmachines, pending_gpu_tasks=pending_gpu_tasks)


class infoBatchJobView(normalView):
    template_path = "batch/batch_info.html"
    error_path = "error.html"
    masterip = ""
    jobid = ""

    @classmethod
    def get(self):
        data = {
            'jobid':self.jobid
        }
        result = dockletRequest.post("/batch/job/info/",data,self.masterip)
        data = result.get("data")
        logger.info(str(data))
        #logger.debug("job_list: %s" % job_list)
        if result.get('success',"") == "true":
            return self.render(self.template_path, masterip=self.masterip, jobinfo=data)
        else:
            return self.render(self.error_path, message = result.get('message'))

class addBatchJobView(normalView):
    template_path = "batch/batch_list.html"
    error_path = "error.html"

    @classmethod
    def post(self):
        masterip = self.masterip
        result = dockletRequest.post("/batch/job/add/", self.job_data, masterip)
        if result.get('success', None) == "true":
            return redirect('/batch_jobs/')
        else:
            return self.render(self.error_path, message = result.get('message'))

class stopBatchJobView(normalView):
    template_path = "batch/batch_list.html"
    error_path = "error.html"

    @classmethod
    def get(self):
        masterip = self.masterip
        data = {'jobid':self.jobid}
        result = dockletRequest.post("/batch/job/stop/", data, masterip)
        if result.get('success', None) == "true":
            return redirect('/batch_jobs/')
        else:
            return self.render(self.error_path, message = result.get('message'))

class outputBatchJobView(normalView):
    template_path = "batch/batch_output.html"
    masterip = ""
    jobid = ""
    taskid = ""
    vnodeid = ""
    issue = ""

    @classmethod
    def get(self):
        data = {
            'jobid':self.jobid,
            'taskid':self.taskid,
            'vnodeid':self.vnodeid,
            'issue':self.issue
        }
        result = dockletRequest.post("/batch/job/output/",data,self.masterip)
        output = result.get("data")
        #logger.debug("job_list: %s" % job_list)
        if result.get('success',"") == "true":
            return self.render(self.template_path, masterip=self.masterip, jobid=self.jobid,
                               taskid=self.taskid, vnodeid=self.vnodeid, issue=self.issue, output=output)
        else:
            return self.error()
