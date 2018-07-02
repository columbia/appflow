import action
import util
import config


class Widget(object):
    def __init__(self, tree, nodeid=None):
        if nodeid is None:
            self.node = tree
        else:
            self.node = tree[nodeid]
            self._content = self.get_content(tree, nodeid)
        self.node_id = nodeid
        self.center_x = 50
        self.center_y = 50

    def title(self):
        if self.node['text']:
            return self.node['text']
        elif self.node['desc']:
            return '(%s)' % self.node['desc']
        elif self.node['id']:
            return '#%s' % self.node['id']

    def text(self):
        return self.node['text']

    def content(self):
        return self._content

    def get_content(self, tree, nodeid):
        content = node_content(tree[nodeid])
        for childid in tree[nodeid]['children']:
            content += ' ' + self.get_content(tree, childid)
        return content

    def clazz(self):
        return self.node['class']

    def id(self):
        return self.node['id']

    def x(self):
        return self.node['origx']

    def y(self):
        return self.node['origy']

    def w(self):
        return self.node['origw']

    def h(self):
        return self.node['origh']

    def set_center(self, x, y):
        self.center_x = x
        self.center_y = y

    def center(self):
        return (self.x() + self.w() * self.center_x / 100,
                self.y() + self.h() * self.center_y / 100)

    def is_password(self):
        return self.node['password']

    def orig_prop(self, name):
        return self.node['origitem'][name]

    def relocate(self, newstate):
        # text/desc may change
        # id would not change, and class also
        tree = newstate.get('tree')
        bestrank = -1
        bestnode = None
        for nodeid in tree:
            node = tree[nodeid]
            if node['class'] != self.node['class'] or node['id'] != self.node['id']:
                continue
            # just check location
            rank = 0
            for prop in ('x', 'y', 'width', 'height'):
                if node[prop] == self.node[prop]:
                    rank += 1
            if bestnode is None or bestrank < rank:
                bestrank = rank
                bestnode = nodeid
        if bestnode is None:
            return self
        else:
            return Widget(tree, bestnode)

    def __str__(self):
        return util.describe_node(self.node, short=True)


def node_content(node):
    if ((node['class'] == 'View' or node['class'] == 'Spinner' or
         node['class'] == 'Button' or node['class'] == 'WebView') and
            not node['text']):
        return node['desc']
    return node['text']


def text(dev, node, string):
    click(dev, node)
    action.text(dev, string)
    action.back(dev)


def click(dev, node):
    x = node['origx'] + node['origw'] / 2
    y = node['origy'] + node['origh'] / 2
    action.tap(dev, x, y)


def swipe(dev, node, dir):
    if dir == 'up':
        x = node['origx'] + node['origw'] / 2
        y1 = node['origy'] + node['origh'] * 0.8
        y2 = node['origy'] + node['origh'] * 0.2
        action.swipe(dev, x, y1, x, y2)
    elif dir == 'down':
        x = node['origx'] + node['origw'] / 2
        y2 = node['origy'] + node['origh'] * 0.8
        y1 = node['origy'] + node['origh'] * 0.2
        action.swipe(dev, x, y1, x, y2)


def meta_widget(x, y, w, h, click=True):
    return Widget({'x': x, 'y': y, 'width': w, 'height': h,
                   'origx': x, 'origy': y, 'origw': w, 'origh': h,
                   'raw': [-1], 'class': 'META', 'desc': '', 'text': '', 'id': '',
                   'click': click, 'scroll': False, 'focused': False, 'webview': False})


back_btn = meta_widget(0, 1794, 300, 100)
home_btn = meta_widget(300, 1794, 300, 100)
recent_btn = meta_widget(600, 1794, 300, 100)
ime_btn = meta_widget(900, 1794, 180, 100)
full_screen = meta_widget(0, 0, config.width, config.height)
