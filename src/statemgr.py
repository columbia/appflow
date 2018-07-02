#!/usr/bin/env python3

import logging

import environ
import config
import state
import route
import operation
import progress
import perfmon
import util

logger = logging.getLogger("statemgr")


class StateMgr(object):
    def __init__(self, tlib, slib, dev, observer, watchdog):
        self.tlib = tlib
        self.slib = slib
        self.dev = dev
        self.observer = observer
        self.watchdog = watchdog
        self.ob_succ = self.ob_fail = 0
        self.ob_route_succ = 0
        self.ob_syn_succ = 0
        self.clean_succ = self.clean_fail = 0
        self.ob_prep_succ = self.ob_prep_fail = 0
        self.clean_prep_succ = self.clean_prep_fail = 0
        self.clean_all_succ = self.clean_all_fail = 0
        self.clean_route_succ = self.clean_synth_succ = self.clean_once_succ = 0
        self.cleaner_succ = self.cleaner_fail = 0
        self.good_cleaners = {}

    def observe(self):
        return self.observer.grab_state(self.dev)

    def report_prog(self, prog):
        progress.report_progress(prog)

    def replay_route(self, route, curr_state):
        try:
            ret = route.replay(self.dev, curr_state, self.observer, self.tlib)
        except:
            logger.exception("replay route exception")
            ret = False

        if not ret:
            logger.warning("replay route failed")
            if self.slib is not None:
                self.slib.mark_route_fail(route)
        else:
            logger.info("route replayed")
            if self.slib is not None:
                self.slib.mark_route_succ(route)

        return ret

    @perfmon.op("statemgr", "init_clean")
    def init_clean(self):
        logger.info("ensuring that the environment is clean")
        for prop in config.must_cleanup_keys:
            self.observe_and_clean(prop)
        logger.info("env cleaned")

    @perfmon.op("statemgr", "observe_and_clean_all")
    def observe_and_clean_all(self, curr_state):
        """ Observe and clean every property """
        for prop in config.must_cleanup_keys:
            self.observe_and_clean(prop, curr_state)

    def prepare_input_state(self, curr_state):
        input_state = state.State()
        if curr_state is not None:
            for key in config.cleanup_dep_keys:
                if util.unequal(curr_state.get(key, ''), ''):
                    input_state.set(key, curr_state.get(key))
        return input_state

    @perfmon.op("statemgr", "observe_and_clean")
    def observe_and_clean(self, prop, curr_state=None):
        """ `prop` may be dirty / not dirty, need to observe and clear if necessary """
        logger.info("checking if prop %s should be observed & cleared", prop)
        if not self.check_dep(curr_state):
            logger.info("no dep, no need to clean")
            return True
        else:
            logger.info("prop %s should be observed", prop)

        self.report_prog("OBSERVE and CLEAN %s" % prop)
        input_state = self.prepare_input_state(curr_state)
        if self.observe_prop(prop, input_state):
            # state observed
            if not util.is_def_val(input_state.get(prop, '')):
                # we need to clean it
                logger.info("yes, prop %s should be cleared", prop)
                return self.cleanup_prop(prop, input_state.get(prop), input_state)
            else:
                return True
        else:
            logger.error("possible property changed! %s ???", prop)
            return False

    def cleanup_from_full_synth(self, prop, init_state, curr_state, try_count, lead):
        target_state = state.State({prop: ''})
        self.add_dep_keys(curr_state, target_state)

        methods = self.tlib.query_cache(init_state, target_state)
        if len(methods) < try_count:
            methods += self.tlib.synthesis(target_state, init_state, try_count -
                                           len(methods))

        for method in methods:
            logger.info("way to cleanup %s: %s", prop, method)
            self.watchdog.kick()
            curr_state = self.observe()

            if not lead.replay(self.dev, curr_state, self.observer, self.tlib):
                continue

            if not method.replay(self.dev, curr_state, self.observer, self.tlib):
                logger.info("cleanup of %s error!", prop)
            else:
                logger.info("== prop %s cleaned ==", prop)
                curr_state.set(prop, '')
                self.tlib.record_route_succ(init_state, target_state, method)
                return True

        logger.info("== no method works! ==")
        return False

    @perfmon.op("statemgr", "cleanup_prop")
    def cleanup_prop(self, prop, val, curr_state):
        self.report_prog("CLEAN %s=%s" % (prop, val))
        logger.info("=== clearing prop %s, val %s ===", prop, val)
        gui_state = self.observe()
        curr_state.merge(gui_state)

        to_state = curr_state.filter_with(config.cleanup_dep_keys)

        logger.info("=== first, try to cleanup from current state ===")
        init_state = curr_state.to_essential(self.tlib.essential_props())
        init_state.set(prop, val)
        if self.cleanup_from_once(prop, init_state, curr_state):
            self.clean_succ += 1
            return True

        logger.info("=== can't cleanup from current state, cleanup from home ===")

        logger.info("== try route first ==")
        logger.info(" Clean prop %s from home" % prop)
        from_state = state.State({'screen': 'init', prop: val})
        if self.cleanup_from_route(prop, from_state, to_state, curr_state,
                                   try_count=config.CLEANUP_TRY_LIMIT):
            self.clean_succ += 1
            return True

        logger.info("== try synth next ==")
        if self.cleanup_from_synth(prop, from_state, to_state, curr_state,
                                   try_count=config.CLEANUP_SYNTH_TRY_LIMIT):
            self.clean_succ += 1
            return True

        logger.error("=== can't cleanup from home, give up ===")
        self.report_prog("Clean prop %s failed" % prop)
        print("  DIRTY! prop %s still dirty" % prop)
        self.clean_fail += 1
        return False

    def get_observer_states(self, prop, input_state):
        prep_observing_states = set()
        for observing_test in self.tlib.get_observers(prop):
            target_state = input_state.filter_with(config.cleanup_dep_keys)
            observing_test.model_state(target_state)
            prep_observing_states.add(target_state)

        return prep_observing_states

    def use_only_good(self, cleaners, good):
        if good is None:
            return cleaners
        return [good]

    def move_to_head(self, cleaners, good):
        """ Move `good` cleaner to the head of `cleaners` """
        if good is None:
            return
        for i in range(len(cleaners)):
            if cleaners[i].short_name() == good.short_name():
                del cleaners[i]
                cleaners.insert(0, good)
                return

    def good_cleaner(self, prop, cleaners):
        """ Find out the good cleaner in `cleaners` for `prop` """
        if prop in self.good_cleaners:
            good_cleaner = self.good_cleaners[prop]
            for cleaner in cleaners:
                if cleaner.short_name() == good_cleaner.short_name():
                    return good_cleaner
        return None

    def pick_cleaner(self, prop):
        cleaners = self.tlib.get_cleaners(prop)
        if cleaners == []:
            logger.error("no cleaner for %s!", prop)
            return None

        cleaner = self.good_cleaner(prop, cleaners)
        if cleaner is not None:
            return cleaner
        else:
            return cleaners[0]

    def remember_cleaner(self, prop, cleaner):
        self.good_cleaners[prop] = cleaner

    @perfmon.op("statemgr", "cleanup_from_once")
    def cleanup_from_once(self, prop, from_state, curr_state):
        cleaner = self.pick_cleaner(prop)
        target_state = from_state.filter_with(config.cleanup_dep_keys)
        cleaner.model_state(target_state)

        methods = self.tlib.query_cache(from_state, target_state)
        if len(methods) == 0:
            methods = self.tlib.synthesis(target_state, from_state, try_count=1,
                                          unclean_change=False)
        if len(methods) == 0:
            logger.error("can't synthesis or find a route to clean")
            return False

        method = methods[0]
        self.watchdog.kick()
        logger.info("prepare for clean once: using %s + %s", method, cleaner.short_name())
        if not method.replay(self.dev, curr_state, self.observer, self.tlib):
            logger.info("prepare failed")
            self.clean_prep_fail += 1
            return False

        self.clean_prep_succ += 1
        if not cleaner.attempt(self.dev, self.observer, curr_state, self.tlib):
            logger.info("cleaner failed")
            self.cleaner_fail += 1
            return False

        logger.info("synth once CLEANED %s!", prop)
        self.report_prog("  CLEANED at once with %s + %s" % (
            method, cleaner.short_name()))
        self.remember_cleaner(prop, cleaner)
        self.cleaner_succ += 1
        self.clean_once_succ += 1
        return True

    def get_cleaner_req(self, cleaners, curr_state):
        cleaner_reqs = set()
        for cleaner in cleaners:
            target_state = curr_state.filter_with(config.cleanup_dep_keys)
            cleaner.model_state(target_state)
            cleaner_reqs.add(target_state)
        return cleaner_reqs

    def cleanup_now(self, cleaners, target_state, method, curr_state, prop,
                    from_state=None):
        for cleaner in cleaners:
            if cleaner.usable(target_state):
                self.watchdog.kick()
                if not method.replay(self.dev, curr_state, self.observer, self.tlib):
                    logger.info("prepare failed")
                    # route fail, next route
                    self.clean_prep_fail += 1
                    break
                self.clean_prep_succ += 1
                if from_state is not None:
                    self.tlib.record_route_succ(from_state, target_state, method)
                logger.info("ready to clean: using %s", cleaner.short_name())
                if not cleaner.attempt(self.dev, self.observer, curr_state, self.tlib):
                    logger.info("cleaner failed")
                    self.report_prog("  cleaner fail: %s" % cleaner.short_name())
                    # route succ, cleaner fail: bad cleaner
                    self.cleaner_fail += 1
                    continue
                logger.info("cleanup %s succ with %s", prop, cleaner.short_name())
                self.report_prog("  cleaner succ: %s" % cleaner.short_name())
                self.remember_cleaner(prop, cleaner)
                self.tlib.record_cleaner(prop, cleaner)
                self.cleaner_succ += 1
                return True
        return False

    @perfmon.op("statemgr", "cleanup_from_route")
    def cleanup_from_route(self, prop, from_state, to_state, curr_state, try_count):
        if self.slib is None:
            return False

        cleaners = self.tlib.get_cleaners(prop)
        if cleaners == []:
            logger.error("no cleaner for %s!", prop)
            return False

        # first, try good cleaner
        good_cleaner = self.good_cleaner(prop, cleaners)
        #self.move_to_head(cleaners, good_cleaner)
        cleaners = self.use_only_good(cleaners, good_cleaner)

        cleaner_reqs = self.get_cleaner_req(cleaners, to_state)

        for target_state in cleaner_reqs:
            logger.info("target state: %s", target_state)
            orig_val = target_state.get(prop)
            target_state.set(prop, '')
            method = self.slib.pick_route_for_screen(target_state, False)
            target_state.set(prop, orig_val)
            if method is None:
                continue

            logger.info("prepare for clean with route: using %s", method)
            self.report_prog("  CLEAN WITH %s" % method)
            if self.cleanup_now(cleaners, target_state, method, curr_state, prop):
                self.clean_route_succ += 1
                return True

        logger.info("all cleaners failed")
        return False

    @perfmon.op("statemgr", "cleanup_from_synth")
    def cleanup_from_synth(self, prop, from_state, to_state, curr_state, try_count):
        cleaners = self.tlib.get_cleaners(prop)
        if cleaners == []:
            logger.error("no cleaner for %s!", prop)
            return False

        # first, try good cleaner
        good_cleaner = self.good_cleaner(prop, cleaners)
        #self.move_to_head(cleaners, good_cleaner)
        cleaners = self.use_only_good(cleaners, good_cleaner)

        cleaner_reqs = self.get_cleaner_req(cleaners, to_state)

        for target_state in cleaner_reqs:
            logger.info("target state: %s", target_state)
            methods = self.tlib.query_cache(from_state, target_state)
            if len(methods) < try_count:
                methods += self.tlib.synthesis(target_state, from_state,
                                               try_count=try_count - len(methods),
                                               unclean_change=False)

            for method in methods:
                logger.info("prepare for clean: using %s", method)
                print("  clean with synthesized %s" % method)
                if self.cleanup_now(cleaners, target_state, method, curr_state, prop,
                                    from_state):
                    self.clean_synth_succ += 1
                    return True

        logger.info("all cleaners failed")
        return False

    def observe_prop_now(self, prop, curr_state, target_state, input_state):
        for observing_test in self.tlib.get_observers(prop):
            if observing_test.usable(target_state):
                self.report_prog("  OBSERVING at %s with %s" % (
                    target_state, observing_test.short_name()))
                logger.info("OBSERVING %s using %s", prop, observing_test.name)
                if observing_test.attempt(self.dev, self.observer, curr_state,
                                          self.tlib):
                    observing_test.change_state(input_state)
                    logger.info("prop %s observed: '%s'", prop,
                                input_state.get(prop, ''))
                    return True
                else:
                    # route ok, test fail
                    # means that we require other observators
                    logger.info("OBSERVE prop %s FAILED using %s",
                                prop, observing_test.name)
        return False

    def observe_with_route(self, prop, input_state, prep_observing_states):
        if self.slib is None:
            return False

        for target_state in prep_observing_states:
            logger.info("target state: %s", target_state)
            route_to_observe = self.slib.pick_route_for_screen(target_state, False)
            if route_to_observe is None:
                continue

            self.watchdog.kick()
            logger.info("prepare for observe: using %s", route_to_observe)
            self.report_prog("OBSERVE %s through %s" % (prop, route_to_observe))
            curr_state = self.observe()
            if not self.replay_route(route_to_observe, curr_state):
                logger.info("fail to replay %s", route_to_observe)
                self.ob_prep_fail += 1
                continue
            self.ob_prep_succ += 1

            if self.observe_prop_now(prop, curr_state, target_state, input_state):
                self.ob_route_succ += 1
                return True
        return False

    def observe_with_synthesis(self, prop, input_state, prep_observing_states):
        for target_state in prep_observing_states:
            logger.info("target state: %s", target_state)
            methods = self.tlib.query_cache(state.init_state, target_state)
            if len(methods) < config.OBSERVE_TRY_LIMIT:
                methods += self.tlib.synthesis(
                    target_state, state.init_state,
                    try_count=config.OBSERVE_TRY_LIMIT - len(methods),
                    unclean_change=False)

            for method in methods:
                self.watchdog.kick()
                logger.info("prepare for observing using synthesised %s", method)
                curr_state = self.observe()
                route.empty_route.replay(self.dev, curr_state, self.observer, self.tlib)

                if not method.replay(self.dev, curr_state, self.observer, self.tlib):
                    logger.warn("fail to prepare with this route")
                    self.ob_prep_fail += 1
                    continue
                else:
                    self.ob_prep_succ += 1
                    self.tlib.record_route_succ(state.init_state, target_state, method)

                if self.observe_prop_now(prop, curr_state, target_state, input_state):
                    self.ob_syn_succ += 1
                    return True

        return False

    @perfmon.op("statemgr", "observe_prop")
    def observe_prop(self, prop, input_state):
        logger.info("=== observing %s on %s ===", prop, input_state)
        prep_observing_states = self.get_observer_states(prop, input_state)

        if self.observe_with_route(prop, input_state, prep_observing_states):
            self.ob_succ += 1
            return True

        logger.info("=== fail to observe using routes, try synthesis ===")
        if self.observe_with_synthesis(prop, input_state, prep_observing_states):
            self.ob_succ += 1
            return True

        logger.warning("=== fail to observe current state of prop %s ===", prop)
        self.ob_fail += 1
        return False

    def observe_val(self, prop, curr_state):
        if not self.observe_prop(prop, curr_state):
            return None

        return curr_state.get(prop, '')

    def check_dep(self, astate):
        for prop in config.cleanup_dep_keys:
            if util.unequal(astate.get(prop, ''), ''):
                return True
        return False

    def check_dirty(self, astate):
        if not self.check_dep(astate):
            return False
        for prop in config.must_cleanup_keys:
            if util.unequal(astate.get(prop, ''), ''):
                return True
        return False

    @perfmon.op("statemgr", "cleanup")
    def cleanup(self, curr_state):
        logger.info("round-end cleanup")

        if not self.check_dirty(curr_state):
            logger.info("not dirty")
            return True

        # all in one has logic problems
        #if self.cleanup_allinone(curr_state):
        #    self.clean_all_succ += 1
        #    return True

        dirty = {}
        for prop in config.must_cleanup_keys:
            if not util.is_def_val(curr_state.get(prop, '')):
                dirty[prop] = curr_state.get(prop)

        ret = True
        for prop in dirty:
            newval = self.observe_val(prop, curr_state)
            if newval is not None and util.is_def_val(newval):
                logger.info("prop %s already clean", newval)
                continue
            ret = ret and self.cleanup_prop(prop, dirty[prop], curr_state)
            if ret:
                logger.info("prop %s cleaned", prop)
            else:
                logger.warning("prop %s remains!", prop)

        if ret:
            self.clean_all_succ += 1
        else:
            self.clean_all_fail += 1
        return ret

    def add_dep_keys(self, curr_state, target_state):
        for key in config.cleanup_dep_keys:
            if curr_state.get(key, '') != '':
                target_state.set(key, curr_state.get(key))

    @perfmon.op("statemgr", "cleanup_allinone")
    def cleanup_allinone(self, curr_state):
        methods = []
        for i in range(config.CLEANUP_ALLINONE_BACK_LIMIT):
            init_state = curr_state.to_essential(self.tlib.essential_props())

            target_state = state.State()
            for key in config.must_cleanup_keys:
                if curr_state.get(key, '') != '':
                    target_state.set(key, '')
            self.add_dep_keys(curr_state, target_state)

            methods = self.tlib.synthesis(target_state, init_state)
            if methods != []:
                break

            operation.back_op.do(self.dev, self.observer, curr_state,
                                 environ.Environment(), self.tlib)

            gui_state = self.observer.grab_state(self.dev)
            curr_state.merge(gui_state)
            self.tlib.handle_dialog(curr_state, self.dev, self.observer)

            if curr_state.get('exited', False):
                logger.error("fail to find a route to cleanup!")
                return False

        if methods == []:
            logger.info("can't find a route to cleanup all in one")
            return False

        logger.info("start cleanup all in one")
        method = methods[0]
        logger.info("cleanup method: %s", method)

        self.watchdog.kick()
        if not method.replay(self.dev, curr_state, self.observer, self.tlib):
            logger.error("cleanup all in one error!")
            return False

        logger.info("cleanup finished")
        return True

    def save_memory(self, memory_obj):
        memory = {}

        mem_cleaners = {}
        for prop in self.good_cleaners:
            mem_cleaners[prop] = self.good_cleaners[prop].to_obj()
        memory['cleaners'] = mem_cleaners

        memory_obj['statemgr'] = memory
        return memory

    def load_memory(self, memory_obj):
        memory = memory_obj['statemgr']

        mem_cleaners = memory.get('cleaners', {})
        for prop in mem_cleaners:
            cleaner = self.tlib.test_from_obj(mem_cleaners[prop])
            if cleaner is not None:
                self.good_cleaners[prop] = cleaner
        return memory

    def print_stat(self, simple=False):
        logger.info("=== state manager ===")
        if not simple:
            logger.info("OBSERVE: %d+ %d-", self.ob_succ, self.ob_fail)
            logger.info("OB PREP: %d+ %d-", self.ob_prep_succ, self.ob_prep_fail)
            logger.info("OBroute: %d+", self.ob_route_succ)
            logger.info("OBsynth: %d+", self.ob_syn_succ)

            logger.info("CLEAN ALL: %d+ %d-", self.clean_all_succ, self.clean_all_fail)
            logger.info("CL PREP: %d+ %d-", self.clean_prep_succ, self.clean_prep_fail)
            logger.info("CLEANUP: %d+ %d-", self.clean_succ, self.clean_fail)
            logger.info("CL once: %d+", self.clean_once_succ)
            logger.info("CLroute: %d+", self.clean_route_succ)
            logger.info("CLsynth: %d+", self.clean_synth_succ)
            logger.info("CLEANER: %d+ %d-", self.cleaner_succ, self.cleaner_fail)

        for prop in self.good_cleaners:
            logger.info("CLEANER for %s: %s", prop, self.good_cleaners[prop].short_name())


def observe_clean_app(dev, app, prop):
    import watchdog
    wd = watchdog.Watchdog(100000)
    import observer
    ob = observer.Observer("../err/")
    ob.set_app(app)
    ob.load("../model/", "../guis/", "../guis-extra/", config.extra_screens,
            config.extra_element_scrs)
    import testlib
    tlib = testlib.collect_pieces("../tlib/")
    tlib.set_app(app)
    tlib.assume_reached('signin', 'login', 'main')
    tlib.assume_reached('welcome', 'skip sign in / sign up', 'main')
    ob.tlib = tlib
    import microtest
    tlib.add_test(microtest.init_test(appdb.get_app(app)))
    init = tlib.find_test('meta', 'start app')
    logger.info("start once first")
    init.attempt(dev, ob, state.State(), tlib, None)
    st = state.State({'loggedin': '1', prop: '1'})
    ob.update_state(dev, st)
    tlib.mark_succ(init, state.init_state, st)
    most_reached = tlib.get_reached(init)
    logger.info("start -> %s", most_reached)
    smgr = StateMgr(tlib, None, dev, ob, wd)
    logger.info("ready")
    ret = smgr.observe_and_clean(prop, st)
    if ret:
        logger.info("prop %s is clean now" % prop)
    else:
        logger.info("observe/clean error")


if __name__ == "__main__":
    import sys
    app = sys.argv[2]

    import logging
    logging.basicConfig(level=logging.INFO)

    import appdb
    appdb.collect_apps("../apks/")

    import value
    value.init_params("../etc/", app)

    import device
    dev = device.Device(serial=sys.argv[1])
    observe_clean_app(dev, app=sys.argv[2], prop=sys.argv[3])

    dev.finish()
