from PIL import Image
from tesserocr import PyTessBaseAPI, RIL
import skimage.io
import skimage.filters
import numpy as np
import sys
import re

alpha_re = re.compile('[a-zA-z]+')
api = PyTessBaseAPI()

for filename in sys.argv[1:]:
    skimg = skimage.io.imread(filename, as_grey=True)
    #thres = 0.8
    #thres = skimage.filters.threshold_triangle(skimg)
    #print(thres)
    #skimg = skimg >= thres
    #skimg = skimage.img_as_float(skimg)

    #skimage.io.imsave('page0x.png', skimg)

    image = Image.fromarray(np.uint8(skimg*255))
    #image = Image.
    #image.save('page0y.png')
    #image = Image.open('page0.png')
    title = ''
    max_h = 0
    min_y = 10000
    api.SetImage(image)
    #api.SetImageFile(filename)
    boxes = api.GetComponentImages(RIL.TEXTLINE, True)
    #print('Found {} textline image components.'.format(len(boxes)))
    for i, (im, box, _, _) in enumerate(boxes):
        # im is a PIL image object
        # box is a dict with x, y, w and h keys
        api.SetRectangle(box['x'], box['y'], box['w'], box['h'])
        ocrResult = api.GetUTF8Text().replace('\n', ' ').strip()
        conf = api.MeanTextConf()
        print ("Box[{0}]: x={x}, y={y}, w={w}, h={h}, "
               "confidence: {1}, text: {2}".format(i, conf, ocrResult, **box))

        text = ' '.join(alpha_re.findall(ocrResult.strip()))
        if len(text) < 5:
            continue

        if box['y'] <= 50:
            continue

        if box['y'] < min_y:
            min_y = box['y']
            title = text
            break

    print("%s Guessed title: %s" % (filename, title))
