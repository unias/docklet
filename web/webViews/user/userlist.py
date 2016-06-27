from flask import render_template, redirect, request
from webViews.dockletrequest import dockletRequest
from webViews.view import normalView
import json

class userlistView(normalView):
    template_path = "user_list.html"

    @classmethod
    def get(self):
        groups = dockletRequest.post('/user/groupNameList/')["groups"]
        return self.render(self.template_path, groups = groups)

    @classmethod
    def post(self):
        return json.dumps(dockletRequest.post('/user/data/'))


class useraddView(normalView):
    @classmethod
    def post(self):
        dockletRequest.post('/user/add/', request.form)
        return redirect('/user/list/')

class userdataView(normalView):
    @classmethod
    def get(self):
        return json.dumps(dockletRequest.post('/user/data/', request.form))

    @classmethod
    def post(self):
        return json.dumps(dockletRequest.post('/user/data/', request.form))

class userqueryView(normalView):
    @classmethod
    def get(self):
        return json.dumps(dockletRequest.post('/user/query/', request.form))

    @classmethod
    def post(self):
        return json.dumps(dockletRequest.post('/user/query/', request.form))

class usermodifyView(normalView):
    @classmethod
    def post(self):
        try:
            dockletRequest.post('/user/modify/', request.form)
        except:
            return self.render('user/mailservererror.html')
        return redirect('/user/list/')
