#!/usr/bin/env python3

import queue
import tempfile
import os
import re
import logging
import sys
import json

import uievent
import lowevent
import device
import analyze
import util

bound_re = re.compile('Rect\((-?\d+),\s+(-?\d+)\s+-\s+(-?\d+),\s+(-?\d+)\)')

logger = logging.getLogger("recorder")

TAP_LIMIT = 5

def match(std, inp):
    if std == 'null':
        return 0.5

    ret = 0
    sstd = re.findall('\w', std.lower())
    if len(sstd) == 0:
        return 0.5

    sinp = re.findall('\w', inp.lower())
    for x in sstd:
        for y in sinp:
            if x == y:
                ret += 1
                break
    return 1.0 * ret / len(sstd)

def find_source(detail, items, tree):
    if not 'src' in detail:
        return (None, None)
    if 'contentDescription' in detail['src']:
        desc = detail['src']['contentDescription']
    else:
        desc = ''
    text = detail['src']['text']
    clz = detail['src']['className'].split('.')[-1]
    pos = detail['src']['boundsInScreen']

    if not bound_re.match(pos):
        logger.error(pos)
    (x1, y1, x2, y2) = bound_re.match(pos).groups()
    x1 = int(x1)
    y1 = int(y1)
    x2 = int(x2)
    y2 = int(y2)

    targets = {}
    for itemid in items:
        item = items[itemid]
        if (x1 == item['x'] and y1 == item['y'] and
            x2 == item['x'] + item['width'] and y2 == item['y'] + item['height']):

            score = (match(clz, item['class']) + match(desc, item['desc']) +
                        match(text, item['text']))

            targets[score] = itemid

    if len(targets) == 0:
        targets = {}
        for itemid in items:
            item = items[itemid]
            score = 0
            if item['class'] == clz:
                score += 1
            if item['x'] == x1:
                score += 1
            if item['y'] == y1:
                score += 1
            if item['x'] + item['width'] == x2:
                score += 1
            if item['y'] + item['height'] == y2:
                score += 1

            if score > 3:
                targets[score] = itemid

        if len(targets) == 0:
            matchcnt = 0
            for itemid in items:
                if items[itemid]['class'] == clz:
                    logger.info(items[itemid])
                    matchcnt += 1
            if matchcnt == 0:
                for itemid in items:
                    logger.info(items[itemid])

            logger.info("source missing %s %s" % (pos, clz))
            return (None, None)

    source = targets[max(targets)]
    src_nodeid = None
    for itemid in tree:
        if source in tree[itemid]['raw']:
            src_nodeid = itemid

    if src_nodeid is None:
        logger.error("tree node missing!")
    return (source, src_nodeid)

def find_source_weak(x, y, current_items, current_tree):
    targets = []
    for itemid in current_items:
        item = current_items[itemid]
        if (x >= item['x'] and x <= item['x'] + item['width'] and
            y >= item['y'] and y <= item['y'] + item['height'] and
            item['click']):

            targets.append(itemid)

    if len(targets) > 1:
        logger.warn("Multiple targets")
        for itemid in targets:
            logger.warn(current_items[itemid])
    if len(targets) != 0:
        source = targets[-1] # TODO
        src_nodeid = None
        for itemid in current_tree:
            if source in current_tree[itemid]['raw']:
                src_nodeid = itemid
        if src_nodeid is None:
            logger.error("tree node missing!")
            logger.error(current_items[source])
        return (source, src_nodeid)
    return (None, None)

def find_source_fallback(x, y, detail, current_items, current_tree):
    desc = detail['desc']
    text = detail['text']
    clz = detail['class'].split('.')[-1]

    targets = {}
    for itemid in current_items:
        item = current_items[itemid]
        if (x >= item['x'] and x <= item['x'] + item['width'] and
            y >= item['y'] and y <= item['y'] + item['height'] and
            item['click']):

            score = (match(clz, item['class']) + match(desc, item['desc']) +
                        match(text, item['text']))

            targets[score] = itemid

    if len(targets) != 0:
        source = targets[max(targets)]
        for itemid in current_tree:
            if source in current_tree[itemid]['raw']:
                src_nodeid = itemid
        return (source, src_nodeid)
    return (None, None)

def find_source_full(x, y, detail, current_items, current_tree):
    source = None
    src_nodeid = None
    if 'src' in detail:
        (source, src_nodeid) = find_source(detail, current_items, current_tree)
    if source is None:
        (source, src_nodeid) = find_source_fallback(x, y, detail, current_items,
                                                    current_tree)
    return (source, src_nodeid)

class Recorder(object):
    def __init__(self, save=False, save_path="save"):
        self.save = save
        self.save_path = save_path
        self.cap_count = 0
        self.action_file = None
        self.evtcache = []

    def handle_tap(self, x, y):
        self.last_tap_x = x
        self.last_tap_y = y
        if (y > 1794 and x <= 430):
            self.record_action('BACK')
        else:
            (source, src_nodeid) = find_source_weak(x, y,
                self.current_items, self.current_tree)
            if src_nodeid is not None:
                self.evtcache.append({'type': 'TAP', 'detail': {
                    'target': self.current_tree[src_nodeid],
                    'x': x, 'y': y}})

    def flush_cache(self):
        if self.evtcache:
            cache = self.evtcache
            self.evtcache = []
            for evt in cache:
                self.record_action(evt['type'], evt['detail'])

    def purge_cache(self, evttype):
        for i in range(len(self.evtcache) - 1, -1, -1):
            if self.evtcache[i]['type'] == evttype:
                self.evtcache = self.evtcache[:i] + self.evtcache[(i+1):]
                break

    def record_action(self, type_, args={}):
        self.flush_cache()
        ret = "ACTION: %s" % type_
        for item in sorted(args):
            if item == 'target':
                ret += ' target: %s' % util.describe_node(args[item])
            else:
                ret += ' %s: %r' % (item, args[item])
        print(ret)
        if self.save:
            args['action'] = type_
            saction = json.dumps(args)
            self.action_file.write(saction)
            self.action_file.write('\n')
            self.action_file.flush()

    def record(self):
        evtqueue = queue.Queue()

        def record_lowevent(src, evt, subtype, arg, state):
            parsed_evt = lowevent.parse_lowevent(src, evt, subtype, arg, state)
            if parsed_evt:
                item = {'type': 'low', 'evt': parsed_evt}
                evtqueue.put(item)
                logger.warn("LOW %15s", parsed_evt['type'])

        def record_uievent(evt):
            parsed_evt = uievent.parse_event(evt)
            if parsed_evt:
                item = {'type': 'ui', 'evt': parsed_evt}
                evtqueue.put(item)
                logger.warn("UI  %15s", parsed_evt['type'])

        low_mon = lowevent.monitor_lowevent(record_lowevent)
        ui_mon = uievent.monitor_uievent(record_uievent)
        ui_mon.input('see')

        need_dump = False
        dumping = True
        dev = device.Device()
        current_hier_xml = None
        current_capture = None

        self.last_tap_x = 0
        self.last_tap_y = 0
        last_swipe_x1 = 0
        last_swipe_x2 = 0
        last_swipe_y1 = 0
        last_swipe_y2 = 0
        last_scroll_source = None
        last_scroll_src_nodeid = None

        self.current_items = {}
        self.current_tree = {}

        last_evt = None

        low_input_str = ''
        if self.save:
            self.action_file = open(os.path.join(self.save_path, "actions.json"), 'w')

        while True:
            evt = evtqueue.get()
            type_ = evt['type']
            detail = evt['evt']
            subtype = detail['type']
            evtdesc = ''

            if subtype == '':
                for item in detail:
                    logger.debug("%s = %s" % (item, detail[item]))

            if type_ == 'ui':
                if subtype == 'CONTENT_CHANGE' or subtype == 'STATE_CHANGE':
                    evtdesc = "%r %r" % (dumping, need_dump)
                    # content change, update ui info
                    if dumping:
                        need_dump = True
                    else:
                        dumping = True
                        ui_mon.input('see')
                elif subtype == 'SAW':
                    evtdesc = "%r %r" % (dumping, need_dump)
                    if need_dump:
                        need_dump = False
                        ui_mon.input('see')
                    else:
                        dumping = False
                        tempf = tempfile.mktemp(suffix=".xml")
                        dev.grab_file(detail['loc_xml'], tempf)
                        new_hier_xml = open(tempf).read()
                        os.remove(tempf)

                        new_capture = None
                        if detail['loc_png'] != 'NONE':
                            tempf = tempfile.mktemp(suffix=".png")
                            dev.grab_file(detail['loc_png'], tempf)
                            new_capture = open(tempf, 'rb').read()
                            os.remove(tempf)

                        if current_hier_xml != new_hier_xml:
                            self.current_items = analyze.parse_xml(new_hier_xml)
                            self.current_tree = analyze.analyze_items(self.current_items)
                            focused_nodeid = -1
                            for itemid in self.current_tree:
                                item = self.current_tree[itemid]
                                if 'focused' in item and item['focused']:
                                    focused_nodeid = itemid
                                    break

                        if self.save and (current_hier_xml != new_hier_xml or
                                          current_capture != new_capture):
                            self.cap_count += 1
                            with open(os.path.join(self.save_path,
                                                   "hier%d.xml" % self.cap_count),
                                      'w') as outf:
                                outf.write(new_hier_xml)
                            if new_capture is not None:
                                with open(os.path.join(self.save_path,
                                                    "cap%d.png" % self.cap_count),
                                        'wb') as outf:
                                    outf.write(new_capture)

                        current_hier_xml = new_hier_xml
                        current_capture = new_capture

                elif subtype == 'SEEFAILED':
                    # just retry?
                    evtdesc = detail['err']
                    if not 'NullRoot' in detail['err']:
                        # NullRoot seems to be persistent
                        ui_mon.input('see')
                    else:
                        self.current_items = {}
                        self.current_tree = {}
                        last_scroll_src_nodeid = None
                        last_scroll_source = None
                        dumping = False
                        ui_mon.restart()
                        ui_mon.input('see')

            if subtype == "UNKNOWN":
                for item in detail:
                    print("%s = %s" % (item, detail[item]))
            if type_ == 'low' and subtype == 'TAP':
                x = evt['evt']['x']
                y = evt['evt']['y']
                self.handle_tap(x, y)

            if type_ == 'low' and subtype == 'SWIPE':
                x1 = detail['x1']
                y1 = detail['y1']
                x2 = detail['x2']
                y2 = detail['y2']
                if (abs(x1 - x2) < TAP_LIMIT and abs(y1 - y2) < TAP_LIMIT):
                    self.handle_tap(x1, y1)
                    evtdesc = "-> TAP %d %d" % (self.last_tap_x, self.last_tap_y)
                else:
                    last_swipe_x1 = x1
                    last_swipe_y1 = y1
                    last_swipe_x2 = x2
                    last_swipe_y2 = y2

                    if last_scroll_src_nodeid is not None:
                        self.record_action("SWIPE", {'target': self.current_tree[last_scroll_src_nodeid],
                                                'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2})

                        node = self.current_tree[last_scroll_src_nodeid]
                        x1r = 1.0 * (x1 - node['origx']) / node['origw']
                        y1r = 1.0 * (y1 - node['origy']) / node['origh']
                        x2r = 1.0 * (x2 - node['origx']) / node['origw']
                        y2r = 1.0 * (y2 - node['origy']) / node['origh']
                        evtdesc = "%.2f %.2f -> %.2f %.2f" % (x1r, y1r, x2r, y2r)
                    else:
                        logger.warn("swipe: src missing")

            if type_ == 'ui' and subtype == 'CLICK':
                (source, src_nodeid) = find_source_full(self.last_tap_x, self.last_tap_y,
                    detail, self.current_items, self.current_tree)

                if src_nodeid is not None:
                    self.purge_cache('TAP')
                    self.record_action("TAP", {'target': self.current_tree[src_nodeid],
                                        'x': self.last_tap_x, 'y': self.last_tap_y})
                    node = self.current_tree[src_nodeid]
                    xr = 1.0 * (self.last_tap_x - node['origx']) / node['origw']
                    yr = 1.0 * (self.last_tap_y - node['origy']) / node['origh']
                    evtdesc = "%.2f %.2f" % (xr, yr)
                else:
                    logger.warn("fail to find scroll source")
                    logger.warn(detail)

            if type_ == 'ui' and subtype == 'TEXT':
                # text = [foobar]
                text = detail['text'][1:-1]
                evtdesc = text
                if focused_nodeid != -1:
                    node = self.current_tree[focused_nodeid]
                    self.record_action("TEXT", {'target': node, 'text': text})

            if type_ == 'low' and subtype == 'KEY':
                key = detail['key']
                if key == 'ESC':
                    self.record_action('BACK')
                if key == 'ENTER':
                    self.record_action('ENTER')
                low_input_str += detail['key']
                evtdesc = detail['key']

            if type_ == 'ui' and subtype == 'SCROLL':
                (last_scroll_source, last_scroll_src_nodeid) = find_source(
                    detail, self.current_items, self.current_tree)
                if last_scroll_src_nodeid is None:
                    logger.warn("fail to find scroll source")
                    logger.warn(detail)

            if last_evt is None or not (last_evt['evt']['type'] == 'CONTENT_CHANGE' and
                                        subtype == 'CONTENT_CHANGE'):
                #print("[%s] %s %r" % (type_, subtype, detail))
                logger.debug("[%s] %s %s" % (type_, subtype, evtdesc))

            last_evt = evt

if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            os.makedirs(sys.argv[1])
        except:
            pass
        Recorder(True, sys.argv[1]).record()
    else:
        Recorder().record()
