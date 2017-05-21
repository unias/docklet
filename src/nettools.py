#!/usr/bin/python3

import subprocess

class ipcontrol(object):
    @staticmethod
    def parse(cmdout):
        links = {}
        thislink = None
        for line in cmdout.splitlines():
            # empty line
            if len(line)==0:
                continue
            # Level 1 : first line of one link
            if line[0] != ' ':
                blocks = line.split()
                thislink = blocks[1].strip(':')
                links[thislink] = {}
                links[thislink]['state'] = blocks[blocks.index('state')+1] if 'state' in blocks else 'UNKNOWN'
            # Level 2 : line with 4 spaces
            elif line[4] != ' ':
                blocks = line.split()
                if blocks[0] == 'inet':
                    if 'inet' not in links[thislink]:
                        links[thislink]['inet'] = []
                    links[thislink]['inet'].append(blocks[1])
                # we just need inet (IPv4)
                else:
                    pass
            # Level 3 or more : no need for us
            else:
                pass
        return links

    @staticmethod
    def list_links():
        try:
            ret = subprocess.run(['ip', 'link', 'show'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            links = ipcontrol.parse(ret.stdout.decode('utf-8'))
            return [True, list(links.keys())]
        except subprocess.CalledProcessError as suberror:
            return [False, "list links failed : %s" % suberror.stdout.decode('utf-8')]

    @staticmethod
    def link_exist(linkname):
        try:
            subprocess.run(['ip', 'link', 'show', 'dev', str(linkname)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    @staticmethod
    def link_info(linkname):
        try:
            ret = subprocess.run(['ip', 'address', 'show', 'dev', str(linkname)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            return [True, ipcontrol.parse(ret.stdout.decode('utf-8'))[str(linkname)]]
        except subprocess.CalledProcessError as suberror:
            return [False, "get link info failed : %s" % suberror.stdout.decode('utf-8')]

    @staticmethod
    def link_state(linkname):
        try:
            ret = subprocess.run(['ip', 'link', 'show', 'dev', str(linkname)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            return [True, ipcontrol.parse(ret.stdout.decode('utf-8'))[str(linkname)]['state']]
        except subprocess.CalledProcessError as suberror:
            return [False, "get link state failed : %s" % suberror.stdout.decode('utf-8')]

    @staticmethod
    def link_ips(linkname):
        [status, info] = ipcontrol.link_info(str(linkname))
        if status:
            if 'inet' not in info:
                return [True, []]
            else:
                return [True, info['inet']]
        else:
            return [False, info]

    @staticmethod
    def up_link(linkname):
        try:
            subprocess.run(['ip', 'link', 'set', 'dev', str(linkname), 'up'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            return [True, str(linkname)]
        except subprocess.CalledProcessError as suberror:
            return [False, "set link up failed : %s" % suberror.stdout.decode('utf-8')]

    @staticmethod
    def down_link(linkname):
        try:
            subprocess.run(['ip', 'link', 'set', 'dev', str(linkname), 'down'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            return [True, str(linkname)]
        except subprocess.CalledProcessError as suberror:
            return [False, "set link down failed : %s" % suberror.stdout.decode('utf-8')]

    @staticmethod
    def add_addr(linkname, address):
        try:
            subprocess.run(['ip', 'address', 'add', address, 'dev', str(linkname)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            return [True, str(linkname)]
        except subprocess.CalledProcessError as suberror:
            return [False, "add address failed : %s" % suberror.stdout.decode('utf-8')]

    @staticmethod
    def del_addr(linkname, address):
        try:
            subprocess.run(['ip', 'address', 'del', address, 'dev', str(linkname)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            return [True, str(linkname)]
        except subprocess.CalledProcessError as suberror:
            return [False, "delete address failed : %s" % suberror.stdout.decode('utf-8')]


# ovs-vsctl list-br
# ovs-vsctl br-exists <Bridge>
# ovs-vsctl add-br <Bridge>
# ovs-vsctl del-br <Bridge>
# ovs-vsctl list-ports <Bridge>
# ovs-vsctl del-port <Bridge> <Port>
# ovs-vsctl add-port <Bridge> <Port> -- set interface <Port> type=gre options:remote_ip=<RemoteIP>
# ovs-vsctl add-port <Bridge> <Port> tag=<ID> -- set interface <Port> type=internal
# ovs-vsctl port-to-br <Port>
# ovs-vsctl set Port <Port> tag=<ID>
# ovs-vsctl clear Port <Port> tag

class ovscontrol(object):
    @staticmethod
    def list_bridges():
        try:
            ret = subprocess.run(['ovs-vsctl', 'list-br'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            return [True, ret.stdout.decode('utf-8').split()]
        except subprocess.CalledProcessError as suberror:
            return [False, "list bridges failed : %s" % suberror.stdout.decode('utf-8')]

    @staticmethod
    def bridge_exist(bridge):
        try:
            subprocess.run(['ovs-vsctl', 'br-exists', str(bridge)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    @staticmethod
    def port_tobridge(port):
        try:
            ret = subprocess.run(['ovs-vsctl', 'port-to-br', str(port)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            return [True, ret.stdout.decode('utf-8').strip()]
        except subprocess.CalledProcessError as suberror:
            return [False, suberror.stdout.decode('utf-8')]

    @staticmethod
    def port_exists(port):
        return ovscontrol.port_tobridge(port)[0]

    @staticmethod
    def add_bridge(bridge):
        try:
            subprocess.run(['ovs-vsctl', '--may-exist', 'add-br', str(bridge)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            return [True, str(bridge)]
        except subprocess.CalledProcessError as suberror:
            return [False, "add bridge failed : %s" % suberror.stdout.decode('utf-8')]

    @staticmethod
    def del_bridge(bridge):
        try:
            subprocess.run(['ovs-vsctl', 'del-br', str(bridge)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            return [True, str(bridge)]
        except subprocess.CalledProcessError as suberror:
            return [False, "del bridge failed : %s" % suberror.stdout.decode('utf-8')]

    @staticmethod
    def list_ports(bridge):
        try:
            ret = subprocess.run(['ovs-vsctl', 'list-ports', str(bridge)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            return [True, ret.stdout.decode('utf-8').split()]
        except subprocess.CalledProcessError as suberror:
            return [False, "list ports failed : %s" % suberror.stdout.decode('utf-8')]

    @staticmethod
    def del_port(bridge, port):
        try:
            subprocess.run(['ovs-vsctl', 'del-port', str(bridge), str(port)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            return [True, str(port)]
        except subprocess.CalledProcessError as suberror:
            return [False, "delete port failed : %s" % suberror.stdout.decode('utf-8')]

    @staticmethod
    def add_port(bridge, port):
        try:
            subprocess.run(['ovs-vsctl', '--may-exist', 'add-port', str(bridge), str(port)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            return [True, str(port)]
        except subprocess.CalledProcessError as suberror:
            return [False, "add port failed : %s" % suberror.stdout.decode('utf-8')]

    @staticmethod
    def add_port_internal(bridge, port):
        try:
            subprocess.run(['ovs-vsctl', 'add-port', str(bridge), str(port), '--', 'set', 'interface', str(port), 'type=internal'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            return [True, str(port)]
        except subprocess.CalledProcessError as suberror:
            return [False, "add port failed : %s" % suberror.stdout.decode('utf-8')]

    @staticmethod
    def add_port_internal_withtag(bridge, port, tag):
        try:
            subprocess.run(['ovs-vsctl', 'add-port', str(bridge), str(port), 'tag='+str(tag), '--', 'set', 'interface', str(port), 'type=internal'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            return [True, str(port)]
        except subprocess.CalledProcessError as suberror:
            return [False, "add port failed : %s" % suberror.stdout.decode('utf-8')]

    @staticmethod
    def add_port_gre(bridge, port, remote):
        try:
            subprocess.run(['ovs-vsctl', 'add-port', str(bridge), str(port), '--', 'set', 'interface', str(port), 'type=gre', 'options:remote_ip='+str(remote)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            return [True, str(port)]
        except subprocess.CalledProcessError as suberror:
            return [False, "add port failed : %s" % suberror.stdout.decode('utf-8')]

    @staticmethod
    def add_port_gre_withkey(bridge, port, remote, key):
        try:
            subprocess.run(['ovs-vsctl', '--may-exist', 'add-port', str(bridge), str(port), '--', 'set', 'interface', str(port), 'type=gre', 'options:remote_ip='+str(remote), 'options:key='+str(key)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            return [True, str(port)]
        except subprocess.CalledProcessError as suberror:
            return [False, "add port failed : %s" % suberror.stdout.decode('utf-8')]

    @staticmethod
    def set_port_tag(port, tag):
        try:
            subprocess.run(['ovs-vsctl', 'set', 'Port', str(port), 'tag='+str(tag)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            return [True, str(port)]
        except subprocess.CalledProcessError as suberror:
            return [False, "set port tag failed : %s" % suberror.stdout.decode('utf-8')]


class netcontrol(object):
    @staticmethod
    def bridge_exists(bridge):
        return ovscontrol.bridge_exist(bridge)

    @staticmethod
    def del_bridge(bridge):
        return ovscontrol.del_bridge(bridge)

    @staticmethod
    def new_bridge(bridge):
        return ovscontrol.add_bridge(bridge)

    @staticmethod
    def gre_exists(bridge, remote):
        # port is unique, bridge is not necessary
        return ovscontrol.port_exists('gre-'+str(remote))

    @staticmethod
    def setup_gre(bridge, remote):
        return ovscontrol.add_port_gre(bridge, 'gre-'+str(remote), remote)

    @staticmethod
    def gw_exists(bridge, gwport):
        return ovscontrol.port_exists(gwport)

    @staticmethod
    def setup_gw(bridge, gwport, addr):
        [status, result] = ovscontrol.add_port_internal(bridge, gwport)
        if not status:
            return [status, result]
        [status, result] = ipcontrol.add_addr(gwport, addr)
        if not status:
            return [status, result]
        return ipcontrol.up_link(gwport)

    @staticmethod
    def del_gw(bridge, gwport):
        return ovscontrol.del_port(bridge, gwport)

    @staticmethod
    def check_gw(bridge, gwport, uid, addr):
        ovscontrol.add_bridge(bridge)
        if not netcontrol.gw_exists(bridge, gwport):
            return netcontrol.setup_gw(bridge, gwport, addr)
        [status, info] = ipcontrol.link_info(gwport)
        if not status:
            return [False, "get gateway info failed"]
        if ('inet' not in info) or (addr not in info['inet']):
            ipcontrol.add_addr(gwport, addr)
        else:
            info['inet'].remove(addr)
            for otheraddr in info['inet']:
                ipcontrol.del_addr(gwport, otheraddr)
        if info['state'] == 'DOWN':
            ipcontrol.up_link(gwport)
        return [True, "check gateway port %s" % gwport]

    @staticmethod
    def recover_usernet(portname, uid, GatewayHost, isGatewayHost):
        ovscontrol.add_bridge("docklet-br-"+str(uid))
        [success, ports] = ovscontrol.list_ports("docklet-br-"+str(uid))
        if success:
            for port in ports:
                if port.startswith("gre"):
                    ovscontrol.del_port("docklet-br-"+str(uid),port)
        if not isGatewayHost:
            ovscontrol.add_port_gre_withkey("docklet-br-"+str(uid), "gre-"+str(uid)+"-"+GatewayHost, GatewayHost, str(uid))
        ovscontrol.add_port("docklet-br-"+str(uid), portname)
