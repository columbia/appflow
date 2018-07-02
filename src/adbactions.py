"""
The sources are:
      mouse
      keyboard
      joystick
      touchnavigation
      touchpad
      trackball
      stylus
      dpad
      touchscreen
      gamepad

The commands and default sources are:
      text <string> (Default: touchscreen)
      keyevent [--longpress] <key code number or name> ... (Default: keyboard)
      tap <x> <y> (Default: touchscreen)
      swipe <x1> <y1> <x2> <y2> [duration(ms)] (Default: touchscreen)
      press (Default: trackball)
      roll <dx> <dy> (Default: trackball)
"""

import time
import logging
import re

import device
import locator
import app
import config
import widget
import analyze
import sense
import value

logger = logging.getLogger("adbactions")

action_funcs = {
    'text': lambda dev, observer, env, attr: text(dev, attr['str']),
    'tap': lambda dev, observer, env, attr: tap(dev, attr['x'], attr['y']),
    'longclick': lambda dev, observer, env, attr: longclick(dev, attr['x'], attr['y']),
    'back': lambda dev, observer, env, attr: back(dev),
    'enter': lambda dev, observer, env, attr: enter(dev),
    'home': lambda dev, observer, env, attr: home(dev),
    'swipe': lambda dev, observer, env, attr: swipe(dev, attr['x1'], attr['y1'],
                                                    attr['x2'], attr['y2']),
    # app
    'start': lambda dev, observer, env, attr: app.start(dev, attr['name']),
    'stop': lambda dev, observer, env, attr: app.stop(dev, attr['name']),
    'clear': lambda dev, observer, env, attr: app.clear(dev, attr['name']),
    'waitact': lambda dev, observer, env, attr: app.waitact(dev, attr['name']),

    'wait': lambda dev, observer, env, attr: wait(dev, attr['time']),
    'waitfor': lambda dev, observer, env, attr: waitfor(dev, attr['method'],
                                                        attr['value'], observer, env),
    'waitready': lambda dev, observer, env, attr: waitready(dev, observer),
    'waitidle': lambda dev, observer, env, attr: waitidle(dev),
    'seetext': lambda dev, observer, env, attr: seetext(dev, attr['str'], observer),
    'seein': lambda dev, observer, env, attr: seein(dev, attr['widget'], attr['str'],
                                                    observer),
    'increasing': lambda dev, observer, env, attr: increasing(dev, attr['widgets'],
                                                              observer),
    'decreasing': lambda dev, observer, env, attr: decreasing(dev, attr['widgets'],
                                                              observer),
    'select': lambda dev, observer, env, attr: select(dev, attr['target'], attr['value'],
                                                      observer, env),
    'scroll': lambda dev, observer, env, attr: scroll(dev, attr['direction'], observer),
    'scrollit': lambda dev, observer, env, attr: scrollit(dev, attr['widget'],
                                                          attr['direction'], observer),
    'clearfocused': lambda dev, observer, env, attr: clearfocused(dev, observer, env),
    'kbdaction': lambda dev, observer, env, attr: kbd_action(dev, observer, env),
    'kbdon': lambda dev, observer, env, attr: kbd_on(dev, observer, env),
    'kbdoff': lambda dev, observer, env, attr: kbd_off(dev, observer, env),
    'closekbd': lambda dev, observer, env, attr: close_kbd(dev),
}


def run_input(dev, cmd, args):
    args_str = ' '.join(map(lambda x: "'\"%s\"'" % str(x), args))
    cmd = "input %s %s" % (cmd, args_str)
    dev.run_adb_shell(cmd)
    return True


def text(dev, string):
    return run_input(dev, "text", [string])


def tap(dev, x, y):
    logger.info("tapping %d,%d", x, y)
    return run_input(dev, "tap", [x, y])


def longclick(dev, x, y, length=1500):
    return run_input(dev, "swipe", [x, y, x, y, length])


def back(dev):
    return run_input(dev, "keyevent", ["BACK"])


def enter(dev):
    return run_input(dev, "keyevent", ["ENTER"])


def home(dev):
    return run_input(dev, "keyevent", ["HOME"])


def delete(dev, count):
    return run_input(dev, "keyevent", ["DEL"] * count)


def forward_delete(dev, count):
    return run_input(dev, "keyevent", ["FORWARD_DEL"] * count)


def swipe(dev, x1, y1, x2, y2):
    return run_input(dev, "swipe", [x1, y1, x2, y2])


def kbd_on(dev, observer, env):
    st = observer.grab_state(dev, no_img=True)

    logger.info("enable soft keyboard")
    run_input(dev, "keyevent", ["SYM"])

    for retry in range(config.KBDSWITCH_LIMIT):
        loc = locator.const_locator("id", "hard_keyboard_switch")
        st = observer.grab_state(dev, no_img=True)
        switch = loc.locate(st, observer, env)
        if switch == []:
            time.sleep(0.1)
            continue
        offloc = locator.const_locator("text", "OFF")
        if offloc.locate(st, observer, env) == []:
            # can't find OFF, already ON
            # dismiss dialog
            back(dev)
            break
        (x, y) = switch[0].center()
        tap(dev, x, y)

        while True:
            time.sleep(0.1)
            st = observer.grab_state(dev, no_img=True)
            if loc.locate(st, observer, env) == []:
                break
        break
    return True


def kbd_off(dev, observer, env):
    logger.info("disable soft keyboard")
    run_input(dev, "keyevent", ["SYM"])

    for retry in range(config.KBDSWITCH_LIMIT):
        loc = locator.const_locator("id", "hard_keyboard_switch")
        st = observer.grab_state(dev, no_img=True)
        switch = loc.locate(st, observer, env)
        if switch == []:
            time.sleep(0.1)
            continue
        onloc = locator.const_locator("text", "ON")
        if onloc.locate(st, observer, env) == []:
            # can't find ON, already OFF
            # dismiss dialog
            back(dev)
            break
        (x, y) = switch[0].center()
        tap(dev, x, y)
        break

    return True


# DOES NOT WORK
def wait_keyboard(dev, observer, env):
    curr_height = config.real_height

    new_height = curr_height
    logger.info("waiting for soft keyboard")
    for retry in range(config.KBDACTION_KEYBOARD_LIMIT):
        time.sleep(0.1)
        st = observer.grab_state(dev, no_img=True)
        new_height = st.get('items')[1]['height']
        if new_height != curr_height:
            break

    if new_height == curr_height:
        logger.warning("can't find soft keyboard, give up")
        return False
    else:
        return True


def kbd_action(dev, observer, env):
    ret = True

    logger.info("tapping action key on soft keyboard")
    tap(dev, config.width - 80, config.real_height - 90)

    return ret


def waitfor(dev, method, target, observer, env):
    finder = locator.Locator(method, value.ConstValue(target))
    for retry in len(config.WAITFOR_RETRY_LIMIT):
        state = observer.grab_state(dev)
        if finder.locate(state, observer, env) != []:
            return True
        time.sleep(1)
    logger.warn("waitfor %s(%s) timeout", method, target)
    return False


def action_available(state):
    items = state.get('items')
    for itemid in items:
        item = items[itemid]
        if item['click']:
            return True
    return False


def waitready(dev, observer):
    for retry in range(config.WAITREADY_RETRY_LIMIT):
        state = observer.grab_state(dev, no_img=True)
        if action_available(state):
            return True
        if len(state.get('items')) > 20:
            # so many items! must have something!
            return True
        time.sleep(0.2)
    # sometimes, there is just nothing appears clickable
    return True


def waitidle(dev):
    dev.wait_idle()
    return True


def wait(dev, timeout):
    time.sleep(timeout / 1000.0)
    return True


def text_in_item(text, item):
    if text in item['text'].lower():
        return True
    # TODO: mark webview children
    if (item['class'] == 'View' or
            item['class'] == 'Spinner' or
            item['class'] == 'Button'):
        desc = item['desc'].lower()
        desc = desc.replace('\xa0', ' ')
        desc = desc.replace('\n', ' ')
        if text in desc:
            return True
    return False


def seetext(dev, text, observer):
    for i in range(config.CHECK_RETRY_LIMIT):
        gui_state = observer.grab_state(dev, no_img=True)
        items = gui_state.get('items')
        text = text.lower()
        for itemid in items:
            item = items[itemid]
            if text_in_item(text, item):
                return True
        if config.CHECK_OTHER_WINDOWS:
            for winid in range(2, 10):
                targetfile = "/tmp/win.xml"
                if not sense.grab_extra_win(dev, winid, targetfile):
                    break
                items = analyze.load_case(targetfile)[0]
                for itemid in items:
                    if text_in_item(text, items[itemid]):
                        return True

        time.sleep(1)
    logger.warn("see %s timeout", text)
    return False


def seein(dev, widget, text, observer):
    for i in range(config.CHECK_RETRY_LIMIT):
        if text.lower() in widget.content().lower():
            return True
        time.sleep(1)
        gui_state = observer.grab_state(dev, no_img=True)
        widget = widget.relocate(gui_state)
        logger.info("not seen, relocated to %s", widget)
    logger.warn("see %s timeout", text)
    return False


num_re = re.compile("[0-9.]+")


def str_to_value(s):
    val = ''.join(num_re.findall(s))
    try:
        return float(val)
    except:
        return 0


def get_incdec(widgets):
    widgets.sort(key=lambda widget: widget.node_id)
    inc_cnt = 0
    dec_cnt = 0
    for i in range(len(widgets) - 1):
        this_wid = widgets[i]
        next_wid = widgets[i + 1]

        this_val = str_to_value(this_wid.content())
        next_val = str_to_value(next_wid.content())

        print(this_wid.node_id, next_wid.node_id, this_wid, next_wid, this_val, next_val)
        if this_val < next_val:
            inc_cnt += 1
        elif this_val > next_val:
            dec_cnt += 1
    print(inc_cnt, dec_cnt)
    return (inc_cnt, dec_cnt)


def increasing(dev, widgets, observer):
    (inc_cnt, dec_cnt) = get_incdec(widgets)
    return inc_cnt >= dec_cnt


def decreasing(dev, widgets, observer):
    (inc_cnt, dec_cnt) = get_incdec(widgets)
    return inc_cnt <= dec_cnt


def find_scroll_target(state):
    tree = state.get('tree')
    cand = []
    for itemid in tree:
        if tree[itemid]['scroll']:
            cand.append(itemid)
    if len(cand) == 1:
        target = cand[0]
    elif len(cand) == 0:
        return None
    else:
        # TODO: pick from all those scrollable?
        max_size = -1
        target = None
        for itemid in cand:
            size = tree[itemid]['origw'] * tree[itemid]['origh']
            if size > max_size:
                max_size = size
                target = itemid
    target = widget.Widget(tree, target)
    return target


def scroll(dev, direction, observer, state=None):
    if state is None:
        state = observer.grab_state(dev)
    target = find_scroll_target(state)
    if target is None:
        return False
#        target = {'x': 0, 'y': 0, 'width': config.width, 'height': config.height}
    return scrollit(dev, target, direction, observer)


def scrollit(dev, target, direction, observer):
    if direction == 'down':
        x1 = x2 = target.x() + target.w() / 2
        y1 = target.y() + target.h() * 0.8
        y2 = target.y() + target.h() * 0.2
    elif direction == 'up':
        x1 = x2 = target.x() + target.w() / 2
        y1 = target.y() + target.h() * 0.2
        y2 = target.y() + target.h() * 0.8
    elif direction == 'left':
        y1 = y2 = target.y() + target.h() / 2
        x1 = target.x() + target.w() * 0.2
        x2 = target.x() + target.w() * 0.8
    elif direction == 'right':
        y1 = y2 = target.y() + target.h() / 2
        x1 = target.x() + target.w() * 0.8
        x2 = target.x() + target.w() * 0.2
    logger.debug("swiping from %dx%d to %dx%d", x1, y1, x2, y2)
    ret = swipe(dev, x1, y1, x2, y2)
    dev.wait_idle()
    return ret


def select(dev, target, option, observer, env):
    (x, y) = target.center()
    tap(dev, x, y)

    value_loc = locator.Locator('marked', value.ConstValue(option))
    ret = None
    last_state = None
    for retry in range(config.SCROLL_RETRY_LIMIT):
        state = observer.grab_state(dev)
        ret = value_loc.locate(state, observer, env)
        if ret != []:
            break
        if state.same_as(last_state):
            logger.info("scrolled to the bottom")
            return False
        last_state = state
        # TODO: what about other direction?
        if not scroll(dev, 'down', observer, state):
            return False
    if ret == []:
        logger.warn("can't find option '%s'", option)
        return False

    (x, y) = ret[0].center()
    return tap(dev, x, y)


def clearfocused(dev, observer, env):
    loc = locator.const_locator('focused', 'true')
    delete(dev, config.CLEAR_ONCE_CHARS)
    forward_delete(dev, config.CLEAR_ONCE_CHARS)

    screen = observer.grab_state(dev, no_img=True)
    widgets = loc.locate(screen, observer, env)
    if widgets == []:
        # no focused view? okay
        return True
    widget = widgets[0]
    foctext = widget.text()
    if widget != [] and (foctext != '' or widget.is_password()):
        for i in range(config.MAX_CLEAR_CHARS):
            # (x, y) = widget.center()
            # tap(dev, x, y)
            delete(dev, config.CLEAR_ONCE_CHARS)
            forward_delete(dev, config.CLEAR_ONCE_CHARS)

            screen = observer.grab_state(dev, no_img=True)
            widgets = loc.locate(screen, observer, env)
            newtext = widgets[0].text()
            if newtext == '' or newtext == foctext:
                # unchanged? likely cleared
                # for password, we've cleared one round, should be enough
                break
            foctext = newtext

    return True


def kbd_shown(dev):
    if dev.run_adb_shell("dumpsys window | grep inputmethod -A 8 | grep mHasSurface=true",
                         noerr=False):
        return True
    else:
        return False


def close_kbd(dev):
    if kbd_shown(dev):
        back(dev)
    return True


if __name__ == "__main__":
    dev = device.Device()
    tap(dev, 500, 100)
    text(dev, "foobar")
    enter(dev)
    back(dev)
    back(dev)
    back(dev)
