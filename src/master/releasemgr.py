import threading, time, requests, json, traceback
from utils import env
from utils.log import logger
from utils.model import db, VCluster, Container
import smtplib, datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from master.settings import settings

userpoint = "http://" + env.getenv('USER_IP') + ":" + str(env.getenv('USER_PORT'))
def post_to_user(url = '/', data={}):
    return requests.post(userpoint+url,data=data).json()

_ONE_DAY_IN_SECONDS = 60 * 60 * 24

class ReleaseMgr(threading.Thread):

    def __init__(self, vclustermgr, ulockmgr, check_interval=_ONE_DAY_IN_SECONDS):
        threading.Thread.__init__(self)
        self.thread_stop = False
        self.vclustermgr = vclustermgr
        self.ulockmgr = ulockmgr
        self.check_interval = check_interval
        self.warning_days = int(env.getenv("WARNING_DAYS"))
        self.release_days = int(env.getenv("RELEASE_DAYS"))
        if self.release_days <= self.warning_days:
            self.release_days = self.warning_days+1
        logger.info("[ReleaseMgr] start withe warning_days=%d release_days=%d"%(self.warning_days, self.release_days))

    def _send_email(self, to_address, username, vcluster, days, is_released=True):
        email_from_address = settings.get('EMAIL_FROM_ADDRESS')
        if (email_from_address in ['\'\'', '\"\"', '']):
            return
        text = '<html><h4>Dear '+ username + ':</h4>'
        st_str = vcluster.stop_time.strftime("%Y-%m-%d %H:%M:%S")
        text += '''<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Your workspace/vcluster(name:%s id:%d) in <a href='%s'>%s</a>
                   has been stopped more than %d days now(stopped at:%s). </p>
                ''' % (vcluster.clustername, vcluster.clusterid, env.getenv("PORTAL_URL"), env.getenv("PORTAL_URL"), days, st_str)
        if is_released:
            text += '''<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Therefore, the workspace/vcluster has been released now.</p>
                       <p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<b>And the data in it couldn't be recoverd</b> unless you save it.</p>
                       <p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;You can create new workspace/vcluster if you need.</p>
                    '''
        else:
            #day_d = self.release_days - (datetime.datetime.now() - vcluster.stop_time).days
            release_date = vcluster.stop_time + datetime.timedelta(days=self.release_days)
            day_d = (release_date - datetime.datetime.now()).days
            rd_str = release_date.strftime("%Y-%m-%d %H:%M:%S")
            text += '''<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;It will be released after <b>%s(in about %d days)</b>.</p>
                       <p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<b>And the data in it couldn't be recoverd after releasing.</b></p>
                       <p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Please start or save it before <b>%s(in about %d days)</b> if you want to keep the data.</p>
                    ''' % (rd_str, day_d, rd_str, day_d)
        text += '''<br>
                   <p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Note: DO NOT reply to this email!</p>
                   <br><br>
                   <p> <a href='http://docklet.unias.org'>Docklet Team</a>, SEI, PKU</p>
                '''
        subject = 'Docklet workspace/vcluster releasing alert'
        msg = MIMEMultipart()
        textmsg = MIMEText(text,'html','utf-8')
        msg['Subject'] = Header(subject, 'utf-8')
        msg['From'] = email_from_address
        msg['To'] = to_address
        msg.attach(textmsg)
        s = smtplib.SMTP()
        s.connect()
        try:
            s.sendmail(email_from_address, to_address, msg.as_string())
        except Exception as err:
            logger.error(traceback.format_exc())
        s.close()

    def run(self):
        while not self.thread_stop:
            logger.info("[ReleaseMgr] Begin checking each vcluster if it needs to be released...")

            auth_key = env.getenv('AUTH_KEY')
            res = post_to_user("/master/user/groupinfo/", {'auth_key':auth_key})
            groups = json.loads(res['groups'])
            quotas = {}
            for group in groups:
                quotas[group['name']] = group['quotas']

            vcs = VCluster.query.filter_by(status='stopped').all()
            #logger.info(str(vcs))
            for vc in vcs:
                vc = VCluster.query.get(vc.clusterid)
                if vc.stop_time is None:
                    continue
                days = (datetime.datetime.now() - vc.stop_time).days

                if days >= self.release_days:
                    logger.info("[ReleaseMgr] VCluster(id:%d,user:%s) has been stopped(%s) for more than %d days, it will be released."
                                % (vc.clusterid, vc.ownername, vc.stop_time.strftime("%Y-%m-%d %H:%M:%S"), self.release_days))
                    rc_info = post_to_user("/master/user/recoverinfo/", {'username':vc.ownername,'auth_key':auth_key})
                    logger.info("[ReleaseMgr] %s"%str(rc_info))
                    groupname = rc_info['groupname']
                    user_info = {"data":{"id":rc_info['uid'],"group":groupname,"groupinfo":quotas[groupname]}}
                    self.ulockmgr.acquire(vc.ownername)
                    try:
                        [status, usage_info] = self.vclustermgr.get_clustersetting(vc.clustername, vc.ownername, "all", True)
                        success, msg = self.vclustermgr.delete_cluster(vc.clustername, vc.ownername, json.dumps(user_info))
                        if not success:
                            logger.error("[ReleaseMgr] Can't release VCluster(id:%d,user:%s) for %s"%(vc.clusterid, vc.ownername, msg))
                        else:
                            if status:
                                logger.info("[ReleaseMgr] Release Quota.")
                                post_to_user("/master/user/usageRelease/", {'auth_key':auth_key,'username':vc.ownername,
                                             'cpu':usage_info['cpu'], 'memory':usage_info['memory'],'disk':usage_info['disk']})
                            self._send_email(rc_info['email'], vc.ownername, vc, self.release_days)
                            logger.info("[ReleaseMgr] Succeed to releasing VCluster(id:%d,user:%s) for %s. Send mail to info."%(vc.clusterid, vc.ownername, msg))
                    except Exception as err:
                        logger.error(traceback.format_exc())
                    finally:
                        self.ulockmgr.release(vc.ownername)

                elif days >= self.warning_days:
                    logger.info("[ReleaseMgr] VCluster(id:%d,user:%s) has been stopped(%s) for more than %d days. A warning email will be sent to the user."
                                % (vc.clusterid, vc.ownername, vc.stop_time.strftime("%Y-%m-%d %H:%M:%S"), self.warning_days))
                    if vc.is_warned:
                        logger.info("[ReleaseMgr] VCluster(id:%d,user:%s) has been warned before. Skip it."% (vc.clusterid, vc.ownername))
                        continue
                    rc_info = post_to_user("/master/user/recoverinfo/", {'username':vc.ownername,'auth_key':auth_key})
                    logger.info("[ReleaseMgr] %s"%str(rc_info))
                    self._send_email(rc_info['email'], vc.ownername, vc, self.warning_days, False)
                    vc.is_warned = True

                    try:
                        db.session.commit()
                    except Exception as err:
                        db.session.rollback()
                        logger.warning(traceback.format_exc())
            time.sleep(self.check_interval)

    def stop(self):
        self.thread_stop = True
        return
