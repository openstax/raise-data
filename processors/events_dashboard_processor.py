import os
import argparse
import boto3
import json
import logging
from fastavro import reader
from urllib.parse import unquote
from datetime import datetime, timezone
from urllib.parse import unquote
import hashlib
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .common import (
    ProcessorException,
    processor_runner,
    commit_ignoring_unique_violations,
)
from raise_data.dashboard.schema import (
    ContentLoadedEvent,
    PsetProblemAttemptedEvent,
    InputSubmittedEvent,
)


logging.basicConfig(level=logging.INFO)

# We setup the sqlalchemy resources at global scope and so read some expected
# environment variables here. If they end up being missing, we'll fail later
# anyways.

pg_server = os.getenv("POSTGRES_SERVER", "")
pg_db = os.getenv("POSTGRES_DB", "")
pg_user = os.getenv("POSTGRES_USER", "")
pg_password = os.getenv("POSTGRES_PASSWORD", "")
sqlalchemy_url = f"postgresql://{pg_user}:{pg_password}@{pg_server}/{pg_db}"

engine = create_engine(sqlalchemy_url)
session_factory = sessionmaker(engine)


def get_config():
    try:
        return {
            "consumer_queue": os.environ["SQS_QUEUE"],
            "poll_interval_mins": int(os.environ["POLL_INTERVAL_MINS"]),
            "event_type": os.environ["EVENT_TYPE"],
            "postgres_server": os.environ["POSTGRES_SERVER"],
            "postgres_db": os.environ["POSTGRES_DB"],
            "postgres_user": os.environ["POSTGRES_USER"],
            "postgres_password": os.environ["POSTGRES_PASSWORD"],
        }
    except KeyError as e:
        raise ProcessorException(f"Missing expected environment variable: {e}")


def timestamp_utc_conversion(millisecond_timestamp):
    # Remove decimal from timestamp_seconds via int()
    timestamp_seconds = int(millisecond_timestamp / 1000)
    timestamp_utc = datetime.fromtimestamp(timestamp_seconds, timezone.utc)
    return timestamp_utc


def process_events(event_data, event_type):
    event_timestamp_utc = timestamp_utc_conversion(event_data["timestamp"])
    user_uuid_md5 = hashlib.md5(event_data["user_uuid"].encode("utf-8")).hexdigest()
    modified_event_data = {
        "user_uuid_md5": user_uuid_md5,
        "course_id": event_data["course_id"],
        "impression_id": event_data["impression_id"],
        "timestamp": event_timestamp_utc,
        "content_id": event_data["content_id"],
        "variant": event_data["variant"],
    }

    if event_type == "input_submitted_event":
        modified_event_data["input_content_id"] = event_data["input_content_id"]
    elif event_type == "pset_problem_attempted_event":
        modified_event_data["pset_content_id"] = event_data["pset_content_id"]
        modified_event_data["pset_problem_content_id"] = event_data[
            "pset_problem_content_id"
        ]
        modified_event_data["problem_type"] = event_data["problem_type"]
        modified_event_data["correct"] = event_data["correct"]
        modified_event_data["attempt"] = event_data["attempt"]
        modified_event_data["final_attempt"] = event_data["final_attempt"]

    with session_factory() as session:
        if event_type == "content_loaded_event":
            session.add(ContentLoadedEvent(**modified_event_data))
        elif event_type == "input_submitted_event":
            session.add(InputSubmittedEvent(**modified_event_data))
        elif event_type == "pset_problem_attempted_event":
            session.add(PsetProblemAttemptedEvent(**modified_event_data))

        commit_ignoring_unique_violations(session)


def process_s3_notification(s3_client, s3_notification, event_type):
    for record in s3_notification["Records"]:
        event_name = record["eventName"]

        if not event_name.startswith("ObjectCreated:"):
            raise ProcessorException(f"Unexpected S3 event: {event_name}")

        s3_data = record["s3"]
        bucket = s3_data["bucket"]["name"]
        key = unquote(s3_data["object"]["key"])

        event_data = s3_client.get_object(Bucket=bucket, Key=key)

        types_of_events = {
            "content_loaded_event": "content_loaded_event",
            "input_submitted_event": "input_submitted_event",
            "pset_problem_attempted_event": "pset_problem_attempted_event",
        }

        avro_reader = reader(event_data["Body"])
        for event in avro_reader:
            for field in [
                "source_scheme",
                "source_host",
                "source_path",
                "source_query",
            ]:
                del event[field]
            if event_type != "content_loaded_event":
                del event["response"]

            if types_of_events[event_type]:
                process_events(event, event_type)
            else:  # pragma: no cover
                raise ProcessorException(f"Unexpected event type {event_type}")


def get_sqs_message_processor(s3_client, event_type):
    def inner(sqs_message):
        sns_data = json.loads(sqs_message["Body"])
        s3_notification = json.loads(sns_data["Message"])

        process_s3_notification(s3_client, s3_notification, event_type)

    return inner


def main():
    logging.info("Starting processor...")
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("--daemonize", action="store_true", help="Deamonize processor")
    args = parser.parse_args()
    daemonize = args.daemonize
    config = get_config()

    sqs_client = boto3.client("sqs")
    s3_client = boto3.client("s3")

    processor = get_sqs_message_processor(
        s3_client=s3_client, event_type=config["event_type"]
    )

    processor_runner(
        sqs_client=sqs_client,
        sqs_queue_name=config["consumer_queue"],
        processor=processor,
        poll_interval_mins=config["poll_interval_mins"],
        daemonize=daemonize,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
