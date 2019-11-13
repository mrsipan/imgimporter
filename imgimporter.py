from pprint import pprint as pp
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
import pytest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

PYTEST = False


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


def upload_file(filename: str, bucket_name: str) -> (str, str):

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


def set_role_and_policy(bucket_name: str):

    client = boto3.client('iam')

    try:
        logger.info(pp(client.create_role(
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
            )))
    except Exception as ex:
        logger.exception(ex)

    policies = client.list_policies()
    policy_arn = None

    for elem in policies['Policies']:
        if elem['PolicyName'] == 'vmimport_policy':
            policy_arn = elem['Arn']
            break

    rsp = None
    if policy_arn is None:
        try:
            rsp = client.create_policy(
                Path='/',
                PolicyName='vmimport_policy',
                Description='vm import policy',
                PolicyDocument=json.dumps(
                    {'Version': '2012-10-17',
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
            policy_arn = rsp['Policy']['Arn']
            logger.info(pp(rsp))


    logger.info(pp(client.attach_role_policy(
        PolicyArn=policy_arn,
        RoleName='vmimport'
        )))


def import_image(bucket_name: str, object_name: str):

    set_role_and_policy(bucket_name)

    client = boto3.client('ec2')

    logger.info('Importing')
    rsp = None
    try:

        rsp = client.import_image(
            Architecture='x86_64',
            Description=object_name,
            DiskContainers=[
                dict(
                    Description=object_name,
                    Format='raw',
                    UserBucket=dict(S3Bucket=bucket_name, S3Key=object_name)
                    )
                ]
            )

    except botocore.exceptions.ClientError as ex:
        logger.exception(ex)
        sys.exit(3)

    else:

        task_id = rsp['ImportTaskId']

        while True:

            rv = client.describe_import_image_tasks(
                ImportTaskIds=[task_id]
                )

            logger.info(rv['ImportImageTasks'][0]['StatusMessage'])

            if rv['ImportImageTasks'][0]['Status'] == 'completed' or PYTEST:

                logger.info('Task completed')
                break


def delete_object(bucket_name: str, object_name: str):

    client = boto3.client('s3')
    client.delete_object(
        Bucket=bucket_name,
        Key=object_name,
        )


def parse_args(args=None):

    args = args if args is not None else sys.argv[:1]

    parser = argparse.ArgumentParser(description='Import image as aws ami')
    parser.add_argument('bucket_name', help='bucket name')
    parser.add_argument('image_file', help='Image file')
    return parser.parse_args(args)


def main():

    settings = parse_args()

    bucket_name, object_name = upload_file(
        settings.image_file,
        settings.bucket_name,
        )

    import_image(bucket_name, object_name)

    clean(bucket_name, object_name)

### Tests

def test_create_bucket(mocker):

    mocker.patch('boto3.client')
    create_bucket('hello')


def test_upload_file(mocker):

    mocker.patch('boto3.client')
    upload_file('hello', 'bucket-name')


def test_set_role_and_police(mocker):

    mocker.patch('boto3.client')
    set_role_and_policy('bucket-name')


def test_import_image(mocker):

    global PYTEST; PYTEST = True
    mocker.patch('boto3.client')
    import_image('bucket-name', 'bucket-key-name')


def test_parse_args(mocker):

    args = ['bucket-name', 'image-file']

    print(parse_args(args).bucket_name)
    print(parse_args(args).image_file)

if __name__ == '__main__':

    pytest.main(['-s', __file__])

