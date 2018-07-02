#!/usr/bin/env python3

import sys
import os
import glob
import tags

for catname in sys.argv[1:]:
    scrs = {}
    wids = {}
    tags.load("../etc-%s" % catname)
    for filename in glob.glob("../guis-%s/*.xml" % catname):
        basename = os.path.basename(filename).split('.')[0]
        appname = basename.split('_')[0]
        scrname = basename.split('_')[-1]
        if appname not in scrs:
            scrs[appname] = {}
            wids[appname] = {}
        scrs[appname][scrname] = 1

        descfile = filename.replace('.xml', '.desc.txt')
        if os.path.exists(descfile):
            for line in open(descfile):
                tagname = line.strip().split(' ', 1)[1]
                if tags.valid(scrname, tagname):
                    wids[appname][tagname] = 1

    tot = 0
    totw = 0
    appc = 0
    for app in scrs:
        if app not in tags.apps:
            continue
        print(app, len(scrs[app]), len(wids[app]))
        tot += len(scrs[app])
        totw += len(wids[app])
        appc += 1

    print("CAT", catname, tot, 1.0 * tot / appc)
    print("CAT", catname, totw, 1.0 * totw / appc)
