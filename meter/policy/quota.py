from intra.system import system_manager
from intra.cgroup import cgroup_manager
import subprocess

class identify_policy:
	
	def get_score_by_uuid(uuid):
		return 1.0

class etime_rev_policy(identify_policy):
	
	def get_score_by_uuid(uuid):
		pid = cgroup_manager.get_container_pid(uuid)
		etime = system_manager.get_proc_etime(pid)
		return 1.0 / (1.0 + etime)

class mem_usage_policy(identify_policy):
	
	def get_score_by_uuid(uuid):
		sample = cgroup_manager.get_container_sample(uuid)
		return sample["mem_page_sample"]

class mem_quota_policy(identify_policy):
	
	def get_score_by_uuid(uuid):
		sample = cgroup_manager.get_container_limit(uuid)
		return sample["mem_page_quota"]

class cpu_usage_policy(identify_policy):
	
	def get_score_by_uuid(uuid):
		sample = cgroup_manager.get_container_sample(uuid)
		return sample["cpu_sample"]

class cpu_usage_rev_policy(identify_policy):
	
	def get_score_by_uuid(uuid):
		sample = cgroup_manager.get_container_sample(uuid)
		return 1024 * 1024 / (1.0 + sample["cpu_sample"])

class cpu_speed_policy(identify_policy):
	
	def get_score_by_uuid(uuid):
		sample = cgroup_manager.get_container_sample(uuid)
		pid = cgroup_manager.get_container_pid(uuid)
		etime = system_manager.get_proc_etime(pid)
		return sample["cpu_sample"] / etime

class user_state_policy(identify_policy):
	
	def get_score_by_uuid(uuid):
		user = uuid.split('-')[0]
		online = subprocess.getoutput('cat /var/lib/docklet/global/users/%s/status 2>/dev/null' % user) == 'live'
		return 10.0 if online else 1.0


