from core4build import find_lib
import json
import os
import sys


def build_info(project):
    pkg_info = find_lib(project)
    if pkg_info and os.path.exists(pkg_info):
        prev = json.load(open(pkg_info, "r"))
    else:
        prev = {"core4": {}, "project": {}}
    return prev

if __name__ == '__main__':
    print(build_info(sys.argv[1]))