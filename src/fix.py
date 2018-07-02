#!/usr/bin/env python3

import glob
import cairo
import shutil

x = 400
w = 372

for filename in glob.glob("../guis/*.png"):
    s = cairo.ImageSurface.create_from_png(filename)

    if s.get_width() == 1080 and s.get_height() == 660:
        print("fixing", filename)
        s2 = cairo.ImageSurface(cairo.FORMAT_RGB24, 1080, 1920)
        ctx = cairo.Context(s2)
        #ctx.rectangle(x, 0, w, 660)
        #ctx.clip()
        ctx.scale(2.91, 2.91)
        ctx.translate(-x, 0)
        ctx.set_source_surface(s)
        ctx.paint()

        s2.write_to_png("tmp.png")

        shutil.copy("tmp.png", filename)
