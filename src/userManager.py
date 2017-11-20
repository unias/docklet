'''
userManager for Docklet
provide a class for managing users and usergroups in Docklet
Warning: in some early versions, "token" stand for the instance of class model.User
         now it stands for a string that can be parsed to get that instance.
         in all functions start with "@administration_required" or "@administration_or_self_required", "token" is the instance
Original author: Liu Peidong
'''

from model import db, User, UserGroup, Notification, UserUsage
from functools import wraps
import os, subprocess
import hashlib
import pam
from base64 import b64encode
import env
from settings import settings
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from datetime import datetime
import json
from log import logger
from lvmtool import *

PAM = pam.pam()
fspath = env.getenv('FS_PREFIX')
data_quota = env.getenv('DATA_QUOTA')
data_quota_cmd = env.getenv('DATA_QUOTA_CMD')


if (env.getenv('EXTERNAL_LOGIN').lower() == 'true'):
    from plugin import external_receive

def administration_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if ( ('cur_user' in kwargs) == False):
            return {"success":'false', "reason":"Cannot get cur_user"}
        cur_user = kwargs['cur_user']
        if ((cur_user.user_group == 'admin') or (cur_user.user_group == 'root')):
            return func(*args, **kwargs)
        else:
            return {"success": 'false', "reason": 'Unauthorized Action'}

    return wrapper

def administration_or_self_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if ( (not ('cur_user' in kwargs)) or (not ('user' in kwargs))):
            return {"success":'false', "reason":"Cannot get cur_user or user"}
        cur_user = kwargs['cur_user']
        user = kwargs['user']
        if ((cur_user.user_group == 'admin') or (cur_user.user_group == 'root') or (cur_user.username == user.username)):
            return func(*args, **kwargs)
        else:
            return {"success": 'false', "reason": 'Unauthorized Action'}

    return wrapper

def token_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if ( ('cur_user' in kwargs) == False):
            return {"success":'false', "reason":"Cannot get cur_user"}
        return func(*args, **kwargs)

    return wrapper

def send_activated_email(to_address, username):
    email_from_address = settings.get('EMAIL_FROM_ADDRESS')
    if (email_from_address in ['\'\'', '\"\"', '']):
        return
    #text = 'Dear '+ username + ':\n' + '  Your account in docklet has been activated'
    text = '<html><h4>Dear '+ username + ':</h4>'
    text += '''<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Your account in <a href='%s'>%s</a> has been activated</p>
               <p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Enjoy your personal workspace in the cloud !</p>
               <br>
               <p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Note: DO NOT reply to this email!</p>
               <br><br>
               <p> <a href='http://docklet.unias.org'>Docklet Team</a>, SEI, PKU</p>
            ''' % (env.getenv("PORTAL_URL"), env.getenv("PORTAL_URL"))
    text += '<p>'+  str(datetime.now()) + '</p>'
    text += '</html>'
    subject = 'Docklet account activated'
    msg = MIMEMultipart()
    textmsg = MIMEText(text,'html','utf-8')
    msg['Subject'] = Header(subject, 'utf-8')
    msg['From'] = email_from_address
    msg['To'] = to_address
    msg.attach(textmsg)
    s = smtplib.SMTP()
    s.connect()
    s.sendmail(email_from_address, to_address, msg.as_string())
    s.close()

def send_remind_activating_email(username):
    #admin_email_address = env.getenv('ADMIN_EMAIL_ADDRESS')
    nulladdr = ['\'\'', '\"\"', '']
    email_from_address = settings.get('EMAIL_FROM_ADDRESS')
    admin_email_address = settings.get('ADMIN_EMAIL_ADDRESS')
    if (email_from_address in nulladdr or admin_email_address in nulladdr):
        return
    #text = 'Dear '+ username + ':\n' + '  Your account in docklet has been activated'
    text = '<html><h4>Dear '+ 'admin' + ':</h4>'
    text += '''<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;An activating request for %s in <a href='%s'>%s</a> has been sent</p>
               <p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Please check it !</p>
               <br/><br/>
               <p> Docklet Team, SEI, PKU</p>
            ''' % (username, env.getenv("PORTAL_URL"), env.getenv("PORTAL_URL"))
    text += '<p>'+  str(datetime.utcnow()) + '</p>'
    text += '</html>'
    subject = 'An activating request in Docklet has been sent'
    if admin_email_address[0] == '"':
        admins_addr = admin_email_address[1:-1].split(" ")
    else:
        admins_addr = admin_email_address.split(" ")
    alladdr=""
    for addr in admins_addr:
        alladdr = alladdr+addr+", "
    alladdr=alladdr[:-2]
    msg = MIMEMultipart()
    textmsg = MIMEText(text,'html','utf-8')
    msg['Subject'] = Header(subject, 'utf-8')
    msg['From'] = email_from_address
    msg['To'] = alladdr
    msg.attach(textmsg)
    s = smtplib.SMTP()
    s.connect()
    try:
        s.sendmail(email_from_address, admins_addr, msg.as_string())
    except Exception as e:
        logger.error(e)
    s.close()


class userManager:
    def __init__(self, username = 'root', password = None):
        '''
        Try to create the database when there is none
        initialize 'root' user and 'root' & 'primary' group
        '''
        try:
            User.query.all()
        except:
            db.create_all()
            if password == None:
                #set a random password
                password = os.urandom(16)
                password = b64encode(password).decode('utf-8')
                fsdir = env.getenv('FS_PREFIX')
                f = open(fsdir + '/local/generated_password.txt', 'w')
                f.write("User=%s\nPass=%s\n"%(username, password))
                f.close()
            sys_admin = User(username, hashlib.sha512(password.encode('utf-8')).hexdigest())
            sys_admin.status = 'normal'
            sys_admin.nickname = 'root'
            sys_admin.description = 'Root_User'
            sys_admin.user_group = 'root'
            sys_admin.auth_method = 'local'
            db.session.add(sys_admin)
            path = env.getenv('DOCKLET_LIB')
            subprocess.call([path+"/userinit.sh", username])
            db.session.commit()
        if not os.path.exists(fspath+"/global/sys/quota"):
            groupfile = open(fspath+"/global/sys/quota",'w')
            groups = []
            groups.append({'name':'root', 'quotas':{ 'cpu':'4', 'disk':'2000', 'data':'100', 'memory':'2000', 'image':'10', 'idletime':'24', 'vnode':'8', 'portmapping': '8', 'input_rate_limit':'10000', 'output_rate_limit':'10000'}})
            groups.append({'name':'admin', 'quotas':{'cpu':'4', 'disk':'2000', 'data':'100', 'memory':'2000', 'image':'10', 'idletime':'24', 'vnode':'8', 'portmapping': '8', 'input_rate_limit':'10000', 'output_rate_limit':'10000'}})
            groups.append({'name':'primary', 'quotas':{'cpu':'4', 'disk':'2000', 'data':'100', 'memory':'2000', 'image':'10', 'idletime':'24', 'vnode':'8', 'portmapping': '8', 'input_rate_limit':'10000', 'output_rate_limit':'10000'}})
            groups.append({'name':'foundation', 'quotas':{'cpu':'4', 'disk':'2000', 'data':'100', 'memory':'2000', 'image':'10', 'idletime':'24', 'vnode':'8', 'portmapping': '8', 'input_rate_limit':'10000', 'output_rate_limit':'10000'}})
            groupfile.write(json.dumps(groups))
            groupfile.close()
        if not os.path.exists(fspath+"/global/sys/quotainfo"):
            quotafile = open(fspath+"/global/sys/quotainfo",'w')
            quotas = {}
            quotas['default'] = 'foundation'
            quotas['quotainfo'] = []
            quotas['quotainfo'].append({'name':'cpu', 'hint':'the cpu quota, number of cores, e.g. 4'})
            quotas['quotainfo'].append({'name':'memory', 'hint':'the memory quota, number of MB , e.g. 4000'})
            quotas['quotainfo'].append({'name':'disk', 'hint':'the disk quota, number of MB, e.g. 4000'})
            quotas['quotainfo'].append({'name':'data', 'hint':'the quota of data space, number of GB, e.g. 100'})
            quotas['quotainfo'].append({'name':'image', 'hint':'how many images the user can save, e.g. 10'})
            quotas['quotainfo'].append({'name':'idletime', 'hint':'will stop cluster after idletime, number of hours, e.g. 24'})
            quotas['quotainfo'].append({'name':'vnode', 'hint':'how many containers the user can have, e.g. 8'})
            quotas['quotainfo'].append({'name':'portmapping', 'hint':'how many ports the user can map, e.g. 8'})
            quotas['quotainfo'].append({'name':'input_rate_limit', 'hint':'the ingress speed of the network, number of kbps'})
            quotas['quotainfo'].append({'name':'output_rate_limit', 'hint':'the egress speed of the network, number of kbps'})
            quotafile.write(json.dumps(quotas))
            quotafile.close()
        if not os.path.exists(fspath+"/global/sys/lxc.default"):
            settingfile = open(fspath+"/global/sys/lxc.default", 'w')
            settings = {}
            settings['cpu'] = "2"
            settings["memory"] = "2000"
            settings["disk"] = "2000"
            settingfile.write(json.dumps(settings))
            settingfile.close()

        try:
            UserUsage.query.all()
        except:
            db.create_all()

    def auth_local(self, username, password):
        password = hashlib.sha512(password.encode('utf-8')).hexdigest()
        user = User.query.filter_by(username = username).first()
        if (user == None):
            return {"success":'false', "reason": "User did not exist"}
        if (user.password != password):
            return {"success":'false', "reason": "Wrong password"}
        result = {
            "success": 'true',
            "data":{
                "username" : user.username,
                "avatar" : user.avatar,
                "nickname" : user.nickname,
                "description" : user.description,
                "status" : user.status,
                "group" : user.user_group,
                "token" : user.generate_auth_token(),
            }
        }
        return result

    def auth_pam(self, username, password):
        user = User.query.filter_by(username = username).first()
        pamresult = PAM.authenticate(username, password)
        if (pamresult == False or (user != None and user.auth_method != 'pam')):
            return {"success":'false', "reason": "Wrong password or wrong login method"}
        if (user == None):
            newuser = self.newuser();
            newuser.username = username
            newuser.password = "no_password"
            newuser.nickname = username
            newuser.status = "init"
            newuser.user_group = "primary"
            newuser.auth_method = "pam"
            self.register(user = newuser)
            user = User.query.filter_by(username = username).first()
        result = {
            "success": 'true',
            "data":{
                "username" : user.username,
                "avatar" : user.avatar,
                "nickname" : user.nickname,
                "description" : user.description,
                "status" : user.status,
                "group" : user.user_group,
                "token" : user.generate_auth_token(),
            }
        }
        return result

    def auth_external(self, form):

        if (env.getenv('EXTERNAL_LOGIN') != 'True'):
            failed_result = {'success': 'false', 'reason' : 'external auth disabled'}
            return failed_result

        result = external_receive.external_auth_receive_request(form)

        if (result['success'] != 'True'):
            failed_result =  {'success':'false',  'result': result}
            return failed_result

        username = result['username']
        user = User.query.filter_by(username = username).first()
        if (user != None and user.auth_method == result['auth_method']):
            result = {
                "success": 'true',
                "data":{
                    "username" : user.username,
                    "avatar" : user.avatar,
                    "nickname" : user.nickname,
                    "description" : user.description,
                    "status" : user.status,
                    "group" : user.user_group,
                    "token" : user.generate_auth_token(),
                }
            }
            return result
        if (user != None and user.auth_method != result['auth_method']):
            result = {'success': 'false', 'reason': 'other kinds of account already exists'}
            return result
        #user == None , register an account for external user
        newuser = self.newuser();
        newuser.username = result['username']
        newuser.password = result['password']
        newuser.avatar = result['avatar']
        newuser.nickname = result['nickname']
        newuser.description = result['description']
        newuser.e_mail = result['e_mail']
        newuser.truename = result['truename']
        newuser.student_number = result['student_number']
        newuser.status = result['status']
        newuser.user_group = result['user_group']
        newuser.auth_method = result['auth_method']
        newuser.department = result['department']
        newuser.tel = result['tel']
        self.register(user = newuser)
        user = User.query.filter_by(username = username).first()
        result = {
            "success": 'true',
            "data":{
                "username" : user.username,
                "avatar" : user.avatar,
                "nickname" : user.nickname,
                "description" : user.description,
                "status" : user.status,
                "group" : user.user_group,
                "token" : user.generate_auth_token(),
            }
        }
        return result

    def auth(self, username, password):
        '''
        authenticate a user by username & password
        return a token as well as some user information
        '''
        user = User.query.filter_by(username = username).first()
        if (user == None or user.auth_method =='pam'):
            return self.auth_pam(username, password)
        elif (user.auth_method == 'local'):
            return self.auth_local(username, password)
        else:
            result  = {'success':'false', 'reason':'auth_method error'}
            return result

    def auth_token(self, token):
        '''
        authenticate a user by a token
        when succeeded, return the database iterator
        otherwise return None
        '''
        user = User.verify_auth_token(token)
        return user

    def set_nfs_quota_bygroup(self,groupname, quota):
        if not data_quota == "True":
            return
        users = User.query.filter_by(user_group = groupname).all()
        for user in users:
            self.set_nfs_quota(user.username, quota)

    def set_nfs_quota(self, username, quota):
        if not data_quota == "True":
            return
        nfspath = "/users/%s/data" % username
        try:
            cmd = data_quota_cmd % (nfspath,quota+"GB")
            sys_run(cmd.strip('"'))
        except Exception as e:
            logger.error(e)


    @administration_required
    def query(*args, **kwargs):
        '''
        Usage: query(username = 'xxx', cur_user = token_from_auth)
            || query(ID = a_integer, cur_user = token_from_auth)
        Provide information about one user that administrators need to use
        '''
        if ( 'ID' in kwargs):
            user = User.query.filter_by(id = kwargs['ID']).first()
            if (user == None):
                return {"success":False, "reason":"User does not exist"}
            result = {
                "success":'true',
                "data":{
                    "username" : user.username,
                    "password" : user.password,
                    "avatar" : user.avatar,
                    "nickname" : user.nickname,
                    "description" : user.description,
                    "status" : user.status,
                    "e_mail" : user.e_mail,
                    "student_number": user.student_number,
                    "department" : user.department,
                    "truename" : user.truename,
                    "tel" : user.tel,
                    "register_date" : "%s"%(user.register_date),
                    "group" : user.user_group,
                    "description" : user.description,
                    "beans" : user.beans,
                },
                "token": user
            }
            return result

        if ( 'username' not in kwargs):
            return {"success":'false', "reason":"Cannot get 'username'"}
        username = kwargs['username']
        user = User.query.filter_by(username = username).first()
        if (user == None):
            return {"success":'false', "reason":"User does not exist"}
        result = {
            "success": 'true',
            "data":{
                "username" : user.username,
                "password" : user.password,
                "avatar" : user.avatar,
                "nickname" : user.nickname,
                "description" : user.description,
                "status" : user.status,
                "e_mail" : user.e_mail,
                "student_number": user.student_number,
                "department" : user.department,
                "truename" : user.truename,
                "tel" : user.tel,
                "register_date" : "%s"%(user.register_date),
                "group" : user.user_group,
                "beans" : user.beans,
            },
            "token": user
        }
        return result

    @token_required
    def selfQuery(*args, **kwargs):
        '''
        Usage: selfQuery(cur_user = token_from_auth)
        List informantion for oneself
        '''
        user = kwargs['cur_user']
        groupfile = open(fspath+"/global/sys/quota",'r')
        groups = json.loads(groupfile.read())
        groupfile.close()
        group = None
        for one_group in groups:
            if one_group['name'] == user.user_group:
                group = one_group['quotas']
                break
        else:
            for one_group in groups:
                if one_group['name'] == "primary":
                    group = one_group['quotas']
                    break
        result = {
            "success": 'true',
            "data":{
                "username" : user.username,
                "id": user.id,
                "password" : user.password,
                "avatar" : user.avatar,
                "nickname" : user.nickname,
                "description" : user.description,
                "status" : user.status,
                "e_mail" : user.e_mail,
                "student_number": user.student_number,
                "department" : user.department,
                "truename" : user.truename,
                "tel" : user.tel,
                "register_date" : "%s"%(user.register_date),
                "group" : user.user_group,
                "groupinfo": group,
                "beans" : user.beans,
                "auth_method": user.auth_method,
            },
        }
        return result

    @token_required
    def selfModify(*args, **kwargs):
        '''
        Usage: selfModify(cur_user = token_from_auth, newValue = form)
        Modify informantion for oneself
        '''
        form = kwargs['newValue']
        name = form.get('name', None)
        value = form.get('value', None)
        if (name == None or value == None):
            result = {'success': 'false'}
            return result
        user = User.query.filter_by(username = kwargs['cur_user'].username).first()
        if (name == 'nickname'):
            user.nickname = value
        elif (name == 'description'):
            user.description = value
        elif (name == 'department'):
            user.department = value
        elif (name == 'e_mail'):
            user.e_mail = value
        elif (name == 'tel'):
            user.tel = value
        elif (name == 'password'):
            old_password = hashlib.sha512(form.get('old_value', '').encode('utf-8')).hexdigest()
            if (user.password != old_password):
                result = {'success': 'false'}
                return result
            user.password = hashlib.sha512(value.encode('utf-8')).hexdigest()
        else:
            result = {'success': 'false'}
            return result
        db.session.commit()
        result = {'success': 'true'}
        return result

    @token_required
    def usageQuery(self, *args, **kwargs):
        '''
        Usage: usageQuery(cur_user = token_from_auth)
        Query the quota and usage of user
        '''
        cur_user = kwargs['cur_user']
        groupname = cur_user.user_group
        groupinfo = self.groupQuery(name = groupname)['data']
        usage = UserUsage.query.filter_by(username = cur_user.username).first()
        if usage == None:
            new_usage = UserUsage(cur_user.username)
            db.session.add(new_usage)
            db.session.commit()
            usageinfo = {
                    'username': cur_user.username,
                    'cpu': '0',
                    'memory': '0',
                    'disk': '0'
                    }
        else:
            usageinfo = {
                    'username': usage.username,
                    'cpu': usage.cpu,
                    'memory': usage.memory,
                    'disk': usage.disk
                    }
        settingfile = open(fspath+"/global/sys/lxc.default" , 'r')
        defaultsetting = json.loads(settingfile.read())
        settingfile.close()

        return {'success': 'true', 'quota' : groupinfo, 'usage' : usageinfo, 'default': defaultsetting }

    @token_required
    def usageInc(self, *args, **kwargs):
        '''
        Usage: usageModify(cur_user = token_from_auth, modification = data_from_form)
        Modify the usage info of user
        '''
        cur_user = kwargs['cur_user']
        modification = kwargs['modification']
        logger.info("record usage for user:%s" % cur_user.username)
        groupname = cur_user.user_group
        groupinfo = self.groupQuery(name = groupname)['data']
        usage = UserUsage.query.filter_by(username = cur_user.username).first()
        if usage == None:
            new_usage = UserUsage(cur_user.username)
            db.session.add(new_usage)
            db.session.commit()
            usage = UserUsage.query.filter_by(username = cur_user.username).first()
        if int(modification['cpu']) <= 0 or int(modification['memory']) <= 0 or int(modification['disk']) <= 0:
            return {'success':False, 'result':"cpu,memory and disk setting cannot less than zero"}
        cpu = int(usage.cpu) + int(modification['cpu'])
        memory = int(usage.memory) + int(modification['memory'])
        disk = int(usage.disk) + int(modification['disk'])
        if cpu > int(groupinfo['cpu']):
            logger.error("cpu quota exceed, user:%s" % cur_user.username)
            return {'success':False, 'result':"cpu quota exceed"}
        if memory > int(groupinfo['memory']):
            logger.error("memory quota exceed, user:%s" % cur_user.username)
            return {'success':False, 'result':"memory quota exceed"}
        if disk > int(groupinfo['disk']):
            logger.error("disk quota exceed, user:%s" % cur_user.username)
            return {'success':False, 'result':"disk quota exceed"}
        usage.cpu = str(cpu)
        usage.memory = str(memory)
        usage.disk = str(disk)
        db.session.commit()
        return {'success':True, 'result':"distribute the resource"}

    @token_required
    def usageRecover(self, *args, **kwargs):
        '''
        Usage: usageModify(cur_user = token_from_auth, modification = data_from_form)
        Recover the usage info when create container failed
        '''
        cur_user = kwargs['cur_user']
        modification = kwargs['modification']
        logger.info("recover usage for user:%s" % cur_user.username)
        usage = UserUsage.query.filter_by(username = cur_user.username).first()
        if usage == None:
            new_usage = UserUsage(cur_user.username)
            db.session.add(new_usage)
            db.session.commit()
            usage = UserUsage.query.filter_by(username = cur_user.username).first()
            return True
        cpu = int(usage.cpu) - int(modification['cpu'])
        memory = int(usage.memory) - int(modification['memory'])
        disk = int(usage.disk) - int(modification['disk'])
        if cpu < 0:
            cpu = 0
        if memory < 0:
            memory = 0
        if disk < 0:
            disk = 0
        usage.cpu = str(cpu)
        usage.memory = str(memory)
        usage.disk = str(disk)
        db.session.commit()
        return {'success':True}

    @token_required
    def usageRelease(self, *args, **kwargs):
        cur_user = kwargs['cur_user']
        cpu = kwargs['cpu']
        memory = kwargs['memory']
        disk = kwargs['disk']
        usage = UserUsage.query.filter_by(username = cur_user.username).first()
        if usage == None:
            new_usage = UserUsage(cur_user.username)
            db.session.add(new_usage)
            db.session.commit()
            return {'success':True}
        nowcpu = int(usage.cpu) - int(cpu)
        nowmemory = int(usage.memory) - int(memory)
        nowdisk = int(usage.disk) - int(disk)
        if nowcpu < 0:
            nowcpu = 0
        if nowmemory < 0:
            nowmemory = 0
        if nowdisk < 0:
            nowdisk = 0
        usage.cpu = str(nowcpu)
        usage.memory = str(nowmemory)
        usage.disk = str(nowdisk)
        db.session.commit()
        return {'success':True}

    def initUsage(*args, **kwargs):
        """
        init the usage info when start docklet with init mode
        """
        usages = UserUsage.query.all()
        for usage in usages:
            usage.cpu = "0"
            usage.memory = "0"
            usage.disk = "0"
        db.session.commit()
        return True

    @administration_required
    def userList(*args, **kwargs):
        '''
        Usage: list(cur_user = token_from_auth)
        List all users for an administrator
        '''
        alluser = User.query.all()
        result = {
            "success": 'true',
            "data":[]
        }
        for user in alluser:
            userinfo = [
                    user.id,
                    user.username,
                    user.truename,
                    user.e_mail,
                    user.tel,
                    "%s"%(user.register_date),
                    user.status,
                    user.user_group,
                    user.beans,
                    '',
            ]
            result["data"].append(userinfo)
        return result

    @administration_required
    def groupList(*args, **kwargs):
        '''
        Usage: list(cur_user = token_from_auth)
        List all groups for an administrator
        '''
        groupfile = open(fspath+"/global/sys/quota",'r')
        groups = json.loads(groupfile.read())
        groupfile.close()
        quotafile = open(fspath+"/global/sys/quotainfo",'r')
        quotas = json.loads(quotafile.read())
        quotafile.close()
        result = {
            "success": 'true',
            "groups": groups,
            "quotas": quotas['quotainfo'],
            "default": quotas['default'],
        }
        return result

    @administration_required
    def change_default_group(*args, **kwargs):
        form = kwargs['form']
        default_group = form.get('defaultgroup')
        quotafile = open(fspath+"/global/sys/quotainfo",'r')
        quotas = json.loads(quotafile.read())
        quotafile.close()
        quotas['default'] = default_group
        quotafile = open(fspath+"/global/sys/quotainfo",'w')
        quotafile.write(json.dumps(quotas))
        quotafile.close()
        return { 'success':'true', 'action':'change default group' }


    def groupQuery(self, *args, **kwargs):
        '''
        Usage: groupQuery(name = XXX, cur_user = token_from_auth)
        List a group for an administrator
        '''
        groupfile = open(fspath+"/global/sys/quota",'r')
        groups = json.loads(groupfile.read())
        groupfile.close()
        for group in groups:
            if group['name'] == kwargs['name']:
                result = {
                    "success":'true',
                    "data": group['quotas'],
                }
                return result
        else:
            return {"success":False, "reason":"Group does not exist"}

    @administration_required
    def groupListName(*args, **kwargs):
        '''
        Usage: grouplist(cur_user = token_from_auth)
        List all group names for an administrator
        '''
        groupfile = open(fspath+"/global/sys/quota",'r')
        groups = json.loads(groupfile.read())
        groupfile.close()
        result = {
            "groups": [],
        }
        for group in groups:
            result["groups"].append(group['name'])
        return result

    @administration_required
    def groupModify(self, *args, **kwargs):
        '''
        Usage: groupModify(newValue = dict_from_form, cur_user = token_from_auth)
        '''
        groupfile = open(fspath+"/global/sys/quota",'r')
        groups = json.loads(groupfile.read())
        groupfile.close()
        for group in groups:
            if group['name'] == kwargs['newValue'].get('groupname',None):
                form = kwargs['newValue']
                for key in form.keys():
                    if key == "data":
                        if not group['quotas'][key] == form.get(key):
                            self.set_nfs_quota_bygroup(group['name'],form.get(key))
                    else:
                        pass

                    if key == "groupname" or key == "token":
                        pass
                    else:
                        group['quotas'][key] = form.get(key)
                groupfile = open(fspath+"/global/sys/quota",'w')
                groupfile.write(json.dumps(groups))
                groupfile.close()
                return {"success":'true'}
        else:
            return {"success":'false', "reason":"UserGroup does not exist"}

    @administration_required
    def modify(self, *args, **kwargs):
        '''
        modify a user's information in database
        will send an e-mail when status is changed from 'applying' to 'normal'
        Usage: modify(newValue = dict_from_form, cur_user = token_from_auth)
        '''
        if ( kwargs['newValue'].get('Instruction', '') == 'Activate'):
            user_modify = User.query.filter_by(id = kwargs['newValue'].get('ID', None)).first()
            user_modify.status = 'normal'
            send_activated_email(user_modify.e_mail, user_modify.username)
            db.session.commit()
            return {"success": "true"}

        if ( kwargs['newValue'].get('password', '') != ''):
            user_modify = User.query.filter_by(username = kwargs['newValue'].get('username', None)).first()
            new_password = kwargs['newValue'].get('password','')
            new_password = hashlib.sha512(new_password.encode('utf-8')).hexdigest()
            user_modify.password = new_password
            db.session.commit()
            return {"success": "true"}

        user_modify = User.query.filter_by(username = kwargs['newValue'].get('username', None)).first()
        if (user_modify == None):

            return {"success":'false', "reason":"User does not exist"}

        #try:
        form = kwargs['newValue']
        user_modify.truename = form.get('truename', '')
        user_modify.e_mail = form.get('e_mail', '')
        user_modify.department = form.get('department', '')
        user_modify.student_number = form.get('student_number', '')
        user_modify.tel = form.get('tel', '')
        user_modify.user_group = form.get('group', '')
        user_modify.auth_method = form.get('auth_method', '')
        if (user_modify.status == 'applying' and form.get('status', '') == 'normal'):
            send_activated_email(user_modify.e_mail, user_modify.username)
        user_modify.status = form.get('status', '')
        #if (form.get('password', '') != ''):
            #new_password = form.get('password','')
            #new_password = hashlib.sha512(new_password.encode('utf-8')).hexdigest()
            #user_modify.password = new_password
            #self.chpassword(cur_user = user_modify, password = form.get('password','no_password'))
        #modify password in another function now

        db.session.commit()
        res = self.groupQuery(name=user_modify.user_group)
        if res['success']:
            self.set_nfs_quota(user_modify.username,res['data']['data'])
        return {"success":'true'}
        #except:
            #return {"success":'false', "reason":"Something happened"}

    @token_required
    def chpassword(*args, **kwargs):
        '''
        Usage: chpassword(cur_user = token_from_auth, password = 'your_password')
        '''
        cur_user = kwargs['cur_user']
        cur_user.password = hashlib.sha512(kwargs['password'].encode('utf-8')).hexdigest()



    def newuser(*args, **kwargs):
        '''
        Usage : newuser()
        The only method to create a new user
        call this method first, modify the return value which is a database row instance,then call self.register()
        '''
        user_new = User('newuser', 'asdf1234')
        quotafile = open(fspath+"/global/sys/quotainfo",'r')
        quotas = json.loads(quotafile.read())
        quotafile.close()
        user_new.user_group = quotas['default']
        user_new.avatar = 'default.png'
        return user_new

    def register(self, *args, **kwargs):
        '''
        Usage: register(user = modified_from_newuser())
        '''

        if (kwargs['user'].username == None or kwargs['user'].username == ''):
            return {"success":'false', "reason": "Empty username"}
        user_check = User.query.filter_by(username = kwargs['user'].username).first()
        if (user_check != None and user_check.status != "init"):
            #for the activating form
            return {"success":'false', "reason": "Unauthorized action"}
        newuser = kwargs['user']
        if (user_check != None and (user_check.status == "init")):
            db.session.delete(user_check)
            db.session.commit()
        else:
            newuser.password = hashlib.sha512(newuser.password.encode('utf-8')).hexdigest()
        db.session.add(newuser)
        db.session.commit()

        # if newuser status is normal, init some data for this user
        # now initialize for all kind of users
        #if newuser.status == 'normal':
        path = env.getenv('DOCKLET_LIB')
        subprocess.call([path+"/userinit.sh", newuser.username])
        res = self.groupQuery(name=newuser.user_group)
        if res['success']:
            self.set_nfs_quota(newuser.username,res['data']['data'])
        return {"success":'true'}

    @administration_required
    def quotaadd(*args, **kwargs):
        form = kwargs.get('form')
        quotaname = form.get("quotaname")
        default_value = form.get("default_value")
        hint = form.get("hint")
        if (quotaname == None):
            return { "success":'false', "reason": "Empty quota name"}
        if (default_value == None):
            default_value = "--"
        groupfile = open(fspath+"/global/sys/quota",'r')
        groups = json.loads(groupfile.read())
        groupfile.close()
        for group in groups:
            group['quotas'][quotaname] = default_value
        groupfile = open(fspath+"/global/sys/quota",'w')
        groupfile.write(json.dumps(groups))
        groupfile.close()
        quotafile = open(fspath+"/global/sys/quotainfo",'r')
        quotas = json.loads(quotafile.read())
        quotafile.close()
        quotas['quotainfo'].append({'name':quotaname, 'hint':hint})
        quotafile = open(fspath+"/global/sys/quotainfo",'w')
        quotafile.write(json.dumps(quotas))
        quotafile.close()
        return {"success":'true'}

    @administration_required
    def groupadd(*args, **kwargs):
        form = kwargs.get('form')
        groupname = form.get("groupname")
        if (groupname == None):
            return {"success":'false', "reason": "Empty group name"}
        groupfile = open(fspath+"/global/sys/quota",'r')
        groups = json.loads(groupfile.read())
        groupfile.close()
        group = {
            'name': groupname,
            'quotas': {}
        }
        for key in form.keys():
            if key == "groupname" or key == "token":
                pass
            else:
                group['quotas'][key] = form.get(key)
        groups.append(group)
        groupfile = open(fspath+"/global/sys/quota",'w')
        groupfile.write(json.dumps(groups))
        groupfile.close()
        return {"success":'true'}

    @administration_required
    def groupdel(*args, **kwargs):
        name = kwargs.get('name', None)
        if (name == None):
            return {"success":'false', "reason": "Empty group name"}
        groupfile = open(fspath+"/global/sys/quota",'r')
        groups = json.loads(groupfile.read())
        groupfile.close()
        for group in groups:
            if group['name'] == name:
                groups.remove(group)
                break
        groupfile = open(fspath+"/global/sys/quota",'w')
        groupfile.write(json.dumps(groups))
        groupfile.close()
        return {"success":'true'}

    @administration_required
    def lxcsettingList(*args, **kwargs):
        lxcsettingfile = open(fspath+"/global/sys/lxc.default", 'r')
        lxcsetting = json.loads(lxcsettingfile.read())
        lxcsettingfile.close()
        return {"success": 'true', 'data':lxcsetting}

    @administration_required
    def chlxcsetting(*args, **kwargs):
        form = kwargs['form']
        lxcsetting = {}
        lxcsetting['cpu'] = form['lxcCpu']
        lxcsetting['memory'] = form['lxcMemory']
        lxcsetting['disk'] = form['lxcDisk']
        lxcsettingfile = open(fspath+"/global/sys/lxc.default", 'w')
        lxcsettingfile.write(json.dumps(lxcsetting))
        lxcsettingfile.close()
        return {"success": 'true'}

    @administration_required
    def cloud_account_query(*args, **kwargs):
        accountfile = open(fspath+"/global/sys/cloudaccount", 'r')
        account = json.loads(accountfile.read())
        accountfile.close()
        return {"success": 'true', 'accounts':account}

    @administration_required
    def cloud_account_add(*args, **kwargs):
        form = kwargs.get('form')
        accountfile = open(fspath+"/global/sys/cloudaccount", 'r')
        account = json.loads(accountfile.read())
        accountfile.close()
        account.append(
                { 'cloudname' : form['cloudname'],
                    'username' : form['username'],
                    'password' : form['password'],
                })
        accountfile = open(fspath+"/global/sys/cloudaccount", 'w')
        accountfile.write(json.dumps(account))
        accountfile.close()
        return {"success": 'true'}

    @administration_required
    def cloud_account_del(*args, **kwargs):
        form = kwargs.get('form')
        cloudname = form['cloudname']
        accountfile = open(fspath+"/global/sys/cloudaccount", 'r')
        account = json.loads(accountfile.read())
        accountfile.close()
        for acc in account:
            if acc['cloudname'] == cloudname:
                account.remove(acc)
                break
        accountfile = open(fspath+"/global/sys/cloudaccount", 'w')
        accountfile.write(json.dumps(account))
        accountfile.close()
        return {"success": 'true'}

    @administration_required
    def cloud_account_modify(*args, **kwargs):
        form = kwargs.get('form')
        cloudname = form['cloudname']
        accountfile = open(fspath+"/global/sys/cloudaccount", 'r')
        account = json.loads(accountfile.read())
        accountfile.close()
        for acc in account:
            if acc['cloudname'] == cloudname:
                acc['username'] = form['username']
                acc['password'] = form['password']
                break
        accountfile = open(fspath+"/global/sys/cloudaccount", 'w')
        accountfile.write(json.dumps(account))
        accountfile.close()
        return {"success": "true"}


    def queryForDisplay(*args, **kwargs):
        '''
        Usage: queryForDisplay(user = token_from_auth)
        Provide information about one user that administrators need to use
        '''

        if ( 'user' not in kwargs):
            return {"success":'false', "reason":"Cannot get 'user'"}
        user = kwargs['user']
        if (user == None):
            return {"success":'false', "reason":"User does not exist"}
        result = {
            "success": 'true',
            "data":{
                "username" : user.username,
                "password" : user.password,
                "avatar" : user.avatar,
                "nickname" : user.nickname,
                "description" : user.description,
                "status" : user.status,
                "e_mail" : user.e_mail,
                "student_number": user.student_number,
                "department" : user.department,
                "truename" : user.truename,
                "tel" : user.tel,
                "register_date" : "%s"%(user.register_date),
                "group" : user.user_group,
                "auth_method": user.auth_method,
            }
        }
        return result

#    def usermodify(rowID, columnID, newValue, cur_user):
#        '''not used now'''
#        user = um.query(ID = request.form["rowID"], cur_user = root).get('token',  None)
#        result = um.modify(user = user, columnID = request.form["columnID"], newValue = request.form["newValue"], cur_user = root)
#        return json.dumps(result)
