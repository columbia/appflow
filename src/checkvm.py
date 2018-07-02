#!/usr/bin/env python3

import sys
import time
import subprocess

import sense
import device

def check_sf(serial):
    llpid = 0
    count = 0

    print("# checking SurfaceFlinger    ", end='', flush=True)
    for i in range(60):
        spid = subprocess.check_output("adb -s %s shell pgrep surfaceflinger" % serial, shell=True).decode('utf-8').strip()

        if spid == '':
            continue
        elif llpid == 0:
            llpid = spid
            print("tracking", llpid, end='', flush=True)
        elif llpid == spid:
            print(".", end='', flush=True)
            count += 1
        else:
            print("failed!")
            count = 0
            llpid = spid

        if count == 3:
            print("good")
            return True

        time.sleep(2)

    return False

def check_uiauto(serial):
    print("# checking UiAutomator    ", end='', flush=True)
    for i in range(60):
        ret = subprocess.check_output("adb -s %s shell uiautomator dump" % serial, shell=True).decode('utf-8').strip()
        if "dumped" in ret:
            print("uiautomator working")
            return True
        time.sleep(2)

    print("! uiautomator not working!")
    return False

def check_act(serial):
    print("# checking Current Activity    ", end='', flush=True)
    for i in range(5):
        if check_act_once(serial):
            return True
        time.sleep(5)
    return False

def check_act_once(serial):
    subprocess.call("adb -s %s shell input keyevent HOME" % serial, shell=True)
    dev = device.Device(serial=serial, no_uimon=True)
    actname = sense.grab_actname(dev)
    if actname is None:
        print("can't get activity name")
        return False
    if 'launcher' in actname:
        print("at launcher")
        return True
    else:
        print("at %s, not launcher" % actname)
        return False

def check(serial):
    return (check_sf(serial) and check_uiauto(serial) and check_act(serial))

if __name__ == "__main__":
    serial = sys.argv[1]
    if check(serial):
        sys.exit(0)
    else:
        sys.exit(1)
