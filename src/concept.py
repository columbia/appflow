import widget
import locator
import value
import config

import re
import logging

logger = logging.getLogger("concept")

use_onepass = False


class Concept(object):
    def __init__(self, tag, screen=None):
        self.tag = tag
        self.screen = screen

    def locate(self, state, observer, env):
        targets = []
        if use_onepass:
            if self.tag in state.get('guess_items'):
                # TODO: select one from the classification results
                #itemid = state.get('guess_items')[self.tag][0]
                for itemid in state.get('guess_items')[self.tag]:
                    target = widget.Widget(state.get('tree'), itemid)
                    targets.append(target)
        else:
            for itemid in observer.find_elements(state, self.tag):
                target = widget.Widget(state.get('tree'), itemid)
                targets.append(target)

        target = targets[0] if targets != [] else None
        exoverride = value.get_exlocator(state.get('screen'), self.tag)
        if exoverride is not None:
            logger.info("using overrided exlocator for %s %s", state.get('screen'),
                        self.tag)
            for marker in exoverride:
                ret = marker.locate(state, observer, env)
                if ret is not None:
                    value.mark_locator(marker, ret[0], target)
                    return ret
            return []

        override = value.get_locator(self.tag)
        if override is not None:
            logger.info("using overrided locator for %s", self.tag)
            for marker in override:
                ret = marker.locate(state, observer, env)
                if ret is not None:
                    value.mark_locator(marker, ret[0], target)
                    return ret
            return []

        return targets

    def present(self, state) -> bool:
        if state.get('guess_items') is not None:
            if self.tag in state.get('guess_items'):
                return True
        if state.get('tags') is not None and self.tag in state.get('tags'):
            return True
        else:
            return False

    def no_scroll(self):
        return self.tag in config.no_scroll_tags

    def __hash__(self):
        return hash(self.tag)

    def __eq__(self, other):
        return self.tag == other.tag

    def __str__(self):
        return "concept (%s)" % self.tag

concept_re = re.compile("@(.+)")
def parse(part):
    if concept_re.match(part):
        tag = concept_re.match(part).group(1)
        return Concept(tag)
    return locator.parse(part)
