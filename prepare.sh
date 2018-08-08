#!/bin/bash

##################################################
#                before-start.sh
# when you first use docklet, you should run this script to
# check and prepare the environment
# *important* : you need run this script again and again till success
##################################################

if [[ "`whoami`" != "root" ]]; then
	echo "FAILED: Require root previledge !" > /dev/stderr
	exit 1
fi

# install packages that docklet needs (in ubuntu)
# some packages' name maybe different in debian
apt-get install -y cgmanager lxc lxcfs lxc-templates lvm2 bridge-utils curl exim4 openssh-server openvswitch-switch
apt-get install -y python3 python3-netifaces python3-flask python3-flask-sqlalchemy python3-pampy python3-httplib2 python3-pip
apt-get install -y python3-psutil python3-flask-migrate python3-paramiko
apt-get install -y python3-lxc
apt-get install -y python3-requests python3-suds
apt-get install -y nodejs nodejs-legacy npm
apt-get install -y etcd
apt-get install -y glusterfs-client attr
apt-get install -y nginx
pip3 install grpcio grpcio-tools googleapis-common-protos

#add ip forward
echo "net.ipv4.ip_forward=1" >>/etc/sysctl.conf
sysctl -p

# check cgroup control
which cgm &> /dev/null || { echo "FAILED : cgmanager is required, please install cgmanager" && exit 1; }
cpucontrol=$(cgm listkeys cpu)
[[ -z $(echo $cpucontrol | grep cfs_quota_us) ]] && echo "FAILED : cpu.cfs_quota_us of cgroup is not supported, you may need to recompile kernel" && exit 1
memcontrol=$(cgm listkeys memory)
if [[ -z $(echo $memcontrol | grep limit_in_bytes) ]]; then
	echo "FAILED : memory.limit_in_bytes of cgroup is not supported"
	echo "Try : "
	echo -e "  echo 'GRUB_CMDLINE_LINUX=\"cgroup_enable=memory swapaccount=1\"' >> /etc/default/grub; update-grub; reboot" > /dev/stderr
	echo "Info : if not success, you may need to recompile kernel"
	exit 1
fi


# check and install configurable-http-proxy
which configurable-http-proxy &>/dev/null || { npm config set registry https://registry.npm.taobao.org && npm install -g configurable-http-proxy; }
which configurable-http-proxy &>/dev/null || { echo "Error: install configurable-http-proxy failed, you should try again" && exit 1; }

echo ""
[[ -f conf/docklet.conf ]] || { echo "Generating docklet.conf from template" && cp conf/docklet.conf.template conf/docklet.conf; }
[[ -f web/templates/home.html ]] || { echo "Generating HomePage from home.template" && cp web/templates/home.template web/templates/home.html; }

mkdir -p /opt/docklet/global
mkdir -p /opt/docklet/local/

echo "directory /opt/docklet have been created"

if [[ ! -d /opt/docklet/local/basefs && ! $1 = "withoutfs" ]]; then
	mkdir -p /opt/docklet/local/basefs
	echo "Generating basefs"
	wget -P /opt/docklet/local http://iwork.pku.edu.cn:1616/basefs-0.11.tar.bz2 && tar xvf /opt/docklet/local/basefs-0.11.tar.bz2 -C /opt/docklet/local/ > /dev/null
	[ $? != "0" ] && echo "Generate basefs failed, please download it from http://unias.github.io/docklet/download to FS_PREFIX/local and then extract it using root. (defalut FS_PRERIX is /opt/docklet)"
fi

echo "Some packagefs can be downloaded from http://unias.github.io/docklet.download"
echo "you can download the packagefs and extract it to FS_PREFIX/local using root. (default FS_PREFIX is /opt/docklet"

echo ""
echo "All preparation installations are done."
echo "****************************************"
echo "* Please Read Lines Below Before Start *"
echo "****************************************"
echo ""

echo "you may want to custom home page of docklet. Please modify web/templates/home.html"

echo "Next, make sure exim4 can deliver mail out. To enable, run:"
echo "dpkg-reconfigure exim4-config"
echo "select internet site"

echo ""
echo "Then start docklet as described in README.md"
