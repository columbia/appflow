#!/usr/bin/env python3

import logging
import argparse
import copy
import os
import time
import json

import testlib
import state
import screenlib
import observer
import microtest
import console
import route
import operation
import appdb
import device
import condition
import config
import perfmon
import watchdog
import progress
import statemgr
import tags
import environ
import value
import util

logger = logging.getLogger("miner")


class Miner(object):
    def __init__(self, dev, guispath, modelpath, tlibpath, batch, appname, statpath,
                 errpath, skippath, extrapath, mempath, need_observer):
        self.dev = dev
        self.appname = appname # type: str
        self.app = appdb.get_app(appname) # type: str
        self.tlib = testlib.collect_pieces(tlibpath)
        self.tlib.set_app(appname)
        if skippath is not None:
            self.tlib.load_skip(skippath)
        self.slib = screenlib.Screenlib(self.tlib.essential_props())
        if need_observer:
            self.observer = observer.Observer(errpath)
            self.observer.set_app(appname)
            self.observer.load(modelpath, guispath, extrapath, config.extra_screens,
                               config.extra_element_scrs)
            self.observer.tlib = self.tlib # TODO: so ugly
        else:
            self.observer = None
        self.watchdog = watchdog.create(config.WATCHDOG_TIMEOUT)
        self.statemgr = statemgr.StateMgr(self.tlib, self.slib, self.dev, self.observer,
                                          self.watchdog)

        self.statpath = statpath
        self.batch = batch
        if batch:
            self.console = None
        else:
            self.console = console.Console(self.handle_cmd)
            self.console.start()
        self.explored_ops = {} # type: Dict[state.State, Set[operation.Operation]]
        self.round_no = 0
        self.progress = ''

        self.tlib.add_test(microtest.init_test(self.app))
        restart_test = microtest.restart_test(self.app)
        if not config.allow_restart:
            restart_test.set_prio(-1000)
        self.tlib.add_test(restart_test)

        self.mempath = mempath
        self.load_memory()

    def handle_cmd(self, cons, cmd, envs):
        if cmd == "q":
            self.print_stat()
            os._exit(0)
        if cmd == "stat":
            self.print_stat()
        elif cmd == 'perf':
            perfmon.print_stat()
        cons.set_prompt("%s > " % self.progress)

    def print_stat(self, simple=False):
        if self.round_no != 0:
            logger.info("=== ROUND %d ===", self.round_no)
            logger.info("===  APP %s ===", self.appname)
        perfmon.print_stat()
        self.slib.print_stat(simple)
        self.tlib.print_stat(simple)
        self.statemgr.print_stat(simple)
        if not simple:
            self.observer.print_stat()
            value.print_stat()

    def save_stat(self, statfile=None):
        if statfile is None:
            statfile = os.path.join(self.statpath, "%s.txt" % self.appname)
        self.tlib.save_stat(statfile)

    def load_stat(self):
        self.tlib.load_stat(os.path.join(self.statpath, "%s.txt" % self.appname))

    def save_memory(self, memfile=None):
        if memfile is None:
            memfile = os.path.join(self.mempath, "%s.json" % self.appname)
        logger.info("saving memory into %s", memfile)

        if os.path.exists(memfile):
            memfilebak = os.path.join(self.mempath, "%s.json.bak" % self.appname)
            with open(memfile) as memf:
                memory_dump = memf.read()
            with open(memfilebak, 'w') as memfbak:
                memfbak.write(memory_dump)

        memory_obj = {}
        self.tlib.save_memory(memory_obj)
        self.slib.save_memory(memory_obj)
        self.statemgr.save_memory(memory_obj)
        memory_dump = json.dumps(memory_obj, indent=1)
        with open(memfile, 'w') as memf:
            memf.write(memory_dump)

    def load_memory(self, memfile=None):
        if memfile is None:
            memfile = os.path.join(self.mempath, "%s.json" % self.appname)
        if not os.path.exists(memfile):
            return False

        logger.info("loading memory from %s", memfile)
        with open(memfile) as memf:
            memory_dump = memf.read()
        memory_obj = json.loads(memory_dump)
        self.tlib.load_memory(memory_obj)
        self.slib.load_memory(memory_obj, self.tlib)
        self.statemgr.load_memory(memory_obj)
        return True

    def erase_memory(self, feature_name, test_name):
        self.tlib.erase_memory(feature_name, test_name)

    def mine(self, only_tagged, rounds):
        logger.info("mine")

        self.tlib.set_onlytagged(only_tagged)

        logger.info("current test library: %s", self.tlib)

        self.watchdog.start()
        self.mine_now(rounds)

        self.watchdog.kick()
        self.save_stat()
        self.print_stat()

        self.save_memory()

        self.dev.finish()
        self.watchdog.stop()

    def pick_explore_op(self, state, ops):
        # TODO: pick an op
        essential = state.to_essential(self.tlib.essential_props())
        if essential not in self.explored_ops:
            self.explored_ops[essential] = set()
        for op in ops:
            if not str(op) in self.explored_ops[essential]:
                logger.info("choosed op %s at state %s, explored %s", op,
                            essential, self.explored_ops[essential])
                self.explored_ops[essential].add(str(op))
                return op
        return None

    def explore_mode(self):
        if not config.do_exploration:
            return False

        trying_state_id = 0
        progress = False
        while True:
            trying_state_id += 1
            trying_state = self.slib.get_essential_screen(trying_state_id)
            if trying_state is None:
                break

            if not self.slib.check_state_perf(trying_state_id, self.tlib):
                continue

            if not self.slib.should_explore(trying_state_id):
                continue

            logger.info("exploring %s", trying_state)
            trying_route = self.slib.get_route_by_state(trying_state)
            if trying_route is None:
                continue

            logger.info("picked %s", trying_route)
            curr_state = state.State({'screen': 'init'})
            self.replay_route(trying_route, curr_state)

            gui_state = self.observer.grab_state(self.dev)
            if gui_state is None:
                logger.error("fail to grab current state")
                continue

            curr_state.merge(gui_state)

            if trying_state.get('screen', '') == 'WRONG':
                # the new state is likely classified wrong
                curr_state.set('screen', 'WRONG')

            if not curr_state.is_unknown():
                logger.warning("route replayed, but the resulting screen does not match")

            ops = operation.collect_ops(curr_state)
            try_op = self.pick_explore_op(curr_state, ops)
            if try_op is None:
                self.slib.mark_state_finished(trying_state_id)
                continue

            op_test = microtest.MicroTest(
                steps=[try_op], name="generated %s" % try_op,
                conds=[
                    condition.Condition('screen', trying_state.get('screen')),
                    condition.Condition('items', trying_state.get('items'))])
            ret = op_test.attempt(self.dev, self.observer, curr_state, self.tlib)
            if not ret:
                logger.warning("collected op failed??")
                continue

            self.record_new_state(curr_state, trying_route, op_test)

            self.statemgr.cleanup(curr_state)

            progress = True
        return progress

    def record_new_state(self, curr_state, old_route, step, state_repeated=False):
        new_route = route.new(old_route, step)
        new_state = copy.deepcopy(curr_state)

        if not step.read_only and not state_repeated:
            self.slib.add_route(new_route, new_state)
        return (new_route, new_state)

    def replay_route(self, route, curr_state, states=None):
        try:
            ret = route.replay(self.dev, curr_state, self.observer, self.tlib, states)
        except:
            logger.exception("replay route exception")
            ret = False

        if not ret:
            logger.warning("replay route failed")
            self.slib.mark_route_fail(route)
        else:
            logger.info("route replayed")

        return ret

    def should_terminate(self):
        if config.do_exploration and not self.tlib.test_available(self.slib):
            self.slib.check_screens(self.tlib)
        if self.tlib.test_available(self.slib):
            self.tlib.explain_no_test(self.slib)
            logger.info("more test available, do some exploration")
            if not self.explore_mode():
                logger.info("exploration can't save us")
                return True
            return False
        else:
            logger.info("no more test to try, terminating")
            return True

    def observe(self):
        return self.observer.grab_state(self.dev)

    def round_clear(self):
        self.observer.round_clear()

    def report_prog(self, prog):
        self.progress = "R.%d %s" % (self.round_no, prog)
        progress.report_progress(self.progress)

    def kbd_on(self):
        operation.Operation("kbdon").do(self.dev, self.observer, state.State(),
                                        environ.empty, self.tlib)

    def mine_now(self, rounds):
        self.round_no = 0
        curr_state = None
        continue_test = False
        if config.do_init_clean:
            self.statemgr.init_clean()
        self.kbd_on()
        while True:
            self.round_clear()

            self.round_no += 1
            if self.round_no > rounds:
                if continue_test:
                    logger.info("clean before exit")
                    self.statemgr.cleanup(curr_state.to_essential(
                        self.tlib.essential_props()))
                break
            perfmon.record_stop("miner", "round")
            perfmon.record_start("miner", "round")
            self.watchdog.kick()
            try:
                logger.info("mine round %d", self.round_no)
                self.print_stat()
                #logger.info("current test lib: %s", self.tlib)
                logger.info("current screen lib: %s", self.slib)
            except:
                logger.exception("maintainance err")
            self.save_stat()
            self.save_memory()

            test_to_try = None
            if continue_test:
                essential_state = curr_state.to_essential(self.slib.essential_props)
                test_to_try = self.tlib.pick_continuous_test(essential_state, self.slib)

            if test_to_try is None:
                if continue_test:
                    self.statemgr.cleanup(curr_state.to_essential(
                        self.tlib.essential_props()))

                test_to_try = self.tlib.pick_test(self.slib)
                continue_test = False
            else:
                self.report_prog("CONT  %s" % test_to_try.short_name())
                continue_test = True

            if test_to_try is None:
                if self.should_terminate():
                    break
                else:
                    continue

            testinfo = self.tlib.get_testinfo(test_to_try)

            self.watchdog.kick()
            if not continue_test:
                curr_state = state.State({'screen': 'init'})
                (route_to_try, target_state) = self.slib.pick_route(test_to_try, testinfo)
                logger.info("picked %s", target_state)
                logger.info("picked %s", route_to_try)
                self.report_prog("PICKED %s FROM %s" % (test_to_try.short_name(),
                                                        target_state))
                self.report_prog(" ROUTE %s" % route_to_try)

                passed_states = []
                if not self.replay_route(route_to_try, curr_state, passed_states):
                    self.report_prog("REPLAY FAIL %s" % route_to_try)
                    self.statemgr.observe_and_clean_all(curr_state)
                    continue

                passed_essential_states = []
                for astate in passed_states:
                    passed_essential_states.append(
                        astate.to_essential(self.slib.essential_props))

                gui_state = self.observer.grab_state(self.dev)
                if gui_state is None:
                    logger.error("fail to grab current state")
                    continue

                curr_state.merge(gui_state)

            self.watchdog.kick()
            # starting from target_state
            # now, curr_state = state after replay
            if test_to_try.usable(curr_state):
                if not continue_test:
                    self.slib.mark_route_succ(route_to_try)
                continue_test = False
                from_state = copy.deepcopy(target_state)
                logger.info("proceed to try '%s' from %s", test_to_try.short_name(),
                            target_state)
                error = False
                self.report_prog("RUN TEST %s" % test_to_try.short_name())
                try:
                    succd = test_to_try.attempt(self.dev, self.observer, curr_state,
                                                self.tlib)
                except:
                    logger.exception("try test exception")
                    succd = False
                    error = True

                new_essential = curr_state.to_essential(self.slib.essential_props)

                #gui_state = self.observe()
                #curr_state.merge(gui_state)
                # now, curr_state = state after test execution
                if succd:
                    logger.info("===== test SUCCEEDED =====")
                    self.report_prog("TEST %s SUCC, reached %s" %
                                     (test_to_try.short_name(), new_essential))
                    if not self.batch:
                        time.sleep(1)

                    self.tlib.handle_sys_screen(curr_state, self.dev, self.observer)

                    self.tlib.mark_succ(test_to_try, target_state, new_essential)
                    self.slib.mark_screen_succ(target_state)

                    repeated_state = False
                    for astate in passed_essential_states:
                        if new_essential == astate:
                            logger.info("repeated state, discard route")
                            repeated_state = True
                            break

                    (new_route, new_state) = self.record_new_state(curr_state,
                                                                   route_to_try,
                                                                   test_to_try,
                                                                   repeated_state)
                    if new_essential == target_state:
                        # same state
                        # should not change route_to_try
                        # should not change target state
                        route_to_try = copy.deepcopy(route_to_try)
                        target_state = copy.deepcopy(target_state)
                    else:
                        route_to_try = new_route
                        target_state = curr_state.to_essential(self.slib.essential_props)
                    curr_state = copy.deepcopy(new_state)
                elif error:
                    logger.info("===== test EXCEPTION =====")
                    if not self.batch:
                        time.sleep(180)
                    self.tlib.mark_error(test_to_try)
                else:
                    logger.info("===== test    FAILED =====")
                    self.report_prog("TEST %s FAIL" % test_to_try.short_name())
                    if not self.batch:
                        time.sleep(1)
                    self.tlib.mark_fail(test_to_try, target_state)
                    self.slib.mark_screen_fail(target_state)

                self.watchdog.kick()
                state_changed = False
                if error or not succd:
                    # must cleanup now
                    for prop in config.must_cleanup_keys:
                        origval = target_state.get(prop, '')
                        need_clean = False
                        if prop in test_to_try.get_change_keys():
                            if test_to_try.get_change_val(prop) != origval:
                                # maybe the state is changed! maybe not!
                                self.statemgr.observe_and_clean(prop, curr_state)
                                state_changed = True
                            elif util.unequal(origval, ''):
                                # not changed, must clear
                                need_clean = True
                        elif util.unequal(origval, ''):
                            # not changed, must clear
                            need_clean = True
                        if need_clean:
                            #self.statemgr.cleanup_prop(prop, origval, target_state)
                            # although it should be cleared...
                            # sometimes the property is still local
                            # and a restart would clear it
                            # so asking for a clean directly may fail
                            self.statemgr.observe_and_clean(prop, target_state)
                            state_changed = True

                continue_test = self.should_continue(succd, error, state_changed,
                                                     test_to_try, from_state, curr_state,
                                                     route_to_try,
                                                     passed_essential_states,
                                                     new_essential)

                if (config.read_only_continue and test_to_try.read_only and
                        not state_changed):
                    continue_test = True

                if succd and not continue_test:
                    # successd, but should not continue. just clean up
                    self.statemgr.cleanup(curr_state.to_essential(
                        self.tlib.essential_props()))

                if continue_test:
                    if (len(passed_essential_states) == 0 or
                        passed_essential_states[-1] != new_essential):
                        passed_essential_states.append(new_essential)

            else:
                logger.warning("replayed state does not match expectation")
                self.report_prog("REPLAY MISMATCH %s" % route_to_try)
                self.slib.mark_route_fail(route_to_try)
                self.statemgr.cleanup(curr_state.to_essential(
                    self.tlib.essential_props()))
                continue_test = False

            logger.info("continue test: %s", continue_test)

    def should_continue(self, succd, error, state_changed, test_to_try, from_state,
                        curr_state, curr_route, passed_essential, new_essential):
        if error:
            return False

        if state_changed:
            return False

        if not config.continue_testing:
            logger.info("no continue because disabled")
            return False

        # succ/fail, ro is good
        if test_to_try.read_only:
            logger.info("continue because test is readonly")
            return True

        for i in range(len(passed_essential)):
            if new_essential == passed_essential[i]:
                logger.info("no continue because repeating old state")
                return False

        if succd:
            # this check should not be needed now because of the repeated state check
            if from_state.get('screen') == curr_state.get('screen'):
                # same screen, not RO?
                logger.info("no continue because same screen")
                return False

            # different screen
            # check for repeat
            aroute = self.slib.pick_route_for_screen(
                curr_state.to_essential(self.tlib.essential_props()), True)
            if str(aroute) == str(curr_route):
                # okay, this route would be picked
                return True
            else:
                logger.info("no continue because diff route: %s %s", aroute, curr_route)
                return False

        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Miner")
    parser.add_argument('--serial', help="Device serial")
    parser.add_argument('--guispath', help="GUIs path", default="../guis/")
    parser.add_argument('--modelpath', help="Model path", default="../model/")
    parser.add_argument('--tlibpath', help="Test library path", default="../tlib/")
    parser.add_argument('--apkspath', help="Apps path", default="../apks/")
    parser.add_argument('--parampath', help="Param file path", default="../etc/")
    parser.add_argument('--app', help="App name", default="ebay")
    parser.add_argument('--explore', help="Explore mode",
                        default=False, action='store_const', const=True)
    parser.add_argument('--tag', help="Run only tagged ones")
    parser.add_argument('--batch', help="Batch mode (no console)",
                        default=False, action='store_const', const=True)
    parser.add_argument('--rounds', help="Max tests to mine", type=int, default=100)
    parser.add_argument('--statpath', help="Stat path", default="../stat/")
    parser.add_argument('--errpath', help="Error capture path", default="../err/")
    parser.add_argument('--log', help="Log file", default="log.txt")
    parser.add_argument('--state', help="state file", default="state.txt")
    parser.add_argument('--skippath', help="Skip file", default="../etc/skip.txt")
    parser.add_argument('--extrapath', help="extra GUIs path", default="../guis-extra/")
    parser.add_argument('--mempath', help="memory path", default="../memory/")
    args = parser.parse_args()

    loglevel = logging.INFO
    logformat = "%(levelname).4s %(asctime)-15s %(module)10s: %(message)s"
    if args.log:
        logging.basicConfig(level=loglevel, format=logformat, filename=args.log)
    else:
        logging.basicConfig(level=loglevel, format=logformat)

    if args.tag:
        tagged = set(args.tag.split(','))
        tagged.add(args.app)
    else:
        tagged = None

    if args.state:
        progress.init(args.state)
    tags.load(os.path.join(args.parampath, "tags.txt"))
    value.init_params(args.parampath, args.app)
    dev = device.create_device(serial=args.serial)
    if dev.kind == 'adb':
        appdb.collect_apps(args.apkspath)
    elif dev.kind == 'web':
        appdb.load_urls(os.path.join(args.parampath, "urls.txt"))
    miner = Miner(dev, args.guispath, args.modelpath, args.tlibpath, args.batch, args.app,
                  args.statpath, args.errpath, args.skippath, args.extrapath,
                  args.mempath, True)
    if args.explore:
        miner.explore_mode()
    else:
        miner.mine(tagged, args.rounds)
