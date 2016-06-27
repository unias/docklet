from flask import session, redirect
from webViews.view import normalView
from webViews.dockletrequest import dockletRequest
from webViews.dashboard import *
from webViews.checkname import checkname
import time, re

class addClusterView(normalView):
    template_path = "addCluster.html"

    @classmethod
    def get(self):
        result = dockletRequest.post("/image/list/")
        images = result.get("images")
        if (result):
            return self.render(self.template_path, user = session['username'], images = images)
        else:
            self.error()

class createClusterView(normalView):
    template_path = "dashboard.html"
    error_path = "error.html"

    @classmethod
    def post(self):
        index1 = self.image.rindex("_")
        index2 = self.image[:index1].rindex("_")
        checkname(self.clustername)
        data = {
            "clustername": self.clustername,
            'imagename': self.image[:index2],
            'imageowner': self.image[index2+1:index1],
            'imagetype': self.image[index1+1:],
        }
        result = dockletRequest.post("/cluster/create/", data)
        if(result.get('success', None) == "true"):
           return redirect("/dashboard/")
            #return self.render(self.template_path, user = session['username'])
        else:
            return self.render(self.error_path, message = result.get('message'))

class descriptionImageView(normalView):
    template_path = "image_description.html"

    @classmethod
    def get(self):
        index1 = self.image.rindex("_")
        index2 = self.image[:index1].rindex("_")
        data = {
                "imagename": self.image[:index2],
                "imageowner": self.image[index2+1:index1],
                "imagetype": self.image[index1+1:]
        }
        result = dockletRequest.post("/image/description/", data)
        if(result):
            description = result.get("message")
            return self.render(self.template_path, description = description)
        else:
            self.error()

class scaleoutView(normalView):
    error_path = "error.html"

    @classmethod
    def post(self):
        index1 = self.image.rindex("_")
        index2 = self.image[:index1].rindex("_")
        data = {
            "clustername": self.clustername,
            'imagename': self.image[:index2],
            'imageowner': self.image[index2+1:index1],
            'imagetype': self.image[index1+1:]
        }
        result = dockletRequest.post("/cluster/scaleout/", data)
        if(result.get('success', None) == "true"):
            return redirect("/config/")
        else:
            return self.render(self.error_path, message = result.get('message'))

class scaleinView(normalView):
    @classmethod
    def get(self):
        data = {
            "clustername": self.clustername,
            "containername":self.containername
        }
        result = dockletRequest.post("/cluster/scalein/", data)
        if(result):
            return redirect("/config/")
        else:
            self.error()

class listClusterView(normalView):
    template_path = "listCluster.html"

    @classmethod
    def get(self):
        result = dockletRequest.post("/cluster/list/")
        clusters = result.get("clusters")
        if(result):
            return self.render(self.template_path, user = session['username'], clusters = clusters)
        else:
            self.error()

class startClusterView(normalView):
    template_path = "dashboard.html"

    @classmethod
    def get(self):
        data = {
                "clustername": self.clustername
        }
        result = dockletRequest.post("/cluster/start/", data)
        if(result):
            return redirect("/dashboard/")
        else:
            return self.error()

class stopClusterView(normalView):
    template_path = "dashboard.html"

    @classmethod
    def get(self):
        data = {
                "clustername": self.clustername
        }
        result = dockletRequest.post("/cluster/stop/", data)
        if(result):
            return redirect("/dashboard/")
        else:
            return self.error()

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

    @classmethod
    def get(self):
        data = {
                "clustername": self.clustername
        }
        result = dockletRequest.post("/cluster/delete/", data)
        if(result):
            return redirect("/dashboard/")
        else:
            return self.error()

class detailClusterView(normalView):
    template_path = "listcontainer.html"

    @classmethod
    def get(self):
        data = {
                "clustername": self.clustername
        }
        result = dockletRequest.post("/cluster/info/", data)
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
        data = {
                "clustername": self.clustername,
                "image": self.imagename,
                "containername": self.containername,
                "description": self.description,
                "isforce": self.isforce
        }
        result = dockletRequest.post("/cluster/save/", data)
        if(result):
            if result.get('success') == 'true':
                #return self.render(self.success_path, user = session['username'])
                return redirect("/config/") 
                #res = detailClusterView()
                #res.clustername = self.clustername
                #return res.as_view()
            else:
                if result.get('reason') == "exists":
                    return self.render(self.template_path, containername = self.containername, clustername = self.clustername, image = self.imagename, user = session['username'], description = self.description)
                else:
                    return self.render(self.error_path, message = result.get('message'))
        else:
            self.error()

class shareImageView(normalView):
    template_path = "dashboard.html"

    @classmethod
    def get(self):
        data = {
                "image": self.image
        }
        result = dockletRequest.post("/image/share/", data)
        if(result):
            return redirect("/config/")
        else:
            self.error()

class unshareImageView(normalView):
    template_path = "dashboard.html"

    @classmethod
    def get(self):
        data = {
                "image": self.image
        }
        result = dockletRequest.post("/image/unshare/", data)
        if(result):
            return redirect("/config/")
        else:
            self.error()

class deleteImageView(normalView):
    template_path = "dashboard.html"

    @classmethod
    def get(self):
        data = {
                "image": self.image
        }
        result = dockletRequest.post("/image/delete/", data)
        if(result):
            return redirect("/config/")
        else:
            self.error()

class addproxyView(normalView):

    @classmethod
    def post(self):
        data = {
            "clustername": self.clustername,
            "ip": self.ip,
            "port": self.port
        }
        result = dockletRequest.post("/addproxy/", data)
        if(result):
            return redirect("/config/")
        else:
            self.error()

class deleteproxyView(normalView):

    @classmethod
    def get(self):
        data = {
            "clustername":self.clustername
        }
        result = dockletRequest.post("/deleteproxy/", data)
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
        images = dockletRequest.post('/image/list/').get('images')
        clusters = dockletRequest.post("/cluster/list/").get("clusters")
        clusters_info = {}
        data={}
        for cluster in clusters:
            data["clustername"] = cluster
            result = dockletRequest.post("/cluster/info/",data).get("message")
            clusters_info[cluster] = result
        return self.render("config.html", images = images, clusters = clusters_info, mysession=dict(session))

    @classmethod
    def post(self):
        return self.get()
