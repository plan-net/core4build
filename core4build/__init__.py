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
from subprocess import Popen, check_output, call
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
CORE4_SOURCE = "https://github.com/plan-net/core4.git"
RLIB = "../lib/R"
CWD = os.path.abspath(os.curdir)
R_DEFAULT = ("mongoliste", "feather")


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
  --nocolor (-n)      no colored output
  --quiet (-q)        run quietly
  --help (-h)         show detailed help message
  
Install options:
  --test (-t)         don't actually do anything
  --fe (-f)           build and install webapps
  --fe2 (-ff)         build and install core4os framework webapps
  --edit (-e)         install in editable mode (develop mode)
""")


option = {}
argument = [sys.argv[0]]
VERBOSE = 0
COLOR = True
EDIT = False
TEST = False
CORE4_FE = int(os.environ.get("CORE4_FE", "0"))
for elem in sys.argv[1:]:
    swallow = False
    if elem.lower() == "--help" or elem.lower() == "-h":
        print_help()
        sys.exit(0)
    if elem.lower() == "--verbose" or elem.lower() == "-v":
        VERBOSE = 1
        swallow = True
    elif elem.lower() == "--quiet" or elem.lower() == "-q":
        VERBOSE = -1
        swallow = True
    if elem.lower() == "--fe" or elem.lower() == "-f":
        CORE4_FE = 1
        swallow = True
    elif elem.lower() == "--fe2" or elem.lower() == "-ff":
        CORE4_FE = 2
        swallow = True
    if elem.lower() == "--edit" or elem.lower() == "-e":
        EDIT = True
        swallow = True
    if elem.lower() == "--test" or elem.lower() == "-t":
        TEST = True
        swallow = True
    if elem.lower() == "--nocolor" or elem.lower() == "-n":
        COLOR = False
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
    if COLOR:
        sys.stderr.write(bcolors.OKGREEN)
    sys.stderr.write("*** " + args[0].format(*p, **kwargs) + "\n")
    if COLOR:
        sys.stderr.write(bcolors.ENDC)
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


def upgrade_framework(builddir, source, installed_commit, latest_commit,
                      force):
    if parse_version(core4_version) == (0, 0, 0):
        output("core4 upgrade: from None to {}", latest_commit)
    else:
        if latest_commit != installed_commit or force:
            output("core4 upgrade: from {} to {}", installed_commit,
                   latest_commit)
        else:
            output(
                "core4 upgrade: skip at {}", installed_commit)
            return False
    if TEST:
        output("DRY RUN!")
        return True
    target = os.path.join(builddir, "core4.src")
    output("clone core4 source tree from {}", source)
    if CORE4_SOURCE.startswith("/"):
        shutil.copytree(parse_git_url(source)[0], target)
    else:
        url, branch = parse_git_url(source)
        git_clone(url, target)
        git_checkout(target, branch)
    os.chdir(target)
    cmd = [shutil.which("pip")]
    if VERBOSE == 1:
        cmd.append("--verbose")
    elif VERBOSE == -1:
        cmd.append("--quiet")
    cmd += ["install", "."]
    env = os.environ.copy()
    if CORE4_FE == 2:
        env["CORE4_FE"] = "1"
    Popen(cmd, env=env).wait()
    os.chdir(CWD)
    return True


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
    if CORE4_FE != 0:
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
    if CORE4_FE != 0:
        if os.path.exists(".MANIFEST.in"):
            output("restore MANIFEST.in")
            shutil.copy(".MANIFEST.in", "MANIFEST.in")
            os.unlink(".MANIFEST.in")
        elif os.path.exists("MANIFEST.in"):
            output("remove MANIFEST.in")
            os.unlink("MANIFEST.in")


def check_requirements():
    for m in ("pip", "wheel"):
        call([
            sys.executable, "-c",
            "import {m}; print({m}.__version__)".format(m=m)],
            universal_newlines=True)


def upgrade_package(installed_commit, latest_commit, force):
    if installed_commit == latest_commit and not force:
        output("project upgrade: skip at {}", latest_commit)
        return False
    output("project upgrade: from {} to {}", installed_commit, latest_commit)
    if TEST:
        output("DRY RUN!")
        return True
    cmd = [shutil.which("pip"), "install", "."]
    if EDIT:
        cmd.insert(2, "-e")
    if VERBOSE == 1:
        cmd.insert(1, "--verbose")
    elif VERBOSE == -1:
        cmd.insert(1, "--quiet")
    env = os.environ.copy()
    if CORE4_FE != 0:
        env["CORE4_FE"] = "1"
    Popen(cmd, env=env).wait()
    return True


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


def install_r_packages(rlib):
    from rpy2.robjects.packages import importr, isinstalled
    r_requirements = "r.txt"
    if os.path.exists(r_requirements):
        with open(r_requirements, 'r') as file:
            data = file.read()
    else:
        data = ""
    packages_required = data.split(sep='\n')
    for default in R_DEFAULT:
        if default not in packages_required:
            packages_required.append(default)
    utils = importr('utils')
    utils.chooseCRANmirror(ind=1)
    for package in packages_required:
        if package:
            output('Checking package: {}', package)
            output('Installed?: {}', isinstalled(package, lib_loc=rlib))
            if not (isinstalled(package, lib_loc=rlib)):
                utils.install_packages(package, lib=rlib, verbose=False,
                                       quiet=True)


def setup(*args, **kwargs):
    if len(sys.argv) == 1:
        t0 = datetime.datetime.now()
        rlib = os.path.join(os.path.dirname(sys.executable), RLIB)
        if not os.path.exists(rlib):
            output("create {}", rlib)
            if not TEST:
                os.mkdir(rlib)
                os.chmod(rlib, 0o777)
        builddir = tempfile.mkdtemp(prefix="c4-")
        output("build in {}", builddir)
        pkg_info = find_lib(kwargs["name"])
        if pkg_info and os.path.exists(pkg_info):
            output("read build info from {}", pkg_info)
            prev = json.load(open(pkg_info, "r"))
        else:
            prev = {"core4": {}, "project": {}}
        upgrade_pip()
        upgrade_wheel()
        core4_source = kwargs.get("core4", CORE4_SOURCE)
        request = {
            "core4": {
                "commit": get_git_commit(core4_source),
                "source": core4_source,
                "webapps": CORE4_FE == 2
            },
            "project": {
                "commit": check_output(
                    ["git", "rev-parse", "HEAD"],
                    universal_newlines=True).strip(),
                "branch": check_output(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    universal_newlines=True).strip(),
                "version": kwargs.get("version", None),
                "webapps": CORE4_FE != 0
            },
            "timestamp": datetime.datetime.now().isoformat(),
            "runtime": None
        }
        upgrade_core4 = 0
        if kwargs.get("name") != "core4":
            force = (prev["core4"].get("webapps", None)
                     != request["core4"]["webapps"])
            if upgrade_framework(
                    builddir=builddir,
                    source=request["core4"]["source"],
                    installed_commit=prev["core4"].get("commit", None),
                    latest_commit=request["core4"]["commit"],
                    force=force):
                upgrade_core4 = 1
        force = (prev["project"].get("webapps", None)
                 != request["project"]["webapps"])
        upgrade_project = 0
        if upgrade_package(
                installed_commit=prev["project"].get("commit", None),
                latest_commit=request["project"]["commit"],
                force=force):
            upgrade_project = 2
        pkg_info = find_lib(kwargs["name"])
        output("remove build directory {}", builddir)
        shutil.rmtree(builddir)
        delta = datetime.datetime.now() - t0
        request["runtime"] = delta.total_seconds()
        if pkg_info:
            if not TEST:
                output("write build info {}", pkg_info)
                json.dump(request, open(pkg_info, "w"))
        else:
            output("failed to write build info")
        output("runtime {} ({}')", delta, int(delta.total_seconds()))
        upgrade = upgrade_core4 + upgrade_project
        if upgrade == 0:
            output("result: no changes")
        elif upgrade == 1:
            output("result: upgrade core4os")
        elif upgrade == 2:
            output("result: upgrade project")
        else:
            output("result: upgrade core4os and project")
        try:
            install_r_packages(rlib)
        except Exception:
            output("R package installation failed ... R not installed?")
        sys.exit(upgrade)
    else:
        check_requirements()
        kwargs["cmdclass"] = {
            'build_py': BuildPyCommand,
            'develop': DevelopCommand
        }
        orig_setup(**kwargs)
        try:
            import core4
        except:
            core4_source = kwargs.get("core4", CORE4_SOURCE)
            pip_main("install", "git+" + core4_source)
