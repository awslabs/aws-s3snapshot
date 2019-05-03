# -*- coding: utf-8 -*-
#
# cli.py
#
# Copyright 2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# SPDX-License-Identifier: MIT-0
#
""" Backup script to copy files to S3 """

from __future__ import print_function

import datetime
import json
import locale
import sys
import time

import click
import pkg_resources

from .s3snapshot import SNS_ARN
from .s3snapshot import SNS_ARN_ERROR
from .s3snapshot import STOP
from .s3snapshot import STOPPED
from .s3snapshot import VERBOSE
from .s3snapshot import s3snapshot

locale.setlocale(locale.LC_ALL, '')

reload(sys)
sys.setdefaultencoding('utf8')


@click.command()
@click.option('-l', '--label', metavar='LABEL', help='Label to be included in the Snapshot description')
@click.option('-s', '--stop', is_flag=True, default=STOP, help='Stop Instance before start the snapshot')
@click.option('-sp', '--stopped', is_flag=True, default=STOPPED,
              help='Check if instance is stopped before start the snapshot. (If not skip and flag error)')
@click.option('--sns-arn', metavar='SNS_ARN', help='The SNS topic ARN to send message when finished')
@click.option('--sns-arn-error', metavar='SNS_ARN', help='The SNS topic ARN to send message when an error occour!')
@click.option('-f', '--filter', metavar='FILTER', help=('Filter list to snapshot.\n'
                                                        'ex: --filter \'{"instances": ["i-12345678", "i-abcdef12"], "tags": {"tag:Owner": "John", "tag:Name": "PROD"}}\''''))
@click.option('--verbose', is_flag=True, default=VERBOSE, help='Show extra information during execution')
@click.version_option()
# Main function for CLI iteration
def cli(*args, **kwargs):
    filter_args = kwargs.pop('filter')
    label = kwargs.pop('label')
    sns_arn = kwargs.pop('sns_arn') or SNS_ARN
    sns_arn_error = kwargs.pop('sns_arn_error') or SNS_ARN_ERROR
    # Lets build the JSON (dict) variable to pass to s3snapshot
    event = dict()
    event['stop'] = kwargs.pop('stop')
    event['stopped'] = kwargs.pop('stopped')
    event['sns-arn'] = sns_arn
    event['sns-arn-error'] = sns_arn_error
    event['label'] = label

    if filter_args:
        filter_args = json.loads(filter_args)
        if 'tags' in filter_args.keys():
            event['tags'] = filter_args['tags']

        if 'instances' in filter_args.keys():
            event['instances'] = filter_args['instances']

    PACKAGE = pkg_resources.require("s3snapshot")[0].project_name
    VERSION = pkg_resources.require("s3snapshot")[0].version

    click.echo('ECTP Snapshot to S3 - Version {0}'.format(VERSION))
    click.echo('')

    if event['stop'] and event['stopped']:
        click.echo('[!] Unable to process. You need to choose --stop or --stopped option')
        return

    start = time.time()
    click.echo('[+] Start time: {0}'.format(
        time.strftime('%Y-%m-%d %H:%M:%S %Z', time.localtime(start)))
    )

    response = s3snapshot(
        verbose=kwargs.pop('verbose'),
        event=event,
        start_time=start,
        program='{package}-{version}'.format(
            package=PACKAGE, version=VERSION
        )
    )

    elapsed = time.time() - start

    click.echo('[+] Elapsed time {0}'.format(
        datetime.timedelta(seconds=elapsed)
    )
    )
    code = response['result']
    message = '{icon} The s3snapshot was : {status}'.format(
        icon='[=]' if code == 'Sucessfull' else '[!]',
        status=code
    )
    return click.echo(message)
