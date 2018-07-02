#!/usr/bin/env python3

import xml.etree.ElementTree as ET
import re
import os
import logging
import progressbar
import argparse
import yaml
import time
from PIL import Image
import pickle

import util
import config
import listinfo
import webview
import webdriver
import dialog
import hidden

try:
    from yaml import CLoader as YAMLLoader
except:
    from yaml import Loader as YAMLLoader

bound_re = re.compile("\[(\d+),(\d+)\]\[(\d+),(\d+)\]")
price_re = re.compile("\$?[0-9.]+")

logger = logging.getLogger("analyze")

convert_names = {
    'P': 'TextView',
    'H1': 'Big TextView',
    'H2': 'Big TextView',
    'H3': 'Big TextView',
    'SMALL': 'Small TextView',
    'A': 'Link',
    'I': 'Icon',
    'LI': 'ListItem',
    'UL': 'ListView',
}
textlike_names = set(['LABEL', 'SPAN', 'DIV', 'TD'])
class_ranks = {
    'TextView': 3,
    'ImageView': 3,
    'EditText': 3,
    'Spinner': 3,
    'Button': 3,
}
container_classes = ['HTML', 'BODY', 'MAIN', 'DIV', 'SPAN', 'FORM', '#document',
                     'FIELDSET', 'FORM', "LI"]
SCALE_RATIOS = [0.5, 0.666666, 1.0, 1.333333, 1.5, 2.0, 3.0]


def find_closest(val, cands):
    best = cands[0]
    for cand in cands:
        if abs(val - cand) < abs(val - best):
            best = cand
    return best


class XMLParser(object):
    def extract(self, node):
        attrib = node.attrib

        info = {}
        info['class'] = attrib['class'].split('.')[-1]
        info['text'] = attrib['text'].replace('\n', ' ').strip()
        info['desc'] = attrib['content-desc'].replace('\n', ' ').strip()
        info['id'] = attrib['resource-id'].split('/')[-1]

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
        info['scroll'] = attrib['scrollable'] == 'true' and info['class'] != 'Spinner'
        info['selected'] = attrib['selected'] == 'true'
        info['password'] = attrib['password'] == 'true'
        info['focused'] = attrib['focused'] == 'true'
        info['checkable'] = attrib['checkable'] == 'true'
        info['childcount'] = len(node)
        info['webview'] = False # later
        return info

    def parse(self, node, depth, start_id, parent_id, child_id, items):
        my_id = start_id
        start_id += 1

        if node.tag != 'hierarchy':
            nodeinfo = self.extract(node)
        else:
            nodeinfo = {
                'class': 'ROOT',
                'text': '',
                'desc': '',
                'id': '',
                'click': False,
                'scroll': False,
                'selected': False,
                'password': False,
                'focused': False,
                'checkable': False,
                'webview': False,
                'x': 0,
                'y': 0,
                'width': 0,
                'height': 0
            }
        nodeinfo['parent'] = parent_id
        nodeinfo['depth'] = depth
        nodeinfo['childid'] = child_id
        items[my_id] = nodeinfo

        childid = 0
        children = []
        for child in node:
            children.append(start_id)
            start_id = self.parse(child, depth + 1, start_id, my_id, childid, items)
            childid += 1

        items[my_id]['children'] = children

        return start_id


def fix_size(items, filename):
    imgfile = os.path.splitext(filename)[0] + '.png'
    if not os.path.exists(imgfile):
        return

    img = Image.open(imgfile)

    for itemid in sorted(items):
        if items[itemid]['width'] + items[itemid]['x'] > 0:
            orig_width = items[itemid]['width'] + items[itemid]['x']
            orig_height = items[itemid]['height'] + items[itemid]['y']
            minid = itemid
            break
    #orig_width = items[1]['width'] + items[1]['x']
    #orig_height = items[1]['height'] + items[1]['y']
    if orig_width == config.width or orig_height == config.real_height:
        return

    if items[minid]['x'] != 0:
        # not at top-left, usually dialog
        if orig_width <= config.width and orig_height <= config.real_height:
            # seems fine
            return

    real_height = img.height * orig_width / img.width
    for itemid in items:
        item = items[itemid]
        if (item['x'] + item['width'] < 0 or
            item['x'] > orig_width or
            item['y'] + item['height'] < 0 or
            item['y'] > real_height):
            logger.debug("removing OOS %s", util.describe(item))
            item['x'] = item['y'] = item['width'] = item['height'] = 0

    ratio = 1.0 * orig_width / img.width
    img_ratio = find_closest(ratio, SCALE_RATIOS)
    fix_ratio = img_ratio * img.width / config.width
    logger.debug("fixing %s: %d != %d %d, ratio %.3f -> %.3f -> %.3f" % (
        filename, orig_width, config.width, img.width, ratio, img_ratio, fix_ratio))

    for itemid in items:
        items[itemid]['x'] = int(items[itemid]['x'] / fix_ratio)
        items[itemid]['y'] = int(items[itemid]['y'] / fix_ratio)
        items[itemid]['width'] = int(items[itemid]['width'] / fix_ratio)
        items[itemid]['height'] = int(items[itemid]['height'] / fix_ratio)


def load_case(filename):
    filebase = os.path.splitext(filename)[0]
    if '.hier' in filename:
        loaded = webdriver.load(filebase)
        items = loaded['items']
    else:
        with open(filename) as f:
            src = f.read()

        items = parse_xml(src)

    fix_size(items, filename)

    descs = util.load_desc(filebase, 'desc')
    regs = util.load_desc(filebase, 'regs')
#    imgname = filename.replace('.xml', '.png')

    webfile = filebase + '.web'
    if os.path.exists(webfile):
        webdata = yaml.load(open(webfile).read(), Loader=YAMLLoader)
        grabber = webview.WebGrabber()
        grabber.clear_items(items)
        for page in webdata:
            grabber.load(page['page'])
            grabber.annotate(items, page['title'], len(webdata))
            grabber.clear()

    return (items, descs, regs)


def parse_xml(src):
    root = ET.fromstring(src)
    items = {}
    XMLParser().parse(root, 0, 0, 0, 0, items)
    return items


def remove_nest_click(tree, itemid, origid):
    orignode = tree[origid]
    for otherid in tree:
        if tree[otherid]['parent'] == itemid:
            othernode = tree[otherid]
            if (othernode['click'] and
                othernode['x'] >= orignode['x'] and
                othernode['x'] + othernode['width'] <=
                orignode['x'] + orignode['width'] and
                othernode['y'] >= orignode['y'] and
                othernode['y'] + othernode['height'] <=
                    orignode['y'] + orignode['height']):
                print("because of %s" % util.describe_node(orignode))
                print("removing click on %s" % util.describe_node(othernode))
                othernode['click'] = False
            remove_nest_click(tree, otherid, origid)


def subtree_collect(tree, nodeid):
    ret = [nodeid]
    for otherid in tree:
        if tree[otherid]['parent'] == nodeid:
            ret += subtree_collect(tree, otherid)
    return ret


def is_container(node):
    return ('Layout' in node['class'] or 'Group' in node['class'] or
            node['class'] in container_classes)


def is_list_container(node):
    return 'Recycle' in node['class'] or 'List' in node['class']


def has_focus(tree, nodeid):
    if tree[nodeid]['focused']:
        return True
    for childid in tree:
        if tree[childid]['parent'] == nodeid:
            if has_focus(tree, childid):
                return True
    return False


def collect_subtree_id(items, itemid):
    ret = items[itemid]['id']
    for childid in items[itemid]['children']:
        ret += collect_subtree_id(items, childid)
    return ret


def find_in_old(tree, items, nodeid, oldtree, olditems, id_only):
    node = tree[nodeid]
    for rawid in node['raw']:
        for oldrawid in olditems:
            item = items[rawid]
            olditem = olditems[oldrawid]
            if (item['class'] == olditem['class'] and
                item['x'] == olditem['x'] and item['y'] == olditem['y'] and
                item['width'] == olditem['width'] and
                item['height'] == olditem['height'] and
                    item['text'] == olditem['text'] and item['desc'] == olditem['desc']):
                if item['id'] != '' and id_only:
                    if item['id'] == olditem['id']:
                        logger.debug("found old/new id %s", item['id'])
                        return oldrawid
                else:
                    # id missing, use subtree id
                    itemsubid = collect_subtree_id(items, rawid)
                    oldsubid = collect_subtree_id(olditems, oldrawid)
                    if itemsubid != '' and itemsubid == oldsubid:
                        logger.debug("found old/new subtree id %s", itemsubid)
                        return oldrawid
    return None


def get_class_rank(c):
    return class_ranks.get(c, 0)


def is_webnode(nodeid, tree):
    node = tree[nodeid]
    if node['webview']:
        return True
    while node['parent'] != 0:
        if 'webview' in node['class'].lower():
            tree[nodeid]['webview'] = True
            return True
        node = tree[node['parent']]
    return False


def node_filtered(tree, nodeid):
    node = tree[nodeid]
    children = node['children']
    if config.REMOVE_SMALL_LEAF:
        if len(children) == 0 and (node['width'] < 10 or node['height'] < 10):
            return True
    if node['width'] * node['height'] == 0:
        return True

    return False


def collect_children(tree):
    for item in tree:
        children = []
        for other in tree:
            if tree[other]['parent'] == item:
                children.append(other)
        tree[item]['children'] = children
        for i in range(len(children)):
            tree[children[i]]['childid'] = i


def mark_order(items, node, myid):
    items[node]['order'] = myid
    cur_id = myid + 1
    for i in range(len(items[node]['children']) - 1, -1, -1):
        cur_id = mark_order(items, items[node]['children'][i], cur_id)

    return cur_id


def remove_hidden(items, descs):
    mark_order(items, sorted(items)[0], 0)
    removed = []
    for item in sorted(items):
        me = items[item]
        if 'x' not in me:
            continue
        if me['parent'] in removed:
            removed.append(item)
            print('removing child %s' % util.describe(items[item]))
            if item in descs:
                print('WARNING: removing labeled item!')
            continue
        for other in sorted(items):
            him = items[other]
            if him['order'] > me['order']:
                if (him['x'] <= me['x'] and
                    him['x'] + him['width'] >= me['x'] + me['width'] and
                    him['y'] <= me['y'] and
                    him['y'] + him['height'] >= me['y'] + me['height'] and
                    not (him['x'] == me['x'] and
                         him['y'] == me['y'] and
                         him['width'] == me['width'] and
                         him['height'] == me['height'])):
                    removed.append(item)
                    logger.info('removing %s because %s', util.describe(me),
                                util.describe(him))
                    if item in descs:
                        print('WARNING: removing labeled item!')
                    break
    for item in sorted(removed):
        parent = items[item]['parent']
        del items[item]
        if parent in items:
            items[parent]['children'].remove(item)


def analyze_xmlfile(filename):
    (items, descs, regs) = load_case(filename)
    return Analyzer().analyze_items(items, descs, regs, False, False, [])


def analyze(files, print_rets=False, show_progress=False, print_items=False,
            print_error=False, show_ocr=False, show_stat=False, use_ocr=False):
    ret = []
    if show_progress:
        progress = progressbar.ProgressBar()
        items = progress(files)
    else:
        items = files

    analyzer = Analyzer()
    for filename in items:
        filebase = os.path.splitext(filename)[0]
        logger.debug("analyzing %s" % filename)

        (items, descs, regs) = load_case(filename)
        if print_items:
            util.printitems(items)
        start_time = time.time()
        newtree = analyzer.analyze_items(items, descs, regs, print_items, print_error, [])
        ret.append(newtree)
        if print_rets:
            util.print_tree(newtree)
            logger.info("Time used: %.3fs", time.time() - start_time)

        if use_ocr:
            hidden.add_ocrinfo(newtree, filebase + '.png')
            hidden.find_hidden_ocr(newtree)
            util.print_tree(newtree)

        if print_rets:
            dlg = dialog.detect_dialog(newtree)
            if dlg[0]:
                logger.info("I think this is dialog")
                for btnid in dlg[1]:
                    logger.info("btn: %s", util.describe_node(newtree[btnid]))
                    logger.info("is: %s",
                                dialog.detect_dialog_button(newtree, btnid, dlg[1]))
                logger.info("decide to click: %s", dialog.decide_dialog_action(newtree))

        if print_error:
            for itemid in descs:
                found = False
                for nodeid in newtree:
                    if itemid in newtree[nodeid]['raw']:
                        found = True
                        break
                if not found:
                    logger.error("REMOVED: %s %d %s %s", os.path.basename(filename),
                                 itemid, descs[itemid], util.describe(items[itemid]))

    if show_stat:
        analyzer.show_stat()
    return ret


def preorder(items, itemid):
    ret = [itemid]
    for child in items[itemid]['children']:
        ret += preorder(items, child)
    return ret

# Does not work
#        remove_hidden(items, descs)


def analyze_items(items, descs={}, print_rets=False, print_error=False, history=[],
                  regs={}):
    return Analyzer().analyze_items(items, descs, regs, print_rets, print_error, history)


class Analyzer(object):
    def __init__(self):
        self.stat = {}

    def incstat(self, name, val=1):
        self.stat[name] = self.stat.get(name, 0) + val

    # Methods to change the tree
    def del_subtree(self, tree, nodeid):
        logger.debug("deleting subtree %d", nodeid)
        todel = subtree_collect(tree, nodeid)
        for delid in todel:
            del tree[delid]

    def delnode(self, tree, nodeid):
        logger.debug("removing %s: %s", nodeid, util.describe_node(tree[nodeid]))
        del tree[nodeid]

    def merge_geo(self, dst, src):
        if dst['width'] * dst['height'] == 0:
            x1 = src['x']
            x2 = src['x'] + src['width']
            y1 = src['y']
            y2 = src['y'] + src['height']
        elif src['width'] * src['height'] == 0:
            x1 = dst['x']
            x2 = dst['x'] + dst['width']
            y1 = dst['y']
            y2 = dst['y'] + dst['height']
        else:
            x1 = min(dst['x'], src['x'])
            y1 = min(dst['y'], src['y'])
            x2 = max(dst['x'] + dst['width'], src['x'] + src['width'])
            y2 = max(dst['y'] + dst['height'], src['y'] + src['height'])
        dst['x'] = x1
        dst['y'] = y1
        dst['width'] = x2 - x1
        dst['height'] = y2 - y1
        dst['origx'] = src['origx']
        dst['origy'] = src['origy']
        dst['origw'] = src['origw']
        dst['origh'] = src['origh']
        dst['origitem'] = src['origitem']

    def merge_ctx(self, dst, src):
        if src['text']:
            if dst['text']:
                dst['text'] += ' '
            dst['text'] += src['text']
        if src['desc']:
            dst['desc'] += ' ' + src['desc']
        if src['id']:
            dst['id'] += ' ' + src['id']
        dst['raw'] += src['raw']
        dst['tags'] += src['tags']
        dst['regs'] += src['regs']
        dst['click'] = dst['click'] or src['click']
        dst['scroll'] = dst['scroll'] or src['scroll']
        dst['password'] = dst['password'] or src['password']
        dst['focused'] = dst['focused'] or src['focused']
        dst['checkable'] = dst['checkable'] or src['checkable']

    def merge_node_to(self, tree, targetid, srcid):
        target = tree[targetid]
        src = tree[srcid]
        self.merge_ctx(target, src)
        self.merge_geo(target, src)
        for childid in tree:
            if tree[childid]['parent'] == srcid:
                tree[childid]['parent'] = targetid
        self.delnode(tree, srcid)

    def fix_size_to_scr(self, items):
        for itemid in range(max(items)):
            if itemid not in items:
                continue
            item = items[itemid]

            if item['x'] < 0:
                if item['x'] + item['width'] < 0:
                    item['x'] = item['width'] = 0
                else:
                    item['width'] += item['x']
                    item['x'] = 0

            if item['y'] < 0:
                if item['y'] + item['height'] < 0:
                    item['y'] = item['height'] = 0
                else:
                    item['height'] += item['y']
                    item['y'] = 0

            if item['y'] + item['height'] > config.height:
                if item['y'] > config.height:
                    item['y'] = item['height'] = 0
                else:
                    item['height'] = config.height - item['y']

            if item['x'] + item['width'] > config.width:
                if item['x'] > config.width:
                    item['x'] = item['width'] = 0
                else:
                    item['width'] = config.width - item['x']

    # Mark important nodes
    def important(self, items, itemid):
        item = items[itemid]

        if item['height'] < 1 or item['width'] < 1:
            return False

        if item['id']:
            return True

        cls = item['class']
        if 'Image' in cls or 'Button' in cls or 'Edit' in cls:
            #    if 'Button' in cls or 'Edit' in cls:
            return True
        if 'TextView' in cls or cls in textlike_names:
            if item['text'] or item['desc']:
                return True
        if (cls != 'View' and item['click']) or item['scroll']:
            return True
        if not item['webview'] and item['click']:
            return True
        if cls == 'View': # possible webview controls
            if item['desc'] or item['id']:
                return True
        if item['text']:
            return True
        return False

    def mark_important_node(self, nodeid, items):
        is_important = False
        if nodeid != 0 and self.important(items, nodeid):
            is_important = True

        for childid in items[nodeid]['children']:
            self.mark_important_node(childid, items)

        child_important_count = 0
        for childid in items[nodeid]['children']:
            if items[childid]['important']:
                child_important_count += 1
    #    if child_important_count > 1:
    #        is_important = True

        sub_important = 0
        for childid in items[nodeid]['children']:
            if items[childid]['important'] or items[childid]['sub_important'] > 0:
                sub_important += 1

        items[nodeid]['sub_important'] = sub_important
        if sub_important > 0: # and nodeid != 0:
            is_important = True

        if is_important:
            logger.debug("mark %d important [%d]", nodeid, sub_important)
        else:
            logger.debug("mark %d not important [%d]", nodeid, sub_important)
        items[nodeid]['important'] = is_important

    def mark_important(self, items):
        self.mark_important_node(0, items)

    def choose_merge_class(self, c1, c2):
        s1 = get_class_rank(c1)
        s2 = get_class_rank(c2)
        if s1 > s2:
            return c1
        else:
            return c2

    def process(self, tree, items, history):
        mod = False
        if len(tree) == 0:
            return False
        max_id = max(tree)
        for nodeid in range(max_id):
            if nodeid not in tree:
                continue

            node = tree[nodeid]
            children = []
            for childid in tree:
                if tree[childid]['parent'] == nodeid:
                    children.append(childid)
            if len(children) > 0:
                child0 = tree[children[0]]
            if len(children) > 1:
                child1 = tree[children[1]]

            if config.MERGE_NEIGHBOUR:
                for childno in range(1, len(children)):
                    childid = children[childno]
                    child = tree[childid]
                    target = tree[children[childno - 1]]
                    if not is_container(child) and child['class'] == target['class']:
                        self.merge_ctx(target, child)
                        self.merge_geo(target, child)
                        del tree[childid]
                        logger.debug("merge neighbour")
                        self.incstat("neighbour")
                        return True

            if (config.REMOVE_SINGLE_CHILD_CONTAINER and
                    len(children) == 1 and
                    not is_list_container(node) and
                    is_container(node) and
                    (not node['text'] and not node['desc']) and
                    (not config.only_double_containers or is_container(child0))):
                #            and (node['click'] == child0['click'] == False or
                #                 is_container(child0))
                #    ):
                #            grandcount = 0
                #for childid in tree:
                #    if tree[childid]['parent'] == children[0]:
                #        tree[childid]['parent'] = nodeid
                #                    grandcount += 1
                #            if grandcount == 0:
                #child = child0
                node['class'] = self.choose_merge_class(node['class'], child0['class'])
                # + 'C' + 'C' * (len(node['class']) - len(node['class'].rstrip('C')))
                self.merge_node_to(tree, nodeid, children[0])
                #merge_ctx(node, child)
                #merge_geo(node, child)
                #del tree[children[0]]
                logger.debug("single")
                self.incstat("single")
                mod = True
                continue
            if config.MERGE_IMAGE_AND_TEXT_LEAF:
                if len(children) == 2 and (
                    'ImageView' in child0['class'] and 'TextView' in child1['class'] or
                        'ImageView' in child1['class'] and 'TextView' in child0['class']):
                    target = child0
                    src = child1
                    target['class'] = 'ImageText'
                    self.merge_ctx(target, src)
                    self.merge_geo(target, src)
                    del tree[children[1]]
                    mod = True
                    self.incstat("img+text")
                    return mod
            if config.REMOVE_EMPTY_CONTAINER:
                if (is_container(node) and len(children) == 0 and
                        not node['click'] and not node['id'] and not node['text']):
                    if nodeid in tree:
                        del tree[nodeid]
                    logger.debug("remove empty container")
                    mod = True
                    self.incstat("empty")
                    return mod
                if (is_container(node) and len(children) == 0 and not node['click'] and
                    node['width'] == config.width and
                        node['height'] == config.real_height_nostatus):
                    del tree[nodeid]
                    logger.debug("remove empty container")
                    self.incstat("empty")
                    return True

            if (node['class'] == 'ListView' and node['click'] and
                    not is_webnode(nodeid, tree)):
                for child in children:
                    tree[child]['click'] = True
                node['click'] = False

            if config.REMOVE_NEST_CLICK and node['click'] and node['class'] != 'View':
                    remove_nest_click(tree, nodeid, nodeid)

            if config.KEEP_ONLY_FOREGROUND:
                if len(children) == 2:
                    if (child0['height'] >= config.real_height_nostatus and
                        child1['height'] >= config.real_height_nostatus and
                        (child0['width'] == config.width or
                         child1['width'] == config.width)):
                        if child0['width'] < config.width and child0['width'] != 0:
                            logger.debug("del background (width) %d first", nodeid)
                            self.del_subtree(tree, children[1])
                            self.incstat("del bg")
                            return True
                        elif child1['width'] < config.width and child1['width'] != 0:
                            logger.debug("del background (width) %d second", nodeid)
                            self.del_subtree(tree, children[0])
                            self.incstat("del bg")
                            return True

                if node['class'] == 'DrawerLayout' and len(children) == 2:
                    if (tree[children[0]]['width'] == config.width and
                            tree[children[1]]['width'] != config.width):
                        logger.debug("del background (drawer) c0")
                        self.del_subtree(tree, children[0])
                        self.incstat("del bg drawer")
                        return True
                    elif (tree[children[1]]['width'] == config.width and
                            tree[children[0]]['width'] != config.width):
                        logger.debug("del background (drawer) c1")
                        self.del_subtree(tree, children[1])
                        self.incstat("del bg drawer")
                        return True

            if config.KEEP_ONLY_FOREGROUND_H:
                if len(children) == 2:
                    if (tree[children[0]]['width'] == config.width and
                        tree[children[1]]['width'] == config.width and
                        (tree[children[0]]['height'] >= config.real_height_nostatus or
                        tree[children[1]]['height'] >= config.real_height_nostatus)):
                        if (child0['height'] < config.real_height_nostatus and
                            child0['height'] > 0.2 * config.real_height_nostatus):
                            logger.debug("del background (height) %d second", nodeid)
                            self.del_subtree(tree, children[1])
                            self.incstat("del bg h")
                            return True
                        elif (child1['height'] < config.real_height_nostatus and
                              child1['height'] > 0.2 * config.real_height_nostatus):
                            logger.debug("del background (height) %d first", nodeid)
                            self.del_subtree(tree, children[0])
                            self.incstat("del bg h")
                            return True

            if config.FRAME_LAYOUT_CHILD:
                if node['class'] == 'FrameLayout' and len(children) > 1:
                    if (child0['width'] == child1['width'] == config.width and
                        child0['height'] == child1['height'] ==
                        config.real_height_nostatus):
                        st1 = subtree_collect(tree, children[1])
                        if len(st1) > 1:
                            self.del_subtree(tree, children[0])
                            self.incstat("framelayout")
                            return True

            if config.REMOVE_OVERLAPPING:
                if len(children) == 2 and node['class'] == 'FrameLayout':
                    if (child0['width'] == child1['width'] == config.width and
                        child0['height'] == child1['height'] ==
                        config.real_height_nostatus):
                        if has_focus(tree, children[0]):
                            logger.debug("del background (focus) c1")
                            self.del_subtree(tree, children[1])
                            self.incstat("del bg focus")
                            return True
                        if has_focus(tree, children[1]):
                            logger.debug("del background (focus) c0")
                            self.del_subtree(tree, children[0])
                            self.incstat("del bg focus")
                            return True

            if config.REMOVE_BOTSLIDE_BACKGROUND:
                if len(children) == 2:
                    if node['parent'] in tree:
                        if (tree[children[0]]['width'] == config.width and
                            tree[children[1]]['width'] == config.width and
                            (tree[children[0]]['height'] == node['height'] or
                            tree[children[1]]['height'] == node['height'])):
                            if (tree[children[0]]['height'] != node['height'] and
                                tree[children[0]]['height'] > 0.2 * node['height'] and
                                tree[children[0]]['height'] + tree[children[0]]['y'] ==
                                config.real_height):
                                logger.debug("del botslide %d second", nodeid)
                                self.del_subtree(tree, children[1])
                                self.incstat("botslide")
                                return True
                            elif (tree[children[1]]['height'] != node['height'] and
                                  tree[children[1]]['height'] > 0.2 * node['height'] and
                                  tree[children[1]]['height'] + tree[children[1]]['y'] ==
                                  config.real_height):
                                logger.debug("del botslide %d first", nodeid)
                                self.del_subtree(tree, children[0])
                                self.incstat("botslide")
                                return True

            if config.REMOVE_ALPHA_OVERLAY:
                for childid in children:
                    child = tree[childid]
                    if child['id'] == 'alpha_overlay':
                        for otherchildid in children:
                            otherchild = tree[otherchildid]
                            if otherchildid == childid:
                                continue
                            if (otherchild['width'] == child['width'] and
                                otherchild['height'] == child['height']):
                                self.del_subtree(tree, otherchildid)
                                self.del_subtree(tree, childid)
                                logger.debug("del alpha background %d", nodeid)
                                self.incstat("del alpha bg")
                                return True

            if config.MERGE_WEBVIEW_LABEL and node['webview']:
                if len(children) == 2:
                    if ((child0['class'] == 'Button' or child0['class'] == 'CheckBox') and
                        child1['class'] == 'SPAN' and child0['text'] == ''):
                        self.merge_node_to(tree, children[0], children[1])
                        self.incstat("webview label")
                        return True
                if (len(children) >= 2 and
                    child0['x'] == child1['x'] and child0['y'] == child1['y'] and
                    child0['width'] == child1['width'] and
                    child0['height'] == child1['height']):
                    self.merge_node_to(tree, children[0], children[1])
                    self.incstat("webview label")
                    return True

            if config.CONVERT_WEBVIEW_CLASS and node['webview']:
                if node['class'] in textlike_names and children == []:
                    node['class'] = 'TextView'
                    self.incstat("textlike")
                    mod = True
                    continue
                if node['class'] in convert_names:
                    node['class'] = convert_names[node['class']]
                    self.incstat("convert")
                    mod = True
                    continue

            if config.REMOVE_OUT_OF_SCREEN:
                right, bottom = (node['x'] + node['width'], node['y'] + node['height'])
                if right > config.width:
                    right = config.width
                if bottom > config.height:
                    bottom = config.height
                width = right - node['x']
                height = bottom - node['y']
                if width < 0 or height < 0:
                    logger.debug("del out of screen")
                    self.incstat("out of screen")
                    self.del_subtree(tree, nodeid)
                    mod = True
                    continue

        return mod

    def postprocess(self, tree, items, history):
        for nodeid in sorted(tree):
            if nodeid in tree:
                node = tree[nodeid]
            children = []
            for childid in tree:
                if tree[childid]['parent'] == nodeid:
                    children.append(childid)
            if len(children) > 0:
                child0 = tree[children[0]]
            if len(children) > 1:
                child1 = tree[children[1]]

            if config.REMOVE_OVERLAP_OLD:
                if (len(children) > 1 and node['class'] == 'FrameLayout' and
                    child0['width'] == child1['width'] == config.width and
                    child0['height'] == child1['height'] == config.real_height_nostatus):

                    st1 = subtree_collect(tree, children[-1])
                    if len(st1) > 1:
                        for (olditems, oldtree) in reversed(history):
                            oldme = find_in_old(tree, items, nodeid, oldtree, olditems,
                                                True)
                            if oldme is not None:
                                logger.debug("old me: %s", util.describe(olditems[oldme]))
                                appear_in_old = []
                                for childid in children:
                                    oldchild = find_in_old(tree, items, childid, oldtree,
                                                           olditems, False)
                                    if oldchild is not None:
                                        appear_in_old.append(childid)
                                    else:
                                        break

                                if (appear_in_old != [] and
                                        len(appear_in_old) < len(children)):
                                    for childid in appear_in_old:
                                        self.del_subtree(tree, childid)
                                    self.incstat("overlap old")
                                    logger.debug("overlap old %s children %s", node['id'],
                                                 appear_in_old)
                                    return True

        return False

    def get_prefix(self, items, item):
        my_depth = items[item]['depth']
        p = items[item]['parent']
        while p != 0 and not items[p]['important']:
            p = items[p]['parent']
        p_depth = items[p]['depth']
        return '%-25s' % (' ' * p_depth + '+' + '-' * (my_depth - p_depth - 1))

    def analyze_items(self, items, descs, regs, print_rets, print_error, history):
        self.fix_size_to_scr(items)

        self.mark_important(items)

        parents = [0]
        newtree = {}
        for itemid in preorder(items, 0):
            item = items[itemid]
            if item['important']:
                nodeinfo = {}

                par = -1
                while len(parents) > 0 and (
                    item['depth'] <= items[parents[-1]]['depth'] or
                        items[item['parent']]['depth'] < items[parents[-1]]['depth']):
                    parents.pop()
                if len(parents) > 0:
                    par = parents[-1]

                if print_rets:
                    print('%3d' % itemid, self.get_prefix(items, itemid),
                          util.describe(item), item['parent'], par)
    #            orig = item
                nodeinfo['parent'] = par
                nodeinfo['class'] = item['class']
                nodeinfo['text'] = item['text']
                nodeinfo['desc'] = item['desc']
                nodeinfo['id'] = item['id']
                nodeinfo['raw'] = [itemid]
                nodeinfo['width'] = item['width']
                nodeinfo['height'] = item['height']
                nodeinfo['x'] = item['x']
                nodeinfo['y'] = item['y']
                nodeinfo['origw'] = nodeinfo['width']
                nodeinfo['origh'] = nodeinfo['height']
                nodeinfo['origx'] = nodeinfo['x']
                nodeinfo['origy'] = nodeinfo['y']
                nodeinfo['click'] = item['click']
                nodeinfo['scroll'] = item['scroll']
                nodeinfo['password'] = item['password']
                nodeinfo['focused'] = item['focused']
                nodeinfo['checkable'] = item['checkable']
                nodeinfo['childid'] = 0 # placemarker
                nodeinfo['webview'] = item['webview']
                nodeinfo['origitem'] = item
                if itemid in descs:
                    nodeinfo['tags'] = [descs[itemid]]
                else:
                    nodeinfo['tags'] = []
                if itemid in regs:
                    nodeinfo['regs'] = [regs[itemid]]
                else:
                    nodeinfo['regs'] = []

                newtree[itemid] = nodeinfo

                parents.append(itemid)

        self.incstat("before", len(newtree))
        if print_rets:
            util.print_tree(newtree)
        while self.process(newtree, items, history):
            if print_rets:
                util.print_tree(newtree)
                if print_error:
                    for itemid in descs:
                        found = False
                        for nodeid in newtree:
                            if itemid in newtree[nodeid]['raw']:
                                found = True
                                break
                        if not found:
                            logger.error("REMOVED: %d %s %s", itemid, descs[itemid],
                                         util.describe(items[itemid]))

            pass
        while self.postprocess(newtree, items, history):
            pass
        self.incstat("after", len(newtree))
        collect_children(newtree)
        return newtree

    def show_stat(self):
        for rule in self.stat:
            logger.info("%s: %d" % (rule, self.stat[rule]))


def intersect(a, b):
    start = min(a[0], b[0])
    end = max(a[-1], b[-1])
    return start < end


def collect_treeinfo(tree):
    dup_ids = set()
    itemlike = set()
    listlike = set()

    id_count = listinfo.count_ids(tree)
    parent = {}
    parent_count = {}
    dup_nodes = []
    for xid in id_count:
        if id_count[xid] > 1:
            nodes = listinfo.find_same_ids(tree, xid)
            dup_ids.update(nodes)

            # lca of those dup nodes
            # likely same list parent
            lca = listinfo.get_lca(tree, nodes)
            parent[xid] = lca
            parent_count[lca] = parent_count.get(lca, 0) + 1

            listlike.add(lca)
            list_lca = lca

            for othernodes in dup_nodes:
                if intersect(othernodes, nodes):
                    # same list
                    for nodeid in nodes:
                        for othernodeid in othernodes:
                            lca = listinfo.get_lca(tree, [nodeid, othernodeid])
                            if lca != list_lca:
                                # likely item
                                itemlike.add(lca)
                                break

            dup_nodes.append(nodes)

    while True:
        killed = False
        for one in itemlike:
            for two in itemlike:
                if one != two and one in tree and two in tree:
                    lca = listinfo.get_lca(tree, [one, two])
                    if lca == one:
                        itemlike.remove(two)
                        killed = True
                        break
                    if lca == two:
                        itemlike.remove(one)
                        killed = True
                        break
            if killed:
                break
        if not killed:
            break

    return {'dupid': dup_ids, 'itemlike': itemlike, 'listlike': listlike}


def same_items(old, new):
    if len(old) != len(new):
        return False
    if list(sorted(old)) != list(sorted(new)):
        return False

    for itemid in old:
        olditem = old[itemid]
        newitem = new[itemid]

        if olditem['class'] != newitem['class'] or olditem['id'] != newitem['id']:
            return False
    return True


def load_tree(filename):
    filebase = os.path.splitext(filename)[0]
    if os.path.exists(filebase + ".tree"):
        with open(filebase + ".tree", 'rb') as treef:
            unpickler = pickle.Unpickler(treef)
            return unpickler.load()

    if '.xml' in filename:
        tree = analyze_xmlfile(filename)
    else:
        filebase = os.path.splitext(filename)[0]
        loaded = webdriver.load(filebase)
        descs = util.load_desc(filebase, 'desc')
        regs = util.load_desc(filebase, 'regs')
        items = loaded['items']
        fix_size(items, filename)
        tree = analyze_items(items, descs=descs, regs=regs)

    hidden.add_ocrinfo(tree, filebase + '.png')

    with open(filebase + ".tree", 'wb') as treef:
        pickler = pickle.Pickler(treef)
        pickler.dump(tree)

    return tree


def main():
    parser = argparse.ArgumentParser(description="Analyze")
    parser.add_argument('--debug', help='debug',
                        default=False, action='store_const', const=True)
    parser.add_argument('--error', help='only show errors',
                        default=False, action='store_const', const=True)
    parser.add_argument('--stat', help='show stat',
                        default=False, action='store_const', const=True)
    parser.add_argument('--ocr', help='show ocr',
                        default=False, action='store_const', const=True)
    parser.add_argument('file', help='file to analyze', nargs='+')
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    analyze(args.file, print_rets=not args.error, print_items=args.debug,
            print_error=True, show_ocr=args.ocr, show_stat=args.stat, use_ocr=True)


if __name__ == "__main__":
    main()
