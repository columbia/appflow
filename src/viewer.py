#!/usr/bin/env python3
import cairo
import os
import random
import time
from tesserocr import PyTessBaseAPI
from PIL import Image
import argparse
import logging

import analyze
import util
import config
import hidden
import elements
import tags
import locator

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk # noqa
from gi.repository import Gdk # noqa


WHITELIST = "abcedfghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789$().+&!?:"


class ViewerWindow(Gtk.Window):
    def __init__(self, filenames, kind, show, ml):
        Gtk.Window.__init__(self)
        self.ptx = 0
        self.pty = 0
        self.focus_id = -1
        self.file_idx = 0
        self.kind = kind
        self.show_hidden = show
        self.ml = ml
        self.screen_hint = ''
        self.in_hint_screen = False
        self.colors = {}
        self.memory = {}
        self.elem_models = {}
        self.filenames = filenames
        self.tesapi = PyTessBaseAPI(lang='eng')
        self.tesapi.SetVariable("tessedit_char_whitelist", WHITELIST)
        self.init_ui()
        self.load()

    def init_ui(self):
        self.connect("delete-event", Gtk.main_quit)

        darea = Gtk.DrawingArea()
        darea.connect("draw", self.on_draw)
        darea.connect("motion-notify-event", self.move_over)
        darea.connect("button-release-event", self.click_evt)
        darea.connect("scroll-event", self.scroll_evt)
        darea.connect("key-release-event", self.key_evt)
        darea.set_events(Gdk.EventMask.POINTER_MOTION_MASK |
                         Gdk.EventMask.BUTTON_RELEASE_MASK |
                         Gdk.EventMask.BUTTON_PRESS_MASK |
                         Gdk.EventMask.SCROLL_MASK |
                         Gdk.EventMask.KEY_PRESS_MASK |
                         Gdk.EventMask.KEY_RELEASE_MASK)
        darea.set_can_focus(True)
        self.add(darea)

        self.show_all()

    def load(self, prev=False):
        if self.file_idx == len(self.filenames):
            Gtk.main_quit()
            return
        if prev:
            self.file_idx -= 2
        filename = self.filenames[self.file_idx]
        (self.app, self.scr) = util.get_aux_info(filename)
        if self.app not in self.memory:
            self.memory[self.app] = {}
        self.set_title(filename)
        self.file_idx += 1
        print("Loading %s" % filename)
        self.pngfile = os.path.splitext(filename)[0] + '.png'
        self.descname = os.path.splitext(filename)[0] + '.%s.txt' % self.kind

        starttime = time.time()
        self.tree = analyze.load_tree(filename)
        hidden.find_hidden_ocr(self.tree)
        hidden.mark_children_hidden_ocr(self.tree)
        util.print_tree(self.tree, show_hidden=self.show_hidden)

        if self.ml:
            self.get_ml_rets()
        else:
            self.load_desc()

        endtime = time.time()
        print("Load time: %.3fs" % (endtime - starttime))

        self.focus_id = -1
        self.colors = {}
        self.ptx = self.pty = 0

        self.img = cairo.ImageSurface.create_from_png(self.pngfile)
        print('Image:', self.img.get_width(), self.img.get_height())

        root_item_id = min(self.tree)
        root_node = self.tree[root_item_id]
        print('Root node:', root_node['width'], root_node['height'])
        self.scale = 1.0 * self.img.get_width() / config.width
        #self.scale = analyze.find_closest(self.scale, analyze.SCALE_RATIOS)
        print('Scale:', '%.3f' % self.scale, '->', '%.3f' % self.scale)

        self.resize(self.img.get_width(), self.img.get_height())

        self.mark_depth(self.tree)

        for item_id in self.tree:
            color_r = random.random() / 2
            color_g = random.random() / 2
            color_b = random.random() / 2

            self.colors[item_id] = (color_r, color_g, color_b)

        imgocr = Image.open(self.pngfile)
        self.imgwidth = imgocr.width
        self.imgheight = imgocr.height
        #imgocr2 = imgocr.convert("RGB").resize(
        #    (imgocr.width * OCR_RATIO, imgocr.height * OCR_RATIO))
        self.tesapi.SetImage(imgocr)
        self.tesapi.SetSourceResolution(config.ocr_resolution)

        self.dump_memory()

    def remember(self, node, desc):
        nodeid = node['id']
        if not node['id']:
            return

        if node['id'] in self.memory[self.app]:
            if desc != self.memory[self.app][nodeid]:
                # multiple!
                self.memory[self.app][nodeid] = 'MUL'
        else:
            self.memory[self.app][node['id']] = desc

    def forget(self, node):
        if node['id'] in self.memory[self.app]:
            del self.memory[self.app][node['id']]

    def get_elem_model(self, app):
        elem_clas = elements.getmodel("../model/", "../guis/", app, "../guis-extra/",
                                      config.extra_element_scrs)
        self.elem_models[app] = elem_clas

    def get_ml_rets(self):
        if self.app not in self.elem_models:
            self.get_elem_model(self.app)

        guess_descs = {}
        guess_items = {} # type: Dict[str, List[int]]
        guess_score = {}
        elem_clas = self.elem_models[self.app]
        elem_clas.set_imgfile(self.pngfile)
        treeinfo = analyze.collect_treeinfo(self.tree)
        for itemid in self.tree:
            (guess_element, score) = elem_clas.classify(self.scr, self.tree, itemid,
                                                        None, treeinfo)
            if guess_element != 'NONE':
                if tags.single(guess_element, self.scr) and guess_element in guess_items:
                    old_item = guess_items[guess_element][0]
                    if guess_score[old_item] < score:
                        guess_items[guess_element] = [itemid]
                        guess_score[itemid] = score
                        del guess_descs[old_item]
                        guess_descs[itemid] = guess_element
                else:
                    guess_descs[itemid] = guess_element
                    guess_score[itemid] = score
                    guess_items[guess_element] = (guess_items.get(guess_element, []) +
                                                  [itemid])
        for nodeid in guess_descs:
            self.tree[nodeid]['label'] = guess_descs[nodeid]

    def load_desc(self):
        if os.path.exists(self.descname):
            with open(self.descname) as inf:
                for line in inf.read().split('\n'):
                    if not line:
                        continue
                    (item_id, desc) = line.split(' ', 1)
                    item_id = int(item_id)
                    found = False
                    for nodeid in self.tree:
                        node = self.tree[nodeid]
                        if item_id in node['raw']:
                            if 'label' in node:
                                node['label'] += ' ' + desc
                            else:
                                node['label'] = desc
                            print(nodeid, '(', item_id, ')', '->', desc)

                            self.remember(node, desc)

                            found = True
                            break
                    if not found:
                        print("WARNING: %s (%s) is missing!" % (item_id, desc))

    def mark_depth(self, tree):
        for item_id in tree:
            node = tree[item_id]
            if 'depth' in node:
                continue
            self.mark_depth_node(tree, item_id, 0)

    def mark_depth_node(self, tree, node_id, depth):
        node = tree[node_id]
        node['depth'] = depth
        node['descs'] = []
        for child in node['children']:
            descs = self.mark_depth_node(tree, child, depth + 1)
            node['descs'] += descs

        return node['descs'] + [node_id]

    def get_node_info(self, node):
        (x, y, width, height, depth) = (node['x'], node['y'], node['width'],
                                        node['height'], node['depth'])
        x *= self.scale
        y *= self.scale
        width *= self.scale
        height *= self.scale

        width = min(width, self.imgwidth)
        height = min(height, self.imgheight)

        if x < 0:
            width += x
            x = 0

        if y < 0:
            height += y
            y = 0

        return (x, y, width, height, depth)

    def find_containing_widget(self, px, py):
        max_depth = 0
        max_id = -1

        for item_id in self.tree:
            node = self.tree[item_id]
            if self.ignore_node(node):
                continue
            if self.inside(node, px, py):
                if node['depth'] > max_depth:
                    max_depth = node['depth']
                    max_id = item_id

        return max_id

    def inside(self, node, px, py):
        (x, y, width, height, depth) = self.get_node_info(node)
        return x <= px and x + width >= px and y <= py and y + height >= py

    def ignore_node(self, node):
        if node['class'].upper() == 'OPTION':
            return True
        if node.get('visible', '') == 'hidden':
            return True
        return False

    def on_draw(self, wid, ctx):
        ctx.select_font_face("Arial", cairo.FONT_SLANT_NORMAL,
                             cairo.FONT_WEIGHT_BOLD)

        ctx.set_source_surface(self.img, 0, 0)
        ctx.paint()

        ctx.set_font_size(20)
        ctx.set_line_width(5)
        ctx.set_source_rgb(1.0, 0.0, 0.0)

        max_click_id = -1
        max_click_depth = 0

        max_id = self.find_containing_widget(self.ptx, self.pty)

        for item_id in self.tree:
            node = self.tree[item_id]
            depth = node['depth']
            if max_id in node['descs'] and node['click']:
                if depth > max_click_depth:
                    max_click_depth = depth
                    max_click_id = item_id

        for item_id in self.tree:
            node = self.tree[item_id]
            if self.ignore_node(node):
                continue

            if item_id == max_id:
                region_mode = False
            else:
                region_mode = True

            (x, y, width, height, depth) = self.get_node_info(node)

            if not self.inside(node, self.ptx, self.pty):
                continue

            self.show_widget(ctx, item_id, not region_mode, not region_mode)

        if max_click_id != -1 and max_click_id != max_id:
            self.show_widget(ctx, max_click_id, False, True)

        if self.focus_id >= 0:
            self.show_widget(ctx, self.focus_id, True, True, (1, 0, 0))

        for itemid in self.tree:
            node = self.tree[itemid]
            if 'label' in node:
                if itemid == self.focus_id:
                    color = (0, 1, 0)
                else:
                    color = (0, 0, 1)
                self.show_widget(ctx, itemid, True, False, (0, 0, 1))
                self.show_desc(ctx, node, color)

        #s.write_to_png('test.png')
        #os.system("%s %s" % (config.picviewer_path, 'test.png'))
        #report_time(start_time, "displayed")

    def move_sibling(self, to_next):
        leaf_list = []
        any_list = []
        for itemid in self.tree:
            node = self.tree[itemid]
            if not self.inside(node, self.clickx, self.clicky):
                continue

            if len(node['children']) == 0:
                leaf_list.append(itemid)
            any_list.append(itemid)

        for i in range(len(leaf_list)):
            if leaf_list[i] == self.focus_id:
                if to_next:
                    idx = (i + 1) % len(leaf_list)
                else:
                    idx = (i - 1) % len(leaf_list)
                self.focus_id = leaf_list[idx]
                return

        if len(leaf_list) == 0:
            for i in range(len(any_list)):
                if any_list[i] == self.focus_id:
                    if to_next:
                        idx = (i + 1) % len(any_list)
                    else:
                        idx = (i - 1) % len(any_list)
                    self.focus_id = any_list[idx]
                    return
            self.focus_id = any_list[0]
        else:
            self.focus_id = leaf_list[0]

    def show_widget(self, ctx, item_id, fill, show_text, colors=None):
        node = self.tree[item_id]

        (x, y, width, height, depth) = self.get_node_info(node)

        if colors is None:
            color_r = self.colors[item_id][0]
            color_g = self.colors[item_id][1]
            color_b = self.colors[item_id][2]
        else:
            (color_r, color_g, color_b) = colors

        ctx.rectangle(x, y, width, height)
        if fill:
            ctx.set_source_rgba(color_r, color_g, color_b, 0.3)
            ctx.fill()
        else:
            ctx.set_source_rgba(color_r, color_g, color_b, 1)
            ctx.set_line_width(5)
            ctx.stroke()

        if show_text:
            max_char = int(width / ctx.text_extents("a")[2])
            text = str(item_id)
            if node['click']:
                text = 'C' + text
            if node['text']:
                text = text + ':' + node['text'][:(max_char - 5)]
            elif node['id']:
                text += '#' + node['id'][:(max_char - 5)]

            self.show_text(ctx, x + width / 2, y + height / 2, text, color_r, color_g,
                           color_b)

    def show_desc(self, ctx, node, color=(0, 0, 1)):
        desc = node['label']
        (x, y, width, height, depth) = self.get_node_info(node)
        self.show_text(ctx, x + width / 2, y + height / 2, desc,
                       color[0], color[1], color[2])

    def show_text(self, ctx, x, y, text, color_r, color_g, color_b):
        x_bearing, y_bearing, text_width, text_height = ctx.text_extents(text)[:4]

        ctx.move_to(x - text_width / 2, y + text_height / 2)
        ctx.set_source_rgba(1, 1, 1, 1)
        ctx.set_line_width(5)
        ctx.text_path(text)
        ctx.stroke()

        ctx.move_to(x - text_width / 2, y + text_height / 2)
        ctx.set_source_rgba(color_r, color_g, color_b, 1)
        ctx.text_path(text)
        ctx.fill()

    def move_over(self, widget, evt):
        self.ptx = evt.x
        self.pty = evt.y
        self.queue_draw()

    def click_evt(self, widget, evt):
        if self.in_hint_screen:
            self.process_screen_hint_click(evt)
            return

        if evt.button == 3:
            self.focus_id = -1
        else:
            self.clickx = evt.x
            self.clicky = evt.y
            self.focus_id = self.find_containing_widget(evt.x, evt.y)

        self.queue_draw()

    def scroll_evt(self, widget, evt):
        if self.focus_id == -1:
            return

        scroll_up = evt.direction == Gdk.ScrollDirection.UP
        if scroll_up:
            self.focus_id = self.find_parent_widget(self.focus_id)
        else:
            self.focus_id = self.find_child_widget(self.focus_id)

        self.queue_draw()

    def find_parent_widget(self, wid):
        for itemid in self.tree:
            node = self.tree[itemid]
            if self.ignore_node(node):
                continue
            if wid in node['children']:
                return itemid
        return wid

    def find_child_widget(self, wid):
        for itemid in self.tree[wid]['children']:
            node = self.tree[itemid]
            if self.ignore_node(node):
                continue
            if self.inside(node, self.clickx, self.clicky):
                return itemid
        return wid

    def mark_direct(self):
        enter = self.get_text('Please enter id_label', 'format: <id> <label>')
        if enter is None:
            return
        if ' ' in enter:
            nodeid, label = enter.split(' ')
        else:
            nodeid = enter
            label = ''
        nodeid = int(nodeid)
        if nodeid not in self.tree:
            print('missing node', nodeid)
            return
        node = self.tree[nodeid]

        self.mark_node(node, label)

    def mark_focused(self):
        if self.focus_id < 0:
            return
        node = self.tree[self.focus_id]
        label = self.get_text('Please enter label',
                              'label for %s: %s (%s) #%s' % (self.focus_id, node['text'],
                                                             node['desc'], node['id']))
        if label is None:
            return

        if self.ml:
            if label == '':
                if 'label' not in self.tree[self.focus_id]:
                    return

                self.generate_negative_hint(self.tree[self.focus_id]['label'])
                del self.tree[self.focus_id]['label']
            else:
                self.generate_hint_for_widget(self.focus_id, label)
                self.add_label(node, label)
        else:
            self.mark_node(node, label)

    def generate_hint_for_widget(self, nodeid, label):
        return self.generate_hint(label, locator.get_locator(self.tree, nodeid))

    def generate_negative_hint(self, label):
        return self.generate_hint(label, 'notexist')

    def generate_hint(self, label, hint):
        print("@%s.%s %s" % (self.scr, label, hint))

    def mark_node(self, node, label):
        if label == '':
            if 'label' in node:
                del node['label']
                self.forget(node)
        else:
            self.add_label(node, label)
            self.remember(node, label)

        self.save_labels()

    def ocr_text(self):
        node = self.tree[self.focus_id]
        (x, y, width, height, _) = self.get_node_info(node)
        print(x, y, width, height)
        x = max(x - 1, 0)
        y = max(y - 1, 0)
        width = min(width + 2, self.imgwidth)
        height = min(height + 2, self.imgheight)
        #self.tesapi.SetRectangle(x * OCR_RATIO, y * OCR_RATIO,
        #                         width * OCR_RATIO, height * OCR_RATIO)
        self.tesapi.SetRectangle(x, y, width, height)
        print("OCR ret:", self.tesapi.GetUTF8Text())

        x = min(x + width * 0.05, self.imgwidth)
        y = min(y + height * 0.05, self.imgheight)
        width *= 0.9
        height *= 0.9
        self.tesapi.SetRectangle(x, y, width, height)
        print("OCR ret:", self.tesapi.GetUTF8Text())

    def save_region(self):
        if self.focus_id == -1:
            return
        node = self.tree[self.focus_id]
        (x, y, width, height, _) = self.get_node_info(node)
        x = max(x - 1, 0)
        y = max(y - 1, 0)
        width = min(width + 2, self.imgwidth)
        height = min(height + 2, self.imgheight)

        regimg = cairo.ImageSurface(cairo.FORMAT_RGB24, int(width), int(height))
        ctx = cairo.Context(regimg)
        ctx.set_source_surface(self.img, -x, -y)
        ctx.paint()

        regimg.write_to_png("/tmp/region.png")

    def dump_memory(self):
        for _id in self.memory[self.app]:
            print('MEM %s -> %s' % (_id, self.memory[self.app][_id]))

    def add_label(self, node, desc):
        print('%s -> %s' % (util.describe_node(node, short=True), desc))
        node['label'] = desc

    def auto_label(self):
        for nodeid in self.tree:
            node = self.tree[nodeid]
            if 'label' not in node and node['id'] in self.memory[self.app]:
                if self.memory[self.app][node['id']] != 'MUL':
                    self.add_label(node, self.memory[self.app][node['id']])
                else:
                    print('skip MUL id: %s' % node['id'])
        self.save_labels()

    def remove_all(self):
        for nodeid in self.tree:
            node = self.tree[nodeid]
            if 'label' in node:
                del node['label']

    def process_screen_hint_click(self, evt):
        click_id = self.find_containing_widget(evt.x, evt.y)
        if click_id == -1:
            print('Invalid widget selected')
            return

        hint = locator.get_locator(self.tree, click_id)
        if hint is None:
            print('Cannot generate hint for this widget')
            return

        hint = str(hint)
        if evt.button == 3:
            # negate
            hint = 'not ' + hint

        print('Widget hint: "%s"' % hint)
        self.add_screen_hint(hint)

    def add_screen_hint(self, hint):
        if self.screen_hint == '':
            self.screen_hint = hint
        else:
            self.screen_hint += ' && ' + hint

    def hint_screen(self):
        if not self.in_hint_screen:
            label = self.get_text('Please enter screen name', 'screen name like "signin"')
            if label is None:
                return
            self.screen_hint_label = label

            self.in_hint_screen = True
            self.screen_hint = ''
        else:
            self.in_hint_screen = False
            print("%%%s %s" % (self.screen_hint_label, self.screen_hint))

    def key_evt(self, widget, evt):
        if evt.keyval == Gdk.KEY_space:
            self.mark_focused()
        elif evt.keyval == Gdk.KEY_Tab:
            self.load()
        elif evt.keyval == Gdk.KEY_Left:
            self.move_sibling(to_next=True)
        elif evt.keyval == Gdk.KEY_Right:
            self.move_sibling(to_next=False)
        elif evt.keyval == Gdk.KEY_v:
            self.ocr_text()
        elif evt.keyval == Gdk.KEY_a:
            self.auto_label()
        elif evt.keyval == Gdk.KEY_p:
            self.load(prev=True)
        elif evt.keyval == Gdk.KEY_l:
            self.mark_direct()
        elif evt.keyval == Gdk.KEY_r:
            self.remove_all()
        elif evt.keyval == Gdk.KEY_s:
            self.save_region()
        elif evt.keyval == Gdk.KEY_x:
            self.hint_screen()
        self.queue_draw()

    def save_labels(self):
        with open(self.descname, 'w') as outf:
            for itemid in sorted(self.tree):
                node = self.tree[itemid]
                if 'label' in node:
                    outf.write("%s %s\n" % (itemid, node['label']))

    def get_text(self, title, prompt):
        #base this on a message dialog
        dialog = Gtk.MessageDialog(self, 0, Gtk.MessageType.QUESTION,
                                   Gtk.ButtonsType.OK_CANCEL, title)
        dialog.format_secondary_text(prompt)
        #create the text input field
        entry = Gtk.Entry()
        #allow the user to press enter to do ok
        entry.connect("activate", lambda entry: dialog.response(Gtk.ResponseType.OK))
        #create a horizontal box to pack the entry and a label
        hbox = Gtk.HBox()
        hbox.pack_start(Gtk.Label("Label:"), False, 5, 5)
        hbox.pack_end(entry, True, 0, 0)
        #add it and show it
        dialog.vbox.pack_end(hbox, True, True, 0)
        dialog.show_all()
        #go go go
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            text = entry.get_text()
        else:
            text = None
        dialog.destroy()
        return text


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Classifier")
    parser.add_argument('--kind', help='kind of tag', default='desc')
    parser.add_argument('--show', help='show hidden items', default=False,
                        action='store_const', const=True)
    parser.add_argument('--ml', help='show ml results', default=False,
                        action='store_const', const=True)
    parser.add_argument('file', help='stat file', nargs='*')
    args = parser.parse_args()

    tags.load("../etc/tags.txt")
    win = ViewerWindow(args.file, args.kind, args.show, args.ml)
    Gtk.main()
