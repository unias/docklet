#!/usr/bin/python3

########################################
# Boot for Local:
#   sudo ./main (or: sudo ./main [master-ipaddr])
#

########################################
# Usage for Local:
#    curl -F uuid="lxc-name1" http://0.0.0.0:1729/v1/cgroup/container/sample
#

import time, sys, signal, json, subprocess, os

if __name__ == '__main__':
	if not subprocess.getoutput('lsb_release -r -s 2>/dev/null').startswith('16.04'):
		raise Exception('Ubuntu 16.04 LTS is required.')
	
	if not os.path.exists('/sys/fs/cgroup/memory/memory.memsw.usage_in_bytes'):
		raise Exception('Please append "swapaccount=1" to kernel.')
	
	if subprocess.getoutput('whoami') != 'root':
		raise Exception('Root privilege is required.')
	
	from daemon.http import *
	if len(sys.argv) == 1:
		sys.argv.append('disable-network')
	
	def signal_handler(signal, frame):
		if sys.argv[1] == 'master':
			subprocess.getoutput('ovs-vsctl del-br ovs-master >/dev/null 2>&1')
		else:
			subprocess.getoutput('ovs-vsctl del-br ovs-minion >/dev/null 2>&1')
		sys.exit(0)
	signal.signal(signal.SIGINT, signal_handler)
	
	if sys.argv[1] != 'master': # for minions
		from intra.cgroup import cgroup_manager
		cgroup_manager.auto_detect_prefix()
		cgroup_manager.set_default_memory_limit(4)

		from intra.system import system_manager
		system_manager.set_db_prefix('/var/lib/docklet/meter')
		# system_manager.extend_swap(32)
		
		if sys.argv[1] != 'disable-network':
			from connector.minion import minion_connector
			minion_connector.start(sys.argv[1])
		else:
			print("(No network mode)")

		from policy.quota import identify_policy
		from intra.smart import smart_controller
		
		smart_controller.set_policy(identify_policy)
		smart_controller.start()
		
		print("Minion REST Daemon Starts Listening ..")
		http = http_daemon_listener(minion_http_handler)
		http.listen()
		
	else: # for master: sudo ./main master
		from connector.master import master_connector
		master_connector.start()
		
		print("Master REST Daemon Starts Listening ..")
		http = http_daemon_listener(master_http_handler, master_connector)
		http.listen()

