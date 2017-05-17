# -*- coding: utf-8 -*-
#
# s3backup.py
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
""" AWS Lambda handler """

from __future__ import print_function

import time

import click
import pkg_resources

from s3snapshot.s3snapshot import s3snapshot


def lambda_handler(event, context):
    """
    This function read the event data and parse to s3snapshot function
    """
    PACKAGE = pkg_resources.require("s3snapshot")[0].project_name
    VERSION = pkg_resources.require("s3snapshot")[0].version

    start = time.time()
    click.echo('[+] Start time: {0}'.format(time.strftime('%Y-%m-%d %H:%M:%S %Z', time.localtime(start))))

    response = s3snapshot(
        event=event,
        context=context,
        start_time=start,
        program='{package}-{version}'.format(
            package=PACKAGE, version=VERSION
        )
    )

    code = response.get('result')
    message = '{icon} The s3snapshot was : {status}'.format(
        icon='[=]' if code == 'Sucessfull' else '[!]',
        status=code
    )
    return message
