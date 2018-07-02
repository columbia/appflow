#!/usr/bin/env python3

import sys
import subprocess
import os
import re
import glob
import config
import uievent
import time
import logging

non_rep_pages = []
non_login_pages_1 = ["filter"]
non_login_pages_2 = ["checkout"]
non_login_pages_3 = []
login_pages = [] #"order", "history"]
#non_rep_pages = ["signin", "register", "cat1"]
#non_login_pages_1 = ["main"]
#non_login_pages_2 = ["cat2", "cat3", "list"]
#non_login_pages_3 = ["searchret", "detail"]
#login_pages = ["cart"]
#pages = ["main", "searchret", "detail", "cart", "signin", "register", "cat1", "cat2", "cat3", "list"]
#pages = ["cat", "list"]
last_page_name = ""
use_adb = False
logger = logging.getLogger("dump")

def collect_app_names():
    apps = set()
    for filename in glob.glob("../guis/*.xml"):
        apps.add(os.path.basename(filename).split('_')[0])
    return sorted(apps)

def capture_img(page_name, path, dev):
    page_file = os.path.join(path, "%s.png" % page_name)
    subprocess.check_output("adb shell screencap -p /sdcard/screen.png", shell=True)
    subprocess.check_call("adb pull /sdcard/screen.png %s" % page_file, shell=True)

    if os.stat(page_file).st_size != 0:
        return True

    windowid = subprocess.check_output(
        "xdotool search --onlyvisible --class Genymotion", shell=True)
    windowid = windowid.decode('utf-8').strip()
    if windowid:
        subprocess.check_call("import -window %s %s" % (windowid, page_file),
                                shell=True)
        subprocess.check_call(
            "convert %s -resize 1200x1920 -crop 1080x1920+0+0 %s" % (page_file, page_file),
            shell=True)
        if os.stat(page_file).st_size > 0:
            return True

    return False

class Handler(object):
    def __init__(self):
        self.finished = False
        self.err = False

    def handle_uievent(self, evt):
        if evt['status'] == 'exited':
            self.err = True
            self.finished = True
        parsed_evt = uievent.parse_event(evt)
        if parsed_evt:
            type_ = parsed_evt['type']
            if type_ == 'UIDUMPED':
                self.finished = True
            if type_ == 'DUMPFAILED':
                self.err = True
                self.finished = True

def dodump(dev=None):
    if use_adb:
        if dev is None or dev.serial is None:
            cmd = "%s shell uiautomator dump" % config.adb_path
        else:
            cmd = "%s -s %s shell uiautomator dump" % (config.adb_path, dev.serial)

        dump_out = subprocess.check_output(cmd, shell=True)
        if "dumped to" not in dump_out.decode('utf-8'):
            logger.warn(dump_out.decode("utf-8"))
            return False
    elif config.use_my_dump:
        ret = dev.run_adb_shell(
            ' '.join(["CLASSPATH=/sdcard/uiauto.jar", "app_process", "/sdcard",
            "com.android.commands.uiautomator.Launcher", "dump"])).decode('utf-8')
        if "UIDUMPED" in ret:
            return True
        else:
            return False
    elif config.use_uimon:
        dev.uimon_cmd("dump")
        ret = dev.uimon_ret()
        if "UIDUMPED" in ret:
            return True
        else:
            return False
    else:
        handler = Handler()
        ui_mon = uievent.monitor_uievent(handler.handle_uievent, dev=dev)
        ui_mon.input('dump')
        while not handler.finished:
            time.sleep(0.2)
        ui_mon.kill()
        if handler.err:
            logger.warn("fail to capture")
            return False
        return True

def capture_layout(page_name, path, dev):
    while True:
        if not dodump():
            return False
        subprocess.check_call("adb pull /sdcard/window_dump.xml %s" % os.path.join(path, "%s.xml" % page_name), shell=True)
        page_xml = open(os.path.join(path, "%s.xml" % page_name), "rb").read().decode('utf-8')
        if "WebView" in page_xml:
            if webview_empty_re.search(page_xml):
                print("WARN: WebView empty!")
                continue
        return True

def capture_act(page_name, path, dev):
    focused_act = subprocess.check_output("adb shell dumpsys activity | %s mFocusedActivity" % config.grepper, shell=True)
    focused_act = focused_act.split(b' ')[5].decode('utf-8')
    with open(os.path.join(path, "%s.txt" % page_name), "w") as appf:
        appf.write(focused_act)
    print(focused_act)
    return True

webview_empty_re = re.compile("WebView[^/>]+/>")
def capture_web(page_name, path, dev):
    page_xml = open(os.path.join(path, "%s.xml" % page_name), "rb").read().decode('utf-8')
    if "WebView" in page_xml:
        print("WebView present")
#        os.system("python grabpage.py %s" % page_name)
    return True

def capture(page_name, direct=False, path=".", dev=None):
    if not direct:
        global last_page_name
        while True:
            enter = input("Go to Activity for %s" % page_name)
            if "s" in enter:
                return "skipped"
            elif "r" in enter:
                if last_page_name:
                    capture(last_page_name, path, dev)
                else:
                    print("No last page!")
            elif "q" in enter:
                return "quit"
            else:
                break
        last_page_name = page_name

    if not capture_img(page_name, path, dev):
        return "error"

    if not capture_act(page_name, path, dev):
        return "error"

    if not capture_layout(page_name, path, dev):
        return "error"
    else:
        capture_web(page_name, path, dev)

    return "ok"

def capture_multi(page_name, path, dev):
    if (not capture_img(page_name, path, dev) or
        not capture_act(page_name, path, dev) or
        not capture_layout(page_name, path, dev)):
        return False

ROUND_COUNT = 5

def get_next_page_id(dirs, appname, scrname):
    max_caseid = -1
    pattern = "%s_*_%s.xml" % (appname, scrname)
    pattern2 = "%s_*_%s.hier" % (appname, scrname)
    for directory in dirs:
        for entry in (glob.glob(os.path.join(directory, pattern)) +
                      glob.glob(os.path.join(directory, pattern2))):
            (_, caseid, _) = os.path.basename(entry).split('_', 2)
            caseid = int(caseid)
            if caseid > max_caseid:
                max_caseid = caseid
    return max_caseid + 1

def detect_case_count(app_name, page_name):
    return get_next_page_id([".", "../guis/"], app_name, page_name)

def capture_scrs():
    app_name = sys.argv[1]
    page_name = None
    case_num = 0
    while True:
        cmd = input("ready to capture> ")
        if cmd == "":
            if page_name is None:
                print("You must enter page name first")
            else:
                capture("%s_%d_%s" % (app_name, case_num, page_name), direct=True)
                case_num += 1
        elif cmd == "q":
            break
        else:
            page_name = cmd
            case_num = detect_case_count(app_name, page_name)
            print("capturing page %s, starting from %d" % (page_name, case_num))

def capture_manual():
    while True:
        cmd = input("ready to capture> ")
        if cmd == "":
            ret = capture_once()
            if ret == 'error':
                print("error!")
        elif cmd == "q":
            sys.exit(0)

def capture_once(path=".", dev=None):
    page_id = 0
    while (os.path.exists(os.path.join(path, "page%d.png" % page_id)) and
           os.path.exists(os.path.join(path, "page%d.xml" % page_id))):
        page_id += 1
    return capture("page%d" % page_id, direct=True, path=path, dev=dev)

def capture_old():
    if len(sys.argv) > 1:
        app_names = sys.argv[1:]
    else:
        app_names = collect_app_names()

    for app_name in app_names:
        print("Working on %s" % app_name)
        skip_app = False

        for page in non_rep_pages:
            page_name = "%s_%s" % (app_name, page)
            if capture(page_name) == "quit":
                skip_app = True
                break
        if skip_app: continue

        for case_num in range(ROUND_COUNT):
            print("=== Round %d ===" % case_num)
            for page in non_login_pages_1:
                page_name = "%s_%d_%s" % (app_name, case_num, page)
                if capture(page_name) == "quit":
                    skip_app = True
                    break
            if skip_app: break
        if skip_app: continue

        for case_num in range(ROUND_COUNT):
            print("=== Round %d ===" % case_num)
            for page in non_login_pages_2:
                page_name = "%s_%d_%s" % (app_name, case_num, page)
                if capture(page_name) == "quit":
                    skip_app = True
                    break
            if skip_app: break
        if skip_app: continue

        for case_num in range(ROUND_COUNT):
            print("=== Round %d ===" % case_num)
            for page in non_login_pages_3:
                page_name = "%s_%d_%s" % (app_name, case_num, page)
                if capture(page_name) == "quit":
                    skip_app = True
                    break
            if skip_app: break
        if skip_app: continue

        for case_num in range(ROUND_COUNT):
            print("=== Round %d ===" % case_num)
            for page in login_pages:
                page_name = "%s_%d_%s" % (app_name, case_num, page)
                if capture(page_name) == "quit":
                    skip_app = True
                    break
            if skip_app: break
        if skip_app: continue


if __name__ == "__main__":
    config.use_uimon = False
#    capture_scrs()
    capture_manual()
