#!/bin/bash

bindir=${0%/*}
# $bindir maybe like /opt/docklet/src/../sbin
# use command below to make $bindir in normal absolute path
DOCKLET_BIN=$(cd $bindir; pwd)
DOCKLET_HOME=${DOCKLET_BIN%/*}
DOCKLET_CONF=$DOCKLET_HOME/conf
FS_PREFIX=/opt/docklet
WORKER_DIR=$2
do_update () {
    source $DOCKLET_CONF/docklet.conf
    echo "" > $DOCKLET_HOME/tools/update_output.txt
    $DOCKLET_HOME/bin/docklet-master stop >> $DOCKLET_HOME/tools/update_output.txt
    date '+%Y-%m-%d %T INFO' | tee -a $FS_PREFIX/local/log/docklet-master.log $DOCKLET_HOME/tools/update_output.txt > /dev/null
    git pull origin master:master 2>&1 | tee -a $FS_PREFIX/local/log/docklet-master.log $DOCKLET_HOME/tools/update_output.txt > /dev/null
    $DOCKLET_HOME/bin/docklet-master init >> $DOCKLET_HOME/tools/update_output.txt
    date '+%Y-%m-%d %T INFO' | tee -a $FS_PREFIX/local/log/docklet-master.log $DOCKLET_HOME/tools/update_output.txt > /dev/null
    $DOCKLET_HOME/bin/docklet-master status | tee -a $FS_PREFIX/local/log/docklet-master.log $DOCKLET_HOME/tools/update_output.txt > /dev/null
    $DOCKLET_HOME/bin/docklet-worker stop >> $DOCKLET_HOME/tools/update_output.txt
    if [ $LOCAL_WORKER == True ]
    then
        date '+%Y-%m-%d %T INFO' | tee -a $FS_PREFIX/local/log/docklet-master.log $DOCKLET_HOME/tools/update_output.txt > /dev/null
        $DOCKLET_HOME/bin/docklet-worker start | tee -a $FS_PREFIX/local/log/docklet-master.log $DOCKLET_HOME/tools/update_output.txt > /dev/null
    fi
    
    arr=(${WORKER_ADDRESSES//,/ })  
    for i in ${arr[@]}  
    do
        date '+%Y-%m-%d %T INFO worker at ' | tee -a $FS_PREFIX/local/log/docklet-master.log $DOCKLET_HOME/tools/update_output.txt > /dev/null
        echo -n "$i" | tee -a $FS_PREFIX/local/log/docklet-master.log $DOCKLET_HOME/tools/update_output.txt > /dev/null
        ssh root@$i "${WORKER_DIR}/tools/auto_update_worker.sh $WORKER_DIR" | tee -a $FS_PREFIX/local/log/docklet-master.log $DOCKLET_HOME/tools/update_output.txt > /dev/null
    done  
    mv $DOCKLET_HOME/tools/update_output.txt $DOCKLET_HOME/web/static/update_log.txt
}

case $1 in
    *)
        do_update
        ;;
esac
exit 0
