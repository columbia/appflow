import logging
logger = logging.getLogger("action")


class Action(object):
    def __init__(self, name, attr=None):
        if attr is None:
            attr = []
        self.name = name
        self.attr = attr

    def do(self, dev, observer, env):
        return dev.do_action(self, observer, env)
