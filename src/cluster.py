#!/usr/bin/env python3

import sklearn
import elements
import sklearn.cluster

import logging
import sys
import progressbar

logger = logging.getLogger("cluster")

DATADIR = "../guis"

def cluster(files):
    print("Loading points")
    (points, labels, _, scrs) = elements.load_points(files)

    pipelines = {}
    for scr in sorted(set(scrs)):
        print("Working on screen %s" % scr)
        scr_points = []
        scr_labels = []
        clf = sklearn.cluster.KMeans(n_clusters=20, random_state=0, verbose=1)
        pipeline = elements.prepare_pipeline(clf)[0]

        for i in range(len(points)):
            if scrs[i] == scr:
                scr_points.append(points[i])
                scr_labels.append(labels[i])

        pipeline.fit(scr_points, scr_labels)
        pipelines[scr] = pipeline

        center_labels = {}
        progress = progressbar.ProgressBar()
        for i in progress(range(len(scr_points))):
            center = pipeline.predict([scr_points[i]])[0]
            center_labels[center] = center_labels.get(center, []) + [scr_labels[i]]

        for center in center_labels:
            print("center: %r" % center, end="")
            for label in sorted(set(center_labels[center])):
                print(" %s: %d" % (label, center_labels[center].count(label)), end="")
            print()


if __name__ == '__main__':
    if sys.argv[1:]:
        files = sys.argv[1:]
    else:
        files = elements.collect_files(DATADIR)

    cluster(files)

