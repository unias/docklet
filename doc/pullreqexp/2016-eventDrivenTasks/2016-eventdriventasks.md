class: center, middle

# Event Driven Tasks

Author: [Li Haonan](mailto:jolteon@pku.edu.cn)  

Source Code: https://github.com/remileon/DistGears/

---

# Goal 

1. **Test the efficient of different implements of http server**

	There are 5 different implements: thread, threadpool, process, processpool and asyncio.

2. **use server-client calls instead of polling on etcd between master and workers**

	Not completed

---

# Preparing Knowledge

1. **5 implements**
	
	When accept a request, server will **create thread**/ **use thread pool**/ **fork process**/ **use process pool**/ **create task in the event loop** to handle the request.

2. **asyncio**

	Asyncio is a library in python3 that can multiplex I/O in one thread. It requires tasks are **coroutine** and get I/O using **yield/yield from** expression. It's said that servers using asyncio has the best concurrency which means it can deal with the most huge amount of socket connections at one time.

---

# Design

1. **Server implements**

	Python package [socketserver](https://docs.python.org/3/library/socketserver.html) provides base HTTP/TCP/UDP servers, handlers and **ThreadingMixIn**, **ForkingMixIn** to make servers handle request using new thread/new process. By reading the  [source code](https://hg.python.org/cpython/file/3.5/Lib/socketserver.py) minxins using thread pool/ process pool can easily writed the same way.

2. **problem on asyncio**

	Asyncio needs specialized coroutine to be efficient. It's not easy to mix socketserver with asyncio, so write a brand new simple http server for asyncio.

3. **test client**

	Use some threads to send requests in endless loops, and test the total times per second.

---

# Experiment

1. **condition**

	Server runs on small cloud with 1 core. Client runs on the same machine. It's a problem that the client may use a lot of cpu that effects the performance of the server.

2. **results**

	asyncio: about 1200 requests/second
	
	thread, threadpool: 1100

	process: 150

	processpool: 600

---

# Codes & Future works

1. **codes**

	Servers except asyncio in **packed/separated** are the same, they are only different on file organizing. The new asyncio server is tested in **test2.py** temporary. Testing client is the same **client.py**.

2. **future works**

	Maybe the most efficient server is the mix of processpool and asyncio on multicore machines, not tried. Use the result to contribute to [docklet](https://github.com/unias/docklet) one day.

---

# Gains

1. **read and learn a lot**

	python3, [docklet](https://github.com/unias/docklet), git, markdown, lxc, [threading(python)](https://docs.python.org/3/library/threading.html), [multiprocessing(python)](https://docs.python.org/3/library/multiprocessing.html), coroutine, yield/yield from, [asyncio(python)](https://docs.python.org/3/library/asyncio.html), [socketserver(python)](https://docs.python.org/3/library/socketserver.html).

2. **journey on different python parallel coding**

3. **a little familiar with distributed cloud operating system**