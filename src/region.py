#!/usr/bin/env python3

from sklearn import svm
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.base import TransformerMixin, BaseEstimator
from sklearn.feature_extraction.text import TfidfVectorizer
#from sklearn.tree import DecisionTreeClassifier
#from sklearn.ensemble import AdaBoostClassifier, RandomForestClassifier
#from sklearn.naive_bayes import GaussianNB, MultinomialNB
from sklearn.neural_network import MLPClassifier # noqa
#from sklearn.multiclass import OneVsOneClassifier
from sklearn.decomposition import TruncatedSVD # noqa
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

import re
import os
import logging
import pickle
import argparse
import time
import random

import analyze
import util
import tags
import config
import perfmon
import hidden

logger = logging.getLogger("region")

anything_re = re.compile(".*")
id_re = re.compile("[a-zA-Z]+")
text_re = re.compile("[a-zA-Z]+")
digit_re = re.compile("[0-9]+")

PARENT_DEPTH_LIMIT = 2
BINARY = False
OBSERVE_ONLY = [] # type: List[str]

print_perapp = False
print_detail = True
print_per_screen = True
save_err = False

use_threshold = True
use_single = True
sample_untagged = False
untagged_ratio = 0.1
use_oneclass = False
discard_middle_layer = False
use_nn = True

use_bool = [True, True, True, True, False, False]

OCR_RATIO = 3

word_re = re.compile("([A-Z0-9]?[a-z0-9]+)|[A-Z0-9]+")

n_pca_components = 1024
TFIDF_FEATURES = 1024


def ignore_node(node):
    # OPTION nodes are actually invisible
    if node['class'].lower() == 'option':
        return True
    if node['visible'] == 'hidden':
        return True
    return False


def find_contain_region_ids_node(tree, nodeid):
    ids = []
    node = tree[nodeid]
    any_child_contain = False
    for childid in node['children']:
        (child_ids, child_contain) = find_contain_region_ids_node(tree, childid)
        ids += child_ids
        any_child_contain = any_child_contain or child_contain

    node_contain = node['regs'] != []

    if not node_contain and any_child_contain:
        ids.append(nodeid)

    return (ids, node_contain or any_child_contain)


def find_contain_region_ids(tree):
    return find_contain_region_ids_node(tree, min(tree))[0]


def discard_middle(pts, tree):
    contain_region_ids = find_contain_region_ids(tree)
    for pt in pts:
        if pt['id'] in contain_region_ids:
            pt['discard'] = True
        else:
            pt['discard'] = False


def cannot_be_region(node):
    if node['children'] == []:
        return True
    return False


def gen_ngram(text, regex=word_re):
    ret = ''
    parts = regex.findall(text)
    for i in range(len(parts) - 1):
        ret += ' ' + parts[i] + parts[i + 1]
    return ret


class FeatureCollector(object):
    def __init__(self, tree, imgfile):
        self.tree = tree
        self.collect_texts()
        self.imgfile = imgfile
        self.tesapi = PyTessBaseAPI(lang='eng')
        self.set_tes_image()

    def set_tes_image(self):
        #imgpil = Image.fromarray(numpy.uint8(imgdata * 255))
        imgpil = Image.open(self.imgfile)
        (self.imgwidth, self.imgheight) = (imgpil.width, imgpil.height)
        imgpil = imgpil.convert("RGB").resize(
            (imgpil.width * OCR_RATIO, imgpil.height * OCR_RATIO))
        self.tesapi.SetImage(imgpil)

    def add_ctx_attr(self, ctx, data, attr_re, word_limit=1000):
        if ctx not in self.point:
            self.point[ctx] = ''
        words = attr_re.findall(data)
        if word_limit and len(words) > word_limit:
            return
        for word in words:
            if self.point[ctx]:
                self.point[ctx] += ' '
            self.point[ctx] += '%s' % word.lower()

    def add_ctx(self, ctx, node, attrs, attr_re=anything_re, word_limit=None):
        for attr in attrs:
            self.add_ctx_attr(ctx, node[attr], attr_re, word_limit)

    def collect_texts(self):
        for nodeid in self.tree:
            node = self.tree[nodeid]
            if 'fulltext' not in node:
                self.collect_text(node)

    def collect_text(self, node):
        """ Collect text from node and all its children """
        if 'fulltext' in node:
            return node['fulltext']

        cls = node['class']
        if cls == 'View':
            text = node['desc']
        else:
            text = node['text']

        for child in node['children']:
            text = text.strip() + ' ' + self.collect_text(self.tree[child])

        node['fulltext'] = text
        return text

    def prepare_neighbour(self):
        node = self.tree[self.nodeid]
        self.point['neighbour_ctx'] = ''
        self.point['adj_ctx'] = ''
        neighbour_count = 0
        for other in self.tree:
            if self.tree[other]['parent'] == node['parent'] and other != self.nodeid:
                self.add_ctx_attr('neighbour_ctx',
                                  self.collect_text(self.tree[other]), text_re)
                self.add_ctx('neighbour_ctx', self.tree[other], ['id'], id_re)
                if self.tree[other]['class'] == node['class']:
                    neighbour_count += 1

            # left sibling
            if (self.tree[other]['parent'] == node['parent'] and other != self.nodeid and
                    self.tree[other]['childid'] < node['childid'] and
                    self.tree[other]['childid'] > node['childid'] - 2):
                self.add_ctx_attr('adj_ctx',
                                  self.collect_text(self.tree[other]), text_re)
                self.add_ctx('adj_ctx', self.tree[other], ['id'], id_re)

        self.point['neighbour_count'] = neighbour_count

    def ctx_append(self, ctx, kind, clz, detail):
        ret = ctx
        ret += ' ' + kind + clz
        regex = word_re
        for part in regex.findall(detail):
            ret += ' ' + kind + part
        return ret

    def collect_subtree_info(self, node, root):
        if ignore_node(node):
            return {'ctx': '', 'text': '', 'count': 0}
        ctx = ''
        count = 1

        clz = node['class']

        if clz == 'View':
            text = node['desc'][:30]
        else:
            text = node['text'][:30]
        desc = node['desc'][:30]

        ctx += clz + ' '
        ctx += node['id'] + ' '
        ctx += text + ' '
        ctx += desc + ' '
        ctx += gen_ngram(text) + ' '
        ctx += gen_ngram(desc) + ' '

        if root is not None:
            if node['width'] > 0.6 * config.width:
                ctx = self.ctx_append(ctx, "WIDE", clz, node['id'])

            if node['height'] > 0.6 * config.height:
                ctx = self.ctx_append(ctx, "TALL", clz, node['id'])

            if node['y'] + node['height'] < root['y'] + 0.3 * root['height']:
                ctx = self.ctx_append(ctx, "TOP", clz, node['id'])

            if node['x'] + node['width'] < root['x'] + 0.3 * root['width']:
                ctx = self.ctx_append(ctx, "LEFT", clz, node['id'])

            if node['y'] > root['y'] + 0.7 * root['height']:
                ctx = self.ctx_append(ctx, "BOTTOM", clz, node['id'])

            if node['x'] > root['x'] + 0.7 * root['width']:
                ctx = self.ctx_append(ctx, "RIGHT", clz, node['id'])

        for child in node['children']:
            child_info = self.collect_subtree_info(self.tree[child],
                                                   root if root is not None else node)
            ctx = ctx.strip() + ' ' + child_info['ctx']
            count += child_info['count']
            text = text.strip() + ' ' + child_info['text']

        return {'ctx': ctx, 'text': text, 'count': count}

    def prepare_children(self):
        node = self.tree[self.nodeid]
        #self.add_ctx_attr('node_subtree_text', self.collect_text(node), text_re, 10)
        subtree_info = self.collect_subtree_info(node, None)
        self.point['subtree'] = subtree_info['ctx']
        self.point['node_subtree_text'] = subtree_info['text']
        self.point['node_childs'] = subtree_info['count']

    def prepare_ancestor(self):
        node = self.tree[self.nodeid]
        parent = node['parent']
        self.point['parent_ctx'] = ''
        parent_click = parent_scroll = parent_manychild = False
        parent_depth = 0
        while parent != 0 and parent != -1 and parent_depth < PARENT_DEPTH_LIMIT:
            self.add_ctx('parent_ctx', self.tree[parent], ['class', 'id'], id_re)
            parent_click |= self.tree[parent]['click']
            parent_scroll |= self.tree[parent]['scroll']
            parent_manychild |= len(self.tree[parent]['children']) > 1
            parent = self.tree[parent]['parent']
            parent_depth += 1

        self.point['parent_prop'] = [parent_click, parent_scroll, parent_manychild]

    def prepare_self(self):
        node = self.tree[self.nodeid]
        # AUX info
        self.point['id'] = self.nodeid
        self.point['str'] = util.describe_node(node, None)

        self.add_ctx('node_text', node, ['text'], text_re, 10)
        self.add_ctx('node_ctx', node, ['desc'], text_re)
        self.add_ctx('node_ctx', node, ['id'], id_re)
        self.add_ctx('node_class', node, ['class'], id_re)
        if 'Recycler' in node['class'] or 'ListView' in node['class']:
            self.point['node_class'] += " ListContainer"
        self.point['node_x'] = node['x']
        self.point['node_y'] = node['y']
        self.point['node_w'] = node['width']
        self.point['node_h'] = node['height']

    def prepare_point(self, nodeid, app, scr, caseid, imgdata, treeinfo, path):
        """Convert a node in the tree into a data point for ML"""
        self.nodeid = nodeid
        self.point = {}

        # AUX info
        self.point['app'] = app
        self.point['scr'] = scr
        self.point['case'] = caseid

        self.prepare_self()
        self.prepare_neighbour()
        self.prepare_ancestor()
        self.prepare_global(path, treeinfo)
        self.prepare_img(imgdata)
        self.prepare_ocr()
        self.prepare_children()

        return self.point

    def prepare_global(self, path, treeinfo):
        node = self.tree[self.nodeid]
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
        self.point['node_prop'] = [node['click'], node['scroll'],
                                   len(node['children']) > 1,
                                   has_dupid, is_itemlike, is_listlike]

        self.point['path'] = path

    def prepare_img(self, imgdata):
        node = self.tree[self.nodeid]
        # your widget should be inside the screenshot
        # not always!
        self.min_x = max(node['x'], 0)
        self.min_y = max(node['y'], 0)
        self.max_x = min(node['x'] + node['width'], self.imgwidth)
        self.max_y = min(node['y'] + node['height'], self.imgheight)
        self.empty = self.max_x <= self.min_x or self.max_y <= self.min_y
        self.point['empty'] = self.empty

    def prepare_ocr(self):
        node = self.tree[self.nodeid]
        if config.region_use_ocr and not self.empty:
            if 'ocr' in node:
                ocr_text = node['ocr']
            else:
                self.tesapi.SetRectangle(self.min_x * OCR_RATIO, self.min_y * OCR_RATIO,
                                         (self.max_x - self.min_x) * OCR_RATIO,
                                         (self.max_y - self.min_y) * OCR_RATIO)
                try:
                    ocr_text = self.tesapi.GetUTF8Text()
                except:
                    logger.warning("tessearact fail to recognize")
                    ocr_text = ''
                ocr_text = ocr_text.strip().replace('\n', ' ')
        else:
            ocr_text = 'dummy'
        self.point['node_ocr'] = ocr_text
        #if point['node_text'].strip() == '':
        #    point['node_text'] = ocr_text
        logger.debug("%s VS %s" % (ocr_text, node['text']))

        (missing, found, other) = (node['ocr_missing'], node['ocr_found'],
                                   node['ocr_other'])
        self.point['ocr_missing'] = missing
        self.point['ocr_found'] = found
        self.point['ocr_other'] = other
        self.point['ocr_ratio'] = (1.0 * missing / (missing + other)
                                   if missing + other > 0 else 0.0)
        self.point['ocr_visible'] = node['visible']


def print_point(point, label=None):
    print("===", point['str'], "===")
    print("%s %s %s => %s" % (point['app'], point['case'], point['scr'], label))
    for prop in sorted(point):
        if (prop != 'str' and prop != 'img_hog' and prop != 'img' and
            prop != 'img_flat' and prop != 'img_thr' and prop != 'extra' and
            prop != 'app' and prop != 'case' and prop != 'scr'):
            print("%30s = %s" % (prop, point[prop]))


class ColumnExtractor(BaseEstimator, TransformerMixin):
    def __init__(self, column):
        self.column = column

    def transform(self, X, **transform_params):
        result = []
        for row in X:
            result.append(row[self.column])
        return numpy.asarray(result)

    def fit(self, X, y=None, **fit_params):
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
                result.append([row['node_w'] / config.width,
                               row['node_h'] / config.height,
                               row['node_x'] / config.width,
                               row['node_y'] / config.height,
                               row['node_childs'],
                               row['ocr_missing'],
                               row['ocr_found'],
                               row['ocr_other'],
                               row['ocr_ratio'],
                               ])
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
                    rowret.append(1.0)
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


class Sparse2DenseTransformer(BaseEstimator, TransformerMixin):
    def fit(self, X, Y=None):
        return self

    def transform(self, X):
        return X.todense()


class Dumper(TransformerMixin):
    def __init__(self, label):
        TransformerMixin.__init__(self)
        self.label = label

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
        print(self.label, row.shape)


def has_label(tree):
    for itemid in tree:
        if tree[itemid]['regs']:
            return True
    return False


def prepare_pipeline():
    #clf = svm.SVC(kernel='rbf', decision_function_shape='ovr',
    #              class_weight='balanced', C=1000)
    #clf = svm.LinearSVC(class_weight='balanced', C=0.01)
    #clf = svm.OneClassSVM(nu=0.1, kernel="linear", gamma=0.1)
    #clf = DecisionTreeClassifier(max_depth=100, random_state=0)
    #clf = AdaBoostClassifier()
    if use_nn:
        clf = MLPClassifier(hidden_layer_sizes=(10, 10,), max_iter=1000, verbose=True,
                            early_stopping=False, random_state=0)

    pipeline = Pipeline([
        ('features', FeatureUnion(transformer_list=[
            ('node_cls', Pipeline([
                ('extract', ColumnExtractor('node_class')),
                ('vec', TfidfVectorizer(token_pattern=id_re.pattern, binary=BINARY,
                                        sublinear_tf=True)),
                #('dumper', Dumper('cls')),
                #                ('scale', StandardScaler(with_mean=False))
            ])),
            #('node_text', Pipeline([
            #    ('extract', ColumnExtractor('node_text')),
            #    ('dumper', Dumper('cls')),
            #    ('vec', TfidfVectorizer(binary=binary, sublinear_tf=True)),
            #    ('dumper', Dumper('text')),
            #                    ('scale', StandardScaler(with_mean=False))
            #])),
            ('node_ctx', Pipeline([
                ('extract', ColumnExtractor('node_ctx')),
                ('vec', TfidfVectorizer(binary=BINARY, sublinear_tf=True)),
                #('dumper', Dumper('ctx')),
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
                ('extract', ColumnExtractor('parent_ctx')),
                ('vec', TfidfVectorizer(binary=BINARY, sublinear_tf=True)),
                #                ('scale', StandardScaler(with_mean=False))
            ])),
            #            ('parent_prop', Pipeline([
            #                ('node_prop_extract', ColumnExtractor('parent_prop')),
            #                ('node_prop_vec', BooleanVectorizer())
            #            ])),
            ('nb_ctx', Pipeline([
                ('extract', ColumnExtractor('neighbour_ctx')),
                ('vec', TfidfVectorizer(binary=BINARY, sublinear_tf=True)),
                #                ('scale', StandardScaler(with_mean=False))
            ])),
            ('adj_ctx', Pipeline([
                ('extract', ColumnExtractor('adj_ctx')),
                ('vec', TfidfVectorizer(binary=BINARY, sublinear_tf=True)),
                #                ('scale', StandardScaler(with_mean=False))
            ])),
            #('img_hog', ColumnExtractor('img_hog')),
            ('node_ocr', Pipeline([
                ('extract', ColumnExtractor('node_ocr')),
                ('vec', TfidfVectorizer(binary=BINARY, sublinear_tf=False)),
            ])),
            ('path', Pipeline([
                ('ext', ColumnExtractor('path')),
                ('vec', TfidfVectorizer(binary=BINARY, sublinear_tf=True)),
            ])),
            ('subtree', Pipeline([
                ('ext', ColumnExtractor('subtree')),
                ('vec', TfidfVectorizer(binary=BINARY, sublinear_tf=False)),
                #('dumper', Dumper('subtree')),
            ])),
            ('subtree_text', Pipeline([
                ('extract', ColumnExtractor('node_subtree_text')),
                ('vec', TfidfVectorizer(binary=BINARY, sublinear_tf=False)),
                #('dumper', Dumper('subtree_text')),
                #                ('scale', StandardScaler(with_mean=False))
            ])),
        ], transformer_weights={
            # text
            #'node_text': 0.0,
            # ctx
            'node_cls': 0.0,
            'node_ctx': 1.0,
            # neighbour
            'nb_ctx': 1.0,
            'adj_ctx': 1.0,
            # graphical
            'img_hog': 0.0,
            # ocr
            'node_ocr': 1.0,
            # metadata
            'size': 1.0,
            'prop': 0.0,
            # ancestor
            'p_ctx': 1.0,
            'parent_prop': 1.0,

            'path': 1.0,
            'subtree': 1.0,
            'subtree_text': 1.0,
        }
        )),
        #('todense', Sparse2DenseTransformer()),
        #('final_scale', StandardScaler()),
        #('dumper', Dumper('total')),
        #('pca', TruncatedSVD(n_components=n_pca_components)),
        #('pca', PCA(n_components=n_pca_components)),
        ('svc', clf)
    ])

    pipeline.set_params(
        #features__node_text__vec__ngram_range=(1, 2),
        #features__node_text__vec__max_df=0.8,
        #features__node_text__vec__min_df=2,
        #features__node_text__vec__stop_words=None,
        #features__node_text__vec__max_features=TFIDF_FEATURES,

        features__node_cls__vec__ngram_range=(1, 2),
        features__node_cls__vec__max_df=0.8,
        features__node_cls__vec__min_df=2,
        features__node_cls__vec__stop_words=None,

        features__node_ctx__vec__ngram_range=(1, 2),
        features__node_ctx__vec__max_df=0.8,
        features__node_ctx__vec__min_df=2,
        features__node_ctx__vec__stop_words=None,
        features__node_ctx__vec__max_features=TFIDF_FEATURES,

        features__p_ctx__vec__ngram_range=(1, 2),
        features__p_ctx__vec__max_df=0.8,
        features__p_ctx__vec__min_df=2,
        features__p_ctx__vec__stop_words=None,
        features__p_ctx__vec__max_features=TFIDF_FEATURES,

        features__nb_ctx__vec__ngram_range=(1, 2),
        features__nb_ctx__vec__max_df=0.8,
        features__nb_ctx__vec__min_df=2,
        features__nb_ctx__vec__stop_words=None,
        features__nb_ctx__vec__max_features=TFIDF_FEATURES,

        features__adj_ctx__vec__ngram_range=(1, 2),
        features__adj_ctx__vec__max_df=0.8,
        features__adj_ctx__vec__min_df=2,
        features__adj_ctx__vec__stop_words=None,
        features__adj_ctx__vec__max_features=TFIDF_FEATURES,

        features__node_ocr__vec__ngram_range=(1, 2),
        features__node_ocr__vec__max_df=0.8,
        features__node_ocr__vec__min_df=2,
        features__node_ocr__vec__stop_words=None,
        features__node_ocr__vec__max_features=TFIDF_FEATURES,

        features__path__vec__ngram_range=(1, 1),
        features__path__vec__max_df=0.5,
        features__path__vec__min_df=2,
        features__path__vec__stop_words='english',
        features__path__vec__max_features=TFIDF_FEATURES,

        features__subtree__vec__ngram_range=(1, 1),
        features__subtree__vec__max_df=0.5,
        features__subtree__vec__min_df=2,
        features__subtree__vec__stop_words='english',
        features__subtree__vec__max_features=TFIDF_FEATURES,

        features__subtree_text__vec__ngram_range=(1, 2),
        features__subtree_text__vec__max_df=0.5,
        features__subtree_text__vec__min_df=2,
        features__subtree_text__vec__stop_words='english',
        features__subtree_text__vec__max_features=TFIDF_FEATURES,
    )

    return pipeline


def prepare_img_pipeline():
    img_clf = svm.LinearSVC()

    img_pipeline = Pipeline([
        ('ext', ColumnExtractor('img_flat')),
        ('cnn', img_clf)
    ])

    return img_pipeline


def load_cached_point(filebase):
    points = []
    labels = []
    apps = []
    scrs = []

    featurefile = filebase + '.rpts'
    if os.path.exists(featurefile):
        featuref = open(featurefile, 'rb')
        unpickler = pickle.Unpickler(featuref)
        try:
            count = unpickler.load()
        except:
            logger.error("fail to unpickle from %s, removing", featurefile)
            os.remove(featurefile)
            return None

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

    return None


def cache_points(filebase, points, labels, apps, scrs):
    featurefile = filebase + '.rpts'
    with open(featurefile, 'wb') as featuref:
        pickler = pickle.Pickler(featuref)
        pickler.dump(len(points))
        for i in range(len(points)):
            pickler.dump(points[i])
            pickler.dump(labels[i])
            pickler.dump(apps[i])
            pickler.dump(scrs[i])


def load_point(no_appname, nopt, filename):
    points = []
    labels = []
    apps = []
    scrs = []

    filebase = os.path.splitext(filename)[0]
    (appname, caseid, scrname) = re.search('([a-z0-9]+)_?([0-9]+)?_([a-z0-9]+)',
                                           filename).groups()

    if appname is not None and appname == no_appname:
        return (points, labels, apps, scrs)

    if scrname in tags.tag['ignored_screens']:
        return (points, labels, apps, scrs)

    if not nopt:
        cached = load_cached_point(filebase)
        if cached is not None:
            if discard_middle_layer:
                tree = analyze.load_tree(filename)
                discard_middle(cached[0], tree)
            return cached

    tree = analyze.load_tree(filename)
    hidden.find_hidden_ocr(tree)
    hidden.mark_children_hidden_ocr(tree)

    if not has_label(tree):
        logger.info("%s: no label", filename)
        return (points, labels, apps, scrs)

    logger.debug("analyzing %s", filename)

    pngfile = filebase + '.png'
    imgdata = skimage.io.imread(pngfile, as_grey=True)
    imgdata = skimage.transform.resize(imgdata, (config.height, config.width),
                                       mode='constant')

    treeinfo = analyze.collect_treeinfo(tree)

    path = get_path(filebase)

    collector = FeatureCollector(tree, pngfile)
    for itemid in sorted(tree):
        if cannot_be_region(tree[itemid]):
            continue

        try:
            point = collector.prepare_point(itemid, appname, scrname, caseid,
                                            imgdata, treeinfo, path)
        except ValueError:
            logger.exception("ERROR at %s" % filename)
            return (points, labels, apps, scrs)

        if point['empty']:
            continue

        pt_tag = 'NONE'
        if len(tree[itemid]['regs']) > 0:
            firsttag = tree[itemid]['regs'][0]
            pt_tag = firsttag

        points.append(point)
        labels.append(pt_tag)
        apps.append(appname)
        scrs.append(scrname)

    cache_points(filebase, points, labels, apps, scrs)

    if discard_middle_layer:
        tree = analyze.load_tree(filename)
        discard_middle(points, tree)

    return (points, labels, apps, scrs)


def load_points(files, show_progress=False, no_appname=None, extra=[], parallel=True,
                nopt=False):
    points = []
    labels = []
    apps = []
    scrs = []
    rets = util.parallel_work(functools.partial(load_point, no_appname, nopt), files,
                              parallel, show_progress=show_progress)
    for (xpoints, xlabels, xapps, xscrs) in rets:
        for i in range(len(xpoints)):
            xpoints[i]['extra'] = False
            xscrs[i] = 'region'
            if xlabels[i] != 'NONE' and not tags.valid(xscrs[i], xlabels[i]):
                xlabels[i] = 'NONE'

            points.append(xpoints[i])
            labels.append(xlabels[i])
            apps.append(xapps[i])
            scrs.append(xscrs[i])

    rets = util.parallel_work(functools.partial(load_point, no_appname, nopt), extra,
                              parallel, show_progress=show_progress)
    for (xpoints, xlabels, xapps, xscrs) in rets:
        for i in range(len(xpoints)):
            xpoints[i]['extra'] = True
            xscrs[i] = 'region'
            if xlabels[i] != 'NONE' and not tags.valid(xscrs[i], xlabels[i]):
                xlabels[i] = 'NONE'

            if xlabels[i] != 'NONE':
                points.append(xpoints[i])
                labels.append(xlabels[i])
                apps.append(xapps[i])
                scrs.append(xscrs[i])

    return (points, labels, apps, scrs)


class RegionClassifier(object):
    def __init__(self, path=None, nopt=False):
        if path is not None:
            self.load(path)
        else:
            self.pipelines = {}
        self.nopt = nopt

    def learn(self, datadir, appname, extrapath, parallel=True):
        files = util.collect_files(datadir)
        extrafiles = util.collect_files(extrapath)
        (points, labels, _, _) = load_points(files, no_appname=appname, extra=extrafiles,
                                             parallel=parallel, nopt=self.nopt)

        (points, labels) = self.filter_pts(points, labels)

        self.classes = list(set(labels))
        for lbl in self.classes:
            self.pipelines[lbl] = prepare_pipeline()

            pts_with_lbl = []
            my_labels = []
            for i in range(len(labels)):
                if labels[i] == lbl:
                    pts_with_lbl.append(points[i])
                    my_labels.append(1)
                elif not use_oneclass:
                    pts_with_lbl.append(points[i])
                    my_labels.append(-1)

            self.pipelines[lbl].fit(pts_with_lbl, my_labels)

    @perfmon.op("region", "classify")
    def classify(self, tree, imgfile, path, points=None):
        imgdata = read_imgdata(imgfile)
        results = []
        treeinfo = analyze.collect_treeinfo(tree)
        best_result = {}

        if points is None:
            points = []
            collector = FeatureCollector(tree, imgfile)
            for nodeid in tree:
                if cannot_be_region(tree[nodeid]):
                    continue
                point = collector.prepare_point(nodeid, '', '', 0, imgdata, treeinfo,
                                                path)
                if point['empty']:
                    continue

                points.append(point)

        for point in points:
            nodeid = point['id']
            if tree[nodeid]['visible'] == 'hidden':
                continue
            scores = []
            try:
                for lbl in self.classes:
                    if use_nn:
                        scores.append(self.pipelines[lbl].predict_proba([point])[0])
                    else:
                        scores.append(self.pipelines[lbl].decision_function([point])[0])
            except:
                logger.error("error at item %s", tree[nodeid])
                logger.error("  pt: %s", point)
                raise

            best_score = config.REGION_SCORE_BOUND
            result = 'NONE'

            for i in range(len(self.classes)):
                if self.classes[i] == 'NONE':
                    continue
                if best_score is None or scores[i] > best_score:
                    best_score = scores[i]
                    result = self.classes[i]

            if result != 'NONE':
                if tags.single(result, "region"):
                    if result not in best_result or best_result[result][0] < best_score:
                        best_result[result] = (best_score, nodeid)
                else:
                    results.append((nodeid, result, best_score))

        for result in best_result:
            results.append((best_result[result][1], result, best_result[result][0]))
        return results

    def save(self, path):
        joblib.dump(self.pipelines, path)

    def load(self, path):
        self.pipelines = joblib.load(path)

    def filter_pts(self, pts, lbls):
        newpts = []
        newlbls = []
        for i in range(len(pts)):
            if pts[i]['ocr_visible'] == 'hidden':
                continue
            if lbls[i] == 'NONE':
                if sample_untagged and random.random() > untagged_ratio:
                    continue
            if discard_middle_layer and pts[i]['discard']:
                continue
            newpts.append(pts[i])
            newlbls.append(lbls[i])

        return (newpts, newlbls)


def learn(datadir, appname, extrapath, parallel=True, nopt=False):
    clas = RegionClassifier(nopt=nopt)
    clas.learn(datadir, appname, extrapath, parallel)
    return clas


def modelfile(modelpath, appname):
    if appname is None:
        return os.path.join(modelpath, 'region')
    else:
        return os.path.join(modelpath, 'region_%s' % appname)


def load(modelpath, appname):
    path = modelfile(modelpath, appname)
    if os.path.exists(path):
        clas = RegionClassifier(path)
        return clas
    else:
        return None


def getmodel(modelpath, datadir, appname, extrapath, extrascr):
    clas = load(modelpath, appname)
    if clas is None:
        clas = learn(datadir, appname, extrapath, extrascr)
        clas.save(modelfile(modelpath, appname))
    return clas


def collect_tags(tree):
    tags = []
    for nodeid in tree:
        node = tree[nodeid]
        if len(node['regs']) > 0:
            tags += node['regs']
    return tags


def get_path(filebase):
    if os.path.exists(filebase + '.txt'):
        content = open(filebase + '.txt').read()
    elif os.path.exists(filebase + '.url'):
        content = util.url_to_actname(open(filebase + '.url').read())

    if '/' in content:
        content = content.split("/", 1)[1]
    pat = re.compile("[A-Z][a-z]+")
    return " ".join(pat.findall(content))


def read_imgdata(imgfile):
    imgdata = skimage.io.imread(imgfile, as_grey=True)
    imgwidth = imgdata.shape[1]
    # we assume scaling based on width
    ratio = 1.0 * imgwidth / config.width
    newheight = int(imgdata.shape[0] / ratio)

    imgdata = skimage.transform.resize(imgdata, (newheight, config.width),
                                       mode='constant')
    return imgdata


def load_info(only_app, only_scrs, filename):
    (appname, caseid, scrname) = re.search('([a-z0-9]+)_?([0-9]+)?_([a-z0-9]+)',
                                           filename).groups()
    if only_app is not None and appname != only_app:
        return None
    if only_scrs is not None and scrname not in only_scrs:
        return None

    filebase = os.path.splitext(filename)[0]
    tree = analyze.load_tree(filename)
    hidden.find_hidden_ocr(tree)
    hidden.mark_children_hidden_ocr(tree)

    pngfile = filebase + '.png'

    path = get_path(filebase)

    return {'tree': tree, 'img': pngfile, 'regs': collect_tags(tree), 'app': appname,
            'file': filename, 'path': path, 'scr': scrname}


def evaluate_app(parallel, guispath, extrapath, my_points):
    good_cnt = total_cnt = inside_cnt = 0
    app = my_points[0]['app']
    logger.info("app %s, learning...", app)
    start_time = time.time()
    clas = learn(guispath, app, extrapath, parallel=parallel)
    logger.info("%s: Learned in %.3fs, testing...", app, time.time() - start_time)
    correct = []
    missing = []
    extra = []
    correct_scr = {}
    total_scr = {}
    for point in my_points:
        cached_pts = load_cached_point(os.path.splitext(point['file'])[0])
        rets = clas.classify(point['tree'], point['img'], point['path'],
                             cached_pts[0] if cached_pts else None)
        regs = list(filter(lambda tag: tags.valid('region', tag), point['regs']))
        print(os.path.basename(point['file']), 'Tags:', regs, 'Rets:', rets)
        ret_region = set()
        for ret in rets:
            ret_region.add(ret[1])

        if set(regs) == ret_region:
            good_cnt += 1
            correct_scr[point['scr']] = correct_scr.get(point['scr'], 0) + 1

        found = 0
        for tag in regs:
            if tag in ret_region:
                found += 1
                correct.append(tag)
            else:
                missing.append(tag)

        for tag in ret_region:
            if tag not in regs:
                extra.append(tag)

        if found == len(regs):
            inside_cnt += 1

        total_cnt += 1
        total_scr[point['scr']] = total_scr.get(point['scr'], 0) + 1

    avg_scr_ratio = 0.0
    for scr in total_scr:
        scr_ratio = 1.0 * correct_scr.get(scr, 0) / total_scr[scr]
        avg_scr_ratio += scr_ratio

    avg_scr_ratio /= len(total_scr)

    return {'good': good_cnt, 'total': total_cnt, 'inside': inside_cnt,
            'correct': correct, 'missing': missing, 'extra': extra, 'app': app,
            'scr_avg': avg_scr_ratio}


def count_items(items):
    ret = {}
    for item in items:
        ret[item] = ret.get(item, 0) + 1
    return ret


def print_hash(hash):
    ret = ''
    for key in sorted(hash):
        if ret != '':
            ret += ' '
        ret += '%s: %s' % (key, hash[key])
    return ret


def main():
    parser = argparse.ArgumentParser(description="Classifier")
    parser.add_argument('--guispath', help='data path', default="../guis/")
    parser.add_argument('--tagspath', help='tags path', default="../etc/tags.txt")
    parser.add_argument('--extrapath', help='extra data path', default="../guis-extra/")
    parser.add_argument('--app', help='only for app')
    parser.add_argument('--scrs', help='only for screens')
    parser.add_argument('--debug', help='debug',
                        default=False, action='store_const', const=True)
    parser.add_argument('--nopt', help='no pt cache',
                        default=False, action='store_const', const=True)
    parser.add_argument('--printpt', help='print points',
                        default=False, action='store_const', const=True)
    parser.add_argument('--onlyfor', help='only print for')
    parser.add_argument('--analyze', help='show pt for one file', default=None)
    parser.add_argument('--thres', help='threshold')
    args = parser.parse_args()
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    tags.load(args.tagspath)

    if args.analyze:
        (pts, lbls, _, _) = load_points([args.analyze], nopt=True)
        for i in range(len(pts)):
            print_point(pts[i], lbls[i])
        return

    if args.thres is not None:
        config.REGION_SCORE_BOUND = float(args.thres)

    start_time = time.time()
    points = {}
    point_count = 0
    files = util.collect_files(args.guispath)

    # load points first so we have cache later
    logger.info("Caching points...")
    (pts, lbls, _, _) = load_points(files, nopt=args.nopt, show_progress=True)
    if args.printpt:
        if args.onlyfor:
            onlyfor = args.onlyfor.split(',')
        else:
            onlyfor = None
        for i in range(len(pts)):
            if onlyfor is None or lbls[i] in onlyfor:
                if args.app is None or pts[i]['app'] == args.app:
                    print_point(pts[i], lbls[i])
        return

    logger.info("cached %d points.", len(pts))

    logger.info("Load points...")
    if args.scrs is None:
        scrs = None
    else:
        scrs = args.scrs.split(',')
    rets = util.parallel_work(functools.partial(load_info, args.app, scrs), files,
                              True, show_progress=True)
    for ret in rets:
        if ret is not None:
            points[ret['app']] = points.get(ret['app'], []) + [ret]
            point_count += 1
    logger.info("Point count: %d, used %.3fs", point_count, time.time() - start_time)

    apps = list(set(points))

    logger.info("Testing, app count %d", len(apps))
    if args.app is None and config.parallel:
        pool = multiprocessing.Pool(processes=config.threads)
        rets = pool.map(functools.partial(evaluate_app, False, args.guispath,
                                          args.extrapath), points.values())
        pool.close()
    else:
        rets = map(functools.partial(evaluate_app, True, args.guispath,
                                     args.extrapath), points.values())

    good_cnt = total_cnt = inside_cnt = 0
    correct = []
    missing = []
    extra = []
    good_ratio = 0.0
    for ret in rets:
        good_cnt += ret['good']
        total_cnt += ret['total']
        inside_cnt += ret['inside']
        correct += ret['correct']
        missing += ret['missing']
        extra += ret['extra']
        logger.info("app %s: %d/%d avg(scr): %.2f", ret['app'], ret['good'], ret['total'],
                    ret['scr_avg'])
        good_ratio += ret['scr_avg']

    good_ratio /= len(apps)

    logger.info("Good/Total: %d/%d %.2f", good_cnt, total_cnt, 1.0 * good_cnt / total_cnt)
    logger.info("Inside/Total: %d/%d %.2f", inside_cnt, total_cnt,
                1.0 * inside_cnt / total_cnt)
    logger.info("Correct: %s", print_hash(count_items(correct)))
    logger.info("Missing: %s", print_hash(count_items(missing)))
    logger.info("Extra: %s", print_hash(count_items(extra)))
    logger.info("Good ratio(app avg): %.3f", good_ratio)


if __name__ == '__main__':
    main()
