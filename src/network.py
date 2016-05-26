#!/usr/bin/python3

import json, sys, netifaces
from nettools import netcontrol

from log import logger

from tools import netid_decode

# getip : get ip from network interface
# ifname : name of network interface
def getip(ifname):
    if ifname not in netifaces.interfaces():
        return False # No such interface
    else:
        addrinfo = netifaces.ifaddresses(ifname)
        if 2 in addrinfo:
            return netifaces.ifaddresses(ifname)[2][0]['addr']
        else:
            return False # network interface is down

def ip_to_int(addr):
    [a, b, c, d] = addr.split('.')
    return (int(a)<<24) + (int(b)<<16) + (int(c)<<8) + int(d)

def int_to_ip(num):
    return str((num>>24)&255)+"."+str((num>>16)&255)+"."+str((num>>8)&255)+"."+str(num&255)

# fix addr with cidr, for example, 172.16.0.10/24 --> 172.16.0.0/24
def fix_ip(addr, cidr):
    return int_to_ip(ip_to_int(addr) & ((-1)<<(32-int(cidr))))
    #return int_to_ip(ip_to_int(addr) & ( ~( (1<<(32-int(cidr)))-1 ) ) )

# jump to next interval address with cidr
def next_interval(addr, cidr):
    addr = fix_ip(addr, int(cidr))
    return int_to_ip(ip_to_int(addr)+(1<<(32-int(cidr))))

# jump to before interval address with cidr
def before_interval(addr, cidr):
    addr = fix_ip(addr, int(cidr))
    addrint = ip_to_int(addr)-(1<<(32-int(cidr)))
    # addrint maybe negative
    if addrint < 0:
        return "-1.-1.-1.-1"
    else:
        return int_to_ip(addrint)


# IntervalPool :  manage network blocks with IP/CIDR
# Data Structure :
#       ... ...
#       cidr=16 : A1, A2, ...      # A1 is an IP, means an interval [A1, A1+2^16-1], equals to A1/16
#       cidr=17 : B1, B2, ...
#       ... ...
# API :
#       allocate
#       free
class IntervalPool(object):
    # cidr : 1,2, ..., 32
    def __init__(self, addr_cidr=None, copy=None):
        if addr_cidr:
            self.pool = {}
            [addr, cidr] = addr_cidr.split('/')
            cidr = int(cidr)
            # fix addr with cidr, for example, 172.16.0.10/24 --> 172.16.0.0/24
            addr = fix_ip(addr, cidr)
            self.info = addr+"/"+str(cidr)
            # init interval pool
            #   cidr   : [ addr ]
            #   cidr+1 : [ ]
            #   ...
            #   32     : [ ]
            self.pool[str(cidr)] = [addr]
            for i in range(cidr+1, 33):
                self.pool[str(i)] = []
        elif copy:
            self.info = copy['info']
            self.pool = copy['pool']
        else:
            logger.error("IntervalPool init failed with no addr_cidr or center")

    def __str__(self):
        return json.dumps({'info':self.info, 'pool':self.pool})

    def printpool(self):
        cidrs = list(self.pool.keys())
        # sort with key=int(cidr)
        cidrs.sort(key=int)
        for i in cidrs:
            print(i + " : " + str(self.pool[i]))

    # allocate an interval with CIDR
    def allocate(self, thiscidr):
        # thiscidr -- cidr for this request
        # upcidr -- up stream which has interval to allocate
        thiscidr = int(thiscidr)
        upcidr = thiscidr
        # find first cidr who can allocate enough ips
        while (str(upcidr) in self.pool) and len(self.pool[str(upcidr)]) == 0:
            upcidr = upcidr-1
        if str(upcidr) not in self.pool:
            return [False, 'Not Enough to Allocate']
        # get the block/interval to allocate ips
        upinterval = self.pool[str(upcidr)][0]
        self.pool[str(upcidr)].remove(upinterval)
        # split the upinterval and put the rest intervals back to interval pool
        for i in range(int(thiscidr), int(upcidr), -1):
            self.pool[str(i)].append(next_interval(upinterval, i))
            #self.pool[str(i)].sort(key=ip_to_int)  # cidr between thiscidr and upcidr are null, no need to sort
        return [True, upinterval]

    # check whether the addr/cidr overlaps the self.pool
    # for example, addr/cidr=172.16.0.48/29 overlaps self.pool['24']=[172.16.0.0]
    def overlap(self, addr, cidr):
        cidr = int(cidr)
        start_cidr = int(self.info.split('/')[1])
        # test self.pool[cidr] from first cidr pool to last cidr pool
        for cur_cidr in range(start_cidr, 33):
            if not self.pool[str(cur_cidr)]:
                continue
            # for every cur_cidr, test every possible element covered by pool[cur_cidr] in range of addr/cidr
            cur_addr = fix_ip(addr, min(cidr, cur_cidr))
            last_addr = next_interval(addr, cidr)
            while ip_to_int(cur_addr) < ip_to_int(last_addr):
                if cur_addr in self.pool[str(cur_cidr)]:
                    return  True
                cur_addr = next_interval(cur_addr, cur_cidr)
        return False

    # whether addr/cidr is in the range of self.pool
    def inrange(self, addr, cidr):
        pool_addr, pool_cidr = self.info.split('/')
        if int(cidr) >= int(pool_cidr) and fix_ip(addr, pool_cidr) == pool_addr:
            return True
        else:
            return False

    # deallocate an interval with IP/CIDR
    def free(self, addr, cidr):
        if not self.inrange(addr, cidr):
            return [False, '%s/%s not in range of %s' % (addr, str(cidr), self.info)]
        if self.overlap(addr, cidr):
            return [False, '%s/%s overlaps the center pool:%s' % (addr, str(cidr), self.__str__())]
        cidr = int(cidr)
        # cidr not in pool means CIDR out of pool range
        if str(cidr) not in self.pool:
            return [False, 'CIDR not in pool']
        addr = fix_ip(addr, cidr)
        # merge interval and move to up cidr
        while True:
            # cidr-1 not in pool means current CIDR is the top CIDR
            if str(cidr-1) not in self.pool:
                break
            # if addr can satisfy cidr-1, and next_interval also exist,
            #           merge addr with next_interval to up cidr (cidr-1)
            # if addr not satisfy cidr-1, and before_interval exist,
            #           merge addr with before_interval to up cidr, and interval index is before_interval
            if addr == fix_ip(addr, cidr-1):
                if next_interval(addr, cidr) in self.pool[str(cidr)]:
                    self.pool[str(cidr)].remove(next_interval(addr, cidr))
                    cidr = cidr-1
                else:
                    break
            else:
                if before_interval(addr, cidr) in self.pool[str(cidr)]:
                    addr = before_interval(addr, cidr)
                    self.pool[str(cidr)].remove(addr)
                    cidr = cidr - 1
                else:
                    break
        self.pool[str(cidr)].append(addr)
        # sort interval with key=ip_to_int(IP)
        self.pool[str(cidr)].sort(key=ip_to_int)
        return [True, "Free success"]

# EnumPool : manage network ips with ip or ip list
# Data Structure : [ A, B, C, ... X ] , A is a IP address
class EnumPool(object):
    def __init__(self, addr_cidr=None, copy=None):
        if addr_cidr:
            self.pool = []
            [addr, cidr] = addr_cidr.split('/')
            cidr = int(cidr)
            addr = fix_ip(addr, cidr)
            self.info = addr+"/"+str(cidr)
            # init enum pool
            # first IP is network id, last IP is network broadcast address
            # first and last IP can not be allocated
            for i in range(1, pow(2, 32-cidr)-1):
                self.pool.append(int_to_ip(ip_to_int(addr)+i))
        elif copy:
            self.info = copy['info']
            self.pool = copy['pool']
        else:
            logger.error("EnumPool init failed with no addr_cidr or copy")

    def __str__(self):
        return json.dumps({'info':self.info, 'pool':self.pool})

    def printpool(self):
        print(str(self.pool))

    def acquire(self, num=1):
        if num > len(self.pool):
            return [False, "No enough IPs: %s" % self.info]
        result = []
        for _ in range(0, num):
            result.append(self.pool.pop())
        return [True, result]

    def acquire_cidr(self, num=1):
        [status, result] = self.acquire(int(num))
        if not status:
            return [status, result]
        return [True, [(x+"/"+self.info.split('/')[1]) for x in result]]
        # return [True, list(map(lambda x: x+"/"+self.info.split('/')[1], result))]

    def inrange(self, ip):
        addr = self.info.split('/')[0]
        addrint = ip_to_int(addr)
        cidr = int(self.info.split('/')[1])
        if addrint+1 <= ip_to_int(ip) <= addrint+pow(2, 32-cidr)-2:
            return True
        return False

    def release(self, ip_or_ips):
        if isinstance(ip_or_ips, str):
            ips = [ip_or_ips]
        else:
            ips = ip_or_ips
        # check whether all IPs are not in the pool but in the range of pool
        for ip in ips:
            ip = ip.split('/')[0]
            if (ip in self.pool) or (not self.inrange(ip)):
                return [False, 'release IPs failed for ip already existing or ip exceeding the network pool, ips to be released: %s, ip pool is: %s and content is : %s' % (ips, self.info, self.pool)]
        for ip in ips:
            # maybe ip is in format IP/CIDR
            ip = ip.split('/')[0]
            self.pool.append(ip)
        return [True, "release success"]

# wrap EnumPool with netid and gateway
class UserPool(EnumPool):
    def __init__(self, addr_cidr=None, netid=None, copy=None):
        if addr_cidr and netid != None:
            EnumPool.__init__(self, addr_cidr=addr_cidr)
            self.netid = netid
            self.pool.sort(key=ip_to_int)
            self.gateway = self.pool[0]
            self.pool.remove(self.gateway)
        elif copy:
            EnumPool.__init__(self, copy=copy)
            self.netid = int(copy['netid'])
            self.gateway = copy['gateway']
        else:
            logger.error("UserPool init failed with no addr_cidr or copy")

    def get_gateway(self):
        return self.gateway

    def get_gateway_cidr(self):
        return self.gateway+"/"+self.info.split('/')[1]

    def inrange(self, ip):
        addr = self.info.split('/')[0]
        addrint = ip_to_int(addr)
        cidr = int(self.info.split('/')[1])
        if addrint+2 <= ip_to_int(ip) <= addrint+pow(2, 32-cidr)-2:
            return True
        return False

    def printpool(self):
        print("user netid:"+str(self.netid)+",  net info:"+self.info+",  gateway:"+self.gateway)
        print(str(self.pool))

class NetIdMgr(object):
    def __init__(self, etcdclient, mode):
        self.__etcd = etcdclient
        self.netid_count = 0
        # pool_size should not be changed after master init
        self.__pool_size = 89
        self.__pool_count = 0
        self.cur_pool_index = -1
        self.cur_pool = []
        if mode == 'new':
            logger.info("init net id manager")
        elif mode == 'recovery':
            logger.info("init net id manager from etcd")
            self.__load_info()
            self.__load_cur_pool_index()
            self.__load_pool(self.cur_pool_index)
        else:
            logger.error("__init__ in NetIdMgr: mode: %s not supported" % (mode))
            sys.exit(1)

    def __dump_info(self):
        self.__etcd.setkey('netids/info', json.dumps({'netid_count': self.netid_count, 'pool_count': self.__pool_count}))

    def __load_info(self):
        [sts, res] = self.__etcd.getkey('netids/info')
        if sts:
            info = json.loads(res)
            self.netid_count = int(info['netid_count'])
            self.__pool_count = int(info['pool_count'])
        else:
            self.netid_count = 0
            self.__pool_count = 0
            logger.warning('load_info in NetIdMgr: etcd get info failed, use default')

    def __dump_cur_pool(self):
        if self.cur_pool_index >= 0 and self.cur_pool_index < self.__pool_count:
            self.__etcd.setkey('netids/cur_pool_index', self.cur_pool_index)
            self.__etcd.setkey('netids/pools/'+str(self.cur_pool_index), self.cur_pool)

    def __load_cur_pool_index(self):
        [sts, res] = self.__etcd.getkey('netids/cur_pool_index')
        if sts:
            self.cur_pool_index = int(res)
        else:
            self.cur_pool_index = -1
            logger.warning('load_info in NetIdMgr: etcd get cur_pool_index failed, use default')

    def __load_pool(self, pool_index):
        [sts, res] = self.__etcd.getkey('netids/pools/'+str(pool_index))
        if sts:
            self.cur_pool = list(json.loads(res))
        else:
            self.cur_pool = []
            logger.warning('load_pool in NetIdMgr: etcd get pools /%s failed, used default' % (str(pool_index)))

    # add pools to etcd, modify etcd info and pools
    def add_pool(self):
        pool = list(range(self.netid_count, self.netid_count + self.__pool_size))
        self.__etcd.setkey('netids/pools/'+str(self.__pool_count), json.dumps(pool))
        self.netid_count += self.__pool_size
        self.__pool_count += 1
        self.__dump_info()

    # get netid, if current pool is empty, load next pool
    def get_netid(self):
        if len(self.cur_pool) == 0:
            self.cur_pool_index += 1
            if self.cur_pool_index == self.__pool_count:
                self.add_pool()
            self.__load_pool(self.cur_pool_index)
        netid = self.cur_pool.pop()
        self.__dump_cur_pool()
        return int(netid)

    # return netid, if current pool is full, load previous pool
    def ret_netid(self, netid):
        if len(self.cur_pool) == self.__pool_size:
            self.cur_pool_index -= 1
            if self.cur_pool_index == -1:
                # should should not happen
                self.cur_pool_index += 1
                logger.warning('ret_netid in NetIdMgr: return netid %s when all pools are full' % (str(netid)))
            else:
                self.__load_pool(self.cur_pool_index)
        self.cur_pool.append(netid)
        self.__dump_cur_pool()
        return

# NetworkMgr : mange docklet network ip address
#   center : interval pool to allocate and free network block with IP/CIDR
#   system : enumeration pool to acquire and release system ip address
#   users : set of users' enumeration pools to manage users' ip address
class NetworkMgr(object):
    def __init__(self, vsmgr, addr_cidr, etcdclient, mode):
        self.etcd = etcdclient
        self.vsmgr = vsmgr
        self.idmgr = NetIdMgr(self.etcd, mode)
        if mode == 'new':
            logger.info("init network manager with %s" % (addr_cidr))
            self.center = IntervalPool(addr_cidr=addr_cidr)
            # allocate a pool for system IPs, use CIDR=27, has 32 IPs
            syscidr = 27
            [status, sysaddr] = self.center.allocate(syscidr)
            if not status:
                logger.error("allocate system ips in __init__ failed")
                sys.exit(1)
            # maybe for system, the last IP address of CIDR is available
            # But, EnumPool drop the last IP address in its pool -- it is not important
            self.system = EnumPool(sysaddr+"/"+str(syscidr))
            self.users = {}
            self.dump_center()
            self.dump_system()
        elif mode == 'recovery':
            logger.info("init network manager from etcd")
            self.center = None
            self.system = None
            self.users = {}
            self.load_center()
            self.load_system()
        else:
            logger.error("mode: %s not supported" % mode)

    def load_center(self):
        [status, centerdata] = self.etcd.getkey("network/center")
        if status:
            center = json.loads(centerdata)
            self.center = IntervalPool(copy=center)
        else:
            logger.info("load center failed")

    def dump_center(self):
        self.etcd.setkey("network/center", json.dumps({'info':self.center.info, 'pool':self.center.pool}))

    def load_system(self):
        [status, systemdata] = self.etcd.getkey("network/system")
        if status:
            system = json.loads(systemdata)
            self.system = EnumPool(copy=system)
        else:
            logger.info("load system failed")

    def dump_system(self):
        self.etcd.setkey("network/system", json.dumps({'info':self.system.info, 'pool':self.system.pool}))

    def load_user(self, username):
        [status, userdata] = self.etcd.getkey("network/users/"+username)
        if status:
            usercopy = json.loads(userdata)
            user = UserPool(copy=usercopy)
            self.users[username] = user
        else:
            logger.info("load user %s failed" % username)

    def dump_user(self, username):
        self.etcd.setkey("network/users/"+username, json.dumps({'info':self.users[username].info, 'netid':self.users[username]. netid, 'gateway':self.users[username].gateway, 'pool':self.users[username].pool}))

    def printpools(self):
        print("<Center>")
        self.center.printpool()
        print("<System>")
        self.system.printpool()
        print("<users>")
        print("    users in users is in etcd, not in memory")
        print("<netids>")
        print("%s : %s" % (str(self.idmgr.cur_pool_index), str(self.idmgr.cur_pool)))

    def add_user(self, username, cidr):
        logger.info("add user %s with cidr=%s" % (username, str(cidr)))
        if self.has_user(username):
            return [False, "user already exists in users set"]
        [status, result] = self.center.allocate(cidr)
        self.dump_center()
        if not status:
            return [False, result]
        netid = self.idmgr.get_netid()
        if status:
            netid = int(netid)
        else:
            self.center.free(result, cidr)
            self.dump_center()
            return [False, netid]
        self.users[username] = UserPool(addr_cidr=result+"/"+str(cidr), netid=netid)
        logger.info("setup gateway for %s with %s and netid=%s" % (username, self.users[username].get_gateway_cidr(), str(netid)))
        [switchid, vlanid] = netid_decode(netid)
        self.vsmgr.check_switch(switchid)
        netcontrol.setup_gw(switchid, username, self.users[username].get_gateway_cidr(), vlanid)
        self.dump_user(username)
        del self.users[username]
        return [True, 'add user success']

    def del_user(self, username):
        if not self.has_user(username):
            return [False, username+" not in users set"]
        self.load_user(username)
        [addr, cidr] = self.users[username].info.split('/')
        netid = self.users[username].netid
        logger.info("delete user %s with cidr=%s" % (username, int(cidr)))
        self.center.free(addr, int(cidr))
        self.dump_center()
        self.idmgr.ret_netid(netid)
        [switchid, _] = netid_decode(netid)
        self.vsmgr.check_switch(switchid)
        netcontrol.del_gw(switchid, username)
        self.etcd.deldir("network/users/"+username)
        del self.users[username]
        return [True, 'delete user success']

    def check_usergw(self, username):
        self.load_user(username)
        [switchid, vlanid] = netid_decode(self.users[username].netid)
        self.vsmgr.check_switch(switchid)
        netcontrol.check_gw(switchid, username, self.users[username].get_gateway_cidr(), vlanid)
        del self.users[username]
        return [True, 'check gw ok']

    def has_user(self, username):
        [status, _] = self.etcd.getkey("network/users/"+username)
        return status

    def acquire_userips(self, username, num=1):
        logger.info("acquire user ips of %s" % (username))
        if not self.has_user(username):
            return [False, 'username not exists in users set']
        self.load_user(username)
        result = self.users[username].acquire(num)
        self.dump_user(username)
        del self.users[username]
        return result

    def acquire_userips_cidr(self, username, num=1):
        logger.info("acquire user ips of %s" % (username))
        if not self.has_user(username):
            return [False, 'username not exists in users set']
        self.load_user(username)
        result = self.users[username].acquire_cidr(num)
        self.dump_user(username)
        del self.users[username]
        return result

    # ip_or_ips : one IP address or a list of IPs
    def release_userips(self, username, ip_or_ips):
        logger.info("release user ips of %s with ips: %s" % (username, str(ip_or_ips)))
        if not self.has_user(username):
            return [False, 'username not exists in users set']
        self.load_user(username)
        result = self.users[username].release(ip_or_ips)
        self.dump_user(username)
        del self.users[username]
        return result

    def get_usergw(self, username):
        if not self.has_user(username):
            return [False, 'username not exists in users set']
        self.load_user(username)
        result = self.users[username].get_gateway()
        self.dump_user(username)
        del self.users[username]
        return result

    def get_usergw_cidr(self, username):
        if not self.has_user(username):
            return [False, 'username not exists in users set']
        self.load_user(username)
        result = self.users[username].get_gateway_cidr()
        self.dump_user(username)
        del self.users[username]
        return result

    def get_usernetid(self, username):
        if not self.has_user(username):
            return [False, 'username not exists in users set']
        self.load_user(username)
        result = self.users[username].netid
        self.dump_user(username)
        del self.users[username]
        return result

    def acquire_sysips(self, num=1):
        logger.info("acquire system ips")
        result = self.system.acquire(num)
        self.dump_system()
        return result

    def acquire_sysips_cidr(self, num=1):
        logger.info("acquire system ips")
        result = self.system.acquire_cidr(num)
        self.dump_system()
        return result

    def release_sysips(self, ip_or_ips):
        logger.info("acquire system ips: %s" % str(ip_or_ips))
        result = self.system.release(ip_or_ips)
        self.dump_system()
        return result


class VSMgr:
    def __init__(self, nodemgr, addr, master, mode):
        self.__mode = mode
        self.__addr = addr
        self.__master = master
        self.__switches = []
        self.__nodemgr = nodemgr

    # worker and master: check if a switch exists, if not add one
    def check_switch(self, switchid):
        switchid = int(switchid)
        if switchid not in self.__switches and self.__mode == 'new' and netcontrol.bridge_exists(switchid):
            [sts, _] = netcontrol.del_bridge(switchid)
            if not sts:
                return [False, "del virtual switch failed with mode new"]
        if not netcontrol.bridge_exists(switchid):
            [sts, _] = netcontrol.new_bridge(switchid)
            if not sts:
                return [False, "add virtual switch failed"]
        if switchid not in self.__switches:
            self.__switches.append(switchid)
        return [True, "check virtual switch okay"]

    # master: add a new switch and a gre tunnel to the worker
    # if master on this node, reuse master's virtual network
    def connect_switch(self, switchid, worker_rpc):
        if self.__addr != self.__master:
            return [False, 'not master']
        [sts, _] = self.check_switch(switchid)
        if not sts:
            return [False, 'master switch check failed']
        workerip = self.__nodemgr.rpc_to_ip(worker_rpc)
        if self.__addr == workerip:
            return [True, 'worker reuse master switch']
        if not netcontrol.gre_exists(switchid, workerip):
            [sts, _] = netcontrol.setup_gre(switchid, workerip, switchid)
            if not sts:
                return [False, 'master setup gre failed']
        [sts, _] = worker_rpc.check_switch_with_gre(switchid)
        if sts:
            return [True, 'switch connected']
        else:
            return [False, 'worker setup failed']

    # worker: check a switch and a gre tunnel to the master
    # if master on this node, reuse master's virtual network
    def check_switch_with_gre(self, switchid):
        if self.__addr == self.__master:
            return True
        switchid = int(switchid)
        if switchid not in self.__switches and self.__mode == 'new' and netcontrol.bridge_exists(switchid):
            [sts, _] = netcontrol.del_bridge(switchid)
            if not sts:
                return [False, "del virtual switch failed with mode new"]
        if not netcontrol.bridge_exists(switchid):
            [sts, _] = netcontrol.new_bridge(switchid)
            if not sts:
                return [False, "add virtual switch failed"]
        if switchid not in self.__switches:
            self.__switches.append(switchid)
        if not netcontrol.gre_exists(switchid, self.__master):
            [sts, _] = netcontrol.setup_gre(switchid, self.__master, switchid)
            if not sts:
                return [False, "setup gre to master failed"]
        return [True, "check virtual switch okay"]
