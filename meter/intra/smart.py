import subprocess, time, os, threading, math

from intra.system import system_manager
from intra.cgroup import cgroup_manager
from intra.billing import billing_manager

class smart_controller:
	
	def set_policy(policy):
		smart_controller.policy = policy
	
	def start(interval = 4):
		thread = threading.Thread(target = smart_controller.smart_control_forever, args = [interval])
		thread.setDaemon(True)
		thread.start()
		return thread
	
	def smart_control_forever(interval):
		last_live = []
		while True:
			time.sleep(interval)
			try:
				mem_usage_mapping = {}
				live = cgroup_manager.get_cgroup_containers()
				for item in live:
					try:
						last_live.remove(item)
					except:
						pass
					try:
						cgroup_manager.protect_container_oom(item)
						sample = cgroup_manager.get_container_sample(item)
						mem_usage_mapping[item] = math.ceil(sample['mem_page_sample'] * 1e-6)
						billing_manager.add_usage_sample(item, sample, interval)
					except:
						pass
				for item in last_live:
					billing_manager.clean_dead_node(item)
				last_live = live
				is_ready = True
				
				memory_available = system_manager.get_available_memsw()
				if memory_available['Mbytes'] <= 0:
					size_in_gb = int(math.ceil(-memory_available['Mbytes'] / 1024 / 16) * 16)
					print("[warning]", 'overloaded containers, auto-extending %d G memsw.' % size_in_gb)
					system_manager.extend_swap(size_in_gb)
				
				total_score = 0.0
				score_mapping = {}
				for item in live:
					score = max(1e-8, smart_controller.policy.get_score_by_uuid(item))
					score_mapping[item] = score
					print(item, "(score/cpu)", score)
					total_score += score
				
				# CPU Scoring
				for item in live:
					ceof = score_mapping[item] / total_score
					cgroup_manager.set_container_cpu_priority_limit(item, ceof)
				
				# Iterative Memory Scoring
				free_mem = system_manager.get_total_physical_memory_for_containers()['Mbytes']
				local_nodes = live
				mem_alloc = {}
				for item in live:
					mem_alloc[item] = 0
				
				while free_mem > 0 and len(local_nodes) > 0:
					excess_mem = 0
					next_local_nodes = []
					for item in local_nodes:
						mem_alloc[item] += int(math.floor(free_mem * score_mapping[item] / total_score))
						if mem_alloc[item] >= mem_usage_mapping[item]:
							excess_mem += mem_alloc[item] - mem_usage_mapping[item]
							mem_alloc[item] = mem_usage_mapping[item]
						else:
							next_local_nodes.append(item)
					free_mem = excess_mem
					local_nodes = next_local_nodes
				
				for item in live:
					mem_alloc[item] += int(math.floor(free_mem * score_mapping[item] / total_score))
					cgroup_manager.set_container_physical_memory_limit(item, mem_alloc[item])
					print(item, "(malloc:usage)", mem_alloc[item], mem_usage_mapping[item])
				
				if len(live) > 0:
					print("-------------------------------")
				
			except:
				pass


# echo "8:0 1000" > /sys/fs/cgroup/blkio/lxc/docklet-1-0/blkio.throttle.write_bps_device
# https://www.kernel.org/doc/Documentation/devices.txt
# while true; do clear; cat /sys/fs/cgroup/blkio/lxc/docklet-1-0/blkio.throttle.io_service_bytes; sleep 0.5; done
# hugetlb, net_cls, net_prio, /sbin/tc
