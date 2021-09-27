import subprocess, re
import os
from functools import wraps

from utils import env
from utils.log import logger

fs_prefix = env.getenv("FS_PREFIX")
hpc_enabled = env.getenv("HPC_ENABLED")
hpc_login_node = env.getenv("HPC_LOGIN_NODE")
hpc_login_user = env.getenv("HPC_LOGIN_USER")
hpc_queue_x86 = env.getenv("HPC_QUEUE_X86")

import paramiko
import pysftp
ssh_client = None
ssh_transport = None


def hpc_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not hpc_enabled or hpc_login_node is None or hpc_login_user is None:
            return False, "[hpccontroller][%s] HPC is not configured" % func.__name__
        return func(*args, **kwargs)
    return wrapper


def ssh_connection_check(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            if ssh_client is None:
                logger.error('[hpccontroller] ssh client is None, connect.')
                connect_ssh()
            return func(*args, **kwargs)
        except Exception as e:
            logger.error('[hpccontroller] ssh failed [%s], reconnect.' % str(e))
            connect_ssh()
            return func(*args, **kwargs)
        except:
            return False, '[hpccontroller] ssh failed'
    return wrapper


@hpc_required
def connect_ssh():
    global ssh_client
    global ssh_transport
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    private_key = paramiko.RSAKey.from_private_key_file('/root/.ssh/id_rsa')
    ssh_transport = paramiko.Transport((hpc_login_node, 22))
    ssh_transport.connect(username=hpc_login_user, pkey=private_key)
    ssh_client._transport = ssh_transport


@hpc_required
def disconnect_ssh():
    ssh_transport.close()


@hpc_required
@ssh_connection_check
def hpc_exec(cmd):
    logger.info('[hpccontroller] run command: %s' % cmd)
    stdin, stdout, stderr = ssh_client.exec_command(cmd)
    out = stdout.read().decode()
    channel = stdout.channel
    if channel.recv_exit_status() == 0:
        return True, out
    else:
        return False, stderr.read().decode()


def gen_hpc_path(username, path):
    path_sp = path.split('/')
    for item in path_sp:
        if item == '..':
            return False, '".." is not supported'
    if len(path_sp) == 0 or (path_sp[0] != '~' and path_sp[0] != '$' and path_sp[0] != '#'):
        path_sp.insert(0, '~')
    if path_sp[0] == '~':
        path_sp[0] = '~/online3/private/%s' % username
    elif path_sp[0] == '$':
        path_sp[0] = '~/online3/public'
    elif path_sp[0] == '#':
        path_sp[0] = '~/online3/batch'
    return True, '/'.join(path_sp)


def submit_task_x86(cmd, user, working_directory, queue=hpc_queue_x86, runlog=None, process_count=1):
    cmd.replace(r'"', r'\\"')
    succ, path = gen_hpc_path(user, working_directory)
    if not succ:
        return False, path
    bsub_command = 'cd %s && bsub -q %s -n %d' %(path, queue, process_count)
    if runlog:
        bsub_command += ' -o '
        bsub_command += runlog
    bsub_command += ' '
    bsub_command += cmd
    succ, ret = hpc_exec(bsub_command)
    if not succ:
        logger.error('[hpccontroller] submit task failed. \ncommand: %s\nmessage: %s' % (bsub_command, ret))
        return False, ret
    result = re.findall('Job <(\\d*)> has been submitted to queue <%s>' % queue, ret)
    if result:
        return True, result[0]
    else:
        return False, ret

def submit_task(cmd,working_directory):
    cmd.replace(r'"', r'\\"')
    hpc_command = 'cd %s && %s' %(working_directory,cmd)
    succ, ret = hpc_exec(hpc_command)
    if not succ:
        logger.error('[hpccontroller] submit task failed. \ncommand: %s\nmessage: %s' % (hpc_command, ret))
        return False, ret
    result = re.findall('Job <(\\d*)> has been submitted to queue', ret)
    if result:
        return True, result[0]
    else:
        return False, ret

def kill_task_x86(jobid):
    cmd = 'bkill %s' % jobid
    succ, ret = hpc_exec(cmd)
    if not succ:
        logger.error('[hpccontroller] kill task failed. \ncommand: %s\nmessage: %s' % (cmd, ret))
        return False, ret
    if ret == 'Job %s is being terminated' % jobid:
        return True, ret
    else:
        return False, ret


def check_recent_tasks():
    cmd = 'bjobs -w -a'
    succ, ret = hpc_exec(cmd)
    if not succ: 
        logger.error('[hpccontroller] check task info failed. \ncommand: %s\nmessage: %s' % (cmd, ret))
        return False, ret
    ret_lines = ret.split('\n')[2:]
    job_map = {}
    for line in ret_lines:
        if line.strip() == '':
            continue
        line_sp = line.split()
        job = {}
        job['id'] = line_sp[0]
        job['status'] = line_sp[1]
        job['job_name'] = line_sp[3]
        job['queue'] = line_sp[4]
        job_map[job['id']] = job
    return True, job_map


###########################################
#                                         #
#                storage                  #
#                                         #
###########################################


def write_public(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        hpc_exec('chmod 755 ~/online3/public')
        ret = func(*args, **kwargs)
        hpc_exec('chmod -w ~/online3/public')
        return ret
    return wrapper


@write_public
def prepare_user_fs(username):
    cmd = 'mkdir ~/online3/private/%s' % username
    succ, msg = hpc_exec(cmd)
    if not succ:
        return False, msg
    cmd = 'mkdir ~/online3/public/%s' % username
    succ, msg = hpc_exec(cmd)
    if not succ:
        return False, msg


@write_public
def share_dir(username, src_path, dst_path):
    if not src_path.startswith('~/'):
        return False, 'Path must start with "~/", which represent your private working directory'
    if '/' in dst_path:
        return False, 'illegal character found: /'
    succ, src_path = gen_hpc_path(username, src_path)
    if not succ:
        return False, src_path
    succ, dst_path = gen_hpc_path(username, '$/%s/%s' % (username, dst_path))
    if not succ:
        return False, dst_path
    cmd = 'ln -s %s %s' % (src_path, dst_path)
    hpc_exec(cmd)


@write_public
def undo_share_dir(username, dst_path):
    if '/' in dst_path:
        return False, 'illegal character found: /'
    succ, dst_path = gen_hpc_path(username, '$/%s/%s' % (username, dst_path))
    if not succ:
        return False, dst_path
    cmd = 'rm -f %s' % dst_path
    hpc_exec(cmd)


def generate_nfs_path(user, relative_path):
    if relative_path.startswith('~/nfs/'):
        relative_path = relative_path[6:]
    while len(relative_path) > 0 and relative_path.startswith('/'):
        relative_path = relative_path[1:]
    return os.path.join(fs_prefix, 'global/users', user, 'data', relative_path)


def generate_hpc_path(relative_path):
    while len(relative_path) > 0 and relative_path.startswith('/'):
        relative_path = relative_path[1:]
    return os.path.join('~/online3/', relative_path)


def sys_run(cmd):
    try:
        ret = subprocess.run(cmd, shell=True)
        return True, ret
    except subprocess.CalledProcessError as e:
        logger.error('[CalledProcessError] cmd: %s, stdout: %s, stderr: %s' % (cmd, e.stdout, e.stderr))
        return False, e.stderr
    except subprocess.TimeoutExpired:
        logger.error('[TimeoutExpired] cmd: %s' % cmd)
        return False, 'Timeout'
    except Exception as e:
        return False, 'Unknown Error'


@hpc_required
def upload(local, remote, mode, callback):
    logger.info('[hpccontroller] upload: [%s] -> [%s]' % (local, remote))
    if remote.startswith('~/'):
        remote = remote[2:]
    with pysftp.Connection(host=hpc_login_node, username=hpc_login_user, private_key='/root/.ssh/id_rsa') as sftp:
        if os.path.isdir(local):
            if sftp.exists(remote) and not sftp.isdir(remote):
                raise Exception('[hpccontroller] Error: trying to copy local directory to existing remote file')
            file_name = local.split('/')[-1]
            remote = remote + '/' + file_name
            if sftp.exists(remote) and not sftp.isdir(remote):
                raise Exception('[hpccontroller] Error: trying to copy local directory to existing remote file')
            try:
                sftp.mkdir(local, 755)
            except FileExistsError:
                pass
            logger.info('[hpccontroller] sftp.put_r("%s", "%s")' % (local, remote))
            sftp.put_r(local, remote, callback=callback)
        else:
            if sftp.isdir(remote):
                file_name = local.split('/')[-1]
                remote = remote + '/' + file_name
            logger.info('[hpccontroller] sftp.put("%s", "%s"), chmod %d' % (local, remote, mode))
            sftp.put(local, remote, callback=callback)
            sftp.chmod(remote, mode)


@hpc_required
def download(remote, local, mode, callback):
    logger.info('[hpccontroller] download: [%s] -> [%s]' % (remote, local))
    if remote.startswith('~/'):
        remote = remote[2:]
    with pysftp.Connection(host=hpc_login_node, username=hpc_login_user, private_key='/root/.ssh/id_rsa') as sftp:
        if sftp.isdir(remote):
            if os.path.exists(local) and not os.path.isdir(local):
                raise Exception('[hpccontroller] Error: trying to copy remote directory to existing local file')
            file_name = remote.split('/')[-1]
            local = local + '/' + file_name
            if os.path.exists(local) and not os.path.isdir(local):
                raise Exception('[hpccontroller] Error: trying to copy remote directory to existing local file')
            try:
                os.mkdir(local, 755)
            except Exception as e:
                logger.error('[hpccontroller] %s' % e)
            logger.info('[hpccontroller] sftp.get_r("%s", "%s")' % (remote, local))
            try:
                # sftp.get_r(remote, local, callback=callback)
                sftp.get_d(remote, local)
            except Exception as e:
                logger.error('[hpccontroller] %s' % e)
        else:
            if os.path.isdir(local):
                file_name = remote.split('/')[-1]
                local = local + '/' + file_name
            logger.info('[hpccontroller] sftp.get("%s", "%s"), chmod %d' % (remote, local, mode))
            try:
                sftp.get(remote, local, callback=callback)
                os.chmod(remote, mode)
            except Exception as e:
                logger.error('[hpccontroller] %s' % e)

def upload_data(user, src, dst, mode=755, callback=None):
    local = generate_nfs_path(user, src)
    succ, remote = gen_hpc_path(user, dst)
    if not succ:
        return False, remote
    try:
        upload(local, remote, mode, callback)
        return True, ''
    except Exception as e:
        return False, str(e)


def download_data(user, src, dst, mode=755, callback=None):
    local = generate_nfs_path(user, dst)
    succ, remote = gen_hpc_path(user, src)
    if not succ:
        return False, remote
    try:
        download(remote, local, mode, callback)
        return True, ''
    except Exception as e:
        return False, str(e)
