#!/usr/bin/python3

# load environment variables in the beginning
# because some modules need variables when import
# for example, userManager/model.py

from flask import Flask, request

# must first init loadenv
import tools, env
# default CONFIG=/opt/docklet/local/docklet-running.conf

config = env.getenv("CONFIG")
tools.loadenv(config)

# second init logging
# must import logger after initlogging, ugly
from log import initlogging
initlogging("docklet-master")
from log import logger

import os
import http.server, cgi, json, sys, shutil
from socketserver import ThreadingMixIn
import nodemgr, vclustermgr, etcdlib, network, imagemgr, notificationmgr
import userManager
import monitor,traceback
import threading
import sysmgr

#default EXTERNAL_LOGIN=False
external_login = env.getenv('EXTERNAL_LOGIN')
if (external_login == 'TRUE'):
    from userDependence import external_auth

app = Flask(__name__)

from functools import wraps


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        global G_usermgr
        logger.info ("get request, path: %s" % request.path)
        token = request.form.get("token", None)
        if (token == None):
            return json.dumps({'success':'false', 'message':'user or key is null'})
        cur_user = G_usermgr.auth_token(token)
        if (cur_user == None):
            return json.dumps({'success':'false', 'message':'token failed or expired', 'Unauthorized': 'True'})
        return func(cur_user, cur_user.username, request.form, *args, **kwargs)

    return wrapper

@app.route("/login/", methods=['POST'])
def login():
    global G_usermgr
    logger.info ("handle request : user login")
    user = request.form.get("user", None)
    key = request.form.get("key", None)
    if user == None or key == None:
        return json.dumps({'success':'false', 'message':'user or key is null'})
    auth_result = G_usermgr.auth(user, key)
    if  auth_result['success'] == 'false':
        return json.dumps({'success':'false', 'message':'auth failed'})
    return json.dumps({'success':'true', 'action':'login', 'data': auth_result['data']})

@app.route("/external_login/", methods=['POST'])
def external_login():
    global G_usermgr
    logger.info ("handle request : external user login")
    try:
        result = G_usermgr.auth_external(request.form)
        return json.dumps(result)
    except:
        result = {'success': 'false', 'reason': 'Something wrong happened when auth an external account'}
        return json.dumps(result)

@app.route("/register/", methods=['POST'])
def register():
    global G_usermgr
    if request.form.get('activate', None) == None:
        logger.info ("handle request : user register")
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        email = request.form.get('email', '')
        description = request.form.get('description','')
        if (username == '' or password == '' or email == ''):
            return json.dumps({'success':'false'})
        newuser = G_usermgr.newuser()
        newuser.username = request.form.get('username')
        newuser.password = request.form.get('password')
        newuser.e_mail = request.form.get('email')
        newuser.student_number = request.form.get('studentnumber')
        newuser.department = request.form.get('department')
        newuser.nickname = request.form.get('truename')
        newuser.truename = request.form.get('truename')
        newuser.description = request.form.get('description')
        newuser.status = "init"
        newuser.auth_method = "local"
        result = G_usermgr.register(user = newuser)
        return json.dumps(result)
    else:
        logger.info ("handle request, user activating")
        token = request.form.get("token", None)
        if (token == None):
            return json.dumps({'success':'false', 'message':'user or key is null'})
        cur_user = G_usermgr.auth_token(token)
        if (cur_user == None):
            return json.dumps({'success':'false', 'message':'token failed or expired', 'Unauthorized': 'True'})
        newuser = G_usermgr.newuser()
        newuser.username = cur_user.username
        newuser.nickname = cur_user.truename
        newuser.status = 'applying'
        newuser.user_group = cur_user.user_group
        newuser.auth_method = cur_user.auth_method
        newuser.e_mail = request.form.get('email','')
        newuser.student_number = request.form.get('studentnumber', '')
        newuser.department = request.form.get('department', '')
        newuser.truename = request.form.get('truename', '')
        newuser.tel = request.form.get('tel', '')
        newuser.description = request.form.get('description', '')
        result = G_usermgr.register(user = newuser)
        userManager.send_remind_activating_email(newuser.username)
        return json.dumps(result)


@app.route("/cluster/create/", methods=['POST'])
@login_required
def create_cluster(cur_user, user, form):
    global G_usermgr
    global G_vclustermgr
    clustername = form.get('clustername', None)
    if (clustername == None):
        return json.dumps({'success':'false', 'message':'clustername is null'})
    image = {}
    image['name'] = form.get("imagename", None)
    image['type'] = form.get("imagetype", None)
    image['owner'] = form.get("imageowner", None)
    user_info = G_usermgr.selfQuery(cur_user = cur_user)
    user_info = json.dumps(user_info)
    logger.info ("handle request : create cluster %s with image %s " % (clustername, image['name']))
    [status, result] = G_vclustermgr.create_cluster(clustername, user, image, user_info)
    if status:
        return json.dumps({'success':'true', 'action':'create cluster', 'message':result})
    else:
        return json.dumps({'success':'false', 'action':'create cluster', 'message':result})

@app.route("/cluster/scaleout/", methods=['POST'])
@login_required
def scaleout_cluster(cur_user, user, form):
    global G_usermgr
    global G_vclustermgr
    clustername = form.get('clustername', None)
    if (clustername == None):
        return json.dumps({'success':'false', 'message':'clustername is null'})
    logger.info("handle request : scale out %s" % clustername)
    image = {}
    image['name'] = form.get("imagename", None)
    image['type'] = form.get("imagetype", None)
    image['owner'] = form.get("imageowner", None)
    logger.debug("imagename:" + image['name'])
    logger.debug("imagetype:" + image['type'])
    logger.debug("imageowner:" + image['owner'])
    user_info = G_usermgr.selfQuery(cur_user = cur_user)
    user_info = json.dumps(user_info)
    [status, result] = G_vclustermgr.scale_out_cluster(clustername, user, image, user_info)
    if status:
        return json.dumps({'success':'true', 'action':'scale out', 'message':result})
    else:
        return json.dumps({'success':'false', 'action':'scale out', 'message':result})

@app.route("/cluster/scalein/", methods=['POST'])
@login_required
def scalein_cluster(cur_user, user, form):
    global G_vclustermgr
    clustername = form.get('clustername', None)
    if (clustername == None):
        return json.dumps({'success':'false', 'message':'clustername is null'})
    logger.info("handle request : scale in %s" % clustername)
    containername = form.get("containername", None)
    [status, result] = G_vclustermgr.scale_in_cluster(clustername, user, containername)
    if status:
        return json.dumps({'success':'true', 'action':'scale in', 'message':result})
    else:
        return json.dumps({'success':'false', 'action':'scale in', 'message':result})

@app.route("/cluster/start/", methods=['POST'])
@login_required
def start_cluster(cur_user, user, form):
    global G_vclustermgr
    clustername = form.get('clustername', None)
    if (clustername == None):
        return json.dumps({'success':'false', 'message':'clustername is null'})
    logger.info ("handle request : start cluster %s" % clustername)
    [status, result] = G_vclustermgr.start_cluster(clustername, user)
    if status:
        return json.dumps({'success':'true', 'action':'start cluster', 'message':result})
    else:
        return json.dumps({'success':'false', 'action':'start cluster', 'message':result})

@app.route("/cluster/stop/", methods=['POST'])
@login_required
def stop_cluster(cur_user, user, form):
    global G_vclustermgr
    clustername = form.get('clustername', None)
    if (clustername == None):
        return json.dumps({'success':'false', 'message':'clustername is null'})
    logger.info ("handle request : start cluster %s" % clustername)
    [status, result] = G_vclustermgr.stop_cluster(clustername, user)
    if status:
        return json.dumps({'success':'true', 'action':'stop cluster', 'message':result})
    else:
        return json.dumps({'success':'false', 'action':'stop cluster', 'message':result})

@app.route("/cluster/delete/", methods=['POST'])
@login_required
def delete_cluster(cur_user, user, form):
    global G_vclustermgr
    global G_usermgr
    clustername = form.get('clustername', None)
    if (clustername == None):
        return json.dumps({'success':'false', 'message':'clustername is null'})
    logger.info ("handle request : delete cluster %s" % clustername)
    user_info = G_usermgr.selfQuery(cur_user=cur_user)
    user_info = json.dumps(user_info)
    [status, result] = G_vclustermgr.delete_cluster(clustername, user, user_info)
    if status:
        return json.dumps({'success':'true', 'action':'delete cluster', 'message':result})
    else:
        return json.dumps({'success':'false', 'action':'delete cluster', 'message':result})

@app.route("/cluster/info/", methods=['POST'])
@login_required
def info_cluster(cur_user, user, form):
    global G_vclustermgr
    clustername = form.get('clustername', None)
    if (clustername == None):
        return json.dumps({'success':'false', 'message':'clustername is null'})
    logger.info ("handle request : info cluster %s" % clustername)
    [status, result] = G_vclustermgr.get_clusterinfo(clustername, user)
    if status:
        return json.dumps({'success':'true', 'action':'info cluster', 'message':result})
    else:
        return json.dumps({'success':'false', 'action':'info cluster', 'message':result})

@app.route("/cluster/list/", methods=['POST'])
@login_required
def list_cluster(cur_user, user, form):
    global G_vclustermgr
    logger.info ("handle request : list clusters for %s" % user)
    [status, clusterlist] = G_vclustermgr.list_clusters(user)
    if status:
        return json.dumps({'success':'true', 'action':'list cluster', 'clusters':clusterlist})
    else:
        return json.dumps({'success':'false', 'action':'list cluster', 'message':clusterlist})

@app.route("/cluster/flush/", methods=['POST'])
@login_required
def flush_cluster(cur_user, user, form):
    global G_vclustermgr
    clustername = form.get('clustername', None)
    if (clustername == None):
        return json.dumps({'success':'false', 'message':'clustername is null'})
    from_lxc = form.get('from_lxc', None)
    G_vclustermgr.flush_cluster(user,clustername,from_lxc)
    return json.dumps({'success':'true', 'action':'flush'})

@app.route("/cluster/save/", methods=['POST'])
@login_required
def save_cluster(cur_user, user, form):
    global G_vclustermgr
    global G_usermgr
    clustername = form.get('clustername', None)
    if (clustername == None):
        return json.dumps({'success':'false', 'message':'clustername is null'})

    imagename = form.get("image", None)
    description = form.get("description", None)
    containername = form.get("containername", None)
    isforce = form.get("isforce", None)
    if not isforce == "true":
        [status,message] = G_vclustermgr.image_check(user,imagename)
        if not status:
            return json.dumps({'success':'false','reason':'exists', 'message':message})

    user_info = G_usermgr.selfQuery(cur_user = cur_user)
    [status,message] = G_vclustermgr.create_image(user,clustername,containername,imagename,description,user_info["data"]["groupinfo"]["image"])
    if status:
        logger.info("image has been saved")
        return json.dumps({'success':'true', 'action':'save'})
    else:
        logger.debug(message)
        return json.dumps({'success':'false', 'reason':'exceed', 'message':message})


@app.route("/image/list/", methods=['POST'])
@login_required
def list_image(cur_user, user, form):
    global G_imagemgr
    images = G_imagemgr.list_images(user)
    return json.dumps({'success':'true', 'images': images})

@app.route("/image/description/", methods=['POST'])
@login_required
def description_image(cur_user, user, form):
    global G_imagemgr
    image = {}
    image['name'] = form.get("imagename", None)
    image['type'] = form.get("imagetype", None)
    image['owner'] = form.get("imageowner", None)
    description = G_imagemgr.get_image_description(user,image)
    return json.dumps({'success':'true', 'message':description})

@app.route("/image/share/", methods=['POST'])
@login_required
def share_image(cur_user, user, form):
    global G_imagemgr
    image = form.get('image')
    G_imagemgr.shareImage(user,image)
    return json.dumps({'success':'true', 'action':'share'})

@app.route("/image/unshare/", methods=['POST'])
@login_required
def unshare_image(cur_user, user, form):
    global G_imagemgr
    image = form.get('image', None)
    G_imagemgr.unshareImage(user,image)
    return json.dumps({'success':'true', 'action':'unshare'})

@app.route("/image/delete/", methods=['POST'])
@login_required
def delete_image(cur_user, user, form):
    global G_imagemgr
    image = form.get('image', None)
    G_imagemgr.removeImage(user,image)
    return json.dumps({'success':'true', 'action':'delete'})

@app.route("/addproxy/", methods=['POST'])
@login_required
def addproxy(cur_user, user, form):
    global G_vclustermgr
    logger.info ("handle request : add proxy")
    proxy_ip = form.get("ip", None)
    proxy_port = form.get("port", None)
    clustername = form.get("clustername", None)
    [status, message] = G_vclustermgr.addproxy(user,clustername,proxy_ip,proxy_port)
    if status is True:
        return json.dumps({'success':'true', 'action':'addproxy'})
    else:
        return json.dumps({'success':'false', 'message': message})

@app.route("/deleteproxy/", methods=['POST'])
@login_required
def deleteproxy(cur_user, user, form):
    global G_vclustermgr
    logger.info ("handle request : delete proxy")
    clustername = form.get("clustername", None)
    G_vclustermgr.deleteproxy(user,clustername)
    return json.dumps({'success':'true', 'action':'deleteproxy'})

@app.route("/monitor/hosts/<com_id>/<issue>/", methods=['POST'])
@login_required
def hosts_monitor(cur_user, user, form, com_id, issue):
    global G_clustername

    logger.info("handle request: monitor/hosts")
    res = {}
    fetcher = monitor.Fetcher(com_id)
    if issue == 'meminfo':
        res['meminfo'] = fetcher.get_meminfo()
    elif issue == 'cpuinfo':
        res['cpuinfo'] = fetcher.get_cpuinfo()
    elif issue == 'cpuconfig':
        res['cpuconfig'] = fetcher.get_cpuconfig()
    elif issue == 'diskinfo':
        res['diskinfo'] = fetcher.get_diskinfo()
    elif issue == 'osinfo':
        res['osinfo'] = fetcher.get_osinfo()
    elif issue == 'containers':
        res['containers'] = fetcher.get_containers()
    elif issue == 'status':
        res['status'] = fetcher.get_status()
    elif issue == 'containerslist':
        res['containerslist'] = fetcher.get_containerslist()
    elif issue == 'containersinfo':
        res = []
        conlist = fetcher.get_containerslist()
        for container in conlist:
            ans = {}
            confetcher = monitor.Container_Fetcher(etcdaddr,G_clustername)
            ans = confetcher.get_basic_info(container)
            ans['cpu_use'] = confetcher.get_cpu_use(container)
            ans['mem_use'] = confetcher.get_mem_use(container)
            res.append(ans)
    else:
        return json.dumps({'success':'false', 'message':'not supported request'})

    return json.dumps({'success':'true', 'monitor':res})


@app.route("/monitor/vnodes/<con_id>/<issue>/", methods=['POST'])
@login_required
def vnodes_monitor(cur_user, user, form, con_id, issue):
    global G_clustername
    logger.info("handle request: monitor/vnodes")
    res = {}
    fetcher = monitor.Container_Fetcher(con_id)
    if issue == 'cpu_use':
        res['cpu_use'] = fetcher.get_cpu_use()
    elif issue == 'mem_use':
        res['mem_use'] = fetcher.get_mem_use()
    elif issue == 'disk_use':
        res['disk_use'] = fetcher.get_disk_use()
    elif issue == 'basic_info':
        res['basic_info'] = fetcher.get_basic_info()
    elif issue == 'owner':
        names = con_id.split('-')
        result = G_usermgr.query(username = names[0], cur_user = cur_user)
        if result['success'] == 'false':
            res['username'] = ""
            res['truename'] = ""
        else:
            res['username'] = result['data']['username']
            res['truename'] = result['data']['truename']
    else:
        res = "Unspported Method!"
    return json.dumps({'success':'true', 'monitor':res})


@app.route("/monitor/user/quotainfo/", methods=['POST'])
@login_required
def user_quotainfo_monitor(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: monitor/user/quotainfo/")
    user_info = G_usermgr.selfQuery(cur_user = cur_user)
    quotainfo = user_info['data']['groupinfo']
    return json.dumps({'success':'true', 'quotainfo':quotainfo})

@app.route("/monitor/listphynodes/", methods=['POST'])
@login_required
def listphynodes_monitor(cur_user, user, form):
    global G_nodemgr
    logger.info("handle request: monitor/listphynodes/")
    res = {}
    res['allnodes'] = G_nodemgr.get_allnodes()
    return json.dumps({'success':'true', 'monitor':res})


@app.route("/user/modify/", methods=['POST'])
@login_required
def modify_user(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/modify/")
    result = G_usermgr.modify(newValue = form, cur_user = cur_user)
    return json.dumps(result)

@app.route("/user/groupModify/", methods=['POST'])
@login_required
def groupModify_user(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/groupModify/")
    result = G_usermgr.groupModify(newValue = form, cur_user = cur_user)
    return json.dumps(result)


@app.route("/user/query/", methods=['POST'])
@login_required
def query_user(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/query/")
    result = G_usermgr.query(ID = form.get("ID"), cur_user = cur_user)
    if (result.get('success', None) == None or result.get('success', None) == "false"):
        return json.dumps(result)
    else:
        result = G_usermgr.queryForDisplay(user = result['token'])
        return json.dumps(result)


@app.route("/user/add/", methods=['POST'])
@login_required
def add_user(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/add/")
    user = G_usermgr.newuser(cur_user = cur_user)
    user.username = form.get('username', None)
    user.password = form.get('password', None)
    user.e_mail = form.get('e_mail', '')
    user.status = "normal"
    result = G_usermgr.register(user = user, cur_user = cur_user)
    return json.dumps(result)


@app.route("/user/groupadd/", methods=['POST'])
@login_required
def groupadd_user(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/groupadd/")
    result = G_usermgr.groupadd(form = form, cur_user = cur_user)
    return json.dumps(result)


@app.route("/user/chdefault/", methods=['POST'])
@login_required
def chdefault(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/chdefault/")
    result = G_usermgr.change_default_group(form = form, cur_user = cur_user)
    return json.dumps(result)


@app.route("/user/quotaadd/", methods=['POST'])
@login_required
def quotaadd_user(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/quotaadd/")
    result = G_usermgr.quotaadd(form = form, cur_user = cur_user)
    return json.dumps(result)


@app.route("/user/groupdel/", methods=['POST'])
@login_required
def groupdel_user(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/groupdel/")
    result = G_usermgr.groupdel(name = form.get('name', None), cur_user = cur_user)
    return json.dumps(result)


@app.route("/user/data/", methods=['POST'])
@login_required
def data_user(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/data/")
    result = G_usermgr.userList(cur_user = cur_user)
    return json.dumps(result)


@app.route("/user/groupNameList/", methods=['POST'])
@login_required
def groupNameList_user(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/groupNameList/")
    result = G_usermgr.groupListName(cur_user = cur_user)
    return json.dumps(result)


@app.route("/user/groupList/", methods=['POST'])
@login_required
def groupList_user(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/groupList/")
    result = G_usermgr.groupList(cur_user = cur_user)
    return json.dumps(result)


@app.route("/user/groupQuery/", methods=['POST'])
@login_required
def groupQuery_user(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/groupQuery/")
    result = G_usermgr.groupQuery(name = form.get("name"), cur_user = cur_user)
    return json.dumps(result)


@app.route("/user/selfQuery/", methods=['POST'])
@login_required
def selfQuery_user(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/selfQuery/")
    result = G_usermgr.selfQuery(cur_user = cur_user)
    return json.dumps(result)


@app.route("/user/selfModify/", methods=['POST'])
@login_required
def selfModify_user(cur_user, user, form):
    global G_usermgr
    logger.info("handle request: user/selfModify/")
    result = G_usermgr.selfModify(cur_user = cur_user, newValue = form)
    return json.dumps(result)


@app.route("/notification/list/", methods=['POST'])
@login_required
def list_notifications(cur_user, user, form):
    global G_notificationmgr
    logger.info("handle request: notification/list/")
    result = G_notificationmgr.list_notifications(cur_user=cur_user, form=form)
    return json.dumps(result)


@app.route("/notification/create/", methods=['POST'])
@login_required
def create_notification(cur_user, user, form):
    global G_notificationmgr
    logger.info("handle request: notification/create/")
    result = G_notificationmgr.create_notification(cur_user=cur_user, form=form)
    return json.dumps(result)


@app.route("/notification/modify/", methods=['POST'])
@login_required
def modify_notification(cur_user, user, form):
    global G_notificationmgr
    logger.info("handle request: notification/modify/")
    result = G_notificationmgr.modify_notification(cur_user=cur_user, form=form)
    return json.dumps(result)

@app.route("/notification/mail/", methods=['POST'])
@login_required
def mail_notification(cur_user, user, form):
    global G_notificationmgr
    logger.info("handle request: notification/mail/")
    result = G_notificationmgr.mail_notification(cur_user=cur_user, form=form)
    return json.dumps(result)

@app.route("/notification/delete/", methods=['POST'])
@login_required
def delete_notification(cur_user, user, form):
    global G_notificationmgr
    logger.info("handle request: notification/delete/")
    result = G_notificationmgr.delete_notification(cur_user=cur_user, form=form)
    return json.dumps(result)


@app.route("/notification/query_self/", methods=['POST'])
@login_required
def query_self_notification_simple_infos(cur_user, user, form):
    global G_notificationmgr
    logger.info("handle request: notification/query_self/")
    result = G_notificationmgr.query_self_notification_simple_infos(cur_user=cur_user, form=form)
    return json.dumps(result)


@app.route("/notification/query/", methods=['POST'])
@login_required
def query_notification(cur_user, user, form):
    global G_notificationmgr
    logger.info("handle request: notification/query/")
    result = G_notificationmgr.query_notification(cur_user=cur_user, form=form)
    return json.dumps(result)


@app.route("/notification/query/all/", methods=['POST'])
@login_required
def query_self_notifications_infos(cur_user, user, form):
    global G_notificationmgr
    logger.info("handle request: notification/query/all/")
    result = G_notificationmgr.query_self_notifications_infos(cur_user=cur_user, form=form)
    return json.dumps(result)


@app.route("/system/parmList/", methods=['POST'])
@login_required
def parmList_system(cur_user, user, form):
    global G_sysmgr
    logger.info("handle request: system/parmList/")
    result = G_sysmgr.getParmList()
    return json.dumps(result)

@app.route("/system/modify/", methods=['POST'])
@login_required
def modify_system(cur_user, user, form):
    global G_sysmgr
    logger.info("handle request: system/modify/")
    field = form.get("field", None)
    parm = form.get("parm", None)
    val = form.get("val", None)
    [status, message] = G_sysmgr.modify(field,parm,val)
    if status is True:
        return json.dumps({'success':'true', 'action':'modify_system'})
    else:
        return json.dumps({'success':'false', 'message': message})
    return json.dumps(result)

@app.route("/system/clear_history/", methods=['POST'])
@login_required
def clear_system(cur_user, user, form):
    global G_sysmgr
    logger.info("handle request: system/clear_history/")
    field = form.get("field", None)
    parm = form.get("parm", None)
    [status, message] = G_sysmgr.clear(field,parm)
    if status is True:
        return json.dumps({'success':'true', 'action':'clear_history'})
    else:
        return json.dumps({'success':'false', 'message': message})
    return json.dumps(result)

@app.route("/system/add/", methods=['POST'])
@login_required
def add_system(cur_user, user, form):
    global G_sysmgr
    logger.info("handle request: system/add/")
    field = form.get("field", None)
    parm = form.get("parm", None)
    val = form.get("val", None)
    [status, message] = G_sysmgr.add(field, parm, val)
    if status is True:
        return json.dumps({'success':'true', 'action':'add_parameter'})
    else:
        return json.dumps({'success':'false', 'message': message})
    return json.dumps(result)

@app.route("/system/delete/", methods=['POST'])
@login_required
def delete_system(cur_user, user, form):
    global G_sysmgr
    logger.info("handle request: system/delete/")
    field = form.get("field", None)
    parm = form.get("parm", None)
    [status, message] = G_sysmgr.delete(field,parm)
    if status is True:
        return json.dumps({'success':'true', 'action':'delete_parameter'})
    else:
        return json.dumps({'success':'false', 'message': message})
    return json.dumps(result)

@app.route("/system/reset_all/", methods=['POST'])
@login_required
def resetall_system(cur_user, user, form):
    global G_sysmgr
    logger.info("handle request: system/reset_all/")
    field = form.get("field", None)
    [status, message] = G_sysmgr.reset_all(field)
    if status is True:
        return json.dumps({'success':'true', 'action':'reset_all'})
    else:
        return json.dumps({'success':'false', 'message': message})
    return json.dumps(result)

@app.errorhandler(500)
def internal_server_error(error):
    logger.debug("An internel server error occured")
    logger.error(traceback.format_exc())
    return json.dumps({'success':'false', 'message':'500 Internal Server Error', 'Unauthorized': 'True'})


if __name__ == '__main__':
    logger.info('Start Flask...:')
    try:
        secret_key_file = open(env.getenv('FS_PREFIX') + '/local/httprest_secret_key.txt')
        app.secret_key = secret_key_file.read()
        secret_key_file.close()
    except:
        from base64 import b64encode
        from os import urandom
        secret_key = urandom(24)
        secret_key = b64encode(secret_key).decode('utf-8')
        app.secret_key = secret_key
        secret_key_file = open(env.getenv('FS_PREFIX') + '/local/httprest_secret_key.txt', 'w')
        secret_key_file.write(secret_key)
        secret_key_file.close()

    os.environ['APP_KEY'] = app.secret_key
    runcmd = sys.argv[0]
    app.runpath = runcmd.rsplit('/', 1)[0]

    global G_nodemgr
    global G_vclustermgr
    global G_usermgr
    global G_notificationmgr
    global etcdclient
    global G_networkmgr
    global G_clustername
    global G_sysmgr
    # move 'tools.loadenv' to the beginning of this file

    fs_path = env.getenv("FS_PREFIX")
    logger.info("using FS_PREFIX %s" % fs_path)

    etcdaddr = env.getenv("ETCD")
    logger.info("using ETCD %s" % etcdaddr)

    G_clustername = env.getenv("CLUSTER_NAME")
    logger.info("using CLUSTER_NAME %s" % G_clustername)

    # get network interface
    net_dev = env.getenv("NETWORK_DEVICE")
    logger.info("using NETWORK_DEVICE %s" % net_dev)

    ipaddr = network.getip(net_dev)
    if ipaddr==False:
        logger.error("network device is not correct")
        sys.exit(1)
    else:
        logger.info("using ipaddr %s" % ipaddr)

    # init etcdlib client
    try:
        etcdclient = etcdlib.Client(etcdaddr, prefix = G_clustername)
    except Exception:
        logger.error ("connect etcd failed, maybe etcd address not correct...")
        sys.exit(1)
    mode = 'recovery'
    if len(sys.argv) > 1 and sys.argv[1] == "new":
        mode = 'new'

    # do some initialization for mode: new/recovery
    if mode == 'new':
        # clean and initialize the etcd table
        if etcdclient.isdir(""):
            etcdclient.clean()
        else:
            etcdclient.createdir("")
        # token is saved at fs_path/golbal/token
        token = tools.gen_token()
        tokenfile = open(fs_path+"/global/token", 'w')
        tokenfile.write(token)
        tokenfile.write("\n")
        tokenfile.close()
        etcdclient.setkey("token", token)
        etcdclient.setkey("service/master", ipaddr)
        etcdclient.setkey("service/mode", mode)
        etcdclient.createdir("machines/allnodes")
        etcdclient.createdir("machines/runnodes")
        etcdclient.setkey("vcluster/nextid", "1")
        # clean all users vclusters files : FS_PREFIX/global/users/<username>/clusters/<clusterid>
        usersdir = fs_path+"/global/users/"
        for user in os.listdir(usersdir):
            shutil.rmtree(usersdir+user+"/clusters")
            shutil.rmtree(usersdir+user+"/hosts")
            os.mkdir(usersdir+user+"/clusters")
            os.mkdir(usersdir+user+"/hosts")
    else:
        # check whether cluster exists
        if not etcdclient.isdir("")[0]:
            logger.error ("cluster not exists, you should use mode:new ")
            sys.exit(1)
        # initialize the etcd table for recovery
        token = tools.gen_token()
        tokenfile = open(fs_path+"/global/token", 'w')
        tokenfile.write(token)
        tokenfile.write("\n")
        tokenfile.close()
        etcdclient.setkey("token", token)
        etcdclient.setkey("service/master", ipaddr)
        etcdclient.setkey("service/mode", mode)
        if etcdclient.isdir("_lock")[0]:
            etcdclient.deldir("_lock")

    G_usermgr = userManager.userManager('root')
    G_notificationmgr = notificationmgr.NotificationMgr()

    clusternet = env.getenv("CLUSTER_NET")
    logger.info("using CLUSTER_NET %s" % clusternet)

    G_sysmgr = sysmgr.SystemManager()

    G_networkmgr = network.NetworkMgr(clusternet, etcdclient, mode)
    G_networkmgr.printpools()

    # start NodeMgr and NodeMgr will wait for all nodes to start ...
    G_nodemgr = nodemgr.NodeMgr(G_networkmgr, etcdclient, addr = ipaddr, mode=mode)
    logger.info("nodemgr started")
    G_vclustermgr = vclustermgr.VclusterMgr(G_nodemgr, G_networkmgr, etcdclient, ipaddr, mode)
    logger.info("vclustermgr started")
    G_imagemgr = imagemgr.ImageMgr()
    logger.info("imagemgr started")
    master_collector = monitor.Master_Collector(G_nodemgr)
    master_collector.start()

    logger.info("startting to listen on: ")
    masterip = env.getenv('MASTER_IP')
    logger.info("using MASTER_IP %s", masterip)

    masterport = env.getenv('MASTER_PORT')
    logger.info("using MASTER_PORT %d", int(masterport))

    # server = http.server.HTTPServer((masterip, masterport), DockletHttpHandler)
    logger.info("starting master server")

    app.run(host = masterip, port = masterport, threaded=True)
