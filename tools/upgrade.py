#!/usr/bin/python3

import os, json, sys
sys.path.append("../src/")
from model import db, User
fspath="/opt/docklet"

def update_quotainfo():
    if not os.path.exists(fspath+"/global/sys/quotainfo"):
        print("quotainfo file not exists, please run docklet to init it")
        return False
    quotafile = open(fspath+"/global/sys/quotainfo", 'r')
    quotas = json.loads(quotafile.read())
    quotafile.close()
    if type(quotas) is list:
        new_quotas = {}
        new_quotas['default'] = 'foundation'
        new_quotas['quotainfo'] = quotas
        quotas = new_quotas
        print("change the type of quotafile from list to dict")
    keys = []
    for quota in quotas['quotainfo']:
        keys.append(quota['name'])
    if 'cpu' not in keys:
        quotas['quotainfo'].append({'name':'cpu', 'hint':'the cpu quota, number of cores, e.g. 4'})
    if 'memory' not in keys:
        quotas['quotainfo'].append({'name':'memory', 'hint':'the memory quota, number of MB, e.g. 4000'})
    if 'disk' not in keys:
        quotas['quotainfo'].append({'name':'disk', 'hint':'the disk quota, number of MB, e.g. 4000'})
    if 'data' not in keys:
        quotas['quotainfo'].append({'name':'data', 'hint':'the quota of data space, number of GB, e.g. 100'})
    if 'image' not in keys:
        quotas['quotainfo'].append({'name':'image', 'hint':'how many images the user can have, e.g. 8'})
    if 'idletime' not in keys:
        quotas['quotainfo'].append({'name':'idletime', 'hint':'will stop cluster after idletime, number of hours, e.g. 24'})
    if 'vnode' not in keys:
        quotas['quotainfo'].append({'name':'vnode', 'hint':'how many containers the user can have, e.g. 8'})
    print("quotainfo updated")
    quotafile = open(fspath+"/global/sys/quotainfo", 'w')
    quotafile.write(json.dumps(quotas))
    quotafile.close()
    if not os.path.exists(fspath+"/global/sys/quota"):
        print("quota file not exists, please run docklet to init it")
        return False
    groupfile = open(fspath+"/global/sys/quota",'r')
    groups = json.loads(groupfile.read())
    groupfile.close()
    for group in groups:
        if 'cpu' not in group['quotas'].keys():
            group['quotas']['cpu'] = "4"
        if 'memory' not in group['quotas'].keys():
            group['quotas']['memory'] = "2000"
        if 'disk' not in group['quotas'].keys():
            group['quotas']['disk'] = "2000"
        if 'data' not in group['quotas'].keys():
            group['quotas']['data'] = "100"
        if 'image' not in group['quotas'].keys():
            group['quotas']['image'] = "10"
        if 'idletime' not in group['quotas'].keys():
            group['quotas']['idletime'] = "24"
        if 'vnode' not in group['quotas'].keys():
            group['quotas']['vnode'] = "8"
    print("quota updated")
    groupfile = open(fspath+"/global/sys/quota",'w')
    groupfile.write(json.dumps(groups))
    groupfile.close()


def name_error():
    quotafile = open(fspath+"/global/sys/quotainfo", 'r')
    quotas = json.loads(quotafile.read())
    quotafile.close()
    if quotas['default'] == 'fundation':
        quotas['default'] = 'foundation'
    quotafile = open(fspath+"/global/sys/quotainfo",'w')
    quotafile.write(json.dumps(quotas)) 
    quotafile.close()

    groupfile = open(fspath+"/global/sys/quota", 'r')
    groups = json.loads(groupfile.read())
    groupfile.close()
    for group in groups:
        if group['name'] == 'fundation':
            group['name'] = 'foundation'
    groupfile = open(fspath+"/global/sys/quota",'w')
    groupfile.write(json.dumps(groups)) 
    groupfile.close()
    
    users = User.query.filter_by(user_group = 'fundation').all()
    for user in users:
        user.user_group = 'foundation'
    db.session.commit()
    

def allquota():
    try:
        quotafile = open(fspath+"/global/sys/quota", 'r')
        quotas = json.loads(quotafile.read())
        quotafile.close()
        return quotas
    except Exception as e:
        print(e)
        return None

def quotaquery(quotaname,quotas):
    for quota in quotas:
        if quota['name'] == quotaname:
            return quota['quotas']
    return None

def enable_gluster_quota():
    conffile=open("../conf/docklet.conf",'r')
    conf=conffile.readlines()
    conffile.close()
    enable = False
    volume_name = ""
    for line in conf:
        if line.startswith("DATA_QUOTA"):
            keyvalue = line.split("=")
            if len(keyvalue) < 2:
                continue
            key = keyvalue[0].strip()
            value = keyvalue[1].strip()
            if value == "YES":
                enable = True
                break
    for line in conf:
        if line.startswith("DATA_QUOTA_CMD"):
            keyvalue = line.split("=")
            if len(keyvalue) < 2:
                continue
            volume_name = keyvalue[1].strip()
    if not enable:
        print("don't need to enable the quota")
        return
    
    users = User.query.all()
    quotas = allquota()
    if quotaquery == None:
        print("quota info not found")
        return
    sys_run("gluster volume quota %s enable" % volume_name)
    for user in users:
        quota = quotaquery(user.user_group, quotas)
        nfs_quota = quota['data']
        if nfs_quota == None:
            print("data quota should be set")
            return
        nfspath = "/users/%s/data" % user.username
        sys_run("gluster volume quota %s limit-usage %s %sGB" % (volume_name,nfspath,nfs_quota))

if __name__ == '__main__':
    update_quotainfo()
    if "fix-name-error" in sys.argv:
        name_error()
#    enable_gluster_quota()
