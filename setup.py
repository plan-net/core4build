
from setuptools import setup

setup(
    name='core4build',
    version="0.0.1",
    author="Michael Rau",
    author_email="Plan.Net Business Intelligence",
    description="core4os delivers a unified insights platform from data "
                "integration, and information/workflow automation to "
                "web-based business applications.",
    url="https://github.com/plan-net/core4",
    packages=["core4build"],
    include_package_data=True,
    install_requires=[],
    zip_safe=False
)

import sys

print("*"*80)
print(sys.executable)
print(sys.argv)
print("*"*80)
import time
time.sleep(30)