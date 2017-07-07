# -*- coding: utf-8 -*-
#
# setup.py
#
# Copyright 2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Amazon Software License (the "License").
# You may not use this file except in compliance with the License.
# A copy of the License is located at
#
#    http://aws.amazon.com/asl/
#
# or in the "license" file accompanying this file.
# This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# express or implied.
# See the License for the specific language governing permissions and limitations under the License.
#
#

"""
S3 Snapshot tools 
"""

import io
import os
import re
from setuptools import setup


def read(*names, **kwargs):
    with io.open(
        os.path.join(os.path.dirname(__file__), *names),
        encoding=kwargs.get("encoding", "utf8")
    ) as fp:
        return fp.read()


def find_version(*file_paths):
    version_file = read(*file_paths)
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


setup(
    name='s3snapshot',
    version=find_version("s3snapshot", "__init__.py"),
    license='Apache Software License',
    py_modules=['s3snapshot.s3snapshot', 's3snapshot.cli', 'lambda_handler'],
    author='Rafael M. Koike',
    author_email='koiker@amazon.com',
    description='Snapshot script',
    install_requires=[
        'boto3',
        'click'
    ],
    entry_points='''
        [console_scripts]
        s3snapshot=s3snapshot.cli:cli
    ''',
)
