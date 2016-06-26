#!/bin/bash

bindir=${0%/*}
# $bindir maybe like /opt/docklet/src/../sbin
# use command below to make $bindir in normal absolute path
DOCKLET_BIN=$(cd $bindir; pwd)
DOCKLET_HOME=${DOCKLET_BIN%/*}
DOCKLET_CONF=$DOCKLET_HOME/conf
GIT_ADDRESS=$2
WORKER_DIR=$3
do_update () {
    source $DOCKLET_CONF/docklet.conf
    arr=(${WORKER_ADDRESSES/ / })
    echo "" > $DOCKLET_HOME/tools/update_output.txt
    echo "$WORKER_DIR"
    for i in ${arr[@]}  
    do  
        echo $i >> $DOCKLET_HOME/tools/update_output.txt
        ssh root@$i "${WORKER_DIR}/tools/auto_update_worker.sh $GIT_ADDRESS $WORKER_DIR" >> $DOCKLET_HOME/tools/update_output.txt
        exit
    done  
}

case $1 in
   # update)
    #    do_update
     #   ;;
    *)
        do_update
       # ;;
       #echo "Parameter error, usage: <scipt_name> update <new_code_address> <working_directory_of_worker>" 
        ;;
esac
exit 0
