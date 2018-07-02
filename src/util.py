import re
import logging
import string
import random
import glob
import os
import multiprocessing
import progressbar

import tags
import config

id_re = re.compile("[a-zA-Z][a-z]+")

WIDTH = 108 * 2
HEIGHT = 192 * 2

logger = logging.getLogger("util")


def describe_node(node, descs={}, scores={}, short=False):
    if len(node['raw']) == 1:
        raws = "%s" % node['raw']
    else:
        raws = "[%d,%d]" % (node['raw'][0], node['raw'][-1])
    ret = "%10s (%2d)" % (raws, len(node['raw']))

    attrs = " ["
    if node['click']:
        attrs += 'C'
    if node['scroll']:
        attrs += 'S'
    if node['focused']:
        attrs += 'F'
    if node['webview']:
        attrs += 'W'
    attrs += "]"

    ret += "%5s" % attrs

    #ret = '%3s ' % node['raw'][0]
    cls = node['class']
    desc = (' (' + node['desc'][:30] + ')') if node['desc'] else ''
    if not desc and 'ocr' in node and node['ocr'] != '' and config.show_ocr_result:
        desc = (' (!' + node['ocr'][:30] + '!)') if node['ocr'] else ''
    text = "%s%s" % (' ' + node['text'][:30], desc)
    desc = re.sub(r"\s+", " ", desc)
    text = re.sub(r"\s+", " ", text)
    #ids = id_re.findall(node['id'].split('/')[-1])
    #id_ = (' #' + ' '.join(ids).lower()[-40:]) if node['id'] else ''
    id_ = node['id'][:55]

    if short:
        fmt = " %s"
        fmt2 = " %15s %s %s"
    else:
        fmt = "%-110s"
        fmt2 = '%15s%-40s%s'

    ret += fmt % (fmt2 % (cls, text, id_))

    if short:
        fmt = " %s"
    else:
        fmt = " %20s"

    if descs is None:
        if node['tags']:
            ret += fmt % ' '.join(node['tags'])
        elif 'regs' in node:
            ret += fmt % ' '.join(map(lambda x: 'r:' + x, node['regs']))
    else:
        ret += fmt % ' '.join(filter(None, map(lambda x: descs.get(x, ''), node['raw'])))
        if scores is not None:
            ret += "%5s" % ' '.join(
                filter(None, map(lambda x: "%.2f" % scores[x] if x in scores and
                                 scores[x] is not None else '', node['raw'])))

    ret += "%10s-%10s" % (
        '%dx%d' % (node['x'], node['y']),
        '%dx%d' % (node['width'], node['height']))

    if 'visible' in node:
        if node['visible'] == 'visible':
            ret += '+'
        if node['visible'] == 'hidden':
            ret += '-%dx%d' % (node['ocr_missing'], node['ocr_other'])
        if node['visible'] == 'maybe':
            ret += '*%dx%d' % (node['ocr_missing'], node['ocr_other'])
        if node['visible'] == 'unknown':
            ret += ' '
    return ret


def print_node(node, descs, scores, depth, tagged_only):
    if tagged_only:
        if descs:
            has_tag = False
            for itemid in node['raw']:
                if itemid in descs:
                    has_tag = True
                    break
            if not has_tag:
                return
        else:
            if node['tags'] == []:
                return
    return "%-10s %s\n" % ((' ' * depth + '+'), describe_node(node, descs, scores))


def print_tree_node(tree, descs, scores, depth, nodeid, tagged_only, show_hidden):
    node = tree[nodeid]
    if not show_hidden and node.get('visible', '') == 'hidden':
        return ''
    #if nodeid != 0:
    ret = print_node(node, descs, scores, depth, tagged_only)
    #else:
    #    ret = ''
    for item in sorted(tree):
        if tree[item]['parent'] == nodeid:
            ret += print_tree_node(tree, descs, scores, depth + 1, item, tagged_only,
                                   show_hidden)
    return ret


def print_tree(tree, descs=None, scores=None, tagged_only=False, use_log=False,
               show_hidden=False):
    ret = print_tree_node(tree, descs, scores, 0, 0, tagged_only, show_hidden)
    if use_log:
        logger.info("current screen:\n%s", ret)
    else:
        print(ret)


def remove_mark(args, items, descs, recursive):
    itemid = int(args[0])
    remove_mark_one(itemid, items, descs, recursive)


def remove_mark_one(itemid, items, descs, recursive):
    if itemid in descs:
        origmark = descs[itemid]
        del descs[itemid]
        print("REMOVED %s from %s" % (origmark, describe(items[itemid])))

        sameid = []
        otherids = list(descs)
        for otherid in otherids:
            if descs[otherid] == origmark:
                sameid.append(otherid)
        if sameid:
            ret = input("do you want to remove other items with same id? ")
            if ret == 'y':
                for otherid in sameid:
                    del descs[otherid]
    else:
        print("no tag for %d" % itemid)
    if recursive:
        for child in items[itemid]['children']:
            remove_mark_one(child, items, descs, recursive)


def mark_item(args, items, descs, screen=None, tagdb=None):
    itemid = int(args[0])
    desc = args[1]
    if screen is not None and not tags.valid(screen, desc):
        print("warn: ILLEGAL TAG %s" % desc)
    descs[itemid] = desc
    print("%s <- %d %s" % (desc, itemid, describe(items[itemid])))

    sameids = []
    if items[itemid]['id'] != '':
        for otheritemid in items:
            if otheritemid == itemid:
                continue
            if items[otheritemid]['id'] == items[itemid]['id']:
                sameids.append(otheritemid)

    if sameids:
        answer = input("do you want to mark others with same id?")
        if answer == 'y':
            for otherid in sameids:
                descs[otherid] = desc
                print("%s <- %d %s" % (desc, otherid, describe(items[otherid])))
            if tagdb is not None:
                tagdb[desc] = items[itemid]['id']


def describe(item):
    is_layout = False
    if 'class' not in item:
        return 'ROOT'
    if 'Layout' in item['class']:
        is_layout = True
    ret = '%15s' % item['class'].replace('View', '')
    text = re.sub(r"\s+", " ", item['text'])
    desc = re.sub(r"\s+", " ", item['desc'])
    ret += ' %.30s' % text
    ret += ' (%.30s)' % desc
    ret += ' #%20s' % item['id'].split('/')[-1]
#    if not is_layout:
    ret += ' +%d+%d %dx%d D%d' % (
        item['x'], item['y'], item['width'], item['height'], item['depth'])
    prop = ''
    if item['click']:
        prop += 'C'
    if item['selected']:
        prop += 'S'
    if 'webview' in item and item['webview']:
        prop += 'W'
    if prop:
        ret += ' [%s]' % prop
    if not is_layout:
        ret += ' C%d' % item['childid']
    ret += " %s" % item['children']

    if 'classes' in item:
        ret += " %.30s" % ' '.join(map(lambda x: '.%s' % x, item['classes']))
    return ret


def save_desc(basename, descs, kind='desc'):
    with open(basename + ".%s.txt" % kind, 'w') as outf:
        for item_id in sorted(descs):
            outf.write("%d %s\n" % (item_id, descs[item_id]))
    print("SAVED to %s" % (basename + '.%s.txt' % kind))


def load_desc(basename, kind='desc'):
    descname = basename + '.%s.txt' % kind
    descs = {}
    if os.path.exists(descname):
        with open(descname) as descf:
            for line in descf.read().split('\n'):
                if not line:
                    continue
                (item_id, desc) = line.split(' ')
                descs[int(item_id)] = desc
    return descs


def printdesc(items, descs):
    for itemid in sorted(descs):
        print("%3d %15s %s" % (itemid, descs[itemid], describe(items[itemid])))


def printitems(items):
    for itemid in sorted(items):
        print("%3d %-20s %s" % (
            itemid, '-' * items[itemid]['depth'], describe(items[itemid])))


def get_app(actname):
    return actname.split('/')[0]


def randstr(len):
    ret = ''
    for i in range(len):
        ret += random.choice(string.ascii_lowercase)
    return ret


def simplify_text(text):
    return re.sub(r"\s+", " ", text).strip()


def url_to_actname(url):
    for i in range(len(url)):
        if i > 0 and url[i] >= 'a' and url[i] <= 'z':
            if not url[i - 1].isalpha():
                url = url[:i] + url[i].upper() + url[i + 1:]

    url = url.split('//', 1)[-1].split('?', 1)[0].split('#', 1)[0]
    if '/' in url:
        (urlhost, urlpath) = url.split('/', 1)
        urlpath = '.'.join(urlpath.split('/'))
        return "%s.%s" % (urlhost, urlpath)
    else:
        return url.replace('/', '.')


def choose_filename(path, template):
    page_id = 0
    while (len(glob.glob(os.path.join(path, "%s.*" % (template % page_id)))) > 0):
        page_id += 1

    return os.path.join(path, template % page_id)


def remove_pt(basename):
    for ext in ["hier", "url", "htm", "png", "xml", "txt", "web"]:
        try:
            os.remove("%s.%s" % (basename, ext))
        except:
            pass


def collect_files(datadir):
    """ Collect GUI files from a dir """
    return (glob.glob(os.path.join(datadir, "*.xml")) +
            glob.glob(os.path.join(datadir, "*.hier")))


def parallel_work(func, jobs, parallel, show_progress=False):
    if len(jobs) == 0:
        return []

    if show_progress:
        bar = progressbar.ProgressBar(maxval=len(jobs))

    if parallel and config.parallel:
        pool = multiprocessing.Pool(processes=config.threads)
        irets = pool.imap_unordered(func, jobs)

        if show_progress:
            irets = bar(irets)

        rets = []
        for ret in irets:
            rets.append(ret)

        pool.close()
    else:
        if show_progress:
            jobs = bar(jobs)

        rets = map(func, jobs)

    return rets


def pbar(iter):
    bar = progressbar.ProgressBar()
    return bar(iter)


def get_aux_info(filename):
    filename = os.path.splitext(os.path.basename(filename))[0]
    appname = filename.split('_')[0]
    scrname = filename.split('_')[-1]
    return (appname, scrname)


def get_test_apps(cat=None):
    if cat is None:
        applist = "../etc/applist.txt"
    else:
        applist = "../etc-%s/applist.txt" % cat

    for line in open(applist):
        return line.strip().split(',')


def is_def_val(val):
    return val == '' or val == 'false'


def equal(a, b):
    if (a == '' and b == 'false') or (a == 'false' and b == ''):
        return True
    return a == b


def unequal(a, b):
    return not equal(a, b)


def get_pid(dev, appname):
    try:
        app_pid = dev.run_adb_shell("pgrep %s\$" % appname).decode('utf-8').strip()
        if app_pid == '':
            app_pid = dev.run_adb_shell("pgrep -f %s[^:]" % appname).decode('utf-8').strip()
        if app_pid == '':
            logger.info("app not running")
            return None
    except:
        return None
    if len(app_pid.strip().split('\n')) > 1:
        for pid in app_pid.strip().split('\n'):
            try:
                app_cmdline = dev.run_adb_shell("cat /proc/%s/cmdline" % pid).decode(
                    'utf-8').strip('\0')
            except:
                continue
            if ':' in app_cmdline:
                continue
            if app_cmdline == appname:
                return pid
    return app_pid
