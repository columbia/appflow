#!/usr/bin/env python3

import tags
import value
import appdb
import miner

import argparse
import logging
import os


def erase(feature_name, test_name, tlibpath, app, mempath):
    mine = miner.Miner(None, None, None, tlibpath, True, app, None, None, None,
                       None, mempath, False)
    mine.erase_memory(feature_name, test_name)
    mine.save_memory()


def main():
    parser = argparse.ArgumentParser(description="Miner")
    parser.add_argument('--tlibpath', help="Test library path", default="../tlib/")
    parser.add_argument('--apkspath', help="Apps path", default="../apks/")
    parser.add_argument('--parampath', help="Param file path", default="../etc/")
    parser.add_argument('app', help="App name")
    parser.add_argument('--mempath', help="memory path", default="../memory/")
    parser.add_argument('--erase', help="erase memory of tests")
    parser.add_argument('--query', help="query screen")
    parser.add_argument('--reset', help="reset route")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    tags.load(os.path.join(args.parampath, "tags.txt"))
    value.init_params(args.parampath, args.app)
    appdb.collect_apps(args.apkspath)
    #appdb.load_urls(os.path.join(args.parampath, "urls.txt"))
    mine = miner.Miner(None, None, None, args.tlibpath, True, args.app, None, None, None,
                       None, args.mempath, False)

    if args.erase is not None:
        if os.path.exists(args.erase):
            keys = list(filter(lambda x: x, open(args.erase).read().strip().split('\n')))
        else:
            keys = args.erase.split('#')

        if len(keys) == 0:
            print("no case to erase!")
            return

        print("%d cases to erase" % len(keys))
        for key in keys:
            feature_name, test_name = key.split(':')
            mine.erase_memory(feature_name, test_name)

        #mine.print_stat(simple=True)
        mine.save_memory()

        print("%d cases erased" % len(keys))
        return

    if args.reset is not None:
        route_no = int(args.reset)
        mine.slib.reset_route(route_no)
        mine.save_memory()
        return

    if args.query is not None:
        attrs = {}
        if ',' in args.query:
            screen = args.query.split(',')[0]
            for entry in args.query.split(',')[1:]:
                if '=' in entry:
                    key, val = entry.split('=', 1)
                    attrs[key] = val
                else:
                    if entry[0] == '-':
                        attrs[entry[1:]] = 'false'
                    else:
                        attrs[entry] = 'true'
        else:
            screen = args.query
        if screen != '.':
            attrs['screen'] = screen
        mine.slib.query_screen(attrs)
        return

    mine.print_stat(simple=True)


if __name__ == "__main__":
    main()
