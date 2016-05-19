#!/usr/bin/python3

import os, random

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
    return [int(netid/4094) + 1, netid%4094 + 1]
