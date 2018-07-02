#!/usr/bin/env python3

import sys
import xml.etree.ElementTree as ET
import re
import os
import subprocess
import config
import logging
import analyze

logger = logging.getLogger("migrate")

bound_re = re.compile("\[(\d+),(\d+)\]\[(\d+),(\d+)\]")
desc_varwidth = set(['item_brand', 'item_title', 'item_price', 'item_count', 'cat_parent', 'detail_price', 'detail_brand', 'search_keyword', 'cat_title'])
desc_varheight = set(['searchret_list', 'list_list', 'cart_list', 'item_image', 'detail_image', 'item_title', 'cat_image'])
desc_varsize = set(['item_title', 'detail_title'])
desc_samecontent = set(['item_remove'])

def extract(node):
    attrib = node.attrib

    info = {}
    info['class'] = attrib['class'].split('.')[-1]
    info['text'] = attrib['text'].replace('\n', ' ').strip()
    info['desc'] = attrib['content-desc'].replace('\n', ' ').strip()
    info['id'] = attrib['resource-id']

    (x1, y1, x2, y2) = bound_re.match(attrib['bounds']).groups()
    x1 = int(x1)
    y1 = int(y1)
    x2 = int(x2)
    y2 = int(y2)
    width = x2 - x1
    height = y2 - y1
    info['x'] = x1
    info['y'] = y1
    info['width'] = width
    info['height'] = height

    info['click'] = attrib['clickable'] == 'true'
    info['scroll'] = attrib['scrollable'] == 'true'
    info['selected'] = attrib['selected'] == 'true' or attrib['checked'] == 'true'
    info['childcount'] = len(node)
    return info

def parse(node, depth, start_id, parent_id, child_id, items):
    my_id = start_id
    start_id += 1

    if node.tag != 'hierarchy':
        nodeinfo = extract(node)
        nodeinfo['parent'] = parent_id
        nodeinfo['depth'] = depth
        nodeinfo['childid'] = child_id
        items[my_id] = nodeinfo

    childid = 0
    for child in node:
        start_id = parse(child, depth + 1, start_id, my_id, childid, items)
        childid += 1

    return start_id

def compare(myitems, itemid, origitems, origid, origdescs, good_ids):
    myself = myitems[itemid]
    himself = origitems[origid]
    origdesc = origdescs[origid]

    if myself['class'] != himself['class']:
        return (0.0, 'cls')
    if myself['depth'] != himself['depth']:
        return (0.0, 'depth')
    if myself['click'] != himself['click']:
        return (0.0, 'click')
#    if myself['scroll'] != himself['scroll']:
#        return (0.0, 'scroll')
    if myself['id'] != himself['id']:
        return (0.0, 'id')

    if origdesc in desc_samecontent:
        if myself['text'] != himself['text']:
            return (0.0, 'content')
        if myself['desc'] != himself['desc']:
            return (0.0, 'content')

    if myself['id']:
        samecount = 0
        for otheritemid in myitems:
            if myitems[otheritemid]['id'] == myself['id']:
                samecount += 1
        if samecount == 1:
            return (0.9, 'byid')

        if myself['id'] in good_ids:
            return (1.0, 'goodid')

    if myself['selected'] != himself['selected']:
        return (0.0, 'selected')

#    if not origdesc.endswith('_item'):
#        if myself['childid'] != himself['childid']:
#            return (0.0, 'childid')

    if abs(myself['width'] - himself['width']) < 3:
        if abs(myself['height'] - himself['height']) < 3:
            if myself['x'] == himself['x'] and myself['y'] == himself['y']:
                return (1.0, 'possize')
            return (0.9, 'size')

    if origdesc.endswith('_item'):
        if myself['width'] != himself['width']:
            return (0.0, 'width')
        return (0.9, 'item1')

    if origdesc in desc_varwidth:
        if abs(myself['height'] - himself['height']) < 2:
            return (0.9, 'varwidth')

    if origdesc in desc_varheight:
        if myself['width'] == himself['width']:
            return (0.9, 'varheight')

    if origdesc in desc_varsize:
        return (0.9, 'varsize')

    return (0.0, 'DEFAULT')

def describe(item):
    ret = '%10s' % item['class']
    if item['text']:
        ret += ' %s' % item['text']
    if item['desc']:
        ret += ' (%s)' % item['desc']
    if item['id']:
        ret += ' #%s' % item['id'].split('/')[-1]
    ret += ' %dx%d D%d' % (item['width'], item['height'], item['depth'])
    prop = ''
    if item['click']:
        prop += 'C'
    if item['selected']:
        prop += 'S'
    ret += ' [%s]' % prop
    ret += ' C%d' % item['childid']
    return ret

def important(items, itemid):
    item = items[itemid]

    if item['height'] < 3 or item['width'] < 3:
        return False

    cls = item['class']
    if 'Text' in cls or 'Image' in cls or 'Edit' in cls or 'Button' in cls:
        return True
    if (cls != 'View' and item['click']) or item['scroll']:
        return True
    if cls == 'View': # possible webview controls
        if item['desc']:
            return True
    return False

def printdesc(items, descs):
    for itemid in sorted(descs):
        print("%3d %15s %s" % (itemid, descs[itemid], describe(items[itemid])))

def get_good_ids(items, descs):
    ''' IDs with only one type of mark, so decisive '''
    markofid = {}
    for item in items:
        itemid = items[item]['id']
        if itemid:
            if item in descs:
                markofid[itemid] = markofid.get(itemid, []) + [descs[item]]
            else:
                markofid[itemid] = markofid.get(itemid, []) + ['NONE']
    ret = set()
    for itemid in markofid:
        markset = set(markofid[itemid])
        if len(markset) == 1 and markset.pop() != 'NONE':
            ret.add(itemid)
    return ret

def printitems(items):
    for itemid in sorted(items):
        print("%3d %s" % (itemid, describe(items[itemid])))

def invalid(item):
    if item['width'] == 0 or item['height'] == 0:
        return True
    return False

def load_example(filename):
    (items, descs) = analyze.load_case(filename)

    printdesc(items, descs)

    good_ids = get_good_ids(items, descs)

    return (items, descs, good_ids)

def guess(otheritems, otherdesc, items, descs, good_ids):
    print("GUESS:")
    for item in otheritems:
        if item in otherdesc:
            continue
        if invalid(otheritems[item]):
            continue
#            print(item, otheritems[item])

        best_score = 0
        best_desc = None
        best_reason = None

        for marked in sorted(descs):
            (score, reason) = compare(otheritems, item, items, marked, descs, good_ids)
#                if descs[marked] == 'item_price':
#                    print(describe(otheritems[item]), reason)
            if score > best_score:
                best_score = score
                best_desc = descs[marked]
                best_reason = reason
        if best_score > 0.8:
            print("%3d %15s %s %s" % (item, best_desc, describe(otheritems[item]), best_reason))
            otherdesc[item] = best_desc

    print("UNLABELED:")
    for item in sorted(otheritems):
        if important(otheritems, item):
            if not item in otherdesc:
                print("%3d %s" % (item, describe(otheritems[item])))

    for mark in sorted(set(descs.values())):
        found = False
        for item in otherdesc:
            if otherdesc[item] == mark:
                found = True
                break
        if not found:
            print("desc %s is missing" % mark)

viewproc = None
for filename in sys.argv[1:]:
    parts = filename.replace('.xml', '').split('_')
    if len(parts) != 3:
        continue
    (appname, caseid, scrname) = parts

    try:
        (items, descs, good_ids) = load_example(filename)
    except:
        logger.exception("can't load example %s" % filename)
        continue

    for otherid in range(1, 5):
        othername = "%s_%d_%s" % (appname, otherid, scrname)
        if not os.path.exists(othername + ".xml"):
            continue
        otheritems = {}
        with open(othername + ".xml") as f:
            othersrc = f.read()
        otherroot = ET.fromstring(othersrc)
        parse(otherroot, 0, 0, 0, 0, otheritems)

        if viewproc is not None:
            viewproc.kill()
        viewproc = subprocess.Popen([config.picviewer_path, othername + ".png"])

        otherdesc = {}
        if os.path.exists(othername + ".desc.txt"):
            with open(othername + ".desc.txt") as f:
                for line in f.read().split('\n'):
                    if not line: continue
                    (itemid, desc) = line.split(' ')
                    otherdesc[int(itemid)] = desc
            print("OLD:")
            printdesc(otheritems, otherdesc)

        guess(otheritems, otherdesc, items, descs, good_ids)

        while True:
            ret = input("results for %s:" % othername)
            if ret == 'y':
                with open(othername + ".desc.txt", 'w') as outf:
                    for item_id in sorted(otherdesc):
                        outf.write("%d %s\n" % (item_id, otherdesc[item_id]))
                print("saved results to %s.desc.txt" % othername)
                break
            elif ret == '?':
                printdesc(otheritems, otherdesc)
            elif ret == ';':
                printitems(otheritems)
            elif ret == 'q':
                sys.exit(0)
            elif ret == 'f':
                otherdesc = {}
                guess(otheritems, otherdesc, items, descs, good_ids)
            if len(ret) > 1:
                cmd = ret[0]
                if ret[0] == 'd':
                    itemid = int(ret.split(' ')[1])
                    del otherdesc[itemid]
                    print("removed %s" % describe(otheritems[itemid]))
                elif ret[0] == 'l':
                    caseid = ret.split(' ')[1]
                    (items, descs, good_ids) = load_example(filename.replace('0', caseid))
                    otherdesc = {}
                    guess(otheritems, otherdesc, items, descs, good_ids)
                if ret[0] >= '0' and ret[0] <= '9':
                    (itemid, desc) = ret.split(' ')
                    itemid = int(itemid)
                    otherdesc[itemid] = desc
                    print("%s <- %d %s" % (desc, itemid, describe(otheritems[itemid])))
            elif ret == '':
                break


if viewproc is not None:
    viewproc.kill()
