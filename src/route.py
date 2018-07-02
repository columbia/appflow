import microtest
import device
import perfmon
import progress

import copy
import logging

logger = logging.getLogger("route")


class Route(object):
    """
    steps: List<Microtest>
    """
    def __init__(self, steps=[]):
        self.steps = steps
        self._id = 0

    def is_unclean(self):
        for step in self.steps:
            if step.has_tag("affect_server_state"):
                return True
        return False

    def set_id(self, _id):
        self._id = _id

    def get_id(self):
        return self._id

    def add_test(self, test):
        self.steps.append(test)

    @perfmon.op("route")
    def replay(self, dev: device.Device, state, observer, tlib, states=None):
        for test in self.steps:
            try:
                ret = test.attempt(dev, observer, state, tlib)
            except:
                progress.report_progress("  STEP %s EXCEPTION" % test.short_name())
                raise
            if not ret:
                progress.report_progress("  STEP %s FAILED" % test.short_name())
                return False
            tlib.handle_sys_screen(state, dev, observer)
            if states is not None:
                states.append(copy.deepcopy(state))
        return True

    def length(self):
        return len(self.steps)

    def has_tag(self, tag):
        for step in self.steps:
            if step.has_tag(tag):
                return True
        return False

    def __repr__(self):
        ret = "["
        for step in self.steps:
            ret += "%s," % step.name
        ret += "]"
        return ret

    def __str__(self):
        ret = "route ["
        for step in self.steps:
            ret += " %s," % step.name
        ret += "]"
        return ret

    def to_obj(self):
        obj_steps = []
        for step in self.steps:
            obj_steps.append({"feature": step.feature_name, "name": step.name})
        return {"id": self._id, "steps": obj_steps}

    @staticmethod
    def from_obj(obj, tlib):
        self = Route()
        self._id = obj['id']
        self.steps = []
        for obj_step in obj['steps']:
            step = tlib.find_test(obj_step['feature'], obj_step['name'])
            if step is None:
                logger.error("fail to find test %(feature)s %(name)s" % obj_step)
                #raise Exception("fail to find test %(feature)s %(name)s" % obj_step)
                return None
            else:
                self.steps.append(step)
        return self


empty_route = Route([microtest.gohome()])


def new(route, step):
    new_route = copy.deepcopy(route)
    new_route.add_test(step)
    return new_route
