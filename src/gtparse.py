#!/usr/bin/env python3

import os
import argparse
import glob
import subprocess

import statinfo
import config
import appdb
import util
import testlib


def is_override_test(tlib, feature_name, test_name):
    test = tlib.find_test(feature_name, test_name)
    if test is not None:
        return test.has_tag('override')
    else:
        #print("unknown test!", feature_name, test_name)
        return False


def is_custom_test(feature_name, test_name):
    if appdb.has_app(feature_name):
        return True
    else:
        return False


def load_gt(cat):
    apps = []
    data = {'total': {}, 'custom': {}}
    tests = []

    if cat is None:
        gt_path = config.gt_path
    else:
        gt_path = "../etc-%s/gt.tsv" % cat

    for line in open(gt_path).read().split('\n'):
        parts = line.split('\t')
        if apps == []:
            apps = parts
            continue
        if parts[0] == '':
            break
        feature = parts[0]
        if feature.startswith('@'):
            feature = feature[1:]

        testname = parts[1]
        key = "%s %s" % (feature, testname)
        tests.append(key)

        data[key] = {}

        for i in range(2, len(parts)):
            if parts[i] == '???' or parts[i] == 'BUG':
                data[key][apps[i]] = 3
            elif parts[i] == '':
                data[key][apps[i]] = 4
            else:
                try:
                    data[key][apps[i]] = int(parts[i])
                except:
                    data[key][apps[i]] = -1

    for app in util.get_test_apps(cat):
        if not app:
            continue
        total = 0
        custom = 0
        for test in tests:
            if data[test][app] == 1 or data[test][app] == 6:
                total += 1
            if data[test][app] == 5:
                custom += 1
        data['total'][app] = total
        data['custom'][app] = custom
    return (apps, data)


def compare_stat(filename, data, detail, todo, best, ignore_small, latest,
                 report_missing, only_show_err, tlib, erase, appname, use_memory):

    if appname is None:
        appname = os.path.splitext(os.path.basename(filename))[0]

    if use_memory:
        statdata = statinfo.stat_from_memory(appname)
    else:
        statdata = statinfo.load_statfile(filename)

    if erase:
        erasefile = open("%s_erase.txt" % appname, 'w')

    goodcnt = 0
    fpcnt = 0
    fncnt = 0
    flaky = 0
    todocnt = 0
    overgoodcnt = 0
    cusgoodcnt = 0

    lines = []

    for key in sorted(statdata):
        xkey = key
        feature_name, test_name = xkey.split(' ', 1)
        if appdb.has_app(feature_name) and feature_name != appname:
            continue

        if is_override_test(tlib, feature_name, test_name):
            is_override = True
            #print("override test:", key)
        else:
            is_override = False

        if is_custom_test(feature_name, test_name):
            is_custom = True
            #print("custom test:", key)
        else:
            is_custom = False

        if xkey not in data:
            #xkey = xkey.split('[')[0].strip()
            #if xkey not in data:
            #    #print("ERROR: unknown test %s" % xkey)
            #    found = False
            #    if appname == xkey.split(' ', 1)[0]:
            #        for ykey in data:
            #            if ykey.split(' ', 1)[-1] == xkey.split(' ', 1)[-1]:
            #                print("found %s for %s %s" % (ykey, key, appname))
            #                xkey = ykey
            #                found = True
            #                break
            #    if not found:
            #        if (feature_name != 'sys' and feature_name != 'meta' and
            #            report_missing):
            #            print("ERROR: GT missing test %s" % xkey)
            #        continue
            if not is_custom:
                continue

        if not is_custom:
            if appname not in data[xkey]:
                print("skipping", xkey)
                return
            gt = data[xkey][appname]
        else:
            gt = 1

        pt = statdata[key]

        if gt == 3:
            if pt[0] > 0 and pt[1] == 0:
                state = 'err+'
            elif pt[0] == 0 and pt[1] > 0:
                state = 'err-'
            else:
                state = 'err'
        elif gt == 4:
            state = 'unknown'
        else:
            if pt[0] > 0:
                if pt[1] == 0:
                    if gt == 1:
                        state = 'good'
                        if is_custom:
                            if is_override:
                                overgoodcnt += 1
                            else:
                                cusgoodcnt += 1
                        else:
                            goodcnt += 1
                    elif gt == 0:
                        state = 'FPtodo'
                        fpcnt += 1
                    elif gt == 5:
                        #if key.startswith(appname):
                        #    state = 'good'
                        #    goodcnt += 1
                        #else:
                        state = 'over+'
                    elif gt == 6:
                        state = 'good'
                        if not is_custom or is_override:
                            goodcnt += 1
                    else:
                        state = 'todo+'
                else:
                    flaky += 1
                    if gt == 1 or gt == 6:
                        state = 'flaky'
                    elif gt == 0:
                        state = 'flaky-'
                    else:
                        state = 'todo?'
            elif pt[1] > 0:
                if gt == 1:
                    state = 'FNtodo'
                    fncnt += 1
                elif gt == 0:
                    state = 'expected'
                elif gt == 5:
                    #if key.startswith(appname):
                    #    state = 'FNover'
                    #else:
                    state = 'over'
                elif gt == 6:
                    state = 'myerr'
                else:
                    state = 'todo-'
            else:
                if gt == 2:
                    state = 'expected'
                else:
                    if gt == 1:
                        if not is_custom or is_override:
                            state = 'todo'
                            todocnt += 1
                        else:
                            state = 'expected'
                    elif gt == 5:
                        state = 'over'
                    else:
                        state = 'unreach'

        (feature, testname) = key.split(' ', 1)
        if (detail or
            ('err' in state) or
            (todo and 'todo' in state) or
            (latest and 'todo' in state) or
            'flaky' in state or
            (only_show_err and ('FN' in state or 'FP' in state))):
            lines.append("%8s %10s %-60s %2d [%2d+ %2d-]" % (
                state, '@' + feature, testname, gt, pt[0], pt[1]))

        if args.erase and (state == 'FPtodo' or state == 'FNtodo' or state == 'flaky'):
            erasefile.write("%s:%s\n" % (feature, testname))

    scrhnt = elemhnt = cfg = hintcnt = 0
    hintfile = "../etc/%s.txt" % appname
    if os.path.exists(hintfile):
        for line in open(hintfile).read().split('\n'):
            if line.strip() and not line.strip().startswith('#'):
                hintcnt += 1
                if line.startswith('%'):
                    scrhnt += 1
                elif line.startswith('@'):
                    elemhnt += 1
                else:
                    cfg += 1

    cuscnt = 0
    if os.path.exists("../tlib/%s.feature" % appname):
        for line in open("../tlib/%s.feature" % appname).read().split('\n'):
            if "Scenario" in line:
                cuscnt += 1

    is_best = False
    if appname not in best or best[appname]['good'] <= goodcnt or latest:
        best[appname] = {'good': goodcnt, 'fp': fpcnt, 'fn': fncnt, 'flaky': flaky,
                         'hint': hintcnt, 'scrhint': scrhnt, 'elemhint': elemhnt,
                         'config': cfg, 'filename': filename}
        is_best = True

    totalcnt = data['total'][appname]
    customcnt = data['custom'][appname]
    if not ignore_small or (is_best and goodcnt > 10) or latest:
        for line in lines:
            print(line)
        print("%d+%d (C%d)/%d+%d FP: %d FN: %d ?: %d   TODO: %2d" % (
            goodcnt, overgoodcnt, cusgoodcnt, totalcnt, customcnt, fpcnt, fncnt, flaky,
            todocnt), "  HINT: %2d   CUSTOM: %d %10s [S%d/E%d/C%d] %s" % (
                hintcnt, cuscnt, appname, scrhnt, elemhnt, cfg, filename))


def collect_files():
    return glob.glob("../log/*/stat/*.txt")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--detail', help='detail',
                        default=False, action='store_const', const=True)
    parser.add_argument('--todo', help='only todo',
                        default=False, action='store_const', const=True)
    parser.add_argument('--err', help='only err',
                        default=False, action='store_const', const=True)
    parser.add_argument('--latest', help='show latest',
                        default=False, action='store_const', const=True)
    parser.add_argument('--nohint', help='show hint info',
                        default=False, action='store_const', const=True)
    parser.add_argument('--see', help='see log',
                        default=False, action='store_const', const=True)
    parser.add_argument('--erase', help='erase bad memory',
                        default=False, action='store_const', const=True)
    parser.add_argument('--nomem', help='load from memory',
                        default=False, action='store_const', const=True)
    parser.add_argument('file', help='stat file', nargs='*')
    args = parser.parse_args()

    appdb.collect_apps("../apks/")

    tlib = testlib.collect_pieces("../tlib/")

    cat = None
    app = None
    if len(args.file) == 1 and '.' not in args.file[0]:
        if '#' in args.file[0]:
            (cat, app) = args.file[0].split('#', 1)
        else:
            app = args.file[0]
        files = sorted(glob.glob("../log/2*/stat/%s.txt" % app))
        args.err = True
    elif len(args.file) > 0:
        files = args.file
    else:
        files = collect_files()

    (apps, data) = load_gt(cat)

    detail = args.detail or len(files) == 1

    if args.see:
        args.latest = True
    if args.latest:
        args.nomem = True

    best = {}
    if not args.nomem:
        files = ['dummy']
    if args.latest:
        files = [files[-1]]
    for filename in files:
        compare_stat(filename, data, detail=detail, todo=args.todo, best=best,
                     ignore_small=len(files) > 1, latest=args.latest,
                     report_missing=len(files) == 1, only_show_err=args.err,
                     tlib=tlib, erase=args.erase, appname=app,
                     use_memory=not args.nomem)

    for app in apps:
        if app == '':
            continue
        if app not in best:
            continue
        rec = best[app]
        print("%10s %2d+ %dFP %dFN %d? %dH [%d/%d/%d] %s" % (
            app, rec['good'], rec['fp'], rec['fn'],
            rec['flaky'], rec['hint'], rec['scrhint'],
            rec['elemhint'], rec['config'], rec['filename']))

        if args.nomem:
            logfile = rec['filename'].replace('stat/', '').replace('.txt', '.log')
            if not args.nohint:
                if os.path.exists(logfile):
                    subprocess.call("./hintstat.py %s" % logfile, shell=True)
            if args.see:
                #input("enter to see log")
                os.system("vim %s" % logfile)
        if args.erase:
            if os.path.exists("%s_erase.txt" % app):
                erased = open("%s_erase.txt" % app).read()
                print("erased:")
                print(erased)
