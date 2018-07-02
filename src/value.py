#!/usr/bin/env python3

import re
import logging
import os
import json

import locator
import config

logger = logging.getLogger("value")


class ConstValue(object):
    def __init__(self, value):
        self.value = value

    def get(self, env):
        return self.value

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "%s" % self.value


class Parameter(object):
    def __init__(self, name):
        self.name = name

    def get(self, env):
        return get_param(self.name)

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return '@%s' % self.name


class Argument(object):
    def __init__(self, name):
        self.name = name

    def get(self, env):
        return env.get_arg(self.name)

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return '$%s' % self.name


params = {} # type: Dict[str, str]
locators = {}
exlocators = {}
screenobs = {}
locstat = {}


def get_param(name, defval=None):
    if name not in params:
        logger.info("param undef: %s", name)
    return params.get(name, defval)


def has_param(name):
    return name in params


def get_locator(tag):
    return locators.get(tag, None)


def get_exlocator(screen, tag):
    key = "%s.%s" % (screen, tag)
    return exlocators.get(key, None)


def get_screenobs():
    return screenobs


def init_params(paramsdir: str, app: str=None):
    params.clear()
    locators.clear()
    exlocators.clear()
    screenobs.clear()
    read_param(os.path.join(paramsdir, "params.txt"))
    if app is not None:
        read_param(os.path.join(paramsdir, "%s.txt" % app))


param_re = re.compile("([^ ]+)\s+(.+)")
locator_re = re.compile("@([^ ]+)\s+(.+)")
exlocator_re = re.compile("@([^ .]+)\.([^ .]+)\s+(.+)")
screenob_re = re.compile("%([^ ]+)\s+(.+)")
config_re = re.compile("config.([^ ]+)\s+(.+)")


def read_param(filename: str):
    if not os.path.exists(filename):
        return
    logger.debug("loading params from %s", filename)
    for line in open(filename).read().split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        if config_re.match(line):
            (name, val) = config_re.match(line).groups()
            val = json.loads(val)
            setattr(config, name, val)
        elif exlocator_re.match(line):
            (screen, name, marker) = exlocator_re.match(line).groups()
            key = "%s.%s" % (screen, name)
            exlocators[key] = exlocators.get(key, []) + [locator.parse(marker)]
        elif locator_re.match(line):
            (name, marker) = locator_re.match(line).groups()
            locators[name] = locators.get(name, []) + [locator.parse(marker)]
        elif screenob_re.match(line):
            (name, clue) = screenob_re.match(line).groups()
            screenobs[name] = screenobs.get(name, []) + [
                locator.parse_screenob(name, clue)]
        elif param_re.match(line):
            (name, value) = param_re.match(line).groups()
            params[name] = value


def parse_value(text: str):
    if text.startswith('@'):
        return Parameter(text[1:])
    elif text.startswith('$'):
        return Argument(text[1:])
    else:
        return ConstValue(text)


def is_parameter(value):
    return type(value) is Parameter


def mark_locator(marker, loc_ret, ml_ret):
    key = str(marker)
    logger.info("LOCATOR [%s] -> |%s|, ML |%s|", key, loc_ret, ml_ret)
    if key not in locstat:
        locstat[key] = [0, 0]
    if ml_ret is None or str(ml_ret) != str(loc_ret):
        locstat[key][1] += 1
    else:
        locstat[key][0] += 1


def print_stat():
    logger.info("======= locator statistics =======")
    for key in locstat:
        entry = locstat[key]
        logger.info("locator %s: %d+ %d-", key, entry[0], entry[1])


if __name__ == "__main__":
    import sys
    init_params("../etc/", sys.argv[1])
    print("  Params:")
    for param in params:
        print("%s = %s" % (param, params[param]))
    print("  Locators:")
    for tag in locators:
        for marker in locators[tag]:
            print("%s = %s" % (tag, marker))
    print("  ExLocators:")
    for tag in exlocators:
        for marker in exlocators[tag]:
            print("%s = %s" % (tag, marker))
    print("  ScreenObservers:")
    for screen in screenobs:
        for ob in screenobs[screen]:
            print("%s" % (ob))
    print("  Config:")
    for key in dir(config):
        if key.startswith('_'):
            continue
        print("%s = %s" % (key, getattr(config, key)))
