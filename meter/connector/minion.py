#!/usr/bin/python3

import socket, time, threading, os

class minion_connector:
	
	def connect(server_ip):
		from connector.master import master_connector
		connected = True
		while True:
			try:
				fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
				fd.connect((server_ip, master_connector.tcp_port))
				connected = True
				print("[info]", "connected to master.")
				
				master_connector.establish_vswitch('minion')
				master_connector.build_gre_conn('minion', server_ip)
				
				while True:
					data = b'ack'
					if fd.send(data) != len(data):
						break
					readData = fd.recv(1024)
					time.sleep(0.5)
				fd.close()
			except socket.error as e:
				master_connector.break_gre_conn('minion', server_ip)
				if connected:
					print("[info]", "non-connected with master.")
			except Exception as e:
				pass
			finally:
				if connected:
					os.system('ovs-vsctl del-br ovs-minion >/dev/null 2>&1')
				connected = False
				time.sleep(1)
	
	def start(server_ip):
		thread = threading.Thread(target = minion_connector.connect, args = [server_ip])
		thread.setDaemon(True)
		thread.start()
		return thread
