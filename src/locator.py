import widget
import value

import re
import logging

logger = logging.getLogger('locator')

def match(a, val, case):
    if case:
        return a.strip() == val.strip()
    else:
        return a.strip().lower() == val.strip().lower()

def contains(a, val, case):
    if case:
        x = val.strip()
        y = a.strip()
    else:
        x = val.strip().lower()
        y = a.strip().lower()

    return re.findall(x, y) != []


path_segment_re = re.compile("([A-Z])(\d+)")

class Locator(object):
    def __init__(self, method, value, clz=None, x=None, y=None, path=None):
        self.method = method
        self.value = value
        self.clz = clz
        self.x = x
        self.y = y
        self.path = path
        self.counter = 0

    def follow_path(self, tree, nodeid):
        if self.path is not None:
            for segment in path_segment_re.findall(self.path):
                node = tree[nodeid]
                (direction, count) = segment
                count = int(count)
                if direction == 'P':
                    for i in range(count):
                        nodeid = node['parent']
                elif direction == 'C':
                    nodeid = node['children'][count]
                elif direction == 'L' or direction == 'R':
                    parent = node['parent']
                    for xnum in range(len(tree[parent]['children'])):
                        if tree[parent]['children'][xnum] == nodeid:
                            if direction == 'L':
                                nodeid = tree[parent]['children'][xnum - 1]
                            else:
                                nodeid = tree[parent]['children'][xnum + 1]
                            break

        return widget.Widget(tree, nodeid)

    def find_node(self, state, itemid):
        tree = state.get('tree')
        for nodeid in tree:
            if itemid in tree[nodeid]['raw']:
                return self.follow_path(tree, nodeid)
        return None

    def match_item(self, item, env, val, case):
        if self.clz is not None and item['class'] != self.clz:
            return False

        item_is_webnode = (('webview' in item and item['webview']) or
                           (item['class'] == 'View' or item['class'] == 'Button'
                            or item['class'] == 'Spinner' or item['class'] == 'WebView'))

        if self.method == 'text':
            if match(item['text'], val, case):
                return True

        elif self.method == 'textcontains':
            #logger.info("%s text %s contain %s?", item['class'], item['text'], val)
            if(contains(item['text'], val, case) or (
                item_is_webnode and contains(item['desc'], val, case))):
                return True

        elif self.method == 'id':
            if match(item['id'], val, case):
                return True

        elif self.method == 'desc':
            if match(item['desc'], val, case):
                return True

        elif self.method == 'marked':
            if (match(item['id'], val, case) or
                match(item['text'], val, case) or
                match(item['desc'], val, case)):
                return True

        elif self.method == 'class':
            if match(item['class'], val, case):
                return True
        elif self.method == 'focused':
            if 'focused' in item and item['focused'] == (val == 'true'):
                return True

        elif self.method == 'empty':
            if ((item_is_webnode and match(item['id'], val, case)
                 and item['desc'].strip() == '' and item['text'].strip() == '') or
                ((not item_is_webnode and match(item['id'], val, case) and
                  item['text'].strip() == ''))):
                return True
        elif self.method == 'no':
            self.counter += 1
            if self.counter == int(val):
                return True
        else:
            logger.error("unknown method %s(%s)", self.method, val)
            return None
        return False

    def locate(self, state, observer, env):
        if self.method == 'back':
            return [widget.back_btn]
        elif self.method == 'home':
            return [widget.home_btn]
        elif self.method == 'recent':
            return [widget.recent_btn]
        elif self.method == 'ime':
            return [widget.ime_btn]

        items = state.get('items')
        val = self.value.get(env)
        if val is None or val == 'notexist':
            return []

        self.counter = 0
        for itemid in items:
            if self.method == 'itemid':
                ret = (itemid == val)
            else:
                ret = self.match_item(items[itemid], env, val, case=True)
            if ret is None:
                return []
            if ret:
                ret = self.find_node(state, itemid)
                if ret is not None:
                    if self.x is not None:
                        ret.set_center(self.x, self.y)
                    return [ret]

        self.counter = 0
        for itemid in items:
            ret = self.match_item(items[itemid], env, val, case=False)
            if ret:
                ret = self.find_node(state, itemid)
                if ret is not None:
                    if self.x is not None:
                        ret.set_center(self.x, self.y)
                    return [ret]

        return []

    def present(self, state) -> bool:
        # I don't want to save too much info in state
        return True

    def no_scroll(self):
        return False

    def get_parent(self, level):
        path = 'P%d' % level
        if self.path is not None:
            path = self.path + path
        return Locator(self.method, self.value, self.clz, self.x, self.y, path)

    def __hash__(self):
        return hash(self.method) + hash(self.value)

    def __eq__(self, other):
        return self.method == other.method and self.value == other.value

    def __str__(self):
        return '!' + self.to_str()

    def to_str(self):
        ret = ''

        if self.path:
            ret += '%s.' % self.path

        if self.clz:
            ret += '%s+' % self.clz

        if self.value is None:
            ret += self.method
        else:
            ret += "%s:'%s'" % (self.method, self.value)

        if self.x is not None:
            ret += '+%d+%d' % (self.x, self.y)

        return ret

class Function(object):
    def __init__(self, name, arg):
        self.name = name
        self.arg = arg

    def evaluate(self, state):
        if self.name == 'locator':
            if self.arg.locate(state, None, None) == []:
                return False
            else:
                return True
        elif self.name == 'not':
            return not self.arg.evaluate(state)
        elif self.name == 'act':
            return re.compile(self.arg).match(state['act']) is not None
        return False

def inv_func(func):
    return Function('not', func)

class ScreenObserver(object):
    def __init__(self, screen):
        self.screen = screen
        self.funcs = []

    def add_func(self, func):
        self.funcs.append(func)

    def check(self, state):
        for func in self.funcs:
            if not func.evaluate(state):
                return False
        return True

    def __str__(self):
        ret = "#%s [" % self.screen
        for func in self.funcs:
            ret += "%s, " % func
        ret += ']'
        return ret

locator_re = re.compile("!([^:]+):'(.+)'")
clslocator_re = re.compile("!([^+]+)\+([^:]+):'(.+)'")
pathlocator_re = re.compile("!([^+]+)\.([^:]+):'(.+)'")
poslocator_re = re.compile("!([^:]+):'(.+)'\+(.+)\+(.+)")
simple_re = re.compile("!(.+)")
def parse(part):
    if pathlocator_re.match(part):
        (path, method, val) = pathlocator_re.match(part).groups()
        val = value.parse_value(val)
        return Locator(method, val, path=path)
    if clslocator_re.match(part):
        (clz, method, val) = clslocator_re.match(part).groups()
        val = value.parse_value(val)
        return Locator(method, val, clz=clz)
    if poslocator_re.match(part):
        (method, val, x, y) = poslocator_re.match(part).groups()
        x = int(x)
        y = int(y)
        val = value.parse_value(val)
        return Locator(method, val, x=x, y=y)
    if locator_re.match(part):
        (method, val) = locator_re.match(part).groups()
        val = value.parse_value(val)
        return Locator(method, val)
    if simple_re.match(part):
        method = simple_re.match(part).group(1)
        return Locator(method, None)
    return Locator('marked', value.parse_value(part))

function_re = re.compile("([a-z_A-Z0-9]+)\((.*)\)")
def parse_func(part):
    if function_re.match(part):
        (name, arg) = function_re.match(part).groups()
        return Function(name, arg)
    return Function('locator', parse(part))


def collect_descs(items, rootid):
    descs = {rootid: 0}
    while True:
        changed = False
        for itemid in items:
            item = items[itemid]
            if item['parent'] in descs and itemid not in descs:
                descs[itemid] = descs[item['parent']] + 1
                changed = True
        if not changed:
            break
    del descs[rootid]
    return descs


marked_keys = ('id', 'text', 'desc')
def get_locator(items, itemid):
    item = items[itemid]
    samekey_locator = None

    for key in marked_keys:
        my_value = item[key]
        if not my_value:
            continue
        global_uniq = True
        samekey_uniq = True
        for otheritemid in items:
            if otheritemid == itemid:
                continue
            otheritem = items[otheritemid]
            for otherkey in marked_keys:
                if otheritem[otherkey] == my_value:
                    global_uniq = False
                    if otherkey == key:
                        samekey_uniq = False

        if key == 'id':
            if samekey_uniq:
                return const_locator(key, my_value)

        if global_uniq:
            return const_locator('marked', my_value)
        if samekey_uniq and samekey_locator is None:
            samekey_locator = const_locator(key, my_value)

    if samekey_locator is not None:
        return samekey_locator

    my_clz = item['class']
    for key in marked_keys:
        my_value = item[key]
        if not my_value:
            continue
        global_uniq = True
        samekey_uniq = True
        for otheritemid in items:
            if otheritemid == itemid:
                continue
            otheritem = items[otheritemid]
            if otheritem['class'] != my_clz:
                continue
            for otherkey in marked_keys:
                if otheritem[otherkey] == my_value:
                    global_uniq = False
                    if otherkey == key:
                        samekey_uniq = False

        if key == 'id':
            if samekey_uniq:
                return const_locator(key, my_value, my_clz)

        if global_uniq:
            return const_locator('marked', my_value, my_clz)
        if samekey_uniq and samekey_locator is None:
            samekey_locator = const_locator(key, my_value, my_clz)

    if samekey_locator is not None:
        return samekey_locator

    descs = collect_descs(items, itemid)
    for descid in descs:
        desc_loc = get_locator(items, descid)
        if desc_loc is not None:
            return desc_loc.get_parent(descs[descid])

    return None

def const_locator(key, val, clz=None):
    return Locator(key, value.ConstValue(val), clz)

def itemid_locator(itemid):
    return Locator("itemid", value.ConstValue(itemid))

inv_re = re.compile("(?:not|!)\s+(.+)")
def parse_screenob(name, clue):
    ret = ScreenObserver(name)
    clues = clue.split('&&')
    for item in clues:
        item = item.strip()
        if inv_re.match(item):
            ret.add_func(inv_func(parse_func(inv_re.match(item).group(1))))
        else:
            ret.add_func(parse_func(item))
    return ret

