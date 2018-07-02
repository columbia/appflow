#!/usr/bin/env python3

import threading
import time
import os
import logging

logger = logging.getLogger("watchdog")


def terminate():
    os._exit(1)


class Watchdog(object):
    def __init__(self, timeout, handler=terminate):
        self.timeout = timeout
        self.counter = 0
        self.thr = None
        self.stopped = True
        self.handler = handler

    def start(self):
        self.stopped = False
        self.thr = threading.Thread(target=self.run, daemon=True)
        self.thr.start()

    def stop(self):
        self.stopped = True

    def run(self):
        while not self.stopped:
            if self.counter > self.timeout:
                logger.error("watchdog timeout!")
                self.handler()

            self.counter += 1
            time.sleep(1)

    def kick(self):
        self.counter = 0


def create(timeout):
    return Watchdog(timeout)


if __name__ == "__main__":
    watchdog = create(5)
    watchdog.start()
    time.sleep(3)
    print("kick")
    watchdog.kick()
    time.sleep(3)
    print("kick")
    watchdog.kick()
    time.sleep(3)
    print("no kick")
    time.sleep(3)
