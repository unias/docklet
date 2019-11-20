#!/usr/bin/python3

'''
This module consists of three parts:
1.send_beans_email: a function to send email to remind users of their beans.

2.ApplicationMgr: a class that will deal with users' requests about beans application.

3.ApprovalRobot: a automatic robot to examine and approve users' applications.

'''

import threading,datetime,random,time
from utils.model import db,User,ApplyMsg
from master.userManager import administration_required
from utils import env
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from master.settings import settings


# send email to remind users of their beans
def send_beans_email(to_address, username, beans):
    email_from_address = settings.get('EMAIL_FROM_ADDRESS')
    if (email_from_address in ['\'\'', '\"\"', '']):
        return
    #text = 'Dear '+ username + ':\n' + '  Your beans in docklet are less than' + beans + '.'
    text = '<html><h4>Dear '+ username + ':</h4>'
    text += '''<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Your beans in <a href='%s'>docklet</a> are %d now. </p>
               <p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;If your beans are less than or equal to 0, all your worksapces will be stopped.</p>
               <p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Please apply for more beans to keep your workspaces running by following link:</p>
               <p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<a href='%s/beans/application/'>%s/beans/application/</p>
               <br>
               <p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Note: DO NOT reply to this email!</p>
               <br><br>
               <p> <a href='http://docklet.unias.org'>Docklet Team</a>, SEI, PKU</p>
            ''' % (env.getenv("PORTAL_URL"), beans, env.getenv("PORTAL_URL"), env.getenv("PORTAL_URL"))
    text += '<p>'+  str(datetime.datetime.now()) + '</p>'
    text += '</html>'
    subject = 'Docklet beans alert'
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

# a class that will deal with users' requests about beans application.
class ApplicationMgr:

    def __init__(self):
        # create database
        try:
            ApplyMsg.query.all()
        except:
            db.create_all()

    # user apply for beans
    def apply(self,username,number,reason):
        user = User.query.filter_by(username=username).first()
        if user is not None and user.beans >= 1000:
            return [False, "Your beans must be less than 1000."]
        if int(number) < 100 or int(number) > 5000:
            return [False, "Number field must be between 100 and 5000!"]
        applymsgs = ApplyMsg.query.filter_by(username=username).all()
        lasti = len(applymsgs) - 1      # the last index, the last application is also the latest application.
        if lasti >= 0 and applymsgs[lasti].status == "Processing":
            return [False, "You already have a processing application, please be patient."]
        # store the application into the database
        applymsg = ApplyMsg(username,number,reason)
        db.session.add(applymsg)
        db.session.commit()
        return [True,""]

    # get all applications of a user
    def query(self,username):
        applymsgs = ApplyMsg.query.filter_by(username=username).all()
        ans = []
        for msg in applymsgs:
            ans.append(msg.ch2dict())
        return ans

    # get all unread applications
    @administration_required
    def queryUnRead(self,*,cur_user):
        applymsgs = ApplyMsg.query.filter_by(status="Processing").all()
        ans = []
        for msg in applymsgs:
            ans.append(msg.ch2dict())
        return {"success":"true","applymsgs":ans}

    # agree an application
    @administration_required
    def agree(self,msgid,*,cur_user):
        applymsg = ApplyMsg.query.get(msgid)
        if applymsg is None:
            return {"success":"false","message":"Application doesn\'t exist."}
        applymsg.status = "Agreed"
        user = User.query.filter_by(username=applymsg.username).first()
        if user is not None:
            # update users' beans
            user.beans += applymsg.number
        db.session.commit()
        return {"success":"true"}

    # reject an application
    @administration_required
    def reject(self,msgid,*,cur_user):
        applymsg = ApplyMsg.query.get(msgid)
        if applymsg is None:
            return {"success":"false","message":"Application doesn\'t exist."}
        applymsg.status = "Rejected"
        db.session.commit()
        return {"success":"true"}

# a automatic robot to examine and approve users' applications.
class ApprovalRobot(threading.Thread):

    def __init__(self,maxtime=3600):
        threading.Thread.__init__(self)
        self.stop = False
        self.interval = 20
        self.maxtime = maxtime      # The max time that users may wait for from 'processing' to 'agreed'

    def stop(self):
        self.stop = True

    def run(self):
        while not self.stop:
            # query all processing applications
            applymsgs = ApplyMsg.query.filter_by(status="Processing").all()
            for msg in applymsgs:
                secs = (datetime.datetime.now() - msg.time).seconds
                #ranint = random.randint(self.interval,self.maxtime)
                if secs >= self.maxtime:
                    msg.status = "Agreed"
                    user = User.query.filter_by(username=msg.username).first()
                    if user is not None:
                    # update users'beans
                        user.beans += msg.number
                    db.session.commit()
            time.sleep(self.interval)
