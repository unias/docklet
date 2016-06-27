from flask import render_template, redirect, request
from webViews.dockletrequest import dockletRequest
from webViews.view import normalView


class userActivateView(normalView):
    template_path = 'user/activate.html'

    @classmethod
    def get(self):
        userinfo = dockletRequest.post('/user/selfQuery/')
        userinfo = userinfo["data"]
        if (userinfo["description"] == ''):
            userinfo["description"] = "Describe why you want to use Docklet"
        return self.render(self.template_path, info = userinfo)

    @classmethod
    def post(self):
        dockletRequest.post('/register/', request.form)
        return redirect('/logout/')
