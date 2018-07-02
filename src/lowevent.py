#!/usr/bin/env python3

import re
import logging
import functools

import monitor

logger = logging.getLogger("lowevent")

event_re = re.compile("/dev/input/([^:]+):\s+([^\s]+)\s+([^\s]+)\s+([^\s]+)")

"""
('event5', 'EV_KEY', 'BTN_TOUCH', 'DOWN')
('event5', 'EV_ABS', 'ABS_MT_PRESSURE', '00000001')
('event5', 'EV_ABS', 'ABS_MT_POSITION_X', '00000243')
('event5', 'EV_ABS', 'ABS_MT_POSITION_Y', '0000009d')
('event5', 'EV_SYN', 'SYN_MT_REPORT', '00000000')
('event5', 'EV_SYN', 'SYN_REPORT', '00000000')
('event5', 'EV_KEY', 'BTN_TOUCH', 'UP')
('event5', 'EV_SYN', 'SYN_MT_REPORT', '00000000')
('event5', 'EV_SYN', 'SYN_REPORT', '00000000')
"""

shift_map = {'0': ')', '1': '!', '2': '@', '3': '#', '4': '$', '5': '%',
             '6': '^', '7': '&', '8': '*', '9': '(', '/': '?', ',': '<',
             '.': '>', ';': ':', '\'': '"', '\\': '|', '`': '~', '[': '{',
             ']': '}'}

translate_key = {'DOT': '.', 'COMMA': ',', 'SLASH': '/', 'LEFTBRACE': '[',
                 'RIGHTBRACE': ']', 'BACKSLASH': '\\', 'SEMICOLON': ';',
                 'APOSTROPHE': '\'', 'GRAVE': '`'}

class LowEventState(object):
    def __init__(self):
        self.last_x = 0
        self.last_y = 0
        self.first_x = 0
        self.first_y = 0
        self.first = True
        self.rep_count = 0
        self.shift = False

def lowevent_cb(state, cb, info, line):
    if info == monitor.ProcInfo.exited:
        print("Terminated")
    elif info == monitor.ProcInfo.output:
        line = line.decode('utf-8')
        ret = event_re.match(line)
        if ret:
            (src, evt, subtype, arg) = ret.groups()
            cb(src, evt, subtype, arg, state)

def parse_lowevent(src, evt, subtype, arg, state):
    if subtype == "BTN_TOUCH":
        if arg == "DOWN":
#                    print("tap down")
            state.first = True
            state.rep_count = 0
        else:
            if state.rep_count == 1:
                return {'type': 'TAP', 'x': state.last_x, 'y': state.last_y}
            else:
                return {'type': 'SWIPE', 'x1': state.first_x, 'y1': state.first_y,
                        'x2': state.last_x, 'y2': state.last_y}
    elif subtype == "ABS_MT_POSITION_X":
        x = int(arg, 16)
        if state.first:
            state.first_x = x
        state.last_x = x
    elif subtype == "ABS_MT_POSITION_Y":
        y = int(arg, 16)
        if state.first:
            state.first_y = y
        state.last_y = y
    elif subtype == "SYN_REPORT":
        state.first = False
        state.rep_count += 1
#                print("at %d %d" % (state.last_x, state.last_y))
    elif evt == "EV_KEY":
        if subtype.startswith("KEY_"):
            key = subtype[4:]
            if arg == "UP":
                key = translate_key.get(key, key)
                if len(key) == 1:
                    if state.shift:
                        if key in shift_map:
                            key = shift_map[key]
                        else:
                            key = key.upper()
                    else:
                        key = key.lower()
                if not 'SHIFT' in key:
                    return {'type': 'KEY', 'key': key}
                if "SHIFT" in key:
                    state.shift = False
            elif arg == "DOWN":
                if "SHIFT" in key:
                    state.shift = True

    elif subtype == "REL_WHEEL":
        if arg == '00000001':
            direction = 'UP'
        elif arg == 'ffffffff':
            direction = 'DOWN'
        else:
            direction = arg
        return {'type': 'WHEEL', 'direction': direction}
    elif subtype == 'ABS_MT_PRESSURE':
        pass
    elif subtype == 'SYN_MT_REPORT':
        pass
    else:
        return {'type': 'UNKNOWN', 'src': src, 'evt': evt, 'subtype': subtype, 'arg': arg}
    return None

def print_lowevent(src, evt, subtype, arg, state):
    parsed = parse_lowevent(src, evt, subtype, arg, state)
    if parsed:
        type_ = parsed['type']
        if type_ == 'TAP':
            print("tap up %d,%d" % (parsed['x'], parsed['y']))
        elif type_ == 'SWIPE':
            print("swipe %d,%d -> %d,%d" % (parsed['x1'], parsed['y1'],
                                            parsed['x2'], parsed['y2']))
        elif type_ == 'KEY':
            print("key %s" % parsed['key'])
        else:
            print(parsed['src'], parsed['evt'], parsed['subtype'], parsed['arg'])

def monitor_lowevent(cb=print_lowevent, state=LowEventState()):
    return monitor.monitor_cmd(["adb", "shell", "getevent", "-l"],
                               functools.partial(lowevent_cb, state, cb))

if __name__ == "__main__":
    monitor_lowevent()
