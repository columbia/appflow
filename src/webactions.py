import logging
import time
from selenium import webdriver
import config
import locator

logger = logging.getLogger("webactions")

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
    'start': lambda dev, observer, env, attr: start(dev, attr['name']),
    'stop': lambda dev, observer, env, attr: stop(dev, attr['name']),
    'clear': lambda dev, observer, env, attr: clear(dev, attr['name']),
    'waitact': lambda dev, observer, env, attr: waitact(dev, attr['name']),

    'wait': lambda dev, observer, env, attr: wait(dev, attr['time']),
    'waitfor': lambda dev, observer, env, attr: waitfor(dev, attr['method'],
                                                        attr['value'], observer, env),
    'waitready': lambda dev, observer, env, attr: waitready(dev, observer),
    'waitidle': lambda dev, observer, env, attr: waitidle(dev),
    'seetext': lambda dev, observer, env, attr: seetext(dev, attr['str'], observer),
    'seein': lambda dev, observer, env, attr: seein(dev, attr['widget'], attr['str'],
                                                    observer),
    'select': lambda dev, observer, env, attr: select(dev, attr['target'], attr['value'],
                                                      observer, env),
    'scroll': lambda dev, observer, env, attr: scroll(dev, attr['direction'], observer),
    'scrollit': lambda dev, observer, env, attr: scrollit(dev, attr['widget'],
                                                          attr['direction'], observer),
    'clearfocused': lambda dev, observer, env, attr: clearfocused(dev, observer, env),
    'kbdon': lambda dev, observer, env, attr: True,
}


def text(dev, string):
    chain = webdriver.common.action_chains.ActionChains(dev.driver)
    chain.send_keys(string)
    chain.perform()
    return True


def tap(dev, x, y):
    chain = webdriver.common.action_chains.ActionChains(dev.driver)
    chain.move_to_element_with_offset(
        dev.driver.find_element_by_xpath("/html/body"), x, y)
    chain.click()
    chain.perform()
    return True


def longclick(dev, x, y):
    return False


def back(dev):
    dev.driver.back()
    return True


def enter(dev):
    return text(dev, webdriver.common.keys.Keys.ENTER)


def home(dev):
    return True


def swipe(dev, x1, y1, x2, y2):
    chain = webdriver.common.action_chains.ActionChains(dev.driver)
    chain.move_to_element_with_offset(
        dev.driver.find_element_by_xpath("/html/body"), x1, y1)
    chain.click_and_hold()
    chain.move_by_offset(x2 - x1, y2 - y1)
    chain.release()
    chain.perform()
    return True


def start(dev, name):
    dev.driver.get(name)
    return True


def stop(dev, name):
    dev.driver.get("about:blank")
    return True


def clear(dev, name):
    return True


def waitact(dev, name):
    return True


def wait(dev, timeout):
    time.sleep(timeout / 1000.0)
    return True


def waitfor(dev, method, value, observer, env):
    finder = locator.Locator(method, value)
    for retry in len(config.WAITFOR_RETRY_LIMIT):
        state = observer.grab_state(dev)
        if finder.locate(state, observer, env) != []:
            return True
        time.sleep(1)
    logger.warn("waitfor %s(%s) timeout", method, value)
    return False


def waitready(dev, observer):
    return True


def waitidle(dev):
    return True


def seetext(dev, string, observer):
    xpath = "//*[contains(text(), '%s'" % string
    elem = dev.driver.find_element_by_xpath(xpath)
    if elem is None:
        return False
    else:
        return True


def seein(dev, target, observer, env):
    pass


def add_attr(attrs, name, value):
    if attrs == '':
        return '@%s="%s"' % (name, value)
    else:
        return '%s and @%s="%s"' % (attrs, name, value)


def widget_to_xpath(widget):
    orig_props = widget.orig_prop('props')
    tag = widget.orig_prop('tag')
    xpath = "//%s" % tag

    attrs = ''
    if 'name' in orig_props:
        attrs = add_attr(attrs, 'name', orig_props['name'])
    if 'id' in orig_props:
        attrs = add_attr(attrs, 'id', orig_props['id'])

    if attrs != '':
        return '%s[%s]' % (xpath, attrs)
    else:
        return xpath


def select(dev, target, value, observer, env):
    xpath = widget_to_xpath(target)
    webelement = dev.driver.find_element_by_xpath(xpath)
    action = webdriver.support.select.Select(webelement)
    try:
        action.select_by_visible_text(value)
        return True
    except:
        logger.exception("cannot select '%s'", value)
        return False


def scroll(dev, direction, observer):
    scrollX = 0
    scrollY = 0
    if direction == 'down':
        scrollY = config.height / 4 * 3
    elif direction == 'up':
        scrollY = -config.height / 4 * 3
    elif direction == 'left':
        scrollX = -config.width / 4 * 3
    elif direction == 'right':
        scrollX = config.width / 4 * 3
    dev.driver.execute_script("window.scrollBy(%d, %d);" % (scrollX, scrollY))
    return True
    #return scrollit(dev, widget.full_screen, direction, observer)


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
    ret = swipe(dev, x1, y1, x2, y2)
    dev.wait_idle()
    return ret


def clearfocused(dev, observer, env):
    chain = webdriver.common.action_chains.ActionChains(dev.driver)
    chain.send_keys(webdriver.common.keys.Keys.DELETE * config.CLEAR_ONCE_CHARS)
    chain.send_keys(webdriver.common.keys.Keys.BACKSPACE * config.CLEAR_ONCE_CHARS)
    chain.send_keys(webdriver.common.keys.Keys.DELETE * config.CLEAR_ONCE_CHARS)
    chain.send_keys(webdriver.common.keys.Keys.BACKSPACE * config.CLEAR_ONCE_CHARS)
    chain.perform()
    return True
