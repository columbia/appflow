#!/usr/bin/env python3

import subprocess
import json
import glob
import os
import re
import logging

import config

logger = logging.getLogger("appdb")

apps = {
    "syspack": " com.android.packageinstaller",
}

appid_re = re.compile("Package Group.*name=(.*)")


def get_appid(apkfile):
    out = subprocess.check_output(
        [config.aapt_path, "dump", "resources", apkfile]).decode('utf-8')
    for line in out.split('\n'):
        if appid_re.match(line):
            return appid_re.match(line).group(1)


def collect_apps(apkspath):
    cachefile = os.path.join(apkspath, "appdb.cache")
    if os.path.exists(cachefile):
        logger.debug("loading cached appinfo from %s", apkspath)
        loaded_apps = json.loads(open(cachefile).read())
        apps.update(loaded_apps)
        return

    logger.info("collecting apps from %s", apkspath)
    for apkfile in glob.glob(os.path.join(apkspath, "*.apk")):
        appname = apkfile.split('/')[-1].split('.')[0]
        appid = get_appid(apkfile)

        apps[appname] = appid

    with open(cachefile, 'w') as cachef:
        cachef.write(json.dumps(apps))


def load_urls(urlsfile):
    urls = json.loads(open(urlsfile).read())
    apps.update(urls)


def get_app(appname):
    return apps.get(appname)


def has_app(appname):
    return appname in apps


def guess_app(act):
    appid = app_from_act(act)
    for app in apps:
        if apps[app] in appid:
            return app
    return None


def guess_site(url):
    urlbase = url.split('//', 1)[-1].split('/', 1)[0]
    for app in apps:
        if app in urlbase:
            return app
    return None


def app_from_act(act):
    return act.split('/')[0]


if __name__ == '__main__':
    collect_apps("../apks/")
    for appname in apps:
        print(appname, apps[appname])
