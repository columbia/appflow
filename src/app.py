#!/usr/bin/env python3

import sense
import config
import appdb
import device

import time
import os
import logging
import sys
import subprocess
import re

WAIT_RETRYLIMIT = 30

PACKAGEINSTALLER_NAME = "com.android.packageinstaller"

logger = logging.getLogger("app")


def clear(dev, name):
    dev.run_adb_shell("pm clear %(component)s" % {'component': name})
    try:
        dev.run_adb_shell("pm disable %(component)s" % {'component': name})
        dev.run_adb_shell("pm enable %(component)s" % {'component': name})
    except:
        logger.warn("pm disable/enable failed. possible: lack of permission")
    return True


def start(dev, name):
    #    action = "android.intent.action.MAIN"
    category = "android.intent.category.LAUNCHER"
#    dev.run_adb_shell("am start -c %(category)s -a %(action)s %(component)s" %
#                      {'category': category, 'action': action, 'component': name})
    """adb shell monkey -p com.ebay.mobile -c android.intent.category.LAUNCHER 1"""
    dev.run_adb_shell("monkey -p %(name)s -c %(category)s 1" %
                      {'name': name, 'category': category})

    return True


def stop(dev, name):
    dev.run_adb_shell("am force-stop %s" % name)
    return True


def uninstall(dev, appname):
    app = appdb.get_app(appname)
    dev.run_adb_shell("pm uninstall %s" % app)
    return True


def install(dev, appname):
    apkfile = os.path.join(config.apk_path, "%s.apk" % appname)
    dev.run_adb_cmd("install", apkfile)
    logger.info("installing %s" % appname)
    return True


aapt_version_re = re.compile(
    r"package:\s+name='[^']+'\s+versionCode='([^']+)'\s+versionName='([^']+)'.+")


def apk_version(appname):
    apkfile = os.path.join(config.apk_path, "%s.apk" % appname)
    for line in subprocess.check_output("%s d badging %s" % (config.aapt_path, apkfile),
                                        shell=True).decode('utf-8').split('\n'):
        rets = aapt_version_re.match(line)
        if rets:
            ver_code, ver_name = rets.groups()
            print(appname, ver_code, ver_name)
    return ver_code


dver_vercode_re = re.compile(r"\s+versionCode=([^\s]+)\s+.*")
dver_vername_re = re.compile(r"\s+versionName=(.*)")


def check_dev_version(dev, appname):
    app = appdb.get_app(appname)
    ret = dev.run_adb_shell("pm list packages").decode('utf-8')

    found = False
    for line in ret.split('\n'):
        line = line.strip()
        if line == 'package:' + app:
            found = True
            break
    if not found:
        print(appname, "NOT INSTALLED")
        return False

    ret = dev.run_adb_shell("pm dump %s" % app).decode('utf-8')
    vercode = None
    vername = None
    for line in ret.split('\n'):
        if dver_vercode_re.match(line):
            vercode = dver_vercode_re.match(line).group(1)
        elif dver_vername_re.match(line):
            vername = dver_vername_re.match(line).group(1)

    print(appname, vercode, vername)
    ver_code_apk = apk_version(appname)
    if ver_code_apk == vercode:
        print(appname, "VERSION MATCH")
        return True
    else:
        print(appname, "VERSION MISMATCH!")
        return False


def waitact(dev, name):
    retry = 0
    while retry < WAIT_RETRYLIMIT:
        actname = sense.grab_actname(dev)
        if name in actname:
            return True
        if PACKAGEINSTALLER_NAME in actname:
            return True
        retry += 1
        time.sleep(1)
    return False


def handle_cmd():
    appdb.collect_apps("../apks/")

    serial = sys.argv[1]
    cmd = sys.argv[2]
    args = sys.argv[3:]

    dev = device.Device(serial=serial, no_uimon=True)

    if cmd == "clear":
        if args[0] == 'all':
            for app in appdb.apps:
                clear(dev, appdb.get_app(app))
        else:
            clear(dev, appdb.get_app(args[0]))
    elif cmd == "install":
        appname = args[0]
        install(dev, appname)
    elif cmd == "uninstall":
        appname = args[0]
        uninstall(dev, appname)
    elif cmd == "version":
        appname = args[0]
        apk_version(appname)
    elif cmd == "dver":
        appname = args[0]
        ret = check_dev_version(dev, appname)
        if ret:
            sys.exit(0)
        else:
            sys.exit(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    handle_cmd()
