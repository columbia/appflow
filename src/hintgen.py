#!/usr/bin/env python3

import glob
import logging

import sense
import appdb
import tags
import analyze
import locator
import elements
import classify

logger = logging.getLogger("hintgen")

def find_element(element, clas, tree, screen, imgdata):
    best_score = None
    best_itemid = None
    for itemid in tree:
#            print('checking', itemid, guess_scr, element, util.describe_node(tree[itemid]))
        (guess_element, score) = clas.classify(screen, tree, itemid,
                                               imgdata)
        if guess_element == element:
            if best_score is None or score > best_score:
                best_score = score
                best_itemid = itemid

    return best_itemid

def gen_hints(app=None):
    if app is None:
        appdb.collect_apps("../apks/")
        apps = appdb.apps
    else:
        apps = [app]
    for app in apps:
        scr_clas = classify.getmodel("../model/", "../guis", app)
        for screen in tags.tag:
            elem_clas = elements.getmodel("../model/", "../guis/", app)
            locs = {}
            screenhint = 0
            fail_tag = set()
            elem_hint = set()
            for filename in glob.glob("../guis/%s*%s.xml" % (app, screen)):
                (items, descs) = analyze.load_case(filename)
                tree = analyze.analyze_items(items, descs)

                xmldata = open(filename).read()

                actfile = filename.replace('.xml', '.txt')
                actname = open(actfile).read()

                imgfile = filename.replace('.xml', '.png')
                imgdata = sense.load_image(imgfile)

                guess_scr = scr_clas.classify(xmldata, actname, imgfile)
                if guess_scr != screen:
                    screenhint += 1

                for itemid in items:
                    if itemid in descs:
                        loc = locator.get_locator(items, itemid)
                        tag = descs[itemid]
                        if loc is not None:
                            locs[tag] = locs.get(tag, []) + [loc]
                        else:
                            fail_tag.add(tag)

                for tag in tags.tag[screen]:
                    nodeid = find_element(tag, elem_clas, tree, screen, imgdata)
                    if nodeid is None:
                        if nodeid in descs.values():
                            elem_hint.add(tag)
                        continue
                    for itemid in items:
                        if itemid in descs and descs[itemid] == tag:
                            if not itemid in tree[nodeid]['raw']:
                                elem_hint.add(tag)

            for tag in locs:
                taglocs = set()
                for loc in locs[tag]:
                    taglocs.add("%s" % loc)

                while taglocs:
                    print("%s %s @%s %s" % (app, screen, tag, taglocs.pop()))

            for tag in fail_tag:
                if tag in elem_hint:
                    print("FAIL for %s %s %s" % (app, screen, tag))

            for tag in elem_hint:
                print("ELEMHINT for %s %s %s" % (app, screen, tag))

            if screenhint:
                print("SCREENHINT for %s %s" % (app, screen))

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--app', help="App name")
    args = parser.parse_args()

    gen_hints(args.app)
