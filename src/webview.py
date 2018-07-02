#!/usr/bin/env python3

import sys
import urllib
import json
import websocket
import threading
import functools
import time
import logging
import html.parser

import config
import perfmon
import objdump
import util

logger = logging.getLogger("webview")
htmlparser = html.parser.HTMLParser()

fwd_port = 12345
filtered_names = set(['SCRIPT', '#comment', 'META', 'LINK', 'NOSCRIPT'])
unclickable_names = set(['LABEL', 'H3', 'H1', 'H2', 'P', 'LI'])
clickable_names = set(['A', 'INPUT', 'BUTTON'])
unclear_names = set(['A', 'DIV', 'SPAN', 'P'])
textlike_names = set(['LABEL', 'A', 'P', 'H1', 'H2', 'H3'])
notext_names = filtered_names.union(set(['#document', 'HTML', 'BODY', 'FORM', 'MAIN']))
get_rect_func = """function() {
    var x = this.getBoundingClientRect();
    return x.left + ' ' + x.top + ' ' + x.width + ' ' + x.height + ' ' + this.value;
}"""

def diff(a, b):
    return abs(a-b)

def clip(s1, w1, s2, w2):
    e1 = s1 + w1
    e2 = s2 + w2
    start = max(s1, s2)
    end = min(e1, e2)
    if start < end:
        return (start, end - start)
    else:
        return (0, 0)

def intersect(s1, e1, s2, e2):
    start = max(s1, s2)
    end = min(e1, e2)
    return start < end

class HTMLDumper(html.parser.HTMLParser):
    def __init__(self):
        html.parser.HTMLParser.__init__(self)
        self.filtered = False
        self.level = 0

    def handle_starttag(self, tag, attrs):
        if tag.upper() in filtered_names:
            self.filtered = True
            return
        attr = {}
        for pair in attrs:
            attr[pair[0]] = pair[1]
            print("%s<%s %s>" % (' ' * self.level,
                                 tag,
                                 ' '.join(list(
                                     map(lambda x: "%s='%s'" % (x, attr[x]), attr)))))
        self.level += 1

    def handle_endtag(self, tag):
        if tag.upper() in filtered_names:
            self.filtered = False
            return
        self.level -= 1
        print("%s</%s>" % (' ' * self.level, tag))

    def handle_data(self, data):
        if self.filtered:
            return
        if data.strip():
            print(' ' * self.level, data.strip())

class WebGrabber(object):
    props = ["parents", "nodes", "scaling", "base_x", "base_y", "base_w", "base_h",
             "page", "html_w", "html_h"]
    def __init__(self, appname=None):
        self.handlers = {}
        self.req_id = 0
        self.ws = None
        self.nodes = {}
        self.parents = {}
        self.resolved = set()
        self.appname = appname
        self.pending = 0
        self.scaling = 1.0
        self.base_x = 0
        self.base_y = 0
        self.base_w = 10000
        self.base_h = 10000
        self.url = ''
        self.closed = True
        self.handler_exited = False
        self.method_handlers = {}
        for key in self.method_handlers_temp:
            self.method_handlers[key] = functools.partial(
                self.method_handlers_temp[key], self)

    def clear(self):
        self.nodes.clear()
        self.parents.clear()
        self.handlers.clear()
        self.resolved.clear()

    def create_req(self, method, params, handler=None):
        self.req_id += 1
        if handler is not None:
            self.handlers[self.req_id] = handler
        return json.dumps({'id': self.req_id, 'method': method, 'params': params})

    def send_req(self, method, params, handler=None):
        self.pending += 1
        self.ws.send(self.create_req(method, params, handler))

    def get_prop_reply(self, result):
        print(result)

    def call_func_reply(self, nodeid, result):
        if 'wasThrown' in result and result['wasThrown']:
            logger.warning("node: %s", self.nodes[nodeid])
            logger.warning("call func error: %s", result)
            return
        #print(result['result'])
    #    if result['result']['type'] != 'number':
    #        return
        val = result['result']['value']
        (x, y, width, height, value) = val.split(' ', 4)
        x = float(x)
        y = float(y)
        width = float(width)
        height = float(height)
        if value == 'undefined':
            value = ''
        view = self.nodes[nodeid]
        view['x'] = x
        view['y'] = y
        view['w'] = width
        view['h'] = height
        view['value'] = value

    def resolve_node_reply(self, nodeid, result):
        #print(result)
        obj = result['object']
        #ws.send(create_req('Runtime.getProperties', {'objectId': obj['objectId'],
        #                                             'accessorPropretiesOnly': True},
        #                   get_prop_reply))
        self.send_req('Runtime.callFunctionOn', {'objectId': obj['objectId'],
                                                 'functionDeclaration': get_rect_func},
                      functools.partial(self.call_func_reply, nodeid))

    def set_childnodes(self, params):
        #print(params)
        for node in params['nodes']:
            nodeid = node['nodeId']
            if nodeid in self.parents:
                if self.parents[nodeid] != params['parentId']:
                    logger.warning("parent mismatch! node=%d origpar=%d newpar=%d",
                                   nodeid, self.parents[nodeid], params['parentId'])
            else:
                self.parents[node['nodeId']] = params['parentId']
                if not params['parentId'] in self.nodes:
                    logger.warning("parent not resolved! node=%d parent=%d",
                                   nodeid, params['parentId'])
                    #self.resolve_node(params['parentId'])
            self.resolve_node(node)

    method_handlers_temp = {'DOM.setChildNodes': set_childnodes}

    def get_doc_reply(self, result):
        #print(result)
        self.resolve_node(result['root'])
        self.send_req('DOM.requestChildNodes', {'nodeId': result['root']['nodeId'],
                                                'depth': -1})
        self.send_req('DOM.getOuterHTML', {'nodeId': result['root']['nodeId']},
                      self.get_html_reply)

    def get_html_reply(self, result):
        self.html = result['outerHTML']

    def handler(self):
        while True:
            try:
                ret = json.loads(self.ws.recv())
                if 'id' in ret:
                    if ret['id'] in self.handlers:
                        if not 'result' in ret:
                            logger.warning("req %d no result: %s", ret['id'], ret)
                        else:
                            self.handlers[ret['id']](ret['result'])
                        del self.handlers[ret['id']]
                    self.pending -= 1
                if 'method' in ret:
                    if ret['method'] in self.method_handlers:
                        self.method_handlers[ret['method']](ret['params'])
            except:
                if not self.closed and self.pending > 0:
                    self.handler_exited = True
                    logger.exception("handler exit")
                break

    def resolve_node(self, node):
        nodeid = node['nodeId']
        self.nodes[nodeid] = node
        for child in self.children(nodeid):
            self.parents[child['nodeId']] = nodeid

        name = node['nodeName']
        if name in filtered_names:
            return

        if name == 'IFRAME':
            content_node = node['contentDocument']
            self.parents[content_node['nodeId']] = nodeid
            self.resolve_node(content_node)
            self.send_req('DOM.requestChildNodes', {'nodeId': content_node['nodeId'],
                                                    'depth': -1})

        if (name != '#text' and name != 'html' and name != '#document' and
            name != '#comment' and not nodeid in self.resolved):
            self.resolved.add(nodeid)
            self.send_req('DOM.resolveNode', {'nodeId': nodeid},
                          functools.partial(self.resolve_node_reply, nodeid))

        for child in self.children(nodeid):
            #print("resolving %d.%d" % (nodeid, child['nodeId']))
            self.resolve_node(child)

    def visible(self, viewid):
        view = self.nodes[viewid]

        if self.html_w == 0 or self.html_h == 0:
            # whatever...
            return True

        if 'x' in view:
            return (intersect(0, self.html_w, view['x'], view['x'] + view['w']) and
                    intersect(0, self.html_h, view['y'], view['y'] + view['h']))
        else:
            return False

    def print_node(self, nodeid, ignore_check=False):
        node = self.nodes[nodeid]
        name = node['nodeName']
        if name in filtered_names:
            if not ignore_check:
                return
        value = node['nodeValue']
#        if value == '':
#            value = node['value']
        #_type = node['nodeType']
        #lname = node['localName']
        if nodeid in self.parents:
            parent = self.parents[nodeid]
        else:
            parent = -1

        if 'x' in node:
            x = node['x'] * self.scaling + self.base_x
            y = node['y'] * self.scaling + self.base_y
            w = node['w'] * self.scaling
            h = node['h'] * self.scaling
        else:
            x = y = w = h = 0

        if x + w < 0 or y + h < 0:
            return

        props = node['props']
        text = self.collect_text(nodeid, depth=1)

        prop = ''
        if self.is_clickable(nodeid):
            prop += 'C'

        if 'id' in props:
            _id = '#' + props['id']
        else:
            _id = ''

        if 'class' in props:
            clz = ' '.join(map(lambda x: '.' + x, props['class'].split(' ')))
        else:
            clz = ''

        depth = self.get_depth(nodeid)

        #if name != '#text':
        if not self.valid_view(nodeid) and ignore_check:
            if not self.visible(nodeid):
                logger.info("invisible but displayed")
        if self.valid_view(nodeid) or ignore_check:
            print("%d %s %-6s %s %s %s %s P%d +%d+%d %dx%d [%s]" % (
                nodeid, ' ' * depth, name, text, _id, clz, value, parent, x, y, w, h, prop))

    def valid_view(self, viewid):
        if not viewid in self.nodes:
            return False
        view = self.nodes[viewid]
        if view['nodeName'] in filtered_names:
            return False
        if not 'x' in view:
            return False
        w = view['w']
        h = view['h']
        return w > 0.1 and h > 0.1 and self.visible(viewid)

    def calc_recurse_valid(self, viewid):
        if viewid in self.valid_views:
            return self.valid_views[viewid]
        is_valid = self.valid_view(viewid)
        for childid in self.nodes:
            if childid in self.parents and self.parents[childid] == viewid:
                is_valid = is_valid or self.calc_recurse_valid(childid)
        self.valid_views[viewid] = is_valid
        return is_valid

    def calc_valid(self):
        self.valid_views = {}
        for viewid in self.nodes:
            self.calc_recurse_valid(viewid)

    def get_depth(self, viewid):
        depth = 0
        while viewid in self.parents:
            depth += 1
            viewid = self.parents[viewid]
        return depth

    def calc_scale(self):
        for nodeid in sorted(self.nodes):
            node = self.nodes[nodeid]
            if node['nodeName'] == 'HTML':
                if not 'w' in node:
                    self.html_w = self.html_h = 0
                    return 2.625
                self.html_w = node['w']
                self.html_h = node['h']
                if node['w'] == 0:
                    # from dpi:
                    # 420 DPI / 160 facial DPI = 2.625
                    self.scale_w = 2.625
                else:
                    self.scale_w = 1.0 * self.base_w / node['w']
                    if abs(self.scale_w - 2.625) < 0.01:
                        self.scale_w = 2.625
                if node['h'] == 0:
                    self.scale_h = 2.625
                else:
                    # scale_h is not very useful
                    # it is the actual content height
                    # it can be much smaller than the full webview's h
                    self.scale_h = 1.0 * (1920 - self.base_y) / node['h']
                logger.debug("%dx%d +%d+%d %dx%d", self.html_w, self.html_h, self.base_x,
                             self.base_y, self.base_w, self.base_h)
                return self.scale_w
        return 1.0

    @perfmon.op("webview", "capture_pages")
    def find_webviews(self, dev):
        if self.appname is None:
            raise Exception("WebGrabber.find_webviews without appname")
        app_pid = util.get_pid(dev, self.appname)
        if app_pid is None:
            return []

        logger.info("forwarding tcp:%d to localabstract:webview_devtools_remote_%s" % (
            fwd_port, app_pid))
        dev.run_adb_cmd("forward", "tcp:%d localabstract:webview_devtools_remote_%s" % (
            fwd_port, app_pid))

        count = 0
        rets = []
        try:
            req = urllib.request.urlopen("http://127.0.0.1:%d/json" % fwd_port)
            ret = json.loads(req.read().decode('utf-8'))
        except:
            logger.warning("fail to connect to webview")
            return []
        for item in ret:
            try:
                desc = json.loads(item['description'])
            except:
                logger.exception("fail to parse description %s", item['description'])
                raise
            if not desc['attached']:
                continue
            count += 1
            base_x = desc['screenX']
            base_y = desc['screenY']
            if 'width' in desc:
                base_w = desc['width']
                base_h = desc['height']
            else:
                base_w = base_h = 0
            if 'empty' in desc:
                empty = desc['empty']
            else:
                empty = True
            logger.info("found %s %s", item['url'].split('?')[0], item['title'])
            url = item['url']
            ws_url = item['webSocketDebuggerUrl']
            title = item['title']

            rets.append({'base_x': base_x, 'base_y': base_y, 'base_w': base_w,
                         'base_h': base_h, 'url': url, 'ws_url': ws_url,
                         'title': title, 'empty': empty})
        logger.info("captured %d webviews", count)
        return rets

    def get_iframe_info(self, nodeid):
        node = self.nodes[nodeid]
        parentid = nodeid
        while parentid in self.parents:
            parentid = self.parents[parentid]
            parent = self.nodes[parentid]
            if parent['nodeName'] == 'IFRAME':
                dx = parent['x']
                dy = parent['y']
                scale = 1.0

                if node['nodeName'] == '#document' or node['nodeName'] == 'HTML':
                    return (scale, dx, dy)

                iframe_w = parent['w']
                #iframe_h = parent['h']

                htmlid = nodeid
                while htmlid in self.parents:
                    htmlid = self.parents[htmlid]
                    html = self.nodes[htmlid]
                    if not 'w' in html:
                        continue
                    html_w = html['w']
                    if html_w < 0.1:
                        continue
                    #html_h = html['h']
                    break


                scale = scale * iframe_w / html_w

                logger.debug('scale for %s: %s %s %s', nodeid, scale, dx, dy)
                return (scale, dx, dy)
        return (None, None, None)

    def fix_iframe_size(self):
        for nodeid in self.nodes:
            node = self.nodes[nodeid]
            if not 'x' in node:
                continue
            (scale, dx, dy) = self.get_iframe_info(nodeid)
            if scale is not None:
                node['x'] = dx + node['x'] * scale
                node['y'] = dy + node['y'] * scale
                node['w'] = node['w'] * scale
                node['h'] = node['h'] * scale
                logger.debug('scaled %s to %s %s %s %s',
                             nodeid, node['x'], node['y'], node['w'], node['h'])

    @perfmon.op("webview", "capture_nodes", showtime=True)
    def capture_webnodes(self, dev, page, print_nodes=False):
        self.closed = False
        self.page = page
        self.ws = websocket.WebSocket()
        try:
            self.ws.connect(page['ws_url'])
        except:
            logger.exception("fail to connect to websocket")
            return False

        self.handler_exited = False
        thr = threading.Thread(target=self.handler, daemon=True)
        thr.start()
        self.send_req('DOM.getDocument', {}, self.get_doc_reply)

        retry = config.WEBVIEW_GRAB_LIMIT
        while self.pending > 0 and retry > 0 and not self.handler_exited:
            retry -= 1
            time.sleep(0.1)

        self.closed = True
        self.ws.close()

        for nodeid in self.nodes:
            node = self.nodes[nodeid]
            if nodeid in self.parents:
                parent = self.parents[nodeid]
            else:
                parent = -1
            node['parent'] = parent

            #if node['nodeName'] == '#text' and parent != -1:
            #    self.nodes[parent]['text'] = node['nodeValue']

            prop = {}
            key = None
            if 'attributes' in node:
                attrs = node['attributes']
            else:
                attrs = []

            for item in attrs:
                if key is None:
                    key = item
                else:
                    prop[key] = item
                    key = None

            node['props'] = prop

        self.collect_children()

        self.fix_iframe_size()

        self.base_x = page['base_x']
        self.base_y = page['base_y']
        self.base_w = page['base_w']
        self.base_h = page['base_h']
        self.scaling = self.calc_scale()

        if print_nodes:
            HTMLDumper().feed(self.html)
            for nodeid in sorted(self.nodes):
                self.print_node(nodeid, ignore_check=False)

        title = htmlparser.unescape(page['title'])
        if title.startswith('http'):
            title = title.split('?')[0]
        logger.info("captured %d webnodes for %s", len(self.nodes), title)

        return True

    def is_webview_item(self, items, itemid):
        while 'parent' in items[itemid] and items[itemid]['parent'] != itemid:
            if 'WebView' in items[itemid]['class']:
                return True
            itemid = items[itemid]['parent']
        return False

    def best_match(self, item):
        bestmatch = None
        bestscore = None
        for viewid in self.nodes:
            view = self.nodes[viewid]

            score = self.calc_score(view, item)
            if bestscore is None or score < bestscore:
                bestscore = score
                bestmatch = viewid

        return bestmatch

    def convert_name(self, name, props):
        if name == 'IMG':
            return 'ImageView'
        if name == 'BUTTON':
            return 'Button'
        #if name in textlike_names:
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

    def convert_view(self, viewid, legacy_info):
        item = {}

        view = self.nodes[viewid]
        name = view['nodeName']
        value = view['nodeValue']
        if value == '' and 'value' in view:
            value = view['value']

        if 'x' in view:
            x = view['x']
            y = view['y']
            w = view['w']
            h = view['h']

            if self.html_w != 0:
                (x, w) = clip(x, w, 0, self.html_w)
            if self.html_h != 0:
                (y, h) = clip(y, h, 0, self.html_h)

            x = x * self.scaling + self.base_x
            y = y * self.scaling + self.base_y
            w = w * self.scaling
            h = h * self.scaling

            if x + w > self.base_x + self.base_w:
                logger.debug("extra width: %d+%d %d+%d %d %.3f %d %d", x, w, view['x'],
                             view['w'], self.html_w, self.scaling, self.base_w,
                             self.base_x)
                w = self.base_x + self.base_w - x

            if y + h > self.base_y + self.base_h:
                logger.debug("extra height: %d+%d %d+%d %d %.3f %d %d", y, h, view['y'],
                             view['h'], self.html_h, self.scaling, self.base_h,
                             self.base_y)
                h = self.base_y + self.base_h - y
        else:
            x = y = w = h = 0

        props = view['props']
        text = self.collect_text(viewid, depth=1)
        if text == '':
            text = value

        if name in notext_names:
            text = ''
            value = ''

        desc = value
        # alt text for image
        if 'alt' in props and props['alt']:
            desc = props['alt']
        # hint for text box
        if 'placeholder' in props and props['placeholder']:
            desc = props['placeholder']

        classes = props['class'].split(' ') if 'class' in props else []

        if 'id' in props:
            _id = props['id']
        elif len(classes) > 0:
            _id = classes[0]
        else:
            _id = ''

        if 'type' in props:
            _type = props['type']
        else:
            _type = ''

        item['class'] = self.convert_name(name, props)
        item['text'] = text
        item['desc'] = desc
        item['x'] = int(x)
        item['y'] = int(y)
        item['width'] = int(w)
        item['height'] = int(h)
        item['id'] = _id
        item['classes'] = classes
        item['click'] = self.is_clickable(viewid)
        item['scroll'] = False
        item['selected'] = False
        item['password'] = 'type' in props and props['type'] == 'password'
        item['focused'] = False
        #item['childcount'] = 0
        item['children'] = []
        item['webview'] = True
        item['checkable'] = _type == 'checkbox' or _type == 'radio'

        if text.strip() in legacy_info:
            item['click'] = True

        return item

    def harvest_legacy_info_node(self, items, nodeid, info):
        node = items[nodeid]
        if node['click']:
            desc = node['desc'].strip()
            if desc:
                info[desc] = True
        for childid in node['children']:
            self.harvest_legacy_info_node(items, childid, info)
        return info

    def harvest_legacy_info(self, items, rootid):
        info = {}
        self.harvest_legacy_info_node(items, rootid, info)
        return info

    def fill_webview(self, items, rootid):
        legacy_info = self.harvest_legacy_info(items, rootid)
        self.del_subtree(items, rootid)
        rootitem = items[rootid]
        rootitem['children'] = []
        rootitem['childcount'] = 0
        rootitem['filled'] = True
        startid = max(items) + 100
        count = 0
        convert = {}

        self.calc_valid()
        for viewid in sorted(self.nodes):
            if self.valid_views[viewid]:
                if count == 0:
                    parentid = rootid
                else:
                    if viewid in self.parents:
                        viewpid = self.parents[viewid]
                        if not viewpid in self.nodes:
                            logger.error("parent not present! viewid=%d viewpid=%d",
                                         viewid, viewpid)
                            self.print_node(viewid, ignore_check=True)
                            continue
                        err = False
                        while not viewpid in convert:
                            if not viewpid in self.valid_views:
                                logger.error("parent not in valid! viewid=%d viewpid=%d",
                                            viewid, viewpid)
                                self.print_node(viewid, ignore_check=True)
                                err = True
                                break
                            logger.error("parent not converted! viewid=%d viewpid=%d %s",
                                         viewid, viewpid, self.valid_views[viewpid])
                            self.print_node(viewid, ignore_check=True)
                            viewpid = self.parents[viewpid]

                        if err:
                            continue

                        parentid = convert[viewpid]
                    else:
                        logger.error("parent missing! viewid=%d", viewid)
                        self.print_node(viewid, ignore_check=True)
                        continue
                logger.debug("parent: %d" % parentid)

                count += 1
                fillid = count + startid
                items[fillid] = self.convert_view(viewid, legacy_info)
                item = items[fillid]
                logger.debug("%d -> %d" % (fillid, viewid))
                convert[viewid] = fillid

                item['parent'] = parentid
                item['depth'] = self.get_depth(viewid) + rootitem['depth'] + 1
                if parentid != -1:
                    items[parentid]['children'].append(fillid)
                    #items[parentid]['childcount'] += 1
                    items[fillid]['childid'] = len(items[parentid]['children']) - 1
        logger.debug("filled %d nodes under %d", count, rootid)

    def del_subtree(self, items, itemid):
        for childid in items[itemid]['children']:
            self.del_subtree(items, childid)
            del items[childid]

    def clear_items(self, items):
        to_del = []
        for itemid in items:
            item = items[itemid]

            if (item['class'] == 'WebView' and item['children'] != [] and
                items[item['children'][0]]['class'] != 'WebView'):
                to_del.append(itemid)

        for itemid in to_del:
            self.del_subtree(items, itemid)
            items[itemid]['children'] = []
            #if 'childcount' in items[itemid]:
            #    items[itemid]['childcount'] -= 1

    def annotate(self, items, title, npages, page=None):
        title = htmlparser.unescape(title)

        if page is not None:
            if page['base_x'] >= config.width or page['base_y'] >= config.height:
                logger.info("page out of screen")
                return
            if page['empty']:
                logger.info("empty page")
                return

        webviews = []
        for itemid in items:
            if items[itemid]['class'] == 'WebView':
                if not (itemid + 1) in items or items[itemid + 1]['class'] != 'WebView':
                    webviews.append(itemid)

        for itemid in webviews:
            if (((len(webviews) == 1 and npages == 1) or
                 items[itemid]['desc'].strip() == title.strip()) and
                not items[itemid].get('filled', False)):
                logger.info('matched by title: %s', title.strip())
                self.fill_webview(items, itemid)
                return

            #self.annotate_item(item, bestmatch)

        if page is not None:
            base_x = page['base_x']
            base_y = page['base_y']
            base_w = page['base_w']
            base_h = page['base_h']
        else:
            base_x = self.base_x
            base_y = self.base_y
            base_w = self.base_w
            base_h = self.base_h

        for itemid in webviews:
            item = items[itemid]
            if (base_x == item['x'] and base_y == item['y'] and
                base_w == item['width'] and base_h >= item['height'] and
                not items[itemid].get('filled', False)):
                logger.info("matched by size %d,%d %dx%d for %s", base_x, base_y,
                            base_w, base_h, title.strip())
                self.fill_webview(items, itemid)
                return

        for itemid in webviews:
            item = items[itemid]
            if (base_x == item['x'] and base_y == item['y'] and
                base_w > 0 and base_h > 0 and
                not items[itemid].get('filled', False)):
                logger.warning("matched by last resort %d,%d for %s!", base_x, base_y,
                               title.strip())
                self.fill_webview(items, itemid)
                return

        for itemid in webviews:
            item = items[itemid]
            if (base_x == item['x'] and base_w == item['width'] and
                base_y <= item['y'] and base_h >= item['height'] and
                base_y + base_h >= item['y'] + item['height'] and
                not items[itemid].get('filled', False)):
                logger.warning("matched by last' resort %d,%d for %s!", base_x, base_y,
                               title.strip())
                self.fill_webview(items, itemid)
                return

        if page is not None:
            logger.warning("can't find corresponding webview item for %s", page)

    def annotate_tree(self, tree):
        #for nodeid in tree:
        #    node = tree[nodeid]
        #    if itemid in node['raw']:
        #        self.annotate_node(node, bestmatch)
        #        break
        return

    def calc_score(self, view, node):
        return (diff(view.get('x', 0) * self.scaling + self.base_x, node.get('x', 0)) *
                diff(view.get('y', 0) * self.scaling + self.base_y, node.get('y', 0)) *
                diff(view.get('w', 0) * self.scaling, node.get('width', 0)) *
                diff(view.get('h', 0) * self.scaling, node.get('height', 0)))

    def collect_text(self, viewid, depth=1):
        text = ''
        if not viewid in self.nodes:
            return text
        view = self.nodes[viewid]
        if 'text' in view:
            text = view['text']
        if view['nodeName'] == '#text' and 'nodeValue' in view and text == '':
            text = view['nodeValue']

        if depth > 0 or depth < 0:
            for child in self.children(viewid):
                text = (text + ' ' +
                        self.collect_text(child['nodeId'], depth - 1)).strip()
        return text

    def is_clickable(self, viewid):
        if not viewid in self.nodes:
            return False
        view = self.nodes[viewid]
        if 'props' in view and 'onclick' in view['props']:
            return True
        if view['nodeName'] in clickable_names:
            return True
        #if viewid in self.parents:
        #    if self.is_clickable(self.parents[viewid]):
        #        return True
        return False

    def has_img(self, viewid):
        view = self.nodes[viewid]
        if view['nodeName'] == 'IMG':
            return True
        if 'children' in view:
            for child in view['children']:
                if self.has_img(child['nodeId']):
                    return True
        return False

    def children(self, viewid):
        if not viewid in self.nodes:
            return []
        view = self.nodes[viewid]
        if 'children' in view:
            return view['children']
        elif 'contentDocument' in view:
            return [view['contentDocument']]
        else:
            return []

    def collect_children(self):
        childrenids = {}
        for viewid in self.nodes:
            if viewid in self.parents:
                viewpid = self.parents[viewid]
                childrenids[viewpid] = childrenids.get(viewpid, []) + [viewid]
        for viewid in self.nodes:
            self.nodes[viewid]['childrenids'] = childrenids.get(viewid, [])

    def annotate_node(self, node, viewid):
        view = self.nodes[viewid]
        node['webview'] = True
        if node['text'] == '':
            if len(node['children']) == 0:
                node['text'] = self.collect_text(viewid, -1)
            else:
                node['text'] = self.collect_text(viewid, 0)
        name = view['nodeName']
        node['webtag'] = name
        if 'props' in view:
            self.annotate_prop(node, view['props'])

        if name in unclickable_names:
            node['click'] = False
        if self.is_clickable(viewid):
            node['click'] = True

        if self.children(viewid) != [] and name in unclear_names:
            if self.has_img(viewid):
                name = 'ImageView'
            else:
                name = 'TextView'

        if node['class'] == 'View':
            node['class'] = name

    def annotate_prop(self, node, attrs):
        if 'id' in attrs and node['id'] == '':
            node['id'] = attrs['id']
        if 'class' in attrs:
            node['classes'] = attrs['class']
            if node['id'] == '':
                node['id'] = attrs['class']

    def annotate_item(self, item, viewid):
        view = self.nodes[viewid]
        item['webview'] = True
        if 'text' in view and item['text'] == '':
            item['text'] = view['text']
        if 'nodeValue' in view and item['text'] == '' and view['nodeName'] == '#text':
            item['text'] = view['nodeValue']
        if 'props' in view:
            self.annotate_item_prop(item, view['props'])

    def annotate_item_prop(self, item, attrs):
        if 'id' in attrs and item['id'] == '':
            item['id'] = attrs['id']
        if 'class' in attrs:
            item['classes'] = attrs['class']
            if item['id'] == '':
                item['id'] = attrs['class']

    def check_children(self):
        for viewid in self.nodes:
            if viewid in self.parents:
                found = False
                for child in self.children(self.parents[viewid]):
                    if child['nodeId'] == viewid:
                        found = True
                        break
                if not found:
                    logger.debug("MISSING child: %d is child of %d", viewid, self.parents[viewid])
                else:
                    logger.debug("OK")
            else:
                if viewid != min(self.nodes):
                    logger.error("missing parent! %d", viewid)

    def check_convert(self):
        startid = 0
        count = 0
        convert = {}

        legacy_info = {}
        self.calc_valid()
        for viewid in sorted(self.nodes):
            if self.valid_views[viewid]:
                count += 1
                fillid = count + startid
                self.convert_view(viewid, legacy_info)
                convert[viewid] = fillid

                if count != 1:
                    if viewid in self.parents:
                        viewpid = self.parents[viewid]
                        if not viewpid in self.nodes:
                            logger.error("ERROR! parent not available! %d -> %d?",
                                         viewid, viewpid)
                        if not viewpid in convert:
                            logger.error("ERROR! parent not converted! %d->%d %d?",
                                         viewid, fillid, viewpid)
                            logger.error("valid: %s %s", self.valid_views[viewid],
                                         self.valid_views[viewpid])
                    else:
                        logger.error("ERROR! parent missing!")

    def dump(self):
        dumper = objdump.ObjDumper(self.props)
        return dumper.dump(self)

    def load(self, s):
        dumper = objdump.ObjDumper(self.props)
        return dumper.load(self, s)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    import appdb
    appdb.collect_apps("../apks/")

    serial = sys.argv[1]
    app = sys.argv[2]
    appname = appdb.get_app(app)

    import device
    dev = device.Device(serial=serial, no_uimon=True)

    webgrabber = WebGrabber(appname)
    pages = webgrabber.find_webviews(dev)
    for page in pages:
        webgrabber.capture_webnodes(dev, page, print_nodes=True)
        webgrabber.check_convert()
        webgrabber.clear()
