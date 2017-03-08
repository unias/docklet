#!/bin/bash

# more details for https://coreos.com/etcd/docs/latest

which etcd &>/dev/null || { echo "etcd not installed, please install etcd first" && exit 1; }

if 0; then#[ $# -eq 0 ] ; then
    echo "Usage: `basename $0` ip1 ip2 ip3"
    echo "    ip1 ip2 ip3 are the ip address of node etcd_1 etcd_2 etcd_3"
    exit 1
fi

index=1
# while [ $# -gt 0 ] ; do
    h="etcd_$index" 
#    if [ $index -eq 1 ] ; then
        CLUSTER="$h=http://104.236.59.112:2380"
#    else
#        CLUSTER="$CLUSTER,$h=http://$1:2380"
#    fi 
#    index=$(($index+1))
#    shift
#done

# -initial-advertise-peer-urls  :  tell others what peer urls of me
# -listen-peer-urls             :  what peer urls of me

# -listen-client-urls           :  what client urls to listen
# -advertise-client-urls        :  tell others what client urls to listen of me

# -initial-cluster-state        :  new means join a new cluster; existing means join an existing cluster
#                               :  new not means clear 

etcd_1=104.236.59.112
etcd --name etcd_1 \
     --initial-advertise-peer-urls http://$etcd_1:2380 \
     --listen-peer-urls http://$etcd_1:2380 \
     --listen-client-urls http://$etcd_1:2379 \
     --advertise-client-urls http://$etcd_1:2379 \
     --initial-cluster-token etcd-cluster \
     --initial-cluster $CLUSTER \
     --initial-cluster-state new 
