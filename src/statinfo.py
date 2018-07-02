#!/usr/bin/env python3

import os

import appdb
import miner

print_by_feature = False

def load_statfile(filename):
    data = {}
    if os.path.exists(filename):
        statf = open(filename, 'r')
        for line in statf.read().split('\n'):
            if line.strip() == '':
                continue
            (succ, fail, key) = line.split(' ', 2)
            data[key[1:]] = [int(succ), int(fail)]
        statf.close()
    return data


def stat_from_memory(app, tlibpath="../tlib/", mempath="../memory/"):
    if os.path.exists("/tmp/stat.txt"):
        os.remove("/tmp/stat.txt")
    mine = miner.Miner(None, None, None, tlibpath, True, app, None, None, None,
                       None, mempath, False)
    mine.save_stat("/tmp/stat.txt")
    return load_statfile("/tmp/stat.txt")


def print_stat(filename, only_feature):
    data = load_statfile(filename)
    stat = {}
    for key in data:
        (feature, name) = key.split(' ', 1)
        if not feature in stat:
            stat[feature] = [0, 0, 0, 0] # good, flaky, bad, never
        (good, fail) = data[key]
        if good > 0:
            if fail > 0:
                stat[feature][1] += 1
            else:
                stat[feature][0] += 1
        else:
            if fail > 0:
                stat[feature][2] += 1
            else:
                stat[feature][3] += 1
    totalgood = 0
    totalreached = 0
    for feature in stat:
        if feature in appdb.apps:
            continue
        if feature in ['sys', 'meta']:
            continue
        if only_feature is not None and feature != only_feature:
            continue
        for key in data:
            if key.split(' ')[0] == feature:
                s = data[key]
                if s[0] > 0:
                    if s[1] > 0:
                        mark = '*'
                    else:
                        mark = '+'
                else:
                    if s[1] > 0:
                        mark = '-'
                    else:
                        mark = '?'

                if mark != '?':
                    print("\t%s %s" % (key.split(' ', 1)[1], mark))
        s = stat[feature]
        if s[0] + s[1] + s[2] > 0:
            print("feature %10s: %d+ %d* %d- %d?" % (feature, s[0], s[1], s[2], s[3]))
            totalgood += s[0]
            totalreached += s[0] + s[1] + s[2]
    return (totalgood, totalreached)

def print_stats(files, only_feature):
    for filename in files:
        appname = os.path.splitext(os.path.basename(filename))[0]
        (goods, reached) = print_stat(filename, only_feature)
        print("APP %15s: %3d / %3d" % (appname.upper(), goods, reached))

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--screen', help='only for screen')
    parser.add_argument('files', help='files to parse', nargs='+')
    args = parser.parse_args()

    appdb.collect_apps("../apks/")
    print_stats(args.files, args.screen)
