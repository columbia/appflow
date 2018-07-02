#!/usr/bin/env python3

import logging
import time
import copy
import shutil

import classify
import elements
import state
import sense
import analyze
import util
import device
import tags
import appdb
import value
import perfmon
import config
import webview
import hidden

logger = logging.getLogger("observer")

LAUNCHER_APP = 'com.android.launcher3'


def is_sys_screen(screen):
    return screen.startswith('sys_') or screen.startswith('app_')


class Observer(object):
    def __init__(self, errpath=None):
        self.clas = None
        self.element_clas = None
        self.appname = None
        self.app = None
        self.err_cap_path = errpath
        self.clas_stat = {}
        self.tlib = None
        self.history = []
        self.history_act = ''
        self.last_state = None
        self.last_state_screen = None

    def load(self, modelpath, guispath, extrapath, extrascr, extraelemscr):
        if self.appname:
            logger.info("obtain models for %s", self.appname)
        else:
            logger.warning("obtain general models. unrealistic")
        self.clas = classify.getmodel(modelpath, guispath, self.appname, extrapath,
                                      extrascr)
        self.element_clas = elements.getmodel(modelpath, guispath, self.appname,
                                              extrapath, extraelemscr)
        self.guispath = guispath
        self.last_state = None

    def set_app(self, appname):
        self.appname = appname
        self.app = appdb.get_app(appname)

    @perfmon.op("observer", "find_element", True)
    def find_elements(self, state, element):
        tree = state.get('tree')
        guess_scr = state.get('screen')
        imgdata = state.get('screen_img')
        rets = []
        treeinfo = analyze.collect_treeinfo(tree)
        self.element_clas.set_page(imgdata)
        for itemid in tree:
            if analyze.node_filtered(tree, itemid):
                continue
#          print('checking', itemid, guess_scr, element, util.describe_node(tree[itemid]))
            (guess_element, score) = self.element_clas.classify(guess_scr, tree, itemid,
                                                                imgdata, treeinfo)
            if guess_element == element:
                rets.append([score, itemid])
                #if best_score is None or score > best_score:
                #    best_score = score
                #    best_itemid = itemid

        rets.sort(key=lambda entry: entry[0], reverse=True)
        return list(map(lambda entry: entry[1], rets))

    def verify_screen_tag(self, state, screen_tag):
        if screen_tag in tags.required_tags:
            for required_tag in tags.required_tags[screen_tag]:
                # print('verifying %s' % required_tag)
                if self.find_elements(state, required_tag) == []:
                    return False
        return True

    def update_state(self, dev, curr_state, no_img=False):
        gui_state = self.grab_state(dev, no_img=no_img)
        curr_state.merge(gui_state)

    @perfmon.op("observer", "grab_state", True)
    def grab_state(self, dev, no_verify=False, no_print=False, no_img=False,
                   known_scr=None) -> state.State:
        for retry in range(config.GRAB_RETRYCOUNT):
            st = self.grab_state_once(dev, no_verify, no_print, no_img, known_scr)
            if st is not None:
                return st
            time.sleep(0.5)
        logger.error("retry exhausted, cannot grab")
        return None

    def grab_web(self, dev, no_img):
        #screen = None
        #if self.last_state is not None and (not self.last_state.get('noimg', False) or
        #                                    no_img):
        #    screen = dev.grab(no_img=True)
        #    if screen['src'] == self.last_state.get('src'):
        #        logger.info("reuse last screen")
        #        return copy.deepcopy(self.last_state)

        #if screen is None or not no_img:
        screen = dev.grab(self.last_state)

        if (self.last_state is not None and
                sense.same_snapshot(self.last_state.get('screenshot'), screen['scr'])):
            logger.debug("old screenshot: %s", self.last_state.get('screenshot'))
            logger.debug("new screenshot: %s", screen['scr'])
            logger.info("screenshot match, reuse last state")
            return [copy.deepcopy(self.last_state),
                    sense.restore_screen(self.last_state_screen)]

        actname = util.url_to_actname(screen['url'])
        logger.debug("screen grabbed")

        curr_state = state.State()
        curr_state.set('src', screen['src'])
        curr_state.set('noimg', no_img)
        items = screen['items']
        curr_url = screen['url']
        curr_state.set('url', curr_url)
        curr_state.set('act', actname)
        tree = analyze.analyze_items(items, history=self.history)
        curr_state.set('app', self.app)

        return (screen, actname, tree, items, curr_state)

    def grab_adb(self, dev, no_img):
        screen = None
        if (self.last_state is not None and
            self.last_state_screen is not None and
            (not self.last_state.get('noimg', False) or no_img)):
            screen = sense.grab_full(dev, no_img=True)
            if not screen['xml']:
                logger.warning("fail to grab screen info")
                return [None, None]

            if screen['xml'] == self.last_state.get('xml'):
                # not 'WebView' in screen['xml']):
                logger.info("reuse last screen")
                return [copy.deepcopy(self.last_state),
                        sense.restore_screen(self.last_state_screen)]

        if screen is None or not no_img:
            screen = sense.grab_full(dev, no_img=no_img)
            if not screen['xml']:
                logger.warning("fail to grab screen info")
                return [None, None]

        actname = screen['act']
        logger.debug("screen grabbed")

        curr_state = state.State()
        curr_state.set('xml', screen['xml'])
        curr_state.set('act', screen['act'])
        curr_state.set('noimg', no_img)
        items = analyze.parse_xml(screen['xml'])
        curr_url = ''
        if 'WebView' in screen['xml'] and config.GRAB_WEBVIEW:
            curr_url = self.grab_webview(items, dev)
        curr_state.set('url', curr_url)

        if 1 not in items:
            # not loaded yet, we should wait and retry
            logger.warning("got empty screen")
            return [None, None]

        tree = analyze.analyze_items(items, history=self.history)
        if len(tree) == 0:
            logger.warning("got empty tree")
            return [None, None]

        if 'WebView' in screen['xml'] and config.GRAB_WEBVIEW:
            self.annotate_webview(tree)

        if 'scr' in screen:
            hidden.add_ocrinfo(tree, screen['scr'])
            if config.observe_remove_hidden_ocr:
                hidden.find_hidden_ocr(tree)
                hidden.mark_children_hidden_ocr(tree)

        if config.GRAB_WEBVIEW and curr_url != '' and curr_url != 'about:blank':
            actname += util.url_to_actname(curr_url)

        if screen['act'] is None:
            logger.warning("fail to observe activity")
            curr_app = 'unknown'
        else:
            logger.info("at %s", screen['act'])
            curr_app = util.get_app(screen['act'])

        curr_state.set('app', curr_app)

        return (screen, actname, tree, items, curr_state)

    def grab_state_once(self, dev, no_verify, no_print, no_img, known_scr) -> state.State:
        if not no_img:
            logger.info("observing%s", " -img" if no_img else "")

        if dev.use_web_grab:
            grab_ret = self.grab_web(dev, no_img)
        else:
            grab_ret = self.grab_adb(dev, no_img)

        if len(grab_ret) == 2:
            reuse_state = grab_ret[0]
            if (reuse_state is None or reuse_state.get('guess_descs') is not None or
                not config.show_guess_tags or reuse_state.get('screen') == 'NONE'):
                return reuse_state
            else:
                if reuse_state is None:
                    return None
                tree = reuse_state.get('tree')
                items = reuse_state.get('items')
                curr_state = reuse_state
                actname = reuse_state.get('act')
                screen = copy.deepcopy(grab_ret[1])
        else:
            (screen, actname, tree, items, curr_state) = grab_ret

        self.record_tree(tree, items, actname)

        curr_state.set('items', items)
        curr_state.set('tree', tree)

        curr_app = curr_state.get('app')

        if 'scr' in screen:
            imgdata = sense.load_image(screen['scr'])
            curr_state.set('screen_img', imgdata)
            curr_state.set('screenshot', screen['scr'])

        guess_scr = None
        for (screen_name, obs) in value.get_screenobs().items():
            for ob in obs:
                if ob.check(curr_state):
                    if guess_scr is not None:
                        if guess_scr != screen_name:
                            if (guess_scr.startswith('sys_') and
                                    screen_name.startswith('app_')):
                                guess_scr = screen_name
                            else:
                                logger.warning("multiple sys screen match: %s, %s",
                                               guess_scr, screen_name)
                    else:
                        guess_scr = screen_name
            if guess_scr is not None:
                if guess_scr not in self.clas_stat:
                    self.clas_stat[guess_scr] = [0, 0]
                scrstat = self.clas_stat[guess_scr]
                logger.info("screen overrided to %s %d+ %d-", screen_name,
                            scrstat[0], scrstat[1])
                curr_state.set('screen', guess_scr)

                if (not no_img and self.err_cap_path is not None and
                        not is_sys_screen(guess_scr) and
                        scrstat[1] < config.ERR_CAP_LIMIT):
                    clas_scr = self.clas.classify(actname, screen['scr'],
                                                  tree)
                    if guess_scr != clas_scr:
                        # yes, it's incorrect
                        logger.info("screen misclassified as %s", clas_scr)
                        if config.dump_err_page:
                            sense.dump_page(dev, self.err_cap_path, self.appname,
                                            guess_scr, self.guispath)
                        scrstat[1] += 1
                    else:
                        scrstat[0] += 1
                break

        if (self.app is not None and curr_app != self.app and
                'browser' not in curr_app and 'com.google.android' not in curr_app):
            logger.info("switched to %s from %s", curr_app, self.app)

            if LAUNCHER_APP == curr_app:
                logger.info("at launcher")
                curr_state.set('exited', True)
                curr_state.set('screen', 'init')

            if curr_state.get('screen', '') == '':
                curr_state.set('screen', 'other')

            while self.tlib.handle_sys_screen(curr_state, dev, self):
                pass

            self.last_state = copy.deepcopy(curr_state)
            self.last_state_screen = sense.duplicate_screen(screen)
            return curr_state

        if guess_scr is not None:
            for count in range(config.HANDLE_SYS_LIMIT):
                if not no_print and is_sys_screen(guess_scr):
                    util.print_tree(tree, tagged_only=False, use_log=True)
                if not self.tlib.handle_sys_screen(curr_state, dev, self):
                    break
            guess_scr = curr_state.get('screen')
            tree = curr_state.get('tree')

        if self.clas is None:
            self.last_state = copy.deepcopy(curr_state)
            return curr_state

        if no_img:
            # no img: no screen/element classify
            self.last_state = copy.deepcopy(curr_state)
            return curr_state

        if guess_scr is None:
            if known_scr is not None:
                guess_scr = known_scr
            else:
                guess_scr = self.clas.classify(actname, screen['scr'], tree)
        curr_state.set('screen', guess_scr)

        if guess_scr != 'NONE':
            if not self.verify_screen_tag(curr_state, guess_scr) and not no_verify:
                # failed the tag verify!
                logger.info("the screen was considered %s, but it is not", guess_scr)
                guess_scr = 'NONE'
                curr_state.set('screen', guess_scr)

        if known_scr is None:
            logger.info("I think this is %s", guess_scr)
        else:
            logger.info("Using old knowledge %s", known_scr)

        if guess_scr != 'NONE' and config.show_guess_tags:
            # I know! (I think)
            self.classify_elements(curr_state, no_print)
        else:
            curr_state.set('guess_descs', None)
            if not no_print:
                util.print_tree(tree, tagged_only=False, use_log=True)
        self.last_state = copy.deepcopy(curr_state)
        self.last_state_screen = sense.duplicate_screen(screen)
        return curr_state

    def grab_webview(self, items, dev):
        self.webgrabber = webview.WebGrabber(self.app)
        pages = self.webgrabber.find_webviews(dev)
        if len(pages) == 0:
            return ''
        #self.webgrabber.clear_items(items)
        for page in pages:
            try:
                self.webgrabber.capture_webnodes(dev, page)
                self.webgrabber.annotate(items, page['title'], len(pages), page=page)
            except:
                logger.exception("capture webpage error. use uiautomator result")
            self.webgrabber.clear()
        # maybe incorrect
        return pages[0]['url']

    def annotate_webview(self, tree):
        #self.webgrabber.annotate_tree(tree)
        pass

    @perfmon.op("observer", "classify elements", True)
    def classify_elements(self, curr_state, no_print):
        guess_descs = {}
        guess_items = {} # type: Dict[str, List[int]]
        guess_score = {}
        tree = curr_state.get('tree')
        guess_scr = curr_state.get('screen')
        imgdata = curr_state.get('screen_img')
        treeinfo = analyze.collect_treeinfo(tree)
        self.element_clas.set_page(imgdata)
        points = {}
        for itemid in tree:
            (guess_element, score, point) = self.element_clas.classify(guess_scr, tree,
                                                                itemid, imgdata, treeinfo,
                                                                with_point=True)
            points[itemid] = point
            #elements.print_point(point)
            if guess_element != 'NONE':
                if tags.single(guess_element, guess_scr) and guess_element in guess_items:
                    old_item = guess_items[guess_element][0]
                    if guess_score[old_item] < score:
                        guess_items[guess_element] = [itemid]
                        guess_descs[itemid] = guess_element
                        guess_score[itemid] = score
                        del guess_descs[old_item]
                        del guess_score[old_item]
                else:
                    guess_descs[itemid] = guess_element
                    guess_score[itemid] = score
                    guess_items[guess_element] = (guess_items.get(guess_element, []) +
                                                  [itemid])
        if not no_print:
            util.print_tree(tree, guess_descs, scores=guess_score, tagged_only=False,
                            use_log=True)
        curr_state.set('guess_descs', guess_descs)
        curr_state.set('guess_score', guess_score)
        curr_state.set('guess_items', guess_items)

    def round_clear(self):
        sense.round_clear()

    def record_tree(self, tree, items, actname):
        if self.history_act == actname:
            for (olditems, oldtree) in self.history:
                if analyze.same_items(olditems, items):
                    logger.info("tree already seen")
                    return
        else:
            self.history = []
            self.history_act = actname

        logger.info("adding tree to history")
        self.history.append((copy.deepcopy(items), copy.deepcopy(tree)))

    def wait_idle(self, dev):
        ret = dev.wait_idle()
        for i in range(config.OB_EXTRA_WAIT_IDLE_LIMIT):
            st = self.grab_state(dev, no_img=True)
            items = st.get('items')
            for itemid in items:
                item = items[itemid]
                if item['class'] == 'ProgressBar':
                    time.sleep(0.2)
                    continue
            # good
            return ret
        return False

    def print_stat(self):
        logger.info("=== classification results ===")
        for scr in self.clas_stat:
            if is_sys_screen(scr):
                continue
            entry = self.clas_stat[scr]
            logger.info("screen %s: %d+ %d-" % (scr, entry[0], entry[1]))


class DevObserver(object):
    def __init__(self, dev, observer):
        self.dev = dev
        self.observer = observer

    def observe(self):
        return self.observer.grab_state(self.dev)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    tags.load("../etc/tags.txt")
    dev = device.Device()
    observer = Observer()
    observer.load("../model/", "../guis/", "../guis-extra/", None, None)
    print("%s" % observer.grab_state(dev))
