#!/usr/bin/python3

# load environment variables in the beginning
# because some modules need variables when import
# for example, userManager/model.py

import sys
if sys.path[0].endswith("master"):
    sys.path[0] = sys.path[0][:-6]
from flask import Flask, request

# must first init loadenv
from utils import tools, env
# default CONFIG=/opt/docklet/local/docklet-running.conf

config = env.getenv("CONFIG")
tools.loadenv(config)

# second init logging
# must import logger after initlogging, ugly
from utils.log import initlogging
initlogging("docklet-master")
from utils.log import logger

import os
import http.server, cgi, json, sys, shutil, traceback
import xmlrpc.client
from socketserver import ThreadingMixIn
from utils import etcdlib, imagemgr
from master import nodemgr, vclustermgr, notificationmgr, lockmgr, cloudmgr, jobmgr, taskmgr
from utils.logs import logs
from master import userManager, beansapplicationmgr, monitor, sysmgr, network, releasemgr
from worker.monitor import History_Manager
import threading
import requests
from utils.nettools import portcontrol

#default EXTERNAL_LOGIN=False
external_login = env.getenv('EXTERNAL_LOGIN')
if (external_login == 'TRUE'):
    from userDependence import external_auth

userpoint = "http://" + env.getenv('USER_IP') + ":" + str(env.getenv('USER_PORT'))
G_userip = env.getenv("USER_IP")

def post_to_user(url = '/', data={}):
    return requests.post(userpoint+url,data=data).json()

app = Flask(__name__)

from functools import wraps


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        logger.info ("get request, path: %s" % request.path)
        token = request.form.get("token", None)
        if (token == None):
            logger.info ("get request without token, path: %s" % request.path)
            return json.dumps({'success':'false', 'message':'user or key is null'})
        result = post_to_user("/authtoken/", {'token':token})
        if result.get('success') == 'true':
            username = result.get('username')
            beans = result.get('beans')
        else:
            return result
        #if (cur_user == None):
        #    return json.dumps({'success':'false', 'message':'token failed or expired', 'Unauthorized': 'True'})
        return func(username, beans, request.form, *args, **kwargs)

    return wrapper

def auth_key_required(func):
    @wraps(func)
    def wrapper(*args,**kwargs):
        key_1 = env.getenv('AUTH_KEY')
        key_2 = request.form.get("auth_key",None)
        #logger.info(str(ip) + " " + str(G_userip))
        if key_2 is not None and key_1 == key_2:
           return func(*args, **kwargs)
        else:
           return json.dumps({'success':'false','message': 'auth_key is required!'})

    return wrapper

def beans_check(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        beans = args[1]
        if beans <= 0:
            return json.dumps({'success':'false','message':'user\'s beans are less than or equal to zero!'})
        else:
            return func(*args, **kwargs)

    return wrapper

@app.route("/isalive/", methods = ['POST'])
@login_required
def isalive(user, beans, form):
    return json.dumps({'success':'true'})



@app.route("/logs/list/", methods=['POST'])
@login_required
def logs_list(user, beans, form):
    user_group = post_to_user('/user/selfQuery/', {'token': request.form.get("token", None)}).get('data', None).get('group', None)
    return json.dumps(logs.list(user_group = user_group))

@app.route("/logs/get/", methods=['POST'])
@login_required
def logs_get(user, beans, form):
    user_group = post_to_user('/user/selfQuery/', {'token': request.form.get("token", None)}).get('data', None).get('group', None)
    return json.dumps(logs.get(user_group = user_group, filename = form.get('filename', '')))


@app.route("/cluster/create/", methods=['POST'])
@login_required
@beans_check
def create_cluster(user, beans, form):
    global G_vclustermgr
    global G_ulockmgr
    clustername = form.get('clustername', None)
    if (clustername == None):
        return json.dumps({'success':'false', 'message':'clustername is null'})
    G_ulockmgr.acquire(user)
    try:
        image = {}
        image['name'] = form.get("imagename", None)
        image['type'] = form.get("imagetype", None)
        image['owner'] = form.get("imageowner", None)
        user_info = post_to_user("/user/selfQuery/", {'token':form.get("token")})
        user_info = json.dumps(user_info)
        logger.info ("handle request : create cluster %s with image %s " % (clustername, image['name']))
        setting = {
                'cpu': form.get('cpuSetting'),
                'memory': form.get('memorySetting'),
                'disk': form.get('diskSetting')
                }
        res = post_to_user("/user/usageInc/", {'token':form.get('token'), 'setting':json.dumps(setting)})
        status = res.get('success')
        result = res.get('result')
        if not status:
            return json.dumps({'success':'false', 'action':'create cluster', 'message':result})
        [status, result] = G_vclustermgr.create_cluster(clustername, user, image, user_info, setting)
        if status:
            return json.dumps({'success':'true', 'action':'create cluster', 'message':result})
        else:
            post_to_user("/user/usageRecover/", {'token':form.get('token'), 'setting':json.dumps(setting)})
            return json.dumps({'success':'false', 'action':'create cluster', 'message':result})
    except Exception as ex:
        logger.error(str(ex))
        return json.dumps({'success':'false', 'message': str(ex)})
    finally:
        G_ulockmgr.release(user)

@app.route("/cluster/scaleout/", methods=['POST'])
@login_required
@beans_check
def scaleout_cluster(user, beans, form):
    global G_vclustermgr
    global G_ulockmgr
    clustername = form.get('clustername', None)
    logger.info ("scaleout: %s" % form)
    if (clustername == None):
        return json.dumps({'success':'false', 'message':'clustername is null'})
    G_ulockmgr.acquire(user)
    try:
        logger.info("handle request : scale out %s" % clustername)
        image = {}
        image['name'] = form.get("imagename", None)
        image['type'] = form.get("imagetype", None)
        image['owner'] = form.get("imageowner", None)
        user_info = post_to_user("/user/selfQuery/", {'token':form.get("token")})
        user_info = json.dumps(user_info)
        setting = {
                'cpu': form.get('cpuSetting'),
                'memory': form.get('memorySetting'),
                'disk': form.get('diskSetting')
                }
        res = post_to_user("/user/usageInc/", {'token':form.get('token'), 'setting':json.dumps(setting)})
        status = res.get('success')
        result = res.get('result')
        if not status:
            return json.dumps({'success':'false', 'action':'scale out', 'message': result})
        [status, result] = G_vclustermgr.scale_out_cluster(clustername, user, image, user_info, setting)
        if status:
            return json.dumps({'success':'true', 'action':'scale out', 'message':result})
        else:
            post_to_user("/user/usageRecover/", {'token':form.get('token'), 'setting':json.dumps(setting)})
            return json.dumps({'success':'false', 'action':'scale out', 'message':result})
    except Exception as ex:
        logger.error(str(ex))
        return json.dumps({'success':'false', 'message': str(ex)})
    finally:
        G_ulockmgr.release(user)

@app.route("/cluster/scalein/", methods=['POST'])
@login_required
def scalein_cluster(user, beans, form):
    global G_vclustermgr
    global G_ulockmgr
    clustername = form.get('clustername', None)
    if (clustername == None):
        return json.dumps({'success':'false', 'message':'clustername is null'})
    G_ulockmgr.acquire(user)
    try:
        logger.info("handle request : scale in %s" % clustername)
        containername = form.get("containername", None)
        [status, usage_info] = G_vclustermgr.get_clustersetting(clustername, user, containername, False)
        if status:
            post_to_user("/user/usageRelease/", {'token':form.get('token'), 'cpu':usage_info['cpu'], 'memory':usage_info['memory'],'disk':usage_info['disk']})
        [status, result] = G_vclustermgr.scale_in_cluster(clustername, user, containername)
        if status:
            return json.dumps({'success':'true', 'action':'scale in', 'message':result})
        else:
            return json.dumps({'success':'false', 'action':'scale in', 'message':result})
    except Exception as ex:
        logger.error(str(ex))
        return json.dumps({'success':'false', 'message': str(ex)})
    finally:
        G_ulockmgr.release(user)

@app.route("/cluster/start/", methods=['POST'])
@login_required
@beans_check
def start_cluster(user, beans, form):
    global G_vclustermgr
    global G_ulockmgr
    clustername = form.get('clustername', None)
    if (clustername == None):
        return json.dumps({'success':'false', 'message':'clustername is null'})
    G_ulockmgr.acquire(user)
    try:
        user_info = post_to_user("/user/selfQuery/", {'token':form.get("token")})
        logger.info ("handle request : start cluster %s" % clustername)
        [status, result] = G_vclustermgr.start_cluster(clustername, user, user_info)
        if status:
            return json.dumps({'success':'true', 'action':'start cluster', 'message':result})
        else:
            return json.dumps({'success':'false', 'action':'start cluster', 'message':result})
    except Exception as ex:
        logger.error(str(ex))
        return json.dumps({'success':'false', 'message': str(ex)})
    finally:
        G_ulockmgr.release(user)

@app.route("/cluster/stop/", methods=['POST'])
@login_required
def stop_cluster(user, beans, form):
    global G_vclustermgr
    global G_ulockmgr
    clustername = form.get('clustername', None)
    if (clustername == None):
        return json.dumps({'success':'false', 'message':'clustername is null'})
    G_ulockmgr.acquire(user)
    try:
        logger.info ("handle request : stop cluster %s" % clustername)
        [status, result] = G_vclustermgr.stop_cluster(clustername, user)
        if status:
            return json.dumps({'success':'true', 'action':'stop cluster', 'message':result})
        else:
            return json.dumps({'success':'false', 'action':'stop cluster', 'message':result})
    except Exception as ex:
        logger.error(str(ex))
        return json.dumps({'success':'false', 'message': str(ex)})
    finally:
        G_ulockmgr.release(user)

@app.route("/cluster/delete/", methods=['POST'])
@login_required
def delete_cluster(user, beans, form):
    global G_vclustermgr
    global G_ulockmgr
    clustername = form.get('clustername', None)
    if (clustername == None):
        return json.dumps({'success':'false', 'message':'clustername is null'})
    G_ulockmgr.acquire(user)
    try:
        logger.info ("handle request : delete cluster %s" % clustername)
        user_info = post_to_user("/user/selfQuery/" , {'token':form.get("token")})
        user_info = json.dumps(user_info)
        [status, usage_info] = G_vclustermgr.get_clustersetting(clustername, user, "all", True)
        if status:
            post_to_user("/user/usageRelease/", {'token':form.get('token'), 'cpu':usage_info['cpu'], 'memory':usage_info['memory'],'disk':usage_info['disk']})
        [status, result] = G_vclustermgr.delete_cluster(clustername, user, user_info)
        if status:
            return json.dumps({'success':'true', 'action':'delete cluster', 'message':result})
        else:
            return json.dumps({'success':'false', 'action':'delete cluster', 'message':result})
    except Exception as ex:
        logger.error(str(ex))
        return json.dumps({'success':'false', 'message': str(ex)})
    finally:
        G_ulockmgr.release(user)

@app.route("/cluster/info/", methods=['POST'])
@login_required
def info_cluster(user, beans, form):

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
def list_cluster(user, beans, form):
    global G_vclustermgr
    logger.info ("handle request : list clusters for %s" % user)
    [status, clusterlist] = G_vclustermgr.list_clusters(user)
    if status:
        return json.dumps({'success':'true', 'action':'list cluster', 'clusters':clusterlist})
    else:
        return json.dumps({'success':'false', 'action':'list cluster', 'message':clusterlist})

@app.route("/cluster/stopall/",methods=['POST'])
@auth_key_required
def stopall_cluster():
    global G_vclustermgr
    global G_ulockmgr
    user = request.form.get('username',None)
    if user is None:
        return json.dumps({'success':'false', 'message':'User is required!'})
    G_ulockmgr.acquire(user)
    try:
        logger.info ("handle request : stop all clusters for %s" % user)
        [status, clusterlist] = G_vclustermgr.list_clusters(user)
        if status:
            for cluster in clusterlist:
                G_vclustermgr.stop_cluster(cluster,user)
            return json.dumps({'success':'true', 'action':'stop all cluster'})
        else:
            return json.dumps({'success':'false', 'action':'stop all cluster', 'message':clusterlist})
    except Exception as ex:
        logger.error(str(ex))
        return json.dumps({'success':'false', 'message': str(ex)})
    finally:
        G_ulockmgr.release(user)

@app.route("/cluster/flush/", methods=['POST'])
@login_required
def flush_cluster(user, beans, form):
    global G_vclustermgr
    clustername = form.get('clustername', None)
    if (clustername == None):
        return json.dumps({'success':'false', 'message':'clustername is null'})
    from_lxc = form.get('from_lxc', None)
    G_vclustermgr.flush_cluster(user,clustername,from_lxc)
    return json.dumps({'success':'true', 'action':'flush'})

@app.route("/cluster/save/", methods=['POST'])
@login_required
def save_cluster(user, beans, form):
    global G_vclustermgr
    clustername = form.get('clustername', None)
    if (clustername == None):
        return json.dumps({'success':'false', 'message':'clustername is null'})

    imagename = form.get("image", None)
    description = form.get("description", None)
    containername = form.get("containername", None)
    isforce = form.get("isforce", None)
    G_ulockmgr.acquire(user)
    try:
        if not isforce == "true":
            [status,message] = G_vclustermgr.image_check(user,imagename)
            if not status:
                return json.dumps({'success':'false','reason':'exists', 'message':message})

        user_info = post_to_user("/user/selfQuery/", {'token':form.get("token")})
        [status,message] = G_vclustermgr.create_image(user,clustername,containername,imagename,description,user_info["data"]["groupinfo"]["image"])
        if status:
            logger.info("image has been saved")
            return json.dumps({'success':'true', 'action':'save'})
        else:
            logger.debug(message)
            return json.dumps({'success':'false', 'reason':'exceed', 'message':message})
    except Exception as ex:
        logger.error(str(ex))
        return json.dumps({'success':'false', 'message': str(ex)})
    finally:
        G_ulockmgr.release(user)

@app.route("/admin/ulock/release/", methods=['POST'])
@login_required
def release_ulock(user, beans, form):
    global G_ulockmgr
    if user != 'root':
        return json.dumps({'success':'false', 'message':'root is required.'})
    release_user = form.get("ulockname",None)
    if release_user is None:
        return json.dumps({'success':'false', 'message':'ulockname is required.'})

    try:
        G_ulockmgr.release(release_user)
    except Exception as e:
        logger.error(traceback.format_exc())
        return json.dumps({'success':'false', 'message':'fail to release lock %s' % release_user})
    return json.dumps({'success':'true', 'message':'lock %s release successfully' % release_user})

@app.route("/admin/migrate_cluster/", methods=['POST'])
@auth_key_required
def migrate_cluster():
    global G_vclustermgr
    global G_ulockmgr
    user = request.form.get('username',None)
    if user is None:
        return json.dumps({'success':'false', 'message':'User is required!'})
    clustername = request.form.get('clustername', None)
    if (clustername == None):
        return json.dumps({'success':'false', 'message':'clustername is null'})
    new_hosts = request.form.get('new_hosts', None)
    if (new_hosts == None):
        return json.dumps({'success':'false', 'message':'new_hosts is null'})
    new_host_list = new_hosts.split(',')
    G_ulockmgr.acquire(user)
    auth_key = env.getenv('AUTH_KEY')
    try:
        logger.info ("handle request : migrate cluster to %s. user:%s clustername:%s" % (str(new_hosts), user, clustername))
        res = post_to_user("/master/user/groupinfo/", {'auth_key':auth_key})
        groups = json.loads(res['groups'])
        quotas = {}
        for group in groups:
            #logger.info(group)
            quotas[group['name']] = group['quotas']
        rc_info = post_to_user("/master/user/recoverinfo/", {'username':user,'auth_key':auth_key})
        groupname = rc_info['groupname']
        user_info = {"data":{"id":rc_info['uid'],"groupinfo":quotas[groupname]}}

        logger.info("Migrate cluster for user(%s) cluster(%s) to new_hosts(%s). user_info(%s)"
                    %(clustername, user, str(new_host_list), user_info))

        [status,msg] = G_vclustermgr.migrate_cluster(clustername, user, new_host_list, user_info)
        if not status:
            logger.error(msg)
            return json.dumps({'success':'false', 'message': msg})
        return json.dumps({'success':'true', 'action':'migrate_container'})
    except Exception as ex:
        logger.error(traceback.format_exc())
        return json.dumps({'success':'false', 'message': str(ex)})
    finally:
        G_ulockmgr.release(user)

@app.route("/host/migrate/", methods=['POST'])
@login_required
def migrate_host(user, beans, form):
    global G_vclustermgr
    global G_ulockmgr
    src_host = request.form.get('src_host', None)
    dst_host_list = request.form.getlist('dst_host_list', None)

    if src_host is None or dst_host_list is None:
        return json.dumps({'success':'false', 'message': 'src host or dst host list is null'})
    [status, msg] = G_vclustermgr.migrate_host(src_host, dst_host_list, G_ulockmgr)
    if status:
        return json.dumps({'success': 'true', 'action': 'migrate_host'})
    else:
        return json.dumps({'success': 'false', 'message': msg})



@app.route("/image/list/", methods=['POST'])
@login_required
def list_image(user, beans, form):
    global G_imagemgr
    images = G_imagemgr.list_images(user)
    return json.dumps({'success':'true', 'images': images})

@app.route("/image/updatebase/", methods=['POST'])
@login_required
def update_base(user, beans, form):
    global G_imagemgr
    global G_vclustermgr
    [success, status] = G_imagemgr.update_base_image(user, G_vclustermgr, form.get('image'))
    return json.dumps({'success':'true', 'message':status})

@app.route("/image/description/", methods=['POST'])
@login_required
def description_image(user, beans, form):
    global G_imagemgr
    image = {}
    image['name'] = form.get("imagename", None)
    image['type'] = form.get("imagetype", None)
    image['owner'] = form.get("imageowner", None)
    description = G_imagemgr.get_image_description(user,image)
    return json.dumps({'success':'true', 'message':description})

@app.route("/image/share/", methods=['POST'])
@login_required
def share_image(user, beans, form):
    global G_imagemgr
    image = form.get('image')
    G_ulockmgr.acquire(user)
    try:
        G_imagemgr.shareImage(user,image)
        return json.dumps({'success':'true', 'action':'share'})
    except Exception as ex:
        logger.error(str(ex))
        return json.dumps({'success':'false', 'message': str(ex)})
    finally:
        G_ulockmgr.release(user)

@app.route("/image/unshare/", methods=['POST'])
@login_required
def unshare_image(user, beans, form):
    global G_imagemgr
    image = form.get('image', None)
    G_ulockmgr.acquire(user)
    try:
        G_imagemgr.unshareImage(user,image)
        return json.dumps({'success':'true', 'action':'unshare'})
    except Exception as ex:
        logger.error(str(ex))
        return json.dumps({'success':'false', 'message': str(ex)})
    finally:
        G_ulockmgr.release(user)

@app.route("/image/delete/", methods=['POST'])
@login_required
def delete_image(user, beans, form):
    global G_imagemgr
    image = form.get('image', None)
    G_ulockmgr.acquire(user)
    try:
        G_imagemgr.removeImage(user,image)
        return json.dumps({'success':'true', 'action':'delete'})
    except Exception as ex:
        logger.error(str(ex))
        return json.dumps({'success':'false', 'message': str(ex)})
    finally:
        G_ulockmgr.release(user)

@app.route("/image/copy/", methods=['POST'])
@login_required
def copy_image(user, beans, form):
    global G_imagemgr
    global G_ulockmgr
    image = form.get('image', None)
    target = form.get('target',None)
    token = form.get('token',None)
    G_ulockmgr.acquire(user)
    try:
        res = G_imagemgr.copyImage(user,image,token,target)
        return json.dumps(res)
    except Exception as ex:
        logger.error(str(ex))
        return json.dumps({'success':'false', 'message': str(ex)})
    finally:
        G_ulockmgr.release(user)

@app.route("/image/copytarget/", methods=['POST'])
@login_required
@auth_key_required
def copytarget_image(user, beans, form):
    global G_imagemgr
    global G_ulockmgr
    imagename = form.get('imagename',None)
    description = form.get('description',None)
    try:
        G_ulockmgr.acquire(user)
        res = G_imagemgr.updateinfo(user,imagename,description)
        return json.dumps({'success':'true', 'action':'copy image to target.'})
    except Exception as ex:
        logger.error(str(ex))
        return json.dumps({'success':'false', 'message':str(ex)})
    finally:
        G_ulockmgr.release(user)

@app.route("/cloud/setting/get/", methods=['POST'])
@login_required
def query_account_cloud(cur_user, user, form):
    global G_cloudmgr
    logger.info("handle request: cloud/setting/get/")
    result = G_cloudmgr.getSettingFile()
    return json.dumps(result)

@app.route("/cloud/setting/modify/", methods=['POST'])
@login_required
def modify_account_cloud(cur_user, user, form):
    global G_cloudmgr
    logger.info("handle request: cloud/setting/modify/")
    result = G_cloudmgr.modifySettingFile(form.get('setting',None))
    return json.dumps(result)

@app.route("/cloud/node/add/", methods=['POST'])
@login_required
def add_node_cloud(user, beans, form):
    global G_cloudmgr
    logger.info("handle request: cloud/node/add/")
    G_cloudmgr.engine.addNodeAsync()
    result = {'success':'true'}
    return json.dumps(result)

@app.route("/addproxy/", methods=['POST'])
@login_required
def addproxy(user, beans, form):
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
def deleteproxy(user, beans, form):
    global G_vclustermgr
    logger.info ("handle request : delete proxy")
    clustername = form.get("clustername", None)
    G_vclustermgr.deleteproxy(user,clustername)
    return json.dumps({'success':'true', 'action':'deleteproxy'})

@app.route("/port_mapping/add/", methods=['POST'])
@login_required
def add_port_mapping(user, beans, form):
    global G_vclustermgr
    global G_ulockmgr
    logger.info ("handle request : add port mapping")
    node_name = form.get("node_name",None)
    node_ip = form.get("node_ip", None)
    node_port = form.get("node_port", None)
    clustername = form.get("clustername", None)
    if node_name is None or node_ip is None or node_port is None or clustername is None:
        return json.dumps({'success':'false', 'message': 'Illegal form.'})
    user_info = post_to_user("/user/selfQuery/", data = {"token": form.get("token")})
    G_ulockmgr.acquire(user)
    try:
        [status, message] = G_vclustermgr.add_port_mapping(user,clustername,node_name,node_ip,node_port,user_info['data']['groupinfo'])
        if status is True:
            return json.dumps({'success':'true', 'action':'addproxy'})
        else:
            return json.dumps({'success':'false', 'message': message})
    except Exception as ex:
        logger.error(str(ex))
        return json.dumps({'success':'false', 'message':str(ex)})
    finally:
        G_ulockmgr.release(user)

@app.route("/port_mapping/delete/", methods=['POST'])
@login_required
def delete_port_mapping(user, beans, form):
    global G_vclustermgr
    global G_ulockmgr
    logger.info ("handle request : delete port mapping")
    node_name = form.get("node_name",None)
    clustername = form.get("clustername", None)
    node_port = form.get("node_port", None)
    if node_name is None or clustername is None:
        return json.dumps({'success':'false', 'message': 'Illegal form.'})
    G_ulockmgr.acquire(user)
    try:
        [status, message] = G_vclustermgr.delete_port_mapping(user,clustername,node_name,node_port)
        if status is True:
            return json.dumps({'success':'true', 'action':'addproxy'})
        else:
            return json.dumps({'success':'false', 'message': message})
    except Exception as ex:
        logger.error(str(ex))
        return json.dumps({'success':'false', 'message':str(ex)})
    finally:
        G_ulockmgr.release(user)

@app.route("/monitor/hosts/<com_id>/<issue>/", methods=['POST'])
@login_required
def hosts_monitor(user, beans, form, com_id, issue):
    global G_clustername

    logger.info("handle request: monitor/hosts")
    res = {}
    fetcher = monitor.Fetcher(com_id)
    if issue == 'meminfo':
        res['meminfo'] = fetcher.get_meminfo()
    elif issue == 'gpuinfo':
        res['gpuinfo'] = fetcher.get_gpuinfo()
    elif issue == 'cpuinfo':
        res['cpuinfo'] = fetcher.get_cpuinfo()
    elif issue == 'cpuconfig':
        res['cpuconfig'] = fetcher.get_cpuconfig()
    elif issue == 'diskinfo':
        res['diskinfo'] = fetcher.get_diskinfo()
    elif issue == 'osinfo':
        res['osinfo'] = fetcher.get_osinfo()
    #elif issue == 'concpuinfo':
     #   res['concpuinfo'] = fetcher.get_concpuinfo()
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
def vnodes_monitor(user, beans, form, con_id, issue):
    global G_clustername
    global G_historymgr
    logger.info("handle request: monitor/vnodes")
    res = {}
    fetcher = monitor.Container_Fetcher(con_id)
    if issue == 'info':
        res = fetcher.get_info()
    elif issue == 'cpu_use':
        res['cpu_use'] = fetcher.get_cpu_use()
    elif issue == 'mem_use':
        res['mem_use'] = fetcher.get_mem_use()
    elif issue == 'disk_use':
        res['disk_use'] = fetcher.get_disk_use()
    elif issue == 'basic_info':
        res['basic_info'] = fetcher.get_basic_info()
    elif issue == 'net_stats':
        res['net_stats'] = fetcher.get_net_stats()
    elif issue == 'history':
        res['history'] = G_historymgr.getHistory(con_id)
    elif issue == 'owner':
        names = con_id.split('-')
        result = post_to_user("/user/query/", data = {"token": form.get(token)})
        if result['success'] == 'false':
            res['username'] = ""
            res['truename'] = ""
        else:
            res['username'] = result['data']['username']
            res['truename'] = result['data']['truename']
    else:
        res = "Unspported Method!"
    return json.dumps({'success':'true', 'monitor':res})


@app.route("/monitor/user/<issue>/", methods=['POST'])
@login_required
def user_quotainfo_monitor(user, beans, form, issue):
    global G_historymgr
    if issue == 'quotainfo':
        logger.info("handle request: monitor/user/quotainfo/")
        user_info = post_to_user("/user/selfQuery/", {'token':form.get("token")})
        quotainfo = user_info['data']['groupinfo']
        return json.dumps({'success':'true', 'quotainfo':quotainfo})
    elif issue == 'createdvnodes':
        logger.info("handle request: monitor/user/createdvnodes/")
        res = G_historymgr.getCreatedVNodes(user)
        return json.dumps({'success':'true', 'createdvnodes':res})
    elif issue == 'net_stats':
        logger.info("handle request: monitor/user/net_stats/")
        res = monitor.Container_Fetcher.get_user_net_stats(user)
        return json.dumps({'success':'true', 'net_stats':res})
    else:
        return json.dumps({'success':'false', 'message':"Unspported Method!"})

@app.route("/monitor/listphynodes/", methods=['POST'])
@login_required
def listphynodes_monitor(user, beans, form):
    global G_nodemgr
    logger.info("handle request: monitor/listphynodes/")
    res = {}
    res['allnodes'] = G_nodemgr.get_nodeips()
    return json.dumps({'success':'true', 'monitor':res})

@app.route("/monitor/pending_gpu_tasks/", methods=['POST'])
@login_required
def pending_gpu_tasks_monitor(user, beans, form):
    global G_taskmgr
    logger.info("handle request: monitor/pending_gpu_tasks/")
    res = {}
    res['pending_tasks'] = G_taskmgr.get_pending_gpu_tasks_info()
    return json.dumps({'success':'true', 'monitor':res})

@app.route("/billing/beans/", methods=['POST'])
@auth_key_required
def billing_beans():
    form = request.form
    res = post_to_user("/billing/beans/",data=form)
    logger.info(res)
    return json.dumps(res)


@app.route("/system/parmList/", methods=['POST'])
@login_required
def parmList_system(user, beans, form):
    global G_sysmgr
    logger.info("handle request: system/parmList/")
    result = G_sysmgr.getParmList()
    return json.dumps(result)

@app.route("/system/modify/", methods=['POST'])
@login_required
def modify_system(user, beans, form):
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
def clear_system(user, beans, form):
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
def add_system(user, beans, form):
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
def delete_system(user, beans, form):
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
def resetall_system(user, beans, form):
    global G_sysmgr
    logger.info("handle request: system/reset_all/")
    field = form.get("field", None)
    [status, message] = G_sysmgr.reset_all(field)
    if status is True:
        return json.dumps({'success':'true', 'action':'reset_all'})
    else:
        return json.dumps({'success':'false', 'message': message})
    return json.dumps(result)

@app.route("/batch/job/add/", methods=['POST'])
@login_required
@beans_check
def add_job(user,beans,form):
    global G_jobmgr
    job_data = form.to_dict()
    job_info = {
        'tasks': {}
    }
    message = {
        'success': 'true',
        'message': 'add batch job success'
    }
    for key in job_data:
        if key == 'csrf_token':
            continue
        key_arr = key.split('_')
        value = job_data[key]
        if key_arr[0] == 'srcAddr' and value == '':
            #task_idx = 'task_' + key_arr[1]
            if task_idx in job_info['tasks']:
                job_info['tasks'][task_idx]['srcAddr'] = '/root'
            else:
                job_info['tasks'][task_idx] = {
                    'srcAddr': '/root'
                }
        elif key_arr[0] != 'dependency'and value == '':
            message['success'] = 'false'
            message['message'] = 'value of %s is null' % key
        elif len(key_arr) == 1:
            job_info[key_arr[0]] = value
        elif len(key_arr) == 2:
            key_prefix, task_idx = key_arr[0], key_arr[1]
            #task_idx = 'task_' + task_idx
            if task_idx in job_info["tasks"]:
                job_info["tasks"][task_idx][key_prefix] = value
            else:
                tmp_dict = {
                    key_prefix: value
                }
                job_info["tasks"][task_idx] = tmp_dict
        elif len(key_arr) == 3:
            key_prefix, task_idx, mapping_idx = key_arr[0], key_arr[1], key_arr[2]
            #task_idx = 'task_' + task_idx
            mapping_idx = 'mapping_' + mapping_idx
            if task_idx in job_info["tasks"]:
                if "mapping" in job_info["tasks"][task_idx]:
                    if mapping_idx in job_info["tasks"][task_idx]["mapping"]:
                        job_info["tasks"][task_idx]["mapping"][mapping_idx][key_prefix] = value
                    else:
                        tmp_dict = {
                            key_prefix: value
                        }
                        job_info["tasks"][task_idx]["mapping"][mapping_idx] = tmp_dict
                else:
                    job_info["tasks"][task_idx]["mapping"] = {
                        mapping_idx: {
                            key_prefix: value
                        }
                    }
            else:
                tmp_dict = {
                    "mapping":{
                        mapping_idx: {
                            key_prefix: value
                        }
                    }
                }
                job_info["tasks"][task_idx] = tmp_dict
    logger.debug('batch job adding info %s' % json.dumps(job_info, indent=4))
    [status, msg] = G_jobmgr.add_job(user, job_info)
    if status:
        return json.dumps(message)
    else:
        logger.debug('fail to add batch job: %s' % msg)
        message["success"] = "false"
        message["message"] = msg
        return json.dumps(message)
    return json.dumps(message)

@app.route("/batch/job/list/", methods=['POST'])
@login_required
def list_job(user,beans,form):
    global G_jobmgr
    result = {
        'success': 'true',
        'data': G_jobmgr.list_jobs(user)
    }
    return json.dumps(result)

@app.route("/batch/job/info/", methods=['POST'])
@login_required
def info_job(user,beans,form):
    global G_jobmgr
    jobid = form.get("jobid","")
    [success, data] = G_jobmgr.get_job(user, jobid)
    if success:
        return json.dumps({'success':'true', 'data':data})
    else:
        return json.dumps({'success':'false', 'message': data})

@app.route("/batch/job/stop/", methods=['POST'])
@login_required
def stop_job(user,beans,form):
    global G_jobmgr
    jobid = form.get("jobid","")
    [success,msg] = G_jobmgr.stop_job(user,jobid)
    if success:
        return json.dumps({'success':'true', 'action':'stop job'})
    else:
        return json.dumps({'success':'false', 'message': msg})

@app.route("/batch/job/output/", methods=['POST'])
@login_required
def get_output(user,beans,form):
    global G_jobmgr
    jobid = form.get("jobid","")
    taskid = form.get("taskid","")
    vnodeid = form.get("vnodeid","")
    issue = form.get("issue","")
    result = {
        'success': 'true',
        'data': G_jobmgr.get_output(user,jobid,taskid,vnodeid,issue)
    }
    return json.dumps(result)

@app.route("/batch/task/info/", methods=['POST'])
@login_required
def info_task(user,beans,form):
    pass

@app.route("/batch/vnodes/list/", methods=['POST'])
@login_required
def batch_vnodes_list(user,beans,form):
    global G_taskmgr
    result = {
        'success': 'true',
        'data': G_taskmgr.get_user_batch_containers(user)
    }
    return json.dumps(result)

# @app.route("/inside/cluster/scaleout/", methods=['POST'])
# @inside_ip_required
# def inside_cluster_scalout(cur_user, cluster_info, form):
#     global G_usermgr
#     global G_vclustermgr
#     clustername = cluster_info['name']
#     logger.info("handle request : scale out %s" % clustername)
#     image = {}
#     image['name'] = form.get("imagename", None)
#     image['type'] = form.get("imagetype", None)
#     image['owner'] = form.get("imageowner", None)
#     user_info = G_usermgr.selfQuery(cur_user = cur_user)
#     user = user_info['data']['username']
#     user_info = json.dumps(user_info)
#     setting = {
#             'cpu': form.get('cpuSetting'),
#             'memory': form.get('memorySetting'),
#             'disk': form.get('diskSetting')
#             }
#     [status, result] = G_usermgr.usageInc(cur_user = cur_user, modification = setting)
#     if not status:
#         return json.dumps({'success':'false', 'action':'scale out', 'message': result})
#     [status, result] = G_vclustermgr.scale_out_cluster(clustername, user, image, user_info, setting)
#     if status:
#         return json.dumps({'success':'true', 'action':'scale out', 'message':result})
#     else:
#         G_usermgr.usageRecover(cur_user = cur_user, modification = setting)
#         return json.dumps({'success':'false', 'action':'scale out', 'message':result})

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
    global G_notificationmgr
    global etcdclient
    global G_networkmgr
    global G_clustername
    global G_sysmgr
    global G_historymgr
    global G_applicationmgr
    global G_ulockmgr
    global G_cloudmgr
    global G_jobmgr
    global G_taskmgr
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

    # get public IP and set public Ip in etcd
    public_IP = env.getenv("PUBLIC_IP")
    etcdclient.setkey("machines/publicIP/"+ipaddr, public_IP)

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

    #init portcontrol
    portcontrol.init_new()
    G_ulockmgr = lockmgr.LockMgr()

    clusternet = env.getenv("CLUSTER_NET")
    logger.info("using CLUSTER_NET %s" % clusternet)

    G_sysmgr = sysmgr.SystemManager()

    G_networkmgr = network.NetworkMgr(clusternet, etcdclient, mode, ipaddr)
    G_networkmgr.printpools()

    G_cloudmgr = cloudmgr.CloudMgr()

    # start NodeMgr and NodeMgr will wait for all nodes to start ...
    G_nodemgr = nodemgr.NodeMgr(G_networkmgr, etcdclient, addr = ipaddr, mode=mode)
    logger.info("nodemgr started")
    distributedgw = env.getenv("DISTRIBUTED_GATEWAY")
    G_vclustermgr = vclustermgr.VclusterMgr(G_nodemgr, G_networkmgr, etcdclient, ipaddr, mode, distributedgw)
    logger.info("vclustermgr started")
    G_imagemgr = imagemgr.ImageMgr()
    logger.info("imagemgr started")

    G_releasemgr = releasemgr.ReleaseMgr(G_vclustermgr,G_ulockmgr)
    G_releasemgr.start()
    logger.info("releasemgr started")

    logger.info("startting to listen on: ")
    masterip = env.getenv('MASTER_IP')
    logger.info("using MASTER_IP %s", masterip)

    masterport = env.getenv('MASTER_PORT')
    logger.info("using MASTER_PORT %d", int(masterport))

    G_historymgr = History_Manager()
    master_collector = monitor.Master_Collector(G_nodemgr,ipaddr+":"+str(masterport))
    master_collector.start()
    logger.info("master_collector started")
    # server = http.server.HTTPServer((masterip, masterport), DockletHttpHandler)
    logger.info("starting master server")

    G_taskmgr = taskmgr.TaskMgr(G_nodemgr, monitor.Fetcher, ipaddr)
    G_jobmgr = jobmgr.JobMgr(G_taskmgr)
    G_taskmgr.set_jobmgr(G_jobmgr)
    G_taskmgr.start()

    app.run(host = masterip, port = masterport, threaded=True)
