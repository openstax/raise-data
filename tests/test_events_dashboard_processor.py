from raise_data.processors import events_dashboard_processor, common
import pytest
import json
import io
import os
import boto3
import botocore.stub
from fastavro import writer, parse_schema
from datetime import datetime, timezone, timedelta
from raise_data.dashboard.schema import (
    ContentLoadedEvent,
    PsetProblemAttemptedEvent,
    InputSubmittedEvent,
)


@pytest.fixture(autouse=True)
def clear_database_tables():
    """This fixture is setup to clear tables before each test run in
    this file
    """
    with events_dashboard_processor.session_factory.begin() as session:
        session.query(ContentLoadedEvent).delete()
        session.query(PsetProblemAttemptedEvent).delete()
        session.query(InputSubmittedEvent).delete()


def test_process_single_message_new_content_loaded_event_data(mocker):
    s3_client = boto3.client("s3")
    sqs_client = boto3.client("sqs", region_name="halo")
    s3_stubber = botocore.stub.Stubber(s3_client)
    sqs_stubber = botocore.stub.Stubber(sqs_client)

    mock_s3_notification_data = {
        "Records": [
            {
                "eventName": "ObjectCreated:Post",
                "s3": {
                    "bucket": {"name": "testeventbucket"},
                    "object": {"key": "testeventkey"},
                },
            }
        ]
    }
    mock_sns_data = {"Message": json.dumps(mock_s3_notification_data)}

    mock_avro_schema = {
        "namespace": "test",
        "type": "record",
        "name": "Event",
        "fields": [
            {"name": "user_uuid", "type": "string"},
            {"name": "course_id", "type": "int"},
            {"name": "impression_id", "type": "string"},
            {"name": "source_scheme", "type": "string"},
            {"name": "source_host", "type": "string"},
            {"name": "source_path", "type": "string"},
            {"name": "source_query", "type": "string"},
            {"name": "timestamp", "type": "string"},
            {"name": "content_id", "type": "string"},
            {"name": "variant", "type": "string"},
        ],
    }
    parsed_schema = parse_schema(mock_avro_schema)
    mock_avro_data = [
        {
            "user_uuid": "1-1-1-1-1",
            "course_id": 1,
            "impression_id": "1-1-1-1-1",
            "source_scheme": "scheme",
            "source_host": "host",
            "source_path": "path",
            "source_query": "query",
            "timestamp": "1671230604737",
            "content_id": "1-1-1-1-1",
        },
        {
            "user_uuid": "2-2-2-2-2",
            "course_id": 2,
            "impression_id": "2-2-2-2-2",
            "source_scheme": "scheme",
            "source_host": "host",
            "source_path": "path",
            "source_query": "query",
            "timestamp": "1671230604737",
            "content_id": "2-2-2-2-2",
        },
    ]
    mock_avro_bytes = io.BytesIO()
    writer(mock_avro_bytes, parsed_schema, mock_avro_data, codec="snappy")
    mock_avro_bytes.seek(0)
    expected_post_data = {
        "data_sources": ["s3://testeventbucket/testeventkey"],
        "data": [{"course_id": 1}, {"course_id": 2}],
    }

    sqs_stubber.add_response(
        "get_queue_url",
        {"QueueUrl": "https://testqueue"},
        expected_params={"QueueName": "testqueue"},
    )
    sqs_stubber.add_response(
        "receive_message",
        {
            "Messages": [
                {"ReceiptHandle": "message1", "Body": json.dumps(mock_sns_data)}
            ]
        },
        expected_params={
            "QueueUrl": "https://testqueue",
            "MaxNumberOfMessages": 10,
            "WaitTimeSeconds": 20,
        },
    )
    sqs_stubber.add_response(
        "delete_message",
        {},
        expected_params={"QueueUrl": "https://testqueue", "ReceiptHandle": "message1"},
    )
    s3_stubber.add_client_error(
        "get_object",
        service_error_code="NoSuchKey",
        expected_params={
            "Bucket": "testdatabucket",
            "Key": "testdatakey",
        },
    )
    s3_stubber.add_response(
        "get_object",
        {"Body": mock_avro_bytes},
        expected_params={
            "Bucket": "testeventbucket",
            "Key": "testeventkey",
        },
    )
    s3_stubber.add_response(
        "put_object",
        {},
        {
            "Bucket": "testdatabucket",
            "Body": json.dumps(expected_post_data).encode("utf-8"),
            "Key": "testdatakey",
        },
    )

    s3_stubber.activate()
    sqs_stubber.activate()
    mocker_map = {"s3": s3_client, "sqs": sqs_client}
    mocker.patch("boto3.client", lambda client: mocker_map[client])
    mocker.patch(
        "os.environ",
        {
            "SQS_QUEUE": "testqueue",
            "POLL_INTERVAL_MINS": "1",
            "JSON_OUTPUT_S3_BUCKET": "testdatabucket",
            "JSON_OUTPUT_S3_KEY": "testdatakey",
        },
    )
    mocker.patch("sys.argv", [""])
    events_dashboard_processor.main()

    s3_stubber.assert_no_pending_responses()
    sqs_stubber.assert_no_pending_responses()


# def test_process_single_message_duplicate_data(mocker):
#     s3_client = boto3.client("s3")
#     sqs_client = boto3.client("sqs", region_name="tatooine")
#     s3_stubber = botocore.stub.Stubber(s3_client)
#     sqs_stubber = botocore.stub.Stubber(sqs_client)

#     mock_s3_notification_data = {
#         "Records": [
#             {
#                 "eventName": "ObjectCreated:Put",
#                 "s3": {
#                     "bucket": {"name": "testeventbucket"},
#                     "object": {"key": "testeventkey"},
#                 },
#             }
#         ]
#     }
#     mock_sns_data = {"Message": json.dumps(mock_s3_notification_data)}
#     mock_event_data = {
#         "data_sources": ["s3://testeventbucket/testeventkey"],
#         "data": [{"course_id": 1}, {"course_id": 2}],
#     }

#     expected_put_data = {
#         "data_sources": ["s3://testeventbucket/testeventkey"],
#         "data": [{"course_id": 1}, {"course_id": 2}],
#     }

#     sqs_stubber.add_response(
#         "get_queue_url",
#         {"QueueUrl": "https://testqueue"},
#         expected_params={"QueueName": "testqueue"},
#     )
#     sqs_stubber.add_response(
#         "receive_message",
#         {
#             "Messages": [
#                 {"ReceiptHandle": "message1", "Body": json.dumps(mock_sns_data)}
#             ]
#         },
#         expected_params={
#             "QueueUrl": "https://testqueue",
#             "MaxNumberOfMessages": 10,
#             "WaitTimeSeconds": 20,
#         },
#     )
#     sqs_stubber.add_response(
#         "delete_message",
#         {},
#         expected_params={"QueueUrl": "https://testqueue", "ReceiptHandle": "message1"},
#     )

#     s3_stubber.add_response(
#         "get_object",
#         {"Body": io.BytesIO(json.dumps(mock_event_data).encode("utf-8"))},
#         expected_params={
#             "Bucket": "testdatabucket",
#             "Key": "testdatakey",
#         },
#     )
#     s3_stubber.add_response(
#         "put_object",
#         {},
#         {
#             "Bucket": "testdatabucket",
#             "Body": json.dumps(expected_put_data).encode("utf-8"),
#             "Key": "testdatakey",
#         },
#     )

#     s3_stubber.activate()
#     sqs_stubber.activate()
#     mocker_map = {"s3": s3_client, "sqs": sqs_client}
#     mocker.patch("boto3.client", lambda client: mocker_map[client])
#     mocker.patch(
#         "os.environ",
#         {
#             "SQS_QUEUE": "testqueue",
#             "POLL_INTERVAL_MINS": "1",
#             "JSON_OUTPUT_S3_BUCKET": "testdatabucket",
#             "JSON_OUTPUT_S3_KEY": "testdatakey",
#         },
#     )
#     mocker.patch("sys.argv", [""])
#     events_enclave_processor.main()

#     s3_stubber.assert_no_pending_responses()
#     sqs_stubber.assert_no_pending_responses()


# def test_process_single_message_bad_event(mocker):
#     s3_client = boto3.client("s3")
#     sqs_client = boto3.client("sqs", region_name="tatooine")
#     s3_stubber = botocore.stub.Stubber(s3_client)
#     sqs_stubber = botocore.stub.Stubber(sqs_client)

#     mock_s3_notification_data = {
#         "Records": [
#             {
#                 "eventName": "ObjectSomething",
#                 "s3": {
#                     "bucket": {"name": "testeventbucket"},
#                     "object": {"key": "testeventkey"},
#                 },
#             }
#         ]
#     }
#     mock_sns_data = {"Message": json.dumps(mock_s3_notification_data)}

#     sqs_stubber.add_response(
#         "get_queue_url",
#         {"QueueUrl": "https://testqueue"},
#         expected_params={"QueueName": "testqueue"},
#     )
#     sqs_stubber.add_response(
#         "receive_message",
#         {
#             "Messages": [
#                 {"ReceiptHandle": "message1", "Body": json.dumps(mock_sns_data)}
#             ]
#         },
#         expected_params={
#             "QueueUrl": "https://testqueue",
#             "MaxNumberOfMessages": 10,
#             "WaitTimeSeconds": 20,
#         },
#     )

#     s3_stubber.add_client_error(
#         "get_object",
#         service_error_code="NoSuchKey",
#         expected_params={
#             "Bucket": "testdatabucket",
#             "Key": "testdatakey",
#         },
#     )

#     s3_stubber.activate()
#     sqs_stubber.activate()
#     mocker_map = {"s3": s3_client, "sqs": sqs_client}
#     mocker.patch("boto3.client", lambda client: mocker_map[client])
#     mocker.patch(
#         "os.environ",
#         {
#             "SQS_QUEUE": "testqueue",
#             "POLL_INTERVAL_MINS": "1",
#             "JSON_OUTPUT_S3_BUCKET": "testdatabucket",
#             "JSON_OUTPUT_S3_KEY": "testdatakey",
#         },
#     )
#     mocker.patch("sys.argv", [""])
#     events_enclave_processor.main()

#     s3_stubber.assert_no_pending_responses()
#     sqs_stubber.assert_no_pending_responses()


# def test_missing_config(mocker):
#     mocker.patch("sys.argv", [""])
#     with pytest.raises(common.ProcessorException):
#         events_enclave_processor.main()
