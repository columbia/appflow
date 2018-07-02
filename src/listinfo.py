#!/usr/bin/env python3

import analyze
import dump
import util
import widget
import device
import time

def dump_tree():
    dump.capture_layout("temp", ".", None)
    tree = analyze.analyze(["temp.xml"])[0]

    util.print_tree(tree)
    return tree

def is_container(node):
    clz = node['class']
    if 'Recycler' in clz or 'List' in clz or 'Grid' in clz:
        return True
    return False

def collect_text(tree, node):
    subtext = ''
    for childid in node['children']:
        childtext = collect_text(tree, tree[childid])
        if childtext:
            if subtext:
                subtext += '/' + childtext
            else:
                subtext = childtext
    mytext = node['text']
    if not mytext:
        if node['desc']:
            mytext = '(' + node['desc'] + ')'
        else:
            mytext = '.' + node['class']
    if mytext:
        return (mytext + '/' + subtext).strip()
    else:
        return subtext.strip()

def get_listinfo(tree, nodeid):
    node = tree[nodeid]
    list_items = []
    for childid in node['children']:
        child = tree[childid]
        list_item = {}
        list_item['text'] = collect_text(tree, child)
        list_item['click'] = child['click']

        list_items.append(list_item)

    print("Items of list %s %dx%d @%d-%d" % (util.describe_node(node), node['origw'], node['origh'], node['origx'], node['origy']))
    for item in list_items:
        print(item)
    return list_items

def get_lists(tree):
    listidx = 0
    lists = {}
    for nodeid in tree:
        if is_container(tree[nodeid]):
            listidx += 1
            lists[nodeid] = get_listinfo(tree, nodeid)

    return lists

def merge_lists(a, b):
    for i in range(len(a)):
        for j in range(len(b)):
            if a[i] == b[j]:
                return a[:i] + b[j:]
    return a + b

def get_ancs(tree, nodeid):
    anc = [nodeid]
    while True:
        par = tree[nodeid]['parent']
        anc.append(par)
        nodeid = par
        if par == 0 or par == -1:
            break
    anc.reverse()
    return anc

def get_lca(tree, nodes):
    ancs = []
    for nodeid in nodes:
        ancs.append(get_ancs(tree, nodeid))

    for i in range(len(ancs[0])):
        for anc in ancs:
            if i >= len(anc) or anc[i] != ancs[0][i]:
                return anc[i-1]

    return ancs[0][len(ancs[0]) - 1]

def count_ids(tree):
    id_count = {}
    for nodeid in tree:
        xid = tree[nodeid]['id']
        if xid:
            id_count[xid] = id_count.get(xid, 0) + 1
    return id_count

def find_same_ids(tree, xid):
    nodes = []
    for nodeid in tree:
        if tree[nodeid]['id'] == xid:
            nodes.append(nodeid)
    return nodes

if __name__ == "__main__":
    tree = dump_tree()
    #lists = get_lists(tree)
    lists = {}
    if len(lists) == 0:
        id_count = count_ids(tree)
        parent = {}
        parent_count = {}
        for xid in id_count:
            if id_count[xid] > 1:
                print(xid)
                nodes = find_same_ids(tree, xid)
                lca = get_lca(tree, nodes)
                parent[xid] = lca
                parent_count[lca] = parent_count.get(lca, 0) + 1
        print(parent)
        print(parent_count)
        for par in parent_count:
            lists[par] = get_listinfo(tree, par)

    if len(lists) > 1:
        target = int(input("choose list"))
    else:
        target = 0

    listid = sorted(lists)[target]
    mylist = lists[listid]

    listnode = tree[listid]
    bottom = listnode['origh'] + listnode['origy']
    if bottom == 1794:
        end = False
        while True:
            dev = device.Device()
            widget.swipe(dev, listnode, 'up')
            time.sleep(2)
            newtree = dump_tree()
            newlists = get_lists(newtree)
            for newlistid in newlists:
                if tree[newlistid]['id'] == listnode['id']:
                    newlist = merge_lists(mylist, newlists[newlistid])
                    if newlist == mylist:
                        end = True
                    mylist = newlist
                    break
            if end:
                break

            print("Merged")
            for item in mylist:
                print(item)

        print("Merged")
        for item in mylist:
            print(item)
