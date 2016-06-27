import subprocess, time, os

from intra.cgroup import cgroup_manager

class system_manager:
	
	db_prefix = '.'
	
	def set_db_prefix(prefix):
		system_manager.db_prefix = prefix
		try:
			os.makedirs(prefix)
		except:
			pass
	
	def clear_all_swaps():
		subprocess.getoutput('swapoff -a')
		subprocess.getoutput('losetup -D')
	
	def extend_swap(size):
		if size < 0:
			(mem_free, mem_total) = system_manager.get_memory_sample()
			size = (mem_total + mem_total // 8) // 1024
		nid = 128
		while subprocess.getoutput("cat /proc/swaps | grep cg-loop | awk '{print $1}' | awk -F\- '{print $NF}' | grep %d$" % nid) != "":
			nid = nid + 1
		start_time = time.time()
		# setup
		os.system('dd if=/dev/zero of=/tmp/cg-swap-%d bs=1G count=0 seek=%d >/dev/null 2>&1' % (nid, size))
		os.system('mknod -m 0660 /dev/cg-loop-%d b 7 %d >/dev/null 2>&1' % (nid, nid))
		os.system('losetup /dev/cg-loop-%d /tmp/cg-swap-%d >/dev/null 2>&1' % (nid, nid))
		os.system('mkswap /dev/cg-loop-%d >/dev/null 2>&1' % nid)
		success = os.system('swapon /dev/cg-loop-%d >/dev/null 2>&1' % nid) == 0
		# detach
		# os.system('swapoff /dev/cg-loop-%d >/dev/null 2>&1' % nid)
		# os.system('losetup -d /dev/cg-loop-%d >/dev/null 2>&1' % nid)
		# os.system('rm -f /dev/cg-loop-%d /tmp/cg-swap-%d >/dev/null 2>&1' % (nid, nid))
		end_time = time.time()
		return {"setup": success, "time": end_time - start_time }

	def get_cpu_sample():
		[a, b, c, d] = subprocess.getoutput("cat /proc/stat | grep ^cpu\  | awk '{print $2, $3, $4, $6}'").split()
		cpu_time = int(a) + int(b) + int(c) + int(d)
		return (cpu_time, time.time())

	def get_memory_sample():
		mem_free = int(subprocess.getoutput("awk '{if ($1==\"MemAvailable:\") print $2}' /proc/meminfo 2>/dev/null")) // 1024
		mem_total = int(subprocess.getoutput("awk '{if ($1==\"MemTotal:\") print $2}' /proc/meminfo 2>/dev/null")) // 1024
		return (mem_free, mem_total)

	def get_swap_sample():
		swap_free = int(subprocess.getoutput("awk '{if ($1==\"SwapFree:\") print $2}' /proc/meminfo 2>/dev/null")) // 1024
		swap_total = int(subprocess.getoutput("awk '{if ($1==\"SwapTotal:\") print $2}' /proc/meminfo 2>/dev/null")) // 1024
		return (swap_free, swap_total)

	def get_system_loads():
		if 'last_cpu_sample' not in system_manager.__dict__:
			system_manager.last_cpu_sample = system_manager.get_cpu_sample()
			time.sleep(1)
		cpu_sample = system_manager.get_cpu_sample()
		(mem_free, mem_total) = system_manager.get_memory_sample()
		(swap_free, swap_total) = system_manager.get_swap_sample()
		ncpus = int(subprocess.getoutput("grep processor /proc/cpuinfo | wc -l"))
		cpu_free = ncpus - (cpu_sample[0] - system_manager.last_cpu_sample[0]) * 0.01 / (cpu_sample[1] - system_manager.last_cpu_sample[1])
		cpu_free = 0.0 if cpu_free <= 0.0 else cpu_free
		system_manager.last_cpu_sample = cpu_sample
		return {"mem_free": mem_free, "mem_total": mem_total, "swap_free": swap_free, "swap_total": swap_total, "cpu_free": cpu_free, "cpu_total": ncpus }
	
	def get_proc_etime(pid):
		fmt = subprocess.getoutput("ps -A -opid,etime | grep '^ *%d' | awk '{print $NF}'" % pid).strip()
		if fmt == '':
			return -1
		parts = fmt.split('-')
		days = int(parts[0]) if len(parts) == 2 else 0
		fmt = parts[-1]
		parts = fmt.split(':')
		hours = int(parts[0]) if len(parts) == 3 else 0
		parts = parts[len(parts)-2:]
		minutes = int(parts[0])
		seconds = int(parts[1])
		return ((days * 24 + hours) * 60 + minutes) * 60 + seconds

	def get_available_memsw():
		total_mem_limit = 0
		total_mem_used = 0
		sysloads = system_manager.get_system_loads()
		live = cgroup_manager.get_cgroup_containers()
		
		for item in live:
			try:
				sample = cgroup_manager.get_container_sample(item)
				limit = cgroup_manager.get_container_limit(item)
				total_mem_limit += limit["mem_page_quota"]
				total_mem_used += sample["mem_page_sample"]
			except:
				pass
		
		total_mem_limit >>= 20
		total_mem_used = (total_mem_used + (1<<20) - 1) >> 20
		
		available_mem_resource = sysloads['mem_free'] + \
			sysloads['swap_free'] - total_mem_limit + total_mem_used
		return {"Mbytes": available_mem_resource, "physical": sysloads['mem_free'], "cpu_free": sysloads['cpu_free']}

	def get_total_physical_memory_for_containers():
		total_mem_used = 0
		sysloads = system_manager.get_system_loads()
		live = cgroup_manager.get_cgroup_containers()
		
		for item in live:
			try:
				sample = cgroup_manager.get_container_sample(item)
				total_mem_used += sample["mem_page_sample"]
			except:
				pass
		
		total_mem_used = (total_mem_used + (1<<20) - 1) >> 20
		total_physical_memory_for_containers = sysloads['mem_free'] + total_mem_used
		
		return {"Mbytes": total_physical_memory_for_containers}

