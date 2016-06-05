#!/usr/bin/python3

import subprocess, os, json
import imagemgr
from log import logger
import env
from lvmtool import sys_run, check_volume

class Container(object):
    def __init__(self, addr, etcdclient):
        self.addr = addr
        self.etcd=etcdclient
        self.libpath = env.getenv('DOCKLET_LIB')
        self.confpath = env.getenv('DOCKLET_CONF')
        self.fspath = env.getenv('FS_PREFIX')
        # set jupyter running dir in container
        self.rundir = "/home/jupyter"
        # set root running dir in container
        self.nodehome = "/root"

        self.lxcpath = "/var/lib/lxc"
        self.imgmgr = imagemgr.ImageMgr()

    def create_container(self, lxc_name, username, user_info, clustername, clusterid, containerid, hostname, ip, gateway, vlanid, image):
        logger.info("create container %s of %s for %s" %(lxc_name, clustername, username))
        try:
            user_info = json.loads(user_info) 
            cpu = int(user_info["data"]["groupinfo"]["cpu"]) * 100000
            memory = user_info["data"]["groupinfo"]["memory"]
            disk = user_info["data"]["groupinfo"]["disk"]
            image = json.loads(image) 
            status = self.imgmgr.prepareFS(username,image,lxc_name,disk)
            if not status:
                return [False, "Create container failed when preparing filesystem, possibly insufficient space"]
            
            #Ret = subprocess.run([self.libpath+"/lxc_control.sh",
            #    "create", lxc_name, username, str(clusterid), hostname,
            #    ip, gateway, str(vlanid), str(cpu), str(memory)], stdout=subprocess.PIPE,
            #    stderr=subprocess.STDOUT,shell=False, check=True)
            
            rootfs = "/var/lib/lxc/%s/rootfs" % lxc_name
            
            if not os.path.isdir("%s/global/users/%s" % (self.fspath,username)):
                logger.error("user %s directory not found" % username)
                return [False, "user directory not found"]
            sys_run("mkdir -p /var/lib/lxc/%s" % lxc_name)
            logger.info("generate config file for %s" % lxc_name)
            
            def config_prepare(content):
                content = content.replace("%ROOTFS%",rootfs)
                content = content.replace("%HOSTNAME%",hostname)
                content = content.replace("%IP%",ip)
                content = content.replace("%GATEWAY%",gateway)
                content = content.replace("%CONTAINER_MEMORY%",str(memory))
                content = content.replace("%CONTAINER_CPU%",str(cpu))
                content = content.replace("%FS_PREFIX%",self.fspath)
                content = content.replace("%USERNAME%",username)
                content = content.replace("%CLUSTERID%",str(clusterid))
                content = content.replace("%LXCSCRIPT%",env.getenv("LXC_SCRIPT"))
                content = content.replace("%LXCNAME%",lxc_name)
                content = content.replace("%VLANID%",str(vlanid))
                content = content.replace("%CLUSTERNAME%", clustername)
                content = content.replace("%VETHPAIR%", str(clusterid)+'-'+str(containerid))
                return content

            conffile = open(self.confpath+"/container.conf", 'r')
            conftext = conffile.read()
            conffile.close()
            conftext = config_prepare(conftext)

            conffile = open("/var/lib/lxc/%s/config" % lxc_name,"w")
            conffile.write(conftext)
            conffile.close()

            if os.path.isfile(self.confpath+"/lxc.custom.conf"):
                conffile = open(self.confpath+"/lxc.custom.conf", 'r')
                conftext = conffile.read()
                conffile.close()
                conftext = config_prepare(conftext)
                conffile = open("/var/lib/lxc/%s/config" % lxc_name, 'a')
                conffile.write(conftext)
                conffile.close()

            #logger.debug(Ret.stdout.decode('utf-8'))
            logger.info("create container %s success" % lxc_name)

            # get AUTH COOKIE URL for jupyter
            [status, authurl] = self.etcd.getkey("web/authurl")
            if not status:
                [status, masterip] = self.etcd.getkey("service/master")
                if status:
                    webport = env.getenv("WEB_PORT")
                    authurl = "http://%s:%s/jupyter" % (masterip,
                            webport)
                else:
                    logger.error ("get AUTH COOKIE URL failed for jupyter")
                    authurl = "error"
            
            cookiename='docklet-jupyter-cookie'

            rundir = self.lxcpath+'/'+lxc_name+'/rootfs' + self.rundir

            logger.debug(rundir)

            if not os.path.exists(rundir):
                os.makedirs(rundir)
            else:
                if not os.path.isdir(rundir):
                    os.remove(rundir)
                    os.makedirs(rundir)

            jconfigpath = rundir + '/jupyter.config'
            config = open(jconfigpath, 'w')
            jconfigs="""USER=%s
PORT=%d
COOKIE_NAME=%s
BASE_URL=%s
HUB_PREFIX=%s
HUB_API_URL=%s
IP=%s
""" % (username, 10000, cookiename, '/go/'+username+'/'+clustername, '/jupyter',
        authurl, ip.split('/')[0])
            config.write(jconfigs)
            config.close()

        except subprocess.CalledProcessError as sube:
            logger.error('create container %s failed: %s' % (lxc_name,
                    sube.stdout.decode('utf-8')))
            return [False, "create container failed"]
        except Exception as e:
            logger.error(e)
            return [False, "create container failed"]
        return [True, "create container success"]

    def delete_container(self, lxc_name):
        logger.info ("delete container:%s" % lxc_name)
        if self.imgmgr.deleteFS(lxc_name):
            logger.info("delete container %s success" % lxc_name)
            return [True, "delete container success"]
        else:
            logger.info("delete container %s failed" % lxc_name)
            return [False, "delete container failed"]
        #status = subprocess.call([self.libpath+"/lxc_control.sh", "delete", lxc_name])
        #if int(status) == 1:
        #    logger.error("delete container %s failed" % lxc_name)
        #    return [False, "delete container failed"]
        #else:
        #    logger.info ("delete container %s success" % lxc_name)
        #    return [True, "delete container success"]

    # start container, if running, restart it
    def start_container(self, lxc_name):
        logger.info ("start container:%s" % lxc_name)
        #status = subprocess.call([self.libpath+"/lxc_control.sh", "start", lxc_name])
        #if int(status) == 1:
        #    logger.error ("start container %s failed" % lxc_name)
        #    return [False, "start container failed"]
        #else:
        #    logger.info ("start container %s success" % lxc_name)
        #    return [True, "start container success"]
        #subprocess.run(["lxc-stop -k -n %s" % lxc_name],
        #        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, check=True)
        try :
            subprocess.run(["lxc-start -n %s" % lxc_name],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, check=True)
            logger.info ("start container %s success" % lxc_name)
            return [True, "start container success"]
        except subprocess.CalledProcessError as sube:
            logger.error('start container %s failed: %s' % (lxc_name,
                    sube.stdout.decode('utf-8')))
            return [False, "start container failed"]

    # start container services
    # for the master node, jupyter must be started, 
    # for other node, ssh must be started.
    # container must be RUNNING before calling this service
    def start_services(self, lxc_name, services=[]):
        logger.info ("start services for container %s: %s" % (lxc_name, services))
        try:
            #Ret = subprocess.run(["lxc-attach -n %s -- ln -s /nfs %s" %
                #(lxc_name, self.nodehome)],
                #stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                #shell=True, check=False)
            #logger.debug ("prepare nfs for %s: %s" % (lxc_name,
                #Ret.stdout.decode('utf-8')))
            # not sure whether should execute this 
            #Ret = subprocess.run(["lxc-attach -n %s -- service ssh start" % lxc_name],
            #        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            #shell=True, check=False)
            #logger.debug(Ret.stdout.decode('utf-8'))
            if len(services) == 0: # master node
                Ret = subprocess.run(["lxc-attach -n %s -- su -c %s/start_jupyter.sh" % (lxc_name, self.rundir)],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, check=True)
                logger.debug (Ret)
            logger.info ("start services for container %s success" % lxc_name)
            return [True, "start container services success"]
        except subprocess.CalledProcessError as sube:
            logger.error('start services for container %s failed: %s' % (lxc_name,
                    sube.output.decode('utf-8')))
            return [False, "start services for container failed"]

    # recover container: if running, do nothing. if stopped, start it
    def recover_container(self, lxc_name):
        logger.info ("recover container:%s" % lxc_name)
        #status = subprocess.call([self.libpath+"/lxc_control.sh", "status", lxc_name])
        [success, status] = self.container_status(lxc_name)
        if not success:
            return [False, status]
        if status == 'stopped':
            logger.info("%s stopped, recover it to running" % lxc_name)
            if self.start_container(lxc_name)[0]:
                if self.start_services(lxc_name)[0]:
                    logger.info("%s recover success" % lxc_name)
                    return [True, "recover success"]
                else:
                    logger.error("%s recover failed with services not start" % lxc_name)
                    return [False, "recover failed for services not start"]
            else:
                logger.error("%s recover failed for container starting failed" % lxc_name)
                return [False, "recover failed for container starting failed"]
        else:
            logger.info("%s recover success" % lxc_name)
            return [True, "recover success"]

    def stop_container(self, lxc_name):
        logger.info ("stop container:%s" % lxc_name)
        #status = subprocess.call([self.libpath+"/lxc_control.sh", "stop", lxc_name])
        [success, status] = self.container_status(lxc_name)
        if not success:
            return [False, status]
        if status == "running":
            sys_run("lxc-stop -k -n %s" % lxc_name)
        [success, status] = self.container_status(lxc_name)
        if status == "running":
            logger.error("stop container %s failed" % lxc_name)
            return [False, "stop container failed"]
        else:
            logger.info("stop container %s success" % lxc_name)
            return [True, "stop container success"]
        #if int(status) == 1:
        #    logger.error ("stop container %s failed" % lxc_name)
        #    return [False, "stop container failed"]
        #else:
        #    logger.info ("stop container %s success" % lxc_name)
        #    return [True, "stop container success"]

    # check container: check LV and mountpoints, if wrong, try to repair it
    def check_container(self, lxc_name):
        logger.info ("check container:%s" % lxc_name)
        if not check_volume("docklet-group", lxc_name):
            logger.error("check container %s failed" % lxc_name)
            return [False, "check container failed"]
        #status = subprocess.call([self.libpath+"/lxc_control.sh", "check", lxc_name])
        self.imgmgr.checkFS(lxc_name)
        logger.info ("check container %s success" % lxc_name)
        return [True, "check container success"]

    def is_container(self, lxc_name):
        if os.path.isdir(self.lxcpath+"/"+lxc_name):
            return True
        else:
            return False

    def container_status(self, lxc_name):
        if not self.is_container(lxc_name):
            return [False, "container not found"]
        Ret = sys_run("lxc-info -n %s | grep RUNNING" % lxc_name)
        #status = subprocess.call([self.libpath+"/lxc_control.sh", "status", lxc_name])
        if Ret.returncode == 0:
            return [True, 'running']
        else:
            return [True, 'stopped']

    def list_containers(self):
        if not os.path.isdir(self.lxcpath):
            return [True, []]
        lxclist = []
        for onedir in os.listdir(self.lxcpath):
            if os.path.isfile(self.lxcpath+"/"+onedir+"/config"):
                lxclist.append(onedir)
            else:
                logger.warning ("%s in lxc directory, but not container directory" % onedir)
        return [True, lxclist]

    def delete_allcontainers(self):
        logger.info ("deleting all containers...")
        [status, containers] = self.list_containers()
        result = True
        for container in containers:
            [result, status] = self.container_status(container)
            if status=='running':
                self.stop_container(container)
            result = result & self.delete_container(container)[0]
        if result:
            logger.info ("deleted all containers success")
            return [True, 'all deleted']
        else:
            logger.error ("deleted all containers failed")
            return [False, 'some containers delete failed']

    # list containers in /var/lib/lxc/ as local
    # list containers in FS_PREFIX/global/... on this host as global
    def diff_containers(self):
        [status, localcontainers] = self.list_containers()
        globalpath = self.fspath+"/global/users/"
        users = os.listdir(globalpath)
        globalcontainers = []
        for user in users:
            clusters = os.listdir(globalpath+user+"/clusters")
            for cluster in clusters:
                clusterfile = open(globalpath+user+"/clusters/"+cluster, 'r')
                clusterinfo = json.loads(clusterfile.read())
                for container in clusterinfo['containers']:
                    if container['host'] == self.addr:
                        globalcontainers.append(container['containername'])
        both = []
        onlylocal = []
        onlyglobal = []
        for container in localcontainers:
            if container in globalcontainers:
                both.append(container)
            else:
                onlylocal.append(container)
        for container in globalcontainers:
            if container not in localcontainers:
                onlyglobal.append(container)
        return [both, onlylocal, onlyglobal]

    def create_image(self,username,imagename,containername,description="not thing",imagenum=10):
        return self.imgmgr.createImage(username,imagename,containername,description,imagenum)

    # check all local containers
    def check_allcontainers(self):
        [both, onlylocal, onlyglobal] = self.diff_containers()
        logger.info("check all containers and repair them")
        status = True
        result = True
        for container in both:
            logger.info ("%s in LOCAL and GLOBAL checks..." % container)
            [status, meg]=self.check_container(container)
            result = result & status
        if len(onlylocal) > 0:
            result = False
            logger.error ("some container only exists in LOCAL: %s" % onlylocal)
        if len(onlyglobal) > 0:
            result = False
            logger.error ("some container only exists in GLOBAL: %s" % onlyglobal)
        if status:
            logger.info ("check all containers success")
            return [True, 'all is ok']
        else:
            logger.error ("check all containers failed")
            return [False, 'not ok']
