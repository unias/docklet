import master.taskmgr
from concurrent import futures
import grpc
from protos.rpc_pb2 import *
from protos.rpc_pb2_grpc import *
import threading, json, time, random
from utils import env


class SimulatedNodeMgr():
	def get_nodeips(self):
		return ['0.0.0.0']


class SimulatedMonitorFetcher():
	def __init__(self, ip):
		self.info = {}
		self.info['cpuconfig'] = [1,1,1,1]
		self.info['meminfo'] = {}
		self.info['meminfo']['free'] = 4 * 1024 * 1024 # (kb) simulate 4 GB memory
		self.info['diskinfo'] = []
		self.info['diskinfo'].append({})
		self.info['diskinfo'][0]['free'] = 8 * 1024 * 1024 * 1024 # (b) simulate 8 GB disk


class SimulatedTaskController(WorkerServicer):

	def __init__(self, worker):
		self.worker = worker

	def process_task(self, task, context):
		print('[SimulatedTaskController] receive task [%s] instanceid [%d] token [%s]' % (task.id, task.instanceid, task.token))
		worker.process(task)
		return Reply(status=Reply.ACCEPTED,message="")


class SimulatedWorker(threading.Thread):

	def __init__(self):
		threading.Thread.__init__(self)
		self.thread_stop = False
		self.tasks = []

	def run(self):
		worker_port = env.getenv('BATCH_WORKER_PORT')
		server = grpc.server(futures.ThreadPoolExecutor(max_workers=5))
		add_WorkerServicer_to_server(SimulatedTaskController(self), server)
		server.add_insecure_port('[::]:' + worker_port)
		server.start()
		while not self.thread_stop:
			for task in self.tasks:
				seed = random.random()
				if seed < 0.25:
					report(task.id, task.instanceid, RUNNING, task.token)
				elif seed < 0.5:
					report(task.id, task.instanceid, COMPLETED, task.token)
					self.tasks.remove(task)
				elif seed < 0.75:
					report(task.id, task.instanceid, FAILED, task.token)
					self.tasks.remove(task)
				else:
					pass
			time.sleep(5)
		server.stop(0)

	def stop(self):
		self.thread_stop = True

	def process(self, task):
		self.tasks.append(task)


class SimulatedJobMgr(threading.Thread):

	def __init__(self):
		threading.Thread.__init__(self)
		self.thread_stop = False

	def run(self):
		while not self.thread_stop:
			time.sleep(5)
		server.stop(0)

	def stop(self):
		self.thread_stop = True

	def report(self, task):
		print('[SimulatedJobMgr] task[%s] status %d' % (task.info.id, task.status))

	def assignTask(self, taskmgr, taskid, instance_count, retry_count, timeout, cpu, memory, disk):
		task = {}
		task['instanceCount'] = instance_count
		task['maxRetryCount'] = retry_count
		task['timeout'] = timeout
		task['parameters'] = {}
		task['parameters']['command'] = {}
		task['parameters']['command']['commandLine'] = ''
		task['parameters']['command']['packagePath'] = ''
		task['parameters']['command']['envVars'] = {'a':'1'}
		task['parameters']['stderrRedirectPath'] = ''
		task['parameters']['stdoutRedirectPath'] = ''
		task['cluster'] = {}
		task['cluster']['image'] = {}
		task['cluster']['image']['name'] = ''
		task['cluster']['image']['type'] = 1
		task['cluster']['image']['owner'] = ''
		task['cluster']['instance'] = {}
		task['cluster']['instance']['cpu'] = cpu
		task['cluster']['instance']['memory'] = memory
		task['cluster']['instance']['disk'] = disk
		task['cluster']['instance']['gpu'] = 0
		task['cluster']['mount'] = [{'remotePath':'', 'localPath':''}]

		taskmgr.add_task('user', taskid, json.dumps(task))


class SimulatedLogger():
	def info(self, msg):
		print('[INFO]    ' + msg)

	def warning(self, msg):
		print('[WARNING] ' + msg)

	def error(self, msg):
		print('[ERROR]   ' + msg)


def test():
	global worker
	global jobmgr
	global taskmgr

	worker = SimulatedWorker()
	worker.start()
	jobmgr = SimulatedJobMgr()
	jobmgr.start()

	taskmgr = master.taskmgr.TaskMgr(SimulatedNodeMgr(), SimulatedMonitorFetcher, SimulatedLogger(), scheduler_interval=2)
	taskmgr.set_jobmgr(jobmgr)
	taskmgr.start()

	add('task_0', instance_count=2, retry_count=2, timeout=60, cpu=2, memory=2048, disk=2048)


def add(taskid, instance_count, retry_count, timeout, cpu, memory, disk):
	global jobmgr
	global taskmgr
	jobmgr.assignTask(taskmgr, taskid, instance_count, retry_count, timeout, cpu, memory, disk)


def report(taskid, instanceid, status, token):
	global taskmgr

	master_port = env.getenv('BATCH_MASTER_PORT')
	channel = grpc.insecure_channel('%s:%s' % ('0.0.0.0', master_port))
	stub = MasterStub(channel)
	response = stub.report(ReportMsg(taskmsgs=TaskMsg(taskid=taskid, instanceid=instanceid, instanceStatus=status, token=token)))


def stop():
	global worker
	global jobmgr
	global taskmgr

	worker.stop()
	jobmgr.stop()
	taskmgr.stop()