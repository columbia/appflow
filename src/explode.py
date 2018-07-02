#!/usr/bin/env python3
import sys
import os
import skimage.io
import skimage.transform
import skimage.filters
import skimage.util
import skimage

import analyze
import util
import config

def explode(filename, path):
    rets = analyze.analyze([filename])[0]
    util.print_tree(rets)
    pngfile = filename.replace('.xml', '.png')
    imgdata = skimage.io.imread(pngfile, as_grey=True)

    imgdata = skimage.transform.resize(imgdata, (config.height, config.width))

    for itemid in sorted(rets):
        node = rets[itemid]
        itemimg = imgdata[node['y']: node['y'] + node['height'],
                          node['x']: node['x'] + node['width']]
#        itemimg = skimage.transform.resize(itemimg, (32, 32))
        try:
            thres = skimage.filters.threshold_otsu(itemimg)
        except:
            thres = 0.5
#        print(itemimg)
        itemimg = itemimg >= thres
        itemimg = skimage.img_as_float(itemimg)
        print(itemimg.mean())
        if itemimg.mean() < 0.2:
            itemimg = 1.0 - itemimg
#        print(td)
#        if node['click']:
        skimage.io.imsave(os.path.join(path, "part%d.png" % itemid), itemimg)

if __name__ == "__main__":
    if len(sys.argv) > 2:
        path = sys.argv[2]
    else:
        path = "."
    explode(sys.argv[1], path)
