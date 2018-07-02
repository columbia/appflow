from selenium import webdriver
from html.parser import HTMLParser
import logging
import tempfile
import json
import time

import webactions
import sense
import util
import config
import monitor

logger = logging.getLogger("webdriver")

no_close = set(['meta', 'link', 'img', 'input', 'param', 'hr', 'area', 'base', 'br',
                'col', 'embed', 'command', 'keygen', 'source', 'track', 'wbr'])
clickable_tags = set(['a', 'input', 'button', 'select'])
filtered_tags = set(['script', 'meta', 'link', 'noscript', 'style', '#comment'])
notext_tags = filtered_tags.union(set(['#document', 'html', 'body', 'form', 'main']))

grab_script = """
function traverse(node, depth) {
    var width = 0, height = 0, x = 0, y = 0;
    try {
        var clientRect = node.getBoundingClientRect();
        width = clientRect.width;
        height = clientRect.height;
        x = clientRect.x;
        y = clientRect.y;
    } catch (e) {
    }
    var props = {}
    try {
        for (var i = 0; i < node.attributes.length; i++) {
            props[node.attributes[i].name] = node.attributes[i].value
        }
    } catch (e) {
    }
    var nodeId = "";
    try {
        nodeId = node.attributes["id"].value
    } catch (e) {
    }
    var classes = [];
    try {
        classes = node.classList.values();
    } catch (e) {
    }
    var ret = {
        "tag": node.nodeName,
        "id": nodeId,
        "class": node.className,
        "classes": classes,
        "value": node.value,
        "text": node.wholeText,
        "click": node.onclick != null,
        "props": props,
        "depth": depth,
        "width": width,
        "height": height,
        "x": x,
        "y": y,
        "children": [],
        "childid": 0,
    }

    for (var i = 0; i < node.childNodes.length; i++) {
        var child = node.childNodes[i];
        var childRet = traverse(child, depth + 1);
        if (childRet != null) {
            if (childRet["tag"] == "#text") {
                if (ret["text"] == null) {
                    ret["text"] = "";
                }
                ret["text"] = ret["text"] + childRet["text"];
            } else {
                childRet["childid"] = ret["children"].length;
                ret["children"].push(childRet);
            }
        }
    };

    return ret;
}

return traverse(document.body, 0)

"""


def hier_to_items(hier):
    jsitems = JSItems()
    jsitems.add_tree(hier)
    return jsitems.get_items()


def load(basename):
    with open(basename + ".hier", 'r') as f:
        s = f.read()
        grab_ret = json.loads(s)
        items = hier_to_items(grab_ret)

    with open(basename + ".htm", 'r') as f:
        src = f.read()

    with open(basename + ".url", 'r') as f:
        url = f.read()

    screenshot = basename + ".png"

    return {
        'src': src,
        'items': items,
        'url': url,
        'scr': screenshot,
    }


# legacy
def is_useful(tag_name):
    return tag_name in set(['input', 'div', 'span', 'a', 'form'])


def traverse(node, depth):
    tag_name = node['tag']
    if is_useful(tag_name):
        print(' ' * depth, tag_name, node['id'], '%dx%d @%dx%d' % (
            node['width'], node['height'], node['x'], node['y']), node['data'])
    for child in node['children']:
        traverse(child, depth + 1)
# legacy end


class MyHTMLParser(HTMLParser):
    def __init__(self, driver):
        HTMLParser.__init__(self)
        self.stack = []
        self.root = None
        self.driver = driver

    def grab_page(self):
        self.feed(self.driver.page_source)

    def handle_starttag(self, tag, attrs):
        # print('start tag:', tag)
        if len(self.stack) > 0:
            childid = len(self.stack[-1]['children'])
        else:
            childid = 0

        new_node = {'tag': tag,
                    'attrs': attrs,
                    'childid': childid,
                    'data': None,
                    'children': [],
                    'id': None}
        for pair in attrs:
            if pair[0] == 'id':
                new_node['id'] = pair[1]
        if self.root is None:
            self.root = new_node
        if len(self.stack) > 0:
            self.stack[-1]['children'].append(new_node)
        self.stack.append(new_node)
        self.get_rect(new_node)
        if tag in no_close:
            self.closetag(tag)

    def closetag(self, tag):
        # print('end tag:', tag)
        self.stack.pop()

    def handle_endtag(self, tag):
        if tag not in no_close:
            self.closetag(tag)

    def handle_data(self, data):
        self.stack[-1]['data'] = data

    def get_xpath(self):
        ret = ''
        for level in self.stack:
            ret += '/*[%d]' % (level['childid'] + 1)
        if ret == '':
            return '/'
        return ret

    def get_rect(self, node):
        xpath = self.get_xpath()
        try:
            webnode = self.driver.find_element_by_xpath(xpath)
            rect = webnode.rect
            node['width'] = rect['width']
            node['height'] = rect['height']
            node['x'] = rect['x']
            node['y'] = rect['y']
        except:
            logging.exception("get_rect")
            node['width'] = 0
            node['height'] = 0
            node['x'] = 0
            node['y'] = 0

    def get_items(self):
        webitems = WebItems()
        webitems.add_tree(self.root)
        return webitems.get_items()


class JSItems(object):
    def __init__(self):
        self.counter = 0
        self.items = {}

    def add_item(self, node, depth):
        self.counter += 1
        self.items[self.counter - 1] = self.convert_node(node, depth)
        return self.counter - 1

    def add_tree(self, root):
        self.add_node(root, 0)

    def add_node(self, node, depth):
        if node['tag'].lower() in filtered_tags:
            return None
        nodeid = self.add_item(node, depth)
        for child in node['children']:
            childid = self.add_node(child, depth + 1)
            if childid is None:
                continue
            self.items[nodeid]['children'].append(childid)
            self.items[childid]['parent'] = nodeid
        return nodeid

    def convert_name(self, name, props):
        if name == 'IMG':
            return 'ImageView'
        if name == 'BUTTON':
            return 'Button'
        # if name in textlike_names:
        #    return 'TextView'
        if name == 'INPUT':
            if 'type' in props:
                _type = props['type']
                if (_type == 'email' or _type == 'password' or
                        _type == 'tel' or _type == 'text'):
                    return 'EditText'
                elif _type == 'checkbox':
                    return 'CheckBox'
                elif _type == 'submit' or _type == 'button':
                    return 'Button'
                elif _type == 'radio':
                    return 'RadioButton'
            return 'EditText'
        if name == 'SELECT':
            return 'Spinner'
        if name == 'TEXTAREA':
            return 'EditText'
#        if name == 'DIV':
#            return 'DivLayout'
#        if name == 'SPAN':
#            return 'SpanLayout'
        return name

    def get_value(self, node, props):
        if node['value'] is not None:
            return util.simplify_text(str(node['value']))
        else:
            return ''

    def get_classes(self, node, props):
        return node['class']

    def is_clickable(self, node, props):
        return node['click'] or node['tag'].lower() in clickable_tags

    def is_password(self, node, props):
        return 'type' in props and props['type'] == 'password'

    def is_checkable(self, node, props):
        if 'type' not in props:
            return False
        return props['type'] == 'checkbox' or props['type'] == 'radio'

    def get_text(self, node):
        if node['tag'] in notext_tags:
            return ''
        elif node['text'] is not None:
            return util.simplify_text(node['text'])
        else:
            return ''

    def convert_node(self, node, depth):
        props = node['props']
        item = {'class': self.convert_name(node['tag'], props),
                'text': self.get_text(node),
                'desc': self.get_value(node, props),
                'x': int(node['x']),
                'y': int(node['y']),
                'width': int(node['width']),
                'height': int(node['height']),
                'id': str(node['id']) if node['id'] else str(node['class']),
                'classes': self.get_classes(node, props),
                'click': self.is_clickable(node, props),
                'scroll': False,
                'selected': False,
                'password': self.is_password(node, props),
                'focused': False,
                'children': [],
                'checkable': self.is_checkable(node, props),
                'childid': node['childid'],
                'parent': 0,
                'depth': depth,
                'props': props,
                'tag': node['tag'],
                'webview': True
                }
        return item

    def get_items(self):
        return self.items


class WebItems(object):
    def __init__(self):
        self.counter = 0
        self.items = {}

    def add_item(self, node, depth):
        self.counter += 1
        self.items[self.counter - 1] = self.convert_node(node, depth)
        return self.counter - 1

    def add_tree(self, root):
        self.add_node(root, 0)

    def add_node(self, node, depth):
        if node['tag'] in filtered_tags:
            return None
        nodeid = self.add_item(node, depth)
        for child in node['children']:
            childid = self.add_node(child, depth + 1)
            if childid is None:
                continue
            self.items[nodeid]['children'].append(childid)
            self.items[childid]['parent'] = nodeid
        return nodeid

    def attrs_to_props(self, attrs):
        props = {}
        for pair in attrs:
            props[pair[0]] = pair[1]
        return props

    def convert_name(self, name, props):
        name = name.upper()
        if name == 'IMG':
            return 'ImageView'
        if name == 'BUTTON':
            return 'Button'
        # if name in textlike_names:
        #    return 'TextView'
        if name == 'INPUT':
            if 'type' in props:
                _type = props['type']
                if (_type == 'email' or _type == 'password' or
                        _type == 'tel' or _type == 'text'):
                    return 'EditText'
                elif _type == 'checkbox':
                    return 'CheckBox'
                elif _type == 'submit':
                    return 'Button'
                elif _type == 'radio':
                    return 'RadioButton'
            return 'EditText'
        if name == 'SELECT':
            return 'Spinner'
        if name == 'TEXTAREA':
            return 'EditText'
#        if name == 'DIV':
#            return 'DivLayout'
#        if name == 'SPAN':
#            return 'SpanLayout'
        return name

    def get_value(self, node, props):
        if 'value' in props:
            return props['value']
        else:
            return ''

    def get_classes(self, props):
        return props['class'].split(' ') if 'class' in props else []

    def is_clickable(self, node, props):
        return node['tag'] in clickable_tags or 'onclick' in props

    def is_password(self, node, props):
        return 'type' in props and props['type'] == 'password'

    def is_checkable(self, node, props):
        if 'type' not in props:
            return False
        return props['type'] == 'checkbox' or props['type'] == 'radio'

    def get_text(self, node):
        if node['tag'] in notext_tags:
            return ''
        else:
            return node['data'] if node['data'] else ''

    def convert_node(self, node, depth):
        props = self.attrs_to_props(node['attrs'])
        item = {'class': self.convert_name(node['tag'], props),
                'text': self.get_text(node),
                'desc': self.get_value(node, props),
                'x': int(node['x']),
                'y': int(node['y']),
                'width': int(node['width']),
                'height': int(node['height']),
                'id': node['id'] if node['id'] is not None else '',
                'classes': self.get_classes(props),
                'click': self.is_clickable(node, props),
                'scroll': False,
                'selected': False,
                'password': self.is_password(node, props),
                'focused': False,
                'children': [],
                'checkable': self.is_checkable(node, props),
                'childid': node['childid'],
                'depth': depth,
                'webview': True
                }
        return item

    def get_items(self):
        return self.items


class GeckoDriver(object):
    def __init__(self):
        self.proc = None
        self.port = 0

    def run(self):
        self.proc = monitor.monitor_cmd(["geckodriver", "-p", "0"], self.proc_cb)

    def start(self):
        self.run()
        while self.port == 0:
            time.sleep(0.2)

        return self.port

    def kill(self):
        if self.proc is not None:
            self.proc.kill()

    def proc_cb(self, kind, value):
        if kind == monitor.ProcInfo.errout:
            value = value.decode('utf-8')
            if "Listening on" in value:
                self.port = int(value.strip().split(':')[-1])
        elif kind == monitor.ProcInfo.exited:
            logger.info("geckodriver exited")


class WebDevice(object):
    def __init__(self):
        self.driver = None
        self.action_funcs = webactions.action_funcs
        self.use_web_grab = True
        self.kind = 'web'
        self.geckodriver = None

    def connect(self, addr='http://localhost:4444',
                useragent="Mozilla/5.0 (Android 4.4; Mobile; rv:41.0) Gecko/41.0 " +
                "Firefox/41.0"):
            #useragent="Mozilla/5.0 (Linux; Android 5.1.1; Nexus 5 Build/LMY48B; wv)" +
            #"AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 " +
            #"Chrome/43.0.2357.65 Mobile Safari/537.36"):
        capabilities = {
            "moz:firefoxOptions": {
                "prefs": {
                    "general.useragent.override": useragent,
                    "layout.css.devPixelsPerPx": "1.5",
                }
            }
        }
        try:
            self.driver = webdriver.Remote(addr, desired_capabilities=capabilities)
        except:
            logger.info("fail to connect, start own geckodriver")
            self.geckodriver = GeckoDriver()
            port = self.geckodriver.start()
            addr = "http://localhost:%d" % port
            logger.info("connecting to %s", addr)
            try:
                self.driver = webdriver.Remote(addr, desired_capabilities=capabilities)
            except:
                logger.exception("fail to connect again!")
                raise

        self.driver.set_window_size(config.width, config.height)

    def goto(self, url):
        self.driver.get(url)

    def capture_hierarchy(self):
        return self.driver.execute_script(grab_script)

    def capture(self):
        #parser = MyHTMLParser(self.driver)
        #parser.grab_page()
        #return parser.get_items()

        return hier_to_items(self.capture_hierarchy())

        # elements = driver.find_elements_by_xpath('//*')
        # for element in elements:
        #    parent = element.find_element_by_xpath("..")
        #    parents[element] = parent
        #    children[parent] = children.get(parent, []) + [element]

    def dump(self, basename):
        grab_ret = self.capture_hierarchy()
        try:
            hier = json.dumps(grab_ret)
        except:
            logger.exception("fail to serialize %r", grab_ret)
            raise

        try:
            with open(basename + ".hier", 'w') as f:
                f.write(hier)
            self.driver.get_screenshot_as_file(basename + ".png")
            with open(basename + ".url", 'w') as f:
                f.write(self.driver.current_url)
            with open(basename + ".htm", 'w') as f:
                f.write(self.driver.page_source)
        except:
            logger.exception("dump to %s error", basename)
            util.remove_pt(basename)

    def finish(self):
        self.close()
        if self.geckodriver is not None:
            self.geckodriver.kill()

    def close(self):
        self.driver.quit()

    def do_action(self, act, observer, env):
        if act.name in self.action_funcs:
            logger.debug("doing action %s %s", act.name, act.attr)
            return self.action_funcs[act.name](self, observer, env, act.attr)
        else:
            logger.warn("can't do unknown action %s %r", act.name, act.attr)
            return False

    def wait_idle(self):
        return True

    def grab(self, last_state):
        screenshot = tempfile.mktemp(suffix=".png", prefix='appmodel_scr')
        self.driver.get_screenshot_as_file(screenshot)

        if (last_state is not None and
                sense.same_snapshot(last_state.get('screenshot'), screenshot)):
            logger.info("screenshot match, reuse last result")
            return {
                'src': last_state.get('src'),
                'items': last_state.get('items'),
                'url': last_state.get('url'),
                'scr': screenshot,
            }

        items = self.capture()
        screen = {
            'src': self.driver.page_source,
            'items': items,
            'url': self.driver.current_url,
            'scr': screenshot,
        }
        return screen


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    import analyze
    import sys

    device = WebDevice()
    try:
        device.connect(sys.argv[1])
        device.goto("http://m.hm.com/us/product/69060?article=69060-B")
        #https://www.amazon.com")
        start_time = time.time()
        items = device.capture()
        end_time = time.time()
        print('used:', end_time - start_time)
        device.dump("/tmp/testdump")
    finally:
        device.close()

    util.printitems(items)
    tree = analyze.analyze_items(items)
    util.print_tree(tree)

    loaded = load("/tmp/testdump")
