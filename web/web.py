#!/usr/bin/python3
import json
import os
import getopt

import sys, inspect


this_folder = os.path.realpath(os.path.abspath(os.path.split(inspect.getfile(inspect.currentframe()))[0]))
src_folder = os.path.realpath(os.path.abspath(os.path.join(this_folder,"..", "src")))
if src_folder not in sys.path:
    sys.path.insert(0, src_folder)

# must first init loadenv
import tools, env
config = env.getenv("CONFIG")
tools.loadenv(config)

from webViews.log import initlogging
initlogging("docklet-web")
from webViews.log import logger

from flask import Flask, request, session, render_template, redirect, send_from_directory, make_response, url_for, abort
from webViews.dashboard import dashboardView
from webViews.user.userlist import userlistView, useraddView, usermodifyView, userdataView, userqueryView
from webViews.notification.notification import CreateNotificationView, NotificationView, QuerySelfNotificationsView, \
    QueryNotificationView, ModifyNotificationView, DeleteNotificationView
from webViews.user.userinfo import userinfoView
from webViews.user.userActivate import userActivateView
from webViews.syslogs import logsView
from webViews.user.grouplist import grouplistView, groupqueryView, groupdetailView, groupmodifyView
from functools import wraps
from webViews.dockletrequest import dockletRequest
from webViews.cluster import *
from webViews.admin import *
from webViews.monitor import *
from webViews.beansapplication import *
from webViews.cloud import *
from webViews.authenticate.auth import login_required, administration_required,activated_required
from webViews.authenticate.register import registerView
from webViews.authenticate.login import loginView, logoutView
import webViews.dockletrequest
from webViews import cookie_tool
import traceback

from werkzeug.utils import secure_filename



external_login = env.getenv('EXTERNAL_LOGIN')
#default config
external_login_url = '/external_auth/'
external_login_callback_url = '/external_auth_callback/'
if (external_login == 'True'):
    sys.path.insert(0, os.path.realpath(os.path.abspath(os.path.join(this_folder,"../src", "plugin"))))
    import external_generate
    from webViews.authenticate.login import external_loginView, external_login_callbackView
    external_login_url = external_generate.external_login_url
    external_login_callback_url = external_generate.external_login_callback_url


app = Flask(__name__)



@app.route("/", methods=['GET'])
def home():
    return render_template('home.html')

@app.route("/login/", methods=['GET', 'POST'])
def login():
    loginView.open_registry = os.environ["OPEN_REGISTRY"]
    return loginView.as_view()

@app.route(external_login_url, methods=['GET'])
def external_login_func():
    try:
        return external_loginView.as_view()
    except:
        abort(404)

@app.route(external_login_callback_url, methods=['GET'])
def external_login_callback():
    try:
        return external_login_callbackView.as_view()
    except:
        abort(404)

@app.route("/logout/", methods=["GET"])
@login_required
def logout():
    return logoutView.as_view()

@app.route("/register/", methods=['GET', 'POST'])
#@administration_required
#now forbidden,only used by SEI & PKU Staffs and students.
#can be used by admin for testing
def register():
    return registerView.as_view()



@app.route("/activate/", methods=['GET', 'POST'])
@login_required
def activate():
    return userActivateView.as_view()

@app.route("/dashboard/", methods=['GET'])
@login_required
def dashboard():
    return dashboardView.as_view()

@app.route("/document/", methods=['GET'])
def redirect_dochome():
    return redirect("http://unias.github.io/docklet/userguide")

@app.route("/config/", methods=['GET'])
@login_required
def config():
    return configView.as_view()


@app.route("/workspace/create/", methods=['GET'])
@activated_required
def addCluster():
    return addClusterView.as_view()

@app.route("/workspace/<masterip>/list/", methods=['GET'])
@login_required
def listCluster(masterip):
    listClusterView.masterip = masterip
    return listClusterView.as_view()

@app.route("/workspace/<masterip>/add/", methods=['POST'])
@login_required
def createCluster(masterip):
    createClusterView.clustername = request.form["clusterName"]
    createClusterView.image = request.form["image"]
    createClusterView.masterip = masterip
    return createClusterView.as_view()

@app.route("/workspace/<masterip>/scaleout/<clustername>/", methods=['POST'])
@login_required
def scaleout(clustername,masterip):
    scaleoutView.image = request.form["image"]
    scaleoutView.masterip = masterip
    scaleoutView.clustername = clustername
    return scaleoutView.as_view()

@app.route("/workspace/<masterip>/scalein/<clustername>/<containername>/", methods=['GET'])
@login_required
def scalein(clustername,containername,masterip):
    scaleinView.clustername = clustername
    scaleinView.containername = containername
    scaleinView.masterip = masterip
    return scaleinView.as_view()

@app.route("/workspace/<masterip>/start/<clustername>/", methods=['GET'])
@login_required
def startClustet(clustername,masterip):
    startClusterView.clustername = clustername
    startClusterView.masterip = masterip
    return startClusterView.as_view()

@app.route("/workspace/<masterip>/stop/<clustername>/", methods=['GET'])
@login_required
def stopClustet(clustername,masterip):
    stopClusterView.clustername = clustername
    stopClusterView.masterip = masterip
    return stopClusterView.as_view()

@app.route("/workspace/<masterip>/delete/<clustername>/", methods=['GET'])
@login_required
def deleteClustet(clustername,masterip):
    deleteClusterView.clustername = clustername
    deleteClusterView.masterip = masterip
    return deleteClusterView.as_view()

@app.route("/workspace/<masterip>/detail/<clustername>/", methods=['GET'])
@login_required
def detailCluster(clustername,masterip):
    detailClusterView.clustername = clustername
    detailClusterView.masterip = masterip
    return detailClusterView.as_view()

@app.route("/workspace/<masterip>/flush/<clustername>/<containername>/", methods=['GET'])
@login_required
def flushCluster(clustername,containername):
    flushClusterView.clustername = clustername
    flushClusterView.containername = containername
    return flushClusterView.as_view()

@app.route("/workspace/<masterip>/save/<clustername>/<containername>/", methods=['POST'])
@login_required
def saveImage(clustername,containername,masterip):
    saveImageView.clustername = clustername
    saveImageView.containername = containername
    saveImageView.masterip = masterip
    saveImageView.isforce = "false"
    saveImageView.imagename = request.form['ImageName']
    saveImageView.description = request.form['description']
    return saveImageView.as_view()

@app.route("/workspace/<masterip>/save/<clustername>/<containername>/force/", methods=['POST'])
@login_required
def saveImage_force(clustername,containername,masterip):
    saveImageView.clustername = clustername
    saveImageView.containername = containername
    saveImageView.masterip = masterip
    saveImageView.isforce = "true"
    saveImageView.imagename = request.form['ImageName']
    saveImageView.description = request.form['description']
    return saveImageView.as_view()

'''@app.route("/addproxy/<masterip>/<clustername>/", methods=['POST'])
@login_required
def addproxy(clustername,masterip):
    addproxyView.clustername = clustername
    addproxyView.masterip = masterip
    addproxyView.ip = request.form['proxy_ip']
    addproxyView.port = request.form['proxy_port']
    return addproxyView.as_view()'''

'''@app.route("/deleteproxy/<masterip>/<clustername>/", methods=['GET'])
@login_required
def deleteproxy(clustername,masterip):
    deleteproxyView.clustername = clustername
    deleteproxyView.masterip = masterip
    return deleteproxyView.as_view()'''

@app.route("/port_mapping/add/<masterip>/", methods=['POST'])
@login_required
def addPortMapping(masterip):
    addPortMappingView.masterip = masterip
    return addPortMappingView.as_view()

@app.route("/port_mapping/delete/<masterip>/<clustername>/<node_name>/<node_port>/", methods=['GET'])
@login_required
def delPortMapping(masterip,clustername,node_name,node_port):
    delPortMappingView.masterip = masterip
    delPortMappingView.clustername = clustername
    delPortMappingView.node_name = node_name
    delPortMappingView.node_port = node_port
    return delPortMappingView.as_view()

@app.route("/getmasterdesc/<mastername>/", methods=['POST'])
@login_required
def getmasterdesc(mastername):
    return env.getenv(mastername+"_desc")[1:-1]

@app.route("/masterdesc/<mastername>/", methods=['GET'])
@login_required
def masterdesc(mastername):
    descriptionMasterView.desc=env.getenv(mastername+"_desc")[1:-1]
    return descriptionMasterView.as_view()

@app.route("/image/<masterip>/list/", methods=['POST'])
@login_required
def image_list(masterip):
    data = {
        "user": session['username']
    }
#    path = request.path[:request.path.rfind("/")]
#    path = path[:path.rfind("/")+1]
    result = dockletRequest.post("/image/list/", data, masterip)
    logger.debug("image" + str(type(result)))
    return json.dumps(result)

@app.route("/image/<masterip>/description/<image>/", methods=['GET'])
@login_required
def descriptionImage(image,masterip):
    descriptionImageView.image = image
    descriptionImageView.masterip = masterip
    return descriptionImageView.as_view()

@app.route("/image/<masterip>/share/<image>/", methods=['GET'])
@login_required
def shareImage(image,masterip):
    shareImageView.image = image
    shareImageView.masterip = masterip
    return shareImageView.as_view()

@app.route("/image/<masterip>/unshare/<image>/", methods=['GET'])
@login_required
def unshareImage(image,masterip):
    unshareImageView.image = image
    unshareImageView.masterip = masterip
    return unshareImageView.as_view()

@app.route("/image/<masterip>/delete/<image>/", methods=['GET'])
@login_required
def deleteImage(image,masterip):
    deleteImageView.image = image
    deleteImageView.masterip = masterip
    return deleteImageView.as_view()

@app.route("/image/<masterip>/updatebase/<image>/", methods=['GET'])
@login_required
def updatebaseImage(image,masterip):
    updatebaseImageView.image = image
    updatebaseImageView.masterip = masterip
    return updatebaseImageView.as_view()

@app.route("/hosts/", methods=['GET'])
@administration_required
def hosts():
    return hostsView.as_view()

@app.route("/hosts/<masterip>/<com_ip>/", methods=['GET'])
@administration_required
def hostsRealtime(com_ip,masterip):
    hostsRealtimeView.com_ip = com_ip
    hostsRealtimeView.masterip = masterip
    return hostsRealtimeView.as_view()

@app.route("/hosts/<masterip>/<com_ip>/containers/", methods=['GET'])
@administration_required
def hostsConAll(com_ip,masterip):
    hostsConAllView.com_ip = com_ip
    hostsConAllView.masterip = masterip
    return hostsConAllView.as_view()

@app.route("/vclusters/", methods=['GET'])
@login_required
def status():
    return statusView.as_view()

@app.route("/vclusters/<masterip>/<vcluster_name>/<node_name>/", methods=['GET'])
@login_required
def statusRealtime(vcluster_name,node_name,masterip):
    statusRealtimeView.masterip = masterip
    statusRealtimeView.node_name = node_name
    return statusRealtimeView.as_view()

@app.route("/history/", methods=['GET'])
#@login_required
def history():
    return historyView.as_view()


@app.route("/history/<masterip>/<vnode_name>/", methods=['GET'])
@login_required
def historyVNode(vnode_name,masterip):
    historyVNodeView.masterip = masterip
    historyVNodeView.vnode_name = vnode_name
    return historyVNodeView.as_view()

@app.route("/monitor/<masterip>/hosts/<comid>/<infotype>/", methods=['POST'])
@app.route("/monitor/<masterip>/vnodes/<comid>/<infotype>/", methods=['POST'])
@login_required
def monitor_request(comid,infotype,masterip):
    data = {
        "user": session['username']
    }
    path = request.path[request.path.find("/")+1:]
    path = path[path.find("/")+1:]
    path = path[path.find("/")+1:]
    logger.debug(path + "_____" + masterip)
    result = dockletRequest.post("/monitor/"+path, data, masterip)
    logger.debug("monitor" + str(type(result)))
    return json.dumps(result)

@app.route("/beans/application/", methods=['GET'])
@login_required
def beansapplication():
    return beansapplicationView.as_view()

@app.route("/beans/apply/", methods=['POST'])
@login_required
def beansapply():
    return beansapplyView.as_view()

@app.route("/beans/admin/<msgid>/<cmd>/", methods=['GET'])
@login_required
@administration_required
def beansadmin(msgid,cmd):
    beansadminView.msgid = msgid
    if cmd == "agree" or cmd == "reject":
        beansadminView.cmd = cmd
        return beansadminView.as_view()
    else:
        return redirect("/user/list/")

'''@app.route("/monitor/User/", methods=['GET'])
@administration_required
def monitorUserAll():
    return monitorUserAllView.as_view()
'''

@app.route("/logs/", methods=['GET', 'POST'])
@administration_required
def logs():
    return logsView.as_view()

@app.route("/logs/<filename>/", methods=['GET'])
@administration_required
def logs_get(filename):
    data = {
            "filename": filename
    }
    result = dockletRequest.post('/logs/get/', data).get('result', '')
    response = make_response(result)
    response.headers["content-type"] = "text/plain"
    return response

@app.route("/user/list/", methods=['GET', 'POST'])
@administration_required
def userlist():
    return userlistView.as_view()

@app.route("/group/list/", methods=['POST'])
@administration_required
def grouplist():
    return grouplistView.as_view()

@app.route("/group/detail/", methods=['POST'])
@administration_required
def groupdetail():
    return groupdetailView.as_view()

@app.route("/group/query/", methods=['POST'])
@administration_required
def groupquery():
    return groupqueryView.as_view()

@app.route("/group/modify/<groupname>/", methods=['POST'])
@administration_required
def groupmodify(groupname):
    return groupmodifyView.as_view()

@app.route("/user/data/", methods=['GET', 'POST'])
@administration_required
def userdata():
    return userdataView.as_view()

@app.route("/user/add/", methods=['POST'])
@administration_required
def useradd():
    return useraddView.as_view()

@app.route("/user/modify/", methods=['POST'])
@administration_required
def usermodify():
    return usermodifyView.as_view()

@app.route("/user/change/", methods=['POST'])
@administration_required
def userchange():
    return usermodifyView.as_view()

@app.route("/quota/add/", methods=['POST'])
@administration_required
def quotaadd():
    return quotaaddView.as_view()

@app.route("/quota/chdefault/", methods=['POST'])
@administration_required
def chdefault():
    return chdefaultView.as_view()

@app.route("/quota/chlxcsetting/", methods=['POST'])
@administration_required
def chlxcsetting():
    return chlxcsettingView.as_view()

@app.route("/group/add/", methods=['POST'])
@administration_required
def groupadd():
    return groupaddView.as_view()

@app.route("/group/delete/<groupname>/", methods=['POST', 'GET'])
@administration_required
def groupdel(groupname):
    groupdelView.groupname = groupname
    return groupdelView.as_view()

@app.route("/user/info/", methods=['GET', 'POST'])
@login_required
def userinfo():
    return userinfoView.as_view()

@app.route("/user/query/", methods=['GET', 'POST'])
@administration_required
def userquery():
    return userqueryView.as_view()

@app.route("/cloud/", methods=['GET', 'POST'])
@administration_required
def cloud():
    return cloudView.as_view()

@app.route("/cloud/account/add/", methods = ['POST'])
@administration_required
def cloud_account_add():
    return cloudAccountAddView.as_view()

@app.route("/cloud/account/delete/<cloudname>/", methods = ['POST', 'GET'])
@administration_required
def cloud_account_del(cloudname):
    cloudAccountDelView.cloudname = cloudname
    return cloudAccountDelView.as_view()


@app.route("/cloud/account/modify/<cloudname>/", methods = ['POST'])
@administration_required
def cloud_account_modify(cloudname):
    return cloudAccountModifyView.as_view()


@app.route("/notification/", methods=['GET'])
@administration_required
def notification_list():
    return NotificationView.as_view()


@app.route("/notification/create/", methods=['GET', 'POST'])
@administration_required
def create_notification():
    return CreateNotificationView.as_view()


@app.route("/notification/modify/", methods=['POST'])
@administration_required
def modify_notification():
    return ModifyNotificationView.as_view()


@app.route("/notification/delete/", methods=['POST'])
@administration_required
def delete_notification():
    return DeleteNotificationView.as_view()


@app.route("/notification/query_self/", methods=['POST'])
@login_required
def query_self_notifications():
    return QuerySelfNotificationsView.as_view()


@app.route("/notification/detail/<notify_id>/", methods=['GET'])
@login_required
def query_notification_detail(notify_id):
    return QueryNotificationView.get_by_id(notify_id)


@app.route("/system/modify/", methods=['POST'])
@administration_required
def systemmodify():
    return systemmodifyView.as_view()

@app.route("/system/clear_history/", methods=['POST'])
@administration_required
def systemclearhistory():
    return systemclearView.as_view()

@app.route("/system/add/", methods=['POST'])
@administration_required
def systemadd():
    return systemaddView.as_view()

@app.route("/system/delete/", methods=['POST'])
@administration_required
def systemdelete():
    return systemdeleteView.as_view()

@app.route("/system/resetall/", methods=['POST'])
@administration_required
def systemresetall():
    return systemresetallView.as_view()

@app.route("/settings/", methods=['GET', 'POST'])
@administration_required
def adminpage():
    return adminView.as_view()

@app.route("/settings/update/", methods=['POST'])
@administration_required
def updatesettings():
    return updatesettingsView.as_view()

@app.route('/index/', methods=['GET'])
def jupyter_control():
    return redirect('/dashboard/')

# for download basefs.tar.bz
# remove, not the function of docklet
# should download it from a http server
#@app.route('/download/basefs', methods=['GET'])
#def download():
    #fsdir = env.getenv("FS_PREFIX")
    #return send_from_directory(fsdir+'/local', 'basefs.tar.bz', as_attachment=True)

# jupyter auth APIs
@app.route('/jupyter/', methods=['GET'])
def jupyter_prefix():
    path = request.args.get('next')
    if path == None:
        return redirect('/login/')
    return redirect('/login/'+'?next='+path)

@app.route('/jupyter/home/', methods=['GET'])
def jupyter_home():
    return redirect('/dashboard/')

@app.route('/jupyter/login/', methods=['GET', 'POST'])
def jupyter_login():
    return redirect('/login/')

@app.route('/jupyter/logout/', methods=['GET'])
def jupyter_logout():
    return redirect('/logout/')

@app.route('/jupyter/authorizations/cookie/<cookie_name>/<cookie_content>/', methods=['GET'])
def jupyter_auth(cookie_name, cookie_content):
    username = cookie_tool.parse_cookie(cookie_content, app.secret_key)
    if username == None:
        resp = make_response('cookie auth failed')
        resp.status_code = 404
        return resp
    return json.dumps({'name': username})

@app.errorhandler(401)
def not_authorized(error):
    if "username" in session:
        if "401" in session:
            reason = session['401']
            session.pop('401', None)
            if (reason == 'Token Expired'):
                return redirect('/logout/')
        return render_template('error/401.html', mysession = session)
    else:
        return redirect('/login/')

@app.errorhandler(500)
def internal_server_error(error):
    logger.error(error)
    logger.error(traceback.format_exc())
    if "username" in session:
        if "500" in session and "500_title" in session:
            reason = session['500']
            title = session['500_title']
            session.pop('500', None)
            session.pop('500_title', None)
        else:
            reason = '''The server encountered something unexpected that didn't allow it to complete the request. We apologize.You can go back to
<a href="/dashboard/">dashboard</a> or <a href="/logout">log out</a>'''
            title = 'Internal Server Error'
        return render_template('error/500.html', mysession = session, reason = reason, title = title)
    else:
        return redirect('/login/')
if __name__ == '__main__':
    '''
    to generate a secret_key

    from base64 import b64encode
    from os import urandom

    secret_key = urandom(24)
    secret_key = b64encode(secret_key).decode('utf-8')

    '''
    logger.info('Start Flask...:')
    try:
        secret_key_file = open(env.getenv('FS_PREFIX') + '/local/web_secret_key.txt')
        app.secret_key = secret_key_file.read()
        secret_key_file.close()
    except:
        from base64 import b64encode
        from os import urandom
        secret_key = urandom(24)
        secret_key = b64encode(secret_key).decode('utf-8')
        app.secret_key = secret_key
        secret_key_file = open(env.getenv('FS_PREFIX') + '/local/web_secret_key.txt', 'w')
        secret_key_file.write(secret_key)
        secret_key_file.close()

    try:
        open_registryfile = open(env.getenv('FS_PREFIX') + '/local/settings.conf')
        settings = jsobn.loads(open_registryfile.read())
        open_registryfile.close()
        os.environ['OPEN_REGISTRY'] = settings.get('OPEN_REGISTRY',"False")
    except:
        os.environ['OPEN_REGISTRY'] = "False"

    os.environ['APP_KEY'] = app.secret_key
    runcmd = sys.argv[0]
    app.runpath = runcmd.rsplit('/', 1)[0]

    webip = "0.0.0.0"
    webport = env.getenv("WEB_PORT")

    webViews.dockletrequest.endpoint = 'http://%s:%d' % (env.getenv('MASTER_IP'), env.getenv('MASTER_PORT'))


    try:
        opts, args = getopt.getopt(sys.argv[1:], "i:p:", ["ip=", "port="])
    except getopt.GetoptError:
        print ("%s -i ip -p port" % sys.argv[0])
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-i", "--ip"):
            webip = arg
        elif opt in ("-p", "--port"):
            webport = int(arg)

app.run(host = webip, port = webport, debug = True, threaded=True)
