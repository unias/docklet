# Docklet

- http://unias.github.io/docklet
- http://docklet.unias.org

## Intro

Docklet is a cloud operating system for mini-datacener. Its goal is to
help multi-user share cluster resources effectively.  In Docklet, every
user has their own private **virtual cluster (vcluster)**, which
consists of a number of virtual Linux container nodes distributed over
the physical cluster. Each vcluster is separated from others and can be
operated like a real physical cluster. Therefore, most applications,
especially those requiring a cluster environment, can run in vcluster
seamlessly.

Users manage and use their vcluster all through web. The only client
tool needed is a modern web browser supporting HTML5, like Safari,
Firefox, or Chrome.  The integrated *jupyter notebook* provides a web
**Workspace**. In the Workspace, users can code, debug, test,
and runn their programs, even visualize the outputs online.
Therefore, it is ideal for data analysis and processing.

Docklet creates virtual nodes from a base image. Admins can
pre-install development tools and frameworks according to their
interests. The users are also free to install their specific software
in their vcluster.

Docklet only need **one** public IP address. The vclusters are
configured to use private IP address range, e.g., 172.16.0.0/16,
192.168.0.0/16, 10.0.0.0/8. A proxy is setup to help
users visit their vclusters behind the firewall/gateway.

The Docklet system runtime consists of four components:

- distributed file system server
- etcd server
- docklet master
- docklet worker

## Install

Currently the Docklet system is recommend to run in Unbuntu 15.10+.

Ensure that python3.5 is the default python3 version.

Clone Docklet from github

```
git clone  https://github.com/unias/docklet.git
```

Run **prepare.sh** from console to install depended packages and
generate necessary configurations.

A *root* users will be created for managing the Docklet system. The
password is recorded in `FS_PREFIX/local/generated_password.txt` .

## Config ##

The main configuration file of docklet is conf/docklet.conf. Most
default setting works for a single host environment.

First copy docklet.conf.template to get docklet.conf.

Pay attention to the following settings:

- NETWORK_DEVICE : the network interface to use.
- ETCD : the etcd server address. For distributed multi hosts
  environment, it should be one of the ETCD public server address.
  For single host environment, the default value should be OK.
- STORAGE : using disk or file to storage persistent data, for
  single host, file is convenient.
- FS_PREFIX: the working dir of docklet runtime. default is
  /opt/docklet.
- CLUSTER_NET: the vcluster network ip address range, default is
  172.16.0.1/16. This network range should all be allocated to  and
  managed by docklet.
- PROXY_PORT : the listening port of configurable-http-proxy. It proxy
  connections from exteral public network to internal private
  container networks.
- PORTAL_URL : the portal of the system. Users access the system
  by visiting this address. If the system is behind a firewall, then
  a reverse proxy should be setup. Default is MASTER_IP:NGINX_PORT.
- NGINX_PORT : the access port of the public portal. User use this
  port to visit docklet system.
- DISTRIBUTED_GATEWAY : whether the users' gateways are distributed
  or not. Both master and worker must be set by same value.
- PUBLIC_IP : publick ip of this machine. If DISTRIBUTED_GATEWAY is True,
  users' gateways can be setup on this machine. Users can visit this
  machine by the public ip. default: IP of NETWORK_DEVICE.

## Start ##

### distributed file system ###

For multi hosts distributed environment, a distributed file system is
needed to store global data. Currently, glusterfs has been tested.
Lets presume the file system server export filesystem as nfs
**fileserver:/pub** :

In each physical host to run docklet, mount **fileserver:/pub** to
**FS_PEFIX/global** .

For single host environment, nothing to do.

### etcd ###

For single host environment, start **tools/etcd-one-node.sh** . Some recent
Ubuntu releases have included **etcd** in the repository, just `apt-get
install etcd`, and it need not to start etcd manually. For others, you
should install etcd manually.

For multi hosts distributed environment, **must** start
**dep/etcd-multi-nodes.sh** in each etcd server hosts. This scripts
requires users providing the etcd server address as parameters.

### master ###

First, select a server with 2 network interface card, one having a
public IP address/url, e.g., docklet.info; the other having a private IP
address, e.g., 172.16.0.1. This server will be the master.

If it is the first time you start docklet, run `bin/docklet-master init`
to init and start docklet master. Otherwise, run  `bin/docklet-master start`,
which will start master in recovery mode in background using
conf/docklet.conf. (Note: if docklet will run in the distributed gateway mode
and recovery mode, please start the workers first.)

You can check the daemon status by running `bin/docklet-master status`

The master logs are in **FS_PREFIX/local/log/docklet-master.log** and
**docklet-web.log**.

### worker ###

Worker needs a basefs image to create containers.

You can create such an image with `lxc-create -n test -t download`,
then copy the rootfs to **FS_PREFIX/local**, and rename `rootfs`
to `basefs`.

Note the `jupyerhub` package must be installed for this image.  And the
start script `tools/start_jupyter.sh` should be placed at
`basefs/home/jupyter`.

You can check and run `tools/update-basefs.sh` to update basefs.

Run `bin/docklet-worker start`, will start worker in background.

You can check the daemon status by running `bin/docklet-worker status`.

The log is in **FS_PREFIX/local/log/docklet-worker.log**.

Currently, the worker must be run after the master has been started.

## Usage ##

Open a browser, visiting the address specified by PORTAL_URL ,
e.g., ` http://docklet.info/ `

That is it.

# Contribute #

Contributions are welcome. Please check [devguide](https://github.com/unias/docklet/blob/master/doc/devguide/devguide.md).
