import subprocess, os

class cgroup_controller:
	
	def read_value(group, uuid, item):
		path = cgroup_manager.__default_prefix__ % (group, uuid, item)
		if not os.path.exists(path):
			raise Exception('read: container "%s" not found!' % uuid)
		with open(path, 'r') as file:
			value = file.read()
		return value.strip()
	
	def write_value(group, uuid, item, value):
		path = cgroup_manager.__default_prefix__ % (group, uuid, item)
		if not os.path.exists(path):
			raise Exception('write: container "%s" not found!' % uuid)
		try:
			with open(path, 'w') as file:
				file.write(str(value))
		except:
			pass

class cgroup_manager:
	
	__prefix_docker__ = '/sys/fs/cgroup/%s/system.slice/docker-%s.scope/%s'
	__prefix_lxc__ = '/sys/fs/cgroup/%s/lxc/%s/%s'
	__prefix_lxcinit__ = '/sys/fs/cgroup/%s/init.scope/lxc/%s/%s'
	
	def set_default_memory_limit(limit):
		cgroup_manager.__default_memory_limit__ = limit
	
	def set_cgroup_prefix(prefix = __prefix_lxc__):
		cgroup_manager.__default_prefix__ = prefix
	
	def auto_detect_prefix():
		cgroup_manager.__default_prefix__ = cgroup_manager.__prefix_docker__
		if len(cgroup_manager.get_cgroup_containers()) > 0:
			return
		cgroup_manager.__default_prefix__ = cgroup_manager.__prefix_lxcinit__
		if len(cgroup_manager.get_cgroup_containers()) > 0:
			return
		cgroup_manager.__default_prefix__ = cgroup_manager.__prefix_lxc__
		if len(cgroup_manager.get_cgroup_containers()) > 0:
			return
		# print("[info]", "set cgroup prefix to %s" % cgroup_manager.__default_prefix__)
	
	def get_cgroup_containers():
		containers = subprocess.getoutput("find %s -type d 2>/dev/null | awk -F\/ '{print $(NF-1)}'" % (cgroup_manager.__default_prefix__ % ('cpu', '*', '.'))).split()
		uuids = []
		for item in containers:
			if item.startswith('docker-') and item.endswith('.scope') and len(item) > 64:
				uuids.append(item[7:-6])
			else:
				uuids.append(item)
		return uuids
	
	def get_container_pid(uuid):
		return int(cgroup_controller.read_value('cpu', uuid, 'tasks').split()[0])
	
	def get_container_sample(uuid):
		mem_page_sample = int(cgroup_controller.read_value('memory', uuid, 'memory.memsw.usage_in_bytes'))
		mem_phys_sample = int(cgroup_controller.read_value('memory', uuid, 'memory.usage_in_bytes'))
		cpu_sample = int(cgroup_controller.read_value('cpu', uuid, 'cpuacct.usage'))
		pids_sample = int(cgroup_controller.read_value('pids', uuid, 'pids.current'))
		container_pid = cgroup_manager.get_container_pid(uuid)
		
		from intra.system import system_manager
		real_time = system_manager.get_proc_etime(container_pid)
		return {"cpu_sample": cpu_sample, "pids_sample": pids_sample, "mem_page_sample": mem_page_sample, "mem_phys_sample": mem_phys_sample, "pid": container_pid, "real_time": real_time}
	
	def get_container_limit(uuid):
		mem_phys_quota = int(cgroup_controller.read_value('memory', uuid, 'memory.limit_in_bytes'))
		mem_page_quota = int(cgroup_controller.read_value('memory', uuid, 'memory.memsw.limit_in_bytes'))
		cpu_shares = int(cgroup_controller.read_value('cpu', uuid, 'cpu.shares'))
		cpu_quota = int(cgroup_controller.read_value('cpu', uuid, 'cpu.cfs_quota_us'))
		cpu_quota = cpu_quota if cpu_quota >= 0 else -1
		
		pids_quota = cgroup_controller.read_value('pids', uuid, 'pids.max')
		pids_quota = int(pids_quota) if pids_quota != 'max' else -1
		return {"cpu_quota": cpu_quota, "cpu_shares": cpu_shares, "mem_phy_quota": mem_phys_quota, "mem_page_quota": mem_page_quota, "pids_quota": pids_quota}

	def get_container_oom_status(uuid):
		[_x, idle, _y, oom] = cgroup_controller.read_value('memory', uuid, 'memory.oom_control').split()
		return (idle == '1', oom == '1')

	def set_container_oom_idle(uuid, idle):
		cgroup_controller.write_value('memory', uuid, 'memory.oom_control', 1 if idle else 0)
	
	def protect_container_oom(uuid):
		cgroup_controller.write_value('memory', uuid, 'memory.oom_control', 1)
		data = cgroup_manager.get_container_limit(uuid)
		if data["mem_page_quota"] >= 9223372036854771712:
			memory_limit_in_bytes = cgroup_manager.__default_memory_limit__ << 30
			mem_phy_quota = min(data["mem_phy_quota"], memory_limit_in_bytes)
			mem_page_quota = memory_limit_in_bytes
			cgroup_controller.write_value('freezer', uuid, 'freezer.state', 'FROZEN')
			cgroup_controller.write_value('memory', uuid, 'memory.limit_in_bytes', mem_phy_quota)
			cgroup_controller.write_value('memory', uuid, 'memory.limit_in_bytes', mem_phy_quota)
			cgroup_controller.write_value('memory', uuid, 'memory.memsw.limit_in_bytes', mem_page_quota)
			cgroup_controller.write_value('freezer', uuid, 'freezer.state', 'THAWED')
	
	def set_container_physical_memory_limit(uuid, Mbytes, freeze = False):
		if freeze:
			cgroup_controller.write_value('freezer', uuid, 'freezer.state', 'FROZEN')
		memory_limit = int(max(0, Mbytes)) << 20
		cgroup_controller.write_value('memory', uuid, 'memory.limit_in_bytes', memory_limit)
		if freeze:
			cgroup_controller.write_value('freezer', uuid, 'freezer.state', 'THAWED')
		
	def set_container_cpu_priority_limit(uuid, ceof):
		cpu_scaling = min(1024, 10 + int(1024 * ceof))
		cgroup_controller.write_value('cpu', uuid, 'cpu.shares', cpu_scaling)
