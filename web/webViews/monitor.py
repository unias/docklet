from flask import session
from webViews.view import normalView
from webViews.dockletrequest import dockletRequest


class statusView(normalView):
    template_path = "monitor/status.html"

    @classmethod
    def get(self):
        data = {
            "user": session['username'],
        }
        result = dockletRequest.post('/cluster/list/', data)
        clusters = result.get('clusters')
        result = dockletRequest.post('/monitor/user/quotainfo/', data)
        quotainfo = result.get('quotainfo')
        quotainfo['cpu'] = int(int(quotainfo['cpu'])/100000)
        print(quotainfo)
        if (result):
            containers = {}
            for cluster in clusters:
                data["clustername"] = cluster
                message = dockletRequest.post('/cluster/info/', data)
                if (message):
                   message = message.get('message')
                else:
                   self.error()
                containers[cluster] = message
            return self.render(self.template_path, clusters = clusters, quotainfo = quotainfo, containers = containers, user = session['username'])
        else:
            self.error()

class statusRealtimeView(normalView):
    template_path = "monitor/statusRealtime.html"
    node_name = ""

    @classmethod
    def get(self):
        data = {
            "user": session['username'],
        }
        result = dockletRequest.post('/monitor/vnodes/%s/basic_info'%(self.node_name), data)
        basic_info = result.get('monitor').get('basic_info')
        return self.render(self.template_path, node_name = self.node_name, user = session['username'], container = basic_info)

class hostsRealtimeView(normalView):
    template_path = "monitor/hostsRealtime.html"
    com_ip = ""

    @classmethod
    def get(self):
        data = {
            "user": session['username'],
        }
        result = dockletRequest.post('/monitor/hosts/%s/cpuconfig'%(self.com_ip), data)
        proc = result.get('monitor').get('cpuconfig')
        result = dockletRequest.post('/monitor/hosts/%s/osinfo'%(self.com_ip), data)
        osinfo = result.get('monitor').get('osinfo')
        result = dockletRequest.post('/monitor/hosts/%s/diskinfo'%(self.com_ip), data)
        diskinfos = result.get('monitor').get('diskinfo')

        return self.render(self.template_path, com_ip = self.com_ip, user = session['username'],processors = proc, OSinfo = osinfo, diskinfos = diskinfos)

class hostsConAllView(normalView):
    template_path = "monitor/hostsConAll.html"
    com_ip = ""

    @classmethod
    def get(self):
        data = {
            "user": session['username'],
        }
        result = dockletRequest.post('/monitor/hosts/%s/containerslist'%(self.com_ip), data)
        containers = result.get('monitor').get('containerslist')
        containerslist = []
        for container in containers:
            result = dockletRequest.post('/monitor/vnodes/%s/basic_info'%(container), data)
            basic_info = result.get('monitor').get('basic_info')
            containerslist.append(basic_info)
        return self.render(self.template_path, containerslist = containerslist, com_ip = self.com_ip, user = session['username'])

class hostsView(normalView):
    template_path = "monitor/hosts.html"

    @classmethod
    def get(self):
        data = {
            "user": session['username'],
        }
        result = dockletRequest.post('/monitor/listphynodes', data)
        iplist = result.get('monitor').get('allnodes')
        machines = []
        for ip in iplist:
           containers = {}
           result = dockletRequest.post('/monitor/hosts/%s/containers'%(ip), data)
           containers = result.get('monitor').get('containers')
           result = dockletRequest.post('/monitor/hosts/%s/status'%(ip), data)
           status = result.get('monitor').get('status')
           machines.append({'ip':ip,'containers':containers, 'status':status})
        #print(machines)
        return self.render(self.template_path, machines = machines, user = session['username'])

class monitorUserAllView(normalView):
    template_path = "monitor/monitorUserAll.html"

    @classmethod
    def get(self):
        data = {
            "user": session['username'],
        }
        result = dockletRequest.post('/monitor/listphynodes', data)
        userslist = [{'name':'root'},{'name':'libao'}]
        for user in userslist:
            result = dockletRequest.post('/monitor/user/%s/clustercnt'%(user['name']), data)
            user['clustercnt'] = result.get('monitor').get('clustercnt')
        return self.render(self.template_path, userslist = userslist, user = session['username'])
