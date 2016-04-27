#!/usr/bin/python3

############################################################
# etcdlib.py -- etcdlib provides a python etcd client
# author : Bao Li <libao14@pku.edu.cn>, UniAS, SEI, PKU
# license : BSD License
############################################################

import urllib.request, urllib.error
import random, json, time
#import sys

# send http request to etcd server and get the json result 
# url : url
# data : data to send by POST/PUT
# method : method used by http request 
def dorequest(url, data = "", method = 'GET'):
    try: 
        if method == 'GET':
            response = urllib.request.urlopen(url, timeout=10).read()
        else:
            # use PUT/DELETE/POST, data should be encoded in ascii/bytes 
            request = urllib.request.Request(url, data = data.encode('ascii'), method = method)
            response = urllib.request.urlopen(request, timeout=10).read()
    # etcd may return json result with response http error code
    # http error code will raise exception in urlopen
    # catch the HTTPError and get the json result
    except urllib.error.HTTPError as e:
        # e.fp must be read() in this except block.
        # the e will be deleted and e.fp will be closed after this block
        response = e.fp.read()
    # response is encoded in bytes. 
    # recoded in utf-8 and loaded in json
    result = json.loads(str(response, encoding='utf-8'))
    return result


# client to use etcd
# not all APIs are implemented below. just implement what we want
class Client(object):
    # server is a string of one server IP and PORT, like 192.168.4.12:2379
    def __init__(self, server, prefix = ""):
        self.clientid = str(random.random())
        self.server = "http://"+server
        prefix = prefix.strip("/")
        if prefix == "":
            self.keysurl = self.server+"/v2/keys/"
        else:
            self.keysurl = self.server+"/v2/keys/"+prefix+"/"
        self.members = self.getmembers()

    def getmembers(self):
        out = dorequest(self.server+"/v2/members")
        result = []
        for one in out['members']:
            result.append(one['clientURLs'][0])
        return result 

    # list etcd servers 
    def listmembers(self):
        return self.members

    def clean(self):
        [baseurl, dirname] = self.keysurl.split("/v2/keys/", maxsplit=1)
        dirname = dirname.strip("/") 
        if dirname == '': # clean root content
            [status, result] = self.listdir("")
            if status:
                for one in result:
                    if 'dir' in one:
                        self.deldir(one['key'])
                    else:
                        self.delkey(one['key'])
            if self.isdir("_lock"):
                self.deldir("_lock")
        else: # clean a directory
            if self.isdir("")[0]:
                self.deldir("")
            self.createdir("")

    def getkey(self, key):
        key = key.strip("/")
        out = dorequest(self.keysurl+key)
        if 'action' not in out:
            return [False, "key not found"]
        else:
            return [True, out['node']['value']]

    def setkey(self, key, value, ttl=0):
        key = key.strip("/")
        if ttl == 0:
            out = dorequest(self.keysurl+key, 'value='+str(value), 'PUT')
        else:
            out = dorequest(self.keysurl+key, 'value='+str(value)+"&ttl="+str(ttl), 'PUT')
        if 'action' not in out:
            return [False, 'set key failed']
        else:
            return [True, out['node']['value']]

    def delkey(self, key):
        key = key.strip("/")
        out = dorequest(self.keysurl+key, method='DELETE')
        if 'action' not in out:
            return [False, 'delete key failed']
        else:
            return [True, out['node']['key']]

    def isdir(self, dirname):
        dirname = dirname.strip("/") 
        out = dorequest(self.keysurl+dirname)
        if 'action' not in out:
            return [False, dirname+" not found"]
        if 'dir' not in out['node']:
            return [False, dirname+" is a key"]
        return [True, dirname]

    def createdir(self, dirname):
        dirname = dirname.strip("/")
        out = dorequest(self.keysurl+dirname, 'dir=true', 'PUT')
        if 'action' not in out:
            return [False, 'create dir failed']
        else:
            return [True, out['node']['key']]
    
    # list key-value in the directory. BUT not recursive.
    # if necessary, recursive can be supported by add ?recursive=true in url
    def listdir(self, dirname):
        dirname = dirname.strip("/")
        out = dorequest(self.keysurl+dirname)
        if 'action' not in out:
            return [False, 'list directory failed']
        else:
            if "dir" not in out['node']:
                return [False, dirname+" is a key"]
            if 'nodes' not in out['node']:
                return [True, []]
            result=[]
            for kv in out['node']['nodes']:
                if 'dir' in kv:
                    result.append({"key":kv['key'], 'dir':True})
                else:
                    result.append({"key":kv['key'], 'value':kv['value']})
            return [True, result]
        
    # del directory with recursive=true
    def deldir(self, dirname):
        dirname = dirname.strip("/")
        out = dorequest(self.keysurl+dirname+"?recursive=true", method='DELETE')
        if 'action' not in out:
            return [False, 'delete directory failed']
        else:
            return [True, out['node']['key']]

    # watch a key or directory when it changes. 
    # recursive=true means anything in the directory changes, it will return
    def watch(self, key):
        key = key.strip("/")
        out = dorequest(self.keysurl+key+"?wait=true&recursive=true")
        if 'action' not in out:
            return [False, 'watch key failed']
        else:
            return [True, out['node']['value']]

    # atomic create a key. return immediately with True or False
    def atomiccreate(self, key, value='atom'):
        key = key.strip("/")
        out = dorequest(self.keysurl+key+"?prevExist=false", 'value='+value, method='PUT')
        if 'action' not in out:
            return [False, 'atomic create key failed']
        else:
            return [True, out['node']['key']]

    ################# Lock ##################
    # lockref(key) : get a reference of a lock named key in etcd.
    #                not need to create this lock. it is automatical.
    # acquire(lockref) : acquire this lock by lockref.
    #                    blocked if lock is holded by others
    # release(lockref) : release this lock by lockref
    #                    only can be released by holder
    #########################################
    def lockref(self, key):
        key = key.strip("/")
        return "_lock/"+key

    def acquire(self, lockref):
        while(True):
            if self.atomiccreate(lockref, self.clientid)[0]:
                return [True, 'get lock']
            else:
                time.sleep(0.01)

    def release(self, lockref):
        value = self.getkey(lockref)
        if value[0]:
            if value[1] == self.clientid:
                self.delkey(lockref)
                return [True, 'release lock']
            else:
                return [False, 'you are not lock holder']
        else:
            return [False, 'no one holds this lock']

    def getnode(self, key):
        key = key.strip("/")
        out = dorequest(self.keysurl+key)
        if 'action' not in out:
            return [False, "key not found"]
        elif 'dir' in out:
            return [False, dirname+" is a directory"]
        else:
            return [True, {"key":out['node']['key'], 'value':out['node']['value']}]