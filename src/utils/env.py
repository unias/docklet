import os,netifaces

def getenv(key):
    if key == "CLUSTER_NAME":
        return os.environ.get("CLUSTER_NAME", "docklet-vc")
    elif key == "FS_PREFIX":
        return os.environ.get("FS_PREFIX", "/opt/docklet")
    elif key == "CLUSTER_SIZE":
        return int(os.environ.get("CLUSTER_SIZE", 1))
    elif key == "CLUSTER_NET":
        return os.environ.get("CLUSTER_NET", "172.16.0.1/16")
    elif key == "CONTAINER_CPU":
        return int(os.environ.get("CONTAINER_CPU", 100000))
    elif key == "CONTAINER_DISK":
        return int(os.environ.get("CONTAINER_DISK", 1000))
    elif key == "CONTAINER_MEMORY":
        return int(os.environ.get("CONTAINER_MEMORY", 1000))
    elif key == "DISKPOOL_SIZE":
        return int(os.environ.get("DISKPOOL_SIZE", 10000))
    elif key == "ETCD":
        return os.environ.get("ETCD", "localhost:2379")
    elif key == "NETWORK_DEVICE":
        return os.environ.get("NETWORK_DEVICE", "eth0")
    elif key == "MASTER_IP":
        return os.environ.get("MASTER_IP", "0.0.0.0")
    elif key == "MASTER_IPS":
        return os.environ.get("MASTER_IPS", "0.0.0.0@docklet")
    elif key == "MASTER_PORT":
        return int(os.environ.get("MASTER_PORT", 9000))
    elif key == "WORKER_PORT":
        return int(os.environ.get("WORKER_PORT", 9001))
    elif key == "NGINX_PORT":
        return int(os.environ.get("NGINX_PORT", 8080))
    elif key == "PROXY_PORT":
        return int(os.environ.get("PROXY_PORT", 8000))
    elif key == "PROXY_API_PORT":
        return int(os.environ.get("PROXY_API_PORT", 8001))
    elif key == "WEB_PORT":
        return int(os.environ.get("WEB_PORT", 8888))
    elif key == "PORTAL_URL":
        return os.environ.get("PORTAL_URL",
            "http://"+getenv("MASTER_IP") + ":" + str(getenv("NGINX_PORT")))
    elif key == "LOG_LEVEL":
        return os.environ.get("LOG_LEVEL", "DEBUG")
    elif key == "LOG_LIFE":
        return int(os.environ.get("LOG_LIFE", 10))
    elif key == "WEB_LOG_LEVEL":
        return os.environ.get("WEB_LOG_LEVEL", "DEBUG")
    elif key == "STORAGE":
        return os.environ.get("STORAGE", "file")
    elif key =="EXTERNAL_LOGIN":
        return os.environ.get("EXTERNAL_LOGIN", "False")
    elif key =="DATA_QUOTA":
        return os.environ.get("DATA_QUOTA", "False")
    elif key =="DATA_QUOTA_CMD":
        return os.environ.get("DATA_QUOTA_CMD", "gluster volume quota docklet-volume limit-usage %s %s")
    elif key == 'DISTRIBUTED_GATEWAY':
        return os.environ.get("DISTRIBUTED_GATEWAY", "False")
    elif key == "PUBLIC_IP":
        device = os.environ.get("NETWORK_DEVICE","eth0")
        addr = netifaces.ifaddresses(device)
        if 2 in addr:
            return os.environ.get("PUBLIC_IP",addr[2][0]['addr'])
        else:
            return os.environ.get("PUBLIC_IP","0.0.0.0")
    elif key == "NGINX_CONF":
        return os.environ.get("NGINX_CONF","/etc/nginx")
    elif key =="USER_IP":
        return os.environ.get("USER_IP","0.0.0.0")
    elif key =="USER_PORT":
        return int(os.environ.get("USER_PORT",9100))
    elif key =="AUTH_KEY":
        return os.environ.get("AUTH_KEY","docklet")
    elif key =="OPEN_REGISTRY":
        return os.environ.get("OPEN_REGISTRY","False")
    elif key =="APPROVAL_RBT":
        return os.environ.get("APPROVAL_RBT","ON")
    elif key =="ALLOCATED_PORTS":
        return os.environ.get("ALLOCATED_PORTS","10000-65535")
    elif key =="ALLOW_SCALE_OUT":
        return os.environ.get("ALLOW_SCALE_OUT", "False")
    elif key == "WARNING_DAYS":
        return os.environ.get("WARNING_DAYS", "7")
    elif key == "RELEASE_DAYS":
        return os.environ.get("RELEASE_DAYS", "14")
    elif key == "BATCH_ON":
        return os.environ.get("BATCH_ON","True")
    elif key == "BATCH_MASTER_PORT":
        return os.environ.get("BATCH_MASTER_PORT","50050")
    elif key == "BATCH_WORKER_PORT":
        return os.environ.get("BATCH_WORKER_PORT","50051")
    elif key == "BATCH_TASK_CIDR":
        return os.environ.get("BATCH_TASK_CIDR","4")
    elif key == "BATCH_NET":
        return os.environ.get("BATCH_NET","10.16.0.0/16")
    elif key == "BATCH_MAX_THREAD_WORKER":
        return os.environ.get("BATCH_MAX_THREAD_WORKER","5")
    else:
        return os.environ.get(key,"")
