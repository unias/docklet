import lxc
import subprocess
import os
import signal
from utils.log import logger


# Note: keep physical device id always the same as the virtual device id
# device_path e.g. /dev/nvidia0
def add_device(container_name, device_path):
    c = lxc.Container(container_name)
    return c.add_device_node(device_path, device_path)


def remove_device(container_name, device_path):
    c = lxc.Container(container_name)
    return c.remove_device_node('', device_path)


# Mon May 21 10:51:45 2018
# +-----------------------------------------------------------------------------+
# | NVIDIA-SMI 381.22                 Driver Version: 381.22                    |
# |-------------------------------+----------------------+----------------------+
# | GPU  Name        Persistence-M| Bus-Id        Disp.A | Volatile Uncorr. ECC |
# | Fan  Temp  Perf  Pwr:Usage/Cap|         Memory-Usage | GPU-Util  Compute M. |
# |===============================+======================+======================|
# |   0  GeForce GTX 108...  Off  | 0000:02:00.0     Off |                  N/A |
# | 33%   53C    P2    59W / 250W |    295MiB / 11172MiB |      2%      Default |
# +-------------------------------+----------------------+----------------------+
# |   1  GeForce GTX 108...  Off  | 0000:84:00.0     Off |                  N/A |
# | 21%   35C    P8    10W / 250W |    161MiB / 11172MiB |      0%      Default |
# +-------------------------------+----------------------+----------------------+
#
# +-----------------------------------------------------------------------------+
# | Processes:                                                       GPU Memory |
# |  GPU       PID  Type  Process name                               Usage      |
# |=============================================================================|
# |    0    111893    C   python3                                        285MiB |
# |    1    111893    C   python3                                        151MiB |
# +-----------------------------------------------------------------------------+
#
def nvidia_smi(args=[]):
    try:
        cmd = ['nvidia-smi']
        cmd.extend(args)
        ret = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=5)
        return ret.split('\n')
    except subprocess.TimeoutExpired:
        return None
    except subprocess.CalledProcessError:
        return None
    except Exception as e:
        return None


def get_gpu_driver_version():
    output = nvidia_smi()
    if not output:
        return None
    else:
        return output[2].split()[-2]


# GPU 0: GeForce GTX 1080 Ti (UUID: GPU-a1c9b91b-5fb2-6059-9784-29ae78cdba8f)
# GPU 1: GeForce GTX 1080 Ti (UUID: GPU-36a9e2ff-b71d-8601-d0c5-72e0ec72564b)
def get_gpu_names():
    output = nvidia_smi(['-L'])
    if not output:
        return []
    gpu_names = []
    for line in output:
        start = line.find(':') + 1
        end = line.find('(')
        name = line[start:end].strip().replace(' ', '-')
        if name:
            gpu_names.append(name)
    return gpu_names


def get_gpu_status():
    output = nvidia_smi()
    if not output:
        return []
    interval_index = [index for index in range(len(output)) if len(output[index].strip()) == 0][0]
    status_list = []
    for index in range(7, interval_index, 3):
        status = {}
        status['id'] = output[index].split()[1]
        sp = output[index+1].split()
        status['fan'] = sp[1]
        status['memory'] = sp[8]
        status['memory_max'] = sp[10]
        status['util'] = sp[12]
        status_list.append(status)
    return status_list


def get_gpu_processes():
    output = nvidia_smi()
    if not output:
        return []
    interval_index = [index for index in range(len(output)) if len(output[index].strip()) == 0][0]
    process_list = []
    for index in range(interval_index + 5, len(output)):
        sp = output[index].split()
        if len(sp) != 7:
            break
        process = {}
        process['gpu'] = sp[1]
        process['pid'] = sp[2]
        process['name'] = sp[4]
        process['memory'] = sp[5]
        process['container'] = get_container_name_by_pid(sp[2])
        process_list.append(process)
    return process_list


def get_container_name_by_pid(pid):
    with open('/proc/%s/cgroup' % pid) as f:
        content = f.readlines()[0].strip().split('/')
        if content[1] != 'lxc':
            return 'host'
        else:
            return content[2]
    return None


def clean_up_processes_in_gpu(gpu_id):
    logger.info('[gputools] start clean up processes in gpu %d' % gpu_id)
    processes = get_gpu_processes()
    for process in [p for p in processes if p['gpu'] == gpu_id]:
        logger.info('[gputools] find process %d running in gpu %d' % (process['pid'], process['gpu']))
        if process['container'] == 'host':
            logger.warning('[gputools] find process of host, ignored')
        else:
            logger.warning('[gputools] find process of container [%s], killed' % process['container'])
            try:
                os.kill(process['pid'], signal.SIGKILL)
            except OSError:
                continue
