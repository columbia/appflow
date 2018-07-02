import logging
import re

import config
import value

logger = logging.getLogger("dialog")

negative_words = ['cancel', 'no', 'back', 'disagree', 'reject', 'decline', 'ignore',
                  'never', 'disallow', 'deny', 'later', 'not']
positive_words = ['ok', 'yes', 'next', 'agree', 'accept', 'proceed', 'sure', 'allow',
                  'remove']
id_re = re.compile("[a-zA-Z][a-z]+")
text_re = re.compile("[a-zA-Z]+")
negative_desc = ['notification', 'location', 'mail']
positive_desc = ['remove', 'permission']


def detect_dialog(tree):
    if 1 not in tree:
        logger.info("no dialog: not yet loaded")
        return (False, [])
    clicks = []
    for nodeid in tree:
        node = tree[nodeid]
        if node['scroll'] or node['password'] or node['class'] == 'ListView':
            # not the dialog I expected
            logger.info("no dialog: strange things")
            return (False, [])
        if node['click']:
            clicks.append(nodeid)
    if len(clicks) > 3:
        # too complex
        logger.info("no dialog: too complex")
        return (False, [])
    if (tree[1]['width'] == config.width and
            tree[1]['height'] >= config.real_height_nostatus):
        logger.info("no dialog: fullscreen")
        return (False, [])
    if tree[1]['height'] < config.dialog_min_height:
        logger.info("no dialog: too small")
        return (False, [])
    return (True, clicks)


def detect_dialog_button(tree, bid, bsid=None):
    node = tree[bid]
    fulldesc = (text_re.findall("%s %s" % (node['text'], node['desc'])) +
                id_re.findall(node['id']))
    for word in negative_words + value.get_param('dialog_negative_button', '').split(','):
        if word:
            for descword in fulldesc:
                if word.lower() == descword.lower():
                    return 'no'
    for word in positive_words + value.get_param('dialog_positive_button', '').split(','):
        if word:
            for descword in fulldesc:
                if word.lower() == descword.lower():
                    return 'yes'
    if bsid is not None and len(bsid) == 2:
        if bid == bsid[0]:
            otherid = bsid[1]
        else:
            otherid = bsid[0]

        other = detect_dialog_button(tree, otherid)
        if other == 'no':
            return 'yes'
        if other == 'yes':
            return 'no'
    return 'neutral'


def decide_dialog_action(tree):
    for nodeid in tree:
        node = tree[nodeid]
        fulldesc = ('%s %s %s' % (node['text'].lower(), node['desc'].lower(),
                                  node['id'].lower())).lower()
        for word in negative_desc + value.get_param('dialog_negative', '').split(','):
            if word and word in fulldesc:
                return 'no'
        for word in positive_desc + value.get_param('dialog_positive', '').split(','):
            if word and word in fulldesc:
                return 'yes'
    return 'yes'
