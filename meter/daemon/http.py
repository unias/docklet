import json, cgi, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

class base_http_handler(BaseHTTPRequestHandler):
	
	def load_module(self):
		return None
	
	def do_POST(self):
		try:
			default_exception = 'unsupported request.'
			success = True
			data = None
			
			length = self.headers['content-length']
			if length == None:
				length = self.headers['content-length'] = 0
			if int(length) > (1<<12):
				raise Exception("data too large")
			http_form = cgi.FieldStorage(fp=self.rfile, headers=self.headers,environ={'REQUEST_METHOD':'POST','CONTENT_TYPE': "text/html"})
			
			form = {}
			for item in http_form:
				try:
					value = http_form[item].file.read().strip()
				except:
					value = http_form[item].value
				try:
					value = value.decode()
				except:
					pass
				form[item] = value
			
			parts = self.path.split('/', 2)
			if len(parts) != 3:
				raise Exception(default_exception)
			[null, version, path] = parts
			
			pymodule = self.load_module() + '_' + version
			module = __import__('daemon.' + pymodule)
			handler = module.__dict__[pymodule].__dict__['case_handler']
			method = path.replace('/', '_')
			if not hasattr(handler, method):
				raise Exception(default_exception)
			
			data = handler.__dict__[method](form, self.handler_class.args)
		except Exception as e:
			success = False
			data = {"reason": str(e)}
		finally:
			self.send_response(200)
			self.send_header("Content-type", "application/json")
			self.end_headers()
			self.wfile.write(json.dumps({"success": success, "data": data}).encode())
			self.wfile.write("\n".encode())
		return

class master_http_handler(base_http_handler):
	
	http_port = 1728
	
	def load_module(self):
		self.handler_class = master_http_handler
		return 'master'

class minion_http_handler(base_http_handler):
	
	http_port = 1729
	
	def load_module(self):
		self.handler_class = minion_http_handler
		return 'minion'

class http_daemon_listener:
	
	def __init__(self, handler_class, args = None):
		handler_class.args = args
		self.handler_class = handler_class

	def listen(self):
		server = HTTPServer(('', self.handler_class.http_port), self.handler_class)
		server.serve_forever()
