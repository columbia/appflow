#!/usr/bin/env python3

import logging
import re

import action
import concept
import locator
import value
import config
import perfmon
import time
import microtest
import appdb

logger = logging.getLogger("operation")

op_actions = {
    ### APP
    "start": lambda name, attr, widget, env: [action.Action(name, attr)],
    "stop": lambda name, attr, widget, env: [action.Action(name, attr)],
    "clear": lambda name, attr, widget, env: [action.Action(name, attr)],
    "waitact": lambda name, attr, widget, env: [action.Action(name, attr)],
    "type": lambda name, attr, widget, env: [
        action.Action('text', {'str': attr['text'].get(env)})],
    "back": lambda name, attr, widget, env: [action.Action(name, attr)],
    "enter": lambda name, attr, widget, env: [action.Action(name, attr)],
    "home": lambda name, attr, widget, env: [action.Action(name, attr)],
    "waitfor": lambda name, attr, widget, env: [action.Action(name, attr)],
    "wait": lambda name, attr, widget, env: [action.Action(name, attr)],
    "waitready": lambda name, attr, widget, env: [action.Action(name, attr)],
    "waitidle": lambda name, attr, widget, env: [action.Action(name, attr)],
    "clearfocused": lambda name, attr, widget, env: [action.Action(name, attr)],
    "kbdaction": lambda name, attr, widget, env: [action.Action(name, attr)],
    "kbdon": lambda name, attr, widget, env: [action.Action(name, attr)],
    "kbdoff": lambda name, attr, widget, env: [action.Action(name, attr)],
    "closekbd": lambda name, attr, widget, env: [action.Action(name, attr)],
}

READONLY_OPS = set(['waitact', 'waitfor', 'wait', 'waitready', 'see', 'seetext', 'seein',
                    'increasing', 'decreasing'])


class Operation(object):
    """
    name: str = type of op
    target: Concept = op target
    attr: map<str, object> = args
    """

    def __init__(self, name, target=None, attr=None):
        if attr is None:
            attr = {}
        self.name = name
        self.target = target
        self.attr = attr

    def to_actions(self, widgets, env):
        if widgets != []:
            widget = widgets[0]
        else:
            widget = None
        if self.name in op_actions:
            return op_actions[self.name](self.name, self.attr, widget, env)
        ### INTERACTIVE
        elif self.name == 'click':
            # click in the middle
            (x, y) = widget.center()
            return [action.Action('tap', {'x': x, 'y': y})]
        elif self.name == 'longclick':
            # click in the middle
            (x, y) = widget.center()
            return [action.Action('longclick', {'x': x, 'y': y})]
        elif self.name == 'text':
            if widget.clazz() == 'Spinner':
                # You cannot type into a spinner
                return None
            (x, y) = widget.center()
            return [
                # click
                action.Action('tap', {'x': x, 'y': y}),
                # clear
                action.Action('clearfocused'),
                # type
                action.Action('text', {'str': self.attr['text'].get(env)}),
                # hide kbd
                action.Action('closekbd')
            ]
        elif self.name == 'select':
            return [action.Action('select', {
                'target': widget, 'value': self.attr['option'].get(env)})]
        elif self.name == 'scroll':
            return [action.Action('scroll', {'direction': self.attr['direction']})]
        elif self.name == 'scrollit':
            return [action.Action('scrollit', {
                'widget': widget, 'direction': self.attr['direction'].get(env)})]
        ### WAIT and CHECK
        elif self.name == 'see':
            # when widget is resolved, it should be ok
            return []
        elif self.name == 'seetext':
            return [action.Action('seetext', {'str': self.attr['text'].get(env)})]
        elif self.name == 'seein':
            return [action.Action('seein', {'widget': widget,
                                            'str': self.attr['text'].get(env)})]
        elif self.name == 'increasing' or self.name == 'decreasing':
            return [action.Action(self.name, {'widgets': widgets})]
        else:
            logger.warn("unknown action %s %r on %s", self.name, self.attr, self.target)
            return None

    def do(self, dev, observer, state, env, tlib):
        logger.info("doing %s", self)
        perfmon.record_start("op", self)

        if self.name == 'call':
            realargs = []
            for arg in self.attr['args']:
                realargs.append(arg.get(env))

            return tlib.call(self.attr['func'], realargs, dev, observer, state)
        elif self.name == 'not':
            return not self.attr['op'].do(dev, observer, state, env, tlib)
        elif self.name == 'restart':
            appname = appdb.get_app(tlib.app)
            return microtest.restart_test(appname).attempt(
                dev, observer, state, tlib, env)

        widgets = []
        if self.target is not None:
            logger.info("finding target %s", self.target)
            perfmon.record_start("find", "%s" % self.target)
            state = observer.grab_state(dev)
            init_scr = state.get('screen')
            last_state = state
            for scroll_count in range(config.NOTFOUND_SCROLLDOWN_LIMIT):
                widgets = self.target.locate(state, observer, env)
                if widgets != []:
                    break

                if self.target.no_scroll():
                    logger.info("not found, scroll forbidden, fail")
                    perfmon.record_stop("find", "%s" % self.target)
                    return False

                logger.info("%s not found, scroll down", self.target)
                scroll_act = action.Action("scroll", {'direction': 'down'})
                if not scroll_act.do(dev, observer, env):
                    logger.info("nothing to scroll, fail")
                    perfmon.record_stop("find", "%s" % self.target)
                    return False
                state = observer.grab_state(dev, known_scr=init_scr)
                if state.same_as(last_state):
                    logger.info("scrolled to the bottom")
                    break

                # TODO: hack!
                tlib.handle_sys_screen(state, dev, observer)

            if widgets == []:
                for scroll_count in range(config.NOTFOUND_SCROLLUP_LIMIT):
                    widgets = self.target.locate(state, observer, env)
                    if widgets != []:
                        break

                    logger.info("%s not found, scroll up", self.target)
                    scroll_act = action.Action("scroll", {'direction': 'up'})
                    if not scroll_act.do(dev, observer, env):
                        logger.info("nothing to scroll, fail")
                        perfmon.record_stop("find", "%s" % self.target)
                        return False
                    state = observer.grab_state(dev, known_scr=init_scr)
                    if state.same_as(last_state):
                        logger.info("scrolled to the top")
                        break

                    # TODO: hack!
                    tlib.handle_sys_screen(state, dev, observer)

            if widgets == []:
                logger.warn("fail to find %s", self.target)
                return False

            perfmon.record_stop("find", "%s" % self.target)
            logger.info("found %s", widgets[0])

        actions = self.to_actions(widgets, env)
        if actions is None:
            return False
        for act in actions:
            ret = act.do(dev, observer, env)
            if not ret:
                return False
            # TODO: maybe wait for idle?
            time.sleep(0.1)

        usedtime = perfmon.record_stop("op", self)
        logger.info("%s finished %.3fs", self, usedtime)

        return True

    def doable(self, state):
        if self.target is not None:
            if not self.target.present(state):
                return False
        return True

    def read_only(self):
        if self.name == 'not':
            return self.attr['op'].read_only()
        return self.name in READONLY_OPS

    def collect_vars(self):
        var = set()
        for key in self.attr:
            if value.is_parameter(self.attr[key]):
                var.add(self.attr[key].name)
        if self.name == "call":
            for arg in self.attr['args']:
                if value.is_parameter(arg):
                    var.add(arg.name)
            # TODO: vars used by function
        elif self.name == "not":
            return self.attr['op'].collect_vars()

        return var

    def __hash__(self):
        return hash(self.name) + hash(self.target)

    def __eq__(self, other):
        return (self.name == other.name and self.target == other.target and
                self.attr == other.attr)

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        ret = "%s (%s" % (self.name.upper(),
                          self.target if self.target is not None else "")
        for key in self.attr:
            ret += " %s:%s," % (key, self.attr[key])
        ret += ")"
        return ret


enter_re = re.compile("enter")
back_re = re.compile("back")
home_re = re.compile("home")
click_re = re.compile("click (.+)")
longclick_re = re.compile("longclick (.+)")
wait_re = re.compile("wait (.+)")
waitfor_re = re.compile("waitfor (.+):(.+)")
waitready_re = re.compile("waitready")
waitidle_re = re.compile("waitidle")
text_re = re.compile("text (.+) '([^']*)'")
type_re = re.compile("type '([^']+)'")
select_re = re.compile("select (.+) '([^']+)'")
scroll_re = re.compile("scroll (.*)")
scrollit_re = re.compile("scrollit (.+) ([^ ]+)")
see_re = re.compile("see (.+)")
seein_re = re.compile("seein (.+) '(.+)'")
seetext_re = re.compile("seetext '(.+)'")
increasing_re = re.compile("increasing (.+)")
decreasing_re = re.compile("decreasing (.+)")
call_re = re.compile("call ([^ ]+)(.+)")
rev_re = re.compile("not (.*)")
start_re = re.compile("start (.*)")
stop_re = re.compile("stop (.*)")
clearfocused_re = re.compile("clearfocused")
kbdaction_re = re.compile("kbdaction")
kbdon_re = re.compile("kbdon")
kbdoff_re = re.compile("kbdoff")
closekbd_re = re.compile("closekbd")
restart_re = re.compile("restart")

ops = {
    enter_re: lambda: Operation("enter"),
    back_re: lambda: Operation("back"),
    home_re: lambda: Operation("home"),
    waitidle_re: lambda: Operation("waitidle"),
    click_re: lambda target: Operation("click", concept.parse(target)),
    longclick_re: lambda target: Operation("longclick", concept.parse(target)),
    wait_re: lambda timeout: Operation("wait", attr={'time': float(timeout) * 1000}),
    waitfor_re: lambda method, val: Operation("waitfor",
                                              attr={'method': value.parse_value(method),
                                                    'value': value.parse_value(val)}),
    waitready_re: lambda method, val: Operation("waitready"),

    text_re: lambda target, text: Operation("text", concept.parse(target),
                                            {'text': value.parse_value(text)}),
    type_re: lambda text: Operation("type", attr={'text': value.parse_value(text)}),
    select_re: lambda target, option: Operation("select", concept.parse(target),
                                                {'option': value.parse_value(option)}),
    scroll_re: lambda direction: Operation("scroll", None, {'direction': direction}),
    scrollit_re: lambda target, direction: Operation(
        "scrollit", concept.parse(target), {'direction': value.parse_value(direction)}),
    see_re: lambda target: Operation("see", concept.parse(target)),
    seein_re: lambda target, text: Operation("seein", concept.parse(target),
                                             attr={'text': value.parse_value(text)}),
    increasing_re: lambda target: Operation("increasing", concept.parse(target)),
    decreasing_re: lambda target: Operation("decreasing", concept.parse(target)),
    seetext_re: lambda text: Operation("seetext", attr={'text': value.parse_value(text)}),
    call_re: lambda funcname, args: Operation("call",
                                              attr={'func': funcname,
                                                    'args': parse_call_args(args)}),
    rev_re: lambda real_op: Operation("not", attr={'op': parse_line(real_op)}),
    start_re: lambda appname: Operation("start", None, {'name': appname}),
    stop_re: lambda appname: Operation("stop", None, {'name': appname}),
    clearfocused_re: lambda: Operation("clearfocused"),
    kbdaction_re: lambda: Operation("kbdaction"),
    kbdon_re: lambda: Operation("kbdon"),
    kbdoff_re: lambda: Operation("kbdoff"),
    closekbd_re: lambda: Operation("closekbd"),
    restart_re: lambda: Operation("restart"),
}


def parse_line(line):
    for match_re in ops:
        ret = match_re.match(line)
        if ret:
            return ops[match_re](*ret.groups())

    return None


str_re = re.compile("'([^']+)',?")
other_re = re.compile("([^,]+),?")


def parse_call_args(args):
    ret = []
    while True:
        args = args.strip()
        if not args:
            break
        if args[0] == "'":
            match = str_re.match(args)
            str_arg = match.group(1)
            val = value.parse_value(str_arg)
        else:
            match = other_re.match(args)
            other_arg = match.group(1)
            val = concept.parse(other_arg)
        args = args[match.span()[1]:]
        ret.append(val)
    return ret


def collect_ops(state):
    items = state.get('items')
    ops = []
    for itemid in items:
        item = items[itemid]
        if item['click']:
            item_locator = locator.get_locator(items, itemid)
            if item_locator is None:
                continue
            op = Operation("click", item_locator)
            ops.append(op)

    return ops


back_op = Operation("back")
home_op = Operation("home")
