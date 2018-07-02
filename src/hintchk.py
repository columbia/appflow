#!/usr/bin/env python3

import argparse
import glob

import tags
import value
import hintstat

show_unused = False
show_good = True


def get_good_cnt(app, scrhint, widhint, files):
    goodscrcnt = goodwidcnt = 0
    badscrcnt = badwidcnt = 0
    scr_stat = {}
    wid_stat = {}
    for filename in glob.glob(files + "/%s.log" % app):
        hintstat.get_hint_stat(filename, scr_stat, wid_stat)
    for key in scr_stat:
        val = scr_stat[key]
        if key not in scrhint:
            #print(key, val, "not exist")
            continue
        if val[0] > 0 and val[1] == 0:
            if show_good:
                print("GOOD SCR", key, val)
            goodscrcnt += 1
        elif val[1] > 0:
            badscrcnt += 1
    for scr in scrhint:
        if scr not in scr_stat:
            if show_unused:
                print("%s: %%%s never used!" % (app, scr))
    for key in widhint:
        val = widhint[key]
        if val not in wid_stat:
            if not "!marked:'%s'" % val in wid_stat:
                if val == 'notexist':
                    entry = [0, 1]
                else:
                    if show_unused:
                        print(key, val, "never used")
                    continue
            else:
                entry = wid_stat["!marked:'%s'" % val]
        else:
            entry = wid_stat[val]

        if entry[0] > 0 and entry[1] == 0:
            goodwidcnt += 1
            if show_good:
                print("GOOD WID", key, val, entry)
        elif entry[1] > 0:
            badwidcnt += 1

    return goodscrcnt, goodwidcnt, badscrcnt, badwidcnt


def calc_hints(cat, files):
    totwidcnt = totscrcnt = totparamcnt = 0
    for app in tags.apps:
        confcnt = widcnt = scrcnt = paramcnt = 0
        widhint = {}
        scrhint = {}
        for line in open("../etc-%s/%s.txt" % (cat, app)):
            line = line.strip()
            if line == '' or line[0] == '#':
                continue

            if value.config_re.match(line):
                confcnt += 1
            elif value.exlocator_re.match(line):
                widcnt += 1
                groups = value.exlocator_re.match(line).groups()
                widhint[groups[1]] = groups[2]
            elif value.locator_re.match(line):
                groups = value.locator_re.match(line).groups()
                if not tags.validtag(groups[0]):
                    continue
                widhint[groups[0]] = groups[1]
                widcnt += 1
            elif value.screenob_re.match(line):
                groups = value.screenob_re.match(line).groups()
                scrname = groups[0]
                if not tags.validscr(scrname):
                    continue
                scrhint[groups[0]] = groups[1]
                scrcnt += 1
            elif value.param_re.match(line):
                paramcnt += 1

        (goodscrcnt, goodwidcnt, badscrcnt, badwidcnt) = get_good_cnt(
            app, scrhint, widhint, files)
        seenscrcnt = goodscrcnt + badscrcnt
        seenwidcnt = goodwidcnt + badwidcnt

        print("%10s: S%2d(%2d-%2d) W%2d(%2d-%2d) P%2d C%2d" % (app, scrcnt, seenscrcnt,
                                                               goodscrcnt, widcnt,
                                                               seenwidcnt, goodwidcnt,
                                                               paramcnt, confcnt))
        totscrcnt += badscrcnt
        totwidcnt += badwidcnt
        #totscrcnt += scrcnt - goodscrcnt
        #totwidcnt += widcnt - goodwidcnt
        totparamcnt += paramcnt

    appcnt = len(tags.apps)
    print("S%d W%d P%d" % (totscrcnt, totwidcnt, totparamcnt))
    print("S%.1f W%.1f P%.1f" % (1.0 * totscrcnt / appcnt, 1.0 * totwidcnt / appcnt,
                                 1.0 * totparamcnt / appcnt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="hintchk")
    parser.add_argument('--cat', help='category')
    parser.add_argument('--files', help='files', default='../log/*/')
    args = parser.parse_args()
    if args.cat:
        tags.load("../etc-%s" % args.cat)
    else:
        tags.load("../etc")
    calc_hints(args.cat, args.files)
