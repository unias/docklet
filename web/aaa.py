#!/usr/bin/python3
import json
import os
import getopt
os.system("touch wawaw")
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
from webViews.user.userinfo import userinfoView
from webViews.user.userActivate import userActivateView
from webViews.user.grouplist import grouplistView, groupqueryView, groupdetailView, groupmodifyView
from functools import wraps
from webViews.dockletrequest import dockletRequest
from webViews.cluster import *
from webViews.admin import *
from webViews.monitor import *
from webViews.authenticate.auth import login_required, administration_required,activated_required
from webViews.authenticate.register import registerView
from webViews.authenticate.login import loginView, logoutView
import webViews.dockletrequest
from webViews import cookie_tool





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
@administration_required
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

@app.route("/dashboard_guest/", methods=['GET'])
def dashboard_guest():
    resp = make_response(dashboard_guestView.as_view())
    resp.set_cookie('guest-cookie', cookie_tool.generate_cookie('guest', app.secret_key))
    return resp

@app.route("/document/", methods=['GET'])
def redirect_dochome():
    return redirect("http://docklet.unias.org/userguide")

@app.route("/config/", methods=['GET'])
@login_required
def config():
    return configView.as_view()


@app.route("/workspace/create/", methods=['GET'])
@activated_required
def addCluster():
    return addClusterView.as_view()

@app.route("/workspace/list/", methods=['GET'])
@login_required
def listCluster():
    return listClusterView.as_view()

@app.route("/workspace/add/", methods=['POST'])
@login_required
def createCluster():
    createClusterView.clustername = request.form["clusterName"]
    createClusterView.image = request.form["image"]
    return createClusterView.as_view()

@app.route("/workspace/scaleout/<clustername>/", methods=['POST'])
@login_required
def scaleout(clustername):
    scaleoutView.image = request.form["image"]
    scaleoutView.clustername = clustername
    return scaleoutView.as_view()

@app.route("/workspace/scalein/<clustername>/<containername>/", methods=['GET'])
@login_required
def scalein(clustername,containername):
    scaleinView.clustername = clustername
    scaleinView.containername = containername
    return scaleinView.as_view()

@app.route("/workspace/start/<clustername>/", methods=['GET'])
@login_required
def startClustet(clustername):
    startClusterView.clustername = clustername
    return startClusterView.as_view()

@app.route("/workspace/stop/<clustername>/", methods=['GET'])
@login_required
def stopClustet(clustername):
    stopClusterView.clustername = clustername
    return stopClusterView.as_view()

@app.route("/workspace/delete/<clustername>/", methods=['GET'])
@login_required
def deleteClustet(clustername):
    deleteClusterView.clustername = clustername
    return deleteClusterView.as_view()

@app.route("/workspace/detail/<clustername>/", methods=['GET'])
@login_required
def detailCluster(clustername):
    detailClusterView.clustername = clustername
    return detailClusterView.as_view()

@app.route("/workspace/flush/<clustername>/<containername>/", methods=['GET'])
@login_required
def flushCluster(clustername,containername):
    flushClusterView.clustername = clustername
    flushClusterView.containername = containername
    return flushClusterView.as_view()

@app.route("/workspace/save/<clustername>/<containername>/", methods=['POST'])
@login_required
def saveImage(clustername,containername):
    saveImageView.clustername = clustername
    saveImageView.containername = containername
    saveImageView.isforce = "false"
    saveImageView.imagename = request.form['ImageName']
    saveImageView.description = request.form['description']
    return saveImageView.as_view()

@app.route("/workspace/save/<clustername>/<containername>/force/", methods=['POST'])
@login_required
def saveImage_force(clustername,containername):
    saveImageView.clustername = clustername
    saveImageView.containername = containername
    saveImageView.isforce = "true"
    saveImageView.imagename = request.form['ImageName']
    saveImageView.description = request.form['description']
    return saveImageView.as_view()

@app.route("/addproxy/<clustername>/", methods=['POST'])
@login_required
def addproxy(clustername):
    addproxyView.clustername = clustername
    addproxyView.ip = request.form['proxy_ip']
    addproxyView.port = request.form['proxy_port']
    return addproxyView.as_view()

@app.route("/deleteproxy/<clustername>/", methods=['GET'])
@login_required
def deleteproxy(clustername):
    deleteproxyView.clustername = clustername
    return deleteproxyView.as_view()

@app.route("/image/description/<image>/", methods=['GET'])
@login_required
def descriptionImage(image):
    descriptionImageView.image = image
    return descriptionImageView.as_view()

@app.route("/image/share/<image>/", methods=['GET'])
@login_required
def shareImage(image):
    shareImageView.image = image
    return shareImageView.as_view()

@app.route("/image/unshare/<image>/", methods=['GET'])
@login_required
def unshareImage(image):
    unshareImageView.image = image
    return unshareImageView.as_view()

@app.route("/image/delete/<image>/", methods=['GET'])
@login_required
def deleteImage(image):
    deleteImageView.image = image
    return deleteImageView.as_view()

@app.route("/hosts/", methods=['GET'])
@administration_required
def hosts():
    return hostsView.as_view()

@app.route("/hosts/<com_ip>/", methods=['GET'])
@administration_required
def hostsRealtime(com_ip):
    hostsRealtimeView.com_ip = com_ip
    return hostsRealtimeView.as_view()

@app.route("/hosts/<com_ip>/containers/", methods=['GET'])
@administration_required
def hostsConAll(com_ip):
    hostsConAllView.com_ip = com_ip
    return hostsConAllView.as_view()

@app.route("/vclusters/", methods=['GET'])
@login_required
def status():
    return statusView.as_view()

@app.route("/vclusters/<vcluster_name>/<node_name>/", methods=['GET'])
@login_required
def statusRealtime(vcluster_name,node_name):
    statusRealtimeView.node_name = node_name
    return statusRealtimeView.as_view()

@app.route("/monitor/hosts/<comid>/<infotype>", methods=['POST'])
@app.route("/monitor/vnodes/<comid>/<infotype>", methods=['POST'])
@login_required
def monitor_request(comid,infotype):
    data = {
        "user": session['username']
    }
    result = dockletRequest.post(request.path, data)
    return json.dumps(result)

@app.route("/monitor/User/", methods=['GET'])
@administration_required
def monitorUserAll():
    return monitorUserAllView.as_view()




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

@app.route("/quota/add/", methods=['POST'])
@administration_required
def quotaadd():
    return quotaaddView.as_view()

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


@app.route("/admin/", methods=['GET', 'POST'])
@administration_required
def adminpage():
    return adminView.as_view()

@app.route("/update-codes", methods=['POST'])
@administration_required
def update_codes_page():
    f = open("/root/my_log_file","w")
    git = request.form.get('working_dir_of_worker')
    print("sh ../tools/auto_update_master.sh "+git, file=f)
    os.system("bash ../tools/auto_update_master.sh update "+git)
    print(git,file=f)
    return redirect('/admin/')

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
        return render_template('error/401.html', mysession = session)
    else:
        return redirect('/login/')

@app.errorhandler(500)
def internal_server_error(error):
    if "username" in session:
        return render_template('error/500.html', mysession = session)
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
