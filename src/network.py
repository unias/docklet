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
        if addr_cidr and netid:
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
        self.__netid_count = 0
        self.__pool_count = 0
        self.__cur_pool_index = -1
        self.__cur_pool = []
        if mode == 'new':
            logger.info("init net id manager")
        elif mode == 'recovery':
            logger.info("init net id manager from etcd")
            self.__load_info()
            self.__load_pool()
        else:
            logger.error("__init__ in NetIdMgr: mode: %s not supported" % (mode))
            sys.exit(1)

    def __dump_info(self):
        self.__etcd.setkey('netids/info', json.dump({'netid_count': self.__netid_count, 'pool_count': self.__pool_count}))

    def __load_info(self):
        [sts, res] = self.__etcd.getkey('netids/info')
        if sts:
            info = json.loads(res)
            self.__netid_count = int(info['netid_count'])
            self.__pool_count = int(info['pool_count'])
        else:
            self.__netid_count = 0
            self.__pool_count = 0
            logger.warning('load_info in NetIdMgr: etcd get info failed, use default')

    def __dump_cur_pool(self):
        if self.__cur_pool_index >=0 and self.__cur_pool_index < self.__pool_count:
            self.__etcd.setkey('netids/cur_pool_index', self.__cur_pool_index)
            self.__etcd.setkey('netids/pools/'+str(self.__cur_pool_index), self.__cur_pool)

    def __load_cur_pool_index(self):
        [sts, res] = self.__etcd.getkey('netids/cur_pool_index')
        if sts:
            self.__cur_pool_index = int(res)
        else:
            self.__cur_pool_index = -1
            logger.warning('load_info in NetIdMgr: etcd get cur_pool_index failed, use default')

    def __load_pool(self, pool_index):
        [sts, res] = self.__etcd.getkey('netids/pools/'+str(pool_index))
        if sts:
            self.__cur_pool = list(json.loads(res))
        else:
            self.__cur_pool = []
            logger.warning('load_pool in NetIdMgr: etcd get pools/%s failed, used default' % (str(index)))

    # add pools to etcd, modify etcd info and pools
    def add_pool(self, count=4094, pool_size=89):
        new_pool_count = int(celling(count/pool_size))
        for i in range(0, new_pool_count):
            pool = list(range(self.__netid_count + i*pool_size, self.__netid_count + (i+1)*pool_size))
            self.etcd.setkey('netids/pools/'+str(self.__pool_count+i), json.dumps(pool))
        self.__netid_count += count
        self.__pool_count += new_pool_count
        self.__dump_info()

    # get netid, if current pool is empty, load next pool
    def get_netid(self):
        if len(self.__cur_pool) == 0:
            self.__cur_pool_index += 1
            if self.__cur_pool_index == self.__pool_count:
                self.__add_pool()
            self.__load_pool(self.cur_pool_index)
        netid = self.__cur_pool.pop()
        self.__dump_cur_pool()
        return int(netid)
    
    # return netid, if current pool is full, load previous pool
    def ret_netid(self, netid, pool_size=89):
        if len(self.__cur_pool) == pool_size:
            self.__cur_pool_index -= 1
            if self.__cur_pool_index == -1:
                # should should not happen
                self.__cur_pool_index += 1
                logger.warning('ret_netid in NetIdMgr: return netid %s when all pools are full' % (str(netid)))
            else:
                self.__load_pool(self.__cur_pool_index)
        self.__cur_pool.append(netid)
        self.__dump_cur_pool()
        return

# NetworkMgr : mange docklet network ip address
#   center : interval pool to allocate and free network block with IP/CIDR
#   system : enumeration pool to acquire and release system ip address
#   users : set of users' enumeration pools to manage users' ip address
class NetworkMgr(object):
    def __init__(self, vnet_count, addr_cidr, etcdclient, mode):
        self.etcd = etcdclient
        self.__idmgr = NetIdMgr(self.etcd, mode)
        if mode == 'new':
            logger.info("init network manager with %s and max %s ids" % (addr_cidr, str(vnet_count))
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
            #self.netids = {}
            #self.init_netids(vnet_count, 60)
            #self.init_shared_netids()
            self.dump_center()
            self.dump_system()
        elif mode == 'recovery':
            logger.info("init network manager from etcd")
            self.center = None
            self.system = None
            self.users = {}
            #self.netids = {}
            self.load_center()
            self.load_system()
            #self.load_netids()
            #self.load_shared_netids()
        else:
            logger.error("mode: %s not supported" % mode)

    # def init_netids(self, total, block):
    #     self.netids['total'] = total
    #     self.netids['block'] = block
    #     self.etcd.setkey("network/netids/info", str(total)+"/"+str(block))
    #     i = 0
    #     for i in range(1, int((total-1)/block)):
    #         self.etcd.setkey("network/netids/"+str(i), json.dumps(list(range(block*(i-1), block*i))))
    #     self.netids['currentpool'] = list(range(block*i, total))
    #     self.netids['currentindex'] = i+1
    #     self.etcd.setkey("network/netids/"+str(i+1), json.dumps(self.netids['currentpool']))
    #     self.etcd.setkey("network/netids/current", str(i+1))

    # Data Structure:
    # shared_netids = [{netid = ..., remainnum = ...}, {netid = ..., remainnum = ...}, ...]
    # def init_shared_netids(self, netnum=128, sharenum=128):
    #     self.shared_netids = []
    #     for i in range(netnum):
    #         shared_netid = {}
    #         [status, shared_netid['netid']] = self.acquire_netid()
    #         if not status:
    #             logger.info('not enough netids for sharing, still need %s' % str(netnum-i))
    #             break
    #         shared_netid['remainnum'] = sharenum
    #         self.shared_netids.append(shared_netid)
    #     self.etcd.setkey("network/shared_netids", json.dumps(self.shared_netids))

    # load net info and an avaliable net pool
    # def load_netids(self):
    #     [status, info] = self.etcd.getkey("network/netids/info")
    #     if not status:
    #         logger.info("load netids info failed")
    #     self.netids['total'] = int(info.split("/")[0])
    #     self.netids['block'] = int(info.split("/")[1])
    #     [status, current] = self.etcd.getkey("network/netids/current")
    #     self.netids['currentindex'] = int(current)
    #     if self.netids['currentindex'] == 0:
    #         self.netids['currentpool'] = []
    #     else:
    #         [status, pool] = self.etcd.getkey("network/netids/"+str(self.netids['currentindex']))
    #         self.netids['currentpool'] = json.loads(pool)

    # def dump_netids(self):
    #     if self.netids['currentpool'] == []:
    #         if self.netids['currentindex'] != 0:
    #             self.etcd.delkey("network/netids/"+str(self.netids['currentindex']))
    #             self.etcd.setkey("network/netids/current", str(self.netids['currentindex']-1))
    #         else:
    #             pass
    #     else:
    #         self.etcd.setkey("network/netids/"+str(self.netids['currentindex']), json.dumps(self.netids['currentpool']))

    # def load_shared_netids(self):
    #     [status, shared_netids] = self.etcd.getkey("network/shared_netids")
    #     if not status:
    #         self.init_shared_netids()
    #     else:
    #         self.shared_netids = json.loads(shared_netids)

    # def dump_shared_netids(self):
    #     self.etcd.setkey("network/shared_netids", json.dumps(self.shared_netids))

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
        print(str(self.netids['currentindex'])+":"+str(self.netids['currentpool']))

    # def acquire_netid(self, isshared=False):
    #     if isshared:
    #         # only share netid of the front entry
    #         # if remainnum is reduced to 0, move the front entry to the back
    #         # if remainnum is still equal to 0, one round of sharing is complete, start another one
    #         if self.shared_netids[0]['remainnum'] == 0:
    #             self.shared_netids.append(self.shared_netids.pop(0))
    #         if self.shared_netids[0]['remainnum'] == 0:
    #             logger.info("shared netids not enough, add user to full netids")
    #             for shared_netid in self.shared_netids:
    #                 shared_netid['remainnum'] = 128
    #         self.shared_netids[0]['remainnum'] -= 1
    #         self.dump_shared_netids()
    #         return [True, self.shared_netids[0]['netid']]

    #     if self.netids['currentpool'] == []:
    #         if self.netids['currentindex'] == 0:
    #             return [False, "No Net IDs"]
    #         else:
    #             logger.error("netids current pool is empty with current index not zero")
    #             return [False, "internal error"]
    #     netid = self.netids['currentpool'].pop()
    #     self.dump_netids()
    #     if self.netids['currentpool'] == []:
    #         self.load_netids()
    #     return [True, netid]

    # def release_netid(self, netid):
    #     if len(self.netids['currentpool']) == self.netids['block']:
    #         self.netids['currentpool'] = [netid]
    #         self.netids['currentindex'] = self.netids['currentindex']+1
    #         self.dump_netids()
    #     else:
    #         self.netids['currentpool'].append(netid)
    #         self.dump_netids()
    #     return [True, "Release Net ID success"]

    def add_user(self, username, cidr, isshared=False):
        logger.info("add user %s with cidr=%s" % (username, str(cidr)))
        if self.has_user(username):
            return [False, "user already exists in users set"]
        [status, result] = self.center.allocate(cidr)
        self.dump_center()
        if not status:
            return [False, result]
        #[status, netid] = self.acquire_netid(isshared)
        netid = self.__idmgr.get_netid()
        if status:
            netid = int(netid)
        else:
            self.center.free(result, cidr)
            self.dump_center()
            return [False, netid]
        self.users[username] = UserPool(addr_cidr=result+"/"+str(cidr), netid=netid)
        logger.info("setup gateway for %s with %s and netid=%s" % (username, self.users[username].get_gateway_cidr(), str(netid)))
        [switchid, vlanid] = netid_decode(netid)
        netcontrol.setup_gw(switchid, username, self.users[username].get_gateway_cidr(), vlanid)
        self.dump_user(username)
        del self.users[username]
        return [True, 'add user success']

    def del_user(self, username, isshared=False):
        if not self.has_user(username):
            return [False, username+" not in users set"]
        self.load_user(username)
        [addr, cidr] = self.users[username].info.split('/')
        logger.info("delete user %s with cidr=%s" % (username, int(cidr)))
        self.center.free(addr, int(cidr))
        self.dump_center()
        #if not isshared:
        #    self.release_netid(self.users[username].netid)
        self.__idmgr.ret_netid(netid)
        netcontrol.del_gw(self.users[username].switchid, username)
        self.etcd.deldir("network/users/"+username)
        del self.users[username]
        return [True, 'delete user success']

    def check_usergw(self, username):
        self.load_user(username)
        [switchid, vlanid] = netid_decode(self.users[username].netid)
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
