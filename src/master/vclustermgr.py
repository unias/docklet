#!/usr/bin/python3

import os, random, json, sys
import datetime, math, time

from utils.log import logger
from utils import env, imagemgr, proxytool
import requests, threading, traceback
from utils.nettools import portcontrol
from utils.model import db, Container, PortMapping, VCluster
from queue import Queue

userpoint = "http://" + env.getenv('USER_IP') + ":" + str(env.getenv('USER_PORT'))
def post_to_user(url = '/', data={}):
    return requests.post(userpoint+url,data=data).json()

##################################################
#                  VclusterMgr
# Description : VclusterMgr start/stop/manage virtual clusters
#
##################################################

def db_commit():
    try:
        db.session.commit()
    except Exception as err:
        db.session.rollback()
        logger.error(traceback.format_exc())
        return False
    return True

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
        self.clusterid_locks = threading.Lock()

        # check database
        try:
            Container.query.all()
            PortMapping.query.all()
            VCluster.query.all()
        except:
            # create database
            db.create_all()

        logger.info ("vcluster start on %s" % (self.addr))
        if self.mode == 'new':
            logger.info ("starting in new mode on %s" % (self.addr))
            # check if all clusters data are deleted in httprest.py
            clean = True
            usersdir = self.fspath+"/global/users/"
            vclusters = VCluster.query.all()
            if len(vclusters) != 0:
                clean = False
            for user in os.listdir(usersdir):
                if len(os.listdir(usersdir+user+"/hosts")) > 0:
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
        # start a thread to watch recovering node to recover clusters
        threading.Thread(target = self._watchrecovering, args=()).start()

    def _watchrecovering(self):
        logger.info("watching recovering node to recover clusters...")
        while True:
            node = self.nodemgr.recover_queue.get()
            self.recover_cluster_on(node)
            self.nodemgr.recover_queue.task_done()
    
    def recover_allclusters(self):
        logger.info("try to recover all clusters for all users...")
        vcs = VCluster.query.filter(VCluster.status.in_(["running","error"])).all()
        need_recovers = []
        for vc in vcs:
            need_recovers.append([vc.clustername, vc.ownername])
        self.recover_clusters(need_recovers)        

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
        if self.imgmgr.get_image_size(image) + 100 > int(setting["disk"]):
            return [False, "the size of disk is not big enough for the image"]
        clustersize = int(self.defaultsize)
        logger.info ("starting cluster %s with %d containers for %s" % (clustername, int(clustersize), username))
        workers = self.nodemgr.get_base_nodeips()
        image_json = json.dumps(image)
        groupname = json.loads(user_info)["data"]["group"]
        groupquota = json.loads(user_info)["data"]["groupinfo"]
        uid = json.loads(user_info)["data"]["id"]
        if (len(workers) == 0):
            logger.warning ("no workers to start containers, start cluster failed")
            return [False, "no workers are running"]
        # check user IP pool status, should be moved to user init later
        if not self.networkmgr.has_user(username):
            ipnum = int(groupquota["vnode"]) + 3
            cidr = 32 - math.ceil(math.log(ipnum,2))
            self.networkmgr.add_user(username, cidr=cidr, isshared = True if str(groupname) == "fundation" else False)
            if self.distributedgw == "False":
                [success,message] = self.networkmgr.setup_usrgw(groupquota['input_rate_limit'], groupquota['output_rate_limit'], username, uid, self.nodemgr)
                if not success:
                    return [False, message]
        elif not self.networkmgr.has_usrgw(username):
            self.networkmgr.usrgws[username] = self.networkmgr.masterip
            self.networkmgr.dump_usrgw(username)
        [status, result] = self.networkmgr.acquire_userips_cidr(username, clustersize)
        gateway = self.networkmgr.get_usergw(username)
        #vlanid = self.networkmgr.get_uservlanid(username)
        logger.info ("create cluster with gateway : %s" % gateway)
        self.networkmgr.printpools()
        if not status:
            logger.info ("create cluster failed: %s" % result)
            return [False, result]
        ips = result
        clusterid = self._acquire_id()
        clusterpath = self.fspath+"/global/users/"+username+"/clusters/"+clustername
        hostpath = self.fspath+"/global/users/"+username+"/hosts/"+str(clusterid)+".hosts"
        hosts = "127.0.0.1\tlocalhost\n"
        proxy_server_ip = ""
        proxy_public_ip = ""
        containers = []
        for i in range(0, clustersize):
            workerip = workers[random.randint(0, len(workers)-1)]
            oneworker = self.nodemgr.ip_to_rpc(workerip)
            if self.distributedgw == "True" and i == 0 and not self.networkmgr.has_usrgw(username):
                [success,message] = self.networkmgr.setup_usrgw(groupquota['input_rate_limit'], groupquota['output_rate_limit'], username, uid, self.nodemgr, workerip)
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
            logger.info ("create container with : name-%s, username-%s, clustername-%s, clusterid-%s, hostname-%s, ip-%s, gateway-%s, image-%s" % (lxc_name, username, clustername, str(clusterid), hostname, ips[i], gateway, image_json))
            [success,message] = oneworker.create_container(lxc_name, proxy_public_ip, username, uid, json.dumps(setting) , clustername, str(clusterid), str(i), hostname, ips[i], gateway, image_json)
            if success is False:
                self.networkmgr.release_userips(username, ips[i])
                logger.info("container create failed, so vcluster create failed")
                return [False, message]
            logger.info("container create success")
            hosts = hosts + ips[i].split("/")[0] + "\t" + hostname + "\t" + hostname + "."+clustername + "\n"
            containers.append(Container(lxc_name,hostname,ips[i],workerip,image['name'],datetime.datetime.now(),setting))
            #containers.append({ 'containername':lxc_name, 'hostname':hostname, 'ip':ips[i], 'host':workerip, 'image':image['name'], 'lastsave':datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'setting': setting })
        hostfile = open(hostpath, 'w')
        hostfile.write(hosts)
        hostfile.close()
        #clusterfile = open(clusterpath, 'w')
        vcluster = VCluster(clusterid,clustername,username,'stopped',clustersize,clustersize,proxy_server_ip,proxy_public_ip)
        for con in containers:
            vcluster.containers.append(con)
        db.session.add(vcluster)
        db_commit()
        #proxy_url = env.getenv("PORTAL_URL") +"/"+ proxy_public_ip +"/_web/" + username + "/" + clustername
        #info = {'clusterid':clusterid, 'status':'stopped', 'size':clustersize, 'containers':containers, 'nextcid': clustersize, 'create_time':datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'start_time':"------"}
        #info['proxy_url'] = proxy_url
        #info['proxy_server_ip'] = proxy_server_ip
        #info['proxy_public_ip'] = proxy_public_ip
        #info['port_mapping'] = []
        #clusterfile.write(json.dumps(info))
        #clusterfile.close()
        return [True, str(vcluster)]

    def scale_out_cluster(self,clustername,username, image,user_info, setting):
        if not self.is_cluster(clustername,username):
            return [False, "cluster:%s not found" % clustername]
        if self.imgmgr.get_image_size(image) + 100 > int(setting["disk"]):
            return [False, "the size of disk is not big enough for the image"]
        workers = self.nodemgr.get_base_nodeips()
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
        oneworker = self.nodemgr.ip_to_rpc(workerip)
        lxc_name = username + "-" + str(clusterid) + "-" + str(cid)
        hostname = "host-" + str(cid)
        proxy_server_ip = clusterinfo['proxy_server_ip']
        proxy_public_ip = clusterinfo['proxy_public_ip']
        uid = json.loads(user_info)["data"]["id"]
        [success, message] = oneworker.create_container(lxc_name, proxy_public_ip, username, uid, json.dumps(setting), clustername, clusterid, str(cid), hostname, ip, gateway, image_json)
        if success is False:
            self.networkmgr.release_userips(username, ip)
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
        [success,vcluster] = self.get_vcluster(clustername,username)
        if not success:
            return [False, "Fail to write info."]
        vcluster.nextcid = int(clusterinfo['nextcid']) + 1
        vcluster.size = int(clusterinfo['size']) + 1
        vcluster.containers.append(Container(lxc_name,hostname,ip,workerip,image['name'],datetime.datetime.now(),setting))
        #{'containername':lxc_name, 'hostname':hostname, 'ip':ip, 'host':workerip, 'image':image['name'], 'lastsave':datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'setting': setting})
        db.session.add(vcluster)
        db_commit()
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

    def count_port_mapping(self, username):
        return sum([len(self.get_clusterinfo(cluster, username)[1]['port_mapping']) for cluster in self.list_clusters(username)[1]])

    def add_port_mapping(self,username,clustername,node_name,node_ip,port,quota):
        port_mapping_count = self.count_port_mapping(username)

        if port_mapping_count >= int(quota['portmapping']):
            return [False, 'Port mapping quota exceed.']

        [status, clusterinfo] = self.get_clusterinfo(clustername, username)
        if clusterinfo['status'] == 'stopped':
            return [False, 'Please start the clusters first.']
        host_port = 0
        if self.distributedgw == 'True':
            worker = self.nodemgr.ip_to_rpc(clusterinfo['proxy_server_ip'])
            [success, host_port] = worker.acquire_port_mapping(node_name, node_ip, port)
        else:
            [success, host_port] = portcontrol.acquire_port_mapping(node_name, node_ip, port)
        if not success:
            return [False, host_port]
        [status,vcluster] = self.get_vcluster(clustername,username)
        if not status:
            return [False,"VCluster not found."]
        vcluster.port_mapping.append(PortMapping(node_name,node_ip,port,host_port))
        db.session.add(vcluster)
        db_commit()
        return [True, json.loads(str(vcluster))]

    def recover_port_mapping(self,username,clustername):
        [status, clusterinfo] = self.get_clusterinfo(clustername, username)
        for rec in clusterinfo['port_mapping']:
            if self.distributedgw == 'True':
                worker = self.nodemgr.ip_to_rpc(clusterinfo['proxy_server_ip'])
                [success, host_port] = worker.acquire_port_mapping(rec['node_name'], rec['node_ip'], rec['node_port'], rec['host_port'])
            else:
                [success, host_port] = portcontrol.acquire_port_mapping(rec['node_name'], rec['node_ip'], rec['node_port'], rec['host_port'])
            if not success:
                return [False, host_port]
        return [True, clusterinfo]

    def delete_all_port_mapping(self, username, clustername, node_name):
        [status, vcluster] = self.get_vcluster(clustername, username)
        if not status:
            return [False,"VCluster not found."]
        error_msg = None
        delete_list = []
        for item in vcluster.port_mapping:
            if item.node_name == node_name:
                node_ip = item.node_ip
                node_port = item.node_port
                if self.distributedgw == 'True':
                    worker = self.nodemgr.ip_to_rpc(vcluster.proxy_server_ip)
                    [success,msg] = worker.release_port_mapping(node_name, node_ip, str(node_port))
                else:
                    [success,msg] = portcontrol.release_port_mapping(node_name, node_ip, str(node_port))
                if not success:
                    error_msg = msg
                else:
                    delete_list.append(item)
        if len(delete_list) > 0:
            for item in delete_list:
                db.session.delete(item)
            db_commit()
        else:
            return [True,"No port mapping."]
        if error_msg is not None:
            return [False,error_msg]
        else:
            return [True,"Success"]

    def delete_port_mapping(self, username, clustername, node_name, node_port):
        [status, vcluster] = self.get_vcluster(clustername, username)
        if not status:
            return [False,"VCluster not found."]
        for item in vcluster.port_mapping:
            if item.node_name == node_name and str(item.node_port) == str(node_port):
                node_ip = item.node_ip
                node_port = item.node_port
                if self.distributedgw == 'True':
                    worker = self.nodemgr.ip_to_rpc(vcluster.proxy_server_ip)
                    [success,msg] = worker.release_port_mapping(node_name, node_ip, str(node_port))
                else:
                    [success,msg] = portcontrol.release_port_mapping(node_name, node_ip, str(node_port))
                db.session.delete(item)
                db_commit()
                if success:
                    return [True, json.loads(str(vcluster))]
                else:
                    return [False, msg]
        return [False, "No port mapping."]

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
                worker = self.nodemgr.ip_to_rpc(container['host'])
                worker.create_image(username,imagetmp,containername)
                fimage = container['image']
                logger.info("image: %s created" % imagetmp)
                break
        else:
            logger.error("container: %s not found" % containername)
        for container in containers:
            if container['containername'] != containername:
                logger.info("container: %s now flush" % container['containername'])
                worker = self.nodemgr.ip_to_rpc(container['host'])
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
        [status, vcluster] = self.get_vcluster(clustername,username)
        if not status:
            return [False, "cluster not found"]
        containers = vcluster.containers
        for container in containers:
            if container.containername == containername:
                logger.info("container: %s found" % containername)
                worker = self.nodemgr.ip_to_rpc(container.host)
                if worker is None:
                    return [False, "The worker %s can't be found or has been stopped." % container.host]
                res = worker.create_image(username,imagename,containername,description,imagenum)
                container.lastsave = datetime.datetime.now()
                container.image = imagename
                break
        else:
            res = [False, "container not found"]
            logger.error("container: %s not found" % containername)
        db_commit()
        return res

    def delete_cluster(self, clustername, username, user_info):
        [status, vcluster] = self.get_vcluster(clustername, username)
        if not status:
            return [False, "cluster not found"]
        if vcluster.status =='running':
            return [False, "cluster is still running, you need to stop it and then delete"]
        ips = []
        for container in vcluster.containers:
            worker = self.nodemgr.ip_to_rpc(container.host)
            if worker is None:
                return [False, "The worker %s can't be found or has been stopped." % container.host]
            worker.delete_container(container.containername)
            db.session.delete(container)
            ips.append(container.ip)
        logger.info("delete vcluster and release vcluster ips")
        self.networkmgr.release_userips(username, ips)
        self.networkmgr.printpools()
        #os.remove(self.fspath+"/global/users/"+username+"/clusters/"+clustername)
        for bh in vcluster.billing_history:
            db.session.delete(bh)
        db.session.delete(vcluster)
        db_commit()
        os.remove(self.fspath+"/global/users/"+username+"/hosts/"+str(vcluster.clusterid)+".hosts")

        groupname = json.loads(user_info)["data"]["group"]
        uid = json.loads(user_info)["data"]["id"]
        [status, clusters] = self.list_clusters(username)
        if len(clusters) == 0:
            self.networkmgr.del_user(username)
            self.networkmgr.del_usrgwbr(username, uid, self.nodemgr)
            #logger.info("vlanid release triggered")

        return [True, "cluster delete"]

    def scale_in_cluster(self, clustername, username, containername):
        [status, vcluster] = self.get_vcluster(clustername, username)
        if not status:
            return [False, "cluster not found"]
        new_containers = []
        for container in vcluster.containers:
            if container.containername == containername:
                worker = self.nodemgr.ip_to_rpc(container.host)
                if worker is None:
                    return [False, "The worker %s can't be found or has been stopped." % container.host]
                worker.delete_container(containername)
                db.session.delete(container)
                self.networkmgr.release_userips(username, container.ip)
                self.networkmgr.printpools()
        vcluster.size -= 1
        cid = containername[containername.rindex("-")+1:]
        clusterid = vcluster.clusterid
        hostpath = self.fspath + "/global/users/" + username + "/hosts/" + str(clusterid) + ".hosts"
        db_commit()
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
        [success, msg] = self.delete_all_port_mapping(username, clustername, containername)
        if not success:
            return [False, msg]
        [status, info] = self.get_clusterinfo(clustername, username)
        return [True, info]

    def get_clustersetting(self, clustername, username, containername, allcontainer):
        [status,vcluster] = self.get_vcluster(clustername,username)
        if vcluster is None:
            logger.error("cluster file: %s not found" % clustername)
            return [False, "cluster file not found"]
        cpu = 0
        memory = 0
        disk = 0
        if allcontainer:
            for container in vcluster.containers:
                cpu += int(container.setting_cpu)
                memory += int(container.setting_mem)
                disk += int(container.setting_disk)
        else:
            for container in vcluster.containers:
                if container.containername == containername:
                    cpu += int(container.setting_cpu)
                    memory += int(container.setting_mem)
                    disk += int(container.setting_disk)
        return [True, {'cpu':cpu, 'memory':memory, 'disk':disk}]

    def update_cluster_baseurl(self, clustername, username, oldip, newip):
        [status, info] = self.get_clusterinfo(clustername, username)
        if not status:
            return [False, "cluster not found"]
        logger.info("%s %s:base_url need to be modified(%s %s)."%(username,clustername,oldip,newip))
        for container in info['containers']:
            worker = self.nodemgr.ip_to_rpc(container['host'])
            #if worker is None:
            #    return [False, "The worker can't be found or has been stopped."]
            self.nodemgr.call_rpc_function(worker,'update_baseurl',[container['containername'],oldip,newip])
            self.nodemgr.call_rpc_function(worker,'stop_container',[container['containername']])

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

    def start_cluster(self, clustername, username, user_info):
        uid = user_info['data']['id']
        input_rate_limit = user_info['data']['groupinfo']['input_rate_limit']
        output_rate_limit = user_info['data']['groupinfo']['output_rate_limit']
        [status, info] = self.get_clusterinfo(clustername, username)
        if not status:
            return [False, "cluster not found"]
        if info['status'] == 'running':
            return [False, "cluster is already running"]
        # set proxy
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
            logger.info(traceback.format_exc())
            return [False, "start cluster failed with setting proxy failed"]
        # check gateway for user
        # after reboot, user gateway goes down and lose its configuration
        # so, check is necessary
        self.networkmgr.check_usergw(input_rate_limit, output_rate_limit, username, uid, self.nodemgr,self.distributedgw=='True')
        # start containers
        for container in info['containers']:
            # set up gre from user's gateway host to container's host.
            self.networkmgr.check_usergre(username, uid, container['host'], self.nodemgr, self.distributedgw=='True')
            worker = self.nodemgr.ip_to_rpc(container['host'])
            if worker is None:
                return [False, "The worker %s can't be found or has been stopped." % container['host']]
            worker.start_container(container['containername'])
            worker.start_services(container['containername'])
            namesplit = container['containername'].split('-')
            portname = namesplit[1] + '-' + namesplit[2]
            worker.recover_usernet(portname, uid, info['proxy_server_ip'], container['host']==info['proxy_server_ip'])
        [status,vcluster] = self.get_vcluster(clustername,username)
        vcluster.status ='running'
        vcluster.start_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        vcluster.is_warned = False
        if not db_commit():
            return [False, "Commit Errror"]
        return [True, "start cluster"]

    def mount_cluster(self, clustername, username):
        [status, info] = self.get_clusterinfo(clustername, username)
        if not status:
            return [False, "cluster not found"]
        for container in info['containers']:
            worker = self.nodemgr.ip_to_rpc(container['host'])
            if worker is None:
                return [False, "The worker %s can't be found or has been stopped." % container['host']]
            worker.mount_container(container['containername'])
        return [True, "mount cluster"]

    def recover_cluster_on(self, host):
        logger.info("start to recover clusters which has containers on host %s" % host)
        vcs = VCluster.query.filter(VCluster.status.in_(["running","error"])).all()
        need_recovers = []
        for vc in vcs:
            if len(vc.containers.filter_by(host=host).all()) > 0:
                need_recovers.append([vc.clustername, vc.ownername])
        self.recover_clusters(need_recovers)
    
    def recover_clusters(self, clusters_users):
        logger.info("start to recover clusters:"+ str(clusters_users))
        clusters = [d[0] for d in clusters_users]
        users = set([d[1] for d in clusters_users])
        auth_key = env.getenv('AUTH_KEY')
        res = post_to_user("/master/user/groupinfo/", {'auth_key':auth_key})
        #logger.info(res)
        groups = json.loads(res['groups'])
        quotas = {}
        for group in groups:
            #logger.info(group)
            quotas[group['name']] = group['quotas']
        recover_data = {}
        recover_queue = Queue(maxsize=0)
        for user in users:
            recover_info = post_to_user("/master/user/recoverinfo/", {'username':user,'auth_key':auth_key})
            recover_data[user] = {}
            recover_data[user]['uid'] = recover_info['uid']
            recover_data[user]['groupname'] = recover_info['groupname']                
        
        for d in clusters_users:
            recover_queue.put({"user": d[1], "vcluster":d[0], "times":0})
        
        now_times = 0
        sleep_time = 10
        max_times = 1
        while not recover_queue.empty():
            q = recover_queue.get()
            if q['times'] >= max_times:
                logger.error("recovering retry more than %d times, return" % max_times)
                return
            if q['times'] > now_times:
                logger.error("recovering retry %d times, sleep %d seconds" % (q['times'], sleep_time))
                time.sleep(sleep_time)
                sleep_time = 2 * sleep_time
                now_times = q['times']

            user = q['user']
            cluster = q['vcluster']
            logger.info ("recovering cluster:%s for user:%s %d times..." % (cluster, user, q['times']))
            uid = recover_data[user]['uid']
            groupname = recover_data[user]['groupname']
            input_rate_limit = quotas[groupname]['input_rate_limit']
            output_rate_limit = quotas[groupname]['output_rate_limit']
            success1, msg = self.recover_cluster(cluster, user, uid, input_rate_limit, output_rate_limit)
            success2, cludb = self.get_vcluster(cluster, user)
            if not success2:
                logger.error("cannot find vcluster %s" % cluster)
                continue
            if not success1:
                logger.error(msg)
                q["times"] += 1
                recover_queue.put(q)
                cludb.status = "error"
            else:
                cludb.status = "running"
            db_commit()

    def recover_cluster(self, clustername, username, uid, input_rate_limit, output_rate_limit):
        [status, info] = self.get_clusterinfo(clustername, username)
        if not status:
            return [False, "cluster not found"]
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
                try:
                    self.nodemgr.call_rpc_function(worker,'set_route',["/" + info['proxy_public_ip'] + '/go/'+username+'/'+clustername, target])
                except Exception as err:
                    logger.error(traceback.format_exc())
                    return [False, "fail to set proxy on node %s" % info['proxy_server_ip']]
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
        self.networkmgr.check_usergw(input_rate_limit, output_rate_limit, username, uid, self.nodemgr,self.distributedgw=='True')
        # recover containers of this cluster
        for container in info['containers']:
            # set up gre from user's gateway host to container's host.
            self.networkmgr.check_usergre(username, uid, container['host'], self.nodemgr, self.distributedgw=='True')
            worker = self.nodemgr.ip_to_rpc(container['host'])
            if worker is None:
                return [False, "The worker %s can't be found or has been stopped." % container['host']]
            try:
                self.nodemgr.call_rpc_function(worker,'recover_container',[container['containername']])
                namesplit = container['containername'].split('-')
                portname = namesplit[1] + '-' + namesplit[2]
                self.nodemgr.call_rpc_function(worker,'recover_usernet',[portname, uid, info['proxy_server_ip'], container['host']==info['proxy_server_ip']])
            except Exception as err:
                logger.error(traceback.format_exc())
                return [False, "fail to recover container or usernet on node %s" % container['host']]                
        # recover ports mapping
        [success, msg] = self.recover_port_mapping(username,clustername)
        if not success:
            return [False, msg]
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
            self.delete_all_port_mapping(username,clustername,container['containername'])
            worker = self.nodemgr.ip_to_rpc(container['host'])
            if worker is None:
                return [False, "The worker %s can't be found or has been stopped." % container['host']]
            worker.stop_container(container['containername'])
        [status, vcluster] = self.get_vcluster(clustername, username)
        vcluster.status = 'stopped'
        vcluster.start_time ="------"
        vcluster.stop_time = datetime.datetime.now()
        if not db_commit():
            return [False, "Commit Errror"]
        return [True, "stop cluster"]

    def detach_cluster(self, clustername, username):
        [status, info] = self.get_clusterinfo(clustername, username)
        if not status:
            return [False, "cluster not found"]
        if info['status'] == 'running':
            return [False, 'cluster is running, please stop it first']
        for container in info['containers']:
            worker = self.nodemgr.ip_to_rpc(container['host'])
            if worker is None:
                return [False, "The worker %s can't be found or has been stopped." % container['host']]
            worker.detach_container(container['containername'])
        return [True, "detach cluster"]

    def list_clusters(self, user):
        clusters = VCluster.query.filter_by(ownername = user).all()
        clusters = [clu.clustername for clu in clusters]
        '''full_clusters = []
        for cluster in clusters:
            single_cluster = {}
            single_cluster['name'] = cluster
            [status, info] = self.get_clusterinfo(cluster,user)
            if info['status'] == 'running':
                single_cluster['status'] = 'running'
            else:
                single_cluster['status'] = 'stopping'
            full_clusters.append(single_cluster)'''
        return [True, clusters]

    def migrate_container(self, clustername, username, containername, new_host, user_info):
        [status, info] = self.get_clusterinfo(clustername, username)
        if not status:
            return [False, "cluster not found"]
        if info['status'] != 'stopped':
            return [False, 'cluster is not stopped']

        con_db = Container.query.get(containername)
        if con_db is None:
            return [False, 'Container not found']
        if con_db.host == new_host:
            return [False, 'Container has been on the new host']

        oldworker = self.nodemgr.ip_to_rpc(con_db.host)
        if oldworker is None:
            return [False, "Old host worker %s can't be found or has been stopped." % con_db.host]
        oldworker.stop_container(containername)
        imagename = "migrate-" + containername + "-" + datetime.datetime.now().strftime("%Y-%m-%d")
        logger.info("Save Image for container:%s imagename:%s host:%s"%(containername, imagename, con_db.host))
        status,msg = oldworker.create_image(username,imagename,containername,"",10000)
        if not status:
            return [False, msg]
        #con_db.lastsave = datetime.datetime.now()
        #con_db.image = imagename

        self.networkmgr.load_usrgw(username)
        proxy_server_ip = self.networkmgr.usrgws[username]
        [status, proxy_public_ip] = self.etcd.getkey("machines/publicIP/"+proxy_server_ip)
        if not status:
            self.imgmgr.removeImage(username,imagename)
            logger.error("Fail to get proxy_public_ip %s."%(proxy_server_ip))
            return [False, "Fail to get proxy server public IP."]
        uid = user_info['data']['id']
        setting = {
                'cpu': con_db.setting_cpu,
                'memory': con_db.setting_mem,
                'disk': con_db.setting_disk
                }
        _, clusterid, cid = containername.split('-')
        hostname = "host-"+str(cid)
        gateway = self.networkmgr.get_usergw(username)
        image = {'name':imagename,'type':'private','owner':username }
        logger.info("Migrate: proxy_ip:%s uid:%s setting:%s clusterid:%s cid:%s hostname:%s gateway:%s image:%s"
                    %(proxy_public_ip, str(uid), str(setting), clusterid, cid, hostname, gateway, str(image)))
        logger.info("Migrate: create container(%s) on new host %s"%(containername, new_host))

        worker = self.nodemgr.ip_to_rpc(new_host)
        if worker is None:
            self.imgmgr.removeImage(username,imagename)
            return [False, "New host worker %s can't be found or has been stopped." % new_host]
        status,msg = worker.create_container(containername, proxy_public_ip, username, uid, json.dumps(setting),
                     clustername, str(clusterid), str(cid), hostname, con_db.ip, gateway, json.dumps(image))
        if not status:
            self.imgmgr.removeImage(username,imagename)
            return [False, msg]
        con_db.host = new_host
        try:
            db.session.commit()
        except Exception as err:
            logger.error(traceback.format_exc())
            db.session.rollback()
            worker.delete_container(containername)
            self.imgmgr.removeImage(username,imagename)
            return [False, "Database commit error!"]
        oldworker.delete_container(containername)
        self.imgmgr.removeImage(username,imagename)
        return [True,""]

    def migrate_cluster(self, clustername, username, src_host, new_host_list, user_info):
        [status, info] = self.get_clusterinfo(clustername, username)
        if not status:
            return [False, "cluster not found"]
        prestatus = info['status']
        self.stop_cluster(clustername, username)
        for container in info['containers']:
            if not container['host'] == src_host:
                continue
            random.shuffle(new_host_list)
            for new_host in new_host_list:
                status,msg = self.migrate_container(clustername,username,container['containername'],new_host,user_info)
                if status:
                    break
                else:
                    logger.error(msg)
            else:
                if prestatus == 'running':
                    self.start_cluster(clustername, username, user_info)
                return [False, msg]
        logger.info("[Migrate] prestatus:%s for cluster(%s) user(%s)"%(prestatus, clustername, username))
        if prestatus == 'running':
            status, msg = self.start_cluster(clustername, username, user_info)
            if not status:
                return [False, msg]
        return [True, ""]

    def migrate_host(self, src_host, new_host_list, ulockmgr):
        [status, vcluster_list] = self.get_all_clusterinfo()
        if not status:
            return [False, vcluster_list]
        auth_key = env.getenv('AUTH_KEY')
        res = post_to_user("/master/user/groupinfo/", {'auth_key':auth_key})
        groups = json.loads(res['groups'])
        quotas = {}
        for group in groups:
            quotas[group['name']] = group['quotas']

        for vcluster in vcluster_list:
            if 'ownername' not in vcluster.keys():
                return [Flase, 'Ownername not in vcluster(%s).keys' % str(vcluster) ]
            try:
                username = vcluster['ownername']
                ulockmgr.acquire(username)
                clustername = vcluster['clustername']
                rc_info = post_to_user("/master/user/recoverinfo/", {'username':username,'auth_key':auth_key})
                groupname = rc_info['groupname']
                user_info = {"data":{"id":rc_info['uid'],"groupinfo":quotas[groupname]}}
                self.migrate_cluster(clustername, username, src_host, new_host_list, user_info)
            except Exception as ex:
                ulockmgr.release(username)
                logger.error(traceback.format_exc())
                return [False, str(ex)]
            ulockmgr.release(username)
        return [True, ""]

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
        [status, vcluster] = self.get_vcluster(clustername, username)
        if not status:
            return [False, "cluster not found"]
        vcluster.proxy_server_ip = proxy_server_ip
        [status, proxy_public_ip] = self.etcd.getkey("machines/publicIP/"+proxy_server_ip)
        if not status:
            logger.error("Fail to get proxy_public_ip %s."%(proxy_server_ip))
            proxy_public_ip = proxy_server_ip
        vcluster.proxy_public_ip = proxy_public_ip
        #proxy_url = env.getenv("PORTAL_URL") +"/"+ proxy_public_ip +"/_web/" + username + "/" + clustername
        #info['proxy_url'] = proxy_url
        if not db_commit():
            return [False, "Commit Errror"]
        return proxy_public_ip

    def get_clusterinfo(self, clustername, username):
        [success,vcluster] = self.get_vcluster(clustername,username)
        if vcluster is None:
            return [False, "cluster not found"]
        vcluster = json.loads(str(vcluster))
        return [True, vcluster]

    def get_vcluster(self, clustername, username):
        vcluster = VCluster.query.filter_by(ownername=username,clustername=clustername).first()
        if vcluster is None:
            return [False, None]
        else:
            return [True, vcluster]

    def get_all_clusterinfo(self):
        vcluster_list = VCluster.query.all()
        #logger.info(str(vcluster_list))
        if vcluster_list is None:
            return [False, None]
        else:
            return [True, json.loads(str(vcluster_list))]

    # acquire cluster id from etcd
    def _acquire_id(self):
        self.clusterid_locks.acquire()
        clusterid = self.etcd.getkey("vcluster/nextid")[1]
        self.etcd.setkey("vcluster/nextid", str(int(clusterid)+1))
        self.clusterid_locks.release()
        return int(clusterid)
