#!/usr/bin/env python3

import sys
import subprocess
import skimage.io
import skimage.transform

import analyze
import util
import config
import elements
import tags

def in_subtree(ancestor, item, items):
    parent = items[item]['parent']
    while parent in items and parent != 0:
        if parent == ancestor:
            return True
        parent = items[parent]['parent']
    return False

def guess_buttons(items, descs, search=True):
    for itemid in items:
        item = items[itemid]
        if not 'class' in item:
            continue
        text = (item['desc'] + ' ' + item['text']).lower()
        id_ = item['id'].lower()

        if len(item['children']) == 1:
            child = items[item['children'][0]]
            text += (child['desc'] + ' ' + child['text']).lower()
            id_ += ' ' + child['id'].lower()

        if item['click']:
            if search:
                if 'search' in text or 'search' in id_:
                    descs[itemid] = 'search'
            if 'cart' in text or 'cart' in id_ or 'basket' in text or 'basket' in id_ or 'bag' in id_:
                descs[itemid] = 'cart'
            if 'navigate' in text or 'back' in id_:
                descs[itemid] = 'back'
            elif item['x'] < 10 and item['y'] < 70 and item['width'] < 200 and item['height'] < 200:
                descs[itemid] = 'menu'


def guess_list(listid, listtype, items, descs):
    descs[listid] = listtype + '_list'
    realid = listid
    while len(items[realid]['children']) < 3:
        realid = items[realid]['children'][0]

    for item in items:
        if items[item]['parent'] == realid:
            descs[item] = listtype + '_item'
        if in_subtree(listid, item, items):
            cls = items[item]['class']
            if 'Text' in cls:
                if listtype == 'cat':
                    descs[item] = 'cat_title'
                else:
                    if '$' in items[item]['text']:
                        descs[item] = 'item_price'
                    else:
                        descs[item] = 'item_title'
            if 'Image' in cls:
                if listtype == 'cat':
                    descs[item] = 'cat_image'
                else:
                    descs[item] = 'item_image'

def guess_search(items, descs):
    for item in items:
        if not 'class' in items[item]:
            continue
        if items[item]['class'] == 'EditText':
            descs[item] = 'search_input'
            break

def auto_guess(filename, items, descs):
    possible_list = []

    if "search." in filename:
        guess_search(items, descs)
        guess_buttons(items, descs, search=False)
        return

    for item in items:
        if not 'class' in items[item]:
            continue
        cls = items[item]['class']
        if 'ListView' in cls or 'RecyclerView' in cls:
            possible_list.append(item)

    if 'cat' in filename:
        listtype = 'cat'
    elif 'cart' in filename:
        listtype = 'cart'
    elif 'searchret' in filename:
        listtype = 'searchret'
    else:
        return

    if len(possible_list) == 1:
        guess_list(possible_list[0], listtype, items, descs)
    else:
        listid = input("Multiple list: %r" % possible_list)
        guess_list(int(listid), listtype, items, descs)

    guess_buttons(items, descs)

tag_db = {}

def guess(filename, lasttag=None):
    basename = filename.replace('.xml', '')
    (items, descs) = analyze.load_case(filename)
#    if descs:
#        return

    appname = basename.split('/')[-1].split('.')[0].split('_')[0]
    scrname = basename.split('/')[-1].split('.')[0].split('_')[-1]
    imgfile = filename.replace('.xml', '.png')

    if not appname in tag_db:
        tag_db[appname] = {}
    if appname in tag_db:
        for tag in tag_db[appname]:
            xid = tag_db[appname][tag]
            for itemid in items:
                if items[itemid]['id'] == xid:
                    descs[itemid] = tag

    print("%s Current:" % basename)
    util.printdesc(items, descs)
#    analyze.printitems(items)
    tree = analyze.analyze([filename])[0]
    util.print_tree(tree, descs)

    viewproc = subprocess.Popen([config.picviewer_path, basename + ".png"])

    prompt = ''
    while True:
        print(tags.tag['universal'])
        if scrname in tags.tag:
            print(tags.tag[scrname])
        line = input(prompt + "> ")
        parts = line.split(' ')
        cmd = parts[0]

        if cmd == '':
            util.save_desc(basename, descs)
            break
        elif cmd[0] == 'q':
            viewproc.kill()
            sys.exit(0)

        elif cmd[0] == 'l':
            listid = int(parts[1])
            listtype = parts[2]
            guess_list(listid, listtype, items, descs)
            util.printdesc(items, descs)

        elif cmd[0] == 'a':
            auto_guess(filename, items, descs)
            util.print_tree(tree, descs)

        elif cmd[0] == 'y':
            util.save_desc(basename, descs)
            break

        elif cmd[0] >= '0' and cmd[0] <= '9':
            if len(parts) > 1:
                lasttag = parts[1]
                util.mark_item(parts, items, descs, scrname, tag_db[appname])
                util.print_tree(tree, descs)
            else:
                if lasttag is None:
                    print(util.describe(items[int(cmd)]))
                else:
                    util.mark_item([cmd, lasttag], items, descs, scrname, tag_db[appname])
                    util.print_tree(tree, descs)
        elif cmd[0] == 'd':
            if cmd == 'dr':
                recursive = True
            else:
                recursive = False
            util.remove_mark(parts[1:], items, descs, recursive)
            util.print_tree(tree, descs)

        elif cmd[0] == ';':
            util.print_tree(tree, descs)
        elif cmd[0] == '!':
            util.printitems(items)
        elif cmd[0] == 'c':
            element_clas = elements.getmodel("../model/", "../guis/", None)
            imgdata = skimage.io.imread(imgfile, as_grey=True)
            imgdata = skimage.transform.resize(imgdata, (config.height, config.width))
            treeinfo = analyze.collect_treeinfo(tree)
            for itemid in tree:
                (guess_element, score) = element_clas.classify(scrname, tree,
                                                               itemid, imgdata, treeinfo)
                if guess_element != 'NONE':
                    descs[itemid] = guess_element
            util.print_tree(tree, descs)
        elif cmd[0] == '?':
            print(util.describe(items[int(parts[1])]))
        else:
            print("Unknown command")

    viewproc.kill()

if __name__ == "__main__":
    lasttag = None
    tags.load("../etc-news/tags.txt")
    for filename in sys.argv[1:]:
        guess(filename, lasttag)
