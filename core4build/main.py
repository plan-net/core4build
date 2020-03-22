from setuptools import setup as orig_setup


def upgrade_pip():
    try:
        from pip._internal.cli.main import main
    except:
        from pip import main
    main(["install", "--upgrade", "pip"])


def setup(*args, **kwargs):
    upgrade_pip()
    return orig_setup(*args, **kwargs)