#!/usr/bin/env python3

import logging
import sys

import statinfo

logger = logging.getLogger("showdiff")


def get_file(filename):
    data = statinfo.load_statfile(filename)
    ret = {}
    for test in data:
        val = data[test]
        if val[0] > 0 and val[1] == 0:
            state = "ok"
        elif val[0] == 0 and val[1] > 0:
            state = "fail"
        elif val[0] > 0 and val[1] > 0:
            state = "flaky"
        else:
            state = None

        if state is not None:
            ret[test] = state
    return ret


def calc_diff(file1, file2):
    old_ret = get_file(file1)
    new_ret = get_file(file2)

    # ret: test -> state

    for test in old_ret:
        old = old_ret[test]
        if test in new_ret:
            new = new_ret[test]

            if old != new:
                if old == 'ok':
                    if new == 'fail':
                        logger.info("CHANGE FAIL: %s", test)
                    elif new == 'flaky':
                        logger.info("CHANGE FLAKY (WAS OK): %s", test)
                elif old == 'fail':
                    if new == 'ok':
                        logger.info("CHANGE OK: %s", test)
                    elif new == 'flaky':
                        logger.info("CHANGE FLAKY (WAS FAIL): %s", test)
                elif old == 'flaky':
                    if new == 'ok':
                        logger.info("CHANGE OK (WAS FLAKY): %s", test)
                    elif new == 'fail':
                        logger.info("CHANGE FAIL (WAS FLAKY): %s", test)
            else:
                logger.debug("KEEP: %s", test)
        else:
            if old == 'ok':
                logger.info("MISSING OK: %s", test)
            elif old == 'fail':
                logger.info("MISSING FAIL: %s", test)
            elif old == 'flaky':
                logger.info("MISSING FLAKY: %s", test)

    for test in new_ret:
        if test not in old_ret:
            new = new_ret[test]
            if new == 'ok':
                logger.info("NEW OK: %s", test)
            elif new == 'fail':
                logger.info("NEW FAIL: %s", test)
            elif new == 'flaky':
                logger.info("NEW FLAKY: %s", test)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    calc_diff(sys.argv[1], sys.argv[2])
