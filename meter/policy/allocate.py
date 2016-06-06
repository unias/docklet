class candidates_selector:
	
	def select(candidates):
		return max(candidates, key=lambda addr: candidates[addr]['cpu_free'])

