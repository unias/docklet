from webViews.view import normalView
from webViews.authenticate.auth import is_authenticated
from webViews.dockletrequest import dockletRequest
from flask import redirect, request, render_template, session, make_response, abort
from webViews import cookie_tool

import hashlib
#from suds.client import Client

import os, sys, inspect
this_folder = os.path.realpath(os.path.abspath(os.path.split(inspect.getfile(inspect.currentframe()))[0]))
src_folder = os.path.realpath(os.path.abspath(os.path.join(this_folder,"../../..", "src")))
if src_folder not in sys.path:
    sys.path.insert(0, src_folder)

import env

if (env.getenv('EXTERNAL_LOGIN') == 'True'):
    sys.path.insert(0, os.path.realpath(os.path.abspath(os.path.join(this_folder,"../../../src", "plugin"))))
    import external_generate

def refreshInfo():
    data = {}
    result = dockletRequest.post('/user/selfQuery/', data)
    ok = result and result.get('success', None)
    if (ok and ok == "true"):
        session['username'] = result['data']['username']
        session['nickname'] = result['data']['nickname']
        session['description'] = result['data']['description']
        session['avatar'] = '/static/avatar/'+ result['data']['avatar']
        session['usergroup'] = result['data']['group']
        session['status'] = result['data']['status']
    else:
        abort(404)

class loginView(normalView):
    template_path = "login.html"

    @classmethod
    def get(self):
        if is_authenticated():
            refreshInfo()
            return redirect(request.args.get('next',None) or '/dashboard/')
        if (env.getenv('EXTERNAL_LOGIN') == 'True'):
            url = external_generate.external_login_url
            link = external_generate.external_login_link
        else:
            link = ''
            url = ''
        return render_template(self.template_path, link = link, url = url)

    @classmethod
    def post(self):
        if (request.form['username']):
            data = {"user": request.form['username'], "key": request.form['password']}
            result = dockletRequest.unauthorizedpost('/login/', data)
            ok = result and result.get('success', None)
            if (ok and (ok == "true")):
                # set cookie:docklet-jupyter-cookie for jupyter notebook
                resp = make_response(redirect(request.args.get('next',None) or '/dashboard/'))
                app_key = os.environ['APP_KEY']
                resp.set_cookie('docklet-jupyter-cookie', cookie_tool.generate_cookie(request.form['username'], app_key))
                # set session for docklet
                session['username'] = request.form['username']
                session['nickname'] = result['data']['nickname']
                session['description'] = result['data']['description']
                session['avatar'] = '/static/avatar/'+ result['data']['avatar']
                session['usergroup'] = result['data']['group']
                session['status'] = result['data']['status']
                session['token'] = result['data']['token']
                return resp
            else:
                return redirect('/login/')
        else:
            return redirect('/login/')

class logoutView(normalView):

    @classmethod
    def get(self):
        resp = make_response(redirect('/login/'))
        session.pop('username', None)
        session.pop('nickname', None)
        session.pop('description', None)
        session.pop('avatar', None)
        session.pop('status', None)
        session.pop('usergroup', None)
        session.pop('token', None)
        resp.set_cookie('docklet-jupyter-cookie', '', expires=0)
        return resp


class external_login_callbackView(normalView):
    @classmethod
    def get(self):

        form = external_generate.external_auth_generate_request()
        result = dockletRequest.unauthorizedpost('/external_login/', form)
        ok = result and result.get('success', None)
        if (ok and (ok == "true")):
            # set cookie:docklet-jupyter-cookie for jupyter notebook
            resp = make_response(redirect(request.args.get('next',None) or '/dashboard/'))
            app_key = os.environ['APP_KEY']
            resp.set_cookie('docklet-jupyter-cookie', cookie_tool.generate_cookie(result['data']['username'], app_key))
            # set session for docklet
            session['username'] = result['data']['username']
            session['nickname'] = result['data']['nickname']
            session['description'] = result['data']['description']
            session['avatar'] = '/static/avatar/'+ result['data']['avatar']
            session['usergroup'] = result['data']['group']
            session['status'] = result['data']['status']
            session['token'] = result['data']['token']
            return resp
        else:
            return redirect('/login/')

    @classmethod
    def post(self):

        form = external_generate.external_auth_generate_request()
        result = dockletRequest.unauthorizedpost('/external_login/', form)
        ok = result and result.get('success', None)
        if (ok and (ok == "true")):
            # set cookie:docklet-jupyter-cookie for jupyter notebook
            resp = make_response(redirect(request.args.get('next',None) or '/dashboard/'))
            app_key = os.environ['APP_KEY']
            resp.set_cookie('docklet-jupyter-cookie', cookie_tool.generate_cookie(result['data']['username'], app_key))
            # set session for docklet
            session['username'] = result['data']['username']
            session['nickname'] = result['data']['nickname']
            session['description'] = result['data']['description']
            session['avatar'] = '/static/avatar/'+ result['data']['avatar']
            session['usergroup'] = result['data']['group']
            session['status'] = result['data']['status']
            session['token'] = result['data']['token']
            return resp
        else:
            return redirect('/login/')

class external_loginView(normalView):
    if (env.getenv('EXTERNAL_LOGIN') == 'True'):
        template_path = external_generate.html_path
