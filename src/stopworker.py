#!/usr/bin/python3
import env,tools
config = env.getenv("CONFIG")
tools.loadenv(config)
import etcdlib, network

if __name__ == '__main__':
	etcdaddr = env.getenv("ETCD")
	clustername = env.getenv("CLUSTER_NAME")
	etcdclient = etcdlib.Client(etcdaddr, prefix = clustername)
	net_dev = env.getenv("NETWORK_DEVICE")
	ipaddr = network.getip(net_dev)
	etcdclient.deldir("machines/runnodes/"+ipaddr)