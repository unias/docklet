import subprocess, time, os

from intra.system import system_manager

class billing_manager:
	
	history_book = {}
	
	def on_lxc_acct_usage(uuid, prev, curr, interval):
		cpu_gen = max(0, curr['cpu_sample'] - prev['cpu_sample']) >> 20 # in ms
		mem_gen = ((curr['mem_phys_sample'] + prev['mem_phys_sample']) * interval) >> 11 # in kbytes
		try:
			os.makedirs('%s/%s' % (system_manager.db_prefix, uuid))
		except:
			pass
		with open('%s/%s/usage' % (system_manager.db_prefix, uuid), 'a') as fp:
			fp.write('%d %d\n' % (cpu_gen, mem_gen))
	
	def add_usage_sample(uuid, sample, interval):
		if uuid in billing_manager.history_book:
			billing_manager.on_lxc_acct_usage(uuid, billing_manager.history_book[uuid], sample, interval)
		billing_manager.history_book[uuid] = sample
	
	def clean_dead_node(uuid):
		if uuid in billing_manager.history_book:
			billing_manager.history_book.pop(uuid)
	
	def fetch_increment_and_clean(uuid):
		cpu_acct = 0.0
		mem_acct = 0.0
		cnt_acct = 0
		try:
			fetch_path = '%s/%s/%f' % (system_manager.db_prefix, uuid, time.time())
			os.rename('%s/%s/usage' % (system_manager.db_prefix, uuid), fetch_path)
			with open(fetch_path, 'r') as fp:
				line = fp.readline()
				while line != '':
					[cpu, mem] = line.split()
					line = fp.readline()
					cnt_acct += 1
					cpu_acct += float(cpu)
					mem_acct += float(mem)
			os.remove(fetch_path)
		except:
			pass
		return {"cpu_acct": cpu_acct, "mem_acct": mem_acct, "cnt_acct": cnt_acct}
