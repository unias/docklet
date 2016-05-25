#!/usr/bin/python3

import threading, random, time, xmlrpc.client, sys
#import network
from nettools import netcontrol
from log import logger
import env

##########################################
#                NodeMgr
# Description : manage the physical nodes
#               1. list running nodes now
#               2. update node list when new node joins
# ETCD table :
#         machines/allnodes  -- all nodes in docklet, for recovery
#         machines/runnodes  -- run nodes of this start up
##############################################
class NodeMgr(object):
    def __init__(self, networkmgr, etcdclient, addr, mode):
        self.addr = addr
        logger.info ("begin initialize on %s" % self.addr)
        self.networkmgr = networkmgr
        self.etcd = etcdclient
        self.mode = mode
        self.workerport = env.getenv('WORKER_PORT')

        # initialize the network
        logger.info ("initialize network")

        # 'docklet-br' not need ip address. Because every user has gateway
        #[status, result] = self.networkmgr.acquire_sysips_cidr()
        #self.networkmgr.printpools()
        #if not status:
        #    logger.info ("initialize network failed, no IP for system bridge")
        #    sys.exit(1)
        #self.bridgeip = result[0]
        #logger.info ("initialize bridge wih ip %s" % self.bridgeip)
        #network.netsetup("init", self.bridgeip)

        #if self.mode == 'new':
        #    if netcontrol.bridge_exists('docklet-br'):
        #        netcontrol.del_bridge('docklet-br')
        #    netcontrol.new_bridge('docklet-br')
        #else:
        #    if not netcontrol.bridge_exists('docklet-br'):
        #        logger.error("docklet-br not found")
        #        sys.exit(1)

        # init rpc list 
        self.rpcs = []

        # get allnodes
        self.allnodes = self._nodelist_etcd("allnodes")
        self.runnodes = []
        [status, runlist] = self.etcd.listdir("machines/runnodes")
        for node in runlist:
            nodeip = node['key'].rsplit('/',1)[1]
            if node['value'] == 'ok':
                logger.info ("running node %s" % nodeip)
                self.runnodes.append(nodeip)
                self.rpcs.append(xmlrpc.client.ServerProxy("http://%s:%s" % (nodeip, self.workerport)))
                logger.info ("add %s:%s in rpc client list" % (nodeip, self.workerport))
           
        logger.info ("all nodes are: %s" % self.allnodes)
        logger.info ("run nodes are: %s" % self.runnodes)

        # start new thread to watch whether a new node joins
        logger.info ("start thread to watch new nodes ...")
        self.thread_watchnewnode = threading.Thread(target=self._watchnewnode)
        self.thread_watchnewnode.start()
        # wait for all nodes joins
        while(True):
            allin = True
            for node in self.allnodes:
                if node not in self.runnodes:
                    allin = False
                    break
            if allin:
                logger.info("all nodes necessary joins ...")
                break
            time.sleep(0.05)
        logger.info ("run nodes are: %s" % self.runnodes)


    # get nodes list from etcd table
    def _nodelist_etcd(self, which):
        if which == "allnodes" or which == "runnodes":
            [status, nodeinfo]=self.etcd.listdir("machines/"+which)
            if status:
                nodelist = []
                for node in nodeinfo:
                    nodelist.append(node["key"].rsplit('/', 1)[1])
                return nodelist
        return []

    # thread target : watch whether a new node joins
    def _watchnewnode(self):
        while(True):
            time.sleep(0.1)
            [status, runlist] = self.etcd.listdir("machines/runnodes")
            if not status:
                logger.warning ("get runnodes list failed from etcd ")
                continue
            for node in runlist:
                nodeip = node['key'].rsplit('/',1)[1]
                if node['value']=='waiting':
                    #   waiting state can be deleted, there is no use to let master check 
                    # this state because worker will change it and master will not change it now.
                    # it is only preserved for compatible.
                    logger.info ("%s want to joins, call it to init first" % nodeip)
                elif node['value']=='work':
                    logger.info ("new node %s joins" % nodeip)
                    # setup GRE tunnels for new nodes
                    if self.addr == nodeip:
                        logger.debug ("worker start on master node. not need to setup GRE")
                    else:
                        logger.debug ("setup GRE for %s" % nodeip)
                        #if netcontrol.gre_exists('docklet-br', nodeip):
                        #    logger.debug("GRE for %s already exists, reuse it" % nodeip)
                        #else:
                        #    netcontrol.setup_gre('docklet-br', nodeip)
                    self.etcd.setkey("machines/runnodes/"+nodeip, "ok")
                    if nodeip not in self.runnodes:
                        self.runnodes.append(nodeip)
                        # node not in all node list is a new node.
                        if nodeip not in self.allnodes:
                            self.allnodes.append(nodeip)
                            self.etcd.setkey("machines/allnodes/"+nodeip, "ok")
                        logger.debug ("all nodes are: %s" % self.allnodes)
                        logger.debug ("run nodes are: %s" % self.runnodes)
                        self.rpcs.append(xmlrpc.client.ServerProxy("http://%s:%s"
                            % (nodeip, self.workerport)))
                        logger.info ("add %s:%s in rpc client list" %
                            (nodeip, self.workerport))
    # get all run nodes' IP addr
    def get_nodeips(self):
        return self.allnodes

    def get_rpcs(self):
        return self.rpcs

    def get_onerpc(self):
        return self.rpcs[random.randint(0, len(self.rpcs)-1)]

    def rpc_to_ip(self, rpcclient):
        return self.runnodes[self.rpcs.index(rpcclient)]

    def ip_to_rpc(self, nodeip):
        return self.rpcs[self.runnodes.index(nodeip)]

    def get_allnodes(self):
        return self.allnodes
