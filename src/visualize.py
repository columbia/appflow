#!/usr/bin/env python3
import sys
import cairo
import re
import os
import random
import xml.etree.ElementTree as ET
import config

xmlfile = sys.argv[1]
pngfile = xmlfile.replace('.xml', '.png')
descfile = xmlfile.replace('.xml', '.desc.txt')

bound_re = re.compile("\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


def extract(node):
    attrib = node.attrib
    (x1, y1, x2, y2) = bound_re.match(attrib['bounds']).groups()
    x1 = int(x1)
    y1 = int(y1)
    x2 = int(x2)
    y2 = int(y2)
    width = x2 - x1
    height = y2 - y1
    return (x1, y1, width, height)


items = {}
max_depth = 0


def parse(node, depth, start_id):
    global max_depth
    if depth > max_depth:
        max_depth = depth
    if node.tag != 'hierarchy':
        (x, y, width, height) = extract(node)
        items[start_id] = (x, y, width, height, depth)

    start_id += 1

    for child in node:
        start_id = parse(child, depth + 1, start_id)

    return start_id


ret = {}


with open(descfile) as df:
    lines = df.read().split('\n')
    for line in lines:
        if ' ' not in line:
            continue
        (item_id, item_desc) = line.split(' ')
        ret[int(item_id)] = item_desc

with open(xmlfile) as xf:
    src = xf.read()

root = ET.fromstring(src)
parse(root, 0, 0)

s = cairo.ImageSurface.create_from_png(pngfile)
ctx = cairo.Context(s)
ctx.set_font_size(30)
ctx.set_line_width(5)
ctx.set_source_rgb(1.0, 0.0, 0.0)

for item_id in ret:
    (x, y, width, height, depth) = items[item_id]
    ctx.set_source_rgb(random.random() / 2, random.random() / 2, random.random() / 2)
    ctx.set_line_width((max_depth - depth) * 2 + 1)
    ctx.rectangle(x, y, width, height)
    ctx.stroke()
    ctx.move_to(x + 10, y + 30)
    ctx.show_text(ret[item_id])

s.write_to_png('test.png')
os.system("%s %s" % (config.picviewer_path, 'test.png'))
