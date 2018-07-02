import logging

logger = logging.getLogger("condition")


def equal_val(a, b):
    if a == b:
        return True
    if a == '' and b == 'false' or a == 'false' and b == '':
        return True
    return False


class Condition(object):
    def __init__(self, name, attr):
        self.name = name
        self.attr = attr

    def check(self, state):
        if self.name == 'equal':
            for key in self.attr:
                myval = self.attr[key]
                if not equal_val(myval, state.get(key, '')):
                    return False
            return True
        elif self.name == 'notequal':
            for key in self.attr:
                myval = self.attr[key]
                if equal_val(myval, state.get(key, '')):
                    return False
            return True
        logger.warn("unhandled condition %s %r", self.name, self.attr)
        return True

    def apply(self, state):
        if self.name == 'equal':
            for key in self.attr:
                state.set(key, self.attr[key])

    def equals(self, other):
        return self.name == other.name and self.attr == other.attr

    def get_props(self):
        return list(self.attr)

    def explain(self, state):
        if self.name == 'equal':
            for key in self.attr:
                if self.attr[key] != state.get(key, ''):
                    logger.info("mismatch expectation: %s = %s, not %s",
                                key, state.get(key, ''), self.attr[key])
        elif self.name == 'notequal':
            for key in self.attr:
                if self.attr[key] == state.get(key, ''):
                    logger.info("mismatch expectation: %s = %s, bad", key, self.attr[key])

    def __str__(self):
        if self.name == 'equal':
            ret = ''
            for key in self.attr:
                ret += '%s = %s, ' % (key, self.attr[key])
        elif self.name == 'notequal':
            ret = ''
            for key in self.attr:
                ret += '%s != %s, ' % (key, self.attr[key])
        else:
            ret = "cond %s (" % self.name
            for key in self.attr:
                ret += "%s -> %s " % (key, self.attr[key])
            ret += ")"
        return ret
