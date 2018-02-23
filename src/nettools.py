#!/usr/bin/python3

import subprocess, env, threading
from log import logger

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

    @staticmethod
    def netns_add_addr(pid, ip, linkname = 'eth0'):
        try:
            subprocess.run(['ip', 'netns', 'exec', str(pid), 'ifconfig', str(linkname), str(ip), 'up'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            return [True, "netns %s add address succes : %s" % (pid, ip)]
        except subprocess.CalledProcessError as suberror:
            return [False, "netns %s add address failed : %s" % (pid, suberror.stdout.decode('utf-8'))]


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

    @staticmethod
    def set_port_input_qos(port, input_rate_limit):
        input_rate_limiting = int(input_rate_limit)*1000
        if input_rate_limiting == 0:
            return [True, str(port)]
        try:
            p = subprocess.run(['ovs-vsctl', 'create', 'qos', 'type=linux-htb', 'other_config:max-rate='+str(input_rate_limiting)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            subprocess.run(['ovs-vsctl', 'set', 'Port', str(port), 'qos='+p.stdout.decode('utf-8').rstrip()], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            return [True, str(port)]
        except subprocess.CalledProcessError as suberror:
            return [False, "set port input qos failed : %s" % suberror.stdout.decode('utf-8')]

    @staticmethod
    def del_port_input_qos(port):
        try:
            p = subprocess.run(['ovs-vsctl', 'get', 'port', str(port), 'qos'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            subprocess.run(['ovs-vsctl', 'clear', 'port', str(port), 'qos'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            subprocess.run(['ovs-vsctl', 'destroy', 'qos', p.stdout.decode('utf-8').rstrip()], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            return [True, str(port)]
        except subprocess.CalledProcessError as suberror:
            return [False, "del port input qos failed : %s" % suberror.stdout.decode('utf-8')]

    @staticmethod
    def set_port_output_qos(port, output_rate_limit):
        try:
            subprocess.run(['ovs-vsctl', 'set', 'interface', str(port), 'ingress_policing_rate='+str(output_rate_limit)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            subprocess.run(['ovs-vsctl', 'set', 'interface', str(port), 'ingress_policing_burst='+str(output_rate_limit)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            return [True, str(port)]
        except subprocess.CalledProcessError as suberror:
            return [False, "set port output qos failed : %s" % suberror.stdout.decode('utf-8')]

    @staticmethod
    def del_port_output_qos(port):
        try:
            subprocess.run(['ovs-vsctl', 'set', 'interface', str(port), 'ingress_policing_rate=0'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            subprocess.run(['ovs-vsctl', 'set', 'interface', str(port), 'ingress_policing_burst=0'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            return [True, str(port)]
        except subprocess.CalledProcessError as suberror:
            return [False, "del port output qos failed : %s" % suberror.stdout.decode('utf-8')]

    @staticmethod
    def destroy_all_qos():
        try:
            ret = subprocess.run(['ovs-vsctl', '--all', 'destroy', 'qos'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            return [True, 'succeed to destroying all qos.']
        except subprocess.CalledProcessError as suberror:
            return [False, "destroy all qos failed : %s" % suberror.stdout.decode('utf-8')]

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
    def setup_gw(bridge, gwport, addr, input_rate_limit, output_rate_limit):
        [status, result] = ovscontrol.add_port_internal(bridge, gwport)
        if not status:
            return [status, result]
        [status, result] = ipcontrol.add_addr(gwport, addr)
        if not status:
            return [status, result]
        [status, result] = ipcontrol.up_link(gwport)
        if not status:
            return [status, result]
        [status, result] = ovscontrol.set_port_input_qos(gwport, input_rate_limit)
        if not status:
            return [status, result]
        return ovscontrol.set_port_output_qos(gwport, output_rate_limit)

    @staticmethod
    def del_gw(bridge, gwport):
        [status, result] = ovscontrol.del_port_input_qos(gwport)
        if not status:
            return [status, result]
        [status, result] = ovscontrol.del_port_output_qos(gwport)
        if not status:
            return [status, result]
        return ovscontrol.del_port(bridge, gwport)

    @staticmethod
    def check_gw(bridge, gwport, uid, addr, input_rate_limit, output_rate_limit):
        ovscontrol.add_bridge(bridge)
        if not netcontrol.gw_exists(bridge, gwport):
            return netcontrol.setup_gw(bridge, gwport, addr, input_rate_limit, output_rate_limit)
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
        if not isGatewayHost:
            [success, ports] = ovscontrol.list_ports("docklet-br-"+str(uid))
            if success:
                for port in ports:
                    if port.startswith("gre") and (not port == ("gre-"+str(uid)+"-"+GatewayHost) ) :
                        ovscontrol.del_port("docklet-br-"+str(uid),port)
            ovscontrol.add_port_gre_withkey("docklet-br-"+str(uid), "gre-"+str(uid)+"-"+GatewayHost, GatewayHost, str(uid))
        ovscontrol.add_port("docklet-br-"+str(uid), portname)

    @staticmethod
    def update_user_network(username, pid, ip, gateway):
        [status, result] = ipcontrol.netns_add_addr(pid, ip)
        if not status:
            return [False, result]
        [status, route_result] = netcontrol.netns_add_route(pid, gateway)
        if not status:
            return [False, route_result]
        resutl = result + route_result
        return [True, result]

    @staticmethod
    def netns_add_route(pid, gateway):
        try:
            subprocess.run(['ip', 'netns', 'exec', str(pid), 'route', 'add', 'default', 'gw', str(gateway)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            return [True, "netns %s add route success : %s" % (pid, gateway)]
        except subprocess.CalledProcessError as suberror:
            return [False, "netns %s add route failed : %s" % (pid, suberror.stdout.decode('utf-8'))]

free_ports = [False]*65536
allocated_ports = {}
ports_lock = threading.Lock()

class portcontrol(object):

    @staticmethod
    def init_new():
        Free_Ports_str = env.getenv("ALLOCATED_PORTS")
        global free_ports
        #logger.info(Free_Ports_str)
        portsranges=Free_Ports_str.split(',')
        #logger.info(postranges)
        for portsrange in portsranges:
            portsrange=portsrange.strip().split('-')
            start = int(portsrange[0])
            end = int(portsrange[1])
            if end < start or end > 65535 or start < 1:
                return [False, "Illegal port ranges."]
            i = start
            #logger.info(str(start)+" "+str(end))
            while i <= end:
                free_ports[i] = True
                i += 1
        #logger.info(free_ports[10001])
        return [True,""]

    @staticmethod
    def init_recovery(Free_Ports_str):
        Free_Ports_str = env.getenv("ALLOCATED_PORTS")
        return [True,""]

    @staticmethod
    def acquire_port_mapping(container_name, container_ip, container_port, host_port=None):
        global free_ports
        global allocated_ports
        global ports_lock
        ports_lock.acquire()
        # if container_name in allocated_ports.keys():
        #     return [False, "This container already has a port mapping."]
        if container_name not in allocated_ports.keys():
            allocated_ports[container_name] = {}
        elif container_port in allocated_ports[container_name].keys():
            ports_lock.release()
            return [False, "This container port already has a port mapping."]
        if container_name == "" or container_ip == "" or container_port == "":
            ports_lock.release()
            return [False, "Node Name or Node IP or Node Port can't be null."]
        #print("acquire_port_mapping1")
        free_port = 1
        if host_port is not None:
            # recover from host_port
            free_port = int(host_port)
        else:
            # acquire new free port
            while free_port <= 65535:
                if free_ports[free_port]:
                    break
                free_port += 1
            if free_port == 65536:
                ports_lock.release()
                return [False, "No free ports."]
        free_ports[free_port] = False
        allocated_ports[container_name][container_port] = free_port
        public_ip = env.getenv("PUBLIC_IP")
        ports_lock.release()
        try:
            subprocess.run(['iptables','-t','nat','-A','PREROUTING','-p','tcp','--dport',str(free_port),"-j","DNAT",'--to-destination','%s:%s'%(container_ip,container_port)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
            return [True, str(free_port)]
        except subprocess.CalledProcessError as suberror:
            return [False, "set port mapping failed : %s" % suberror.stdout.decode('utf-8')]

    @staticmethod
    def release_port_mapping(container_name, container_ip, container_port):
        global free_ports
        global allocated_ports
        global ports_lock
        if container_name not in allocated_ports.keys():
            return [False, "This container does not have a port mapping."]
        free_port = allocated_ports[container_name][container_port]
        public_ip = env.getenv("PUBLIC_IP")
        try:
            subprocess.run(['iptables','-t','nat','-D','PREROUTING','-p','tcp','--dport',str(free_port),"-j","DNAT",'--to-destination','%s:%s'%(container_ip,container_port)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, check=True)
        except subprocess.CalledProcessError as suberror:
            return [False, "release port mapping failed : %s" % suberror.stdout.decode('utf-8')]
        ports_lock.acquire()
        free_ports[free_port] = True
        allocated_ports[container_name].pop(container_port)
        ports_lock.release()
        return [True, ""]
