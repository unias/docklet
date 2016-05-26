#!/usr/bin/python3

import os, random
import env
#from log import logger

def loadenv(configpath):
    configfile = open(configpath)
    #logger.info ("load environment from %s" % configpath)
    for line in configfile:
        line = line.strip()
        if line == '':
            continue
        keyvalue = line.split("=")
        if len(keyvalue) < 2:
            continue
        key = keyvalue[0].strip()
        value = keyvalue[1].strip()
        #logger.info ("load env and put env %s:%s" % (key, value))
        os.environ[key] = value

def gen_token():
    return str(random.randint(10000, 99999))+"-"+str(random.randint(10000, 99999))

def netid_decode(netid):
    user_per_vs = env.getenv("USER_PER_VS")
    return [int(netid/user_per_vs) + 1, netid%user_per_vs + 1]

