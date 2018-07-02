import subprocess
import threading
import enum
import logging

logger = logging.getLogger('monitor')

class ProcInfo(enum.Enum):
    exited = 0
    output = 1
    errout = 2

def monitor_thr_proc(proc, cb):
    while True:
        if proc.poll() is not None:
            cb(ProcInfo.exited, proc.poll())
            break
        line = proc.stdout.readline()
        cb(ProcInfo.output, line)

def monitor_thr_proc_err(proc, cb):
    while True:
        if proc.poll() is not None:
            break
        line = proc.stderr.readline()
        cb(ProcInfo.errout, line)

def monitor_output(proc, cb):
    monitor_thr = threading.Thread(target=monitor_thr_proc, args=(proc, cb))
    monitor_thr_err = threading.Thread(target=monitor_thr_proc_err, args=(proc, cb))
    monitor_thr.daemon = False
    monitor_thr.start()
    monitor_thr_err.daemon = False
    monitor_thr_err.start()
    return monitor_thr

class Monitor(object):
    def __init__(self, cmd, cb):
        self.cmd = cmd
        self.cb = cb
        self.start()

    def start(self):
        self.proc = subprocess.Popen(self.cmd, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        self.thr = monitor_output(self.proc, self.cb)

    def kill(self):
        try:
            self.proc.kill()
        except:
            pass

    def write(self, cmd, newline):
        self.proc.stdin.write(cmd.encode('utf-8'))
        if newline:
            self.proc.stdin.write(b'\n')
        self.proc.stdin.flush()

    def input(self, cmd, newline=True):
        try:
            self.write(cmd, newline)
        except:
            logger.exception("fail to write to monitor process")
            self.restart()
            self.write(cmd, newline)

    def restart(self):
        self.kill()
        self.start()

def monitor_cmd(cmd, cb):
    return Monitor(cmd, cb)

