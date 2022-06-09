#!/usr/bin/env python3

import pathlib

from setuptools import find_packages, setup

HERE = pathlib.Path(__file__).parent

README = (HERE / "README.md").read_text()

setup(
    name="monaco",
    version="0.1.0",
    description="Python framework for complex parametric simulations",
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/servinagero/monaco",
    author="Sergio Vinagrero Gutierrez",
    author_email="servinagrero@gmail.com",
    license="MIT",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
    ],
    packages=find_packages(),
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "monaco=monaco.monaco:main",
        ]
    },
)
