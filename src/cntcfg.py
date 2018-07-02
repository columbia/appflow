#!/usr/bin/env python3

import appdb
import glob
import sys
import re
import tags

catname = sys.argv[1]

tags.load("../etc-%s" % catname)
sys_cfg_lines = 0
cfg_lines = 0
basic_lines = 0
filter_lines = 0
app_match_lines = 0
param_lines = 0
scr_match = 0
wid_match = 0
for app in tags.apps:
    for line in open("../etc-%s/%s.txt" % (catname, app)):
        line = line.strip()
        if not line or line[0] == '#':
            continue
        if line[0] == '%' or line[0] == '@':
            if ('%app_' not in line and '%sys_' not in line and
                '@app_' not in line and '@sys_' not in line and
                '@pass_intro' not in line):
                if line[0] == '%':
                    scr_match += 1
                elif line[0] == '@':
                    wid_match += 1
                continue
        if "config." in line:
            sys_cfg_lines += 1
        elif "filter_" in line:
            filter_lines += 1
        elif "empty_" in line or "search_nothing" in line:
            basic_lines += 1
        elif line[0] == '@' or line[0] == '%':
            print(line)
            app_match_lines += 1
        else:
            param_lines += 1

        cfg_lines += 1

print("TOTAL CFG:", cfg_lines, 1.0 * cfg_lines / len(tags.apps))
print("Changing Config.py:", sys_cfg_lines)
print("Filter:", filter_lines)
print("Basic:", basic_lines)
print("App matchers:", app_match_lines)
print("Params:", param_lines)
print("Screen matchers (over estimate):", scr_match)
print("Widget matchers (over estimate):", wid_match)
