import time
import re
import logging
import copy

import config
import operation
import condition
import environ
import perfmon
import value

logger = logging.getLogger("microtest")


class MicroTest(object):
    def __init__(self, steps=None, conds=None, state_change=None, filename=None,
                 name=None, expects=None, tags=None, meta=False, args='', feature_name='',
                 prio=0):
        if steps is None:
            steps = []
        if conds is None:
            conds = []
        if state_change is None:
            state_change = {}
        if expects is None:
            expects = []
        if tags is None:
            tags = set()
        self.steps = steps # type: List[Operation]
        self.conds = conds # type: List[Condition]
        self.state_change = state_change
        self.expects = expects
        self.filename = filename
        self.name = name
        self.feature_name = feature_name
        self.tags = set(tags)
        self._id = 0
        self.meta = meta
        self.args = parse_args(args)
        self.init_prio = prio
        self.read_only = self.calc_readonly()
        self.calc_prio()
        self.var = None
        self.update_prop()

    def update_prop(self):
        for prop in self.state_change:
            if (self.state_change[prop] != '' and self.state_change[prop] != 'false' and
                prop in config.must_cleanup_keys):
                self.add_tag('affect_server_state')
                break

    def calc_prio(self):
        prio = self.init_prio

        # change state, server state: bad!
        if self.has_tag('affect_server_state'):
            self.prio -= 1

        # do not change state: good
        prio -= len(self.state_change)

        # read only: good
        if self.read_only:
            prio += 5

        # more condition: harder to reach
        prio += len(self.conds)

        self.prio = prio
        return prio

    def calc_readonly(self):
        for op in self.steps:
            if not op.read_only():
                return False
        return True

    def get_steps(self):
        return self.steps

    def add_step(self, op):
        self.steps.append(op)
        self.read_only = self.calc_readonly()
        self.prio = self.calc_prio()
        self.update_prop()

    def usable(self, state):
        varz = self.collect_vars()
        for var in varz:
            if not value.has_param(var):
                return False
        for cond in self.conds:
            if not cond.check(state):
                return False
        if config.use_firststep_filter:
            if len(self.steps) > 0:
                first_step = self.steps[0]
                if not first_step.doable(state):
                    return False
        return True

    def get_screen(self):
        for cond in self.conds:
            if cond.name == 'equal':
                if 'screen' in cond.attr:
                    return cond.attr['screen']
        return None

    def get_post_cond(self, name):
        if name in self.state_change:
            return self.state_change[name]
        for expect in self.expects:
            if expect.name == 'equal':
                if name in expect.attr:
                    return expect.attr[name]
        return None

    def get_change_keys(self):
        return self.state_change.keys()

    def get_change_val(self, key):
        return self.state_change[key]

    def is_cleaner(self, prop):
        return prop in self.state_change and (self.state_change[prop] == '' or
                                              self.state_change[prop] == 'false')

    def change_state(self, state):
        for entry in self.state_change:
            state.set(entry, self.state_change[entry])

    def has_tag(self, tag):
        return tag in self.tags

    def meets_expectations(self, state):
        for expect in self.expects:
            if not expect.check(state):
                expect.explain(state)
                return False
        return True

    def set_id(self, _id):
        self._id = _id

    def get_id(self):
        return self._id

    def get_conds(self):
        return self.conds

    def model_state(self, state):
        for cond in self.conds:
            cond.apply(state)

    def add_cond(self, cond):
        self.conds.append(cond)
        self.calc_prio()

    def add_tag(self, tag):
        self.tags.add(tag)
        self.calc_prio()

    def add_expect(self, expect):
        self.expects.append(expect)
        self.calc_prio()

    def add_expect_eq(self, key, val):
        """ debug interface! """
        expect = condition.Condition("equal", {key: val})
        self.expects.append(expect)
        self.calc_prio()

    def add_change(self, key, val):
        self.state_change[key] = val
        self.calc_prio()
        self.update_prop()

    def set_prio(self, prio):
        self.init_prio = prio
        self.calc_prio()

    @perfmon.op("test", "%r")
    def attempt(self, dev, observer, state, tlib, env=environ.Environment()) -> bool:
        for step in self.steps:
            ret = step.do(dev, observer, state, env, tlib)
            if not ret:
                return False
            observer.update_state(dev, state, no_img=True)
            tlib.handle_dialog(state, dev, observer)
        self.change_state(state)

        # TODO: use waitforidle
        time.sleep(1)
        observer.wait_idle(dev)
        observer.update_state(dev, state)

        tlib.handle_sys_screen(state, dev, observer)
        tlib.handle_dialog(state, dev, observer)

        for retry in range(config.EXPECT_LIMIT):
            if self.meets_expectations(state):
                return True
            if state.get('screen', '').startswith('%s_' % tlib.app):
                app_screen = state.get('screen', '')
                canon_screen = app_screen.split('_', 1)[-1]
                logger.debug("check against canonical screen: %s -> %s",
                             app_screen, canon_screen)
                state.set('screen', canon_screen)
                if self.meets_expectations(state):
                    state.set('screen', app_screen)
                    return True
            observer.update_state(dev, state)
            time.sleep(0.5)
        return False

    def conds_str(self):
        ret = "conds ["
        for cond in self.conds:
            ret += "%s " % cond
        ret += "]"
        return ret

    def bind_args(self, env, realargs):
        for i in range(len(self.args)):
            env.bind_arg(self.args[i], realargs[i])

    def predict_after(self, screen):
        if self.read_only:
            return screen

        after_screen = self.get_post_cond('screen')
        if after_screen is None:
            # we don't know which screen we will reach
            return None
        after = copy.deepcopy(screen)

        for expect in self.expects:
            expect.apply(after)
        self.change_state(after)
        return after

    def collect_vars(self):
        if self.var is not None:
            return self.var
        self.var = set()
        for op in self.steps:
            self.var.update(op.collect_vars())
        return self.var

    def short_name(self):
        if self.feature_name is None:
            return self.name
        else:
            return "%s:%s" % (self.feature_name, self.name)

    def __repr__(self):
        ret = "%s [" % self.name
        for step in self.steps:
            ret += " %s," % step
        ret += "]"
        return ret

    def __str__(self):
        ret = "piece '%s' (\n" % self.name
        if self.args:
            ret += "  args (%s)" % ','.join(self.args)
        if self.conds:
            ret += "  %s" % self.conds_str()
        if self.state_change:
            ret += "  changes {"
            for key in self.state_change:
                ret += "%s => %s " % (key, self.state_change[key])
            ret += "}"
        if self.expects:
            ret += "  expects ["
            for expect in self.expects:
                ret += "%s " % expect
            ret += "]"
        if self.tags:
            ret += "  tags ["
            for tag in self.tags:
                ret += "#%s " % tag
            ret += "]\n"
        if self.steps:
            for step in self.steps:
                ret += "\t%s,\n" % step
        ret += ")"
        return ret

    def to_obj(self):
        return {'feature': self.feature_name, 'name': self.name}


def init_test(appname):
    test = MicroTest(steps=[
        operation.Operation('clear', None, {'name': appname}),
        #operation.Operation('kbdoff'),
        operation.Operation('start', None, {'name': appname}),
        operation.Operation('wait', None, {'time': 1000}),
        operation.Operation('waitact', None, {'name': appname}),
        operation.Operation('waitready'),
        operation.Operation('waitready'),
    ], conds=[
        condition.Condition('equal', {'screen': 'init'})
    ], name="start app", feature_name="meta", meta=True)
    for prop in config.init_state:
        test.add_change(prop, config.init_state[prop])
    return test


def restart_test(appname):
    return MicroTest(steps=[
        operation.Operation('stop', None, {'name': appname}),
        operation.Operation('start', None, {'name': appname}),
        operation.Operation('wait', None, {'time': 1000}),
        operation.Operation('waitact', None, {'name': appname}),
        operation.Operation('waitready'),
        operation.Operation('waitready'),
    ], conds=[
        condition.Condition('notequal', {'screen': 'init'})
    ], name="restart app", feature_name="meta", meta=True, prio=-30,
        state_change=config.restart_state_change)


arg_re = re.compile("[a-z0-9_]+")


def parse_args(args):
    if args is None:
        return []
    return arg_re.findall(args)


def gohome():
    return MicroTest(steps=[
        operation.Operation('home'),
        #        operation.Operation('wait', None, {'time': 1000}),
    ], state_change={'screen': 'init'}, name='go home', feature_name='meta',
        meta=True, prio=-1000)
