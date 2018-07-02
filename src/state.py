import config
import util

import copy


class State(object):
    def __init__(self, attr=None):
        if attr is None:
            attr = {}
        self.attr = attr

    def set(self, name, val):
        self.attr[name] = val

    def get(self, name, defval=None):
        return self.attr.get(name, defval)

    def remove(self, name):
        if name in self.attr:
            del self.attr[name]

    def matches(self, other):
        for key in self.attr:
            if util.unequal(self.attr[key], other.get(key, '')):
                return False
        return True

    def to_essential(self, essential_props):
        """obtain essential screen"""
        essential = self.filter_with(essential_props)

        if self.is_unknown():
            essential.set('items', simplify_items(self.attr['items']))

        if config.use_firststep_filter:
            if 'guess_items' in self.attr:
                essential.set('tags', list(sorted(self.attr['guess_items'])))

        return essential

    def filter_with(self, props):
        filtered = State()
        for prop in props:
            if prop in self.attr:
                filtered.set(prop, self.attr[prop])
        return filtered

    def merge(self, other):
        for name in other.attr:
            self.attr[name] = other.attr[name]

    def is_unknown(self):
        if ('screen' not in self.attr or
            self.attr['screen'] == 'NONE' or
            self.attr['screen'] == 'WRONG'):
            return True
        else:
            return False

    def same_as(self, other):
        # looks the same
        if other is None:
            return False
        return self.attr['items'] == other.attr['items']

    def reset(self):
        self.attr = {}

    def __hash__(self):
        return hash(self.attr.get('screen', ''))

    def __eq__(self, other):
        for key in self.attr:
            if util.unequal(self.get(key, ''), other.get(key, '')):
                return False
        for key in other.attr:
            if util.unequal(self.get(key, ''), other.get(key, '')):
                return False
        return True

    def __repr(self):
        return self.__str__()

    def __str__(self):
        content = ''
        for key in sorted(self.attr):
            value = self.attr[key]
            if value == '' or value == 'false' or key == 'app':
                continue
            if content != '':
                content += ', '
            if value == 'true':
                content += key
            else:
                content += '%s=%s' % (key, value)
        return "state (%s)" % content

    def to_obj(self):
        new_attr = copy.deepcopy(self.attr)
        if 'screen_img' in new_attr:
            del new_attr['screen_img']

        return new_attr

    @staticmethod
    def from_obj(obj):
        inst = State(obj)
        return inst


init_state = State({'screen': 'init'})

simplify_item_props = ['focused', 'childcount', 'parent', 'depth', 'childid', 'children',
                       'sub_important', 'important', 'password', 'click', 'scroll',
                       'width', 'height', 'x', 'y']


def simplify_items(items):
    simplified = copy.deepcopy(items)
    for itemid in simplified:
        item = simplified[itemid]
        for prop in simplify_item_props:
            if prop in item:
                del item[prop]
        for prop in sorted(item):
            if util.equal(item[prop], ''):
                del item[prop]
    return simplified
