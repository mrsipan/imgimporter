import argparse
import boto3
import botocore.client
import botocore.errorfactory
import botocore.exceptions
import json
import logging
import os
import pathlib
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)


print(os.environ.get('AWS_DEFAULT_REGION'))

def create_bucket(bucket_name: str) -> str:

    client = boto3.client('s3')
    region = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')

    kw = {'Bucket': bucket_name}
    kw.update(
        {CreateBucketConfiguration:
            {'LocationConstraint': region}} if region != 'us-east-1' else {}
        )

    try:
        client.create_bucket(
            **kw
            )
    except botocore.exceptions.ClientError as ex:
        logger.exception(ex)
        sys.exit(1)

    return bucket_name


def upload_file(filename: str, bucket_name: str):

    create_bucket(bucket_name)
    path_to_file = pathlib.Path(filename)
    client = boto3.client('s3')
    object_name = 'vm/' + str(path_to_file.name)

    try:
        rsp = client.upload_file(
            filename,
            bucket_name,
            object_name
            )
    except botocore.exceptions.ClientError as ex:
        logger.exception(ex)
        sys.exit(2)

    return bucket_name, object_name


def set_role_and_policy(bucket_name):

    client = boto3.client('iam')

    try:
        rsp1 = client.create_role(
            Path='/',
            RoleName='vmimport',
            Description='vm import',
            AssumeRolePolicyDocument=json.dumps(
                {'Version': '2012-10-17',
                 'Statement': [{'Effect': 'Allow',
                                'Principal': {'Service': 'vmie.amazonaws.com'},
                                'Action': 'sts:AssumeRole',
                                'Condition': {'StringEquals': {'sts:Externalid': 'vmimport'}}}]}
                )
            )
    except Exception as ex:
        logger.exception(ex)
        pass

    policies = client.list_policies()

    for elem in policies['Policies']:
        if elem['PolicyName'] == 'vmimport_policy':
            policy_arn = elem['Arn']
            break
        else:
            policy_arn = None

    rsp2 = None
    if policy_arn is None:
        try:
            rsp2 = client.create_policy(
                Path='/',
                PolicyName='vmimport_policy',
                Description='vm import policy',
                PolicyDocument=json.dumps({'Version': '2012-10-17',
                                           'Statement': [{'Effect': 'Allow',
                                                          'Action': ['s3:GetBucketLocation',
                                                                     's3:GetObject',
                                                                     's3:ListBucket'],
                                                          'Resource': ['arn:aws:s3:::%s', 'arn:aws:s3:::%s/*']},
                                                          {'Effect': 'Allow',
                                                           'Action': ['ec2:ModifySnapshotAttribute',
                                                                      'ec2:CopySnapshot',
                                                                      'ec2:RegisterImage',
                                                                      'ec2:Describe*'],
                                                           'Resource': '*'}]}
                    )
                )
        except Exception as ex:
            logger.exception(ex)
        else:
            policy_arn = rsp2['Policy']['Arn']


    else:
        print(rsp2)

    rsp3 = client.attach_role_policy(
        PolicyArn=policy_arn,
        RoleName='vmimport'
        )

    print(rsp3)

def import_image(bucket_name, object_name):

    set_role_and_policy(bucket_name)

    client = boto3.client('ec2')

    print('Importing')
    try:
        rsp = client.import_image(
            Architecture='x86_64',
            Description='minimal centos 8 stream',
            DiskContainers=[
                dict(
                    Description='minimal centos 8 stream in raw format',
                    Format='raw',
                    #SnapshotId='',
                    UserBucket=dict(S3Bucket=bucket_name, S3Key=object_name)
                    )
                ]
            )
    except botocore.exceptions.ClientError as ex:
        logger.exception(ex)
        sys.exit(3)

    else:
        print(rsp)


def main():

    # rv = upload_file('build/centos-8-stream-amd64-1571945009.raw', 'sncr-upload-raw-vm-image')
    rv = upload_file('build/final.raw', 'sncr-upload-raw-vm-image')
    import_image(*rv)

if __name__ == '__main__':

    sys.exit(main())

