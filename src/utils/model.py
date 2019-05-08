#coding=utf-8
'''
2 tables: users, usergroup
User:
    id
    username
    password
    avatar
    nickname
    description
    status
    student_number
    department
    truename
    tel
    e_mail
    register_date
    user_group
    auth_method

Usergroup
    id
    name

Token expiration can be set in User.generate_auth_token
'''
from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from datetime import datetime
from base64 import b64encode, b64decode
import os, json

#this class from itsdangerous implements token<->user
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired, BadSignature

from utils import env

fsdir = env.getenv('FS_PREFIX')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///'+fsdir+'/global/sys/UserTable.db'
app.config['SQLALCHEMY_BINDS'] = {
    'history': 'sqlite:///'+fsdir+'/global/sys/HistoryTable.db',
    'beansapplication': 'sqlite:///'+fsdir+'/global/sys/BeansApplication.db',
    'system': 'sqlite:///'+fsdir+'/global/sys/System.db',
    'batch':'sqlite:///'+fsdir+'/global/sys/Batch.db?check_same_thread=False',
    'login': 'sqlite:///'+fsdir+'/global/sys/Login.db'
    }
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
try:
    secret_key_file = open(env.getenv('FS_PREFIX') + '/local/token_secret_key.txt')
    app.secret_key = secret_key_file.read()
    secret_key_file.close()
except:
    from os import urandom
    secret_key = urandom(24)
    secret_key = b64encode(secret_key).decode('utf-8')
    app.secret_key = secret_key
    secret_key_file = open(env.getenv('FS_PREFIX') + '/local/token_secret_key.txt', 'w')
    secret_key_file.write(secret_key)
    secret_key_file.close()

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(10), unique=True)
    password = db.Column(db.String(100))
    avatar = db.Column(db.String(30))
    nickname = db.Column(db.String(10))
    description = db.Column(db.String(15))
    status = db.Column(db.String(10))
    e_mail = db.Column(db.String(20))
    student_number = db.Column(db.String(20))
    department = db.Column(db.String(20))
    truename = db.Column(db.String(20))
    tel = db.Column(db.String(20))
    register_date = db.Column(db.String(10))
    user_group = db.Column(db.String(50))
    auth_method = db.Column(db.String(10))
    beans = db.Column(db.Integer)

    def __init__(self, username, password, avatar="default.png", nickname = "", description = "", status = "init",
                    e_mail = "" , student_number = "", department = "", truename = "", tel="", date = None, usergroup = "primary"
                , auth_method = "local"):
        # using sha512
        #if (len(password) <= 6):
        #    self = None
        #    return None
        self.username = username
        self.password = password
        self.avatar = avatar
        self.nickname = nickname
        self.description = description
        self.status = status
        self.e_mail = e_mail
        self.student_number = student_number
        self.department = department
        self.truename = truename
        self.tel = tel
        self.beans = 150
        if (date != None):
            self.register_date = date
        else:
            self.register_date = datetime.now()
        self.user_group = usergroup
        self.auth_method = auth_method

    def __repr__(self):
        return '<User %r>' % (self.username)

    #token will expire after 3600s
    def generate_auth_token(self, expiration = 3600):
        s = Serializer(app.config['SECRET_KEY'], expires_in = expiration)
        str = s.dumps({'id': self.id})
        return b64encode(str).decode('utf-8')

    @staticmethod
    def verify_auth_token(token):
        s = Serializer(app.config['SECRET_KEY'])
        try:
            data = s.loads(b64decode(token))
        except SignatureExpired:
            return None # valid token, but expired
        except BadSignature:
            return None # invalid token
        user = User.query.get(data['id'])
        return user

class UserGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    cpu = db.Column(db.String(10))
    memory = db.Column(db.String(10))
    imageQuantity = db.Column(db.String(10))
    lifeCycle = db.Column(db.String(10))

    def __init__(self, name):
        self.name = name
        self.cpu = '100000'
        self.memory = '2000'
        self.imageQuantity = '10'
        self.lifeCycle = '24'

    def __repr__(self):
        return '<UserGroup %r>' % self.name

class UserUsage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    cpu = db.Column(db.String(10))
    memory = db.Column(db.String(10))
    disk = db.Column(db.String(10))

    def __init__(self, name):
        self.username = name
        self.cpu = '0'
        self.memory = '0'
        self.disk = '0'

    def __repr__(self):
        return '<UserUsage %s>cpu:%s memory:%s disk:%s' % (self.username,self.cpu,self.memory,self.disk)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    content = db.Column(db.String(8000))
    create_date = db.Column(db.String(10))
    # Status: 'open' -> Open to user, 'closed' -> Closed to user
    status = db.Column(db.String(20))

    def __init__(self, title, content=''):
        self.title = title
        self.content = content
        self.create_date = datetime.utcnow()
        self.status = 'open'

    def __repr__(self):
        return '<Notification %r>' % self.title


class NotificationGroups(db.Model):
    # __tablename__ = 'notification_groups'
    id = db.Column(db.Integer, primary_key=True)
    notification_id = db.Column(db.Integer)
    group_name = db.Column(db.String(100))

    def __init__(self, notification_id, group_name):
        self.notification_id = notification_id
        self.group_name = group_name

    def __repr__(self):
        return '<Notification: %r, Group: %r>' % (self.notification_id, self.group_name)

class UserNotificationPair(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    userName = db.Column(db.String(10))
    notifyId = db.Column(db.Integer)
    isRead = db.Column(db.Integer)

    def __init__(self, username, notifyid):
        self.userName = username
        self.notifyId = notifyid
        self.isRead = 0

    def __repr__(self):
        return '<UserName: %r, NotifyId: %r>' % (self.userName, self.notifyId)

class LoginMsg(db.Model):
    __bind_key__ = 'login'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(10))
    userip = db.Column(db.String(20))
    time = db.Column(db.DateTime)

    def __init__(self, username, userip):
        self.username = username
        self.userip = userip
        self.time = datetime.now()

    def __repr__(self):
        return '<id=%d, username=%s, userip=%s, time=%s>' % (self.id,self.username,self.userip,self.time.strftime("%Y-%m-%d %H:%M:%S"))

class LoginFailMsg(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(10), unique=True)
    failcnt = db.Column(db.Integer)
    bantime = db.Column(db.DateTime)

    def __init__(self, username):
        self.username = username
        self.failcnt = 0
        self.bantime = datetime.now()

    def __repr__(self):
        return '<id=%d, username=%s, failcnt=%d, bantime=%s>' % (self.id,self.username,self.failcnt,self.bantime.strftime("%Y-%m-%d %H:%M:%S"))

class VNode(db.Model):
    __bind_key__ = 'history'
    name = db.Column(db.String(100), primary_key=True)
    laststopcpuval = db.Column(db.Float)
    laststopruntime = db.Column(db.Integer)
    billing = db.Column(db.Integer)
    histories = db.relationship('History', backref='v_node', lazy='dynamic')

    def __init__(self, vnode_name):
        self.name = vnode_name
        self.laststopcpuval = 0
        self.billing = 0
        self.laststopruntime = 0

    def __repr__(self):
        return '<Vnodes %s>' % (self.name)

class History(db.Model):
    __bind_key__ = 'history'
    id = db.Column(db.Integer, primary_key=True)
    vnode = db.Column(db.String(100), db.ForeignKey('v_node.name'))
    action = db.Column(db.String(30))
    runningtime = db.Column(db.Integer)
    cputime = db.Column(db.Float)
    billing = db.Column(db.Integer)
    actionTime = db.Column(db.DateTime)

    def __init__(self, action, runningtime, cputime, billing):
        self.action = action
        self.runningtime = runningtime
        self.cputime = cputime
        self.billing = billing
        self.actionTime = datetime.now()

    def __repr__(self):
        return "{\"id\":\"%d\",\"vnode\":\"%s\",\"action\":\"%s\",\"runningtime\":\"%d\",\"cputime\":\"%f\",\"billing\":\"%d\",\"actionTime\":\"%s\"}" % (self.id, self.vnode, self.action, self.runningtime, self.cputime, self.billing, self.actionTime.strftime("%Y-%m-%d %H:%M:%S"))

class ApplyMsg(db.Model):
    __bind_key__ = 'beansapplication'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(10))
    number = db.Column(db.Integer)
    reason = db.Column(db.String(600))
    status = db.Column(db.String(10))
    time = db.Column(db.DateTime(10))

    def __init__(self,username, number, reason):
        self.username = username
        self.number = number
        self.reason = reason
        self.status = "Processing"
        self.time = datetime.now()

    def ch2dict(self):
        ans = {}
        ans['id'] = self.id
        ans['username'] = self.username
        ans['number'] = self.number
        ans['reason'] = self.reason
        ans['status'] = self.status
        ans['time'] = self.time.strftime("%Y-%m-%d %H:%M:%S")
        return ans

    def __repr__(self):
        return "{\"id\":\"%d\", \"username\":\"%s\", \"number\": \"%d\", \"reason\":\"%s\", \"status\":\"%s\", \"time\":\"%s\"}" % (self.id, self.username, self.number, self.reason, self.status, self.time.strftime("%Y-%m-%d %H:%M:%S"))

class Container(db.Model):
    __bind_key__ = 'system'
    containername = db.Column(db.String(100), primary_key=True)
    hostname = db.Column(db.String(30))
    ip = db.Column(db.String(20))
    host = db.Column(db.String(20))
    image = db.Column(db.String(50))
    lastsave = db.Column(db.DateTime)
    setting_cpu = db.Column(db.Integer)
    setting_mem = db.Column(db.Integer)
    setting_disk = db.Column(db.Integer)
    vclusterid = db.Column(db.Integer, db.ForeignKey('v_cluster.clusterid'))

    def __init__(self, containername, hostname, ip, host, image, lastsave, setting):
        self.containername = containername
        self.hostname = hostname
        self.ip = ip
        self.host = host
        self.image = image
        self.lastsave = lastsave
        self.setting_cpu = int(setting['cpu'])
        self.setting_mem = int(setting['memory'])
        self.setting_disk = int(setting['disk'])

    def __repr__(self):
        return "{\"containername\":\"%s\", \"hostname\":\"%s\", \"ip\": \"%s\", \"host\":\"%s\", \"image\":\"%s\", \"lastsave\":\"%s\", \"setting\":{\"cpu\":\"%d\",\"memory\":\"%d\",\"disk\":\"%d\"}}" % (self.containername, self.hostname, self.ip, self.host, self.image, self.lastsave.strftime("%Y-%m-%d %H:%M:%S"), self.setting_cpu, self.setting_mem, self.setting_disk)

class PortMapping(db.Model):
    __bind_key__ = 'system'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    node_name = db.Column(db.String(100))
    node_ip = db.Column(db.String(20))
    node_port = db.Column(db.Integer)
    host_port= db.Column(db.Integer)
    vclusterid = db.Column(db.Integer, db.ForeignKey('v_cluster.clusterid'))

    def __init__(self, node_name, node_ip, node_port, host_port):
        self.node_name = node_name
        self.node_ip = node_ip
        self.node_port = int(node_port)
        self.host_port = int(host_port)

    def __repr__(self):
        return "{\"id\":\"%d\", \"node_name\":\"%s\", \"node_ip\": \"%s\", \"node_port\":\"%s\", \"host_port\":\"%s\"}" % (self.id, self.node_name, self.node_ip, self.node_port, self.host_port)

class BillingHistory(db.Model):
    __bind_key__ = 'system'
    node_name = db.Column(db.String(100), primary_key=True)
    vclusterid = db.Column(db.Integer, db.ForeignKey('v_cluster.clusterid'))
    cpu = db.Column(db.Float)
    mem = db.Column(db.Float)
    disk = db.Column(db.Float)
    port = db.Column(db.Float)

    def __init__(self,node_name,cpu,mem,disk,port):
        self.node_name = node_name
        self.cpu = cpu
        self.mem = mem
        self.disk = disk
        self.port = port

    def __repr__(self):
        return "{\"node_name\":\"%s\", \"cpu\": %f, \"mem\": %f, \"disk\": %f, \"port\": %f}" % (self.node_name, self.cpu, self.mem, self.disk, self.port)


class VCluster(db.Model):
    __bind_key__ = 'system'
    clusterid = db.Column(db.BigInteger, primary_key=True, autoincrement=False)
    clustername = db.Column(db.String(50))
    ownername = db.Column(db.String(20))
    status = db.Column(db.String(10))
    size = db.Column(db.Integer)
    containers = db.relationship('Container', backref='v_cluster', lazy='dynamic')
    nextcid = db.Column(db.Integer)
    create_time = db.Column(db.DateTime)
    start_time = db.Column(db.String(20))
    stop_time = db.Column(db.DateTime)
    is_warned = db.Column(db.Boolean)
    proxy_server_ip = db.Column(db.String(20))
    proxy_public_ip = db.Column(db.String(20))
    port_mapping = db.relationship('PortMapping', backref='v_cluster', lazy='dynamic')
    billing_history = db.relationship('BillingHistory', backref='v_cluster', lazy='dynamic')

    def __init__(self, clusterid, clustername, ownername, status, size, nextcid, proxy_server_ip, proxy_public_ip):
        self.clusterid = clusterid
        self.clustername = clustername
        self.ownername = ownername
        self.status = status
        self.size = size
        self.nextcid = nextcid
        self.proxy_server_ip = proxy_server_ip
        self.proxy_public_ip = proxy_public_ip
        self.containers = []
        self.port_mapping = []
        self.billing_history = []
        self.create_time = datetime.now()
        self.start_time = "------"
        self.stop_time = datetime.now()
        self.is_warned = False

    def __repr__(self):
        info = {}
        info["clusterid"] = self.clusterid
        info["clustername"] = self.clustername
        info["ownername"] = self.ownername
        info["status"] = self.status
        info["size"] = self.size
        info["proxy_server_ip"] = self.proxy_server_ip
        info["proxy_public_ip"] = self.proxy_public_ip
        info["nextcid"] = self.nextcid
        info["create_time"] = self.create_time.strftime("%Y-%m-%d %H:%M:%S")
        info["start_time"] = self.start_time
        if self.stop_time is None:
            info['stop_time'] = "------"
        else:
            info['stop_time'] = self.stop_time.strftime("%Y-%m-%d %H:%M:%S")
        info["is_warned"] = self.is_warned
        info["containers"] = [dict(eval(str(con))) for con in self.containers]
        info["port_mapping"] = [dict(eval(str(pm))) for pm in self.port_mapping]
        info["billing_history"] = [dict(eval(str(bh))) for bh in self.billing_history]
        #return "{\"clusterid\":\"%d\", \"clustername\":\"%s\", \"ownername\": \"%s\", \"status\":\"%s\", \"size\":\"%d\", \"proxy_server_ip\":\"%s\", \"create_time\":\"%s\"}" % (self.clusterid, self.clustername, self.ownername, self.status, self.size, self.proxy_server_ip, self.create_time.strftime("%Y-%m-%d %H:%M:%S"))
        return json.dumps(info)

class Image(db.Model):
    __bind_key__ = 'system'
    imagename = db.Column(db.String(50))
    id = db.Column(db.Integer, primary_key=True)
    hasPrivate = db.Column(db.Boolean)
    hasPublic = db.Column(db.Boolean)
    ownername = db.Column(db.String(20))
    create_time = db.Column(db.DateTime)
    description = db.Column(db.Text)

    def __init__(self,imagename,hasPrivate,hasPublic,ownername,description):
        self.imagename = imagename
        self.hasPrivate = hasPrivate
        self.hasPublic = hasPublic
        self.ownername = ownername
        self.description = description
        self.create_time = datetime.now()

    def __repr__(self):
        return "{\"id\":\"%d\",\"imagename\":\"%s\",\"hasPrivate\":\"%s\",\"hasPublic\":\"%s\",\"ownername\":\"%s\",\"updatetime\":\"%s\",\"description\":\"%s\"}" % (self.id,self.imagename,str(self.hasPrivate),str(self.hasPublic),self.create_time.strftime("%Y-%m-%d %H:%M:%S"),self.ownername,self.description)

class Batchjob(db.Model):
    __bind_key__ = 'batch'
    id = db.Column(db.String(9), primary_key=True)
    username = db.Column(db.String(10))
    name = db.Column(db.String(30))
    priority = db.Column(db.Integer)
    status = db.Column(db.String(10))
    failed_reason = db.Column(db.Text)
    create_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    billing = db.Column(db.Integer)
    tasks = db.relationship('Batchtask', backref='batchjob', lazy='dynamic')

    def __init__(self,id,username,name,priority):
        self.id = id
        self.username = username
        self.name = name
        self.priority = priority
        self.status = "pending"
        self.failed_reason = ""
        self.create_time = datetime.now()
        self.end_time = None
        self.billing = 0

    def clear(self):
        self.status = "pending"
        self.failed_reason = ""
        self.end_time = None
        self.billing = 0

    def __repr__(self):
        info = {}
        info['job_id'] = self.id
        info['username'] = self.username
        info['job_name'] = self.name
        info['priority'] = self.priority
        info['status'] = self.status
        info['failed_reason'] = self.failed_reason
        info['create_time'] = self.create_time.strftime("%Y-%m-%d %H:%M:%S")
        if self.end_time is None:
            info['end_time'] = "------"
        else:
            info['end_time'] = self.end_time.strftime("%Y-%m-%d %H:%M:%S")
        info['billing'] = self.billing
        return json.dumps(info)

class Batchtask(db.Model):
    __bind_key__ = 'batch'
    id = db.Column(db.String(15), primary_key=True)
    idx = db.Column(db.String(10))
    jobid = db.Column(db.String(9), db.ForeignKey('batchjob.id'))
    status = db.Column(db.String(15))
    failed_reason = db.Column(db.Text)
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    running_time = db.Column(db.Integer)
    billing = db.Column(db.Integer)
    config = db.Column(db.Text)
    tried_times = db.Column(db.Integer)

    def __init__(self, id, idx, config):
        self.id = id
        self.idx = idx
        self.status = "pending"
        self.failed_reason = ""
        self.start_time = None
        self.end_time = None
        self.running_time = 0
        self.billing = 0
        self.config = json.dumps(config)
        self.tried_times = 0

    def clear(self):
        self.status = "pending"
        self.failed_reason = ""
        self.start_time = None
        self.end_time = None
        self.running_time = 0
        self.billing = 0
        self.tried_times = 0

    def __repr__(self):
        info = {}
        info['id'] = self.id
        info['idx'] = self.idx
        info['jobid'] = self.jobid
        info['status'] = self.status
        info['failed_reason'] = self.failed_reason
        if self.start_time is None:
            info['start_time'] = "------"
        else:
            info['start_time'] = self.start_time.strftime("%Y-%m-%d %H:%M:%S")
        if self.end_time is None:
            info['end_time'] = "------"
        else:
            info['end_time'] = self.end_time.strftime("%Y-%m-%d %H:%M:%S")
        info['running_time'] = self.running_time
        info['billing'] = self.billing
        info['config'] = json.loads(self.config)
        info['tried_times'] = self.tried_times
        return json.dumps(info)
