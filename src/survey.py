#!/usr/bin/env python3

import glob
import re
import os
import analyze
import elements
import tags

empty_re = re.compile("WebView[^/>]+/>")

tags.load("../etc/tags.txt")

total_pt_cnt = 0
err_cnt = 0
for filename in glob.glob("../guis/*.xml"):
    imgfile = filename.replace('.xml', '.png')
    if not os.path.exists(imgfile):
        print("%s NOIMG" % filename)

    scrname = filename.split('/')[-1].split('.')[0].split('_')[-1]
    (items, descs) = analyze.load_case(filename)
    tree = analyze.analyze_items(items, descs)
    if items and descs and tree:
        tag_cnt = {}
        for itemid in tree:
            node = tree[itemid]
            if node['tags']:
                firsttag = node['tags'][0]
                tag_cnt[firsttag] = tag_cnt.get(firsttag, 0) + 1
        for tag in tag_cnt:
            if tags.valid(scrname, tag):
                if tag_cnt[tag] > 1:
                    if tag in elements.SINGLE_LABEL:
                        print("%s DUPTAG %s %d" % (filename, tag, tag_cnt[tag]))
            else:
                print("%s UNKNOWNTAG %s" % (filename, tag))

        if not tags.validscr(scrname):
            print("%s UNKNOWNSCR %s" % (filename, scrname))

#        print("%s OK" % filename)
    else:
        if items:
            print("%s NOLBL" % filename)
        else:
            print("%s ERR" % filename)
        err_cnt += 1
    total_pt_cnt += 1

print("total: %d / %d" % (err_cnt, total_pt_cnt))
