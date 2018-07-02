#!/usr/bin/env python3

import appdb
import glob
import sys
import re
import tags

appdb.collect_apps("../apks/")

wid_re = re.compile('@[^\s]+')

for catname in sys.argv[1:]:
    testcnt = 0
    cus_testcnt = 0
    totline = 0
    cus_totline = 0
    app_totline = app_cnt = bridge_totline = bridge_cnt = 0

    header = 0
    cur_scr = ''
    used_scr = set()
    used_wid = set()

    dirname = "../tlib-%s" % catname
    tags.load("../etc-%s/tags.txt" % catname)
    tests = set()
    found = set()

    for line in open("%s/tests.txt" % dirname):
        (scr, name) = line.strip().split('\t')
        key = scr + ':' + name
        if not key.startswith('@'):
            key = '@' + key
        tests.add(key)

    for filename in glob.glob("%s/*.feature" % dirname):
        appname = filename.split('/')[-1].split('.')[0]
        if appname in appdb.apps:
            cus_flow = True
        else:
            cus_flow = False

        if appname == 'sys':
            continue

        test_name = ''
        is_observer = False
        is_override = False
        is_bridge = False
        is_app = False
        for line in open(filename):
            line = line.strip()
            if line.strip() == '':
                continue
            # comments
            if line.startswith('#'):
                continue
            # feature description
            if 'Feature' in line:
                continue
            # tags
            if line.startswith('@'):
                if line == '@observe':
                    is_observer = True
                if line == '@app':
                    is_app = True
                if line == '@bridge':
                    is_bridge = True
                if line == '@override':
                    is_override = True
                continue

            if 'Scenario' in line:
                cur_scr = ''
                am_observer = is_observer
                am_bridge = is_bridge
                am_app = is_app
                am_override = is_override
                is_observer = False
                is_bridge = False
                is_app = False
                is_override = False
                if am_observer:
                    #print(appname, test_name, 'OBSERVER')
                    continue
                test_name = line.split(':')[-1].strip()
                if am_bridge:
                    bridge_cnt += 1
                if am_app:
                    app_cnt += 1
                if cus_flow:
                    cus_testcnt += 1
                    #print(appname, test_name, 'CUSTOM')
                elif '@%s:%s' % (appname, test_name) in tests:
                    testcnt += 1
                    found.add('@%s:%s' % (appname, test_name))
                else:
                    #print(appname, test_name, 'DROPPED')
                    pass

            if am_observer:
                continue

            if am_bridge:
                bridge_totline += 1
            if am_app:
                app_totline += 1

            if cus_flow:
                cus_totline += 1
            elif '@%s:%s' % (appname, test_name) in tests:
                totline += 1
                if "screen is" in line or "screen is not" in line:
                    cur_scr = line.split(' ')[-1]
                    used_scr.add(cur_scr)

                if "@" in line and line[0] != '@':
                    for wid in wid_re.findall(line):
                        wid = wid[1:]
                        if tags.valid(cur_scr, wid):
                            used_wid.add(cur_scr + ':' + wid)

    print("Cat: ", catname)
    if tests - found:
        print(tests - found)
    print('Lib:   ', testcnt, totline, "%.2f" % (1.0 * totline / testcnt))
    print('Custom:', cus_testcnt, cus_totline, "%.2f" % (1.0 * cus_totline / cus_testcnt))
    print('App:', app_cnt, app_totline)
    print('Bridge', bridge_cnt, bridge_totline)
    print('A+B:', app_cnt + bridge_cnt, app_totline + bridge_totline)
    print('Used screens:', len(used_scr), list(sorted(used_scr)))
    print('Used widgets:', len(used_wid), list(sorted(used_wid)))
