#!/bin/sh

MASTER_IP=0.0.0.0
NGINX_PORT=8080
PROXY_PORT=8000
WEB_PORT=8888
NGINX_CONF=/etc/nginx

toolsdir=${0%/*}
DOCKLET_TOOLS=$(cd $toolsdir; pwd)
DOCKLET_HOME=${DOCKLET_TOOLS%/*}
DOCKLET_CONF=$DOCKLET_HOME/conf

. $DOCKLET_CONF/docklet.conf

NGINX_CONF=${NGINX_CONF}/sites-enabled

echo "copy nginx_docklet.conf to nginx config path..."
cp $DOCKLET_CONF/nginx_docklet.conf ${NGINX_CONF}/
sed -i "s/%MASTER_IP/${MASTER_IP}/g" ${NGINX_CONF}/nginx_docklet.conf
sed -i "s/%NGINX_PORT/${NGINX_PORT}/g" ${NGINX_CONF}/nginx_docklet.conf

sed -i "s/%PROXY_PORT/${PROXY_PORT}/g" ${NGINX_CONF}/nginx_docklet.conf
sed -i "s/%WEB_PORT/${WEB_PORT}/g" ${NGINX_CONF}/nginx_docklet.conf

if [ "${NGINX_PORT}" != "80" ] && [ "${NGINX_PORT}" != "443" ]
then
  sed -i "s/\$host/\$host:\$server_port/g" ${NGINX_CONF}/nginx_docklet.conf
fi



echo "restart nginx..."
service nginx restart
