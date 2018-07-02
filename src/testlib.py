#!/usr/bin/env python3

import logging
import glob
import os
import copy

import microtest
import operation
import environ
import state
import config
import locator
import statinfo
import util
import appdb
import route
import dialog
import tlibparser

logger = logging.getLogger("testlib")

DEPTH_LIMIT = 10
SYNTHESIS_QUEUE_LIMIT = 10000


class TestInfo(object):
    def __init__(self):
        self.succ = {}
        self.succs = 0
        self.fail = {}
        self.fails = 0
        self.error = 0
        self.reached_screens = {}

    def mark_succ(self, from_screen, to_screen):
        self.succ[from_screen] = self.succ.get(from_screen, 0) + 1
        self.succs += 1
        to_scrname = to_screen.get('screen')
        self.reached_screens[to_scrname] = self.reached_screens.get(to_scrname, 0) + 1

    def mark_fail(self, screen):
        self.fail[screen] = self.fail.get(screen, 0) + 1
        self.fails += 1

    def mark_error(self):
        self.error += 1

    def clear(self):
        self.succs = 0
        self.fails = 0
        self.error = 0
        self.succ = {}
        self.fail = {}

    def finished(self, screen):
        if self.fails >= config.TOTAL_FAIL_LIMIT or self.error >= config.ERROR_LIMIT:
            return True
        if (screen is not None and
            (self.succ.get(screen, 0) > 0 or
             self.fail.get(screen, 0) >= config.SCREEN_FAIL_LIMIT)):
            return True
        return False

    def unreached(self):
        return self.succs + self.fails + self.error == 0

    def vindicate(self, screen):
        self.fails -= 1
        if screen in self.fail:
            self.fail[screen] -= 1

    def get_most_reached(self):
        most = None
        count = -1
        for screen in self.reached_screens:
            if self.reached_screens[screen] > count:
                count = self.reached_screens[screen]
                most = screen
        return most

    def succ_rate(self):
        if self.succs + self.fails == 0:
            return 101 # better than 100%!
        else:
            return 100 * self.succs / (self.succs + self.fails)

    def __str__(self):
        return "->%s [%d+ %d- %d!]" % (list(self.reached_screens), self.succs,
                                       self.fails, self.error)

    def save_obj(self, mem_info):
        # TestInfo
        mem_info['succs'] = self.succs
        mem_info['fails'] = self.fails
        mem_info['error'] = self.error

        mem_succs = []
        for screen in self.succ:
            mem_succs.append({'screen': screen.to_obj(), 'c': self.succ[screen]})
        mem_info['succ'] = mem_succs
        mem_fails = []
        for screen in self.fail:
            mem_fails.append({'screen': screen.to_obj(), 'c': self.fail[screen]})
        mem_info['fail'] = mem_fails

        mem_reached = []
        for screen in self.reached_screens:
            entry = {'screen': screen, 'count': self.reached_screens[screen]}
            mem_reached.append(entry)
        mem_info['reached'] = mem_reached

        return mem_info

    def load_obj(self, mem_info):
        self.succs = mem_info['succs']
        for mem_succ in mem_info['succ']:
            succ_screen = state.State.from_obj(mem_succ['screen'])
            self.succ[succ_screen] = mem_succ['c']

        self.fails = mem_info['fails']
        for mem_fail in mem_info['fail']:
            fail_screen = state.State.from_obj(mem_fail['screen'])
            self.fail[fail_screen] = mem_fail['c']

        for entry in mem_info.get('reached', []):
            screen = entry['screen']
            count = entry['count']
            self.reached_screens[screen] = count


class Testlib(object):
    def __init__(self, only_tagged=None):
        self.tests = {}
        self.merged_conds = [] # type: List[Condition]
        self.next_id = 0
        self.testinfo = {}
        self.dep_props = set()
        self.only_tagged = only_tagged
        self.funcs = {} # type: Dict[str, microtest.MicroTest]
        self.fail_reason = {}
        self.observers = {}
        self.app = None
        self.handling_sys = set()
        self.disallow_dialog = False
        self.route_cache = {}
        self.cleaner_cache = {}
        self.skip_tests = set()

        self.add_test(microtest.gohome())

    def clear(self):
        self.tests = {}
        self.merged_conds = []
        self.next_id = 0
        self.testinfo = {}
        self.dep_props = set()
        self.funcs = {}
        self.fail_reason = {}
        self.observers = {}

    def set_app(self, app):
        self.app = app

    def record_dep(self, cond):
        for prop in cond.get_props():
            self.dep_props.add(prop)

    def essential_props(self):
        return self.dep_props

    def call(self, name, args, dev, observer, state):
        env = environ.Environment()
        func = self.funcs[name]
        func.bind_args(env, args)

        return func.attempt(dev, observer, state, self, env)

    def add_test(self, test):
        logger.debug("adding test %s", test)

        if test.has_tag("observe"):
            self.add_observer(test)
            return

        if test.has_tag("function"):
            self.funcs[test.name] = test
            return

        self.next_id += 1
        test.set_id(self.next_id)
        self.tests[self.next_id] = test

        for new_cond in test.get_conds():
            self.record_dep(new_cond)

            for cond in self.merged_conds:
                if cond.equals(new_cond):
                    new_cond = None
                    break
            if new_cond is not None:
                self.merged_conds.append(new_cond)

        self.testinfo[self.next_id] = TestInfo()

    def check_app(self, test):
        """ Return True if `test` is appropriate for current app"""
        return (test.feature_name not in appdb.apps or
                self.app is None or
                test.feature_name == self.app)

    def add_observer(self, observing_test):
        for prop in observing_test.get_change_keys():
            self.observers[prop] = self.observers.get(prop, []) + [observing_test]

    def get_observers(self, prop):
        obs = []
        for ob in self.observers.get(prop, []):
            if self.check_app(ob):
                obs.append(ob)
        return obs

    def get_cleaners(self, prop):
        cleaners = self.cleaner_cache.get(prop, [])
        for testid in self.tests:
            test = self.tests[testid]
            if test.is_cleaner(prop) and self.check_app(test) and test not in cleaners:
                cleaners.append(test)
        return cleaners

    def record_cleaner(self, prop, test):
        if prop not in self.cleaner_cache:
            self.cleaner_cache[prop] = []
        if test not in self.cleaner_cache[prop]:
            self.cleaner_cache[prop].append(test)

    def get_testinfo(self, test):
        return self.testinfo[test.get_id()]

    def filter_tests(self, state):
        ret = []
        for testid in self.tests:
            test = self.tests[testid]
            if test.usable(state):
                ret.append(test)
        return ret

    def test_finished(self, test, testinfo, slib):
        test_reachable = False
        for screen in slib.essential_screens:
            if self.test_usable(test, screen):
                test_reachable = True
                if not testinfo.finished(screen):
                    # never succeeded: try it
                    if testinfo.succs < config.TRUST_SUCC_TIMES:
                        return False
                    new_screen = test.predict_after(screen)
                    # conditions:
                    # 1. cannot predict new screen
                    # 2. new screen has not been reached
                    # 3. new screen has no route (possibly discarded)
                    if (new_screen is None or slib.not_seen(new_screen) or
                        slib.no_route(new_screen)):
                        return False
        if test_reachable:
            return True
        else:
            return False

    def should_skip(self, test):
        if test.prio < -500:
            return True
        if test.meta:
            return False
        if test.has_tag('function'):
            return True
        if self.only_tagged:
            for tag in self.only_tagged:
                if test.has_tag(tag):
                    return False
            return True
        if test.short_name() in self.skip_tests:
            return True
        if not self.check_app(test):
            return True
        return False

    def test_usable(self, test, curr_state):
        return test.usable(curr_state) and self.check_app(test)

    def usable_tests(self, curr_state):
        """ For CUI use """
        ret = []
        for testid in self.tests:
            test = self.tests[testid]
            if self.test_usable(test, curr_state) and not test.meta:
                ret.append(test)
        return ret

    def pick_test(self, slib):
        picked = None
        picked_info = None
        picked_route = None
        for testid in self.tests:
            testinfo = self.testinfo[testid]
            test = self.tests[testid]
            if self.should_skip(test):
                continue
            if self.test_finished(test, testinfo, slib):
                #print(test.short_name(), "finished")
                continue
            if slib.route_available(test, testinfo):
                (theroute, _) = slib.pick_route(test, testinfo)
                if theroute is None:
                    logger.error("picked test but no route??? %s", test.short_name())
                    continue
                print("  consider test", test.short_name())
                if self.better_test(test, testinfo, theroute,
                                    picked, picked_info, picked_route):
                    if picked is not None:
                        print("    better than", picked.short_name(), ":",
                              self.better_reason)
                    picked = test
                    picked_info = testinfo
                    picked_route = theroute
            else:
                #print(test.short_name(), "no route")
                pass

        if picked is not None:
            logger.info("PICKED '%s:%s'", picked.feature_name, picked.name)
        else:
            logger.info("nothing picked")
        return picked

    def explain_no_test(self, slib):
        logger.info("=== overview of tests ===")
        for testid in self.tests:
            testinfo = self.testinfo[testid]
            test = self.tests[testid]
            logger.info("consider %s", test.short_name())
            if self.should_skip(test):
                logger.info("  should be skipped")
                continue
            if self.test_finished(test, testinfo, slib):
                logger.info("  finished")
                continue
            if slib.route_available(test, testinfo):
                (theroute, _) = slib.pick_route(test, testinfo)
                if theroute is None:
                    logger.info("  still no route")
                    continue
                logger.info("  runnable")
            else:
                logger.info("  no route")

    def pick_continuous_test(self, curr_state, slib):
        picked = None
        picked_info = None
        for testid in self.tests:
            testinfo = self.testinfo[testid]
            test = self.tests[testid]
            if self.test_finished(test, testinfo, slib):
                continue
            if self.should_skip(test):
                continue
            if not self.test_usable(test, curr_state):
                continue
            if testinfo.finished(curr_state):
                continue
            # if a test is failed before, don't pick it
            # ensure that for the 2nd fail, you are starting clean
            if testinfo.fails > 0:
                continue
            if self.better_test(test, testinfo, None, picked, picked_info, None):
                picked = test
                picked_info = testinfo

        if picked is not None:
            logger.info("CONTINUE '%s:%s'", picked.feature_name, picked.name)
        else:
            logger.info("nothing picked continuously")
        return picked

    def pick_test_for_screen(self, screen):
        tests = []
        for testid in self.tests:
            test = self.tests[testid]
            if test.get_screen() == screen:
                tests.append(test)
        return tests

    def better_test(self, newtest, newtest_info, newroute,
                    oldtest, oldtest_info, oldroute):
        # TODO: better method to select test
        if oldtest is None:
            self.better_reason = "first"
            return True

        # delay tests which affect server state
        if (newtest.has_tag('affect_server_state') and
                not oldtest.has_tag('affect_server_state')):
            return False
        if (not newtest.has_tag('affect_server_state') and
                oldtest.has_tag('affect_server_state')):
            self.better_reason = "does not affect server state"
            return True

        # prefer tests with higher success rate
        # new test has highest success rate
        if newtest_info.succ_rate() > oldtest_info.succ_rate():
            self.better_reason = "high succ rate"
            return True
        elif newtest_info.succ_rate() < oldtest_info.succ_rate():
            return False

        if newtest.prio > oldtest.prio:
            self.better_reason = "high prio"
            return True
        if newtest.prio < oldtest.prio:
            return False

        if oldroute is not None and newroute is not None:
            # prefer tests whose routes do not change server state
            if (not newroute.has_tag('affect_server_state') and
                oldroute.has_tag('affect_server_state')):
                return True
            elif (newroute.has_tag('affect_server_state') and not
                  oldroute.has_tag('affect_server_state')):
                return False

            # prefer tests with short routes
            if newroute.length() > oldroute.length():
                return False
            elif newroute.length() < oldroute.length():
                self.better_reason = "shorter"
                return True

        return False

    def same_state(self, state_a, state_b):
        for cond in self.merged_conds:
            if cond.check(state_a) != cond.check(state_b):
                return False
        return True

    def mark_succ(self, test, from_screen, to_screen):
        testinfo = self.testinfo[test.get_id()]
        testinfo.mark_succ(from_screen, to_screen)

    def mark_fail(self, test, screen):
        testinfo = self.testinfo[test.get_id()]
        testinfo.mark_fail(screen)
        if testinfo.finished(screen):
            logger.info("over limit. completely failed.")

        self.fail_reason[screen] = self.fail_reason.get(screen, []) + [test.get_id()]

    def mark_error(self, test):
        testinfo = self.testinfo[test.get_id()]
        testinfo.mark_error()
        if testinfo.finished(None):
            logger.info("over limit. completely failed.")

    def clear_stat(self, test):
        testinfo = self.testinfo[test.get_id()]
        testinfo.clear()

    def test_available(self, slib):
        for testid in self.tests:
            if self.should_skip(self.tests[testid]):
                continue

            test = self.tests[testid]
            testinfo = self.testinfo[testid]
            if self.test_finished(test, testinfo, slib):
                continue
            return True
        return False

    def vindicate(self, screen):
        for test_id in self.fail_reason.get(screen, []):
            self.testinfo[test_id].vindicate(screen)

    def print_stat(self, simple=False):
        logger.info("=== test results ===")
        test_succ = test_fail = test_norun = test_flaky = 0
        usable_test = []
        flaky_test = []
        failonly_test = []
        unreached_test = []
        for testid in self.tests:
            test = self.tests[testid]
            testinfo = self.testinfo[testid]

            if self.should_skip(self.tests[testid]):
                continue
            if test.meta:
                continue

            if simple and testinfo.succs > 0:
                logger.info("  %s: %d+ %d- ->%s", test.short_name(), testinfo.succs,
                            testinfo.fails, list(testinfo.reached_screens.keys()))
            logger.debug("test %s:'%s': %d+ %d- %d!",
                         test.feature_name, test.name, testinfo.succs, testinfo.fails,
                         testinfo.error)
            if testinfo.succs > 0:
                if testinfo.fails > 0:
                    test_flaky += 1
                    flaky_test.append(test)
                else:
                    test_succ += 1
                    usable_test.append(test)
            elif testinfo.fails > 0:
                test_fail += 1
                failonly_test.append(test)
            else:
                test_norun += 1
                unreached_test.append(test)

        unfinished_conds = set()
        for testid in self.tests:
            if self.only_tagged:
                skip = True
                for tag in self.only_tagged:
                    if self.tests[testid].has_tag(tag):
                        skip = False
                        break
                if skip:
                    continue

            if self.testinfo[testid].unreached():
                unfinished_conds.add(self.tests[testid].conds_str())

        if not simple:
            for cond_str in unfinished_conds:
                logger.info("UNREACHED COND: %s", cond_str)

            for test in usable_test:
                logger.info("USABLE: %s:'%s'", test.feature_name, test.name)

            for test in flaky_test:
                testinfo = self.get_testinfo(test)
                logger.info("FLAKY:  %s:'%s' %d+ %d-", test.feature_name, test.name,
                            testinfo.succs, testinfo.fails)

            for test in failonly_test:
                logger.info("FAILED: %s:'%s'", test.feature_name, test.name)

            for test in unreached_test:
                logger.debug("NOIDEA: %s:'%s'", test.feature_name, test.name)

        logger.info("TOTAL: %d+ %d* %d- %d?",
                    test_succ, test_flaky, test_fail, test_norun)

        total_route = 0
        for key in self.route_cache:
            total_route += len(self.route_cache[key])

        logger.info("cached state pairs: %d cached routes: %d", len(self.route_cache),
                    total_route)

        for prop in self.cleaner_cache:
            logger.info("cleaner for %s: %s", prop, self.cleaner_cache[prop])

    def save_memory(self, memory_obj):
        memory = {}
        tests = []
        for testid in self.tests:
            test = self.tests[testid]
            testinfo = self.testinfo[testid]

            mem_test = {}
            mem_test['id'] = testid
            mem_test['feature'] = test.feature_name
            mem_test['name'] = test.name

            testinfo.save_obj(mem_test)

            tests.append(mem_test)

        memory['tests'] = tests

        mem_cache = []
        for key in self.route_cache:
            from_state, to_state = key
            mem_entry = {'from': from_state.to_obj(), 'to': to_state.to_obj()}

            mem_routes = []
            for aroute in self.route_cache[key]:
                mem_routes.append(aroute.to_obj())
            mem_entry['routes'] = mem_routes

            mem_cache.append(mem_entry)
        memory['cache'] = mem_cache

        memory_obj['testlib'] = memory

    def load_memory(self, memory_obj):
        memory = memory_obj['testlib']

        tests = memory['tests']
        htests = {}
        for mem_test in tests:
            key = "%s:%s" % (mem_test['feature'], mem_test['name'])
            htests[key] = mem_test

        for testid in self.tests:
            test = self.tests[testid]
            testinfo = self.testinfo[testid]
            key = "%s:%s" % (test.feature_name, test.name)
            if key in htests:
                mem_test = htests[key]
                if (config.recall_fails or
                    mem_test['succs'] > 0 and mem_test['fails'] == 0):
                    # good test!
                    testinfo.load_obj(mem_test)

        for entry in memory.get('cache', []):
            from_state = state.State.from_obj(entry['from'])
            to_state = state.State.from_obj(entry['to'])
            key = (from_state, to_state)

            self.route_cache[key] = []
            for mem_route in entry['routes']:
                self.route_cache[key].append(route.Route.from_obj(mem_route, self))

        return memory

    def save_stat(self, filename):
        data = statinfo.load_statfile(filename)
        for testid in self.tests:
            test = self.tests[testid]
            testinfo = self.testinfo[testid]

            key = "%s %s" % (test.feature_name, test.name)
            if (key not in data or
                    testinfo.fails == 0 and testinfo.succs > 0 or
                    testinfo.fails > 0 and testinfo.succs == 0):
                data[key] = [testinfo.succs, testinfo.fails]
            else:
                data[key][0] += testinfo.succs
                data[key][1] += testinfo.fails

        statf = open(filename, 'w')
        for key in data:
            statf.write("%d %d @%s\n" % (data[key][0], data[key][1], key))
        statf.close()

    def erase_memory(self, feature_name, test_name):
        test = self.find_test(feature_name, test_name)
        if test is None:
            logger.error("cannot find test %s:%s to erase", feature_name, test_name)
            return
        testinfo = self.get_testinfo(test)
        testinfo.clear()

    def load_stat(self, filename):
        data = statinfo.load_statfile(filename)
        for key in data:
            for testid in self.tests:
                test = self.tests[testid]
                if "%s %s" % (test.feature_name, test.name) == key:
                    if data[key][0] > 0 and data[key][1] == 0:
                        # good test!
                        test.init_prio += 20

    def set_onlytagged(self, only_tagged):
        self.only_tagged = only_tagged

    def synthesis_test(self, test, try_count=1, unclean_change=True):
        target_state = state.State()
        test.model_state(target_state)
        return self.synthesis(target_state, try_count=try_count,
                              unclean_change=unclean_change)

    def synthesis(self, target_state, init_state=state.State({'screen': 'init'}),
                  try_count=1, unclean_change=True):
        logger.info("synthesis try: %d unclean: %s", try_count, unclean_change)
        logger.info("init state: %s", init_state)
        logger.info("target state: %s", target_state)

        if target_state.matches(init_state):
            return [route.Route()]

        methods = self.synthesis_attempt(target_state, init_state, no_failed=True,
                                         try_count=try_count,
                                         unclean_change=unclean_change)
        if len(methods) < try_count:
            methods2 = self.synthesis_attempt(target_state, init_state, no_failed=False,
                                              try_count=try_count - len(methods),
                                              unclean_change=unclean_change)
            for method2 in methods2:
                found = False
                for method in methods:
                    if str(method) == str(method2):
                        found = True
                        break
                if not found:
                    methods.append(method2)

        logger.info("synthesis rets: %d", len(methods))
        for method in methods:
            logger.info("\t%s", method)
        return methods

    def synthesis_attempt(self, target_state, init_state, no_failed, try_count,
                          unclean_change):
        results = []
        depth = 0
        #queue = [{'state': target_state, 'ops': []}]
        queue = [{'state': init_state, 'ops': []}]
        qh = 0
        qe = 1
        finished = False
        reached_states = {}
        while qh < qe and not finished and depth < DEPTH_LIMIT:
            depth += 1
            logger.debug("depth %d length %d", depth, qe)
            for qi in range(qh, qe):
                queue_entry = queue[qi]
                #to_state = queue_entry['state']
                from_state = queue_entry['state']

                for testid in self.tests:
                    test = self.tests[testid]
                    testinfo = self.testinfo[testid]

                    if not self.test_usable(test, from_state):
                        continue

                    if testinfo.fails > 0 and no_failed:
                        continue

                    if not unclean_change:
                        changed = False
                        for prop in config.must_cleanup_keys:
                            if prop in test.get_change_keys():
                                changed = True
                                break
                        if changed:
                            continue

                    # pre-cond matches, possible
                    to_state = copy.deepcopy(from_state)

                    test.change_state(to_state)

                    to_scrname = test.get_post_cond('screen')
                    if to_scrname is None:
                        to_scrname = testinfo.get_most_reached()

                    if to_scrname is None:
                        # we don't know which screen this would lead us to
                        # usually the test has not been execed
                        # just terminate here
                        to_state.remove('screen')
                    else:
                        to_state.set('screen', to_scrname)

                    # TODO: incorrect, routes may fail
                    if (to_state != from_state and
                        (reached_states.get(to_state, 0) <
                         config.SYNTHESIS_STATE_REP or
                         target_state.matches(to_state))):
                        reached_states[to_state] = reached_states.get(to_state, 0) + 1
                        new_ops = copy.deepcopy(queue_entry['ops'])
                        new_ops.append(test)
                        new_entry = {'state': to_state, 'ops': new_ops}
                        queue.append(new_entry)

                        #if from_state.is_essential(init_state):
                        logger.debug("%s [%s] -> %s", from_state, test.name, to_state)
                        if target_state.matches(to_state):
                            results.append(route.Route(new_ops))

                        if len(results) == try_count:
                            finished = True
                            break

                        if len(queue) > SYNTHESIS_QUEUE_LIMIT:
                            return None

                if finished:
                    break

            qh = qe
            qe = len(queue)

        return results

    def handle_sys_screen(self, curr_state, dev, observer):
        # disable interrupt
        new_screen = curr_state.get('screen')
        if new_screen is None:
            return False

        if new_screen in self.handling_sys:
            logger.info("currently handling %s", new_screen)
            return False

        if new_screen.startswith('sys_') or new_screen.startswith('app_'):
            # system screen, bypass it
            logger.info("sys/app screen %s detected", new_screen)
            sys_tests = self.pick_test_for_screen(new_screen)
            sys_succd = False
            for sys_test in sys_tests:
                logger.info("handle %s with '%s'", new_screen, sys_test.name)
                self.handling_sys.add(new_screen)
                try:
                    sys_succd = sys_test.attempt(dev, observer, curr_state, self)
                finally:
                    self.handling_sys.remove(new_screen)
                if sys_succd:
                    logger.info("%s handled", new_screen)
                    break
            if not sys_succd:
                logger.warning("found sys screen but test can't handle it?")
                #raise Exception("Unhandled sys/app screen: %s" % new_screen)
                # heck, just press back button
#                operation.back_op.do(dev, observer, curr_state, environ.Environment(),
#                                     self)
            # state updated to after sys screen
            # maybe sys screen again! disallowed above, so handling required
            return True

        return False

    def handle_dialog(self, curr_state, dev, observer):
        if self.disallow_dialog:
            return False

        if curr_state.get('tree', None) is None:
            return False
        tree = curr_state.get('tree')
        ret = dialog.detect_dialog(tree)
        if not ret[0]:
            return False

        # sometimes pop up slowly
        dev.wait_idle()
        gui_state = observer.grab_state(dev, no_img=True)
        curr_state.merge(gui_state)
        tree = curr_state.get('tree')
        ret = dialog.detect_dialog(tree)
        if not ret[0]:
            return False

        logger.info("dialog detected")
        buttonsid = ret[1]

        if len(buttonsid) == 1:
            logger.info("single button dialog")
            # what else can you do?
            loc = locator.itemid_locator(buttonsid[0])
            op = operation.Operation("click", loc)
            ret = op.do(dev, observer, curr_state, environ.empty, self)
            gui_state = observer.grab_state(dev)
            curr_state.merge(gui_state)
            return ret

        if len(buttonsid) == 0:
            logger.info("no buttons")
            return False

        types = {}
        for buttonid in buttonsid:
            logger.info("%s", util.describe_node(tree[buttonid], short=True))
            button_type = dialog.detect_dialog_button(tree, buttonid, buttonsid)
            if button_type is None:
                return False
            types[button_type] = buttonid

        action_to_do = dialog.decide_dialog_action(tree)
        logger.info("types: %s,  decide to click %s", types, action_to_do)
        if action_to_do in types:
            loc = locator.itemid_locator(types[action_to_do])
            op = operation.Operation("click", loc)
            ret = op.do(dev, observer, curr_state, environ.empty, self)
            gui_state = observer.grab_state(dev)
            curr_state.merge(gui_state)
            return ret
        else:
            logger.info("can't find the decided action")
            return False

    def find_test(self, feature_name, testname):
        for testid in self.tests:
            test = self.tests[testid]
            if test.name == testname and test.feature_name == feature_name:
                return test
        return None

    def assume_reached(self, feature_name, testname, screen):
        test = self.find_test(feature_name, testname)
        if test is not None:
            test.add_expect_eq('screen', screen)

    def get_reached(self, test):
        testinfo = self.testinfo[test.get_id()]
        return testinfo.get_most_reached()

    def record_route_succ(self, from_state, to_state, aroute):
        key = (from_state, to_state)
        for oldroute in self.route_cache.get(key, []):
            if str(oldroute) == str(aroute):
                return
        self.route_cache[key] = self.route_cache.get(key, []) + [aroute]

    def query_cache(self, from_state, to_state):
        return self.route_cache.get((from_state, to_state), [])

    def load_skip(self, filename):
        if os.path.exists(filename):
            for line in open(filename):
                self.skip_tests.add(line.strip())

    def test_from_obj(self, obj):
        return self.find_test(obj['feature'], obj['name'])

    def __str__(self):
        ret = "testlib (\n"
        for testid in self.tests:
            if not self.should_skip(self.tests[testid]):
                ret += "%s %s\n" % (self.tests[testid], self.testinfo[testid])
        for prop in self.observers:
            ret += "  observe(%s) (\n" % prop
            for observer in self.observers[prop]:
                ret += "    %s\n" % observer
            ret += "  )"
        ret += ")"
        return ret


def collect_pieces(tlibpath):
    logger.debug("collecting tests from %s", tlibpath)
    tlib = Testlib()

    for filename in glob.glob(os.path.join(tlibpath, "*.feature")):
        try:
            tests = tlibparser.parse_feature_file(filename)
        except:
            logger.error("fail to parse %s", filename)
            raise
        for test in tests:
            tlib.add_test(test)

    return tlib


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import value
    value.init_params("../etc/", "cui")
    import sys
    if len(sys.argv) > 1:
        tlibpath = sys.argv[1]
    else:
        tlibpath = "../tlib/"
    tlib = collect_pieces(tlibpath)
    print(tlib)
    tlib.print_stat()
    tlib.add_test(microtest.init_test("testapp"))
    tlib.assume_reached('meta', 'start app', 'main')
    tlib.assume_reached('signin', 'login', 'main')
#    for testid in tlib.tests:
#        test = tlib.tests[testid]
#        methods = tlib.synthesis_test(test, try_count=5)
#        logger.info("TEST %s:", test.name)
#        for method in methods:
#            logger.info("%s", route.Route(method))

    for prop in tlib.observers:
        for observer in tlib.get_observers(prop):
            methods = tlib.synthesis_test(observer, try_count=1, unclean_change=False)
            logger.info("OBSERVER %s:", observer.name)
            for method in methods:
                logger.info("%s", method)
