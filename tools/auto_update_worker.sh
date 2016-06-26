echo "hello world!"
WORKER=$2/bin/docklet-worker
$WORKER stop
echo `$WORKER status`
