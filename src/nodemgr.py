#!/usr/bin/python3

import threading, random, time, xmlrpc.client, sys
#import network
from nettools import netcontrol,ovscontrol
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

        # delete the existing network
        logger.info ("delete the existing network")
        [success, bridges] = ovscontrol.list_bridges()
        if success:
            for bridge in bridges:
                if bridge.startswith("docklet-br"):
                    ovscontrol.del_bridge(bridge)
        else:
            logger.error(bridges)

        '''if self.mode == 'new':
            if netcontrol.bridge_exists('docklet-br'):
                netcontrol.del_bridge('docklet-br')
            netcontrol.new_bridge('docklet-br')
        else:
            if not netcontrol.bridge_exists('docklet-br'):
                logger.error("docklet-br not found")
                sys.exit(1)'''

        # get allnodes
        self.allnodes = self._nodelist_etcd("allnodes")
        self.runnodes = []
        [status, runlist] = self.etcd.listdir("machines/runnodes")
        for node in runlist:
            nodeip = node['key'].rsplit('/',1)[1]
            if node['value'] == 'ok':
                logger.info ("running node %s" % nodeip)
                self.runnodes.append(nodeip)

        logger.info ("all nodes are: %s" % self.allnodes)
        logger.info ("run nodes are: %s" % self.runnodes)

        # start new thread to watch whether a new node joins
        logger.info ("start thread to watch new nodes ...")
        self.thread_watchnewnode = threading.Thread(target=self._watchnewnode)
        self.thread_watchnewnode.start()
        # wait for all nodes joins
        # while(True):
        for i in range(60):
            allin = True
            for node in self.allnodes:
                if node not in self.runnodes:
                    allin = False
                    break
            if allin:
                logger.info("all nodes necessary joins ...")
                break
            time.sleep(1)
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
            etcd_runip = []
            for node in runlist:
                nodeip = node['key'].rsplit('/',1)[1]
                if node['value']=='waiting':
                    #   waiting state can be deleted, there is no use to let master check
                    # this state because worker will change it and master will not change it now.
                    # it is only preserved for compatible.
                    logger.info ("%s want to joins, call it to init first" % nodeip)
                elif node['value']=='work':
                    logger.info ("new node %s joins" % nodeip)
                    etcd_runip.append(nodeip)
                    # setup GRE tunnels for new nodes
                    '''if self.addr == nodeip:
                        logger.debug ("worker start on master node. not need to setup GRE")
                    else:
                        logger.debug ("setup GRE for %s" % nodeip)
                        if netcontrol.gre_exists('docklet-br', nodeip):
                            logger.debug("GRE for %s already exists, reuse it" % nodeip)
                        else:
                            netcontrol.setup_gre('docklet-br', nodeip)'''
                    self.etcd.setkey("machines/runnodes/"+nodeip, "ok")
                    if nodeip not in self.runnodes:
                        self.runnodes.append(nodeip)
                        # node not in all node list is a new node.
                        if nodeip not in self.allnodes:
                            self.allnodes.append(nodeip)
                            self.etcd.setkey("machines/allnodes/"+nodeip, "ok")
                        logger.debug ("all nodes are: %s" % self.allnodes)
                        logger.debug ("run nodes are: %s" % self.runnodes)
                elif node['value'] == 'ok':
                    etcd_runip.append(nodeip)
            new_runnodes = []
            for nodeip in self.runnodes:
                if nodeip not in etcd_runip:
                    logger.info ("Worker %s is stopped, remove %s:%s from rpc client list" %
                        (nodeip, nodeip, self.workerport))
                    #print(self.runnodes)
                    #print(etcd_runip)
                    #print(self.rpcs)
            self.runnodes = etcd_runip

    # get all run nodes' IP addr
    def get_nodeips(self):
        return self.runnodes


    def get_allnodes(self):
        return self.allnodes

    def ip_to_rpc(self,ip):
        return xmlrpc.client.ServerProxy("http://%s:%s" % (ip, env.getenv("WORKER_PORT")))
