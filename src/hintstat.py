#!/usr/bin/env python3

import re
import os
import glob
import sys

import tags

clas_ret_re = re.compile(".*screen (.+): ([0-9]+)\+ ([0-9]+)-")
elem_ret_re = re.compile(".*locator (.+): ([0-9]+)\+ ([0-9]+)-")


def get_hint_stat(filename, stat, estat):
    for line in open(filename):
        parts = clas_ret_re.match(line)
        if parts:
            (screen, good, bad) = parts.groups()
            if screen not in stat:
                stat[screen] = [0, 0]
            stat[screen][0] = int(good)
            stat[screen][1] += int(bad)
        parts = elem_ret_re.match(line)
        if parts:
            (element, good, bad) = parts.groups()
            if element not in estat:
                estat[element] = [0, 0]
            estat[element][0] = int(good)
            estat[element][1] += int(bad)


def print_hint_stat(catname, files):
    tags.load("../etc-%s" % catname)

    detail = True

    latest = {}
    gstat = {}
    gestat = {}

    if files == []:
        files = glob.glob("../log/*/*.log")

    for filename in files:
        appname = os.path.basename(filename).split('.')[0]
        if appname not in tags.apps:
            continue

        t = os.path.basename(os.path.dirname(filename))

        if appname not in gstat:
            gstat[appname] = {}
            gestat[appname] = {}

        if appname not in latest or latest[appname] < t:
            latest[appname] = t

        get_hint_stat(filename, gstat[appname], gestat[appname])

#    for appname in latest:
#        filename = "../log/%s/%s.log" % (latest[appname], appname)
#        if appname not in gstat:
#            gstat[appname] = {}
#            gestat[appname] = {}
#        get_hint_stat(filename, gstat[appname], gestat[appname])
#

    bad_scr = 0
    bad_wid = 0
    for appname in gstat:
        stat = gstat[appname]
        goodcnt = badcnt = 0
        for screen in stat:
            if not tags.validscr(screen):
                continue
            #print("%s %s %d+ %d-" % (appname, screen, stat[screen][0], stat[screen][1]))
            if stat[screen][1] == 0 and stat[screen][0] != 0:
                if detail:
                    print("%10s  SCR %s GOOD (%d)" % (appname, screen, stat[screen][0]))
                goodcnt += 1
            elif stat[screen][1] != 0:
                if detail:
                    print("%10s  SCR %s BAD  (%d/%d)" % (appname, screen, stat[screen][0],
                                                         stat[screen][1]))
                badcnt += 1
            else:
                if detail:
                    print("%10s  SCR %s UNUSED" % (appname, screen))
        print("%10s  SCR TOTAL %d+ %d-" % (appname, goodcnt, badcnt))
        bad_scr += badcnt

        goodcnt = badcnt = 0
        estat = gestat[appname]
        for element in estat:
            #print("%s %s %d+ %d-" % (appname, element, estat[element][0],
            #estat[element][1]))
            if estat[element][1] == 0 and estat[element][0] != 0:
                if detail:
                    print("%10s ELEM %s GOOD (%d)" % (appname, element,
                                                      estat[element][0]))
                goodcnt += 1
            elif estat[element][1] != 0:
                if detail:
                    print("%10s ELEM %s BAD  (%d/%d)" % (appname, element,
                                                         estat[element][0],
                                                         estat[element][1]))
                badcnt += 1
            else:
                if detail:
                    print("%10s ELEM %s UNUSED" % (appname, element))

        print("%10s ELEM TOTAL %d+ %d-" % (appname, goodcnt, badcnt))
        bad_wid += badcnt

    print("CAT %s: SCR %d WID %d" % (catname, bad_scr, bad_wid))


if __name__ == "__main__":
    print_hint_stat(sys.argv[1], sys.argv[2:])
