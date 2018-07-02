import sys
import os
from PIL import Image

#import analyze
import webdriver

for filename in sys.argv[1:]:
    #(items, _, _) = analyze.load_case(filename)
    filebase = os.path.splitext(filename)[0]
    loaded = webdriver.load(filebase)
    items = loaded['items']

    imgfile = os.path.splitext(filename)[0] + '.png'
    imgpil = Image.open(imgfile)
    (orig_width, orig_height) = (imgpil.width, imgpil.height)

    if items[0]['width'] == orig_width == 600:
        continue
    ratio = 1.0 * orig_width / items[0]['width']
    if items[0]['x'] != 0 or items[0]['y'] != 0:
        print(filename, items[0]['x'], items[0]['y'])
    if abs(ratio - 1.0) > 0.01 and abs(ratio - 1.5) > 0.01:
        print(filename, items[0]['width'], orig_width, '%.3f' % (ratio),
              '   ', items[0]['height'], orig_height)
