import os
import argparse
import boto3
import json
import logging
from fastavro import reader
from urllib.parse import unquote
from .common import ProcessorException, processor_runner


logging.basicConfig(level=logging.INFO)


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


def get_sqs_message_processor(
    s3_client, s3_output_bucket, s3_output_key
):

    def inner(sqs_message):
        sns_data = json.loads(sqs_message["Body"])
        s3_notification = json.loads(sns_data["Message"])

        process_s3_notification(
            s3_client,
            s3_notification,
            s3_output_bucket,
            s3_output_key
        )

    return inner


def main():
    logging.info("Starting processor...")
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

    processor = get_sqs_message_processor(
        s3_client=s3_client,
        s3_output_bucket=config["output_bucket"],
        s3_output_key=config["output_key"]
    )

    processor_runner(
        sqs_client=sqs_client,
        sqs_queue_name=config["consumer_queue"],
        processor=processor,
        poll_interval_mins=config["poll_interval_mins"],
        daemonize=daemonize
    )


if __name__ == "__main__":  # pragma: no cover
    main()
