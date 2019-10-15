import requests
from flask import abort, session
from webViews.log import logger
import os,sys,inspect,traceback


this_folder = os.path.realpath(os.path.abspath(os.path.split(inspect.getfile(inspect.currentframe    ()))[0]))
src_folder = os.path.realpath(os.path.abspath(os.path.join(this_folder,"../..", "src")))
if src_folder not in sys.path:
    sys.path.insert(0, src_folder)

from utils import env

masterips=env.getenv('MASTER_IPS').split(",")
user_endpoint = "http://" + env.getenv('USER_IP') + ":" + str(env.getenv('USER_PORT'))
master_port=str(env.getenv('MASTER_PORT'))

def getip(masterip):
    return masterip.split("@")[0]

def getname(masterip):
    return masterip.split("@")[1]


class dockletRequest():

    @classmethod
    def post(self, url = '/', data = {}, endpoint = "http://0.0.0.0:9000"):
        #try:
        data = dict(data)
        data['token'] = session['token']
        logger.info ("Docklet Request: user = %s data = %s, url = %s"%(session['username'], data, url))
        reqtype = url.split("/")[1]
        userreq = {
                'login',
                'external_login',
                'register',
                'user',
                'beans',
                'notification',
                'settings',
                'bug'
                }
        if ":" not in endpoint:
            endpoint = "http://"+endpoint+":"+master_port
        if reqtype in userreq:
            result = requests.post(user_endpoint + url, data=data).json()
        else:
            result = requests.post(endpoint + url, data=data).json()
        # logger.info('response content: %s'%response.content)
        # result = response.json()
        if (result.get('success', None) == "false" and result.get('reason', None) == "Unauthorized Action"):
            abort(401)
        if (result.get('Unauthorized', None) == 'True'):
            session['401'] = 'Token Expired'
            abort(401)
        logstr = "Docklet Response: user = %s result = %s, url = %s" % (session['username'], result, url)
        if (sys.getsizeof(logstr) > 512):
            logstr = "Docklet Response: user = %s, url = %s"%(session['username'], url)
        logger.info(logstr)
        return result
        #except:
            #abort(500)

    @classmethod
    def getdesc(self,mastername):
        return env.getenv(mastername+"_desc")[1:-1]

    @classmethod
    def getalldesc(self):
        masterips = self.post_to_all()
        res={}
        for masterip in masterips:
            mastername = getname(masterip)
            res[mastername]=env.getenv(mastername+"_desc")
        return res

    @classmethod
    def post_to_all(self, url = '/', data={}):
        if (url == '/'):
            res = []
            for masterip in masterips:
                try:
                    requests.post("http://"+getip(masterip)+":"+master_port+"/isalive/",data=data)
                except Exception as e:
                    logger.debug(e)
                    continue
                res.append(masterip)
            return res
        data = dict(data)
        data['token'] = session['token']
        logger.info("Docklet Request: user = %s data = %s, url = %s"%(session['username'], data, url))
        result = {}
        for masterip in masterips:
            try:
                res = requests.post("http://"+getip(masterip)+":"+master_port+url,data=data).json()
            except Exception as e:
                logger.debug(traceback.format_exc())
                continue
            if 'success' in res and res['success'] == 'true':
                result[masterip] = res
                logger.info("get result from %s success" % getip(masterip))
            else:
                logger.error("get result from %s failed" % getip(masterip))

        return result

    @classmethod
    def unauthorizedpost(self, url = '/', data = None):
        data = dict(data)
        data_log = {'user': data.get('user', 'external')}
        logger.info("Docklet Unauthorized Request: data = %s, url = %s" % (data_log, url))
        result = requests.post(user_endpoint + url, data = data).json()
        logger.info("Docklet Unauthorized Response: result = %s, url = %s"%(result, url))
        return result
