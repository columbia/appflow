import pickle
import glob

def missing_pts(filename):
    f = open(filename, 'rb')
    unpickler = pickle.Unpickler(f)
    cnt = unpickler.load()
    try:
        for i in range(cnt):
            unpickler.load()
            unpickler.load()
            unpickler.load()
            unpickler.load()
    except:
        return True
    return False

for filename in glob.glob("../guis/*.pts"):
    if missing_pts(filename):
        print(filename)
