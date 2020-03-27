# from .main import setup

from pip import __version__ as pip_version

try:
    from pip._internal.cli.main import main as _pip_main
except:
    from pip import main as _pip_main

try:
    from wheel import __version__ as wheel_version
except:
    wheel_version = "0.0.0"

try:
    from core4 import __version__ as core4_version
except:
    core4_version = "0.0.0"

import sys
import shutil
from subprocess import Popen, check_output
import os
from setuptools import setup as orig_setup
from setuptools.command.build_py import build_py
from setuptools.command.develop import develop
import json
import tempfile
import re
import datetime

PIP_REQUIRED = (19, 0, 0)
WHEEL_REQUIRED = (0, 34, 0)
CORE4_SOURCE = "https://github.com/plan-net/core4.git@develop.auth"

CWD = os.path.abspath(os.curdir)


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_help():
    print("""
usage: python setup.py

Global options:
  --verbose (-v)      run verbosely
  --quiet (-q)        run quietly
  --help (-h)         show detailed help message
  
Install options:
  --test (-t)         don't actually do anything
  --nofe (-n)         skip webapps build and install
  --edit (-e)         install in editable mode (develop mode)
""")


environ = os.environ.copy()

option = {}
argument = [sys.argv[0]]
VERBOSE = 0
EDIT = False
TEST = False
environ["CORE4_FE"] = "1"
for elem in sys.argv[1:]:
    swallow = False
    if elem.lower() == "--help" or elem.lower() == "-h":
        print_help()
    if elem.lower() == "--verbose" or elem.lower() == "-v":
        VERBOSE = 1
        swallow = True
    elif elem.lower() == "--quiet" or elem.lower() == "-q":
        VERBOSE = -1
        swallow = True
    if elem.lower() == "--nofe" or elem.lower() == "-n":
        environ["CORE4_FE"] = "0"
        swallow = True
    if elem.lower() == "--edit" or elem.lower() == "-e":
        EDIT = True
        swallow = True
    if elem.lower() == "--test" or elem.lower() == "-t":
        TEST = True
        swallow = True
    if not swallow:
        argument.append(elem)
sys.argv = argument


def parse_version(version):
    return tuple([int(i) for i in version.split(".")])


def output(*args, **kwargs):
    if len(args) > 1:
        p = args[1:]
    else:
        p = []
    sys.stderr.write(bcolors.OKGREEN + "*** " + args[0].format(
        *p, **kwargs) + "\n" + bcolors.ENDC)
    sys.stderr.flush()


def pip_main(*args):
    argument = list(args)
    output("install {}", argument[-1])
    if VERBOSE == 1:
        argument.insert(1, "--verbose")
    elif VERBOSE == -1:
        argument.insert(1, "--quiet")
    output("running {}", " ".join(argument))
    _pip_main(argument)


def upgrade_pip():
    if parse_version(pip_version) < PIP_REQUIRED:
        pip_main("install", "--upgrade", "pip")


def upgrade_wheel():
    if parse_version(wheel_version) < WHEEL_REQUIRED:
        pip_main("install", "--upgrade", "wheel")


def git_clone(url, target):
    Popen([shutil.which("git"), "clone", url, target]).wait()


def git_checkout(path, branch="master"):
    Popen([shutil.which("git"), "-C", path, "checkout", branch]).wait()


def parse_git_url(url):
    parts = url.split("@")
    if len(parts) > 1:
        return "@".join(parts[:-1]), parts[-1]
    return url, "master"


def get_git_commit(url):
    (url, branch) = parse_git_url(url)
    out = check_output(
        [shutil.which("git"), "ls-remote", url, "refs/heads/" + branch],
        universal_newlines=True)
    return out.strip().split()[0]


def upgrade_framework(builddir, current, source):
    commit = get_git_commit(source)
    if parse_version(core4_version) == (0, 0, 0):
        output("install core4 from {} at {}", source, commit)
    else:
        if current != commit:
            output("upgrading core4 from {}, {} => {}", source, current, commit)
        else:
            output(
                "skip core4 upgrade from {}, up-to-date at {} ({})", source,
                current, core4_version)
            return commit
    if TEST:
        output("DRY RUN!")
        return commit
    target = os.path.join(builddir, "core4.src")
    output("clone core4 source tree from {}", source)
    if CORE4_SOURCE.startswith("/"):
        shutil.copytree(parse_git_url(source)[0], target)
    else:
        url, branch = parse_git_url(source)
        git_clone(url, target)
        git_checkout(target, branch)
    os.chdir(target)
    environ["CORE4_CALL"] = "1"
    cmd = [shutil.which("pip"), "install", "--upgrade", "."]
    if VERBOSE == 1:
        cmd.insert(1, "--verbose")
    elif VERBOSE == -1:
        cmd.insert(1, "--quiet")
    Popen(cmd, env=environ).wait()
    os.chdir(CWD)
    return commit


def find_webapps(folder):
    for path, directories, filenames in os.walk(folder):
        for directory in directories:
            pkg_json_file = os.path.join(path, directory, "package.json")
            if os.path.exists(pkg_json_file):
                try:
                    pkg_json = json.load(
                        open(pkg_json_file, "r", encoding="utf-8"))
                except:
                    output("failed to parse {}", pkg_json_file)
                else:
                    if "core4" in pkg_json:
                        command = pkg_json["core4"].get(
                            "build_command", None)
                        dist = pkg_json["core4"].get(
                            "dist", None)
                        if command is not None and dist is not None:
                            yield {
                                "base": os.path.join(path, directory),
                                "command": command,
                                "dist": dist,
                                "name": pkg_json.get("name", None)
                            }


def build_webapp(packages):
    if os.environ.get("CORE4_FE") == "1":
        output("build webapps: {}", os.path.abspath(os.curdir))
        manifest = []
        for pkg in packages:
            path = pkg.replace(".", os.path.sep)
            output("searching webapps in {}", pkg)
            for webapp in find_webapps(path):
                output("found {} in  {}", webapp["name"], webapp["base"])
                curdir = os.path.abspath(os.curdir)
                os.chdir(webapp["base"])
                for cmd in webapp["command"]:
                    output("$ {}", cmd)
                    Popen(cmd, shell=True).wait()
                if os.path.exists(webapp["dist"]):
                    build = True
                else:
                    build = False
                os.chdir(curdir)
                if build:
                    dist_path = os.path.join(webapp["base"], webapp["dist"])
                    manifest.append(dist_path)
        if os.path.exists("MANIFEST.in"):
            output("backup MANIFEST.in")
            shutil.copy("MANIFEST.in", ".MANIFEST.in")
        fh = open("MANIFEST.in", "a", encoding="utf-8")
        fh.write("\n")
        for line in manifest:
            fh.write("recursive-include " + line + " *.* .*\n")
        fh.close()
    else:
        output("skip webapps")


def restore_manifest():
    if os.path.exists(".MANIFEST.in"):
        output("restore MANIFEST.in")
        shutil.copy(".MANIFEST.in", "MANIFEST.in")
    elif os.path.exists("MANIFEST.in"):
        output("remove MANIFEST.in")
        os.unlink("MANIFEST.in")


def check_requirements():
    for m in ("pip", "wheel"):
        try:
            v = check_output([
                sys.executable, "-c",
                "import {m}; print({m}.__version__)".format(m=m)],
                universal_newlines=True)
            s = "verified"
        except:
            s = "failed"
        output("{m} {v} ({s})", m=m, v=v.strip(), s=s)


def upgrade_package(current, version):
    proj_commit = check_output(
        ["git", "rev-parse", "HEAD"], universal_newlines=True).strip()
    if proj_commit == current:
        output("skip project upgrade, up-to-date at {} ({})", current, version)
        return proj_commit
    output("project upgrade {} => {} ({})", current, proj_commit, version)
    if TEST:
        output("DRY RUN!")
        return proj_commit
    cmd = [shutil.which("pip"), "install", "."]
    if EDIT:
        cmd.insert(2, "-e")
    if VERBOSE == 1:
        cmd.insert(1, "--verbose")
    elif VERBOSE == -1:
        cmd.insert(1, "--quiet")
    environ["CORE4_CALL"] = "1"
    Popen(cmd, env=environ).wait()
    return proj_commit


class BuildPyCommand(build_py):
    def run(self):
        build_webapp(self.packages)
        super().run()
        restore_manifest()


class DevelopCommand(develop):
    def run(self):
        output("install edit mode in {}", os.path.abspath(os.curdir))
        folder = [d for d in os.listdir() if os.path.isdir(d) and d[0] != "."]
        build_webapp(folder)
        super().run()
        restore_manifest()


def find_lib(name):
    try:
        info = check_output(
            [shutil.which("pip"), "show", "-f", name],
            universal_newlines=True)
        match = re.search(
            r"^location\s*\:\s*(.+?)\s*$", info, re.I + re.S + re.M)
        location = match.groups()[0].strip()
        match = re.search(
            r"^\s+?([^\n]+\-info[\/\\]top_level\.txt)\s*$", info,
            re.I + re.S + re.M)
        pkg_info = match.groups()[0].strip()
        if location and pkg_info:
            return os.path.join(
                location, os.path.dirname(pkg_info), "core4.json")
    except:
        pass
    return None


def setup(*args, **kwargs):
    if len(sys.argv) == 1:
        t0 = datetime.datetime.now()
        builddir = tempfile.mkdtemp(prefix="c4-")
        output("build in {}", builddir)
        pkg_info = find_lib(kwargs["name"])
        if pkg_info and os.path.exists(pkg_info):
            output("read build info from {}", pkg_info)
            info = json.load(open(pkg_info, "r"))
        else:
            info = {}
        upgrade_pip()
        upgrade_wheel()
        core4_source = kwargs.pop("core4", CORE4_SOURCE)
        core4_commit = upgrade_framework(
            builddir, info.get("core4_commit", None), core4_source)
        proj_version = kwargs.get("version", None)
        proj_commit = upgrade_package(info.get("project_commit", None),
                                      proj_version)
        proj_branch = check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                                   universal_newlines=True).strip()
        pkg_info = find_lib(kwargs["name"])
        output("remove build directory {}", builddir)
        shutil.rmtree(builddir)
        delta = datetime.datetime.now() - t0
        if pkg_info:
            if not TEST:
                output("write build info {}", pkg_info)
                json.dump({
                    "core4_commit": core4_commit,
                    "core4_source": core4_source,
                    "project_commit": proj_commit,
                    "project_branch": proj_branch,
                    "project_version": kwargs.get("version", None),
                    "timestamp": str(datetime.datetime.utcnow()),
                    "runtime": delta.total_seconds()
                }, open(pkg_info, "w"))
        else:
            output("failed to write build info")
        output("runtime {} ({}')", delta, int(delta.total_seconds()))
    else:
        if "CORE4_CALL" not in os.environ:
            output("ERROR!")
            print_help()
        else:
            check_requirements()
            kwargs["cmdclass"] = {
                'build_py': BuildPyCommand,
                'develop': DevelopCommand
            }
            orig_setup(**kwargs)
