#!/usr/bin/env python3

import argparse
import logging
import os

import analyze
import util
import hidden


logger = logging.getLogger('dumptree')


class TreeDumper(object):
    def __init__(self, files, hide, print_tree, show, nofill):
        self.files = files
        self.hide = hide
        self.print_tree = print_tree
        self.show = show
        self.nofill = nofill
        self.hidden_cnt = self.total_cnt = 0
        self.hidden_app = {}
        self.total_app = {}

    def dump_tree(self, filename):
        tree = analyze.load_tree(filename)
        app = os.path.basename(filename).split('_')[0]
        if self.hide:
            hidden.find_hidden_ocr(tree)
            if not self.nofill:
                hidden.mark_children_hidden_ocr(tree)
            for nodeid in tree:
                node = tree[nodeid]
                if node['visible'] == 'hidden':
                    self.hidden_cnt += 1
                    self.hidden_app[app] = self.hidden_app.get(app, 0) + 1
                self.total_cnt += 1
                self.total_app[app] = self.total_app.get(app, 0) + 1
                if (node['regs'] or node['tags']) and node['visible'] == 'hidden':
                    logger.error("ERROR!: INVISIBLE %s %d %s", filename, nodeid,
                                 node['regs'][0] if node['regs'] else node['tags'])
        if self.print_tree or self.show:
            util.print_tree(tree, show_hidden=self.show)

    def dump(self):
        for filename in self.files:
            self.dump_tree(filename)
            if (self.print_tree or self.show) and len(self.files) > 1:
                input(filename)

        logger.info("Hidden/Total: %d/%d %.3f", self.hidden_cnt, self.total_cnt,
                    1.0 * self.hidden_cnt / self.total_cnt)
        for app in self.total_app:
            hidden = self.hidden_app.get(app, 0)
            logger.info("%s: %d/%d %.3f", app, hidden, self.total_app[app],
                        1.0 * hidden / self.total_app[app])


def main():
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Dump tree")
    parser.add_argument('--nohide', help='no hidden removal',
                        default=False, action='store_const', const=True)
    parser.add_argument('--print', help='print tree',
                        default=False, action='store_const', const=True)
    parser.add_argument('--show', help='show hidden',
                        default=False, action='store_const', const=True)
    parser.add_argument('--nofill', help='do not fill children',
                        default=False, action='store_const', const=True)
    parser.add_argument('file', help='file to analyze', nargs='+')
    args = parser.parse_args()

    TreeDumper(args.file, not args.nohide, args.print, args.show, args.nofill).dump()


if __name__ == "__main__":
    main()
