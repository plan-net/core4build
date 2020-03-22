from setuptools import setup as orig_setup

def setup(*args, **kwargs):
    print("HELLO WORLD"*10)
    return orig_setup(*args, **kwargs)