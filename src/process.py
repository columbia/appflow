import os
import glob
import subprocess
import xml.etree.ElementTree as ET

DATADIR = "../guis"

def signin(root):
    scores = [0, 0, 0]
    for element in root.findall(".//*"):
        for key in element.attrib:
            value = element.attrib[key].lower()
            if "username" in value or "email" in value:
                scores[0] = 0.3
            if "password" in value or "passwd" in value:
                scores[1] = 0.3
            if "sign in" in value or "login" in value or "log in" in value:
                scores[2] = 0.4
    return sum(scores)

def cart(root):
    scores = [0]
    for element in root.findall(".//*"):
        for key in element.attrib:
            value = element.attrib[key].lower()
            if "checkout" in value or "place order" in value:
                scores[0] = 1
    return sum(scores)

def detail(root):
    scores = [0, 0, 0]
    for element in root.findall(".//*"):
        for key in element.attrib:
            if key != "package":
                value = element.attrib[key].lower()
                if "add to cart" in value or "buy" in value:
                    scores[0] = 0.4
                if "image" in value and key != "class":
                    scores[1] = 0.3
                if "title" in value or "name" in value:
                    scores[2] = 0.3
    return sum(scores)

for filename in glob.glob(os.path.join(DATADIR, "*.xml")):
    formatted = subprocess.check_output("cat %s | xmllint --format -" % filename, shell=True)
    root = ET.fromstring(formatted)
    score = cart(root)
    if score > 0.5:
        print("%s %0.1f" % (filename, score))

