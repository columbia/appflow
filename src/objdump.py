import yaml
import copy
import logging

logger = logging.getLogger("objdump")

class ObjDumper(object):
    def __init__(self, props):
        self.props = props

    def dump(self, obj):
        state = {}
        for prop in self.props:
            state[prop] = copy.deepcopy(getattr(obj, prop))
        return state

    def load(self, obj, state):
        for prop in self.props:
            if prop in state:
                setattr(obj, prop, state[prop])
            else:
                logger.warning("missing prop %s", prop)

    def dumps(self, obj):
        return yaml.dump(obj)

    def loads(self, obj, s):
        return self.load(obj, yaml.load(s))
