#!/bin/bash
bindir=${0%/*}
# $bindir maybe like /opt/docklet/src/../sbin
# use command below to make $bindir in normal absolute path
DOCKLET_BIN=$(cd $bindir; pwd)
DOCKLET_HOME=${DOCKLET_BIN%/*}echo `$DOCKLET_HOME/bin/docklet-master stop` >> $DOCKLET_HOME/tools/update_output.txt
echo `git pull origin master:master` >> $DOCKLET_HOME/tools/update_output.txt
echo `$DOCKLET_HOME/bin/docklet-master init` >> $DOCKLET_HOME/tools/update_output.txt
echo `$DOCKLET_HOME/bin/docklet-master status` >> $DOCKLET_HOME/tools/update_output.txt
