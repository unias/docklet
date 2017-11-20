from flask import session, redirect, request
from webViews.view import normalView
from webViews.dockletrequest import dockletRequest
from webViews.dashboard import *
from webViews.checkname import checkname
import time, re

class addClusterView(normalView):
    template_path = "addCluster.html"

    @classmethod
    def get(self):
        masterips = dockletRequest.post_to_all()
        images = dockletRequest.post("/image/list/",{},masterips[0].split("@")[0]).get("images")
        desc = dockletRequest.getdesc(masterips[0].split("@")[1])
        result = dockletRequest.post("/user/usageQuery/")
        quota = result.get("quota")
        usage = result.get("usage")
        default = result.get("default")
        restcpu = int(quota['cpu']) - int(usage['cpu'])
        restmemory = int(quota['memory']) - int(usage['memory'])
        restdisk = int(quota['disk']) - int(usage['disk'])
        if restcpu >= int(default['cpu']):
            defaultcpu = default['cpu']
        elif restcpu <= 0:
            defaultcpu = "0"
        else:
            defaultcpu = str(restcpu)

        if restmemory >= int(default['memory']):
            defaultmemory = default['memory']
        elif restmemory <= 0:
            defaultmemory = "0"
        else:
            defaultmemory = str(restmemory)

        if restdisk >= int(default['disk']):
            defaultdisk = default['disk']
        elif restdisk <= 0:
            defaultdisk = "0"
        else:
            defaultdisk = str(restdisk)

        defaultsetting = {
                'cpu': defaultcpu,
                'memory': defaultmemory,
                'disk': defaultdisk
                }
        if (result):
            return self.render(self.template_path, user = session['username'],masterips = masterips, images = images, quota = quota, usage = usage, defaultsetting = defaultsetting, masterdesc=desc)
        else:
            self.error()

class createClusterView(normalView):
    template_path = "dashboard.html"
    error_path = "error.html"

    @classmethod
    def post(self):
        masterip = self.masterip
        index1 = self.image.rindex("_")
        index2 = self.image[:index1].rindex("_")
        checkname(self.clustername)
        data = {
            "clustername": self.clustername,
            'imagename': self.image[:index2],
            'imageowner': self.image[index2+1:index1],
            'imagetype': self.image[index1+1:],
        }
        result = dockletRequest.post("/cluster/create/", dict(data, **(request.form)), masterip)
        if(result.get('success', None) == "true"):
           return redirect("/dashboard/")
            #return self.render(self.template_path, user = session['username'])
        else:
            return self.render(self.error_path, message = result.get('message'))

class descriptionMasterView(normalView):
    template_path = "description.html"

    @classmethod
    def get(self):
        return self.render(self.template_path, description=self.desc)

class descriptionImageView(normalView):
    template_path = "description.html"

    @classmethod
    def get(self):
        masterip = self.masterip
        index1 = self.image.rindex("_")
        index2 = self.image[:index1].rindex("_")
        data = {
                "imagename": self.image[:index2],
                "imageowner": self.image[index2+1:index1],
                "imagetype": self.image[index1+1:]
        }
        result = dockletRequest.post("/image/description/", data, masterip)
        if(result):
            description = result.get("message")
            return self.render(self.template_path, description = description)
        else:
            self.error()

class scaleoutView(normalView):
    error_path = "error.html"

    @classmethod
    def post(self):
        masterip = self.masterip
        index1 = self.image.rindex("_")
        index2 = self.image[:index1].rindex("_")
        data = {
            "clustername": self.clustername,
            'imagename': self.image[:index2],
            'imageowner': self.image[index2+1:index1],
            'imagetype': self.image[index1+1:]
        }
        result = dockletRequest.post("/cluster/scaleout/", dict(data, **(request.form)), masterip)
        if(result.get('success', None) == "true"):
            return redirect("/config/")
        else:
            return self.render(self.error_path, message = result.get('message'))

class scaleinView(normalView):
    error_path = "error.html"

    @classmethod
    def get(self):
        masterip = self.masterip
        data = {
            "clustername": self.clustername,
            "containername":self.containername
        }
        result = dockletRequest.post("/cluster/scalein/", data, masterip)
        if(result.get('success', None) == "true"):
            return redirect("/config/")
        else:
            return self.render(self.error_path, message = result.get('message'))

class listClusterView(normalView):
    template_path = "listCluster.html"

    @classmethod
    def get(self):
        masterip = self.masterip
        result = dockletRequest.post("/cluster/list/", {},  masterip)
        clusters = result.get("clusters")
        if(result):
            return self.render(self.template_path, user = session['username'], clusters = clusters)
        else:
            self.error()

class startClusterView(normalView):
    template_path = "dashboard.html"
    error_path = "error.html"

    @classmethod
    def get(self):
        masterip = self.masterip
        data = {
                "clustername": self.clustername
        }
        result = dockletRequest.post("/cluster/start/", data, masterip)
        if(result.get('success', None) == "true"):
           return redirect("/dashboard/")
            #return self.render(self.template_path, user = session['username'])
        else:
            return self.render(self.error_path, message = result.get('message'))

class stopClusterView(normalView):
    template_path = "dashboard.html"
    error_path = "error.html"

    @classmethod
    def get(self):
        masterip = self.masterip
        data = {
                "clustername": self.clustername
        }
        result = dockletRequest.post("/cluster/stop/", data, masterip)
        if(result.get('success', None) == "true"):
            return redirect("/dashboard/")
        else:
            return self.render(self.error_path, message = result.get('message'))

class flushClusterView(normalView):
    success_path = "opsuccess.html"
    failed_path = "opfailed.html"

    @classmethod
    def get(self):
        data = {
                "clustername": self.clustername,
                "from_lxc": self.containername
        }
        result = dockletRequest.post("/cluster/flush/", data)

        if(result):
            if result.get('success') == "true":
                return self.render(self.success_path, user = session['username'])
            else:
                return self.render(self.failed_path, user = session['username'])
        else:
            self.error()

class deleteClusterView(normalView):
    template_path = "dashboard.html"
    error_path = "error.html"

    @classmethod
    def get(self):
        masterip = self.masterip
        data = {
                "clustername": self.clustername
        }
        result = dockletRequest.post("/cluster/delete/", data, masterip)
        if(result.get('success', None) == "true"):
            return redirect("/dashboard/")
        else:
            return self.render(self.error_path, message = result.get('message'))

class detailClusterView(normalView):
    template_path = "listcontainer.html"

    @classmethod
    def get(self):
        masterip = self.masterip
        data = {
                "clustername": self.clustername
        }
        result = dockletRequest.post("/cluster/info/", data, masterip)
        if(result):
            message = result.get('message')
            containers = message['containers']
            status = message['status']
            return self.render(self.template_path, containers = containers, user = session['username'], clustername = self.clustername, status = status)
        else:
            self.error()

class saveImageView(normalView):
    template_path = "saveconfirm.html"
    success_path = "opsuccess.html"
    error_path = "error.html"

    @classmethod
    def post(self):
        masterip = self.masterip
        data = {
                "clustername": self.clustername,
                "image": self.imagename,
                "containername": self.containername,
                "description": self.description,
                "isforce": self.isforce
        }
        result = dockletRequest.post("/cluster/save/", data, masterip)
        if(result):
            if result.get('success') == 'true':
                #return self.render(self.success_path, user = session['username'])
                return redirect("/config/")
                #res = detailClusterView()
                #res.clustername = self.clustername
                #return res.as_view()
            else:
                if result.get('reason') == "exists":
                    return self.render(self.template_path, containername = self.containername, clustername = self.clustername, image = self.imagename, user = session['username'], description = self.description, masterip=masterip)
                else:
                    return self.render(self.error_path, message = result.get('message'))
        else:
            self.error()

class shareImageView(normalView):
    template_path = "dashboard.html"

    @classmethod
    def get(self):
        masterip = self.masterip
        data = {
                "image": self.image
        }
        result = dockletRequest.post("/image/share/", data, masterip)
        if(result):
            return redirect("/config/")
        else:
            self.error()

class unshareImageView(normalView):
    template_path = "dashboard.html"

    @classmethod
    def get(self):
        masterip = self.masterip
        data = {
                "image": self.image
        }
        result = dockletRequest.post("/image/unshare/", data, masterip)
        if(result):
            return redirect("/config/")
        else:
            self.error()

class deleteImageView(normalView):
    template_path = "dashboard.html"

    @classmethod
    def get(self):
        masterip = self.masterip
        data = {
                "image": self.image
        }
        result = dockletRequest.post("/image/delete/", data, masterip)
        if(result):
            return redirect("/config/")
        else:
            self.error()

class addproxyView(normalView):

    @classmethod
    def post(self):
        masterip = self.masterip
        data = {
            "clustername": self.clustername,
            "ip": self.ip,
            "port": self.port
        }
        result = dockletRequest.post("/addproxy/", data, masterip)
        if(result):
            return redirect("/config/")
        else:
            self.error()

class deleteproxyView(normalView):

    @classmethod
    def get(self):
        masterip = self.masterip
        data = {
            "clustername":self.clustername
        }
        result = dockletRequest.post("/deleteproxy/", data, masterip)
        if(result):
            return redirect("/config/")
        else:
            self.error()

    @classmethod
    def post(self):
        return self.get()

class configView(normalView):
    @classmethod
    def get(self):
        allimages = dockletRequest.post_to_all('/image/list/')
        for master in allimages:
            allimages[master] = allimages[master].get('images')
        allclusters = dockletRequest.post_to_all("/cluster/list/")
        for master in allclusters:
            allclusters[master] = allclusters[master].get('clusters')
        allclusters_info = {}
        clusters_info = {}
        data={}
        for master in allclusters:
            allclusters_info[master] = {}
            for cluster in allclusters[master]:
                data["clustername"] = cluster
                result = dockletRequest.post("/cluster/info/", data, master.split("@")[0]).get("message")
                allclusters_info[master][cluster] = result
        result = dockletRequest.post("/user/usageQuery/")
        quota = result.get("quota")
        usage = result.get("usage")
        default = result.get("default")
        restcpu = int(quota['cpu']) - int(usage['cpu'])
        restmemory = int(quota['memory']) - int(usage['memory'])
        restdisk = int(quota['disk']) - int(usage['disk'])
        if restcpu >= int(default['cpu']):
            defaultcpu = default['cpu']
        elif restcpu <= 0:
            defaultcpu = "0"
        else:
            defaultcpu = str(restcpu)

        if restmemory >= int(default['memory']):
            defaultmemory = default['memory']
        elif restmemory <= 0:
            defaultmemory = "0"
        else:
            defaultmemory = str(restmemory)

        if restdisk >= int(default['disk']):
            defaultdisk = default['disk']
        elif restdisk <= 0:
            defaultdisk = "0"
        else:
            defaultdisk = str(restdisk)

        defaultsetting = {
                'cpu': defaultcpu,
                'memory': defaultmemory,
                'disk': defaultdisk
                }
        return self.render("config.html", allimages = allimages, allclusters = allclusters_info, mysession=dict(session), quota = quota, usage = usage, defaultsetting = defaultsetting)

    @classmethod
    def post(self):
        return self.get()

class addPortMappingView(normalView):
    template_path = "error.html"

    @classmethod
    def post(self):
        data = {"clustername":request.form["clustername"],"node_name":request.form["node_name"],"node_ip":request.form["node_ip"],"node_port":request.form["node_port"]}
        result = dockletRequest.post('/port_mapping/add/',data, self.masterip)
        success = result.get("success")
        if success == "true":
            return redirect("/config/")
        else:
            return self.render(self.template_path, message = result.get("message"))

    @classmethod
    def get(self):
        return self.post()

class delPortMappingView(normalView):
    template_path = "error.html"

    @classmethod
    def post(self):
        data = {"clustername":self.clustername,"node_name":self.node_name,"node_port":self.node_port}
        result = dockletRequest.post('/port_mapping/delete/',data, self.masterip)
        success = result.get("success")
        if success == "true":
            return redirect("/config/")
        else:
            return self.render(self.template_path, message = result.get("message"))

    @classmethod
    def get(self):
        return self.post()
