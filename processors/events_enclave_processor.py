import os
import time
import argparse
import boto3
import json
import logging
from fastavro import reader
from urllib.parse import unquote

SQS_WAIT_TIME_SECS = 20
SQS_MAX_MESSAGES = 10

logging.basicConfig(level=logging.INFO)

class ProcessorException(Exception):
    pass


def get_config():
    try:
        return {
            "consumer_queue": os.environ["SQS_QUEUE"],
            "poll_interval_mins": int(os.environ["POLL_INTERVAL_MINS"]),
            "output_bucket": os.environ["JSON_OUTPUT_S3_BUCKET"],
            "output_key": os.environ["JSON_OUTPUT_S3_KEY"]
        }
    except KeyError as e:
        raise ProcessorException(f"Missing expected environment variable: {e}")


def get_json_data(s3_client, bucket, key):
    """This function will attempt to read / parse S3 for JSON events data.
    If data does not already exist, a default object will be returned.
    """
    try:
        data = s3_client.get_object(Bucket=bucket, Key=key)
        contents = data["Body"].read()
        return json.loads(contents)
    except s3_client.exceptions.NoSuchKey:
        return {
            "data_sources": [],
            "data": []
        }


def get_sqs_messages(sqs_client, queue_url):
    res = sqs_client.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=SQS_MAX_MESSAGES,
        WaitTimeSeconds=SQS_WAIT_TIME_SECS
    )
    return res.get("Messages", [])


def process_s3_notification(
        s3_client, s3_notification, output_bucket, output_key
):
    output_data = get_json_data(
        s3_client,
        output_bucket,
        output_key
    )

    for record in s3_notification["Records"]:
        event_name = record["eventName"]

        if not event_name.startswith("ObjectCreated:"):
            raise ProcessorException(f"Unexpected S3 event: {event_name}")

        s3_data = record["s3"]
        bucket = s3_data["bucket"]["name"]
        key = unquote(s3_data["object"]["key"])
        s3_url = f"s3://{bucket}/{key}"

        if s3_url in output_data["data_sources"]:
            logging.info(f"Ignoring previously processed file: {s3_url}")
            continue

        output_data["data_sources"].append(s3_url)

        event_data = s3_client.get_object(
            Bucket=bucket,
            Key=key
        )
        avro_reader = reader(event_data["Body"])
        for event in avro_reader:
            for field in ["source_scheme", "source_host", "source_path",
                          "source_query"]:
                del event[field]
            output_data["data"].append(event)

    put_json_data(
        s3_client,
        output_bucket,
        output_key,
        output_data
    )


def put_json_data(s3_client, bucket, key, data):
    binary_data = json.dumps(data).encode("utf-8")
    s3_client.put_object(Body=binary_data, Bucket=bucket, Key=key)


def main():
    parser = argparse.ArgumentParser(description="")
    parser.add_argument(
        "--daemonize",
        action="store_true",
        help="Deamonize processor"
    )
    args = parser.parse_args()
    daemonize = args.daemonize
    config = get_config()

    sqs_client = boto3.client("sqs")
    s3_client = boto3.client("s3")

    queue_url_data = sqs_client.get_queue_url(
        QueueName=config["consumer_queue"]
    )
    queue_url = queue_url_data["QueueUrl"]

    while True:
        sqs_messages = get_sqs_messages(sqs_client, queue_url)
        for message in sqs_messages:
            receipt_handle = message["ReceiptHandle"]

            sns_data = json.loads(message["Body"])
            s3_notification = json.loads(sns_data["Message"])
            try:
                process_s3_notification(
                    s3_client,
                    s3_notification,
                    config["output_bucket"],
                    config["output_key"]
                )

                # Message processed successfully. Delete from SQS.
                sqs_client.delete_message(
                    QueueUrl=queue_url,
                    ReceiptHandle=receipt_handle
                )
            except ProcessorException as e:
                logging.error(f"Failed processing s3 notification: {e}")

        if not daemonize:
            break

        # Only sleep if the long polling request didn't return any messages.
        # Otherwise we should keep trying to retrieve messages in order to
        # drain the queue as SQS may not have returned all available / max
        # requested. Even an empty response doesn't guarantee the queue
        # is empty, so this is just a heuristic to balance timely processing
        # with SQS requests when the polling interval is non-zero.
        if len(sqs_messages) == 0:
            time.sleep(config["poll_interval_mins"]*60)
        else:
            logging.info(f"Received {len(sqs_messages)} messages")


if __name__ == "__main__":
    main()
