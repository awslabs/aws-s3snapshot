# AWS EC2 Snapshot script

## Instalation Instructions

### CLI Production Mode
- Install the package for running-only:

```pip install s3snapshot-X.Y.Z.tar.gz```

(Replace X,Y,Z to the current version downloaded)

### CLI Development Mode
- Install the package in development mode:
- 
```pip install -e s3snapshot-X.Y.Z.tar.gz```

(Replace X,Y,Z to the current version downloaded)

Or extract the package and run:

```python setup.py develop```


## Lambda Function
If you want to build the package from the source you need to run the build.sh script.
This script will copy all source packages from $VIRTUAL_ENV/lib/python2.7/site-packages to the zip file.
To run the script you just need to copy the s3snapshot-X.Y.Z.zip to a S3 bucket or upload directly to your lambda function

The handler will be: ```lambda_handler:lambda_handler```

## Running

### Parameters:
```
Usage: s3snapshot [OPTIONS]

Options:
  -l, --label LABEL        Label to be included in the Snapshot description
  -s, --stop               Stop Instance before start the snapshot
  -sp, --stopped           Check if instance is stopped before start the
                           snapshot. (If not skip and flag error)
  --sns-arn SNS_ARN        The SNS topic ARN to send message when finished
  --sns-arn-error SNS_ARN  The SNS topic ARN to send message when an error
                           occour!
  -f, --filter FILTER      Filter list to snapshot.
                           ex: --filter
                           '{"instances": ["i-12345678", "i-abcdef12"],
                           "tags": {"tag:Owner": "John", "tag:Name": "PROD"}}'
  --verbose                Show extra information during execution
  -v, --version            Display version number and exit.
  --help                   Show this message and exit.
```

* --filter:
The filter parameter defines which instance will be included in the snapshot job.

To filter only certain instance ids you can use:
```
single instance:
s3snapshot --filter '{"instances": ["i-abcdef12"], "stop" : true}'

multiple instances:
s3snapshot --filter '{"instances": ["i-abcdef12", "i-12345678", "i-abc123ab"]}'
```

To filter only certain tags:

```
single tag:
s3snapshot --filter '{"tags": {"tag:Env": "PROD"}}'

multiple tags:
s3snapshot --filter '{"tags": {"tag:Env": "PROD", "tag:Owner": "John"}}'
```
It's important to show that instances are single array of values while tags are array of key/pair values


### Lambda Payload

* Similar to CLI parameters you must provide a valid json document with all the parameters inside.
* Stop Instance can be included as a new key/value pair with { 'stop' : False } 
** False = Snapshot without stop instance
** True = Stop instance before snapshot (script will start the instance after snapshot)

Sample json filter:

Example 1:
```
{
    "tags": {
        "tag:Env": "PROD", 
        "tag:Owner": "John"
    },
    "stop" : false,
    "stopped" : false,
    "verbose" : false,
    "sns-arn" : "arn:aws:sns:us-east-1:100000000000:Snapshot",
    "sns-arn-error" : "arn:aws:sns:us-east-1:100000000000:Snapshot-Err",
    "label" : "string to include in the description",
    "protected" : false
}
```

Example 2:
```
{
    "instances": [
        "i-abcdef12", 
        "i-12345678", 
        "i-abc123ab"
    ]
}


```

* JSON strings must use double-quote

## Changes

### Version 0.1.5 - 2016-11-17
* Bugix: Introduced a bug in the ClientError handler where I invoked create_tag inside the error handling
* Included the Tagging of keys: Scripted and State:Protected

### Version 0.1.4 - 2016-11-16
* Changed the time.sleep to .1 instead of 1 second

### Version 0.1.3 - 2016-11-14
* Bugfix in error handling that don't have the RequestsLimitsExceeded

### Version 0.1.2 - 2016-08-05
* Included the error management for RequestLimitExceeded in CreateTags API

### Version 0.1.1 - 2016-07-25
* Corrected the stopped flag to start instances after the snapshot

### Version 0.1.0 - 2016-07-15
* Initial version
* Support both cli execution or lambda execution
