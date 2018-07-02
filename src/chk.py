#!/usr/bin/env python3

import glob
import re
import os

empty_re = re.compile("WebView[^/>]+/>")
for filename in glob.glob("../guis/*.xml"):
    with open(filename) as f:
        if empty_re.search(f.read()):
            print("Empty WebView in %s !!" % filename)
            os.rename(filename, filename + ".err")
    imgname = filename.replace('xml', 'png')
    if not os.path.exists(imgname):
        print("missing %s" % imgname)
    actname = filename.replace('xml', 'txt')
    if not os.path.exists(actname):
        print("missing %s" % actname)
#        if actname.count('_') == 1:
#            for i in range(5):
#                ret = os.system("cp %s %s" % (actname.replace("_", "_%d_" % i), actname))
#               if ret == 0:
#                    break;
