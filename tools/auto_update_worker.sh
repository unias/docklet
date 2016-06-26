WORKER=$2/bin/docklet-worker
$WORKER stop
$WORKER status
cd $2
git pull origin master:master
$WORKER start
