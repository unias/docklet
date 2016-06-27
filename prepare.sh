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

# install packages that docklet needs (in ubuntu)
# some packages' name maybe different in debian
apt-get install -y cgmanager lxc lxcfs lxc-templates lvm2 bridge-utils curl exim4 openssh-server openvswitch-switch 
apt-get install -y python3 python3-netifaces python3-flask python3-flask-sqlalchemy python3-pampy
apt-get install -y python3-psutil
apt-get install -y python3-lxc
apt-get install -y python3-requests python3-suds
apt-get install -y nodejs nodejs-legacy npm
apt-get install -y etcd

# check and install configurable-http-proxy
which configurable-http-proxy &>/dev/null || npm install -g configurable-http-proxy
which configurable-http-proxy &>/dev/null || { echo "Error: install configurable-http-proxy failed, you should try again" && exit 1; }

echo ""
[[ -f conf/docklet.conf ]] || { echo "Generating docklet.conf from template" && cp conf/docklet.conf.template conf/docklet.conf; }
[[ -f web/templates/home.html ]] || { echo "Generating HomePage from home.template" && cp web/templates/home.template web/templates/home.html; }

echo ""
echo "All preparation installations are done."
echo "****************************************"
echo "* Please Read Lines Below Before Start *"
echo "****************************************"
echo ""

echo "Before staring : you need a basefs image. "
echo "basefs images are provided at: "
echo "  http://docklet.unias.org/download"
echo "please download it to FS_PREFIX/local and then extract it. (defalut FS_PRERIX is /opt/docklet)"
echo "you will get a dicectory structure like"
echo "  /opt/docklet/local/basefs/etc "
echo "  /opt/docklet/local/basefs/bin "
echo "  /opt/docklet/local/basefs/..."
echo "you may want to custom home page of docklet. Please modify web/templates/home.html"

echo "Next, make sure exim4 can deliver mail out. To enable, run:"
echo "dpkg-reconfigure exim4-config"
echo "select internet site"

echo ""


echo "Then start docklet as described in README.md"

