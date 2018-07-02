#!/usr/bin/env python3

from sklearn import svm
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.base import TransformerMixin
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import PredefinedSplit
#from sklearn.tree import DecisionTreeClassifier
#from sklearn.ensemble import AdaBoostClassifier, RandomForestClassifier
#from sklearn.naive_bayes import GaussianNB, MultinomialNB
from sklearn.neural_network import MLPClassifier # noqa
#from sklearn.multiclass import OneVsOneClassifier
#from sklearn.decomposition import PCA, TruncatedSVD
from sklearn.preprocessing import StandardScaler
from sklearn.externals import joblib
import skimage.io
import skimage.transform
import skimage.feature
import skimage.filters
from PIL import Image
from tesserocr import PyTessBaseAPI
import numpy
import multiprocessing
import functools
import random

import re
import glob
import os
import logging
import pickle
import argparse

import analyze
import util
import tags
import config
import perfmon
import sense
import hidden
#import webdriver

logger = logging.getLogger("elements")

anything_re = re.compile(".*")
id_re = re.compile("[a-zA-Z]?[a-z]+")
text_re = re.compile("[a-zA-Z]+")
digit_re = re.compile("[0-9]+")

REP_COUNT = {'signin': 10, 'register': 10, 'cart': 2, 'detail': 2, 'searchret': 2,
             'cat1': 10}
#CONV = {'lastname': 'name',
#        'firstname': 'name',
#        'register_name': 'name',
#        'password2': 'password',
#        'cat_image': None,
#        'email2': 'email'}
PARENT_DEPTH_LIMIT = 2
#ONLY_CARE_LABEL = {'main': ['search', 'cart', 'searchbox', 'menu'],
#                   'cart': ['checkout', 'back']}
#IGNORE_LABELS = {'signin': ['signin'],
#                 'register': ['signup', 'address'],
#                 'searchret': ['item_brand', 'item_title', 'item_price', 'searchbox',
#                               'item_image'],
#                 'detail': ['share', 'cart_count', 'searchbox', 'detail_brand',
#                 'filter'],
#                 'cat': ['filter'],
#                 'cat1': ['account', 'cart_count', 'cat_title'],
#                 'cat2': ['filter', 'cart_count', 'cat_title'],
#                 'cat3': ['filter', 'cart_count', 'cat_title']}
#ONLY_CARE_LABEL = []
BINARY = False
OBSERVE_ONLY = [] # type: List[str]

print_perapp = False
print_detail = True
print_points = False
print_per_screen = True
print_empty_pt = True
print_train = True
save_err = False
nopt = False
show_correct_pts = False

use_rep = False
use_threshold = True
use_single = True

try_all = False

use_bool = [True, True, True, True, False, False]
BOOL_CONST = 1.0


def get_tesapi():
    return PyTessBaseAPI(lang='eng')


def set_tes_image(tesapi, imgdata):
    imgpil = Image.fromarray(numpy.uint8(imgdata * 255))
    tesapi.SetImage(imgpil)


def add_ctx_attr(point, ctx, data, attr_re, word_limit=1000):
    if ctx not in point:
        point[ctx] = ''
    words = attr_re.findall(data)
    if word_limit and len(words) > word_limit:
        return
    for word in words:
        if point[ctx]:
            point[ctx] += ' '
        point[ctx] += '%s' % word.lower()


def add_ctx(point, ctx, node, attrs, attr_re=anything_re, word_limit=None):
    for attr in attrs:
        add_ctx_attr(point, ctx, node[attr], attr_re, word_limit)


def collect_text(node, tree):
    cls = node['class']
    if cls == 'View':
        text = node['desc']
    else:
        text = node['text']

    for child in node['children']:
        text += ' ' + collect_text(tree[child], tree)
    return text


def prepare_neighbour(tree, itemid, point):
    node = tree[itemid]
    point['neighbour_ctx'] = ''
    point['adj_ctx'] = ''
    neighbour_count = 0
    for other in tree:
        if tree[other]['parent'] == node['parent'] and other != itemid:
            #            and tree[other]['childid'] < node['childid']):
            add_ctx_attr(point, 'neighbour_ctx', collect_text(tree[other], tree), text_re)
            add_ctx(point, 'neighbour_ctx', tree[other], ['id'], id_re)
            if tree[other]['class'] == node['class']:
                neighbour_count += 1

#        if (tree[other]['x'] + tree[other]['width'] == node['x'] or
#            tree[other]['y'] + tree[other]['height'] == node['y']):
            # left adjacent
        if (tree[other]['parent'] == node['parent'] and other != itemid and
                tree[other]['childid'] < node['childid'] and
                tree[other]['childid'] > node['childid'] - 2):
            add_ctx_attr(point, 'adj_ctx', collect_text(tree[other], tree), text_re)
            add_ctx(point, 'adj_ctx', tree[other], ['id'], id_re)

    point['neighbour_count'] = neighbour_count
    point['node_childs'] = len(node['children'])
    point['node_childid'] = node['childid']


def prepare_point(tree, itemid, app, scr, caseid, imgdata, treeinfo, tesapi):
    point = {}
    point['app'] = app
    point['scr'] = scr
    point['case'] = caseid
    point['id'] = itemid
    point['str'] = util.describe_node(tree[itemid], None)

    node = tree[itemid]
    #cls = node['class']
    add_ctx_attr(point, 'node_text', collect_text(node, tree), text_re, 10)
    add_ctx(point, 'node_ctx', node, ['desc'], text_re)
    add_ctx(point, 'node_ctx', node, ['id'], id_re)
    add_ctx(point, 'node_class', node, ['class'], id_re)
    if 'Recycler' in node['class'] or 'ListView' in node['class']:
        point['node_class'] += " ListContainer"
    point['node_x'] = node['x']
    point['node_y'] = node['y']
    point['node_w'] = node['width']
    point['node_h'] = node['height']
    point['node_word_count'] = len(text_re.findall(node['text']))
    point['node_digits'] = len(digit_re.findall(node['text']))

    prepare_neighbour(tree, itemid, point)

    parent = node['parent']
    point['parent_ctx'] = ''
    parent_click = parent_scroll = parent_manychild = False
    parent_depth = 0
    while parent != 0 and parent != -1 and parent_depth < PARENT_DEPTH_LIMIT:
        add_ctx(point, 'parent_ctx', tree[parent], ['class', 'id'], id_re)
        parent_click |= tree[parent]['click']
        parent_scroll |= tree[parent]['scroll']
        parent_manychild |= len(tree[parent]['children']) > 1
        parent = tree[parent]['parent']
        parent_depth += 1
    point['parent_prop'] = [parent_click, parent_scroll, parent_manychild]

    has_dupid = False
    is_itemlike = False
    is_listlike = False
    for _id in node['raw']:
        if _id in treeinfo['dupid']:
            has_dupid = True
            break
    for _id in node['raw']:
        if _id in treeinfo['itemlike']:
            is_itemlike = True
            break
    for _id in node['raw']:
        if _id in treeinfo['listlike']:
            is_listlike = True
            break
    point['node_prop'] = [node['click'], node['scroll'], len(node['children']) > 1,
                          has_dupid, is_itemlike, is_listlike]

    prepare_img(point, node, imgdata, tesapi)

    return point


def prepare_img(point, node, imgdata, tesapi):
    # your widget should be inside the screenshot
    #assert(node['y'] + node['height'] <= imgdata.shape[0])
    #assert(node['x'] + node['width'] <= imgdata.shape[1])
    (min_x, min_y) = (node['x'], node['y'])
    if min_x < 0:
        min_x = 0
    if min_y < 0:
        min_y = 0

    (max_x, max_y) = (node['x'] + node['width'], node['y'] + node['height'])
    if max_x > imgdata.shape[1]:
        if not node['webview']:
            logger.debug("%s widget x2 %d > %d" % (util.describe_node(node, short=True),
                                                   max_x, imgdata.shape[1]))

        max_x = imgdata.shape[1]
    if max_y > imgdata.shape[0]:
        if not node['webview']:
            logger.debug("widget y2 %s %d > %d" % (util.describe_node(node, short=True),
                                                   max_y, imgdata.shape[0]))

        max_y = imgdata.shape[0]
    real_width = max(max_x - min_x, 0)
    real_height = max(max_y - min_y, 0)
    #min_dim = min(real_width, real_height)
    if real_width * real_height == 0:
        myimg_thr = numpy.zeros([32, 32], float)
        logger.debug("empty image!")
    else:
        try:
            myimg = imgdata[min_y: max_y, min_x: max_x]
            #myimg = imgdata[min_y: min_y + min_dim, min_x: min_x + min_dim]
            myimg = skimage.transform.resize(myimg, (32, 32), mode='constant')
        except:
            logger.error("ERROR at %s %dx%d-%dx%d" % (util.describe_node(node),
                                                      min_x, min_y, max_x, max_y))
            raise
#    myimg = imgdata[node['origy']: node['origy'] + node['origh'],
#                    node['origx']: node['origx'] + node['origw']]
#    point['img'] = myimg
        if use_threshold:
            if myimg.max() - myimg.min() < 1e-6:
                thres = 0.5
            else:
                thres = skimage.filters.threshold_otsu(myimg)
            myimg_thr = myimg >= thres
            myimg_thr = skimage.img_as_float(myimg_thr)
        else:
            myimg_thr = myimg

        if myimg_thr.mean() < 0.2:
            myimg_thr = 1.0 - myimg_thr

        point['img_thr'] = myimg_thr
#    point['img_flat'] = myimg_thr.flatten()
    img_feature = skimage.feature.hog(myimg_thr, orientations=8, pixels_per_cell=(8, 8),
                                      cells_per_block=(1, 1), block_norm='L1')
#    print(len(img_feature))
    point['img_hog'] = img_feature

    if config.elements_use_ocr:
        ocr_text = node['ocr']
        #and real_width * real_height > 0:
        #tesapi.SetRectangle(node['x'], node['y'], node['width'], node['height'])
        #try:
        #    ocr_text = tesapi.GetUTF8Text()
        #except:
        #    logger.warning("tessearact fail to recognize")
        #    ocr_text = ''
        #ocr_text = ocr_text.strip().replace('\n', ' ')
    else:
        ocr_text = 'dummy'
    point['node_ocr'] = ocr_text
    #if point['node_text'].strip() == '':
    #    point['node_text'] = ocr_text
    logger.debug("%s VS %s" % (ocr_text, node['text']))


def print_point(point):
    print(point['str'])
    for prop in sorted(point):
        if (prop != 'str' and prop != 'img_hog' and prop != 'img' and
            prop != 'img_flat' and prop != 'img_thr'):
            print("%30s = %s" % (prop, point[prop]))


class ColumnExtractor(TransformerMixin):
    def __init__(self, column):
        self.column = column

    def transform(self, X, **transform_params):
        result = []
        for row in X:
            result.append(row[self.column])
        return numpy.asarray(result)

    def fit(self, X, y=None, **fit_params):
        return self

    def get_params(self, deep=True):
        return {}

    def set_params(self, **params):
        return self


def normalize_count(count, maxval):
    if count > maxval:
        return 1.0
    else:
        return 1.0 * count / maxval


class SizeTransformer(TransformerMixin):
    def transform(self, X, **transform_params):
        result = []
        for row in X:
            try:
                result.append([row['node_w'] / config.width, row['node_h'] /
                               config.height, row['node_x'] / config.width,
                               row['node_y'] / config.height,
                               normalize_count(row['node_childs'], 10),
                               normalize_count(row['neighbour_count'], 10),
                               normalize_count(row['node_word_count'], 20),
                               normalize_count(row['node_digits'], 1)])
    #                           row['node_childid'] / 10.0])
            except:
                print(row)
                raise
        return numpy.asarray(result)

    def fit(self, X, y=None, **fit_params):
        return self

    def get_params(self, deep=True):
        return {}

    def set_params(self, **params):
        return self


class BooleanVectorizer(TransformerMixin):
    def transform(self, X, **transform_params):
        result = []
        for row in X:
            rowret = []
            for i in range(len(row)):
                if use_bool[i] and row[i]:
                    rowret.append(BOOL_CONST)
                else:
                    rowret.append(0.0)
            result.append(rowret)
        return numpy.asarray(result)

    def fit(self, X, y=None, **fit_params):
        return self

    def get_params(self, deep=True):
        return {}

    def set_params(self, **params):
        return self


class Dumper(TransformerMixin):
    def transform(self, X, **transform_params):
        for row in X:
            self.dump(row)
        return X

    def fit(self, X, y=None, **fit_params):
        return self

    def get_params(self, deep=True):
        return {}

    def set_params(self, **params):
        return self

    def dump(self, row):
        print(row)


def has_label(tree):
    for itemid in tree:
        if tree[itemid]['tags']:
            return True
    return False


def prepare_pipeline(use_clf=None):
    #clf = svm.SVC(kernel='rbf', decision_function_shape='ovr', class_weight='balanced',
    #C=100)
    if use_clf is None:
        clf = svm.LinearSVC(dual=True, class_weight='balanced', C=0.01)
        #clf = DecisionTreeClassifier(max_depth=100, random_state=0)
        #clf = AdaBoostClassifier()
        #clf = MLPClassifier(hidden_layer_sizes=(30, 30,), max_iter=1000,
        #                    early_stopping=False,
        #                    random_state=0)
    else:
        clf = use_clf

#    img_clf = MLPClassifier(hidden_layer_sizes=(100, 100,), max_iter=1000,
#                            early_stopping=False, random_state=0)
    img_clf = svm.LinearSVC()

    binary = BINARY

    pipeline = Pipeline([
        ('features', FeatureUnion(transformer_list=[
            ('node_cls', Pipeline([
                ('extract', ColumnExtractor('node_class')),
                ('vec', TfidfVectorizer(token_pattern=id_re.pattern, binary=binary,
                                        sublinear_tf=True)),
                #                ('scale', StandardScaler(with_mean=False))
            ])),
            ('node_text', Pipeline([
                ('extract', ColumnExtractor('node_text')),
                ('vec', TfidfVectorizer(binary=binary, sublinear_tf=True)),
                #                ('scale', StandardScaler(with_mean=False))
            ])),
            ('node_ctx', Pipeline([
                ('extract', ColumnExtractor('node_ctx')),
                ('vec', TfidfVectorizer(binary=binary, sublinear_tf=True)),
                #                ('scale', StandardScaler(with_mean=False))
            ])),
            ('size', Pipeline([
                ('vec', SizeTransformer()),
                ('scale', StandardScaler()),
            ])),
            ('prop', Pipeline([
                ('extract', ColumnExtractor('node_prop')),
                ('vec', BooleanVectorizer()),
                ('scale', StandardScaler()),
            ])),
            ('p_ctx', Pipeline([
                ('parent_ctx_extract', ColumnExtractor('parent_ctx')),
                ('parent_ctx_vec', TfidfVectorizer(binary=binary, sublinear_tf=True)),
                #                ('scale', StandardScaler(with_mean=False))
            ])),
            ('parent_prop', Pipeline([
                ('extract', ColumnExtractor('parent_prop')),
                ('vec', BooleanVectorizer()),
                ('scale', StandardScaler()),
            ])),
            ('nb_ctx', Pipeline([
                ('extract', ColumnExtractor('neighbour_ctx')),
                ('vec', TfidfVectorizer(binary=binary, sublinear_tf=True)),
                #                ('scale', StandardScaler(with_mean=False))
            ])),
            ('adj_ctx', Pipeline([
                ('extract', ColumnExtractor('adj_ctx')),
                ('vec', TfidfVectorizer(binary=binary, sublinear_tf=True)),
                #                ('scale', StandardScaler(with_mean=False))
            ])),
            ('img_hog', ColumnExtractor('img_hog')),
            ('node_ocr', Pipeline([
                ('extract', ColumnExtractor('node_ocr')),
                ('vec', TfidfVectorizer(binary=binary, sublinear_tf=True)),
            ])),
        ],
            transformer_weights={
                # text
                'node_text': 1.0,
                # ctx
                'node_cls': 1.0,
                'node_ctx': 1.0,
                # neighbour
                'nb_ctx': 1.0,
                'adj_ctx': 1.0,
                # graphical
                'img_hog': 1.0,
                # ocr
                'node_ocr': 1.0,
                # metadata
                'size': 1.0,
                'prop': 1.0,
                # ancestor
                'p_ctx': 1.0,
                'parent_prop': 1.0,
        },
        )),
        #        ('pca', TruncatedSVD(n_components=100)),
        ('svc', clf)
    ])

    #print(pipeline.get_params().keys())

    pipeline.set_params(
        features__node_text__vec__ngram_range=(1, 2),
        features__node_text__vec__max_df=0.8,
        features__node_text__vec__min_df=2,
        features__node_text__vec__stop_words=None,
        features__node_cls__vec__ngram_range=(1, 2),
        features__node_cls__vec__max_df=0.8,
        features__node_cls__vec__min_df=2,
        features__node_cls__vec__stop_words=None,
        features__node_ctx__vec__ngram_range=(1, 2),
        features__node_ctx__vec__max_df=0.8,
        features__node_ctx__vec__min_df=2,
        features__node_ctx__vec__stop_words=None
    )

    img_pipeline = Pipeline([
        ('ext', ColumnExtractor('img_flat')),
        ('cnn', img_clf)
    ])

    return (pipeline, img_pipeline)


def collect_files(datadir):
    return (glob.glob(os.path.join(datadir, "*.xml")) +
            glob.glob(os.path.join(datadir, "*.hier")))


def collect_extrafiles(extradir, extrascr):
    logger.info("loading extra input from %s for %s", extradir, extrascr)
    extrascr = extrascr.split(',')
    extrafiles = []
    for filename in collect_files(extradir):
        scrname = filename.split('/')[-1].split('.')[0].split('_', 2)[-1]
        if scrname not in extrascr:
            continue
        extrafiles.append(filename)
    return extrafiles


def load_point(no_appname, filename):
    points = []
    labels = []
    apps = []
    scrs = []

    filebase = os.path.splitext(filename)[0]
    featurefile = filebase + '.pts'
    (appname, caseid, scrname) = re.search('([a-z0-9]+)_?([0-9]+)?_([a-z0-9]+)',
                                           filename).groups()

    if appname is not None and appname == no_appname:
        return (points, labels, apps, scrs)

    if scrname in tags.tag['ignored_screens']:
        return (points, labels, apps, scrs)

    if os.path.exists(featurefile) and not nopt:
        featuref = open(featurefile, 'rb')
        unpickler = pickle.Unpickler(featuref)
        count = unpickler.load()

        for i in range(count):
            try:
                point = unpickler.load()
                pt_tag = unpickler.load()
                appname = unpickler.load()
                scrname = unpickler.load()

                points.append(point)
                labels.append(pt_tag)
                apps.append(appname)
                scrs.append(scrname)
            except:
                break
        return (points, labels, apps, scrs)

    if not nopt and print_empty_pt:
        logger.info("analyzing %s", filename)
    tree = analyze.load_tree(filename)

    hidden.find_hidden_ocr(tree)
    hidden.mark_children_hidden_ocr(tree)
    #if '.xml' in filename:
    #    tree = analyze.analyze([filename], show_progress=False)[0]
#   #     if scrname.startswith('cat'):
#   #         scrname = "cat"
    #else:
    #    loaded = webdriver.load(filebase)
    #    descs = util.load_desc(filebase)
    #    tree = analyze.analyze_items(loaded['items'], descs=descs)

    if not has_label(tree):
        logger.info("%s: no label", filename)
        return (points, labels, apps, scrs)

    pngfile = filebase + '.png'
    imgdata = skimage.io.imread(pngfile, as_grey=True)

    imgdata = skimage.transform.resize(imgdata, (config.height, config.width),
                                       mode='constant')

    featuref = open(featurefile, 'wb')
    pickler = pickle.Pickler(featuref)
    pickler.dump(len(sorted(tree)))

    treeinfo = analyze.collect_treeinfo(tree)

    tesapi = get_tesapi()
    set_tes_image(tesapi, imgdata)

    for itemid in sorted(tree):
        try:
            point = prepare_point(tree, itemid, appname, scrname, caseid, imgdata,
                                  treeinfo, tesapi)
        except ValueError:
            logger.exception("ERROR at %s" % filename)
            return (points, labels, apps, scrs)
        pt_tag = 'NONE'
        if len(tree[itemid]['tags']) > 0:
            firsttag = tree[itemid]['tags'][0]
            #if tags.valid(scrname, firsttag):
            pt_tag = firsttag

#                firsttag = CONV.get(firsttag, firsttag)
#                if firsttag is not None:
#                    if (not scrname in ONLY_CARE_LABEL or
#                        not ONLY_CARE_LABEL[scrname] or
#                        firsttag in ONLY_CARE_LABEL[scrname]):
#                        pt_tag = firsttag
#
#                    if scrname in IGNORE_LABELS and pt_tag in IGNORE_LABELS[scrname]:
#                        pt_tag = 'NONE'

#        cnt[pt_tag] = cnt.get(pt_tag, 0) + 1
#            skimage.io.imsave("%s_%d.png" % (pt_tag, cnt[pt_tag]), point['img_thr'])

        for i in range(REP_COUNT.get(scrname, 1) if use_rep else 1):
            points.append(point)
            labels.append(pt_tag)
            apps.append(appname)
            scrs.append(scrname)

        pickler.dump(point)
        pickler.dump(pt_tag)
        pickler.dump(appname)
        pickler.dump(scrname)

        if print_points:
            print_point(point)

    return (points, labels, apps, scrs)


def load_points(files, show_progress=True, no_appname=None, extra=[]):
    #    files = sklearn.utils.shuffle(files, random_state=0)
    #    rets = analyze.analyze(files, show_progress=show_progress)
    #    for tree in rets:
    #        analyze.print_tree(tree)

    points = []
    labels = []
    apps = []
    scrs = []
    #cnt = {}
    pool = multiprocessing.Pool(processes=config.threads)
    rets = pool.map(functools.partial(load_point, no_appname), files)
    #for i in progress(range(len(files))):
    for (xpoints, xlabels, xapps, xscrs) in rets:
        for i in range(len(xpoints)):
            xpoints[i]['extra'] = False
            if try_all:
                xscrs[i] = 'ALL'
            if xlabels[i] != 'NONE' and not tags.valid(xscrs[i], xlabels[i]):
                xlabels[i] = 'NONE'
        points += xpoints
        labels += xlabels
        apps += xapps
        scrs += xscrs
    rets = pool.map(functools.partial(load_point, no_appname), extra)
    #for i in progress(range(len(files))):
    for (xpoints, xlabels, xapps, xscrs) in rets:
        for i in range(len(xpoints)):
            xpoints[i]['extra'] = True
            if xlabels[i] != 'NONE' and not tags.valid(xscrs[i], xlabels[i]):
                xlabels[i] = 'NONE'

            if xlabels[i] != 'NONE':
                points.append(xpoints[i])
                labels.append(xlabels[i])
                apps.append(xapps[i])
                scrs.append(xscrs[i])
    pool.close()

    return (points, labels, apps, scrs)


class ElementClassifier(object):
    def __init__(self, path=None):
        if path is not None:
            self.load(path)
        else:
            self.pipelines = {}
        self.tesapi = get_tesapi()

    def learn(self, datadir, appname, extrapath, extrascr):
        files = collect_files(datadir)
        extrafiles = collect_extrafiles(extrapath, extrascr)
        (points, labels, _, scrs) = load_points(files, no_appname=appname,
                                                extra=extrafiles)

        for scr in sorted(set(scrs)):
            scr_points = []
            scr_labels = []
            pipeline = prepare_pipeline()[0]

            for i in range(len(points)):
                if scrs[i] == scr:
                    scr_points.append(points[i])
                    scr_labels.append(labels[i])

            try:
                pipeline.fit(scr_points, scr_labels)
            except:
                logger.exception("fit error")
                print(scr)
                print(scr_labels)
                raise
            self.pipelines[scr] = pipeline

    def set_page(self, imgdata):
        set_tes_image(self.tesapi, imgdata)

    def set_imgfile(self, imgfile):
        self.tesapi.SetImageFile(imgfile)
        self.imgdata = sense.load_image(imgfile)

    @perfmon.op("elements", "classify")
    def classify(self, scr, tree, itemid, imgdata, treeinfo, with_point=False):
        if imgdata is None:
            imgdata = self.imgdata
        point = prepare_point(tree, itemid, '', scr, 0, imgdata, treeinfo,
                              self.tesapi)
        if scr in self.pipelines:
            pipeline = self.pipelines[scr]
            try:
                scores = pipeline.decision_function([point])[0]
            except:
                logger.error("error at item %s", tree[itemid])
                logger.error("  pt: %s", point)
                raise
            classes = pipeline.classes_

            if len(classes) == 2:
                scores = [0.0, scores]

            if config.elements_use_bound:
                best_score = config.ELEMENTS_SCORE_BOUND
                result = 'NONE'
            else:
                best_score = None
                result = None

            for i in range(len(classes)):
                if best_score is None or scores[i] > best_score:
                    best_score = scores[i]
                    result = classes[i]
            #return pipeline.predict([point])[0]
            if with_point:
                return (result, best_score, point)
            else:
                return (result, best_score)
        if with_point:
            return (None, None, point)
        else:
            return (None, None)

    def save(self, path):
        joblib.dump(self.pipelines, path)

    def load(self, path):
        self.pipelines = joblib.load(path)


def learn(datadir, appname, extrapath, extrascr):
    clas = ElementClassifier()
    clas.learn(datadir, appname, extrapath, extrascr)
    return clas


def modelfile(modelpath, appname):
    if appname is None:
        return os.path.join(modelpath, 'element')
    else:
        return os.path.join(modelpath, 'element_%s' % appname)


def load(modelpath, appname):
    path = modelfile(modelpath, appname)
    if os.path.exists(path):
        clas = ElementClassifier(path)
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


def evaluate(scr_points, scr_labels, scr_apps, indices):
    good_cnt = {}
    bad_cnt = {}
    badpred_cnt = {}
    conf_cnt = {}
    (train_idx, test_idx) = indices
    (pipeline, img_pipeline) = prepare_pipeline()
    #print('test:', scr_apps[test_idx[0]])
    X_train = []
    X_test = []
    y_train = []
    y_test = []
    for idx in train_idx:
        X_train.append(scr_points[idx])
        y_train.append(scr_labels[idx])
    for idx in test_idx:
        if scr_points[idx]['extra']:
            continue
        X_test.append(scr_points[idx])
        y_test.append(scr_labels[idx])

    if len(X_test) == 0:
        return (0, 0, 0, 0, good_cnt, bad_cnt, badpred_cnt, conf_cnt, None)

    X_labeled = []
    y_labeled = []
    for i in range(len(y_train)):
        if y_train[i] != 'NONE':
            X_labeled.append(X_train[i])
            y_labeled.append(y_train[i])
    #print(len(X_train), len(X_test))
    #X_train, X_test, y_train, y_test = train_test_split(points, labels)
    #pipeline.fit(X_train, y_train)
    try:
        pipeline.fit(X_train, y_train)
        #pipeline.fit(X_labeled, y_labeled)
    except:
        logger.exception("fail to fit pts")
        print(scr_apps[test_idx[0]])
        print(y_train)
        print(y_test)
        raise
    #print(pipeline.score(X_test, y_test))
    classes = list(pipeline.classes_)
    if hasattr(pipeline, 'decision_function'):
        scores_all = pipeline.decision_function(X_test)
        if len(classes) == 2:
            scores_all_new = []
            for i in range(len(scores_all)):
                scores_all_new.append([0.0, scores_all[i]])
            scores_all = scores_all_new

    else:
        scores_all = pipeline.predict_proba(X_test)

    none_good = none_bad = tag_good = tag_bad = 0
    #preds = pipeline.predict(X_test)
    if config.elements_use_bound:
        preds = []
        scores = []
        for idx in range(len(X_test)):
            score = config.ELEMENTS_SCORE_BOUND
            pred = 'NONE'
            #print(scores_all[idx])
            for i in range(len(classes)):
                if scores_all[idx][i] > score and classes[i] != 'NONE':
                    score = scores_all[idx][i]
                    pred = classes[i]

            scores.append(score)
            preds.append(pred)

    else:
        preds = pipeline.predict(X_test)

        scores = []
        for item in scores_all:
            scores.append(max(item))

    if use_single:
        for i in range(len(X_test)):
            if tags.single(preds[i]):
                for j in range(len(X_test)):
                    if i != j and preds[i] == preds[j]:
                        a = X_test[i]
                        b = X_test[j]
                        orig_label = preds[i]
                        if (a['app'] == b['app'] and a['scr'] == b['scr'] and
                                a['case'] == b['case']):
                            if scores[i] > scores[j]:
                                weakidx = j
                            else:
                                weakidx = i
                            if config.elements_use_bound:
                                nextbest = config.ELEMENTS_SCORE_BOUND
                                preds[weakidx] = 'NONE'
                            else:
                                nextbest = -1000

                            for k in range(len(classes)):
                                if (classes[k] != preds[i] and
                                        (not config.elements_use_bound or
                                            classes[k] != 'NONE') and
                                        scores_all[weakidx][k] > nextbest):
                                    nextbest = scores_all[weakidx][k]
                                    preds[weakidx] = classes[k]
                            scores[weakidx] = nextbest

                            logger.debug("kicked one point from %s" % orig_label)

    if print_train:
        print('train: %d/%d %.3f/%.3f' % (len(y_labeled), len(y_train),
                                        pipeline.score(X_labeled, y_labeled),
                                        pipeline.score(X_train, y_train)))
    for idx in range(len(X_test)):
        my_scores = scores_all[idx]
        score = scores[idx]
        pred = preds[idx]

        correct = y_test[idx]
        if pred == correct:
            if pred != 'NONE':
                #if print_detail:
                #    print("good %s" % pred)
                tag_good += 1
            else:
                none_good += 1
            good_cnt[correct] = good_cnt.get(correct, 0) + 1
            if show_correct_pts and pred != 'NONE':
                print("good %s (%.3f)" % (pred, my_scores[classes.index(pred)]))
        else:
            if correct == 'NONE':
                none_bad += 1
            else:
                tag_bad += 1
            bad_cnt[correct] = bad_cnt.get(correct, 0) + 1
            badpred_cnt[pred] = badpred_cnt.get(pred, 0) + 1
            if (print_detail and (not OBSERVE_ONLY or (correct in OBSERVE_ONLY or pred in
                                                       OBSERVE_ONLY))):
                print_point(X_test[idx])
                if correct in classes:
                    corr_idx = classes.index(correct)
                    corr_score = my_scores[corr_idx]
                    corr_order = list(reversed(sorted(my_scores))).index(
                        my_scores[corr_idx])
                else:
                    corr_score = 0
                    corr_order = -1
                print("bad %s (%.3f) should be %s (%.3f)" % (
                    pred, my_scores[classes.index(pred)], correct, corr_score))
#                if save_err:
#                    skimage.io.imsave("%d_%s_%s_%s_%s.png" % (
#                        tag_bad+none_bad+all_tag_bad+all_none_bad, pred, correct,
#                        X_test[idx]['app'], X_test[idx]['scr']), X_test[idx]['img_thr'])

                print("confidence order: %d" % corr_order)

                cls_scores = []
                for i in range(len(classes)):
                    cls_scores.append([classes[i], my_scores[i]])
                cls_scores.sort(key=lambda x: x[1], reverse=True)

                ret = ''
                for item in cls_scores:
                    ret += " %s: %.3f" % (item[0], item[1])
                print(ret)
                conf_cnt[corr_order] = conf_cnt.get(corr_order, 0) + 1

    test_app = scr_apps[test_idx[0]]
    # per-app stat info for this screen
    if print_perapp or print_detail:
        print("%-20s good: %d,%d   bad: %d,%d" % (
            test_app.upper(), tag_good, none_good, tag_bad, none_bad))
    return (tag_good, tag_bad, none_good, none_bad,
            good_cnt, bad_cnt, badpred_cnt, conf_cnt, test_app)


def run_clas(files, eval_app, extrafiles):
    print("Analyzing files")
    (points, labels, apps, scrs) = load_points(files, extra=extrafiles)

    print("Point count: %d" % len(points))

    if len(points) == 0:
        print("No point matches specification!")
        return

    for i in range(len(labels)):
        if not tags.valid(scrs[i], labels[i]):
            labels[i] = 'NONE'

    sorted_apps = sorted(apps)

    global_tag_good = global_none_good = global_tag_bad = global_none_bad = 0
    global_good_cnt = {}
    global_bad_cnt = {}
    global_badpred_cnt = {}
    conf_cnt = {}
    app_stat = {}

    for scr in sorted(set(scrs)):
        scr_points = []
        scr_apps = []
        scr_labels = []
        for i in range(len(points)):
            if scr == 'ALL' or scrs[i] == scr:
                scr_points.append(points[i])
                scr_apps.append(apps[i])
                scr_labels.append(labels[i])

        if len(set(scr_apps)) == 1:
            # single-app screen, can't test
            continue
        if eval_app is None:
            split = PredefinedSplit(test_fold=list(map(
                lambda x: sorted_apps.index(x), scr_apps))).split()
        else:
            train_idx = []
            test_idx = []
            for i in range(len(scr_apps)):
                if scr_apps[i] != eval_app:
                    train_idx.append(i)
                else:
                    test_idx.append(i)
            if test_idx == []:
                continue
            split = [(train_idx, test_idx)]
            #        split = PredefinedSplit(test_fold=list(map(lambda x: 1 if x == 'etsy'
            #        else 0, scr_apps)))
        all_tag_good = all_none_good = all_tag_bad = all_none_bad = 0
        good_cnt = {}
        bad_cnt = {}
        badpred_cnt = {}

        pool = multiprocessing.Pool(processes=config.threads)
        rets = pool.map(functools.partial(evaluate, scr_points, scr_labels, scr_apps),
                        split)

        for (tag_good, tag_bad, none_good, none_bad,
             xgood, xbad, xbadpred, xconf, test_app) in rets:
            if test_app is None:
                continue

            all_tag_good += tag_good
            all_tag_bad += tag_bad
            all_none_good += none_good
            all_none_bad += none_bad

            merge_cnt(good_cnt, xgood)
            merge_cnt(bad_cnt, xbad)
            merge_cnt(badpred_cnt, xbadpred)
            merge_cnt(conf_cnt, xconf)

            if test_app not in app_stat:
                app_stat[test_app] = {}
            merge_cnt(app_stat[test_app], {'tag_good': tag_good, 'tag_bad': tag_bad,
                                           'none_good': none_good, 'none_bad': none_bad})
        pool.close()
        #for train_idx, test_idx in split.split():
        # per-screen stat info
        print("SCREEN %20s   good: %4d,%4d   bad: %4d,%4d  %.3f %.3f" % (
            scr, all_tag_good, all_none_good, all_tag_bad, all_none_bad,
            1.0 * all_tag_good / (all_tag_good + all_tag_bad),
            1.0 * (all_tag_good + all_none_good) / (
                all_tag_bad + all_none_bad + all_tag_good + all_none_good)))
        if print_per_screen:
            print("IN ALL:  good: %d,%d   bad: %d,%d" % (
                all_tag_good, all_none_good, all_tag_bad, all_none_bad))
            print("PER TAG:")
            for item in sorted(set(list(good_cnt) + list(bad_cnt))):
                print("\t%s: %d+ %d- %d*" % (item, good_cnt.get(item, 0),
                                             bad_cnt.get(item, 0),
                                             badpred_cnt.get(item, 0)))
        global_tag_good += all_tag_good
        global_tag_bad += all_tag_bad
        global_none_good += all_none_good
        global_none_bad += all_none_bad
        merge_cnt(global_good_cnt, good_cnt)
        merge_cnt(global_bad_cnt, bad_cnt)
        merge_cnt(global_badpred_cnt, badpred_cnt)

    if len(scrs) > 1:
        print("GLOBAL:  good: %d,%d   bad: %d,%d  G/G: %.3f T/T: %.3f" % (
            global_tag_good, global_none_good, global_tag_bad, global_none_bad,
            1.0 * global_tag_good / (global_tag_bad + global_tag_good),
            1.0 * (global_tag_good + global_none_good) / (
                global_tag_bad + global_none_bad + global_tag_good + global_none_good)))
        print("PER TAG:")
        for item in sorted(set(list(global_good_cnt) + list(global_bad_cnt))):
            print("\t%s: %d+ %d- %d*" % (
                item, global_good_cnt.get(item, 0), global_bad_cnt.get(item, 0),
                global_badpred_cnt.get(item, 0)))

    global_tag_good = 0.0
    global_tag_good_cnt = 0
    global_all_good = 0.0
    global_all_good_cnt = 0
    global_none_good = 0.0
    global_none_good_cnt = 0
    for app in app_stat:
        entry = app_stat[app]
        if entry['tag_good'] + entry['tag_bad'] > 0:
            tag_good_per = 100.0 * entry['tag_good'] / (entry['tag_good'] +
                                                        entry['tag_bad'])
            global_tag_good += tag_good_per
            global_tag_good_cnt += 1
        else:
            tag_good_per = -1.0
        if (entry['tag_good'] + entry['tag_bad'] +
            entry['none_good'] + entry['none_bad'] > 0):
            all_good_per = 100.0 * (entry['tag_good'] + entry['none_good']) / (
                entry['tag_good'] + entry['tag_bad'] +
                entry['none_good'] + entry['none_bad'])
            global_all_good += all_good_per
            global_all_good_cnt += 1
            none_good_per = 100.0 * entry['none_good'] / (entry['none_good'] +
                                                          entry['none_bad'])
            global_none_good += none_good_per
            global_none_good_cnt += 1
        else:
            all_good_per = -1.0
        if print_perapp or print_detail:
            print("%s: good: %d, %d  bad: %d, %d  %.3f, %.3f" % (
                app, entry['tag_good'], entry['none_good'], entry['tag_bad'],
                entry['none_bad'], tag_good_per, all_good_per))
    global_tag_good /= global_tag_good_cnt
    global_all_good /= global_all_good_cnt
    global_none_good /= global_none_good_cnt
    print("FINAL app avg: +%.3f, *%.3f, -%.3f" % (
        global_tag_good, global_all_good, global_none_good))
    print("conf_order: %r" % conf_cnt)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Classifier")
    parser.add_argument('--cat', help='category')
    parser.add_argument('--extra', help='extra category')
    parser.add_argument('--app', help='only for app')
    parser.add_argument('--screen', help='only for screen')
    parser.add_argument('--quiet', help='no detail',
                        default=False, action='store_const', const=True)
    parser.add_argument('--reallyquiet', help='no screen detail',
                        default=False, action='store_const', const=True)
    parser.add_argument('--nopt', help='no pt cache',
                        default=False, action='store_const', const=True)
    parser.add_argument('--guispath', help='data path', default="../guis/")
    parser.add_argument('--tagspath', help='tags path', default="../etc/tags.txt")
    parser.add_argument('--extrapath', help='extra data path', default="../guis-extra/")
    parser.add_argument('--extrascr', help='extra screens',
                        default=config.extra_element_scrs)
    parser.add_argument('--apps', help='limit apps')
    parser.add_argument('--select', help='select apps', type=int)
    parser.add_argument('--seed', help='random seed', type=int)
    parser.add_argument('--detail', help='show detail',
                        default=False, action='store_const', const=True)
    args = parser.parse_args()

    if args.cat:
        args.guispath = "../guis-%s/" % args.cat
        args.tagspath = "../etc-%s/" % args.cat
        args.apps = "../etc-%s/applist.txt" % args.cat

    if args.extra:
        args.extrapath = "../guis-%s/" % args.extra

    if args.quiet:
        print_detail = False
    if args.reallyquiet:
        print_detail = False
        print_per_screen = False
        print_empty_pt = False
        print_train = False
    if args.nopt:
        nopt = True

    if args.detail:
        show_correct_pts = True

    tags.load(args.tagspath)

    if args.apps:
        select_apps = open(args.apps).read().strip().split(',')

    if args.select:
        random.seed(args.seed)
        evalapps = []
        for i in range(args.select):
            evalapp = random.choice(select_apps)
            evalapps.append(evalapp)

        print("selected: %s" % evalapps)
        select_apps = evalapps

    files = []
    for filename in collect_files(args.guispath):
        basename = os.path.basename(filename)
        appname = basename.split('_')[0]
        scrname = basename.split('.')[0].split('_')[-1]
        if args.screen and args.screen != scrname:
            continue
        if args.apps:
            if appname not in select_apps:
                continue
        files.append(filename)

    print("file count: %d" % len(files))

    extrafiles = []
    if args.extrapath is not None:
        extrascr = args.extrascr.split(',')
        for filename in collect_files(args.extrapath):
            basename = os.path.basename(filename)
            appname = basename.split('_')[0]
            scrname = basename.split('.')[0].split('_')[-1]
            if scrname not in extrascr:
                continue
            if args.screen and args.screen != scrname:
                continue
            extrafiles.append(filename)

    print("extra file count: %d" % len(extrafiles))

    run_clas(files, args.app, extrafiles)
