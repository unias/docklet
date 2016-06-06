import subprocess, os

def http_client_post(ip, port, url, entries = {}):
	import urllib.request, urllib.parse, json
	url = url if not url.startswith('/') else url[1:]
	response = urllib.request.urlopen('http://%s:%d/%s' % (ip, port, url), urllib.parse.urlencode(entries).encode())
	obj = json.loads(response.read().decode().strip())
	response.close()
	return obj

class case_handler:
	# [Order-by] lexicographic order
	
	# curl -L -X POST http://0.0.0.0:1728/v1/minions/list
	def minions_list(form, args):
		minions = []
		for item in args.conn:
			minions.append(args.conn[item][1])
		return {"minions": minions}
	
	# curl -L -X POST -F mem=4096 -F cpu=2 http://0.0.0.0:1728/v1/resource/allocation
	def resource_allocation(form, args):
		mem = int(form['mem'])
		cpu = int(form['cpu'])
		candidates = {}
		from daemon.http import minion_http_handler
		for item in args.conn:
			addr = args.conn[item][1]
			obj = http_client_post(addr, minion_http_handler.http_port, '/v1/system/memsw/available')
			if obj['success'] and obj['data']['Mbytes'] >= mem:
				candidates[addr] = obj['data']

		if len(candidates) <= 0:
			raise Exception("no minions")
		else:
			from policy.allocate import candidates_selector
			one = candidates_selector.select(candidates)
			return {"recommend": one}
	
	# curl -L -X POST -F user=docklet http://0.0.0.0:1728/v1/user/live/add
	def user_live_add(form, args):
		if not os.path.exists('/var/lib/docklet/global/users/%s' % form['user']):
			return False
		subprocess.getoutput('echo live > /var/lib/docklet/global/users/%s/status' % form['user'])
		return True
	
	# curl -L -X POST -F user=docklet http://0.0.0.0:1728/v1/user/live/remove
	def user_live_remove(form, args):
		subprocess.getoutput('rm -f /var/lib/docklet/global/users/%s/status' % form['user'])
		return True
	
	# curl -L -X POST http://0.0.0.0:1728/v1/user/live/list
	def user_live_list(form, args):
		return subprocess.getoutput('ls -1 /var/lib/docklet/global/users/*/status 2>/dev/null | awk -F\/ \'{print $(NF-1)\'}').split()
	
	
	
	
