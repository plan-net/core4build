import json
import os
import shutil
import subprocess
import sys
import tempfile

from setuptools import setup as orig_setup

CORE4_BRANCH = "master"
CORE4_REPOSITORY = "https://github.com/plan-net/core4.git"

CWD = os.path.abspath(os.curdir)


def check_prerequisites():
    print("check prerequisites")
    print("Python version >= 3.5 ...", end="")
    assert sys.version_info >= (3, 5), "requires Python >= 3.5"
    print("OK")
    print("git ... ", end="")
    assert shutil.which("git") is not None, "requires git executable"
    print("OK")
    print("yarn ... ", end="")
    assert shutil.which("yarn") is not None, "requires yarn executable"
    print("OK")


def git(command, *args):
    cmd = [shutil.which("git"), command] + list(args)
    print("$", " ".join(cmd))
    proc = subprocess.Popen(cmd, stderr=subprocess.STDOUT)
    proc.wait()


def pip_install(package, *args):
    print("install", package)
    subprocess.check_call([sys.executable, "-m", "pip", "install", args, "-U",
                           package])


def install_core4os(repository, branch):
    # todo: skip if no updated
    pip_install("pip")
    core4_worktree = tempfile.mkdtemp()
    git("clone", repository, core4_worktree)
    git("-C", core4_worktree, "checkout", branch)
    os.chdir(core4_worktree)
    pip_install(".")
    os.chdir(CWD)
    print("Cleaning up", core4_worktree)
    shutil.rmtree(core4_worktree)


def find_webapps(folder):
    for path, directories, filenames in os.walk(folder):
        for directory in directories:
            pkg_json_file = os.path.join(
                path, directory, "package.json")
            if os.path.exists(pkg_json_file):
                pkg_json = json.load(
                    open(pkg_json_file, "r", encoding="utf-8"))
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
                # except:
                #     print("failed to parse", pkg_json_file)

def build_webapp(setting):
    print("Installing webapp", setting["base"])
    return
    os.chdir(setting["base"])
    cwd = os.path.abspath(os.curdir)
    for command in setting["command"]:
        os.chdir(cwd)
        print("$", command)
        proc = subprocess.Popen(command, stderr=subprocess.STDOUT, shell=True)
        proc.wait()
    if os.path.exists(setting["dist"]):
        print("found and install webapp from", os.path.abspath(setting["dist"]))
    else:
        print("not found ./dist")
    os.chdir(CWD)


def setup(*args, **kwargs):
    core4_setting = kwargs.pop("core4", {})
    if {"install", "build"}.intersection(sys.argv):
        check_prerequisites()
        if "install" in sys.argv:
            install_core4os(
                repository=core4_setting.get("repository", CORE4_REPOSITORY),
                branch=core4_setting.get("branch", CORE4_BRANCH))
        for webdir in kwargs["packages"]:
            for app in find_webapps(webdir):
                build_webapp(app)
    return orig_setup(*args, **kwargs)


if __name__ == '__main__':
    sys.argv.append("install")
    setup()
