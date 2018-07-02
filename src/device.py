#!/usr/bin/env python3

import sense
import config
import monitor
import adbactions
import webdriver

import subprocess
import logging
import time

logger = logging.getLogger("device")


class Device(object):
    def __init__(self, serial=None, no_uimon=False):
        self.serial = serial
        if serial is None or serial == '-':
            self.serial = self.detect_serial()
        if config.use_uimon and not no_uimon:
            self.uimon = self.setup_uimon()
        else:
            self.uimon = None
        self.uimon_killed = False
        self.uimon_rets = []
        self.windowid = None
        self.action_funcs = adbactions.action_funcs
        self.use_web_grab = False
        self.kind = 'adb'

    def detect_serial(self):
        self.serial = None
        ret = self.run_adb_cmd("get-serialno", "")
        return ret.decode('utf-8').strip()

    def run_adb_shell(self, cmd, noerr=True):
        try:
            return self.run_adb_cmd("shell", cmd)
        except:
            if noerr:
                raise

    def run_adb_cmd(self, adb_cmd, cmd):
        if self.serial:
            arg_serial = "-s %s" % self.serial
        else:
            arg_serial = ""
        return subprocess.check_output(
            "%s %s %s %s" % (config.adb_path, arg_serial, adb_cmd, cmd), shell=True)

    def remove_file(self, path):
        self.run_adb_shell("rm %s" % path, noerr=False)

    def grab_file(self, src, dst):
        try:
            self.run_adb_cmd("pull", "%s %s" % (src, dst))
            return True
        except:
            return False

    def wait_idle(self):
        if config.use_wait_idle_cmd:
            self.run_adb_shell("CLASSPATH=/sdcard/uiauto.jar app_process /sdcard " +
                               "com.android.commands.uiautomator.Launcher waitforidle")
        else:
            sense.wait_idle(self)

    def setup_uimon(self):
        cmd = [config.adb_path]
        if self.serial is not None:
            cmd += ["-s", self.serial]
        cmd += ["shell", "CLASSPATH=/sdcard/uiauto.jar", "app_process", "/sdcard",
                "com.android.commands.uiautomator.Launcher", "monitor", "noevt"]
        return monitor.monitor_cmd(cmd, self.uimon_event_cb)

    def uimon_event_cb(self, info, line):
        if info == monitor.ProcInfo.exited:
            self.uimon_rets.append("EXITED")
            if not self.uimon_killed:
                logger.warning("uimon exited")
                self.run_adb_shell("killall uiautomator", noerr=False)
                time.sleep(1)
                self.uimon.restart()
        elif info == monitor.ProcInfo.output:
            line = line.strip().decode('utf-8')
            logger.debug("uimon msg: %s", line)
            if 'EventType' in line:
                self.uimon_rets.append(line)
        elif info == monitor.ProcInfo.errout:
            line = line.strip().decode('utf-8')
            if line:
                logger.debug("uimon err msg: %s", line)
        else:
            logger.info("strange callback: type=%s line=%s", info, line)

    def uimon_ret(self):
        while self.uimon_rets == []:
            time.sleep(0.05)
        return self.uimon_rets.pop(0)

    def uimon_cmd(self, cmd):
        self.uimon_rets.clear()
        self.uimon.input(cmd)

    def finish(self):
        self.uimon_killed = True
        try:
            self.uimon.input("q")
            self.uimon.kill()
        except:
            logger.info("error killing uimon")

    def get_ip(self):
        if ':' in self.serial:
            return self.serial.split(':')[0]
        else:
            return self.serial

    def is_emulator(self):
        if ':5555' in self.serial or '192.168' in self.serial:
            return True
        else:
            return False

    def get_windowid(self):
        if not self.is_emulator():
            return None
        if self.windowid is not None:
            return self.windowid
        windowid = subprocess.check_output(
            ["xdotool", "search", "--onlyvisible", "--class", "Genymotion"])
        windowid = windowid.decode('utf-8').strip()
        if len(windowid.split('\n')) > 1:
            for xwindowid in windowid.split('\n'):
                windowname = subprocess.check_output(
                    ["xdotool", "getwindowname", xwindowid]).decode('utf-8')
                if 'dpi' in windowname and self.get_ip() in windowname:
                    windowid = xwindowid
                    break

        self.windowid = windowid
        return windowid

    def do_action(self, action, observer, env):
        if action.name in self.action_funcs:
            logger.debug("doing action %s %s", action.name, action.attr)
            return self.action_funcs[action.name](self, observer, env, action.attr)
        else:
            logger.warn("can't do unknown action %s %r", action.name, action.attr)
            return False

    def dump(self, filename):
        sense.dump_to_file(self, filename)


def create_device(serial):
    try:
        if serial == 'web':
            dev = webdriver.WebDevice()
            dev.connect()
        elif serial is not None and serial.startswith('http'):
            dev = webdriver.WebDevice()
            dev.connect(serial)
        else:
            dev = Device(serial)
            dev.run_adb_shell("killall uiautomator", noerr=False)
        return dev
    except:
        logger.exception("fail to create %s", serial)
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    dev = Device()
    print("serial:", dev.serial)

    import sys
    if len(sys.argv) > 1:
        print(dev.run_adb_shell(' '.join(sys.argv[1:])).decode('utf-8'))

    dev.remove_file("/sdcard/window_dump.xml")
    dev.uimon_cmd("dump")
    print(dev.uimon_ret())
    time.sleep(1)
    dev.uimon_cmd("dump")
    print(dev.uimon_ret())
    time.sleep(1)
    dev.uimon_cmd("dump")
    time.sleep(5)
    dev.finish()
