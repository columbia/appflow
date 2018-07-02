#!/usr/bin/env python3

import os

tag = {}
apps = set()
required_tags = {}
ignore_tags = {}
single_tags = set()


def parse_line(line, cont):
    line = line.strip()
    if line == '':
        return cont
    if line[0] == '#':
        return cont
    if cont == '':
        parts = line.split(' ', 1)
        if len(parts) != 2:
            return cont
        (screen, tags) = parts
    else:
        screen = cont
        tags = line

    if screen not in tag:
        tag[screen] = set()
    if screen not in required_tags:
        required_tags[screen] = set()

    for t in tags.split(','):
        single = False
        t = t.strip()
        if t == '':
            continue
        if '*' in t:
            single = True
            t = t.replace('*', '')
        if t.upper() == t:
            t = t.lower()
            required_tags[screen].add(t)
        if t not in tag[screen]:
            tag[screen].add(t)
        if single:
            single_tags.add(t)
            single_tags.add("%s.%s" % (screen, t))

    if line[-1] == ',':
        return screen
    else:
        return ''


def load(filename):
    if not os.path.isfile(filename):
        dirname = filename
        appsname = dirname + "/applist.txt"
        for app in open(appsname).read().strip().split(','):
            apps.add(app)
        filename = dirname + "/tags.txt"
    conf = open(filename, 'r')
    cont = ''
    for line in conf:
        cont = parse_line(line, cont)
    for t in tag.get('ignored_elements', []):
        if ':' in t:
            (scr, name) = t.split(':')
        else:
            scr = 'all'
            name = t
        ignore_tags[scr] = ignore_tags.get(scr, []) + [name]


def valid(scrname, desc):
    if scrname.startswith('cat'):
        scrname = 'cat'
    if scrname not in tag:
        return False
    if scrname == 'region':
        return desc in tag[scrname]
    if ((desc in tag[scrname] or desc in tag['universal']) and
        desc not in ignore_tags.get(scrname, []) and
        desc not in ignore_tags.get('all', [])):
        return True
    else:
        return False


def validtag(desc):
    for scr in tag:
        if desc in tag[scr]:
            return True
    return False


def validscr(scrname):
    if scrname.startswith('cat'):
        scrname = 'cat'
    if scrname in tag:
        return True
    else:
        return False


def single(tagname, screen=None):
    if screen is not None:
        return "%s.%s" % (screen, tagname) in single_tags or tagname in single_tags
    else:
        return tagname in tag.get('single', []) or tagname in single_tags


def validapp(appname):
    return appname in apps


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        load("../etc-%s/tags.txt" % sys.argv[1])
    else:
        load("../etc/tags.txt")
    scrcnt = elemcnt = 0
    screens = set()
    invalid_tags = set()
    elements = set()
    for screen in sorted(tag):
        if (screen == 'single' or screen == 'ignored_screens' or
            screen == 'ignored_elements' or screen == 'remove_screens'):
            continue
        if screen in tag['ignored_screens']:
            continue
        print("%s:" % screen)
        print("\t", end='')
        if screen != 'universal':
            scrcnt += 1
            screens.add(screen)
        for t in sorted(tag[screen]):
            if not valid(screen, t):
                invalid_tags.add(screen + ':' + t)
            else:
                print("%s " % t, end='')
                elemcnt += 1
                elements.add(screen + ':' + t)
        print()
    print("REQ:")
    for screen in sorted(required_tags):
        if required_tags[screen] == set():
            continue
        print("%s:" % screen)
        print("\t", end='')
        for t in sorted(required_tags[screen]):
            print("'%s' " % t, end='')
        print()

    print("screens: %d %s" % (scrcnt, list(sorted(screens))))
    print("elements: %d %s" % (elemcnt, list(sorted(elements))))
    print("invalid %d %s" % (len(invalid_tags), list(sorted(invalid_tags))))
