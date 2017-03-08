#!/bin/sh

# more details for https://coreos.com/etcd/docs/latest

#which etcd &>/dev/null || { echo "etcd not installed, please install etcd first" && exit 1; }
which etcd >/dev/null || { echo "etcd not installed, please install etcd first" && exit 1; }

etcd_1=104.236.59.112

if [ $# -gt 0 ] ; then
    etcd_1=$1
fi


# -initial-advertise-peer-urls  :  tell others what peer urls of me
# -listen-peer-urls             :  what peer urls of me

# -listen-client-urls           :  what client urls to listen
# -advertise-client-urls        :  tell others what client urls to listen of me

# -initial-cluster-state        :  new means join a new cluster; existing means a new node join an existing cluster
#                               :  new not means clear, old data is still alive

depdir=${0%/*}
tempdir=/opt/docklet/local
[ ! -d $tempdir/log ] && mkdir -p $tempdir/log
[ ! -d $tempdir/run ] && mkdir -p $tempdir/run

echo "starting etcd on $etcd_1"

#stdbuf -o0 -e0 $tempdir/etcd --name etcd_1 \
etcd --name etcd_1 \
	 --data-dir $tempdir/etcd_data \
     --initial-advertise-peer-urls http://$etcd_1:2380 \
     --listen-peer-urls http://$etcd_1:2380 \
     --listen-client-urls http://$etcd_1:2379 \
     --advertise-client-urls http://$etcd_1:2379 \
     --initial-cluster-token etcd_cluster \
     --initial-cluster etcd_1=http://$etcd_1:2380 \
     --initial-cluster-state new > $tempdir/log/etcd.log 2>&1 &

etcdpid=$!
echo "etcd start with pid: $etcdpid and log:$tempdir/log/etcd.log"
echo $etcdpid > $tempdir/run/etcd.pid

