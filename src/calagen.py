#!/usr/bin/env python

import logging
import sys

logger = logging.getLogger("calagen")

class Generator(object):
    def __init__(self, out):
        self.out = out
        self.step_count = 0
        self.scenario_count = 0

    def feature(self, title):
        self.out.write("Feature: %s\n" % title)

    def scenario(self, title):
        self.scenario_count += 1
        self.out.write("\tScenario: %s\n" % title)

    def step(self, content, lead=None):
        self.step_count += 1
        if lead is None:
            if self.step_count == 1:
                lead = 'When'
            else:
                lead = 'Then'
        self.out.write("\t\t%s %s\n" % (lead, content))

    def touch(self, target):
        self.step('I tap \'%s\'' % target)

    def enter(self, target, text):
        self.step('I enter \'%s\' into \'%s\'' % (text, target))

class Locator(object):
    def __init__(self, cls=None, id=None, desc=None, text=None, enabled=True, webview=False):
        self.cls = cls
        self.id = id
        self.desc = desc
        self.text = text
        self.enabled = enabled
        self.webview = webview

    def query(self):
        if self.webview:
            base = 'webView'
        elif self.cls is None:
            base = "*"
        else:
            base = self.cls

        if not self.webview:
            if self.id is not None:
                base += ' id:"%s"' % self.id

            if self.desc is not None:
                base += ' contentDescription:"%s"' % self.desc

            if self.text is not None:
                base += ' marked:"%s"' % self.text

            if self.enabled:
                base += ' isEnabled:true'
            else:
                base += ' isEnabled:false'
        else:
            webquery = ''
            if self.cls is not None:
                webquery += '%s' % self.cls
            if self.id is not None:
                webquery += '#%s' % self.id

            if webquery:
                base += ' css:"%s"' % webquery

        return base

    def __str__(self):
        return self.query()

def test_feature():
    gen = Generator(sys.stdout)
    gen.feature("Test feature")
    gen.scenario("Wake up")
    gen.step("I wake up")
    gen.step("I run")
    gen.scenario("Go to bed")
    gen.step("I lay down")
    gen.step("I sleep")
    gen.scenario("Sign in")
    gen.enter(Locator(cls="edittext", id="username"), "real username")
    gen.enter(Locator(cls="edittext", desc="password"), "real password")
    gen.enter(Locator(id="password", webview=True), "real password")
    gen.touch("sign in")
    gen.touch(Locator(cls="button", id="signin"))

if __name__ == "__main__":
    test_feature()

