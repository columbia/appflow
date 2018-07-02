#!/usr/bin/env python3

import monitor
import config

import logging
import re
import os
import functools

logger = logging.getLogger('monitor')

line_re = re.compile("[0-9\-]+\s+[0-9:.]+\s+(.*)")
item_re = re.compile("([^:]+):\s+([^;]+)\s?;?\s?")
"""11-30 18:58:37.137 EventType: TYPE_WINDOW_CONTENT_CHANGED; EventTime: 426137; PackageName: com.jackthreads.android; MovementGranularity: 0; Action: 0 [ ClassName: android.view.ViewGroup; Text: []; ContentDescription: null; ItemCount: -1; CurrentItemIndex: -1; IsEnabled: true; IsPassword: false; IsChecked: false; IsFullScreen: false; Scrollable: false; BeforeText: null; FromIndex: -1; ToIndex: -1; ScrollX: -1; ScrollY: -1; MaxScrollX: -1; MaxScrollY: -1; AddedCount: -1; RemovedCount: -1; ParcelableData: null ]; recordCount: 0""" # noqa
"""android.view.accessibility.AccessibilityNodeInfo@801ef90a; boundsInParent: Rect(0, 0 - 1080, 1794); boundsInScreen: Rect(0, 0 - 1080, 1794); packageName: com.nordstrom.rack.app; className: android.view.ViewGroup; text: null; error: null; maxTextLength: -1; contentDescription: null; viewIdResName: null; checkable: false; checked: false; focusable: false; focused: false; selected:false; clickable: false; longClickable: false; contextClickable: false; enabled: true; password: false; scrollable: false; actions: [AccessibilityAction: ACTION_SELECT - null, AccessibilityAction: ACTION_CLEAR_SELECTION - null, AccessibilityAction: ACTION_ACCESSIBILITY_FOCUS - null, AccessibilityAction: ACTION_UNKNOWN - null]""" # noqa


def parse_part(part):
    ret = {}
    for item in item_re.findall(part.strip()):
        ret[item[0]] = item[1]
    return ret


def parse_line(line):
    ret = {}
    line = line.strip()
    for part in re.findall('([a-zA-Z]+):[^\[:]+\[(.*)\]', line):
        part_name = part[0]
        part_ret = parse_part(part[1])
        ret[part_name + "_EXT"] = part_ret
    line = re.sub('\[.*\]', '', line)
    for item in item_re.findall(line):
        ret[item[0]] = item[1]

    return ret


def parse_source(line):
    return parse_line(line)


def event_cb(cb, state, info, line):
    if info == monitor.ProcInfo.exited:
        logger.debug("Exited!")
        ret = {'status': 'exited'}
        cb(ret)
    elif info == monitor.ProcInfo.output:
        line = line.strip().decode('utf-8')
        logger.debug("got line %s" % line)
        if line.startswith("SOURCE:"):
            state['src'] = parse_source(line)
        else:
            data_part = line_re.findall(line)
            if data_part:
                ret = parse_line(data_part[0])
                if 'src' in state:
                    ret['src'] = state['src']
                    del state['src']
                ret['status'] = 'data'
                cb(ret)
            else:
                if line and line != 'dump' and line != 'cap' and line != 'see':
                    logger.warn("unknown ui line: %s" % line)


def parse_event(ret):
    if 'EventType' not in ret:
        return None
    if ret['EventType'] == 'TYPE_UIDUMPED':
        return {'type': 'UIDUMPED', 'loc': ret['Location']}
    elif ret['EventType'] == 'TYPE_DUMPFAILED':
        return {'type': 'DUMPFAILED', 'err': ret['Exception']}
    elif ret['EventType'] == 'TYPE_CAPTURED':
        return {'type': 'CAPTURED', 'loc': ret['Location']}
    elif ret['EventType'] == 'TYPE_CAPFAILED':
        return {'type': 'CAPFAILED', 'err': ret['Exception']}
    elif ret['EventType'] == 'TYPE_SAW':
        return {'type': 'SAW', 'loc_xml': ret['LocationXml'],
                'loc_png': ret['LocationPng']}
    elif ret['EventType'] == 'TYPE_SEEFAILED':
        return {'type': 'SEEFAILED', 'err': ret['Exception']}
    evt = {}
    if 'PackageName' in ret:
        pack = ret['PackageName']
        evt['pack'] = pack
    if 'Action_EXT' in ret:
        desc = ret['Action_EXT'].get('ContentDescription', None)
        clazz = ret['Action_EXT'].get('ClassName', None)
        text = ret['Action_EXT'].get('Text', None)
        curitem = ret['Action_EXT'].get('CurrentItemIndex', None)
        itemcount = ret['Action_EXT'].get('ItemCount', None)
        evt['desc'] = desc
        evt['class'] = clazz
        evt['text'] = text
        evt['curitem'] = curitem
        evt['itemcount'] = itemcount
    if 'src' in ret:
        evt['src'] = ret['src']

    type_ = None
    if ret['EventType'] == 'TYPE_VIEW_CLICKED':
        type_ = 'CLICK'
    elif ret['EventType'] == 'TYPE_VIEW_TEXT_CHANGED':
        type_ = 'TEXT'
    elif ret['EventType'] == 'TYPE_VIEW_FOCUSED':
        type_ = 'FOCUS'
    elif ret['EventType'] == 'TYPE_WINDOW_STATE_CHANGED':
        if 'inputmethod' in pack:
            type_ = 'INPUT_CHANGE'
        else:
            type_ = 'STATE_CHANGE'
    elif ret['EventType'] == 'TYPE_WINDOW_CONTENT_CHANGED':
        type_ = 'CONTENT_CHANGE'
    elif ret['EventType'] == 'TYPE_VIEW_TEXT_SELECTION_CHANGED':
        pass
    elif ret['EventType'] == 'TYPE_VIEW_ACCESSIBILITY_FOCUSED':
        type_ = 'AFOCUS'
    elif ret['EventType'] == 'TYPE_VIEW_ACCESSIBILITY_FOCUS_CLEARED':
        pass
    elif ret['EventType'] == 'TYPE_VIEW_SCROLLED':
        type_ = 'SCROLL'
    elif ret['EventType'] == 'TYPE_VIEW_SELECTED':
        type_ = 'SELECT'
    elif ret['EventType'] == 'TYPE_ANNOUNCEMENT':
        type_ = 'ANNOUNCE'
    elif ret['EventType'].startswith('TYPE_VIEW_HOVER'):
        type_ = None
    elif ret['EventType'] == 'TYPE_NOTIFICATION_STATE_CHANGED':
        type_ = 'NOTIFICATION'
    else:
        type_ = 'UNKNOWN'

    if type_:
        evt['type'] = type_
        evt['orig'] = ret
        return evt
    else:
        return None


def print_event(ret):
    parsed = parse_event(ret)
    full = ''
    if parsed is None:
        return
    if 'class' not in parsed:
        print("%s" % parsed['type'])
        return
    full = "%s %s (%s) %s / %s" % (parsed['class'], parsed['text'], parsed['desc'],
                                   parsed['curitem'], parsed['itemcount'])
    if parsed['type'] == 'UNKNOWN':
        for item in sorted(ret):
            if isinstance(ret[item], dict):
                for subitem in sorted(ret[item]):
                    print("%30s => %s" % (subitem, ret[item][subitem]))
            else:
                print("%20s => %60s" % (item, ret[item]))
    else:
        print("%s %s %s" % (parsed['type'], full, parsed['pack']))


class UIMonitor(object):
    pass


def monitor_uievent(cb=print_event, state={}, dev=None):
    cmd = [config.adb_path]
    if dev is not None and dev.serial is not None:
        cmd += ["-s", dev.serial]
    cmd += ["shell", "CLASSPATH=/sdcard/uiauto.jar", "app_process", "/sdcard",
            "com.android.commands.uiautomator.Launcher", "monitor"]
    mon = monitor.monitor_cmd(cmd, functools.partial(event_cb, cb, state))
    return mon


def print_uievents(serial):
    #    mon = monitor.monitor_cmd(["adb", "shell", "uiautomator", "events"],
    #                              functools.partial(event_output_cb, cb))
    import device
    dev = device.Device(serial, no_uimon=True)
    mon = monitor_uievent(print_event, dev=dev)
    while True:
        cmd = input(">")
        if cmd == 'q':
            mon.kill()
            os._exit(0)
        else:
            mon.input(cmd)


if __name__ == "__main__":
    import sys
    print_uievents(sys.argv[1])
