import argparse
import json
import boto3


def create_synthetic_sns_event(s3_bucket, object_key, version_id):
    s3_notification = {
        "Records": [{
            "eventName": "ObjectCreated:Put",
            "s3": {
                "bucket": {
                    "name": s3_bucket
                },
                "object": {
                    "key": object_key,
                    "versionId": version_id
                }
            }
        }]
    }

    return {
        "Message": json.dumps(s3_notification)
    }


def main():
    parser = argparse.ArgumentParser(description="Load Moodle events to SQS")
    parser.add_argument(
        's3_bucket',
        type=str,
        help='S3 bucket name'
    )
    parser.add_argument(
        's3_prefix',
        type=str,
        help='S3 prefix for files'
    )
    parser.add_argument(
        'sqs_queue',
        type=str,
        help='Target SQS queue'
    )
    parser.add_argument(
        '--latest-only',
        action='store_true',
        help="Only consider latest object versions"
    )

    args = parser.parse_args()
    s3_bucket = args.s3_bucket
    s3_prefix = args.s3_prefix
    sqs_queue = args.sqs_queue
    latest_only = args.latest_only

    s3_client = boto3.client('s3')
    sqs_client = boto3.client("sqs")

    paginator = s3_client.get_paginator('list_objects')
    queue_url_data = sqs_client.get_queue_url(
        QueueName=sqs_queue
    )
    queue_url = queue_url_data["QueueUrl"]

    page_iterator = paginator.paginate(
        Bucket=s3_bucket,
        Prefix=s3_prefix
    )

    for page in page_iterator:
        for content in page["Contents"]:
            object_key = content.get("Key")

            if object_key.endswith(".json"):
                object_versions = s3_client.list_object_versions(
                    Bucket=s3_bucket,
                    Prefix=object_key
                )
                for version in object_versions["Versions"]:
                    if latest_only and not version['IsLatest']:
                        continue

                    sns_event = create_synthetic_sns_event(
                        s3_bucket,
                        object_key,
                        version["VersionId"]
                    )
                    sqs_client.send_message(
                        QueueUrl=queue_url,
                        MessageBody=json.dumps(sns_event)
                    )


if __name__ == "__main__":  # pragma: no cover
    main()
