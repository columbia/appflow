#!/usr/bin/env python3

import sys
import numpy
from skimage.feature import hog
from skimage.io import imread
from skimage.transform import resize

pngfile = sys.argv[1]

#s = Image.open(pngfile)
#s = s.convert('1')
s = imread(pngfile, as_grey=True)
print(s.shape)
o = s[1500:1501, 100:200]
#o = resize(s, (100, 100))
print(o)
#height = len(s)
#width = len(s[0])
#out = numpy.ndarray((width, height))
#print(len(s))

print(len(hog(o, orientations=8, pixels_per_cell=(16, 16), cells_per_block=(1, 1))))
