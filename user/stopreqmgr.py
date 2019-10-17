import threading, time
from httplib2 import Http
from urllib.parse import urlencode
from queue import Queue
from utils import tools, env
from utils.log import logger

masterips = env.getenv("MASTER_IPS").split(",")
G_masterips = []
for masterip in masterips:
    G_masterips.append(masterip.split("@")[0] + ":" + str(env.getenv("MASTER_PORT")))

# send http request to master
def request_master(url,data):
    global G_masterips
    #logger.info("master_ip:"+str(G_masterip))
    header = {'Content-Type':'application/x-www-form-urlencoded'}
    http = Http()
    for masterip in G_masterips:
        [resp,content] = http.request("http://"+masterip+url,"POST",urlencode(data),headers = header)
        logger.info("response from master:"+content.decode('utf-8'))

class StopAllReqMgr(threading.Thread):
    def __init__(self, maxsize=100, interval=1):
        threading.Thread.__init__(self)
        self.thread_stop = False
        self.interval = 1
        self.q = Queue(maxsize=maxsize)

    def add_request(self,username):
        self.q.put(username)

    def run(self):
        while not self.thread_stop:
            username = self.q.get()
            logger.info("The beans of User(" + str(username) + ") are less than or equal to zero, all his or her vclusters will be stopped.")
            auth_key = env.getenv('AUTH_KEY')
            form = {'username':username, 'auth_key':auth_key}
            request_master("/cluster/stopall/",form)
            self.q.task_done()

            time.sleep(self.interval)

    def stop(self):
        self.thread_stop = True
        return
