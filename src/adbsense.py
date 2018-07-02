#!/usr/bin/env python3

import config

import tempfile
import logging
import re
import os
import dump
import time
import subprocess
import skimage.io
import skimage.transform
import numpy
import perfmon
import yaml
import webview
import appdb
import util
import shutil

UIAUTOMATOR_DUMPFILE = "/sdcard/window_dump.xml"
UIAUTO_DUMP_ALL = "/sdcard/win*.xml"
webview_empty_re = re.compile("WebView[^/>]+/>")

logger = logging.getLogger("sense")

prefix = "appmodel" + util.randstr(4)


@perfmon.op("sense", "grab_full")
def grab_full(dev, no_img=False):
    xml_hier = grab_hier_xml(dev)
    actname = grab_actname(dev)
    ret = {'xml': xml_hier, 'act': actname}
    if not no_img:
        scrfile = grab_screen(dev)
        ret['scr'] = scrfile

    return ret


@perfmon.op("sense", "grab_xml")
def grab_hier_xml(dev):
    tempf = tempfile.mktemp(prefix=prefix, suffix='.xml')
    has_something = False
    content = None

    for i in range(config.GRAB_XML_RETRY_LIMIT):
        try:
            dev.remove_file(UIAUTO_DUMP_ALL)
            if not dump.dodump(dev):
                logger.warning("uiautomator dump fail, retry")
                time.sleep(0.4)
                continue
            dev.grab_file(UIAUTOMATOR_DUMPFILE, tempf)

            with open(tempf) as f:
                content = f.read()
                os.remove(tempf)
                if "WebView" in content:
                    if webview_empty_re.search(content):
                        logger.warn("WebView empty")
                        has_something = True
                        continue

                if content:
                    return content
        except:
            logger.exception("uiautomator dump fail, retry")

    if has_something:
        logger.warning("partial dump failure")
        return content
    else:
        logger.error("uiautomator dump fail, retry exhausted")
        return None


actname_re = re.compile(
    "mCurrentFocus=Window{[a-z0-9 ]+\s+([a-zA-Z0-9./_]+)}")
#    "mFocusedActivity:\s+ActivityRecord{[a-z0-9 ]+\s+([a-zA-Z0-9./]+)\s+[a-z0-9]+}")
focusapp_re = re.compile(
    "mFocusedApp=.*ActivityRecord{[a-z0-9]+\s+[a-z0-9]+\s+([a-zA-Z0-9./_]+)\s+[a-z0-9]+}")


@perfmon.op("sense", "grab_act")
def grab_actname(dev):
    """mFocusedActivity: ActivityRecord{c6f4bf9 u0 com.wanelo.android/.ui.activity.post.PostProductShareActivity t706}"""
    """mCurrentFocus=Window{abea249 u0 com.nordstrom.app/com.nordstrom.app.main.activity.NordstromActivity}"""
    """mFocusedApp=AppWindowToken{20ba847 token=Token{bd93786 ActivityRecord{2f89061 u0 com.android.vending/com.google.android.finsky.activities.MainActivity t19}}}"""


#    ret = dev.run_adb_shell("dumpsys activity")
    for retry in range(config.GRAB_ACT_RETRY_LIMIT):
        ret = dev.run_adb_shell("dumpsys window windows").decode('utf-8')
        sret = actname_re.search(ret)
        if sret is None:
            sret = focusapp_re.search(ret)
            if sret is None:
                if "mCurrentFocus=null" in ret:
                    time.sleep(1)
                    continue
                # logger.error(ret)
                return None
        return sret.group(1)
    logger.error("fail to grab activity name")
    return None


@perfmon.op("sense", "grab_screen_cap")
def grab_screen_cap(dev, tempf):
    dev.remove_file("/sdcard/screen.png")
    dev.run_adb_shell("screencap -p /sdcard/screen.png")
    dev.grab_file("/sdcard/screen.png", tempf)
    if os.stat(tempf).st_size == 0:
        logger.warn("file too small")
        return False
    else:
        return True

@perfmon.op("sense", "grab_screen_snapshot")
def grab_screen_snapshot(dev, tempf):
    try:
        windowid = dev.get_windowid()
        if windowid:
            for retry in range(config.GRAB_SCREEN_SNAPSHOT_RETRY):
                subprocess.check_call(
                    "import -window %s bmp:- | convert bmp:- -limit thread 1 -resize 1200x1920 -crop 1080x1920+0+0 -define png:compression-level=0 %s" % (
                        windowid, tempf), shell=True)
                if os.path.exists(tempf) and os.stat(tempf).st_size > 0:
                        return True
    except:
        logger.exception("fail to grab image through screenshot")
    return False


@perfmon.op("sense", "grab_screen")
def grab_screen(dev):
    tempf = tempfile.mktemp(suffix=".png", prefix=prefix)

    for i in range(config.GRAB_SCREEN_RETRY_LIMIT):
        if dev.is_emulator() and grab_screen_snapshot(dev, tempf):
            break
        if grab_screen_cap(dev, tempf):
            break

    return tempf

@perfmon.op("sense", "grab_screen_fast")
def grab_screen_fast(dev, windowid=None):
    if not dev.is_emulator():
        return grab_screen(dev)

    try:
        tempf = tempfile.mktemp(suffix=".bmp", prefix=prefix)

        if windowid is None:
            windowid = dev.get_windowid()
        if windowid:
            subprocess.check_call("import -window %s %s" % (windowid, tempf), shell=True)
        return tempf
    except:
        return grab_screen(dev)

@perfmon.op("sense", "same_snapshot")
def same_snapshot(old, new, fast=False):
    ret = subprocess.run(["diff", old, new], stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE).returncode
    if ret == 0:
        return 0
    if fast:
        return -1
    proc = subprocess.run(["compare", "-fuzz", "10%", "-metric", "ae", old, new,
                           "/dev/null"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        ret = int(proc.stderr.strip())
        logger.info("pixel diff: %d", ret)
        if ret < config.WAITIDLE_PIXDIFF:
            return 0
        else:
            return ret
    except:
        return -2

@perfmon.op("sense", "wait_idle", True)
def wait_idle(dev, interval=0.2, count=3, maxtry=None):
    """idle if $count consequent snapshots are the same, max catch $max snapshots"""
    if maxtry is None:
        maxtry = config.WAITIDLE_MAXTRY

    if config.use_idle_script or not dev.is_emulator():
        ret = dev.run_adb_shell("sh /sdcard/idle.sh %f %d %d" % (interval, count, maxtry))
        if 'not' in ret.decode('utf-8'):
            logger.info('not idled')
            return False
        else:
            return True
    snapshot = None
    same_cnt = 0
    min_pixdiff = -1
    try:
        windowid = dev.get_windowid()
    except:
        logger.exception("get_windowid failed!")
        time.sleep(3)
        return False
    for i in range(maxtry):
        start_time = time.time()
        new_snapshot = grab_screen_fast(dev, windowid)
        if snapshot is not None:
            pixdiff = same_snapshot(snapshot, new_snapshot)
            if pixdiff == 0:
                same_cnt += 1
            else:
                same_cnt = 0
                if pixdiff > 0:
                    if min_pixdiff == -1 or min_pixdiff > pixdiff:
                        min_pixdiff = pixdiff
        else:
            same_cnt = 0
        if same_cnt == count:
            logger.info("waited for %d times", i)
            try:
                os.remove(snapshot)
                os.remove(new_snapshot)
            except:
                pass
            return True
        try:
            if snapshot is not None:
                os.remove(snapshot)
        except:
            pass
        snapshot = new_snapshot
        passed_time = time.time() - start_time
        if passed_time < interval:
            time.sleep(interval - passed_time)
    if snapshot is not None:
        os.remove(snapshot)

    logger.info('not idled, min pixdiff: %d', min_pixdiff)
    return False

if __name__ == "__main__":
    import sys
    xmlfile = sys.argv[1] + ".xml"
    pngfile = sys.argv[1] + ".png"

    import device
    dev = device.Device()

    scr = grab_full(dev)

    with open(xmlfile, 'w') as xmlf:
        xmlf.write(scr['xml'])
    shutil.move(scr['scr'], pngfile)
    print("at %s" % scr['act'])

def round_clear():
    logger.info("clearing /tmp/%s*" % prefix)
    subprocess.call("rm -f /tmp/%s*" % prefix, shell=True)

def load_image(filename):
    try:
        imgdata = skimage.io.imread(filename, as_grey=True)
        if imgdata.shape[0] != config.height or imgdata.shape[1] != config.width:
            imgdata = skimage.transform.resize(imgdata, (config.height, config.width))
    except:
        logger.exception("load image file %s error", filename)
        imgdata = numpy.ndarray([config.height, config.width])
    return imgdata

def grab_extra_win(dev, winid, targetfile):
    filename = "/sdcard/win%d.xml" % winid
    if not dev.grab_file(filename, targetfile):
        return False
    logger.info("grabbed extra window %s", filename)
    return True

def dump_page(dev, path, appname=None, scrname=None, guispath=None):
    ret = grab_full(dev)
    if appname is None or scrname is None:
        template = "page%d"
    else:
        template = "%s_%%d_%s" % (appname, scrname)

    if appname is None or scrname is None or guispath is None:
        page_id = 0
        while (os.path.exists(os.path.join(path, ("%s.xml" % template) % page_id)) and
               os.path.exists(os.path.join(path, ("%s.png" % template) % page_id))):
            page_id += 1
    else:
        page_id = dump.get_next_page_id([guispath, path], appname, scrname)
        if page_id > config.PER_PAGE_CAPTURE_LIMIT:
            return

    if appname is None:
        appname = appdb.guess_app(ret['act'])
        logger.info("app guessed as %s", appname)
    else:
        logger.info("dumping for app %s", appname)

    webdatas = None
    if 'WebView' in ret['xml']:
        app = appdb.get_app(appname)
        if app is None:
            app = appdb.app_from_act(ret['act'])
            logger.warning("unknown app, using %s directly", app)
        webgrabber = webview.WebGrabber(app)
        pages = webgrabber.find_webviews(dev)
        webdata = []
        for page in pages:
            webgrabber.capture_webnodes(dev, page)
            webdata.append({'title': page['title'], 'pageinfo': page,
                            'page': webgrabber.dump()})
            webgrabber.clear()
        webdatas = yaml.dump(webdata)

    logger.info("dumping to page %s", template % page_id)
    basename = os.path.join(path, template % page_id)
    with open(basename + ".xml", 'w') as xmlf:
        xmlf.write(ret['xml'])
    shutil.move(ret['scr'], basename + ".png")
    #with open(basename + ".png", 'wb') as pngf:
        #pngf.write(open(ret['scr'], 'rb').read())
    with open(basename + ".txt", "w") as actf:
        actf.write(ret['act'])
    if webdatas is not None:
        with open(basename + ".web", "w") as webf:
            webf.write(webdatas)

