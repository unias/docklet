WORKER=$1/bin/docklet-worker
$WORKER stop
$WORKER status
cd $1
git pull origin master:master
$WORKER start
$WORKER status
