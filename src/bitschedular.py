#  from monitor import summary_resources, summary_usage, curr_usage
#  from monitor import summary_usage_per_user, summary_usage_per_user
#  from monitor import curr_usage_per_machine
from log import logger
import nodemgr
import bisect, uuid
import restricted_price #受限制资源的价格,定值
import machine_num #目前已有的机器数量
import machine_to_rent_list#从将要租借sever的网站上获取的各种类型的sever的信息,按资源数从小到大排列
import rent
import releasemachine #用于租借和释放sever的函数
class Machine_to_rent(object):
    __slots__='id','resources','price'
import price_to_rent 
#price_to_rent是从网站上租借sever时平均每slot每小时的价格，digitalocean中不同机器上这一数值是相同的，这里以bidprice
#是否达到这一固定价格作为标准，因为当已有物理机全部被使用时，工作负载已经处于较高水平，有很高可能租借的sever的剩余资源
#也会被充分利用
global times_of_renting #记录自动租借sever的次数以供管理员参考，决定是否要长期增加sever
#下面函数主要是加入了租借新机器这一选择，以及租借sever上的资源分配和释放，此外对抢占机器的选择，
#对分配不可靠资源的判断等地方根据个人理解做出了修改，
class AllocationOfTask(object):
    __slots__ = 'id','userid','jobid','taskid','resources','bidprice','type','machineid','lxc_name'
    def __key(self):
        return (self.userid, self.jobid, self.taskid, self.machineid)
    def __hash__(self):
        return hash(self.__key())
    def __lt__(self, other):
        if self.bidprice < other.bidprice:
            return True
        else:
            return False
    def __le__(self, other): 
        if self.bidprice <= other.bidprice:
            return True
        else:
            return False
    def __eq__(self, other):
        return self.bidprice==other.bidprice #我认为此处应当判断的是bidprice是否相等而不是key
    def __ne__(self, other):
        return self.bidprice != other.bidprice
    def __gt__(self, other):
        if self.bidprice > other.bidprice:
            return True
        else:
            return False
    def __ge__(self, other):
        if self.bidprice >=  other.bidprice:
            return True
        else:
            return False
         
class AllocationOfMachine(object):
    __slots__ = ['machineid',"resources","reliable_resources_allocation_summary",
                'reliable_allocations', 'restricted_allocations','rented']
                #此处加入了一个rented属性，如果是短期租借的server，只运行bidprice超过price_to_rent的请求可靠资源的任务
    def __lt__(self, other):
        if self.reliable_resources_allocation_summary < other.reliable_resources_allocation_summary:
            return True
        else:
            return False
    def __le__(self, other):
        if self.reliable_resources_allocation_summary <= other.reliable_resources_allocation_summary:
            return True
        else:
            return False
    def __eq__(self, other):
        if self.reliable_resources_allocation_summary == other.reliable_resources_allocation_summary:
            return True
        else:
            return False
    def __ne__(self, other):
        if self.reliable_resources_allocation_summary != other.reliable_resources_allocation_summary:
            return True
        else:
            return False
    def __gt__(self, other):
        if self.reliable_resources_allocation_summary > other.reliable_resources_allocation_summary:
            return True
        else:
            return False
    def __ge__(self, other):
        if self.reliable_resources_allocation_summary >=  other.reliable_resources_allocation_summary:
            return True
        else:
            return False

usages_list=[]
machine_usage_dict = {}
machine_allocation_dict = {}
allocations_list = []
nodemanager = {}
lxcname_allocation_dict = {}

def init_allocations():
    global machine_allocation_dict
    global allocations_list
    global nodemanager
    global usages_list
    global machine_usage_dict
    logger.info("init allocations:")

    machines = nodemanager.get_allnodes()
    for machine in machines:
        allocation = AllocationOfMachine()
        allocation.machineid = machine
        allocation.resources = 2
        allocation.reliable_resources_allocation_summary = 0
        allocation.reliable_allocations = []
        allocation.restricted_allocations = []
        allocations.rented=False
        
        machine_allocation_dict[machine] = allocation
        bisect.insort(allocations_list,allocation)
        
        usage_of_machine = {}
        usage_of_machine['machineid']=machine
        usage_of_machine['cpu_utilization']=0.1
        
        usages_list.append(usage_of_machine)
        machine_usage_dict[machine] = 0.1
        
        #logger.info(allocations_list)
        #logger.info(allocations_dic)

def addNode(machineid,resources=2,rented=False):
    logger.info("add node")
    allocation = AllocationOfMachine()
    allocation.machineid = machineid
    allocation.resources = resources
    allocation.reliable_resources_allocation_summary = 0
    allocation.reliable_allocations = []
    allocation.restricted_allocations = []
    allocation.rented=rented
    machine_allocation_dict[machineid] = allocation
    bisect.insort(allocations_list,allocation)
    
    usage_of_machine = {}
    usage_of_machine['machineid']=machineid
    usage_of_machine['cpu_utilization']=0.1
    
    usages_list.append(usage_of_machine)
    machine_usage_dict[machineid] = 0.1
        
def has_reliable_resources(allocation_of_machine,task_allocation_request):
    if(task_allocation_request['resources']
       +allocation_of_machine.reliable_resources_allocation_summary
       <= allocation_of_machine.resources):
        return True
    else:
        return False

def can_preempt_reliable_resources(allocation_of_machine, task_allocation_request):
#allocation_of_mation的reliable_allocations应当是按照bidprice从小到大顺序排列的，否则不使用break,因为没有找到bisect，所以不知道insort时是否排序
    to_be_preempted=0
    preempt_cost=0
    for a in allocation_of_machine.reliable_allocations:
        if (a.bidprice < task_allocation_request['bidprice']):
            to_be_preempted += a.resources
            preempt_cost +=a.bidprice
            if to_be_preempted >= task_allocation_request['resources']:
                return preempt_cost
        else:
             break
    return -1

# def has_restricted_resources(allocation_of_machine,task_allocation_request):
#    if(task_allocation_request['resources']
#      + machine_usage_dict[allocation_of_machine.machineid]
#      < allocation_of_machine.resources * 0.8):
#        return True
#    else:
#        return False#以slot为单位进行资源分配时，resourses都是很小的整数，比如初始化中的2，而不是真正的CPU和memory
        #所以此处的0.8倍有些不妥，另外既然是restricted_resourses，也就是说随时会被压缩，我认为不需要比较是否有足够资源剩余

def allocate_reliable_task(allocation_of_machine,task_allocation_request):
    global lxcname_allocation_dict
    #if(has_reliable_resources(allocation_of_machine,task_allocation_request)):
    #因为在allocate中是使用has_reliable_resources函数检查过才执行这个函数的，所以可以省略这个判断，会减慢速度
        allocation_of_task = AllocationOfTask()
        allocation_of_task.id = uuid.uuid4()
        allocation_of_task.userid = task_allocation_request['userid']
        allocation_of_task.jobid = task_allocation_request['jobid']
        allocation_of_task.taskid = task_allocation_request['taskid']
        allocation_of_task.resources = task_allocation_request['resources']
        allocation_of_task.bidprice = task_allocation_request['bidprice']
        allocation_of_task.machineid = allocation_of_machine.machineid
        allocation_of_task.lxc_name = (allocation_of_task.userid
                                       + "-"
                                       + str(allocation_of_task.jobid)
                                       + "-"
                                       + str(allocation_of_task.taskid))
        allocation_of_task.type = 'reliable'
        bisect.insort(allocation_of_machine.reliable_allocations, allocation_of_task)
        lxcname_allocation_dict[allocation_of_task.lxc_name]=allocation_of_task
        
        # update allocation_summary
        allocation_of_machine.reliable_resources_allocation_summary += task_allocation_request['resources']
        return {'status':'success', 'allocation':allocation_of_task}
#将分配可靠资源和抢占分开了，在其中插入了检查是否达到租借新sever的标准，这样如果不想让自己的任务被抢占，不需要实时匹配
#最高竞价这样不透明的方法，而是只要bid_price达到price_to_rent就好
def try_preempt_resources(allocation_of_machine,task_allocation_request):
        can_preempt = 0
        can_preempt_count = 0
        # 把被抢占的可靠资源变成受限制资源
        for a in allocation_of_machine.reliable_allocations:
            can_preempt+=a.resources
            can_preempt_count+=1
            # 转成受限
            a.type = 'restricted'
            a.bidprice = restricted_price
            bisect.insort(allocation_of_machine.restricted_allocations,a)
            # 更新allocation_machine的reliable_resources_allocation_summary
            allocation_of_machine.reliable_resources_allocation_summary -= a.resources
            if can_preempt>=task_allocation_request['resources']:
                break
            
        # to-do 调整这些容器的cgroup设置，使用软限制模式，只能使用空闲资源
        for i in range(0,can_preempt_count):
            change_cgroup_settings(allocation_of_machine.reliable_allocations[i], 'restricted')
#此处设想将被抢占任务的价格改为统一的restricte resources 的价格，那么被抢占后计费中价格也需要修改，但是不确定计费中是
#是按整个job计费还是单个task计费，待定


        # 把被抢占的可靠资源从reliable_allocations中删除
        del allocation_of_machine.reliable_allocations[0:can_preempt_count]

        allocation_of_task = AllocationOfTask()
        allocation_of_task.id = uuid.uuid4()
        allocation_of_task.userid = task_allocation_request['userid']
        allocation_of_task.jobid = task_allocation_request['jobid']
        allocation_of_task.taskid = task_allocation_request['taskid']
        allocation_of_task.resources = task_allocation_request['resources']
        allocation_of_task.bidprice = task_allocation_request['bidprice']
        allocation_of_task.resources = task_allocation_request['resources']
        allocation_of_task.machineid = allocation_of_machine.machineid
        allocation_of_task.lxc_name = (allocation_of_task.userid
                                       + "-"
                                       + str(allocation_of_task.jobid)
                                       + "-"
                                       + str(allocation_of_task.taskid))
        allocation_of_task.type = 'reliable'
        bisect.insort(allocation_of_machine.reliable_allocations, allocation_of_task)
        lxcname_allocation_dict[allocation_of_task.lxc_name]=allocation_of_task
        
        # update allocation_summary
        allocation_of_machine.reliable_resources_allocation_summary += task_allocation_request['resources']
        return {'status':'success', 'allocation':allocation_of_task}


def allocate_task_restricted(allocation_of_machine,task_allocation_request):
  ##  if(has_restricted_resources(allocation_of_machine,task_allocation_request)):
  #我认为此处可以不予以检查，因为restricted resources 只是限制资源使用最大值，即使分配任务时检查发现有足够的资源，
  #开始运行后这些资源也很快就会被压缩，所以不如不考虑剩余资源是否足够直接把task分配过去，这样至少不会创建任务失败，
  #任务总是能运行
        allocation_of_task = AllocationOfTask()
        allocation_of_task.id = uuid.uuid4()
        allocation_of_task.userid = task_allocation_request['userid']
        allocation_of_task.jobid = task_allocation_request['jobid']
        allocation_of_task.taskid = task_allocation_request['taskid']
        allocation_of_task.resources = task_allocation_request['resources']
        allocation_of_task.bidprice = task_allocation_request['bidprice']
        allocation_of_task.resources = task_allocation_request['resources']
        allocation_of_task.machineid = allocation_of_machine.machineid
        allocation_of_task.lxc_name = (allocation_of_task.userid
                                       + "-"
                                       + str(allocation_of_task.jobid)
                                       + "-"
                                       + str(allocation_of_task.taskid))
        allocation_of_task.type = 'restricted'
        bisect.insort(allocation_of_machine.restricted_allocations, allocation_of_task)
        lxcname_allocation_dict[allocation_of_task.lxc_name]=allocation_of_task
        return {'status':'success', 'allocation':allocation_of_task}

 #   else:
  #      return {'status': 'failed'}

def allocate(job_allocation_request):
    logger.debug("try allocate")
    print ("try allocate")
    global machine_allocation_dict
    global allocations_list
    job_allocation_response = []

    logger.debug("a1")
    # 先从可靠资源最多的机器分配资源
    if job_allocation_request['bidprice']>restricted_price
        for i in range(int(job_allocation_request['tasks_count'])):
            task_allocation_request = {
                'userid': job_allocation_request['userid'],
                'jobid': job_allocation_request['jobid'],
                'taskid': i,
                'bidprice': job_allocation_request['bidprice'],
                'resources': int(job_allocation_request['resources']),
            }
            logger.debug("a2")
            min=0xFFFF
            allocation_ID=0
            for j in range(0,len(allocations_list))
                if(allocations_list[j].reliable_resources_allocation_summary<min)
                    if allocations_list[j].rented==False or task_allocation_request[i].bidprice>=price_to_rent
                    min=allocations_list[j].reliable_resources_allocation_summary
                    allocation_ID=j
            if(has_reliable_resources(allocations_list[allocation_ID],task_allocation_request)
                task_allocation_response = allocate_reliable_task(allocations_list[allocation_ID],task_allocation_request)
                job_allocation_response.append(task_allocation_response)
            else 
                if(task_allocation_request.bidprice>=price_to_rent)
                    for(k in machine_to_rent_list)
                        if(k.resources>task_allocation_request.resources)
                                rent(k.id)
                                addNode(machine_num,k.resources,True)
                                task_allocation_response =allocate_reliable_task(allocations_list[machine_num],task_allocation_request)
                                job_allocation_response.append(task_allocation_response)
                                machine_num+=1
                                times_of_renting+=1
                                break
                else
                    min=0xFFFF
                    allocations_ID=0
                    for j in range(0,len(allocations_list))
                        cost=can_preempt_reliable_resources(allocations_list[j],task_allocation_request)
                        if cost>0 and cost<min
                            min=cost
                            allocations_ID=j
                    if(min<0xFFFF)
                       task_allocation_response = try_preempt_resources(allocations_list[allocations_ID],task_allocation_request)
                       job_allocation_response.append(task_allocation_response)
                    else
                        break 

    logger.info("a3")
    if (len(job_allocation_response) == int(job_allocation_request['tasks_count'])):
        logger.info("a4")
        return job_allocation_response
    else:
        # 选择使用率最低的机器，分配restricted_resources
        global usages_list
        sorted(usages_list, key=lambda x: x['cpu_utilization'], reverse=True)
        j = 0 
        for i in range(len(job_allocation_response), int(job_allocation_request['tasks_count'])):
            machineid = usages_list[j]['machineid']
            while machine_allocation_dict[machineid].rented==True
                j += 1
                if j>=machine_num
                    j=0
                machineid = usages_list[j]['machineid']
#如果是租借的机器，不分配受限资源，而且不分配出价低于price_to_rent的可靠资源，这样会降低资源利用率，但是
#由于我们没有任务迁移，而且资源一旦被分配，在用户释放其之前会一直保留，而租借sever的费用是按照时间计费的
#如果分配了开价很低的资源，如果资源一直不释放就会导致较大亏损。当没有足够的达到标准的可靠资源分配时，立即退还sever
            j+=1
            if j>=machine_num
                j=0
            allocation_of_machine = machine_allocation_dict[machineid]
            task_allocation_request = {
                'userid': job_allocation_request['userid'],
                'jobid': job_allocation_request['jobid'],
                'taskid': i,
                'bidprice': job_allocation_request['bidprice'],
                'resources': int(job_allocation_request['resources'])
            }
            task_allocation_response = allocate_task_restricted(allocation_of_machine,task_allocation_request)
            job_allocation_response.append(task_allocation_response)

    return job_allocation_response

def release_allocation(lxc_name):
    allocation_of_task = lxcname_allocation_dict[lxc_name]
    allocation_of_machine = machine_allocation_dict[allocation_of_task.machineid]
    if allocation_of_task.type == "reliable":
        i = bisect.bisect_left(allocation_of_machine.reliable_allocations,allocation_of_task)
        del allocation_of_machine.reliable_allocations[i]
        if len(allocation_of_machine.reliable_allocations)==0 and allocation_of_machine.rented==True
            releasemachine(allocation_of_machine.machineid)

    else:
        i = bisect.bisect_left(allocation_of_machine.restricted_allocations,allocation_of_task)
        del allocation_of_machine.restricted_allocations[i]
    return

def change_cgroup_settings(lxc_name, type):
    allocation_of_task = lxcname_allocation_dict[lxc_name]
    configuration = {
        'resources': allocation_of_task.resources,
        'type': type,
        'lxc_name':allocation_of_task.lxc_name
    }
    nodemgr.ip_to_rpc(allocation_of_task.machineid).change_cgroup_settings(configuration)

# 暂时不做，需要设计一下ui
def change_bid(jobid):
    if(has_reliable_resources(allocation_of_machine,task_allocation_request)):
        allocation_of_task = AllocationOfTask()
        allocation_of_task.id = uuid.uuid4()
        allocation_of_task.userid = task_allocation_request['userid']
        allocation_of_task.jobid = task_allocation_request['jobid']
        allocation_of_task.taskid = task_allocation_request['taskid']
        allocation_of_task.resources = task_allocation_request['resources']
        allocation_of_task.bidprice = task_allocation_request['bidprice']
        allocation_of_task.machineid = allocation_of_machine.machineid
        allocation_of_task.lxc_name = (allocation_of_task.userid
                                       + "-"
                                       + str(allocation_of_task.jobid)
                                       + "-"
                                       + str(allocation_of_task.taskid))
        allocation_of_task.type = 'reliable'
        bisect.insort(allocation_of_machine.reliable_allocations, allocation_of_task)
        lxcname_allocation_dict[allocation_of_task.lxc_name]=allocation_of_task
        
        # update allocation_summary
        allocation_of_machine.reliable_resources_allocation_summary += task_allocation_request['resources']
        return {'status':'success', 'allocation':allocation_of_task}

    if(can_preempt_reliable_resources(allocation_of_machine,task_allocation_request)):
        can_preempt = 0
        can_preempt_count = 0
        # 把被抢占的可靠资源变成受限制资源
        for a in allocation_of_machine.reliable_allocations:
            can_preempt+=a.resources
            can_preempt_count+=1
            # 转成受限
            a.type = 'restricted'
            bisect.insort(allocation_of_machine.restricted_allocations,a)

            # 更新allocation_machine的reliable_resources_allocation_summary
            allocation_of_machine.reliable_resources_allocation_summary -= a.resources
            if can_preempt>=task_allocation_request['resources']:
                break
            
        # to-do 调整这些容器的cgroup设置，使用软限制模式，只能使用空闲资源
        for i in range(0,can_preempt_count):
            change_cgroup_settings(allocation_of_machine.reliable_allocations[i], 'restricted')

        # 把被抢占的可靠资源从reliable_allocations中删除
        del allocation_of_machine.reliable_allocations[0:can_preempt_count]

        allocation_of_task = AllocationOfTask()
        allocation_of_task.id = uuid.uuid4()
        allocation_of_task.userid = task_allocation_request['userid']
        allocation_of_task.jobid = task_allocation_request['jobid']
        allocation_of_task.taskid = task_allocation_request['taskid']
        allocation_of_task.resources = task_allocation_request['resources']
        allocation_of_task.bidprice = task_allocation_request['bidprice']
        allocation_of_task.resources = task_allocation_request['resources']
        allocation_of_task.machineid = allocation_of_machine.machineid
        allocation_of_task.lxc_name = (allocation_of_task.userid
                                       + "-"
                                       + str(allocation_of_task.jobid)
                                       + "-"
                                       + str(allocation_of_task.taskid))
        allocation_of_task.lxc_name = allocation_of_task.userid + "-" + allocation_of_task.jobid + "-" + str(allocation_of_task.taskid)
        allocation_of_task.type = 'reliable'
        bisect.insort(allocation_of_machine.reliable_allocations, allocation_of_task)
        lxcname_allocation_dict[allocation_of_task.lxc_name]=allocation_of_task
        
        # update allocation_summary
        allocation_of_machine.reliable_resources_allocation_summary += task_allocation_request['resources']
        return {'status':'success', 'allocation':allocation_of_task}