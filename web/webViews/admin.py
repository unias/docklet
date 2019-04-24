from flask import session, render_template, redirect, request
from webViews.view import normalView
from webViews.dockletrequest import dockletRequest
from webViews.dashboard import *
import time, re, json, os

class adminView(normalView):
    template_path = "settings.html"

    @classmethod
    def get(self):
        result = dockletRequest.post('/user/groupList/')
        groups = result["groups"]
        quotas = result["quotas"]
        defaultgroup = result["default"]
        parms = dockletRequest.post('/system/parmList/')
        rootimage = dockletRequest.post('/image/list/').get('images')
        lxcsetting = dockletRequest.post('/user/lxcsettingList/')['data']
        settings = dockletRequest.post('/settings/list/')['result']
        return self.render(self.template_path, groups = groups, quotas = quotas, defaultgroup = defaultgroup, parms = parms, lxcsetting = lxcsetting, root_image = rootimage['private'], settings=settings)

class updatesettingsView(normalView):
    
    @classmethod
    def post(self):
        result = dockletRequest.post("/settings/update/", request.form)
        os.environ['OPEN_REGISTRY'] = request.form.get('OPEN_REGISTRY')
        return redirect('/settings/')

class groupaddView(normalView):
    @classmethod
    def post(self):
        dockletRequest.post('/user/groupadd/', request.form)
        return redirect('/settings/')

class systemmodifyView(normalView):
    @classmethod
    def post(self):
        dockletRequest.post('/system/modify/', request.form)
        return redirect('/settings/')

class systemclearView(normalView):
    @classmethod
    def post(self):
        dockletRequest.post('/system/clear_history/', request.form)
        return redirect('/settings/')

class systemaddView(normalView):
    @classmethod
    def post(self):
        dockletRequest.post('/system/add/', request.form)
        return redirect('/settings/')

class systemdeleteView(normalView):
    @classmethod
    def post(self):
        dockletRequest.post('/system/delete/', request.form)
        return redirect('/settings/')

class systemresetallView(normalView):
    @classmethod
    def post(self):
        dockletRequest.post('/system/reset_all/', request.form)
        return redirect('/settings/')

class quotaaddView(normalView):
    @classmethod
    def post(self):
        dockletRequest.post('/user/quotaadd/', request.form)
        return redirect('/settings/')

class chdefaultView(normalView):
    @classmethod
    def post(self):
        dockletRequest.post('/user/chdefault/', request.form)
        return redirect('/settings/')

class chlxcsettingView(normalView):
    @classmethod
    def post(self):
        dockletRequest.post('/user/chlxcsetting/', request.form)
        return redirect('/settings/')

class groupdelView(normalView):
    @classmethod
    def post(self):
        data = {
                "name" : self.groupname,
        }
        dockletRequest.post('/user/groupdel/', data)
        return redirect('/settings/')

    @classmethod
    def get(self):
        return self.post()

class chparmView(normalView):
    @classmethod
    def post(self):
        dockletRequest.post('/system/chparm/', request.form)

class historydelView(normalView):
    @classmethod
    def post(self):
        dockletRequest.post('/system/historydel/', request.form)
        return redirect('/settings/')

class updatebaseImageView(normalView):
    @classmethod
    def get(self):
        data = {
                "image": self.image
        }
        dockletRequest.post('/image/updatebase/', data)
        return redirect("/settings/")

class hostMigrateView(normalView):
    @classmethod
    def post(self):
        data = {
                "src_host": self.hostip,
                "dst_host_list": self.target
        }
        dockletRequest.post("/host/migrate/", data, self.masterip)
        return redirect("/hosts/")
