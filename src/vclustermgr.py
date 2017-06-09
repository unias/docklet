#!/usr/bin/python3

import os, random, json, sys, imagemgr
import datetime
import xmlrpc.client

from log import logger
import env
import lxc
import proxytool
import requests
import traceback

userpoint = "http://" + env.getenv('USER_IP') + ":" + str(env.getenv('USER_PORT'))
def post_to_user(url = '/', data={}):
    return requests.post(userpoint+url,data=data).json()

##################################################
#                  VclusterMgr
# Description : VclusterMgr start/stop/manage virtual clusters
#
##################################################

class VclusterMgr(object):
    def __init__(self, nodemgr, networkmgr, etcdclient, addr, mode, distributedgw='False'):
        self.mode = mode
        self.distributedgw = distributedgw
        self.nodemgr = nodemgr
        self.imgmgr = imagemgr.ImageMgr()
        self.networkmgr = networkmgr
        self.addr = addr
        self.etcd = etcdclient
        self.defaultsize = env.getenv("CLUSTER_SIZE")
        self.fspath = env.getenv("FS_PREFIX")

        logger.info ("vcluster start on %s" % (self.addr))
        if self.mode == 'new':
            logger.info ("starting in new mode on %s" % (self.addr))
            # check if all clusters data are deleted in httprest.py
            clean = True
            usersdir = self.fspath+"/global/users/"
            for user in os.listdir(usersdir):
                if len(os.listdir(usersdir+user+"/clusters")) > 0 or len(os.listdir(usersdir+user+"/hosts")) > 0:
                    clean = False
            if not clean:
                logger.error ("clusters files not clean, start failed")
                sys.exit(1)
        elif self.mode == "recovery":
            logger.info ("starting in recovery mode on %s" % (self.addr))
            self.recover_allclusters()
        else:
            logger.error ("not supported mode:%s" % self.mode)
            sys.exit(1)

    def recover_allclusters(self):
        logger.info("recovering all vclusters for all users...")
        usersdir = self.fspath+"/global/users/"
        auth_key = env.getenv('AUTH_KEY')
        for user in os.listdir(usersdir):
            for cluster in self.list_clusters(user)[1]:
                logger.info ("recovering cluster:%s for user:%s ..." % (cluster, user))
                res = post_to_user('/user/uid/',{'username':user,'auth_key':auth_key})
                self.recover_cluster(cluster, user, res['uid'])
        logger.info("recovered all vclusters for all users")

    def mount_allclusters(self):
        logger.info("mounting all vclusters for all users...")
        usersdir = self.fspath+"/global/users/"
        for user in os.listdir(usersdir):
            for cluster in self.list_clusters(user)[1]:
                logger.info ("mounting cluster:%s for user:%s ..." % (cluster, user))
                self.mount_cluster(cluster, user)
        logger.info("mounted all vclusters for all users")

    def stop_allclusters(self):
        logger.info("stopping all vclusters for all users...")
        usersdir = self.fspath+"/global/users/"
        for user in os.listdir(usersdir):
            for cluster in self.list_clusters(user)[1]:
                logger.info ("stopping cluster:%s for user:%s ..." % (cluster, user))
                self.stop_cluster(cluster, user)
        logger.info("stopped all vclusters for all users")

    def detach_allclusters(self):
        logger.info("detaching all vclusters for all users...")
        usersdir = self.fspath+"/global/users/"
        for user in os.listdir(usersdir):
            for cluster in self.list_clusters(user)[1]:
                logger.info ("detaching cluster:%s for user:%s ..." % (cluster, user))
                self.detach_cluster(cluster, user)
        logger.info("detached all vclusters for all users")

    def create_cluster(self, clustername, username, image, user_info, setting):
        if self.is_cluster(clustername, username):
            return [False, "cluster:%s already exists" % clustername]
        clustersize = int(self.defaultsize)
        logger.info ("starting cluster %s with %d containers for %s" % (clustername, int(clustersize), username))
        workers = self.nodemgr.get_nodeips()
        image_json = json.dumps(image)
        groupname = json.loads(user_info)["data"]["group"]
        uid = json.loads(user_info)["data"]["id"]
        if (len(workers) == 0):
            logger.warning ("no workers to start containers, start cluster failed")
            return [False, "no workers are running"]
        # check user IP pool status, should be moved to user init later
        if not self.networkmgr.has_user(username):
            self.networkmgr.add_user(username, cidr=29, isshared = True if str(groupname) == "fundation" else False)
            if self.distributedgw == "False":
                [success,message] = self.networkmgr.setup_usrgw(username, uid, self.nodemgr)
                if not success:
                    return [False, message]
        elif not self.networkmgr.has_usrgw(username):
            self.networkmgr.usrgws[username] = self.networkmgr.masterip
            self.networkmgr.dump_usrgw(username)
        # [status, result] = self.networkmgr.acquire_userips_cidr(username, clustersize)
        gateway = self.networkmgr.get_usergw(username)
        #vlanid = self.networkmgr.get_uservlanid(username)
        logger.info ("create cluster with gateway : %s" % gateway)
        self.networkmgr.printpools()
        # if not status:
        #     logger.info ("create cluster failed: %s" % result)
        #     return [False, result]
        # ips = result
        clusterid = self._acquire_id()
        clusterpath = self.fspath+"/global/users/"+username+"/clusters/"+clustername
        hostpath = self.fspath+"/global/users/"+username+"/hosts/"+str(clusterid)+".hosts"
        hosts = "127.0.0.1\tlocalhost\n"
        proxy_server_ip = ""
        proxy_public_ip = ""
        containers = []
        for i in range(0, clustersize):
            workerip = workers[random.randint(0, len(workers)-1)]
            oneworker = xmlrpc.client.ServerProxy("http://%s:%s" % (workerip, env.getenv("WORKER_PORT")))
            if self.distributedgw == "True" and i == 0 and not self.networkmgr.has_usrgw(username):
                [success,message] = self.networkmgr.setup_usrgw(username, uid, self.nodemgr, workerip)
                if not success:
                    return [False, message]
            if i == 0:
                self.networkmgr.load_usrgw(username)
                proxy_server_ip = self.networkmgr.usrgws[username]
                [status, proxy_public_ip] = self.etcd.getkey("machines/publicIP/"+proxy_server_ip)
                if not status:
                    logger.error("Fail to get proxy_public_ip %s."%(proxy_server_ip))
                    return [False, "Fail to get proxy server public IP."]
            lxc_name = username + "-" + str(clusterid) + "-" + str(i)
            hostname = "host-"+str(i)
            logger.info ("create container with : name-%s, username-%s, clustername-%s, clusterid-%s, hostname-%s, gateway-%s, image-%s" % (lxc_name, username, clustername, str(clusterid), hostname, gateway, image_json))
            [success,message] = oneworker.create_container(lxc_name, proxy_public_ip, username, uid, json.dumps(setting) , clustername, str(clusterid), str(i), hostname, gateway, image_json)
            if success is False:
                logger.info("container create failed, so vcluster create failed")
                return [False, message]
            logger.info("container create success")
            # hosts = hosts + ips[i].split("/")[0] + "\t" + hostname + "\t" + hostname + "."+clustername + "\n"
            containers.append({ 'containername':lxc_name, 'hostname':hostname, 'host':workerip, 'image':image['name'], 'lastsave':datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'setting': setting })
        hostfile = open(hostpath, 'w')
        hostfile.write(hosts)
        hostfile.close()
        clusterfile = open(clusterpath, 'w')
        proxy_url = env.getenv("PORTAL_URL") +"/"+ proxy_public_ip +"/_web/" + username + "/" + clustername
        info = {'clusterid':clusterid, 'status':'stopped', 'size':clustersize, 'containers':containers, 'nextcid': clustersize, 'create_time':datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'start_time':"------"}
        info['proxy_url'] = proxy_url
        info['proxy_server_ip'] = proxy_server_ip
        info['proxy_public_ip'] = proxy_public_ip
        clusterfile.write(json.dumps(info))
        clusterfile.close()
        return [True, info]

    def scale_out_cluster(self,clustername,username, image,user_info, setting):
        if not self.is_cluster(clustername,username):
            return [False, "cluster:%s not found" % clustername]
        workers = self.nodemgr.get_nodeips()
        if (len(workers) == 0):
            logger.warning("no workers to start containers, scale out failed")
            return [False, "no workers are running"]
        image_json = json.dumps(image)
        [status, result] = self.networkmgr.acquire_userips_cidr(username)
        gateway = self.networkmgr.get_usergw(username)
        #vlanid = self.networkmgr.get_uservlanid(username)
        self.networkmgr.printpools()
        if not status:
            return [False, result]
        ip = result[0]
        [status, clusterinfo] = self.get_clusterinfo(clustername,username)
        clusterid = clusterinfo['clusterid']
        clusterpath = self.fspath + "/global/users/" + username + "/clusters/" + clustername
        hostpath = self.fspath + "/global/users/" + username + "/hosts/" + str(clusterid) + ".hosts"
        cid = clusterinfo['nextcid']
        workerip = workers[random.randint(0, len(workers)-1)]
        oneworker = xmlrpc.client.ServerProxy("http://%s:%s" % (workerip, env.getenv("WORKER_PORT")))
        lxc_name = username + "-" + str(clusterid) + "-" + str(cid)
        hostname = "host-" + str(cid)
        proxy_server_ip = clusterinfo['proxy_server_ip']
        proxy_public_ip = clusterinfo['proxy_public_ip']
        uid = json.loads(user_info)["data"]["id"]
        [success, message] = oneworker.create_container(lxc_name, proxy_public_ip, username, uid, json.dumps(setting), clustername, clusterid, str(cid), hostname, ip, gateway, image_json)
        if success is False:
            logger.info("create container failed, so scale out failed")
            return [False, message]
        if clusterinfo['status'] == "running":
            self.networkmgr.check_usergre(username, uid, workerip, self.nodemgr, self.distributedgw=='True')
            oneworker.start_container(lxc_name)
            oneworker.start_services(lxc_name, ["ssh"]) # TODO: need fix
            namesplit = lxc_name.split('-')
            portname = namesplit[1] + '-' + namesplit[2]
            oneworker.recover_usernet(portname, uid, proxy_server_ip, workerip==proxy_server_ip)
        logger.info("scale out success")
        hostfile = open(hostpath, 'a')
        hostfile.write(ip.split("/")[0] + "\t" + hostname + "\t" + hostname + "." + clustername + "\n")
        hostfile.close()
        clusterinfo['nextcid'] = int(clusterinfo['nextcid']) + 1
        clusterinfo['size'] = int(clusterinfo['size']) + 1
        clusterinfo['containers'].append({'containername':lxc_name, 'hostname':hostname, 'ip':ip, 'host':workerip, 'image':image['name'], 'lastsave':datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'setting': setting})
        clusterfile = open(clusterpath, 'w')
        clusterfile.write(json.dumps(clusterinfo))
        clusterfile.close()
        return [True, clusterinfo]

    def addproxy(self,username,clustername,ip,port):
        [status, clusterinfo] = self.get_clusterinfo(clustername, username)
        if 'proxy_ip' in clusterinfo:
            return [False, "proxy already exists"]
        target = "http://" + ip + ":" + port + "/"
        clusterinfo['proxy_ip'] = ip + ":" + port
        if self.distributedgw == 'True':
            worker = self.nodemgr.ip_to_rpc(clusterinfo['proxy_server_ip'])
            worker.set_route("/"+ clusterinfo['proxy_public_ip'] + "/_web/" + username + "/" + clustername, target)
        else:
            proxytool.set_route("/" + clusterinfo['proxy_public_ip'] + "/_web/" + username + "/" + clustername, target)
        clusterfile = open(self.fspath + "/global/users/" + username + "/clusters/" + clustername, 'w')
        clusterfile.write(json.dumps(clusterinfo))
        clusterfile.close()
        return [True, clusterinfo]

    def deleteproxy(self, username, clustername):
        [status, clusterinfo] = self.get_clusterinfo(clustername, username)
        if 'proxy_ip' not in clusterinfo:
            return [True, clusterinfo]
        clusterinfo.pop('proxy_ip')
        if self.distributedgw == 'True':
            worker = self.nodemgr.ip_to_rpc(clusterinfo['proxy_server_ip'])
            worker.delete_route("/" + clusterinfo['proxy_public_ip'] + "/_web/" + username + "/" + clustername)
        else:
            proxytool.delete_route("/" + clusterinfo['proxy_public_ip'] + "/_web/" + username + "/" + clustername)
        clusterfile = open(self.fspath + "/global/users/" + username + "/clusters/" + clustername, 'w')
        clusterfile.write(json.dumps(clusterinfo))
        clusterfile.close()
        return [True, clusterinfo]

    def flush_cluster(self,username,clustername,containername):
        begintime = datetime.datetime.now()
        [status, info] = self.get_clusterinfo(clustername, username)
        if not status:
            return [False, "cluster not found"]
        containers = info['containers']
        imagetmp = username + "_tmp_docklet"
        for container in containers:
            if container['containername'] == containername:
                logger.info("container: %s found" % containername)
                worker = xmlrpc.client.ServerProxy("http://%s:%s" % (container['host'], env.getenv("WORKER_PORT")))
                worker.create_image(username,imagetmp,containername)
                fimage = container['image']
                logger.info("image: %s created" % imagetmp)
                break
        else:
            logger.error("container: %s not found" % containername)
        for container in containers:
            if container['containername'] != containername:
                logger.info("container: %s now flush" % container['containername'])
                worker = xmlrpc.client.ServerProxy("http://%s:%s" % (container['host'], env.getenv("WORKER_PORT")))
                #t = threading.Thread(target=onework.flush_container,args=(username,imagetmp,container['containername']))
                #threads.append(t)
                worker.flush_container(username,imagetmp,container['containername'])
                container['lastsave'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                container['image'] = fimage
                logger.info("thread for container: %s has been prepared" % container['containername'])
        clusterpath = self.fspath + "/global/users/" + username + "/clusters/" + clustername
        infofile = open(clusterpath,'w')
        infofile.write(json.dumps(info))
        infofile.close()
        self.imgmgr.removeImage(username,imagetmp)
        endtime = datetime.datetime.now()
        dtime = (endtime - begintime).seconds
        logger.info("flush spend %s seconds" % dtime)
        logger.info("flush success")


    def image_check(self,username,imagename):
        imagepath = self.fspath + "/global/images/private/" + username + "/"
        if os.path.exists(imagepath + imagename):
            return [False, "image already exists"]
        else:
            return [True, "image not exists"]

    def create_image(self,username,clustername,containername,imagename,description,imagenum=10):
        [status, info] = self.get_clusterinfo(clustername,username)
        if not status:
            return [False, "cluster not found"]
        containers = info['containers']
        for container in containers:
            if container['containername'] == containername:
                logger.info("container: %s found" % containername)
                worker = xmlrpc.client.ServerProxy("http://%s:%s" % (container['host'], env.getenv("WORKER_PORT")))
                if worker is None:
                    return [False, "The worker can't be found or has been stopped."]
                res = worker.create_image(username,imagename,containername,description,imagenum)
                container['lastsave'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                container['image'] = imagename
                break
        else:
            res = [False, "container not found"]
            logger.error("container: %s not found" % containername)
        clusterpath = self.fspath + "/global/users/" + username + "/clusters/" + clustername
        infofile = open(clusterpath, 'w')
        infofile.write(json.dumps(info))
        infofile.close()
        return res

    def delete_cluster(self, clustername, username, user_info):
        [status, info] = self.get_clusterinfo(clustername, username)
        if not status:
            return [False, "cluster not found"]
        if info['status']=='running':
            return [False, "cluster is still running, you need to stop it and then delete"]
        ips = []
        for container in info['containers']:
            worker = xmlrpc.client.ServerProxy("http://%s:%s" % (container['host'], env.getenv("WORKER_PORT")))
            if worker is None:
                return [False, "The worker can't be found or has been stopped."]
            worker.delete_container(container['containername'])
            ips.append(container['ip'])
        logger.info("delete vcluster and release vcluster ips")
        self.networkmgr.release_userips(username, ips)
        self.networkmgr.printpools()
        os.remove(self.fspath+"/global/users/"+username+"/clusters/"+clustername)
        os.remove(self.fspath+"/global/users/"+username+"/hosts/"+str(info['clusterid'])+".hosts")

        groupname = json.loads(user_info)["data"]["group"]
        uid = json.loads(user_info)["data"]["id"]
        [status, clusters] = self.list_clusters(username)
        if len(clusters) == 0:
            self.networkmgr.del_user(username)
            self.networkmgr.del_usrgwbr(username, uid, self.nodemgr)
            #logger.info("vlanid release triggered")

        return [True, "cluster delete"]

    def scale_in_cluster(self, clustername, username, containername):
        [status, info] = self.get_clusterinfo(clustername, username)
        if not status:
            return [False, "cluster not found"]
        new_containers = []
        for container in info['containers']:
            if container['containername'] == containername:
                worker = xmlrpc.client.ServerProxy("http://%s:%s" % (container['host'], env.getenv("WORKER_PORT")))
                if worker is None:
                    return [False, "The worker can't be found or has been stopped."]
                worker.delete_container(containername)
                self.networkmgr.release_userips(username, container['ip'])
                self.networkmgr.printpools()
            else:
                new_containers.append(container)
        info['containers'] = new_containers
        info['size'] -= 1
        cid = containername[containername.rindex("-")+1:]
        clusterid = info['clusterid']
        clusterpath = self.fspath + "/global/users/" + username + "/clusters/" + clustername
        hostpath = self.fspath + "/global/users/" + username + "/hosts/" + str(clusterid) + ".hosts"
        clusterfile = open(clusterpath, 'w')
        clusterfile.write(json.dumps(info))
        clusterfile.close()
        hostfile = open(hostpath, 'r')
        hostinfo = hostfile.readlines()
        hostfile.close()
        hostfile = open(hostpath, 'w')
        new_hostinfo = []
        new_hostinfo.append(hostinfo[0])
        for host in hostinfo[1:]:
            parts = host.split("\t")
            if parts[1][parts[1].rindex("-")+1:] == cid:
                pass
            else:
                new_hostinfo.append(host)
        hostfile.writelines(new_hostinfo)
        hostfile.close()
        return [True, info]

    def get_clustersetting(self, clustername, username, containername, allcontainer):
        clusterpath = self.fspath + "/global/users/" + username + "/clusters/" + clustername
        if not os.path.isfile(clusterpath):
            logger.error("cluster file: %s not found" % clustername)
            return [False, "cluster file not found"]
        infofile = open(clusterpath, 'r')
        info = json.loads(infofile.read())
        infofile.close()
        cpu = 0
        memory = 0
        disk = 0
        if allcontainer:
            for container in info['containers']:
                if 'setting' in container:
                    cpu += int(container['setting']['cpu'])
                    memory += int(container['setting']['memory'])
                    disk += int(container['setting']['disk'])
        else:
            for container in info['containers']:
                if container['containername'] == containername:
                    if 'setting' in container:
                        cpu += int(container['setting']['cpu'])
                        memory += int(container['setting']['memory'])
                        disk += int(container['setting']['disk'])
        return [True, {'cpu':cpu, 'memory':memory, 'disk':disk}]

    def update_cluster_baseurl(self, clustername, username, oldip, newip):
        [status, info] = self.get_clusterinfo(clustername, username)
        if not status:
            return [False, "cluster not found"]
        logger.info("%s %s:base_url need to be modified(%s %s)."%(username,clustername,oldip,newip))
        for container in info['containers']:
            worker = xmlrpc.client.ServerProxy("http://%s:%s" % (container['host'], env.getenv("WORKER_PORT")))
            if worker is None:
                return [False, "The worker can't be found or has been stopped."]
            worker.update_baseurl(container['containername'],oldip,newip)
            worker.stop_container(container['containername'])

    def check_public_ip(self, clustername, username):
        [status, info] = self.get_clusterinfo(clustername, username)
        [status, proxy_public_ip] = self.etcd.getkey("machines/publicIP/"+info['proxy_server_ip'])
        if not info['proxy_public_ip'] == proxy_public_ip:
            logger.info("%s %s proxy_public_ip has been changed, base_url need to be modified."%(username,clustername))
            oldpublicIP= info['proxy_public_ip']
            self.update_proxy_ipAndurl(clustername,username,info['proxy_server_ip'])
            self.update_cluster_baseurl(clustername,username,oldpublicIP,proxy_public_ip)
            return False
        else:
            return True

    def start_cluster(self, clustername, username, uid):
        [status, info] = self.get_clusterinfo(clustername, username)
        if not status:
            return [False, "cluster not found"]
        if info['status'] == 'running':
            return [False, "cluster is already running"]
        # set proxy
        if not "proxy_server_ip" in info.keys():
            info['proxy_server_ip'] = self.addr
        '''try:
            target = 'http://'+info['containers'][0]['ip'].split('/')[0]+":10000"
            if self.distributedgw == 'True':
                worker = self.nodemgr.ip_to_rpc(info['proxy_server_ip'])
                # check public ip
                if not self.check_public_ip(clustername,username):
                    [status, info] = self.get_clusterinfo(clustername, username)
                worker.set_route("/" + info['proxy_public_ip'] + '/go/'+username+'/'+clustername, target)
            else:
                if not info['proxy_server_ip'] == self.addr:
                    logger.info("%s %s proxy_server_ip has been changed, base_url need to be modified."%(username,clustername))
                    oldpublicIP= info['proxy_public_ip']
                    self.update_proxy_ipAndurl(clustername,username,self.addr)
                    [status, info] = self.get_clusterinfo(clustername, username)
                    self.update_cluster_baseurl(clustername,username,oldpublicIP,info['proxy_public_ip'])
                # check public ip
                if not self.check_public_ip(clustername,username):
                    [status, info] = self.get_clusterinfo(clustername, username)
                proxytool.set_route("/" + info['proxy_public_ip'] + '/go/'+username+'/'+clustername, target)
        except:
            logger.info(traceback.format_exc())
            return [False, "start cluster failed with setting proxy failed"]'''
        # check gateway for user
        # after reboot, user gateway goes down and lose its configuration
        # so, check is necessary
        self.networkmgr.check_usergw(username, uid, self.nodemgr,self.distributedgw=='True')
        # start containers
        for container in info['containers']:
            # set up gre from user's gateway host to container's host.`
            self.networkmgr.check_usergre(username, uid, container['host'], self.nodemgr, self.distributedgw=='True')
            worker = xmlrpc.client.ServerProxy("http://%s:%s" % (container['host'], env.getenv("WORKER_PORT")))
            if worker is None:
                return [False, "The worker can't be found or has been stopped."]
            worker.start_container(container['containername'])

            logger.info("acquire ip for container %s" % container['containername'])
            [status, result] = self.networkmgr.acquire_userips_cidr(username)
            gateway = self.networkmgr.get_usergw(username)
            if not status:
                return [False, result]
            ip = result[0]
            container['ip'] = ip
            logger.info("acruire ip for container %s success with ip %s" % (container['containername'], ip))

            # pid = self.get_pid(container['containername']
            [status, result] = worker.update_container(container['containername'], clustername, info['clusterid'], container['hostname'], ip)
            if not status:
                logger.info("update container %s failed: %s" % (container['containername'], result))
                return [False, result]
            pid = result

            logger.info("update user %s network" % username)
            [status, result] = worker.update_user_network(username, pid, ip, gateway)
            if not status:
                logger.info("update user % s network failed: %s" % (username, result))
                return [False, result]
            logger.info("update user %s network with pid %s, ip %s, gateway %s success" % (username, pid, ip,gateway))

            # worker.start_services(container['containername'])
            namesplit = container['containername'].split('-')
            portname = namesplit[1] + '-' + namesplit[2]
            worker.recover_usernet(portname, uid, info['proxy_server_ip'], container['host']==info['proxy_server_ip'])
        info['status']='running'
        info['start_time']=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.write_clusterinfo(info,clustername,username)
        
        [status, info] = self.get_clusterinfo(clustername, username)
        try:
            target = 'http://'+info['containers'][0]['ip'].split('/')[0]+":10000"
            if self.distributedgw == 'True':
                worker = self.nodemgr.ip_to_rpc(info['proxy_server_ip'])
                # check public ip
                if not self.check_public_ip(clustername,username):
                    [status, info] = self.get_clusterinfo(clustername, username)
                worker.set_route("/" + info['proxy_public_ip'] + '/go/'+username+'/'+clustername, target)
            else:
                if not info['proxy_server_ip'] == self.addr:
                    logger.info("%s %s proxy_server_ip has been changed, base_url need to be modified."%(username,clustername))
                    oldpublicIP= info['proxy_public_ip']
                    self.update_proxy_ipAndurl(clustername,username,self.addr)
                    [status, info] = self.get_clusterinfo(clustername, username)
                    self.update_cluster_baseurl(clustername,username,oldpublicIP,info['proxy_public_ip'])
                # check public ip
                if not self.check_public_ip(clustername,username):
                    [status, info] = self.get_clusterinfo(clustername, username)
                
                logger.info("set configurable_http_proxy with proxy_public_ip %s, username %s, clustername %s , target %s" % (info['proxy_public_ip'], username, clustername, target))
                proxytool.set_route("/" + info['proxy_public_ip'] + '/go/'+username+'/'+clustername, target)
        except:
            logger.info(traceback.format_exc())
            return [False, "start cluster failed with setting proxy failed"]
        return [True, "start cluster"]

    def mount_cluster(self, clustername, username):
        [status, info] = self.get_clusterinfo(clustername, username)
        if not status:
            return [False, "cluster not found"]
        for container in info['containers']:
            worker = xmlrpc.client.ServerProxy("http://%s:%s" % (container['host'], env.getenv("WORKER_PORT")))
            if worker is None:
                return [False, "The worker can't be found or has been stopped."]
            worker.mount_container(container['containername'])
        return [True, "mount cluster"]

    def recover_cluster(self, clustername, username, uid):
        [status, info] = self.get_clusterinfo(clustername, username)
        if not status:
            return [False, "cluster not found"]
        if not "proxy_server_ip" in info.keys():
            info['proxy_server_ip'] = self.addr
            self.write_clusterinfo(info,clustername,username)
            [status, info] = self.get_clusterinfo(clustername, username)
        if not "proxy_public_ip" in info.keys():
            self.update_proxy_ipAndurl(clustername,username,info['proxy_server_ip'])
            [status, info] = self.get_clusterinfo(clustername, username)
            self.update_cluster_baseurl(clustername,username,info['proxy_server_ip'],info['proxy_public_ip'])
        if info['status'] == 'stopped':
            return [True, "cluster no need to start"]
        # recover proxy of cluster
        try:
            target = 'http://'+info['containers'][0]['ip'].split('/')[0]+":10000"
            if self.distributedgw == 'True':
                worker = self.nodemgr.ip_to_rpc(info['proxy_server_ip'])
                # check public ip
                if not self.check_public_ip(clustername,username):
                    [status, info] = self.get_clusterinfo(clustername, username)
                worker.set_route("/" + info['proxy_public_ip'] + '/go/'+username+'/'+clustername, target)
            else:
                if not info['proxy_server_ip'] == self.addr:
                    logger.info("%s %s proxy_server_ip has been changed, base_url need to be modified."%(username,clustername))
                    oldpublicIP= info['proxy_public_ip']
                    self.update_proxy_ipAndurl(clustername,username,self.addr)
                    [status, info] = self.get_clusterinfo(clustername, username)
                    self.update_cluster_baseurl(clustername,username,oldpublicIP,info['proxy_public_ip'])
                # check public ip
                if not self.check_public_ip(clustername,username):
                    [status, info] = self.get_clusterinfo(clustername, username)
                proxytool.set_route("/" + info['proxy_public_ip'] + '/go/'+username+'/'+clustername, target)
        except:
            return [False, "start cluster failed with setting proxy failed"]
        # need to check and recover gateway of this user
        self.networkmgr.check_usergw(username, uid, self.nodemgr,self.distributedgw=='True')
        # recover containers of this cluster
        for container in info['containers']:
            # set up gre from user's gateway host to container's host.
            self.networkmgr.check_usergre(username, uid, container['host'], self.nodemgr, self.distributedgw=='True')
            worker = xmlrpc.client.ServerProxy("http://%s:%s" % (container['host'], env.getenv("WORKER_PORT")))
            if worker is None:
                return [False, "The worker can't be found or has been stopped."]
            worker.recover_container(container['containername'])
            namesplit = container['containername'].split('-')
            portname = namesplit[1] + '-' + namesplit[2]
            worker.recover_usernet(portname, uid, info['proxy_server_ip'], container['host']==info['proxy_server_ip'])
        return [True, "start cluster"]

    # maybe here should use cluster id
    def stop_cluster(self, clustername, username):
        [status, info] = self.get_clusterinfo(clustername, username)
        if not status:
            return [False, "cluster not found"]
        if info['status'] == 'stopped':
            return [False, 'cluster is already stopped']
        if self.distributedgw == 'True':
            worker = self.nodemgr.ip_to_rpc(info['proxy_server_ip'])
            worker.delete_route("/" + info['proxy_public_ip'] + '/go/'+username+'/'+clustername)
        else:
            proxytool.delete_route("/" + info['proxy_public_ip'] + '/go/'+username+'/'+clustername)
        for container in info['containers']:
            worker = xmlrpc.client.ServerProxy("http://%s:%s" % (container['host'], env.getenv("WORKER_PORT")))
            if worker is None:
                return [False, "The worker can't be found or has been stopped."]
            pid = self.get_pid(container['containername'])
            worker.stop_container(container['containername'])
        info['status']='stopped'
        info['start_time']="------"
        infofile = open(self.fspath+"/global/users/"+username+"/clusters/"+clustername, 'w')
        infofile.write(json.dumps(info))
        infofile.close()
        return [True, "stop cluster"]

    def detach_cluster(self, clustername, username):
        [status, info] = self.get_clusterinfo(clustername, username)
        if not status:
            return [False, "cluster not found"]
        if info['status'] == 'running':
            return [False, 'cluster is running, please stop it first']
        for container in info['containers']:
            worker = xmlrpc.client.ServerProxy("http://%s:%s" % (container['host'], env.getenv("WORKER_PORT")))
            if worker is None:
                return [False, "The worker can't be found or has been stopped."]
            worker.detach_container(container['containername'])
        return [True, "detach cluster"]

    def list_clusters(self, user):
        if not os.path.exists(self.fspath+"/global/users/"+user+"/clusters"):
            return [True, []]
        clusters = os.listdir(self.fspath+"/global/users/"+user+"/clusters")
        full_clusters = []
        for cluster in clusters:
            single_cluster = {}
            single_cluster['name'] = cluster
            [status, info] = self.get_clusterinfo(cluster,user)
            if info['status'] == 'running':
                single_cluster['status'] = 'running'
            else:
                single_cluster['status'] = 'stopping'
            full_clusters.append(single_cluster)
        return [True, clusters]

    def is_cluster(self, clustername, username):
        [status, clusters] = self.list_clusters(username)
        if clustername in clusters:
            return True
        else:
            return False

    # get id from name
    def get_clusterid(self, clustername, username):
        [status, info] = self.get_clusterinfo(clustername, username)
        if not status:
            return -1
        if 'clusterid' in info:
            return int(info['clusterid'])
        logger.error ("internal error: cluster:%s info file has no clusterid " % clustername)
        return -1

    def update_proxy_ipAndurl(self, clustername, username, proxy_server_ip):
        [status, info] = self.get_clusterinfo(clustername, username)
        if not status:
            return [False, "cluster not found"]
        info['proxy_server_ip'] = proxy_server_ip
        [status, proxy_public_ip] = self.etcd.getkey("machines/publicIP/"+proxy_server_ip)
        if not status:
            logger.error("Fail to get proxy_public_ip %s."%(proxy_server_ip))
            proxy_public_ip = proxy_server_ip
        info['proxy_public_ip'] = proxy_public_ip
        proxy_url = env.getenv("PORTAL_URL") +"/"+ proxy_public_ip +"/_web/" + username + "/" + clustername
        info['proxy_url'] = proxy_url
        self.write_clusterinfo(info,clustername,username)
        return proxy_public_ip

    def get_clusterinfo(self, clustername, username):
        clusterpath = self.fspath + "/global/users/" + username + "/clusters/" + clustername
        if not os.path.isfile(clusterpath):
            return [False, "cluster not found"]
        infofile = open(clusterpath, 'r')
        info = json.loads(infofile.read())
        return [True, info]

    def write_clusterinfo(self, info, clustername, username):
        clusterpath = self.fspath + "/global/users/" + username + "/clusters/" + clustername
        if not os.path.isfile(clusterpath):
            return [False, "cluster not found"]
        infofile = open(clusterpath, 'w')
        infofile.write(json.dumps(info))
        infofile.close()
        return [True, info]

    # acquire cluster id from etcd
    def _acquire_id(self):
        clusterid = self.etcd.getkey("vcluster/nextid")[1]
        self.etcd.setkey("vcluster/nextid", str(int(clusterid)+1))
        return int(clusterid)

    def get_pid(self, lxc_name):
        c = lxc.Container(lxc_name)
        pid = c.init_pid
        return pid

