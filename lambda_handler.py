# -*- coding: utf-8 -*-
#
# s3backup.py
#
# Copyright 2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# SPDX-License-Identifier: MIT-0
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
