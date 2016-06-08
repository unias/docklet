class: center, middle

# Master and Worker start independently

Author: [Tongyuan Zhang](mailto:tongyuan@pku.edu.cn)

Source Code: https://github.com/SourceZh/docklet-1/tree/separate

---

# Goal

Now, Master must start before Worker. So, we want to change that Master and Worker can start up independently. Even if Master restart, Worker will not be effected.

---

# Design

## Master
1. Each time start check all run node in etcd and add them in Master.
2. Listening: 
 1. Check run node in etcd. 
 2. If a run node is not recorded in Master, add it in Master and change it state to "ok". Also this node may be a new node, check it and add it in allnode in etcd.
 3. Until all node in etcd is in Master. 

## Worker
1. Each time start check all node in etcd to judge how to start.
2. Worker will add itself into etcd and start up.
3. But Worker cannot connect Master until Master really find this Worker.
4. Worker will send heartbeat package to keep alive in etcd.

---
# Web Terminal(Unfinished)

Author: [Tongyuan Zhang](mailto:tongyuan@pku.edu.cn)

Source Code: https://github.com/SourceZh/notebook/tree/master

---

# Goal

Make Jupyter Web Terminal into a separately package.

---
# Experiment
## Front End
Use js to control and keep a terminal list.
code here:

1. [notebook/notebook/static/tree/js/main.js(91:95)]()
2. [notebook/notebook/static/tree/js/terminallist.js]()
3. [notebook/notebook/static/terminal/js/terminado.js]()

## Back End
Python
code here

1. [notebook/notebook/notebookapp.py]()
2. [notebook/notebook/terminal]()

---
# Experiment
Someone already do it!
** [Jupyter JS Terminal](http://jupyter.org/jupyter-js-terminal/) **
