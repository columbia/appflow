import logging

logger = logging.getLogger("env")

class Environment(object):
    def __init__(self):
        self.args = {}

    def bind_arg(self, name, value):
        self.args[name] = value

    def get_arg(self, name):
        if not name in self.args:
            logger.error("missing arg %s", name)
            return None
        return self.args[name]

empty = Environment()
