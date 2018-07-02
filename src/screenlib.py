# data: essential state -> [route+]

import logging

import state
import route
import perfmon
import config
import progress
import util

logger = logging.getLogger("screenlib")


class RouteInfo(object):
    def __init__(self, route, state):
        self.route = route
        self.state = state
        self.succ = 0
        self.fail = 0

    def succ_rate(self):
        if self.fail + self.succ == 0:
            return 50
        else:
            return self.succ * 100 / (self.succ + self.fail)

    def length(self):
        return self.route.length()

    def time(self):
        return perfmon.get_avg_time("route", "%r" % self.route)

    def mark_fail(self):
        self.fail += 1

    def mark_succ(self):
        self.succ += 1

    def __str__(self):
        #        ret = "route(%s) [\n" % self.state
        #        ret = "route ["
        ret = "%s" % self.route
        ret += " %d+ %d- |%d|" % (self.succ, self.fail, self.length())
        if self.time():
            ret += " %.3f" % self.time()
        return ret

    def to_obj(self):
        return {"succ": self.succ, "fail": self.fail}

    @staticmethod
    def from_obj(obj, route, state):
        self = RouteInfo(route, state)
        self.succ = obj['succ']
        self.fail = obj['fail']
        return self


class ScreenInfo(object):
    def __init__(self):
        self.succ = 0
        self.fail = 0

    def mark_fail(self):
        self.fail += 1

    def mark_succ(self):
        self.succ += 1

    def always_fail(self):
        return self.succ == 0 and self.fail > 0

    def reset(self):
        self.succ = 0
        self.fail = 0

    def to_obj(self):
        return {"succ": self.succ, "fail": self.fail}

    @staticmethod
    def from_obj(obj):
        inst = ScreenInfo()
        inst.succ = obj['succ']
        inst.fail = obj['fail']
        return inst

    def merge(self, other):
        self.succ += other.succ
        self.fail += other.fail


class Screenlib(object):
    def __init__(self, essential_props):
        self.screens = {}
        self.next_id = 0
        self.essential_screens = []
        self.finished_screens = set()
        self.routeinfo = {}
        self.essential_props = essential_props
        self.screen_info = {}
        self.screen_ids = {}
        self.route_fails = self.route_succs = 0

        self.add_route(route.empty_route, state.init_state)

    def route_available(self, test, testinfo):
        for screen in self.screens:
            if test.usable(screen) and not testinfo.finished(screen):
                if self.screens[screen]:
                    for route_info in self.screens[screen]:
                        if route_info.fail >= config.ROUTE_FAIL_LIMIT:
                            continue
                        return True
        return False

    def add_route(self, route, state):
        self.next_id += 1
        route.set_id(self.next_id)
        routeinfo = RouteInfo(route, state)
        self.routeinfo[self.next_id] = routeinfo

        essential_state = state.to_essential(self.essential_props)

        if essential_state in self.screens:
            self.screens[essential_state].append(routeinfo)
            return
#        if tlib is not None:
#            for screen in self.screens:
#                if tlib.same_state(screen, state):
#                    self.screens[screen].append(routeinfo)
#                    return

        # new essential screen
        self.essential_screens.append(essential_state)
        screen_id = len(self.essential_screens) - 1
        self.screen_ids[essential_state] = screen_id
        self.screen_info[screen_id] = ScreenInfo()
        self.screens[essential_state] = [routeinfo]

    def pick_better_route(self, screen, picked, unclean_change):
        changed = False
        for saved_route_info in self.screens[screen]:
            if not unclean_change:
                if saved_route_info.route.is_unclean():
                    continue
            if self.better_route(saved_route_info, picked):
                picked = saved_route_info
                changed = True
        if changed:
            return picked
        else:
            return None

    def pick_route_for_screen(self, target, unclean_change):
        picked = None
        for screen in self.screens:
            if target.matches(screen):
                newpicked = self.pick_better_route(screen, picked, unclean_change)
                if newpicked is not None:
                    picked = newpicked
        if picked is None:
            return None
        else:
            return picked.route

    def no_route(self, target, unclean_change=True):
        route = self.pick_route_for_screen(target, unclean_change)
        return route is None

    def pick_route(self, test, testinfo=None, unclean_change=True):
        picked = None
        target_state = None
        for screen in self.screens:
            if test.usable(screen) and (
                    testinfo is None or not testinfo.finished(screen)):
                progress.report_progress(
                    "    consider screen %s for test %s" % (screen, test.short_name()))
                newpicked = self.pick_better_route(screen, picked, unclean_change)
                if newpicked is not None:
                    progress.report_progress(
                        "      select %s for %s" % (newpicked, self.better_reason))
                    picked = newpicked
                    target_state = screen

        if picked is not None:
            return (picked.route, target_state)
        else:
            return (None, None)

    def better_route(self, newroute, oldroute):
        if newroute.fail >= config.ROUTE_FAIL_LIMIT:
            return False

        if oldroute is None:
            self.better_reason = "first"
            return True

        # compare length
        if oldroute.length() > newroute.length():
            self.better_reason = "shorter"
            return True
        if oldroute.length() < newroute.length():
            return False

        # compare succ rate
        if oldroute.succ_rate() < newroute.succ_rate():
            self.better_reason = "higher succ rate"
            return True
        if newroute.succ_rate() < oldroute.succ_rate():
            return False

        # compare time
        if oldroute.time() is not None and newroute.time() is not None:
            if oldroute.time() < newroute.time() - 1:
                return False
            if oldroute.time() > newroute.time() + 1:
                self.better_reason = "faster"
                return True

        return False

    def get_essential_screen(self, idx):
        if idx < len(self.essential_screens):
            return self.essential_screens[idx]
        else:
            return None

    def get_route_by_state(self, screen):
        picked = None
        if screen in self.screens:
            for saved_route_info in self.screens[screen]:
                if self.better_route(saved_route_info, picked):
                    picked = saved_route_info
        return picked.route

    def mark_route_fail(self, route):
        self.route_fails += 1
        routeid = route.get_id()
        self.routeinfo[routeid].mark_fail()

    def mark_route_succ(self, route):
        self.route_succs += 1
        routeid = route.get_id()
        self.routeinfo[routeid].mark_succ()

    def mark_state_finished(self, state_id):
        self.finished_screens.add(state_id)

    def is_state_finished(self, state_id):
        return state_id in self.finished_screens

    def get_screen_info(self, state_id):
        return self.screen_info[state_id]

    def mark_state_unknown(self, screen):
        # mark all the routes unknown and reinsert them
        for routeinfo in self.screens[screen]:
            full_state = routeinfo.state
            curr_route = routeinfo.route
            full_state.set('screen', 'WRONG')
            self.add_route(curr_route, full_state)

        del self.screens[screen]

    def check_state_perf(self, state_id, tlib):
        screen_info = self.get_screen_info(state_id)
        if screen_info.always_fail():
            screen = self.get_essential_screen(state_id)
            logger.info("screen %s always fails, mark it as unknown", screen)
            self.mark_state_unknown(screen)
            tlib.vindicate(screen)
            screen_info.reset()
            return False
        return True

    def check_screens(self, tlib):
        for i in range(len(self.essential_screens)):
            if i in self.screen_info:
                self.check_state_perf(i, tlib)

    def should_explore(self, state_id):
        if self.is_state_finished(state_id):
            return False

        screen = self.get_essential_screen(state_id)
        if screen.is_unknown():
            return True

        return False

    def get_screen_id(self, screen):
        return self.screen_ids.get(screen, -1)

    def mark_screen_succ(self, state):
        essential = state.to_essential(self.essential_props)
        screen_id = self.get_screen_id(essential)
        if screen_id == -1:
            logger.warn("mark_screen_succ: no such screen")
            return
        screen_info = self.get_screen_info(screen_id)
        screen_info.mark_succ()

    def mark_screen_fail(self, state):
        essential = state.to_essential(self.essential_props)
        screen_id = self.get_screen_id(essential)
        if screen_id == -1:
            logger.warn("mark_screen_fail: no such screen")
            return
        screen_info = self.get_screen_info(screen_id)
        screen_info.mark_fail()

    def not_seen(self, screen):
        # assuming screen is essential
        return screen not in self.essential_screens

    def __str__(self):
        ret = "Screenlib:\n"
        for screen in self.screens:
            ret += "screen (%s):\n" % screen
            try:
                for routeinfo in self.screens[screen]:
                    ret += "\t%s\n" % routeinfo
            except:
                ret += " !!ERROR!!"
#        ret += ")"
        return ret

    def print_stat(self, simple=False):
        logger.info("=== reachable screens ===")
        for screen in self.screens:
            screen_id = self.get_screen_id(screen)
            if screen_id == -1:
                continue
            screen_info = self.get_screen_info(screen_id)
            routeinfos = self.screens[screen]
            logger.info("%d. %s routes: %d [%d+ %d-]" % (
                screen_id, screen, len(routeinfos), screen_info.succ, screen_info.fail))
            route = self.pick_route_for_screen(screen, True)
            if route:
                logger.info("best route: %s", route)
            else:
                logger.info("  NO ROUTE!")
                for routeinfo in routeinfos:
                    logger.info("  %d. %s", routeinfo.route.get_id(), routeinfo)

        if self.route_succs + self.route_fails > 0:
            logger.info("ROUTE STAT: %d+ %d-", self.route_succs, self.route_fails)

    def query_screen(self, attrs):
        for screen in self.screens:
            match = True
            for key in attrs:
                if util.unequal(attrs[key], screen.get(key, '')):
                    match = False
                    break
            if not match:
                continue

            screen_id = self.get_screen_id(screen)
            if screen_id == -1:
                continue
            screen_info = self.get_screen_info(screen_id)
            routeinfos = self.screens[screen]
            logger.info("%s #%d routes: %d [%d+ %d-]" % (
                screen, screen_id, len(routeinfos), screen_info.succ, screen_info.fail))
            route = self.pick_route_for_screen(screen, True)
            if route:
                logger.info("  best route: %s", route)
            else:
                logger.info("  NO ROUTE!")

            for routeinfo in routeinfos:
                logger.info("  %d. %s", routeinfo.route.get_id(), routeinfo)

    def reset_route(self, route_no):
        if route_no in self.routeinfo:
            routeinfo = self.routeinfo[route_no]
            routeinfo.fail = 0
            logger.info("reset %s", routeinfo.route)
            return True
        else:
            logger.error("route #%d not found", route_no)
            return False

    def save_memory(self, memory_obj):
        memory = {}

        mem_screens = []
        for screen in self.screens:
            screen_id = self.get_screen_id(screen)
            if screen_id == -1:
                continue
            screen_info = self.get_screen_info(screen_id)
            routeinfos = self.screens[screen]

            # screen_id: id
            # screen: key, essential screen
            # screen_info: ScreenInfo
            # routeinfos: routes

            mem_screen = {}
            mem_screen['id'] = screen_id
            mem_screen['screen'] = screen.to_obj()
            mem_screen['info'] = screen_info.to_obj()

            mem_routes = []
            for routeinfo in routeinfos:
                mem_route = {}
                mem_route['info'] = routeinfo.to_obj()
                mem_route['route'] = routeinfo.route.to_obj()
                mem_route['state'] = routeinfo.state.to_obj()
                mem_routes.append(mem_route)

            mem_screen['routes'] = mem_routes
            mem_screens.append(mem_screen)

        memory['screens'] = mem_screens
        memory['nextid'] = self.next_id

        mem_essential_screens = []
        for screen in self.essential_screens:
            mem_essential_screens.append(screen.to_obj())
        memory['essentials'] = mem_essential_screens
        mem_finish = []
        for screen in self.finished_screens:
            mem_finish.append(screen.to_obj())
        memory['finished'] = mem_finish

        memory_obj['screenlib'] = memory
        return memory

    def load_memory(self, memory_obj, tlib):
        memory = memory_obj['screenlib']

        for mem_screen in memory['screens']:
            screen_id = mem_screen['id']
            screen = state.State.from_obj(mem_screen['screen']).to_essential(
                self.essential_props)
            screen_info = ScreenInfo.from_obj(mem_screen['info'])

            routeinfos = []
            for mem_route in mem_screen['routes']:
                aroute = route.Route.from_obj(mem_route['route'], tlib)
                if aroute is None:
                    # tests may be missing
                    continue
                astate = state.State.from_obj(mem_route['state'])
                routeinfo = RouteInfo.from_obj(mem_route['info'], aroute, astate)
                route_id = aroute.get_id()
                self.routeinfo[route_id] = routeinfo
                routeinfos.append(routeinfo)

            if screen in self.screens:
                # already recorded
                self.screens[screen] += routeinfos
                screen_id = self.screen_ids[screen]
                self.screen_info[screen_id].merge(screen_info)
            else:
                self.screens[screen] = routeinfos
                self.screen_info[screen_id] = screen_info
                self.screen_ids[screen] = screen_id

        self.next_id = memory['nextid']
        self.essential_screens = []
        for mem_screen in memory['essentials']:
            self.essential_screens.append(state.State.from_obj(mem_screen))
        self.finished_screens = set()
        for mem_screen in memory['finished']:
            self.finished_screens.add(state.State.from_obj(mem_screen))

        return memory
