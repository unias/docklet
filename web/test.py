import os
import threading
t = threading.Thread(target=os.system, args=["bash " + "../tools/auto_update_master.sh update /root/docklet-1"])
t.start()
