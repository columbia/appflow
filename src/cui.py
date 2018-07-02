#!/usr/bin/env python3

import os
import sys
import logging

import device
import observer
import util
import console
import operation
import state
import testlib
import environ
import value
import concept
import appdb
import threading
import perfmon
import microtest
import analyze
import listinfo
import config
import statemgr
import watchdog
import tags
import app as apputils

logger = logging.getLogger("cui")


def update_prompt(cons, envs):
    state = envs['state']
    tlib = envs['tlib']
    if state.get('items') is not None:
        cons.set_prompt("%s> " % state.to_essential(tlib.essential_props()))


def load_skip(appname):
    skips = set()
    skipfile = "../etc/skip_%s.txt" % appname
    if os.path.exists(skipfile):
        for line in open(skipfile):
            skips.add(line.strip())
    return skips


def save_skip(appname, skips):
    with open("../etc/skip_%s.txt" % appname, 'w') as skipf:
        for skip in skips:
            skipf.write("%s\n" % skip)


def add_skip(appname, shortname):
    skips = load_skip(appname)
    skips.add(shortname)
    save_skip(appname, skips)


def del_skip(appname, shortname):
    skips = load_skip(appname)
    if shortname in skips:
        skips.remove(shortname)
    save_skip(appname, skips)


def load_app(app, ob, tlib, envs):
    ob.set_app(app)
    tlib.set_app(app)
    envs['app'] = app

    value.init_params("../etc/", app)
    ob.load("../model/", "../guis/", "../guis-extra/", config.extra_screens,
            config.extra_element_scrs)

    tlib.add_test(microtest.init_test(appdb.get_app(app)))


def handle_console_cmd(cons, cmd, envs):
    threading.current_thread().name = 'MainThread'

    dev = envs['dev']
    ob = envs['ob']
    st = envs['state']
    tlib = envs['tlib']
    env = envs['env']

    if 'app' in envs:
        app = envs['app']
    else:
        app = 'cui'

    def save_stat():
        tlib.save_stat(os.path.join("../stat/", "%s.txt" % app))

    if cmd == 'q':
        save_stat()
        dev.finish()
        sys.exit(0)
    elif cmd == 'sense':
        scr = ob.grab_state(dev, no_verify=True, no_print=True)
        if scr.get('guess_descs') is None:
            util.print_tree(scr.get('tree'))
        else:
            util.print_tree(scr.get('tree'), scr.get('guess_descs'),
                            scr.get('guess_score'))
        st.merge(scr)
        return
    elif cmd == 'tags':
        config.show_guess_tags = True
        scr = ob.grab_state(dev, no_verify=True, no_print=True)
        util.print_tree(scr.get('tree'), scr.get('guess_descs'), scr.get('guess_score'))
        st.merge(scr)
        config.show_guess_tags = False
        return
    elif cmd == 'tree':
        scr = ob.grab_state(dev, no_img=True)
        util.print_tree(scr.get('tree'))
        st.merge(scr)
        return
    elif cmd.startswith('app '):
        app = cmd.split(' ')[1]
        load_app(app, ob, tlib, envs)
        return
    elif cmd == 'load':
        tlib = testlib.collect_pieces("../tlib/")
        envs['tlib'] = tlib
        load_app(app, ob, tlib, envs)
        return
    elif cmd == 'reload':
        value.init_params("../etc/", app)
        try:
            if app:
                os.remove("../model/screen_%s" % app)
                os.remove("../model/element_%s" % app)
            else:
                os.remove("../model/screen")
                os.remove("../model/element")
        except:
            pass
        ob.load("../model/", "../guis/", "../guis-extra/", config.extra_screens,
                config.extra_element_scrs)
        return
    elif cmd == 'tlib':
        tlib = testlib.collect_pieces("../tlib/")
        envs['tlib'] = tlib
        return
    elif cmd == 'test':
        tlib = testlib.collect_pieces("../tlib/")
        tlib.set_app(app)
        tlib.add_test(microtest.init_test(appdb.get_app(app)))
        envs['tlib'] = tlib

        config.show_guess_tags = True
        scr = ob.grab_state(dev)
        config.show_guess_tags = False
        st.merge(scr)
        begin_state = st.to_essential(tlib.essential_props())

        tests = tlib.usable_tests(st)
        tests.sort(key=lambda test: test.prio)

        for i in range(len(tests)):
            testinfo = tlib.get_testinfo(tests[i])
            print("%2d. %s: %s [%d %d]" % (i, tests[i].feature_name, tests[i].name,
                                           testinfo.succs, testinfo.fails))
        if len(tests) == 0:
            print("no test available!")
            return
        if len(tests) == 1:
            tid = 0
        else:
            tid = input("which one? ")
            try:
                tid = int(tid)
            except:
                return
        test = tests[tid]
        ret = test.attempt(dev, ob, st, tlib, environ.empty)

        util.print_tree(st.get('tree'), st.get('guess_descs'))
        end_state = st.to_essential(tlib.essential_props())
        if ret:
            print("test SUCC")
            tlib.clear_stat(test)
            tlib.mark_succ(test, begin_state, end_state)
        else:
            print("test FAIL")
            tlib.mark_fail(test, begin_state)
        save_stat()
        return
    elif cmd == 'save':
        save_stat()
        return
    elif cmd == 'stat':
        tlib.print_stat()
        return
    elif cmd == 'items':
        scr = ob.grab_state(dev, no_img=True)
        util.printitems(scr.get('items'))
        return
    elif cmd.startswith('item'):
        itemid = int(cmd.split(' ')[1])
        scr = ob.grab_state(dev, no_img=True)
        items = scr.get('items')
        if itemid in items:
            print(util.describe(items[itemid]))
        else:
            print("no such item: %d" % itemid)
        return
    elif cmd == 'debug':
        logging.basicConfig(level=logging.DEBUG)
        return
    elif cmd == 'idle':
        dev.wait_idle()
        return
    elif cmd == 'dialog':
        scr = ob.grab_state(dev)
        ret = tlib.handle_dialog(scr, dev, ob)
        if ret:
            print("dialog handled")
        else:
            print("dialog not handled")
        return
    elif cmd.startswith('find '):
        tag = cmd.split(' ', 1)[1]
        con = concept.parse(tag)
        if con is None:
            print("invalid locator")
            return
        scr = ob.grab_state(dev)
        widgets = con.locate(scr, ob, environ.Environment())
        if widgets == []:
            print("can't find")
        else:
            for widget in widgets:
                print("FOUND: %s" % widget)
                print("    content:", widget.content())
        return
    elif cmd == 'perf':
        perfmon.print_stat()
        return
    elif cmd == 'clear':
        init = tlib.find_test('meta', 'start app')
        st.reset()
        init.attempt(dev, ob, st, tlib, None)
        ob.update_state(dev, st)
        tlib.mark_succ(init, state.init_state, st)
        return
    elif cmd.startswith('set'):
        parts = cmd.split(' ', 2)
        if len(parts) == 2:
            key = parts[1]
            val = "1"
        else:
            (key, val) = parts[1:]
        st.set(key, val)
        return
    elif cmd.startswith('del'):
        parts = cmd.split(' ', 1)
        key = parts[1]
        st.remove(key)
        return
    elif cmd == 'dump':
        filename = util.choose_filename("../cap/", "page%d")
        logger.info("dumping to page %s", filename)
        dev.dump(filename)
        #sense.dump_page(dev, "../cap/")
        return
    elif cmd == 'list':
        scr = ob.grab_state(dev, no_img=True)
        tree = scr.get('tree')
        treeinfo = analyze.collect_treeinfo(tree)
        for root in sorted(treeinfo['listlike']):
            print("ROOT:", util.describe_node(tree[root]))
            for item in sorted(treeinfo['itemlike']):
                if listinfo.get_lca(tree, [root, item]) == root:
                    print("  NODE:", util.describe_node(tree[item]))
                    for field in sorted(treeinfo['dupid']):
                        if listinfo.get_lca(tree, [item, field]) == item:
                            print("    FIELD:", util.describe_node(tree[field]))
        return
    elif cmd == 'webon':
        config.GRAB_WEBVIEW = True
        return
    elif cmd == 'weboff':
        config.GRAB_WEBVIEW = False
        return
    elif cmd.startswith('ob '):
        prop = cmd.split(' ', 1)[1]
        wd = watchdog.Watchdog(100000)
        smgr = statemgr.StateMgr(tlib, None, dev, ob, wd)
        ret = smgr.observe_prop(prop, st)
        if ret:
            print("prop %s = %s" % (prop, st.get(prop, '')))
        else:
            print("observe error")
        return
    elif cmd.startswith('clean '):
        parts = cmd.split(' ', 2)
        if len(parts) == 2:
            prop = parts[1]
            val = "1"
        else:
            (prop, val) = parts[1:]
        wd = watchdog.Watchdog(100000)
        smgr = statemgr.StateMgr(tlib, None, dev, ob, wd)
        ret = smgr.cleanup_prop(prop, val, st)
        if ret:
            print("prop %s cleaned" % prop)
        else:
            print("clean error")
        return
    elif cmd.startswith('oc '):
        prop = cmd.split(' ', 1)[1]
        wd = watchdog.Watchdog(100000)
        smgr = statemgr.StateMgr(tlib, None, dev, ob, wd)
        ret = smgr.observe_and_clean(prop, st)
        if ret:
            print("prop %s is clean now" % prop)
        else:
            print("observe/clean error")
        return
    elif cmd == 'dbg':
        print(tlib)
        return
    elif cmd.startswith('skip '):
        name = cmd.split(' ', 1)[1]
        add_skip(app, name)
        print("skipping %s" % name)
        return
    elif cmd == 'skip':
        skips = load_skip(app)
        for skip in skips:
            print("now skipping %s" % skip)
        return
    elif cmd.startswith('noskip '):
        name = cmd.split(' ', 1)[1]
        del_skip(app, name)
        print("not skipping %s" % name)
        return
    elif cmd == 'src':
        if st.get('xml') is not None:
            print(st.get('xml'))
        if st.get('src') is not None:
            print(st.get('src'))
        return
    elif cmd == 'install':
        apputils.install(dev, app)
        return
    elif cmd == 'uninstall':
        apputils.uninstall(dev, app)
        return

    op = operation.parse_line(cmd)
    if op is None:
        print("unknown op")
        return

    ret = op.do(dev, ob, st, env, tlib)
    if not ret:
        print("op failed")


def run_console():
    if len(sys.argv) > 1:
        serial = sys.argv[1]
    else:
        serial = None

    dev = device.create_device(serial)
    if dev.kind == 'adb':
        appdb.collect_apps("../apks/")
    elif dev.kind == 'web':
        appdb.load_urls("../etc/urls.txt")
    ob = observer.Observer("../err/")
    init_state = state.State()
    env = environ.Environment()
    tlib = testlib.collect_pieces("../tlib/")
    tlib.assume_reached('signin', 'login', 'main')
    tlib.assume_reached('welcome', 'skip sign in / sign up', 'main')
    ob.tlib = tlib
    init_env = {'dev': dev, 'ob': ob, 'state': init_state,
                'env': env, 'tlib': tlib}
    if len(sys.argv) > 2:
        app = sys.argv[2]
        load_app(app, ob, tlib, init_env)

    cons = console.Console(handle_console_cmd, prompt="op> ", after_cb=update_prompt,
                           init_env=init_env)
    cons.start()
    cons.wait()


if __name__ == '__main__':
    if "--debug" in sys.argv:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    tags.load("../etc/tags.txt")
    run_console()
