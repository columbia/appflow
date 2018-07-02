#!/usr/bin/env python3

import glob
import os

import sense

def get_id(filename):
    return int(os.path.basename(filename).split('_')[1])

def get_app(filename):
    return (os.path.basename(filename).split('_')[0])

def get_scr(filename):
    return (os.path.basename(filename).split('.')[0].split('_')[-1])

def remove_case(xmlname):
    print("remove %s" % xmlname)
    os.remove(xmlname)
    os.remove(xmlname.replace('.png', '.xml'))
    os.remove(xmlname.replace('.png', '.txt'))

for file1 in sorted(glob.glob("*.png")):
    print("checking %s" % file1)
    for file2 in glob.glob("*.png"):
        if file1 != file2:
            if get_app(file1) != get_app(file2):
                continue
            if get_scr(file1) != get_scr(file2):
                continue
            if sense.same_snapshot(file1, file2, False):
                id1 = get_id(file1)
                id2 = get_id(file2)
                if id1 > id2:
                    remove_case(file2)
                else:
                    remove_case(file1)
                    break



