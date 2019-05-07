# -*- coding: utf-8 -*-
#
# s3backup.py
#
# Copyright 2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# SPDX-License-Identifier: MIT-0
#
"""Backup script to copy files to S3"""

from __future__ import print_function

import datetime
import json
import time
import traceback

import boto3
import botocore
import click
from botocore.exceptions import ClientError

# Constant strings for Default Values (Change if you need to run diferently)
SUCCESS = 'Successful'
FAULT = 'Fault'
PARTIAL = 'Partial'
STOP = False
STOPPED = False
LABEL = ''
SNS_ARN = 'arn:aws:sns:us-east-1:109881088269:SAP-Backup'
SNS_ARN_ERROR = 'arn:aws:sns:us-east-1:109881088269:SAP-Backup'
PROTECTED = False
VERBOSE = False
SLEEP_TIME = 0.1


class SnapshotItem(object):
    def __init__(self, volume_id, instance_id, instance_name, root_device, tags, state, device_name):
        self.volume_id = volume_id
        self.instance_id = instance_id
        self.instance_name = instance_name
        self.root_device = root_device
        self.tags = tags
        self.state = state
        self.device_name = device_name


class SnapshotName(object):
    def __init__(self, date, name, device, volume_id, owner_id):
        """
        Set the variables to be used in the search of the Snapshot names
        """
        self.date = date
        self.name = name
        self.device = device
        self.volume_id = volume_id
        self.owner_id = owner_id
        self.snapshot_query = 's{date}*'.format(date=date)

    def __call__(self, client):
        """
        Run the search based on the variables and return the result
        The search structure is:
        sYYYYMMDD? and from the same OnwerId and VolumeId
        If the search result is empty the first letter to asign is 'a' otherwise is the next subsequent letter
        """
        response = client.describe_snapshots(
            OwnerIds=[self.owner_id],
            Filters=[
                {'Name': 'tag:Name', 'Values': [self.snapshot_query]},
                {'Name': 'volume-id', 'Values': [self.volume_id]}
            ]
        )

        if response['ResponseMetadata']['HTTPStatusCode'] == 200:
            tag_names = []
            for snapshot in response['Snapshots']:
                for tag in snapshot['Tags']:
                    if tag['Key'] == 'Name':
                        tag_names.append(tag['Value'].split('-')[0])

            # If the list of snapshot is not empty, let's sort and get the last one to increment
            if tag_names:
                tag_names.sort()
                return '{date}-{name}-{device}'.format(
                    date=increment_string(tag_names[-1]),
                    name=self.name,
                    device=self.device
                )

            # The list is empty. Let's build the first name
            else:
                # Return the first name with 'a'
                return 's{date}a-{name}-{device}'.format(
                    date=self.date,
                    name=self.name,
                    device=self.device
                )
        # Any error will result in building the first name
        else:
            # Return the first name with 'a'
            return 's{date}a-{name}-{device}'.format(
                date=self.date,
                name=self.name,
                device=self.device
            )


def increment_string(s):
    pos = ord(s[-1])
    if 65 <= pos <= 90:
        # Upper Case Letter
        upper_limit = 90
        loop_to = 97

    elif 97 <= pos <= 122:
        # Lower Case Letter
        upper_limit = 122
        loop_to = 65

    else:
        # Character not in string.ascii_letters
        return ''

    new_pos = pos + 1 if pos + 1 <= upper_limit else loop_to
    return s[:-1] + chr(new_pos)


def send_sns_message(sns_topic, subject, msg, msg_sms=None, msg_email=None,
                     msg_apns=None, msg_gcm=None):
    """
    This function send SNS message to specific topic and can format different
    mesages to e-mail, SMS, Apple iOS and Android
    """
    client_sns = boto3.client('sns')
    sns_arn = sns_topic

    sns_body = dict()
    sns_body['default'] = msg
    sns_body['email'] = msg_email or msg
    sns_body['sms'] = msg_sms or msg
    sns_body['APNS'] = {'aps': {'alert': msg_apns or msg}}
    sns_body['GCM'] = {'data': {'message': msg_gcm or msg}}

    client_sns.publish(
        TargetArn=sns_arn,
        Subject=subject,
        MessageStructure='json',
        Message=json.dumps(sns_body)
    )


def s3snapshot(verbose=VERBOSE, start_time=time.time(), program='', event=None, context=None):
    """
    This function read the parameters from json list and execute the snapshot

    list = json list with filter (instance-id or tags)
    list can contain stop=true/false (If the instances need to be stopped before
    the snapshot start)
    verbose: bool
    start_time: time
    event: dict
    program: str
    context:
    """
    client = boto3.client('ec2')
    flag_error = False
    stop = STOP
    stopped = STOPPED
    label = LABEL
    sns_arn = SNS_ARN
    sns_arn_error = SNS_ARN_ERROR
    protected = PROTECTED
    error_msg = list()
    filter_list = []

    if event:
        # Start parsing the arguments received from Lambda  
        if 'tags' in event.keys():
            tags = event.get('tags', {})
            for key, value in tags.items():
                filter_list.append({'Name': key, 'Values': [value]})

        if 'instances' in event.keys():
            instances = event.get('instances')
            filter_list.append({
                'Name': 'instance-id',
                'Values': [item for item in instances]
            }
            )

        if 'stop' in event.keys():
            stop = event.get('stop')

        if 'stopped' in event.keys():
            stopped = event.get('stopped')

        if 'verbose' in event.keys():
            verbose = event.get('verbose')

        if 'sns-arn' in event.keys():
            sns_arn = event.get('sns-arn')

        if 'sns-arn-error' in event.keys():
            sns_arn_error = event.get('sns-arn-error')

        if 'label' in event.keys():
            label = event.get('label')

        if 'protected' in event.keys():
            protected = event.get('protected')

    click.echo('[+] The stop parameter is    : {0}'.format(stop))
    click.echo('[+] The stopped parameter is : {0}'.format(stopped))

    try:
        response = client.describe_instances(Filters=filter_list)
        # Get the instances
        instances = response[response.keys()[0]]
        # Get the number of instances to inform in the SNS topic
        total_instances = len(instances)
        snapshot_volumes = list()

        for line in instances:
            instance = line['Instances'][0]

            if verbose:
                click.echo('[+] Instance Id to snapshot : {instance}'.format(instance=instance['InstanceId']))
                click.echo('[+] Block Devices to snapshot:')

            for block in instance['BlockDeviceMappings']:
                tags = []
                name = None
                if block.get('Ebs', None) is None:
                    continue

                if instance.get('Tags'):
                    # Pool the tags and get the Instance name to use and strip the tags that begin 'aws:'
                    for tag in instance.get('Tags', {}):
                        if not tag.get('Key').startswith('aws:') and not tag.get('Key') == 'Name':
                            tags.append({'Key': tag['Key'], 'Value': tag['Value']})

                        elif tag.get('Key') == 'Name':
                            # Search for the snapshots with the current device to check if there
                            # is other snapshots from today
                            name = SnapshotName(
                                date=datetime.datetime.today().strftime('%Y%m%d'),
                                name=tag.get('Value'),
                                device=block.get('DeviceName'),
                                volume_id=block.get('Ebs', {}).get('VolumeId'),
                                owner_id=line.get('OwnerId')
                            )
                            tags.append({'Key': tag.get('Key'), 'Value': name(client)})

                if not name:
                    # If the volume don't have Tags we create the tag Name
                    name = SnapshotName(
                        date=datetime.datetime.today().strftime('%Y%m%d'),
                        name=instance.get('InstanceId'),
                        device=block.get('DeviceName'),
                        volume_id=block.get('Ebs', {}).get('VolumeId'),
                        owner_id=line.get('OwnerId')
                    )
                    tags.append({'Key': "Name", 'Value': name(client)})

                # Add the volume to the list of items to snapshot
                snapshot_volumes.append(
                    SnapshotItem(
                        volume_id=block.get('Ebs', {}).get('VolumeId'),
                        instance_id=instance.get('InstanceId'),
                        instance_name=name if name else instance.get('InstanceId'),
                        device_name=block.get('DeviceName'),
                        root_device=True if block.get('DeviceName') == instance.get('RootDeviceName') else False,
                        tags=tags,
                        state=instance.get('State', {}).get('Name')
                    )
                )

                if verbose:
                    click.echo('[\]  ID: [ {id} - {device} ]'.format(id=id, device=block.get('DeviceName')))

    except Exception:
        click.echo('[!] Unable to get instances info. Check your permissions or connectivity')
        if verbose:
            click.echo('Error {error}'.format(error=traceback.format_exc()))
        flag_error = True
        error_msg.append(traceback.format_exc())
        return {'result': FAULT}

    # Number of items
    total_volumes = len(snapshot_volumes)
    # Number of snapshots successfull (At this point none)
    total_success = 0
    # Number of snapshots failed (At this point is zero :)
    total_failures = 0

    # Start Snapshot Creation
    for snapshot in snapshot_volumes:
        click.echo(
            '[+] Snapshot Instance-id : {id} - Volume-id : {vol} - Block-dev : {block} - Root-dev : {root}'.format(
                id=snapshot.instance_id,
                vol=snapshot.volume_id,
                block=snapshot.device_name,
                root=snapshot.root_device
            )
        )

        snapshot_desc = 'Script {program} [Instance ID = {instance}] [Stop : {stop}] [Stopped : {stopped}] [State : {state}] {label}'.format(
            program=program,
            instance=snapshot.instance_id,
            stop=stop,
            stopped=stopped,
            state=snapshot.state,
            label=label
        )

        # Need to stop first?
        instance_stopped = False
        if stop:
            click.echo('[+] Stopping instance : {id}'.format(id=snapshot.instance_id))
            response = client.stop_instances(InstanceIds=[snapshot.instance_id])

            try:
                click.echo('[+] Waiting till the instance is stopped...')
                client.get_waiter('instance_stopped').wait(InstanceIds=[snapshot.instance_id])
                instance_stopped = True

            except Exception:
                click.echo('[!] Error waiting for instance to stop!')
                flag_error = True
                total_failures += 1
                error_msg.append(traceback.format_exc())

        # Need to check if the instance is already stopped before start the snapshot
        if (stopped and snapshot.state == 'stopped') or (not stopped and stop and instance_stopped) or (
                    not stop and not stopped):

            try:
                # Try to avoid Throttling API requests. Wait 1 second before start.
                time.sleep(SLEEP_TIME)
                response = client.create_snapshot(
                    DryRun=False,
                    VolumeId=snapshot.volume_id,
                    Description=snapshot_desc
                )

            except Exception:
                click.echo(
                    ('[!] Unable to run CreateSnapshot of:\n'
                     'Instance-id : {id}'
                     ' - Volume-id : {vol}'
                     ' - Block-dev : {block}'
                     ' - Root-dev : {root}').format(
                        id=snapshot.instance_id, vol=snapshot.volume_id,
                        block=snapshot.device_name, root=snapshot.root_device
                    )
                )
                flag_error = True
                total_failures += 1
                if verbose:
                    click.echo('[!] {0}'.format(traceback.format_exc()))

                # Add the error message in the stack to send by e-mail later
                error_msg.append(traceback.format_exc())

            # Did the Snapshot run correctly?
            if response.get('State', 'error') is not 'error':
                click.echo('[=] Snapshot created!')
                click.echo('[+] Snapshot Name : {name} - ID : {id}'.format(
                    name=snapshot_desc,
                    id=response['SnapshotId'])
                )
                if verbose:
                    # This in line function will manage datetime.datetime inside response dict
                    date_handler = lambda obj: (
                        obj.isoformat() if isinstance(obj, datetime.datetime) or isinstance(obj,
                                                                                            datetime.date) else None)
                    click.echo('[~] response info {info}'.format(
                        info=json.dumps(response, default=date_handler, indent=4))
                    )

                # Add tags to Snapshot
                try:
                    # loop thru each tag to ignore tags with prefix: 'aws:
                    for tag in snapshot.tags:
                        if not tag.get('Key', '').startswith('aws:'):
                            client.create_tags(Resources=[response['SnapshotId']], Tags=[tag])

                    # Tag the State and Scripted tags
                    client.create_tags(Resources=[response.get('SnapshotId')], Tags=[{"Key": "Scripted", "Value": "True"}])
                    client.create_tags(Resources=[response.get('SnapshotId')],
                                       Tags=[{"Key": "State:Protected", "Value": '{}:{}'.format(snapshot.state, protected)}])

                except botocore.exceptions.ClientError:
                    # If we have requested too fast we need to wait an run again ;-)
                    click.echo('[!] Error writing tags... Waiting for {} secods'.format(SLEEP_TIME))
                    time.sleep(SLEEP_TIME)
                    flag_error = True
                    total_failures += 1
                    pass

                except Exception:
                    click.echo('[!] Error creating Snapshot Tags: {error}'.format(error=traceback.format_exc()))
                    # Add the error message in the stack to send by e-mail later
                    error_msg.append(traceback.format_exc())
                    flag_error = True
                    total_failures += 1
                    pass

            else:
                click.echo('[!] Snapshot creation Failed!')
                flag_error = True
                total_failures += 1

        else:
            click.echo('[!] Instance required to be stopped but is not stopped. Skipping')
            flag_error = True
            total_failures += 1

        if stop or stopped:
            # Bring instance back to running state
            # (Wait 1 second to give time to snapshot start)
            time.sleep(SLEEP_TIME)
            response = client.start_instances(InstanceIds=[snapshot.instance_id])

        if not flag_error:
            total_success += 1
        # Reset the flag_error to iterate again
        flag_error = False
        click.echo('')

    msg_result = ''
    msg_result += '[=] Total Instances          : {instances}\n'.format(instances=total_instances)
    msg_result += '[=] Total volumes to process : {total}\n'.format(total=total_volumes)
    msg_result += '[=] Total volumes failed     : {failed}\n'.format(failed=total_failures)
    msg_result += '[=] Total volumes success    : {success}\n'.format(success=total_success)

    click.echo(msg_result)

    if total_success == total_volumes:
        status = SUCCESS
    elif total_success > 0:
        status = PARTIAL
    else:
        status = FAULT

    # Finished Processing. Send SNS results

    click.echo('[+] Sending SNS topic ')
    elapsed_time = time.time() - start_time
    message_default = (
        'The snapshot of servers has been {status}\n'
        'Start time: {start}\n'
        'Elapsed time {elapsed}\n'
        '{total}').format(
        status=status,
        start=time.strftime('%Y-%m-%d %H:%M:%S %Z', time.localtime(start_time)),
        elapsed=datetime.timedelta(seconds=elapsed_time),
        total=msg_result
    )
    if context:
        message_context = '[+] Json parameter passed to lambda function {json}\n'.format(json=event)
        message_context += (
            '[~] For more information read context\n'
            '[~] Log stream name: {name}\n'
            '[~] Log group name: {group}\n'
            '[~] Request ID: {request}\n'
            '[~] Mem. limits(MB): {limits}\n').format(
            name=context.log_stream_name,
            group=context.log_group_name,
            request=context.aws_request_id,
            limits=context.memory_limit_in_mb
        )
        message_default += message_context
        if verbose:
            click.echo('{message}'.format(message=message_context))
    try:
        send_sns_message(
            sns_arn,
            subject='[Snapshot {status}]'.format(status=status),
            msg=message_default
        )

    except Exception:
        click.echo('[!] Error when sending SNS message: Unable to send SNS')
        if verbose:
            click.echo('[!] Error: {0}'.format(traceback.format_exc()))
        error_msg.append(traceback.format_exc())

    if status == FAULT or status == PARTIAL:
        message_default = (
            'There are errors during the snapshot processing\n'
            'Bellow the information of the processing job:\n'
            'Start time  : {start}\n').format(
            start=time.strftime('%Y-%m-%d %H:%M:%S %Z', time.localtime(start_time))
        )

        # Include all error messages in the default msg
        for line in error_msg:
            message_default += '\n'
            message_default += 'error: {0}'.format(line)

        # Customize the error message to SMS
        message_sms = ('Snapshot status: {status}\n'
                       'There are errors during the Snapshot\n'
                       'Look in your e-mail for more information').format(status=status)
        try:
            send_sns_message(
                sns_arn_error,
                subject='[Snapshot {status}]'.format(status=status),
                msg=message_default,
                msg_sms=message_sms
            )
        except:
            click.echo('[!] Error when sending SNS error message: Unable to send SNS')
            if verbose:
                click.echo('[!] {0}'.format(traceback.format_exc()))

    # Return an HTTP error code
    return {'result': status}
