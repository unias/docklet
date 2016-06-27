#!/bin/sh

## WARNING
## This sript is just for my own convenience . my image is
## based on Ubuntu xenial. I did not test it for other distros.
## Therefore this script may not work for your basefs image.
##


if [ "$1" != "-y" ] ; then 
    echo "This script will update your basefs. backup it first."
    echo "then run:  $0 -y"
    exit 1
fi 


# READ docklet.conf

FS_PREFIX=/opt/docklet

BASEFS=$FS_PREFIX/local/basefs

CONF=../conf/docklet.conf

echo "Reading $CONF"

if [ -f $CONF ] ; then
    . $CONF
    BASEFS=$FS_PREFIX/local/basefs
    echo "$CONF exit, basefs=$BASEFS"
else
    echo "$CONF not exist, default basefs=$BASEFS" 
fi

if [ ! -d $BASEFS ] ; then
    echo "Checking $BASEFS: not exist, FAIL"
    exit 1
else
    echo "Checking $BASEFS: exist. "
fi

echo "[*] Copying start_jupyter.sh to $BASEFS/home/jupyter"

mkdir -p $BASEFS/home/jupyter

cp start_jupyter.sh $BASEFS/home/jupyter

echo ""

echo "[*] Changing $BASEFS/etc/network/interfaces using static"

echo "Original network/interfaces is"

cat $BASEFS/etc/network/interfaces | sed 's/^/OLD    /'

sed -i -- 's/dhcp/static/g' $BASEFS/etc/network/interfaces 

# setting resolv.conf, use your own resolv.conf for your image
echo "[*] Setting $BASEFS/etc/resolv.conf"
cp resolv.conf $BASEFS/etc/resolvconf/resolv.conf.d/base

echo "[*] Masking console-getty.service"
chroot $BASEFS systemctl mask console-getty.service

echo "[*] Masking system-journald.service"
chroot $BASEFS systemctl mask systemd-journald.service

echo "[*] Masking system-logind.service"
chroot $BASEFS systemctl mask systemd-logind.service

echo "[*] Masking dbus.service"
chroot $BASEFS systemctl mask dbus.service

echo "[*] Disabling apache2 service(if installed)"
if [ -d $BASEFS/etc/apache2 ] ; then
chroot $BASEFS update-rc.d apache2 disable
fi

echo "[*] Disabling ondemand service(if installed)"
chroot $BASEFS update-rc.d ondemand disable

echo "[*] Disabling dbus service(if installed)"
chroot $BASEFS update-rc.d dbus disable

echo "[*] Disabling mysql service(if installed)"
if [ -d $BASEFS/etc/mysql ] ; then
chroot $BASEFS update-rc.d mysql disable
fi

echo "[*] Disabling nginx service(if installed)"
if [ -d $BASEFS/etc/nginx ] ; then
chroot $BASEFS update-rc.d nginx disable
fi

echo "[*] Setting worker_processes of nginx to 1(if installed)"
[ -f $BASEFS/etc/nginx/nginx.conf ] && sed -i -- 's/worker_processes\ auto/worker_processes\ 1/g' $BASEFS/etc/nginx/nginx.conf 

echo "[*] Deleting default /etc/nginx/sites-enabled/default"
rm -f  $BASEFS/etc/nginx/sites-enabled/default

echo "[*] Copying vimrc.local to $BASEFS/etc/vim/"
cp vimrc.local $BASEFS/etc/vim

echo "[*] Copying pip.conf to $BASEFS/root/.pip/"
mkdir -p $BASEFS/root/.pip/
cp pip.conf $BASEFS/root/.pip

echo "[*] Copying npmrc to $BASEFS/root/.npmrc"
cp npmrc $BASEFS/root/.npmrc

echo "[*] Copying DOCKLET_NOTES.txt to $BASEFS/root/DOCKLET_NOTES.txt"
cp DOCKLET_NOTES.txt $BASEFS/root/

echo "[*] Updating USER/.ssh/config to disable StrictHostKeyChecking"
for f in $FS_PREFIX/global/users/* ; do 
    cat <<EOF > $f/ssh/config
Host *
    StrictHostKeyChecking no
    UserKnownHostsFile=/dev/null
EOF
done

echo "[*] Generating $BASEFS/home/spark/sbin/dl_{start|stop}_spark.sh for Spark"
if [ -d $BASEFS/home/spark/sbin ] ; then
    cp dl_*_spark.sh $BASEFS/home/spark/sbin
fi

echo "[*] Generating $BASEFS/root/{R|python}_demo.ipynb"
if [ -d $BASEFS/root/ ] ; then
    cp R_demo.ipynb python_demo.ipynb $BASEFS/root/
fi
