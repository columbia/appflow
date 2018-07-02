from tesserocr import PyTessBaseAPI
from PIL import Image
import re

import config


def overlap(a, b):
    start = max(a[0], b[0])
    end = min(a[1], b[1])
    return start < end


def cover(a, b):
    return b[0] <= a[0] and b[1] >= a[1]


def overlap_node(a, b):
    return (overlap((a['x'], a['x'] + a['width']), (b['x'], b['x'] + b['width'])) and
            overlap((a['y'], a['y'] + a['height']), (b['y'], b['y'] + b['height'])))


def cover_node(a, b):
    return (cover((a['x'], a['x'] + a['width']), (b['x'], b['x'] + b['width'])) and
            cover((a['y'], a['y'] + a['height']), (b['y'], b['y'] + b['height'])))


def add_ocrinfo(tree, imgfile):
    imgpil = Image.open(imgfile)
    (orig_width, orig_height) = (imgpil.width, imgpil.height)

    #root_width = tree[min(tree)]['width']
    ratio = 1.0 * orig_width / config.width
    #imgpil = imgpil.convert("RGB").resize(
    #    (orig_width * OCR_RATIO, orig_height * OCR_RATIO))

    tesapi = PyTessBaseAPI(lang='eng')
    tesapi.SetImage(imgpil)
    tesapi.SetSourceResolution(config.ocr_resolution)

    for nodeid in tree:
        node = tree[nodeid]

        if node['children'] and node['text'] == '':
            node['ocr'] = ''
            continue

        x = max(node['x'] * ratio - 1, 0)
        y = max(node['y'] * ratio - 1, 0)
        x2 = min((node['x'] + node['width']) * ratio + 1, orig_width)
        y2 = min((node['y'] + node['height']) * ratio + 1, orig_height)
        width = int(x2 - x)
        height = int(y2 - y)

        if width > 3 and height > 3:
            #tesapi.SetRectangle(int(x * OCR_RATIO), int(y * OCR_RATIO),
            #                    int(width * OCR_RATIO), int(height * OCR_RATIO))
            #print(int(x), int(y), int(width), int(height), orig_width, orig_height)
            tesapi.SetRectangle(int(x), int(y), int(width), int(height))
            ocr_text = tesapi.GetUTF8Text().strip().replace('\n', ' ')
            if ocr_text.strip() == '':
                x = min(x + width * 0.05, orig_width)
                y = min(y + height * 0.05, orig_height)
                width *= 0.9
                height *= 0.9
                tesapi.SetRectangle(int(x), int(y), int(width), int(height))
                ocr_text = tesapi.GetUTF8Text().strip().replace('\n', ' ')

        else:
            ocr_text = ''

        node['ocr'] = ocr_text


ocr_text_re = re.compile("[a-zA-Z][a-zA-Z][a-zA-Z]")


def ocr_text_should_present(node):
    if node['class'].lower() == 'option':
        return False

    # very narrow: likely icon
    if node['width'] < 60:
        return False
    text = node['text']
    if ocr_text_re.findall(text):
        return True
    else:
        return False


def ocr_same_char(a, b):
    return a != ' ' and a.lower() == b.lower()


def ocr_text_matching(text, ocr):
    f = {}
    text = text[:100]
    ocr = ocr[:100]
    for i in range(len(text)):
        for j in range(len(ocr)):
            best = 0
            if ocr_same_char(text[i], ocr[j]):
                if i == 0 or j == 0:
                    best = max(best, 1)
                else:
                    best = max(best, f[i - 1, j - 1] + 1)
            if i > 0:
                best = max(best, f[i - 1, j])
            if j > 0:
                best = max(best, f[i, j - 1])
            f[i, j] = best

    match_len = f[len(text) - 1, len(ocr) - 1]

    #print(text, '/', ocr, ':', match_len)

    if match_len > 10:
        return (1.0, 1.0)

    #best = 0
    #for i in range(len(text)):
    #    cur = 0
    #    for j in range(len(ocr)):
    #        if i + j >= len(text):
    #            break
    #        if text[i + j] == ocr[j]:
    #            cur += 1
    #            if cur > best:
    #                best = cur
    #        else:
    #            cur = 0

    #if best >= 5:
    #    return (1.0, 1.0)

    return (1.0 * match_len / len(text), 1.0 * match_len / len(ocr))


def ocr_text_missing(node):
    text = node['text']
    ocr_text = node['ocr']

    if len(text) == 0 or len(ocr_text) == 0:
        return True

    match = ocr_text_matching(text, ocr_text)
    if match[0] < 0.5 or node['children'] == [] and match[1] < 0.5:
        return True
    else:
        return False


def find_hidden_ocr_node(tree, nodeid):
    node = tree[nodeid]
    missing = found = other = 0
    if 'covered' in node and not node['covered']:
        found = 1
    elif ocr_text_should_present(node):
        if ocr_text_missing(node):
            missing = 1
        else:
            found = 1
    else:
        if not ocr_text_missing(node):
            found = 1
        elif node['children'] == []:
            other = 1

    call_hidden = 0
    for childid in node['children']:
        (c_missing, c_found, c_other, c_hidden) = find_hidden_ocr_node(tree, childid)
        missing += c_missing
        found += c_found
        other += c_other
        call_hidden += c_hidden

    if found > 0:
        #print("visible: %s" % (util.describe_node(node)))
        node['visible'] = 'visible'
    elif missing == 0:
        # found == missing == 0
        node['visible'] = 'unknown'
    elif call_hidden > 0.51 * len(node['children']):
        node['visible'] = 'hidden'
    elif (((missing > 1 and missing > 0.9 * (missing + other)) or
          other == 0 or
          (missing > 0.5 * (missing + other) and node['width'] * node['height'] == 0)) and
          missing + other > 4):
        # found == 0, missing > 0
        #print("hidden : %s" % (util.describe_node(node)))
        node['visible'] = 'hidden'
    elif other == 0 and missing == 1:
        node['visible'] = 'hidden'
    else:
        #print("%2d %2d  : %s" % (missing, other, util.describe_node(node)))
        node['visible'] = 'maybe'

    node['ocr_missing'] = missing
    node['ocr_found'] = found
    node['ocr_other'] = other

    return (missing, found, other, 1 if node['visible'] == 'hidden' else 0)


def mark_hidden_children(tree, nodeid, hidden):
    node = tree[nodeid]
    if hidden:
        node['visible'] = 'hidden'
    elif node['ocr_missing'] == 1 and node['visible'] == 'hidden':
        node['visible'] = 'maybe'

    for childid in node['children']:
        mark_hidden_children(tree, childid, node['visible'] == 'hidden')


def find_hidden_ocr(tree):
    mark_visible(tree)
    find_hidden_ocr_node(tree, min(tree))
    if tree[min(tree)]['visible'] == 'hidden':
        # this is impossible...
        for nodeid in tree:
            node = tree[nodeid]
            node['visible'] = 'visible'
            node['ocr_missing'] = 0
            node['ocr_found'] = 0
            node['ocr_other'] = 0


def mark_visible_node(tree, nodeid, ans):
    node = tree[nodeid]
    if node['children'] == []:
        covered = False
        for otherid in tree:
            if otherid != nodeid and otherid not in ans:
                if cover_node(node, tree[otherid]):
                    covered = True
                    break
        node['covered'] = covered

    for childid in node['children']:
        mark_visible_node(tree, childid, ans + [nodeid])


def mark_visible(tree):
    mark_visible_node(tree, min(tree), [])


def mark_children_hidden_ocr(tree):
    mark_hidden_children(tree, min(tree), False)


if __name__ == '__main__':
    import sys
    print(ocr_text_matching(sys.argv[1], sys.argv[2]))
