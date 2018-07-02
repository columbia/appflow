#!/usr/bin/env python3

import config
import tags
import analyze
import util
import webdriver

import sys
import xml.etree.ElementTree as ET
import re
import os
import subprocess

bound_re = re.compile("\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


def item_valid(scr_name, item_desc):
    if item_desc in tags.tag['universal']:
        return True
    if scr_name in tags.tag:
        if item_desc in tags.tag[scr_name]:
            return True
        else:
            return False
    else:
        return True

def extract(node):
    attrib = node.attrib
    has_something = False
    important = False

    ret = '%20s' % attrib['class'].split('.')[-1] + ' ' + '%-10s' % attrib['text'][:10]
    if attrib['text']:
        has_something = True
    if attrib['content-desc']:
        ret += ' (' + attrib['content-desc'][:60] + ')'
        has_something = True
    if attrib['resource-id']:
        ret += ' #' + attrib['resource-id'].split('/')[-1]
        #has_something = True
    (x1, y1, x2, y2) = bound_re.match(attrib['bounds']).groups()
    x1 = int(x1)
    y1 = int(y1)
    x2 = int(x2)
    y2 = int(y2)
    width = x2 - x1
    height = y2 - y1
    ret += ' %dx%d @%dx%d' % (width, height, x1, y1)

    if attrib['clickable'] == 'true':
        ret += ' [C]'
        has_something = True

    if attrib['scrollable'] == 'true':
        ret += ' [S]'
        has_something = True

    if attrib['selected'] == 'true' or attrib['checked'] == 'true':
        ret += ' [+]'

#    if len(node) > 1:
#        ret += ' C: %d' % len(node)

    cls = attrib['class']
    if 'TextView' in cls or 'ImageView' in cls or 'EditView' in cls or 'Button' in cls or '[C]' in ret or '[S]' in ret or '[+]' in ret:
        if width != 0 and height != 0:
            important = True

    return (ret, width, height, len(node), has_something, important)

def fillstr(space, dilim, tot, step):
    ret = ''
    for i in range(tot):
        if (i+1) % step == 0:
            ret += dilim
        else:
            ret += space
    return ret

def parse(node, depth, start_id, parent, parent_width, parent_height, output_stack, parent_id, items, attrs):
    eat_data = ''
    output_me = False
    if node.tag != 'hierarchy':
        (ext, width, height, child_count, has_something, important) = extract(node)
#        if ext is not None:
        if width > 5 and height > 5 and (has_something or ((width < parent_width * 0.9 or height < parent_height * 0.9)) or (ext is not None and ('ImageView' in ext or 'TextView' in ext))):# or child_count > 1): # and (ext is None or 'CLICK' in ext):
            flag = '+'
            output_me = True
        else:
            flag = '-'
            eat_data += ext

        output = '%3d%s+ %s P:%d' % (start_id, fillstr(' ', '|', depth, 5), ext, parent_id)
        if flag == '+':
            items[start_id] = output
            output_stack.append(output)
            output_idx = len(output_stack) - 1
        else:
            items[start_id] = output
    else:
        width = parent_width
        height = parent_height
        important = False
        output = 'ROOT'

    my_id = start_id
    start_id += 1

    child_important_count = 0
    child_ids = []
    for child in node:
        child_ids.append(start_id)
        (start_id, child_eat, child_important) = parse(child, depth + 1, start_id, node, width, height, output_stack, my_id, items, attrs)
        if child_eat:
            eat_data += ' ' + child_eat
        if child_important:
            child_important_count += 1

    if child_important_count > 1:
        important = True
#        for child_id in child_ids:
#            attrs[child_id]['important'] = True

    attrs[my_id] = {}
    attrs[my_id]['output'] = output
    attrs[my_id]['important'] = important

#    important = important or child_important_count > 0

    if output_me:
        if eat_data.strip():
            output_stack[output_idx] += ' [' + ' '.join(eat_data.split())[:100] + ']'
        eat_data = ''

    return (start_id, eat_data, important)

def print_tags(scrname):
    print("universal: ", ' '.join(tags.tag['universal']))
    print("%9s: " % scrname, ' '.join(tags.tag[scrname]))

def observe(files):
    viewproc = None
    for filename in files:
        filebase = os.path.splitext(filename)[0]
        descname = filebase + '.desc.txt'
        imgname = filebase + '.png'
        if viewproc is not None:
            try:
                viewproc.kill()
            except:
                pass
        viewproc = subprocess.Popen([config.picviewer_path, imgname])

        scr_name = filename.split('/')[-1].split('.')[0].split('_')[-1]
        if scr_name.startswith('cat'):
            scr_name = 'cat'

        if '.xml' in filename:
            with open(filename) as f:
                src = f.read()

            root = ET.fromstring(src)
            output_stack = []
            items = {}
            attrs = {}
            parse(root, 0, 0, None, config.width, config.real_height, output_stack,
                  0, items, attrs)

            def get_depth(line):
                line = line[3:]
                return len(line) - len(line.lstrip())

            max_item_id = max(items)
            ext_items = {}
            for i in range(max_item_id + 1):
                if i in items:
                    my_depth = get_depth(items[i])
                    my_lines = [items[i]]
                    for j in range(i+1, max_item_id + 1):
                        if j in items:
                            his_depth = get_depth(items[j])
                            if his_depth > my_depth:
                                my_lines.append(items[j])
                            else:
                                break
                    ext_items[i] = my_lines

            for output in output_stack:
                print(output)

            print("==== IMPORTANT ====")
            for item_id in sorted(attrs):
                if attrs[item_id]['important']:
                    print(attrs[item_id]['output'])

        rets = {}
        if os.path.exists(descname):
            with open(descname) as inf:
                for line in inf.read().split('\n'):
                    if not line:
                        continue
                    (item_id, desc) = line.split(' ')
                    rets[int(item_id)] = desc

        if '.xml' in filename:
            tree = analyze.analyze([filename])[0]
        elif '.hier' in filename:
            loaded = webdriver.load(filebase)
            items = loaded['items']
            tree = analyze.analyze_items(items)

        print("=== ANALYZED ===")
        util.print_tree(tree)

        def removed_from_tree(itemid, tree):
            for nodeid in tree:
                if itemid in tree[nodeid]['raw']:
                    return False
            return True

        print("=== CURRENT ===")
        for itemid in sorted(rets):
            for nodeid in tree:
                if itemid in tree[nodeid]['raw']:
                    print("%3s %15s %s" % (itemid, rets[itemid],
                                           util.describe_node(tree[nodeid])))
            #print("%3s %15s %s" % (itemid, rets[itemid], items[itemid]))
            if removed_from_tree(itemid, tree):
                print("MISSING FROM TREE!", itemid)

        print_tags(scr_name)

        def save_results():
            with open(descname, 'w') as outf:
                for item_id in sorted(rets):
                    outf.write("%s %s\n" % (item_id, rets[item_id]))

        def find_node(itemid, tree):
            for nodeid in tree:
                if itemid in tree[nodeid]['raw']:
                    return tree[nodeid]
            return None

        history = []
        def mark_item(scr_name, item_id, item_desc, items):
            if not item_valid(scr_name, item_desc):
                print("warn: illegal item %s" % item_desc)
            rets[item_id] = item_desc
            print("Marked as <%s>   %s" % (item_desc, util.describe_node(find_node(item_id, tree), short=True).strip()))
            history.append([item_id, item_desc])
            save_results()

        def unmark_item(item_id):
            del rets[item_id]
            print("deleted item %d" % item_id)

            save_results()

        cur_item = -1
        while True:
            line = input("%s> " % filename)
            if line == '':
                break

            if line == '?':
                for item_id in sorted(rets):
                    print("%20s %-100s" % (rets[item_id], items[item_id]))
                continue

            if line == ';':
                util.print_tree(tree)
                #for line in output_stack:
                #    print(line)
                continue

            if line == '!':
                print_tags(scr_name)
                continue

            if line == 'q':
                sys.exit(0)

            mode = 'l'
            if ' ' in line:
                parts = line.split(' ')
                try:
                    cur_item = int(parts[0])
                    item_desc = parts[1]
                    item_idx = -1
                except:
                    mode = parts[0]
                    if mode == 'r':
                        rep = int(parts[1])
                        offset = int(parts[2])
                        if len(parts) > 3:
                            num = int(parts[3])
                        else:
                            num = 1
                    elif mode == 'd':
                        del_idx = int(parts[1])
            else:
                try:
                    item_idx = int(line)
                except:
                    item_desc = line
                    item_idx = -1

            if mode == 'r':
                cur_len = len(history)
                for j in range(num):
                    for i in range(rep):
                        old_entry = history[cur_len - rep + i]
                        mark_item(scr_name, old_entry[0] + offset + j * offset, old_entry[1], items)
            elif mode == 'd':
                unmark_item(del_idx)
            else:
                if item_idx == -1:
                    if cur_item != -1:
                        mark_item(scr_name, cur_item, item_desc, items)
                    else:
                        print("You must choose an item first")
                else:
                    if item_idx in items:
                        cur_item = item_idx
                        print("item %d is:" % item_idx)
                        for line in ext_items[item_idx]:
                            print(line)
                    else:
                        print("item does not exist")

    if viewproc is not None:
        viewproc.kill()

if __name__ == "__main__":
    tags.load("../etc/tags.txt")
    observe(sys.argv[1:])
