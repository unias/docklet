#!/usr/bin/python3

"""
design:
    1. When user create an image, it will upload to an image server, at the same time, local host
    will save an image. A time file will be made with them. Everytime a container start by this
    image, the time file will update.
    2. When user save an image, if it is a update option, it will faster than create a new image.
    3. At image server and every physical host, run a shell script to delete the image, which is
    out of time.
    4. We can show every user their own images and the images are shared by other. User can new a
    cluster or scale out a new node by them. And user can remove his own images.
    5. When a remove option occur, the image server will delete it. But some physical host may 
    also maintain it. I think it doesn't matter.
    6. The manage of lvm has been including in this module.
"""


from configparser import ConfigParser
from io import StringIO
import os,sys,subprocess,time,re,datetime,threading

from log import logger
import env
from lvmtool import *

class ImageMgr():
    #def sys_call(self,command):
    #    output = subprocess.getoutput(command).strip()
    #    return None if output == '' else output
    
    def sys_return(self,command):
        return_value = subprocess.call(command,shell=True)
        return return_value
    
    def __init__(self):
        self.NFS_PREFIX = env.getenv('FS_PREFIX') 
        self.imgpath = self.NFS_PREFIX + "/global/images/"
        self.srcpath = env.getenv('DOCKLET_LIB') + "/" 
        self.imageserver = "192.168.6.249"
    
    def datetime_toString(self,dt):
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def string_toDatetime(self,string):
        return datetime.datetime.strptime(string, "%Y-%m-%d %H:%M:%S")
            
    def updateinfo(self,imgpath,image,description):
        image_info_file = open(imgpath+"."+image+".info",'w')
        image_info_file.writelines([self.datetime_toString(datetime.datetime.now()) + "\n", "unshare"])
        image_info_file.close()
        image_description_file = open(imgpath+"."+image+".description", 'w')
        image_description_file.write(description)
        image_description_file.close()

    def dealpath(self,fspath):
        if fspath[-1:] == "/":
            return self.dealpath(fspath[:-1])
        else:
            return fspath
   
    def createImage(self,user,image,lxc,description="Not thing", imagenum=10):
        fspath = self.NFS_PREFIX + "/local/volume/" + lxc
        imgpath = self.imgpath + "private/" + user + "/"

        if not os.path.exists(imgpath+image) and os.path.exists(imgpath):
            cur_imagenum = 0
            for filename in os.listdir(imgpath):
                if os.path.isdir(imgpath+filename):
                    cur_imagenum += 1
            if cur_imagenum >= int(imagenum):
                return [False,"image number limit exceeded"]
        try:
            sys_run("mkdir -p %s" % imgpath+image,True)
            sys_run("rsync -a --delete --exclude=lost+found/ --exclude=root/nfs/ --exclude=dev/ --exclude=mnt/ --exclude=tmp/ --exclude=media/ --exclude=proc/ --exclude=sys/ %s/ %s/" % (self.dealpath(fspath),imgpath+image),True)
            sys_run("rm -f %s" % (imgpath+"."+image+"_docklet_share"),True)
        except Exception as e:
            logger.error(e)

        self.updateinfo(imgpath,image,description)
        logger.info("image:%s from LXC:%s create success" % (image,lxc))
        return [True, "create image success"]

    def prepareImage(self,user,image,fspath):
        imagename = image['name']
        imagetype = image['type']
        imageowner = image['owner']
        if imagename == "base" and imagetype == "base":
            return
        if imagetype == "private":
            imgpath = self.imgpath + "private/" + user + "/"
        else:
            imgpath = self.imgpath + "public/" + imageowner + "/"
        try:
            sys_run("rsync -a --delete --exclude=lost+found/ --exclude=root/nfs/ --exclude=dev/ --exclude=mnt/ --exclude=tmp/ --exclude=media/ --exclude=proc/ --exclude=sys/ %s/ %s/" % (imgpath+imagename,self.dealpath(fspath)),True)
        except Exception as e:
            logger.error(e)

        #self.sys_call("rsync -a --delete --exclude=nfs/ %s/ %s/" % (imgpath+image,self.dealpath(fspath)))
        #self.updatetime(imgpath,image)
        return 
    
    def prepareFS(self,user,image,lxc,size="1000",vgname="docklet-group"):
        rootfs = "/var/lib/lxc/%s/rootfs" % lxc
        layer = self.NFS_PREFIX + "/local/volume/" + lxc
        #check mountpoint
        Ret = sys_run("mountpoint %s" % rootfs)
        if Ret.returncode == 0:
            logger.info("%s not clean" % rootfs)
            sys_run("umount -l %s" % rootfs)
        Ret = sys_run("mountpoint %s" % layer)
        if Ret.returncode == 0:
            logger.info("%s not clean" % layer)
            sys_run("umount -l %s" % layer)
        
        try:
            sys_run("rm -rf %s %s" % (rootfs, layer))
            sys_run("mkdir -p %s %s" % (rootfs, layer))
        except Exception as e:
            logger.error(e)

        
        #prepare volume
        if check_volume(vgname,lxc):
            logger.info("volume %s already exists, delete it")
            delete_volume(vgname,lxc)
        if not new_volume(vgname,lxc,size):
            logger.error("volume %s create failed" % lxc)
            return False
        
        try:
            sys_run("mkfs.ext4 /dev/%s/%s" % (vgname,lxc),True)
            sys_run("mount /dev/%s/%s %s" %(vgname,lxc,layer),True)
            #self.sys_call("mkdir -p %s/overlay %s/work" % (layer,layer))
            #self.sys_call("mount -t overlay overlay -olowerdir=%s/local/basefs,upperdir=%s/overlay,workdir=%s/work %s" % (self.NFS_PREFIX,layer,layer,rootfs))
            sys_run("mount -t aufs -o br=%s=rw:%s/local/basefs=ro+wh -o udba=reval none %s/" % (layer,self.NFS_PREFIX,rootfs),True)
            sys_run("mkdir -p %s/local/temp/%s" % (self.NFS_PREFIX,lxc))

        except Exception as e:
            logger.error(e)

        logger.info("FS has been prepared for user:%s lxc:%s" % (user,lxc))
        #self.prepareImage(user,image,layer+"/overlay")
        self.prepareImage(user,image,layer)
        logger.info("image has been prepared")
        return True

    def deleteFS(self,lxc,vgname="docklet-group"):
        rootfs = "/var/lib/lxc/%s/rootfs" % lxc
        layer = self.NFS_PREFIX + "/local/volume/" + lxc
        lxcpath = "/var/lib/lxc/%s" % lxc
        sys_run("lxc-stop -k -n %s" % lxc)
        #check mountpoint
        Ret = sys_run("mountpoint %s" % rootfs)
        if Ret.returncode == 0:
            sys_run("umount -l %s" % rootfs)
        Ret = sys_run("mountpoint %s" % layer)
        if Ret.returncode == 0:
            sys_run("umount -l %s" % layer)
        if check_volume(vgname, lxc):
            delete_volume(vgname, lxc)
        try:
            sys_run("rm -rf %s %s" % (layer,lxcpath))
            sys_run("rm -rf %s/local/temp/%s" % (self.NFS_PREFIX,lxc))
        except Exception as e:
            logger.error(e)

        return True
    
    def checkFS(self, lxc, vgname="docklet-group"):
        rootfs = "/var/lib/lxc/%s/rootfs" % lxc
        layer = self.NFS_PREFIX + "/local/volume/" + lxc
        if not os.path.isdir(layer):
            sys_run("mkdir -p %s" % layer)
        #check mountpoint
        Ret = sys_run("mountpoint %s" % layer)
        if Ret.returncode != 0:
            sys_run("mount /dev/%s/%s %s" % (vgname,lxc,layer))
        Ret = sys_run("mountpoint %s" % rootfs)
        if Ret.returncode != 0:
            sys_run("mount -t aufs -o br=%s=rw:%s/local/basefs=ro+wh -o udba=reval none %s/" % (layer,self.NFS_PREFIX,rootfs))
        return True


    def removeImage(self,user,image):
        imgpath = self.imgpath + "private/" + user + "/"
        try:
            sys_run("rm -rf %s/" % imgpath+image, True)
            sys_run("rm -f %s" % imgpath+"."+image+".info", True)
            sys_run("rm -f %s" % (imgpath+"."+image+".description"), True)
        except Exception as e:
            logger.error(e)

    def shareImage(self,user,image):
        imgpath = self.imgpath + "private/" + user + "/"
        share_imgpath = self.imgpath + "public/" + user + "/"
        image_info_file = open(imgpath+"."+image+".info", 'r')
        [createtime, isshare] = image_info_file.readlines()
        isshare = "shared"
        image_info_file.close()
        image_info_file = open(imgpath+"."+image+".info", 'w')
        image_info_file.writelines([createtime, isshare])
        image_info_file.close()
        try:
            sys_run("mkdir -p %s" % (share_imgpath + image), True)
            sys_run("rsync -a --delete %s/ %s/" % (imgpath+image,share_imgpath+image), True)
            sys_run("cp %s %s" % (imgpath+"."+image+".info",share_imgpath+"."+image+".info"), True)
            sys_run("cp %s %s" % (imgpath+"."+image+".description",share_imgpath+"."+image+".description"), True)
        except Exception as e:
            logger.error(e)

        

    def unshareImage(self,user,image):
        public_imgpath = self.imgpath + "public/" + user + "/"
        imgpath = self.imgpath + "private/" + user + "/"
        if os.path.exists(imgpath + image):
            image_info_file = open(imgpath+"."+image+".info", 'r')
            [createtime, isshare] = image_info_file.readlines()
            isshare = "unshare"
            image_info_file.close()
            image_info_file = open(imgpath+"."+image+".info", 'w')  
            image_info_file.writelines([createtime, isshare])
            image_info_file.close()
        try:
            sys_run("rm -rf %s/" % public_imgpath+image, True)
            sys_run("rm -f %s" % public_imgpath+"."+image+".info", True)
            sys_run("rm -f %s" % public_imgpath+"."+image+".description", True)
        except Exception as e:
            logger.error(e)

    def get_image_info(self, user, image, imagetype):
        if imagetype == "private": 
            imgpath = self.imgpath + "private/" + user + "/"
        else:
            imgpath = self.imgpath + "public/" + user + "/"
        image_info_file = open(imgpath+"."+image+".info",'r')
        time = image_info_file.readline()
        image_info_file.close()
        image_description_file = open(imgpath+"."+image+".description",'r')
        description = image_description_file.read()
        image_description_file.close()
        if len(description) > 15:
            description = description[:15] + "......"
        return [time, description]

    def get_image_description(self, user, image):
        if image['type'] == "private":
            imgpath = self.imgpath + "private/" + user + "/"
        else:
            imgpath = self.imgpath + "public/" + image['owner'] + "/"
        image_description_file = open(imgpath+"."+image['name']+".description", 'r')
        description = image_description_file.read()
        image_description_file.close()
        return description

    def list_images(self,user):
        images = {}
        images["private"] = []
        images["public"] = {}
        imgpath = self.imgpath + "private/" + user + "/"
        try:
            Ret = sys_run("ls %s" % imgpath, True)
            private_images = str(Ret.stdout,"utf-8").split()
            for image in private_images:
                fimage={}
                fimage["name"] = image
                fimage["isshared"] = self.isshared(user,image)
                [time, description] = self.get_image_info(user, image, "private")
                fimage["time"] = time
                fimage["description"] = description
                images["private"].append(fimage)
        except Exception as e:
            logger.error(e)

        imgpath = self.imgpath + "public" + "/"
        try:
            Ret = sys_run("ls %s" % imgpath, True)
            public_users = str(Ret.stdout,"utf-8").split()
            for public_user in public_users:
                imgpath = self.imgpath + "public/" + public_user + "/"
                try:
                    Ret = sys_run("ls %s" % imgpath, True)
                    public_images = str(Ret.stdout,"utf-8").split()
                    images["public"][public_user] = []
                    for image in public_images:
                        fimage = {}
                        fimage["name"] = image
                        [time, description] = self.get_image_info(public_user, image, "public")
                        fimage["time"] = time
                        fimage["description"] = description
                        images["public"][public_user].append(fimage)
                except Exception as e:
                    logger.error(e)
        except Exception as e:
            logger.error(e)

        return images
    
    def isshared(self,user,image):
        imgpath = self.imgpath + "private/" + user + "/"
        image_info_file = open(imgpath+"."+image+".info",'r')
        [time, isshare] = image_info_file.readlines()
        image_info_file.close()
        if isshare == "shared":
            return "true"
        else:
            return "false"

if __name__ == '__main__':
    mgr = ImageMgr()
    if sys.argv[1] == "prepareImage":
        mgr.prepareImage(sys.argv[2],sys.argv[3],sys.argv[4])
    elif sys.argv[1] == "create":
        mgr.createImage(sys.argv[2],sys.argv[3],sys.argv[4])
    else:
        logger.warning("unknown option")
