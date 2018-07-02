#!/usr/bin/env python3
import os
import subprocess
import glob

import dump
import config
import appdb

appdb.collect_apps("../apks/")

app_name = ''
scr_name = ''
viewproc = None # type: subprocess.Popen
for i in range(1000):
    if (os.path.exists("page%d.png" % i)):
        old_name = "page%d" % i

        pngfile = "%s.png" % old_name
        print("handle page %s" % old_name)
        txtfile = "page%d.txt" % i
        if os.path.exists(txtfile):
            actname = open(txtfile).read()
            print("act:", actname)
            if appdb.guess_app(actname) is not None:
                app_name = appdb.guess_app(actname)
                print("app guessed as %s" % app_name)

        urlfile = "page%d.url" % i
        if os.path.exists(urlfile):
            url = open(urlfile).read()
            print("url:", url)
            if appdb.guess_site(url) is not None:
                app_name = appdb.guess_site(url)
                print("site guessed as %s" % app_name)

        if viewproc is not None:
            try:
                viewproc.kill()
            except:
                pass
        viewproc = subprocess.Popen([config.picviewer_path, pngfile])

        skip = False
        delete = False
        while True:
            filename = input("curr: [%s %s]> " % (app_name, scr_name))
            if filename == '':
                # do nothing
                pass
            elif filename == 's':
                # skip
                skip = True
                break
            elif filename == 'd':
                delete = True
                break
            elif ' ' in filename:
                (parta, partb) = filename.split(' ')
                if parta == 'app':
                    app_name = partb
                else:
                    app_name = parta
                    scr_name = partb
            else:
                scr_name = filename

            if app_name == '' or scr_name == '':
                print("incomplete info")
            else:
                break
        if skip:
            continue
        if delete:
            for oldfile in glob.glob("%s.*" % old_name):
                os.remove(oldfile)
            continue

        case_id = dump.detect_case_count(app_name, scr_name)

        if viewproc is not None:
            try:
                viewproc.kill()
            except:
                pass
        #real_xmlname = "%s_%d_%s.xml" % (app_name, case_id, scr_name)

        new_name = "%s_%d_%s" % (app_name, case_id, scr_name)
        print("rename %s -> %s" % (old_name, new_name))
        for oldfile in glob.glob("%s.*" % old_name):
            os.rename(oldfile, oldfile.replace(old_name, new_name))

        #subprocess.call("python3 ../src/observe.py %s" % real_xmlname, shell=True)
