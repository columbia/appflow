#!/usr/bin/env python3

import random
import logging

import device
import sense
import analyze
import util
import classify
import elements
import widget

logger = logging.getLogger("explorer")

def explore():
    print("learning")
    clas = classify.learn("../guis/", None)
    element_clas = elements.learn("../guis/", None)

    print("exploring")
    dev = device.Device()
    while True:
        hier = sense.grab_full(dev)
        if not hier['xml']:
            logger.error("fail to grab hierarchy")
            return

        print(hier['act'])
        guess_scr = clas.classify(hier['xml'], hier['act'], hier['scr'])
        print("classify: %s" % (guess_scr))

        items = analyze.parse_xml(hier['xml'])
        tree = analyze.analyze_items(items)

        imgdata = sense.load_image(hier['scr'])

        guess_descs = {}
        treeinfo = analyze.collect_treeinfo(tree)
        for itemid in tree:
            guess_element = element_clas.classify(guess_scr, tree, itemid, imgdata,
                                                  treeinfo)
            if guess_element != 'NONE':
                guess_descs[itemid] = guess_element

        util.print_tree(tree, guess_descs)

        input('enter')

        if False:
            itemid = random.choice(sorted(tree))
            if 'click' in tree[itemid] and tree[itemid]['click']:
                print("Clicking %s" % util.describe_node(tree[itemid]))
                widget.click(dev, tree[itemid])

if __name__ == "__main__":
    explore()
