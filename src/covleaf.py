#!/usr/bin/env python3

import sys

import analyze
import util
import tags

catname = sys.argv[1]

tags.load("../etc-%s" % catname)

is_leaf = 'leaf' in sys.argv
is_click = 'click' in sys.argv
is_text = 'text' in sys.argv
is_visible = 'visible' in sys.argv

leaf_cnt = 0
tag_cnt = 0
scr_cnt = 0
for filename in util.collect_files("../guis-%s" % catname):
    tree = analyze.load_tree(filename)
    (appname, scrname) = util.get_aux_info(filename)

    if not tags.validapp(appname):
        continue
    if not tags.validscr(scrname) or scrname in tags.tag['ignored_screens']:
        #print('skip', scrname)
        continue

    scr_cnt += 1

    for nodeid in tree:
        node = tree[nodeid]
        tagged = False
        for tag in node['tags']:
            if tags.valid(scrname, tag):
                tagged = True
                break

        if not node['click'] and is_click:
            continue
        if node['children'] != [] and is_leaf:
            continue
        if node['text'] == '' and is_text:
            continue
        if is_visible and (node['height'] < 5 or node['width'] < 5):
            continue
        leaf_cnt += 1
        if tagged:
            tag_cnt += 1

print("screen cnt:", scr_cnt)
print("leaf cnt:", leaf_cnt, "tag cnt:", tag_cnt, "%.3f" % (1.0 * tag_cnt / leaf_cnt))
