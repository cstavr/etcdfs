#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

with open('README.rst') as f:
    readme = f.read()

requirements = [
    'fusepy',
    'boltons',
    'python-etcd',
]

setup_requirements = [
]

test_requirements = [
]

setup(
    name='etcdfs',
    version='0.1.0',
    description="Filesystem based on etcd",
    long_description=readme,
    author="Christos Stavrakakis",
    author_email='stavr.chris@gmail.com',
    url='https://github.com/cstavr/etcdfs',
    packages=find_packages(include=['etcdfs']),
    include_package_data=True,
    install_requires=requirements,
    license="BSD license",
    zip_safe=False,
    keywords='etcdfs',
    classifiers=[
        'License :: OSI Approved :: BSD License',
        "Programming Language :: Python :: 2",
        'Programming Language :: Python :: 2.7',
    ],
    test_suite='tests',
    tests_require=test_requirements,
    setup_requires=setup_requirements,
    entry_points={
        "console_scripts": ["etcdfs = etcdfs.etcdfs:main"],
    }
)
