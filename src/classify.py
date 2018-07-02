#!/usr/bin/env python3

from sklearn.feature_extraction.text import TfidfVectorizer
#, HashingVectorizer, CountVectorizer
#from sklearn.pipeline import make_pipeline
#from sklearn.preprocessing import Normalizer
#from sklearn.model_selection import KFold
from sklearn.svm import LinearSVC, SVC # noqa
from sklearn.neural_network import MLPClassifier
#from sklearn.naive_bayes import GaussianNB, MultinomialNB
from sklearn.tree import DecisionTreeClassifier # noqa
from sklearn.ensemble import AdaBoostClassifier, RandomForestClassifier # noqa
from sklearn.externals import joblib
from sklearn.decomposition import PCA
import sklearn
import numpy
import scipy
from tesserocr import PyTessBaseAPI, RIL
from sklearn.preprocessing import StandardScaler

import glob
import os
#import random
import re
#from functools import reduce
import xml.etree.ElementTree as ET
import subprocess
import multiprocessing
import functools
import logging
import argparse
import pickle
import random

import config
import perfmon
import analyze
import tags as taginfo
import util
import hidden

logger = logging.getLogger("classify")

DATADIR = "../guis"

check_train = True
detail_report = False
missing_warn = False
report_exact = True
show_feature = False

use_rep = False
use_num = False
only_good_pt = True
use_fake_ocr = False
use_pca = False
nopt = False
use_treeinfo = True
use_rootinfo = False
use_scaler = False
use_titleinfo = True

random_state = 0
max_depth = 100
min_samples_leaf = 6
n_estimators = 58
n_components = 1000

if config.parallel:
    thread_count = config.threads
else:
    thread_count = 1

if use_num:
    basic_re = re.compile("[A-Za-z0-9]+")
else:
    basic_re = re.compile("[A-Za-z]+")

word_re = re.compile("[A-Z0-9]?[a-z0-9]+|[A-Z0-9]")
alpha_re = re.compile('[a-zA-z]+')

if use_rep:
    REP_COUNT = {'signin': 5, 'register': 5, 'main': 1, 'checkout': 1, 'addredit': 5,
                 'cardedit': 5, 'filter': 2, 'sort': 2, 'account': 5, 'setting': 5,
                 'address': 3, 'payment': 3, 'search': 5, 'cart': 1, 'detail': 1,
                 'searchret': 1, 'menu': 3, 'cat': 5, 'welcome': 5, 'orders': 5,
                 'about': 5, 'terms': 5, 'help': 5, 'notif': 5, 'contact': 5}
else:
    REP_COUNT = {}


bound_re = re.compile("\[(\d+),(\d+)\]\[(\d+),(\d+)\]")
SCR_SIZE = config.width * config.real_height

VEC_WIDTH = 10


def to_float(boolval):
    return 1.0 if boolval else 0.0


def preprocess_vec(tree):
    ret = numpy.zeros([VEC_WIDTH], numpy.float64)
    if tree is None:
        return ret
    #ret[0] = len(tree) / 100

    if use_treeinfo:
        treeinfo = analyze.collect_treeinfo(tree)
        #ret[1] = 1.0 if treeinfo['listlike'] else 0.0
        ret[2] = len(treeinfo['dupid']) / len(tree)
        ret[3] = len(treeinfo['itemlike']) / len(tree)

    if use_rootinfo:
        rootid = min(tree)
        ret[4] = to_float(tree[rootid]['x'] != 0)
        ret[5] = to_float(tree[rootid]['y'] != 0)
        ret[6] = to_float(tree[rootid]['x'] != 0 and
                          tree[rootid]['x'] + tree[rootid]['width'] < config.width)
        ret[7] = to_float(tree[rootid]['y'] != 0 and
                          tree[rootid]['y'] + tree[rootid]['height'] < config.real_height)

    return ret


def addseg(segs, value, regex=word_re):
    segs.append(value)
    segs.append('\n')
    #parts = regex.findall(value)
    #segs.extend(parts)


def addseg2(segs, kw, value, regex=word_re):
    if value.upper() == value:
        value = value.lower()
    for part in regex.findall(value):
        segs.append(kw + part)
    segs.append('\n')


def addngram(segs, val, regex=word_re, ngram=2):
    parts = regex.findall(val)
    for i in range(len(parts) - 1):
        addseg(segs, parts[i] + parts[i + 1])


def process_tree(tree):
    segs = []
    first_tv = True

    for nodeid in tree:
        node = tree[nodeid]

        if 'visible' in node and node['visible'] == 'hidden':
            continue

        clz = node['class']
        rid = node['id']
        text = node['text'][:30]
        desc = node['desc'][:30]
        ocr = node['ocr']

        addseg(segs, clz)
        addseg(segs, rid)
        addseg(segs, text)
        addseg(segs, desc)
        addseg(segs, ocr)
        addngram(segs, text)
        addngram(segs, desc)
        if node['password']:
            addseg2(segs, "ISPASSWORD", rid)
            addseg2(segs, "ISPASSWORD", clz)
        #if node['scroll']:
        #    addseg2(segs, "SCROLLABLE", rid)
        #    addseg2(segs, "SCROLLABLE", clz)
        #if node['checkable']:
        #    addseg2(segs, "CLICK", rid)
        #    addseg2(segs, "CLICK", clz)

        x = node['x']
        y = node['y']
        width = node['width']
        height = node['height']
        size = width * height
        if size < SCR_SIZE:
            if size > 0.5 * SCR_SIZE:
                segs.append("XXL" + clz)
                addseg2(segs, "XXL", rid)
            elif size > 0.05 * SCR_SIZE:
                segs.append("BIG" + clz)
                addseg2(segs, "BIG", rid)
        if width > 0.6 * config.width:
            segs.append("WIDE" + clz)
            addseg2(segs, "WIDE", rid)
        if height > 0.6 * config.height:
            segs.append("TALL" + clz)
            addseg2(segs, "TALL", rid)
        if y + height < 0.3 * config.height:
            segs.append("TOP" + clz)
            addseg2(segs, "TOP", rid)
        if y > 0.7 * config.height:
            segs.append("BOTTOM" + clz)
            addseg2(segs, "BOTTOM", rid)
        if x + width < 0.3 * config.width:
            segs.append("LEFT" + clz)
            addseg2(segs, "LEFT", rid)
        if x > 0.7 * config.width:
            segs.append("RIGHT" + clz)
            addseg2(segs, "RIGHT", rid)

        if clz == 'TextView' and first_tv:
            first_tv = False
            addseg2(segs, "TITLE", text)

    ret = ' '.join(segs)
    if show_feature:
        print(ret)
    return ret


def traverse(node, ans, segs):
    #    print(node.attrib)
    if 'class' in node.attrib:
        cls = node.attrib['class'].split('.')[-1]
    else:
        cls = 'root'
    if 'resource-id' in node.attrib:
        res_id = node.attrib['resource-id'].split('/')[-1]
    else:
        res_id = ''

    def addseg(prop, default='', split='', reg=basic_re):
        if prop in node.attrib and node.attrib[prop] != default:
            #            segs.append(prop)
            if split == '':
                parts = reg.findall(node.attrib[prop])
            else:
                parts = reg.findall(node.attrib[prop].split(split)[-1])
#            print(node.attrib[prop])
#            print(parts)
            segs.extend(parts[:5])
#            if len(parts) > 160:
#                print(parts, len(parts))
#                print(parts[160:])
#            if prop == "content-desc" or prop == "text":
#                for i in range(min(len(parts), 5) - 2):
#                    segs.append(parts[i] + parts[i+1] + parts[i+2])

    def addattr(cls, default=''):
        if cls in node.attrib and node.attrib[cls] != default:
            segs.append(cls + node.attrib[cls])

    addseg("class", split='.')
    addseg("text")
    addseg("resource-id", split='/', reg=basic_re)
    addseg("content-desc")
    #addseg("checkable", "false")
    #addseg("clickable", "false")
    #addseg("enabled", "true")
    #addseg("focusable", "false")
    #addseg("scrollable", "false")
    #addseg("longclick-able", "false")
    addseg("password", "false")
    #addseg("index")
    if 'bounds' in node.attrib:
        (x1, y1, x2, y2) = bound_re.match(node.attrib['bounds']).groups()
        x1 = int(x1)
        x2 = int(x2)
        y1 = int(y1)
        y2 = int(y2)
        width = x2 - x1
        height = y2 - y1
        size = width * height
        #segs.append(cls + "WIDTH" + str(int(width / 300)))
        #segs.append(cls + "HEIGHT" + str(int(height / 300)))
        #segs.append(cls + "SIZE" + str(int(size / 300 / 300)))
        if size < SCR_SIZE:
            if size > 0.5 * SCR_SIZE:
                segs.append("XXL" + cls)
            elif size > 0.05 * SCR_SIZE:
                segs.append("BIG" + cls)
        if width > 0.6 * config.width:
            segs.append("WIDE" + cls)
        if height > 0.6 * config.height:
            segs.append("TALL" + cls)
#        if width > 0.3 * config.width and height > 0.3 * config.height:
#            segs.append("MAJOR" + cls)
#    addseg("bounds")

#    segs.append(cls)
#    for i in range(3):
#        if len(ans) > i:
#            segs.append(''.join(ans[-(i + 1):]) + res_id)

    for child in node:
        traverse(child, ans + [res_id], segs)

#    segs.append("ret")


def preprocess(content):
    #    ret = ""

    #    tag_re = re.compile("<[^>]+>")
    #    prop_re = re.compile("\s([^\s]+)=\"([^\s]+)\"")
    #
    #    for tag in ["class", "text", "content-desc", "resource-id"]:
    #        for item in tag_re.findall(content):
    #            if item[1] == '/':
    #                ret += "ret ";
    #    #        print(item)
    #            for (key, val) in prop_re.findall(item):
    #                if key == tag:
    #                    ret += val.split('.')[-1] + " "
    #            if item[-2] == '/':
    #                ret += "ret ";

    root = ET.fromstring(content)

    segs = []
    traverse(root, [], segs)
    ret = ' '.join(segs)
#    return content
#    ret = ''
#    words = re.compile("[A-Za-z0-9]+").findall(content)
#    ret += ' '.join(words)
#    words = segs
#    for i in range(len(words)):
#        if i > 0 and words[i-1] == "class":
#            for j in range(i+1, min(len(words), i+20)):
#                if j > 0 and words[j-1] == "class":
#                    print(words[i])
#                    print(words[j])
#                    ret += words[i] + words[j] + ' '
#    ret = ' '.join(re.compile("[A-Za-z0-9]+").findall(content))
#    print(ret)
    return ret


def traverse2(node, segs):
    if 'text' in node.attrib and node.attrib['text'] != '':
        segs.append(node.attrib['text'])
    elif ('class' in node.attrib and node.attrib['class'] == 'android.view.View' and
          'content-desc' in node.attrib and node.attrib['content-desc'] != ''):
        segs.append(node.attrib['content-desc'])
    for child in node:
        traverse2(child, segs)


def preprocess_img_fake(xmldata):
    root = ET.fromstring(xmldata)
    segs = []
    traverse2(root, segs)
#    print(segs)
    return ' '.join(segs)


def preprocess_txt(content):
    if '/' in content:
        content = content.split("/", 1)[1]
    pat = re.compile("[A-Z][a-z]+")
    return " ".join(pat.findall(content))


def preprocess_img_fromocr(tree):
    for nodeid in sorted(tree):
        node = tree[nodeid]
        if node['ocr'].strip():
            return ' '.join(basic_re.findall(node['ocr']))
    return 'dummy'


def preprocess_img(filename):
    ocrfile = filename.replace(".png", ".ocr")
    if os.path.exists(ocrfile):
        with open(ocrfile) as ocrf:
            ocrret = ocrf.read()
    else:
        logger.info("OCR %s" % filename)
        try:
            #"convert %s -density 420 -units pixelsperinch -define
            # png:compression-level=0 - | tesseract - stdout" % filename,
            ocrret = subprocess.check_output("tesseract %s stdout" % filename,
                                             shell=True, stderr=subprocess.PIPE
                                             ).decode("utf-8")
        except:
            ocrret = ''
        with open(ocrfile, 'w') as ocrf:
            ocrf.write(ocrret)
    return ' '.join(basic_re.findall(ocrret))


def preprocess_title(filename):
    title = ''
    api = PyTessBaseAPI()
    api.SetImageFile(filename)
    boxes = api.GetComponentImages(RIL.TEXTLINE, True)
    for i, (im, box, _, _) in enumerate(boxes):
        api.SetRectangle(box['x'], box['y'], box['w'], box['h'])
        ocrResult = api.GetUTF8Text()
        text = ' '.join(alpha_re.findall(ocrResult.strip()))
        if len(text) < 5:
            continue

        title = text
        break

    if title:
        logger.info("%s: %s", filename, title)
    return title


@perfmon.op("screen", "prepare_point")
def prepare_point(actname, imgfile, tree=None):
    #if tree is None:
    #    treeinfo = preprocess(xmlsrc)
    #else:
    treeinfo = process_tree(tree)
    actinfo = preprocess_txt(actname)
    imginfo = preprocess_img(imgfile)
    #imginfo = preprocess_img_fromocr(tree)
    vecinfo = preprocess_vec(tree)
    if use_titleinfo:
        titleinfo = preprocess_title(imgfile)
    else:
        titleinfo = ''
    return {'tree': treeinfo, 'act': actinfo, 'img': imginfo, 'vec': vecinfo,
            'title': titleinfo}


def process_input(filename):
    filebase = os.path.splitext(filename)[0]
    basename = os.path.basename(filename)
    pagename = basename.split(".")[0]
    if basename.count("_") == 1:
        (appname, scrname) = pagename.split("_")
    else:
        (appname, casename, scrname) = pagename.split("_")

    if scrname == 'cat1':
        scrname = "cat"
    elif scrname == 'cat':
        pass
    elif scrname.startswith('cat'):
        scrname = "cat2"
#    if scrname == "cat1":
#        continue
#    if scrname == "searchret":
#        scrname = "list"

    ptfile = filebase + '.pt'
    if os.path.exists(ptfile) and not nopt:
        ptf = open(ptfile, 'rb')
        unpickler = pickle.Unpickler(ptf)
        try:
            pt = unpickler.load()
            return (scrname, pt)
        except:
            pass

    ptf = open(ptfile, 'wb')
    pickler = pickle.Pickler(ptf)

    #with open(filename, 'r') as f:
    #    xmldata = f.read()

    tree = analyze.load_tree(filename)
    hidden.find_hidden_ocr(tree)
    hidden.mark_children_hidden_ocr(tree)
    if '.xml' in filename:
        actfile = filebase + '.txt'
        actname = open(actfile).read()
#        tree = analyze.analyze([filename], show_progress=False)[0]
    elif '.hier' in filename:
        urlfile = filebase + '.url'
        actname = util.url_to_actname(open(urlfile).read())
#        loaded = webdriver.load(filebase)
#        tree = analyze.analyze_items(loaded['items'])

    imgfile = filebase + '.png'

#            treeinfo = preprocess(xmldata)
#    #        data = ""
#
#            actinfo = ''
#            if os.path.exists(actfile):
#                with open(actfile) as txtf:
#                    actinfo = preprocess_txt(txtf.read())
#            else:
#                if only_good_pt:
#                    logger.info("skipping %s: no act", filename)
#                    continue
#                else:
#                    if missing_warn:
#                        logger.warn("WARN: %s missing activity info" % filename)
#
#            imginfo = ''
#            if os.path.exists(imgfile):
#                if not use_fake_ocr:
#                    imginfo = preprocess_img(imgfile)
#                else:
#                    imginfo = preprocess_img_fake(xmldata)
#            else:
#                if only_good_pt:
#                    logger.info("skipping %s: no img", filename)
#                    continue
#                else:
#                    if missing_warn:
#                        logger.warn("WARN: %s missing img info" % filename)
#            pt = {'app': appname, 'tree': treeinfo, 'act': actinfo, 'img': imginfo,
#'file': filename}

    # if config.use_postprocess:
    pt = prepare_point(actname, imgfile, tree)
    # else:
    #    pt = prepare_point(xmldata, open(actfile).read(), imgfile)
    pt['file'] = filename
    pt['app'] = appname
    pt['scr'] = appname
#            treeinfo = ' '.join([treeinfo, actinfo, imginfo])
    pickler.dump(pt)

    return (scrname, pt)


def collect_input(datadir, extrapath=None, extrascr=None):
    logger.info("Processing input")
    dataset = {}

    pool = multiprocessing.Pool(processes=thread_count)
    filelist = glob.glob(os.path.join(datadir, "*.xml")) + \
        glob.glob(os.path.join(datadir, "*.hier"))
    for (scrname, pt) in pool.map(process_input, filelist):
        if scrname is None:
            continue
        pt['extra'] = False
        for x in range(REP_COUNT.get(scrname, 1)):
            dataset[scrname] = dataset.get(scrname, []) + [pt]
    if extrapath is not None:
        filelist = glob.glob(os.path.join(extrapath, "*.xml")) + \
            glob.glob(os.path.join(extrapath, "*.hier"))
        logger.info("loading extra input from %s for %s", extrapath, extrascr)
        extrascr = extrascr.split(',')
        for (scrname, pt) in pool.map(process_input, filelist):
            if scrname is None or scrname not in extrascr:
                continue
            pt['extra'] = True
            for x in range(REP_COUNT.get(scrname, 1)):
                dataset[scrname] = dataset.get(scrname, []) + [pt]
    pool.close()

    return dataset


def load_datapts(datadir, appname=None, extrapath=None, extrascr=None):
    dataset = collect_input(datadir, extrapath, extrascr)
    #print(dataset)

    for screen in taginfo.tag['ignored_screens']:
        if screen in dataset:
            del dataset[screen]
    #dataset['other'] = dataset.pop('main') + dataset.pop('list')
    #del dataset['main']
    #del dataset['cat']
    #del dataset['cat1']
    #del dataset['cat3']
    #del dataset['list']
    #del dataset['register']
    #del dataset['paywith']

    apps = []
    tags = list(dataset.keys())
    tags.sort()

    datapts = []
    cnt_by_tag = {}
    for tag in tags:
        for obj in dataset[tag]:
            # ignore specific app's pts
            if appname is not None and obj['app'] == appname:
                continue
            obj['tag'] = tag
            datapts.append(obj)
            if not obj['extra']:
                apps.append(obj['app'])
        cnt_by_tag[tag] = len(dataset[tag])

    apps = sorted(set(apps))

    datapts = sklearn.utils.shuffle(datapts, random_state=random_state)
    return (datapts, apps, tags, cnt_by_tag)


def vectorize(pts, tree_vec, act_vec, img_vec, title_vec):
    trees = []
    acts = []
    imgs = []
    titles = []
    extras = []
    for datapt in pts:
        trees.append(datapt['tree'])
        acts.append(datapt['act'])
        imgs.append(datapt['img'])
        titles.append(datapt['title'])
        extras.append(datapt['vec'])

    tree_vecs = tree_vec.transform(trees)
    act_vecs = act_vec.transform(acts)
    img_vecs = img_vec.transform(imgs)
    if use_titleinfo:
        title_vecs = title_vec.transform(titles)
    else:
        title_vecs = None
    extra_vecs = numpy.vstack(extras)
    x = scipy.sparse.hstack((tree_vecs, act_vecs, img_vecs, extra_vecs, title_vecs)) # C
    #x = scipy.sparse.hstack((tree_vecs, act_vecs, img_vecs, extra_vecs))
    #x = scipy.sparse.hstack((tree_vecs, img_vecs, title_vecs, extra_vecs)) # CASE B
    #x = scipy.sparse.hstack((tree_vecs, img_vecs, act_vecs))
    #x = scipy.sparse.hstack((tree_vecs, act_vecs))
    #x = scipy.sparse.hstack((tree_vecs, img_vecs))
    #x = scipy.sparse.hstack((tree_vecs, extra_vecs)) # CASE A
    #x = img_vecs
    #x = tree_vecs
    #x = act_vecs
#    if not parallel:
#        print("test shape: %d %d" % x.shape)
    x = x.toarray()

    return (x, tree_vecs, act_vecs, img_vecs, title_vecs)


def vectorize_test(pts, tree_vec, act_vec, img_vec, title_vec, scaler):
    vec = vectorize(pts, tree_vec, act_vec, img_vec, title_vec)[0]
    if use_scaler:
        return scaler.transform(vec)
    else:
        return vec


def vectorize_train(pts):
    trees = []
    acts = []
    imgs = []
    titles = []
    extras = []

    for datapt in pts:
        trees.append(datapt['tree'])
        acts.append(datapt['act'])
        imgs.append(datapt['img'])
        titles.append(datapt['title'])
        extras.append(datapt['vec'])

    tree_vectorizer = TfidfVectorizer(
        max_df=0.5, max_features=8192, min_df=0.01, stop_words='english', use_idf=True,
        ngram_range=(1, 1))
    #tree_vectorizer = CountVectorizer(max_df=0.5, max_features=8192, min_df=0.01,
    #stop_words='english', ngram_range=(1, 1))
    tree_vectorizer.fit(trees)
    act_vectorizer = TfidfVectorizer(
        max_df=1.0, max_features=8192, min_df=0.0, stop_words='english', use_idf=True,
        ngram_range=(1, 1))
    #act_vectorizer =  CountVectorizer(stop_words='english')
    act_vectorizer.fit(acts)
    img_vectorizer = TfidfVectorizer(
        max_df=0.5, max_features=8192, min_df=0.01, stop_words='english', use_idf=True,
        ngram_range=(1, 2))
    #img_vectorizer =  CountVectorizer()
    img_vectorizer.fit(imgs)
    if use_titleinfo:
        title_vectorizer = TfidfVectorizer(max_df=0.5, max_features=8192, min_df=0.01,
                                           stop_words='english', use_idf=True,
                                           ngram_range=(1, 2))
        title_vectorizer.fit(titles)
    else:
        title_vectorizer = None

    (x, tree_vecs, act_vecs, img_vecs, title_vecs) = vectorize(
        pts, tree_vectorizer, act_vectorizer, img_vectorizer, title_vectorizer)

    if use_scaler:
        scaler = StandardScaler()
        x = scaler.fit_transform(x)
    else:
        scaler = None
    #x = scipy.sparse.hstack((tree_vecs, img_vecs, extra_vecs))
    #x = tree_vecs
    #x = scipy.sparse.hstack((tree_vecs, act_vecs))
    #x = act_vecs

#    if not parallel:
#        print("tree cnt: %d %d" % tree_vecs.shape)
#        print("act  cnt: %d %d" % act_vecs.shape)
#        print("img  cnt: %d %d" % img_vecs.shape)
#        print("merged: %d %d" % x.shape)

    #x = x.toarray()

    mydict = [''] * (tree_vecs.shape[1] + act_vecs.shape[1] + img_vecs.shape[1])
    for item in tree_vectorizer.vocabulary_:
        mydict[tree_vectorizer.vocabulary_[item]] = item
    for item in act_vectorizer.vocabulary_:
        mydict[act_vectorizer.vocabulary_[item] + tree_vecs.shape[1]] = 'ACT' + item
    for item in img_vectorizer.vocabulary_:
        mydict[img_vectorizer.vocabulary_[item] + tree_vecs.shape[1] + act_vecs.shape[1]
               ] = 'IMG' + item

    return (x, mydict, tree_vectorizer, act_vectorizer, img_vectorizer, title_vectorizer,
            scaler)


def evaluate_single(datapts, app, screen, term):
    (x, mydict, tree_vectorizer, act_vectorizer, img_vectorizer, title_vectorizer,
     scaler) = vectorize_train(datapts)

    if term != 'ALL':
        indices = []
        for idx in range(len(mydict)):
            if term in mydict[idx]:
                indices.append(idx)
    else:
        indices = range(len(mydict))

    for idx in range(len(x)):
        if datapts[idx]['app'] == app and datapts[idx]['tag'] == screen:
            print("===== pt %d %s" % (idx, datapts[idx]['file']))
            rets = []
            for tidx in indices:
                if x[idx][tidx] > 1e-7:
                    rets.append((mydict[tidx], x[idx][tidx]))
            for item in sorted(rets, key=lambda x: x[1]):
                print("%20s %.3f" % (item[0], item[1]))


def prepare_clas():
    if use_rep:
        class_weight = None
    else:
        class_weight = 'balanced' # noqa
    #clas = SVC(verbose=False, decision_function_shape='ovr', kernel="rbf",
    #           class_weight=class_weight, C=1000)
    #clas = LinearSVC(verbose=False, C=1, class_weight=class_weight)
    clas = MLPClassifier(hidden_layer_sizes=(40, ), max_iter=2000,
                         early_stopping=False, random_state=random_state,
                         solver='adam')
    #clas = GaussianNB()
    #clas = MultinomialNB()
    #clas = DecisionTreeClassifier(max_depth=100, random_state=random_state,
    #                              min_impurity_split=1e-7, min_samples_leaf=10)
    #clas = AdaBoostClassifier(base_estimator=DecisionTreeClassifier(
    # max_depth=max_depth, random_state=random_state, min_impurity_split=1e-7,
    # min_samples_leaf=min_samples_leaf), random_state=random_state,
    # n_estimators=n_estimators)
    #clas = RandomForestClassifier() #n_estimators=50, random_state=random_state)
    return clas


def evaluate(datapts, apps, tags, app=None, evalscreen=None):
    err_webview = 0
    tot_webview = 0

    errs = {} # type: Dict[str, int]
    err_by_tag = {} # type: Dict[str, int]
    case_by_app = {} # type: Dict[str, int]
    err_detail = {} # type: Dict[str, int]

    train_keys = []
    train_lbls = []
    train_apps = []
    test_keys = []
    test_lbls = []
    test_files = []

    my_test_err = 0
    my_test_correct = 0

    train_pt = []
    test_pt = []
    for datapt in datapts:
        if datapt['app'] != app:
            train_pt.append(datapt)
            train_lbls.append(datapt['tag'])
            train_apps.append(datapt['app'])
        else:
            if evalscreen == 'ALL' or evalscreen == datapt['tag']:
                test_pt.append(datapt)
                test_lbls.append(datapt['tag'])
                test_files.append(datapt['file'])

    if not test_pt:
        return (None, 0, 0,
                errs, err_by_tag, case_by_app, err_detail, err_webview, tot_webview)

    if detail_report and not config.parallel:
        print("=== Evaluating %s   / %d ===" % (app, len(apps)))

    (train_keys, mydict, tree_vecter, act_vecter, img_vecter, title_vecter, scaler
     ) = vectorize_train(train_pt)

    test_keys = vectorize_test(test_pt, tree_vecter, act_vecter, img_vecter, title_vecter,
                               scaler)

    if use_pca:
        pca = PCA(n_components=n_components)
        train_keys = pca.fit_transform(train_keys)
        test_keys = pca.transform(test_keys)

    #print(train_apps)
    #print(train_keys)
    #print(train_lbls)
    #print(test_keys)
    #print(test_lbls)

    clas = prepare_clas()
    clas.fit(train_keys, train_lbls)
    my_score = clas.score(test_keys, test_lbls)
    print("app %10s: %.3f" % (app, my_score))
    if not detail_report:
        my_test_correct = int(round(my_score * len(test_keys)))
        my_test_err = len(test_keys) - my_test_correct
    #first = False
    #tot_score += my_score
    #score_count += 1
    # if score_count == 1:
    #     first = True
    #if score_count == len(apps):
    #    print("final test: %f" % (tot_score / score_count))
    # if first and hasattr(clas, 'estimators_'):
    #        print(clas.classes_)
    #     for idx in range(len(clas.estimators_)):
    #         sklearn.tree.export_graphviz(clas.estimators_[idx], feature_names=mydict,
    #class_names=clas.classes_, out_file="tree%d.dot" % idx)

    scr_stat = {}
    if detail_report:
        reported = set()
        all_scores = clas.decision_function(test_keys)
        classes = list(clas.classes_)
        if config.classify_use_bound:
            preds = []
            scores = []
            for idx in range(len(test_keys)):
                score = config.SCREEN_SCORE_BOUND
                pred = 'NONE'
                for i in range(len(classes)):
                    if classes[i] != 'NONE' and all_scores[idx][i] > score:
                        score = all_scores[idx][i]
                        pred = classes[i]
                preds.append(pred)
                scores.append(score)
        else:
            preds = clas.predict(test_keys)
            scores = []
            for idx in range(len(test_keys)):
                scores.append(max(all_scores[idx]))

        for i in range(len(test_lbls)):
            pred = preds[i]
            score = scores[i]
            label = test_lbls[i]
            if app not in case_by_app:
                case_by_app[app] = 0
            case_by_app[app] += 1
            if 'WebView' in test_pt[i]['tree']:
                tot_webview += 1

            if label not in scr_stat:
                scr_stat[label] = [0, 0]
            if pred != label:
                if evalscreen == 'ALL' or evalscreen == pred or evalscreen == label:
                    if report_exact and not test_files[i] in reported:
                        if label in classes:
                            print("app %s: %s (%.3f) SHOULD BE %s (%.3f) %s" % (
                                app, pred, score, label,
                                all_scores[i][classes.index(label)], test_files[i]))
                        else:
                            # single-app screen!
                            print("app %s: %s (%.3f) SHOULD BE %s (SINGLE) %s" % (
                                app, pred, score, label, test_files[i]))

                        reported.add(test_files[i])
#                print(clas.predict_proba(test_keys[i].reshape(1, -1))[0])
                my_test_err += 1
                if app not in errs:
                    errs[app] = 0
                errs[app] += 1
                if label not in err_by_tag:
                    err_by_tag[label] = 0
                err_by_tag[label] += 1
                if app not in err_detail:
                    err_detail[app] = {}
                if label not in err_detail[app]:
                    err_detail[app][label] = []
                err_detail[app][label].append(pred)

                if 'WebView' in test_pt[i]['tree']:
                    err_webview += 1

                scr_stat[label][0] += 1
            else:
                if report_exact and not test_files[i] in reported:
                    print("%10s IS %10s %.3f" % (pred, label, score))
                    reported.add(test_files[i])
                my_test_correct += 1
                scr_stat[label][1] += 1

#    print("test: %d- %d+" % (err, correct))

    if check_train:
        err = 0
        correct = 0
        preds = clas.predict(train_keys)
        for i in range(len(train_lbls)):
            pred = preds[i]
            label = train_lbls[i]
            if pred != label:
                #            print(keys[pred], "should be", keys[label])
                err += 1
            else:
                correct += 1

        print("train: %d- %d+" % (err, correct))
    if detail_report and not config.parallel:
        print("test: %d- %d+ %f" % (my_test_err, my_test_correct, my_score))

    if detail_report:
        tot = 0
        for scr in scr_stat:
            tot += 1.0 * scr_stat[scr][1] / (scr_stat[scr][0] + scr_stat[scr][1])
        tot /= len(scr_stat)
        print("%10s tps: %.3f" % (app, tot))
        #my_score = tot

    return (my_score, my_test_err, my_test_correct,
            errs, err_by_tag, case_by_app, err_detail, err_webview, tot_webview)


class ScreenClassifier(object):
    def __init__(self, path=None):
        if path is not None:
            self.load(path)
        else:
            self.clas = prepare_clas()
            self.pca = None

    def learn(self, datadir, appname, extrapath, extrascr):
        (datapts, _, _, _) = load_datapts(datadir, appname, extrapath, extrascr)
        train_lbls = list(map(lambda x: x['tag'], datapts))
        (train_keys, mydict, self.tree_vec, self.act_vec, self.img_vec, self.title_vec,
         self.scaler) = vectorize_train(datapts)

        if use_pca:
            self.pca = PCA(n_components=n_components)
            train_keys = self.pca.fit_transform(train_keys)

        self.clas.fit(train_keys, train_lbls)
        self.classes = self.clas.classes_

    @perfmon.op("screen", "classify", True)
    def classify(self, actname, imgfile, tree):
        #if tree is None:
        #    test_pt = prepare_point(xmlsrc, actname, imgfile)
        #else:
        test_pt = prepare_point(actname, imgfile, tree=tree)
        logger.info("ocr result: %s", test_pt['img'])
        test_keys = vectorize_test([test_pt], self.tree_vec, self.act_vec, self.img_vec,
                                   self.title_vec, self.scaler)
        if use_pca:
            test_keys = self.pca.transform(test_keys)

        try:
            scores = self.clas.decision_function(test_keys)[0]
            if config.classify_use_bound:
                score = config.SCREEN_SCORE_BOUND
            else:
                score = -1000
            pred = 'NONE'

            for i in range(len(self.classes)):
                if scores[i] > score:
                    score = scores[i]
                    pred = self.classes[i]
            logger.info("score: %.3f", score)
        except:
            pred = self.clas.predict(test_keys)[0]

        return pred
#        return self.clas.predict(test_keys)[0]

    def save(self, path):
        joblib.dump(
            [self.clas, self.classes, self.pca, self.tree_vec, self.act_vec, self.img_vec,
             self.title_vec, self.scaler], path)

    def load(self, path):
        [self.clas, self.classes, self.pca, self.tree_vec, self.act_vec, self.img_vec,
         self.title_vec, self.scaler] = joblib.load(path)


def learn(datadir, appname, extrapath, extrascr):
    clas = ScreenClassifier()
    clas.learn(datadir, appname, extrapath, extrascr)
    return clas


def modelfile(modelpath, appname):
    if appname is None:
        return os.path.join(modelpath, 'screen')
    else:
        return os.path.join(modelpath, 'screen_%s' % appname)


def load(modelpath, appname):
    path = modelfile(modelpath, appname)
    if os.path.exists(path):
        clas = ScreenClassifier(path)
        return clas
    else:
        return None


def getmodel(modelpath, datadir, appname, extrapath, extrascr):
    clas = load(modelpath, appname)
    if clas is None:
        clas = learn(datadir, appname, extrapath, extrascr)
        clas.save(modelfile(modelpath, appname))
    return clas


def merge_cnt(s, case):
    for item in case:
        s[item] = s.get(item, 0) + case[item]


def merge_list2(s, case):
    for item in case:
        if item not in s:
            s[item] = {}
        for key in case[item]:
            s[item][key] = s[item].get(key, []) + case[item][key]


def run_evaluation():
    global report_exact
    global detail_report
    global check_train
    global nopt

    parser = argparse.ArgumentParser(description="Classifier")
    parser.add_argument('--cat', help='category')
    parser.add_argument('--extra', help='extra category')
    parser.add_argument('--app', help='only for app', default='ALL')
    parser.add_argument('--screen', help='only for screen', default='ALL')
    parser.add_argument('--term', help='only for term', default='ALL')
    parser.add_argument('--quiet', help='no detail',
                        default=False, action='store_const', const=True)
    parser.add_argument('--reallyquiet', help='no any detail',
                        default=False, action='store_const', const=True)
    parser.add_argument('--nopt', help='ignore pt cache',
                        default=False, action='store_const', const=True)
    parser.add_argument('--show', help='show feature',
                        default=False, action='store_const', const=True)
    parser.add_argument('--guispath', help='data path', default=DATADIR)
    parser.add_argument('--tagspath', help='tags path', default="../etc/tags.txt")
    parser.add_argument('--extrapath', help='extra data path', default="../guis-extra/")
    parser.add_argument('--extrascr', help='extra screens', default=config.extra_screens)
    parser.add_argument('--seed', help='random seed', default=0, type=int)
    parser.add_argument('--apps', help='only use apps from arg')
    args = parser.parse_args()

    if args.cat:
        args.guispath = "../guis-%s/" % args.cat
        args.tagspath = "../etc-%s/" % args.cat
        args.apps = "../etc-%s/applist.txt" % args.cat

    if args.extra:
        args.extrapath = "../guis-%s/" % args.extra

    taginfo.load(args.tagspath)

    if args.reallyquiet:
        report_exact = False
        detail_report = False
        check_train = False

    if args.quiet:
        report_exact = False

    if args.nopt:
        nopt = True

    logger.info("Loading pts")
    (datapts, apps, tags, cnt_by_tag) = load_datapts(args.guispath,
                                                     extrapath=args.extrapath,
                                                     extrascr=args.extrascr)

    if args.show:
        for pt in datapts:
            if args.app and pt['app'] != args.app:
                continue
            if args.screen and pt['scr'] != args.screen:
                continue
            print(pt['file'])
            print('tree:', re.sub(r'\s+', ' ', pt['tree']))

    if args.apps:
        select_apps = open(args.apps).read().strip().split(',')
        select_pts = []
        #select_tags = []
        for i in range(len(datapts)):
            if datapts[i]['app'] in select_apps or datapts[i]['extra']:
                select_pts.append(datapts[i])

        apps = select_apps
        datapts = select_pts

    if args.app.startswith('SEL'):
        random.seed(args.seed)
        app_count = int(args.app[3:])
        select_apps = []
        all_apps = apps
        for i in range(app_count):
            selected = random.choice(all_apps)
            select_apps.append(selected)
            all_apps.remove(selected)
        print("selected: %s" % select_apps)

        select_pts = []
        #select_tags = []
        for i in range(len(datapts)):
            if datapts[i]['app'] in select_apps or datapts[i]['extra']:
                select_pts.append(datapts[i])

        apps = select_apps
        datapts = select_pts
        #tags = select_tags
        args.app = 'ALL'

    logger.info("Evaluating, pt cnt: %d" % len(datapts))
    if args.app != 'ALL' and args.screen != 'ALL':
        return evaluate_single(datapts, args.app, args.screen, args.term)

    test_err = 0
    test_correct = 0
    tot_score = 0
    score_count = 0

    errs = {} # type: Dict[str, int]
    err_by_tag = {} # type: Dict[str, int]
    case_by_app = {} # type: Dict[str, int]
    err_detail = {} # type: Dict[str, int]

    tot_webview = 0
    err_webview = 0

    if args.app != 'ALL':
        score_count = 1
        (tot_score, test_err, test_correct, errs, err_by_tag,
         case_by_app, err_detail, err_webview, tot_webview) = evaluate(
             datapts, apps, tags, app=args.app, evalscreen=args.screen)
    else:
        pool = multiprocessing.Pool(processes=thread_count)
        for (xtot_score, xtest_err, xtest_correct, xerrs, xerr_by_tag,
             xcase_by_app, xerr_detail, xerr_webview, xtot_webview) in pool.map(
                 functools.partial(evaluate, datapts, apps, tags,
                                   evalscreen=args.screen), apps):
            if xtot_score is not None:
                score_count += 1
                tot_score += xtot_score
                test_err += xtest_err
                test_correct += xtest_correct
                tot_webview += xtot_webview

                merge_cnt(errs, xerrs)
                merge_cnt(err_by_tag, xerr_by_tag)
                merge_cnt(case_by_app, xcase_by_app)
                merge_list2(err_detail, xerr_detail)
                err_webview += xerr_webview

        pool.close()

    if detail_report:
        print("errs:")
        for app in apps:
            if app in errs:
                if app not in case_by_app:
                    case_by_app[app] = 1
                print("  %12s: %3d / %3d %.3f" % (app, errs[app], case_by_app[app],
                                                  1.0 * errs[app] / case_by_app[app]))
            if app in err_detail:
                for tag in tags:
                    if tag in err_detail[app]:
                        print(" tag %9s: %3d %s" % (tag, len(err_detail[app][tag]),
                                                    ' '.join(err_detail[app][tag])))
        print("err by tag:")
        for tag in (tags if args.screen == 'ALL' else [args.screen]):
            if tag not in err_by_tag:
                err_by_tag[tag] = 0
            print("  %10s: %3d / %3d %.3f" % (
                tag, err_by_tag[tag], cnt_by_tag[tag],
                1.0 * err_by_tag[tag] / cnt_by_tag[tag]))

        print("test cases: %d- %d+   total: %d" % (test_err, test_correct, test_err +
                                                   test_correct))
        print("error of webview: %d / %d" % (err_webview, tot_webview))
    print("final test: %.3f total: %d/%d" % (tot_score / score_count, test_correct,
                                             test_correct + test_err))

    #sklearn.tree.export_graphviz(
    #clas, feature_names=mydict, class_names=clas.classes_, out_file="tree.dot")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_evaluation()
