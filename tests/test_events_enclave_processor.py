from raise_data.processors import events_enclave_processor
import json
import io
import boto3
import botocore.stub
from fastavro import writer, parse_schema


def test_process_single_message_new_data(mocker):
    s3_client = boto3.client("s3")
    sqs_client = boto3.client("sqs", region_name="tatooine")
    s3_stubber = botocore.stub.Stubber(s3_client)
    sqs_stubber = botocore.stub.Stubber(sqs_client)

    mock_s3_notification_data = {
        "Records": [{
            "eventName": "ObjectCreated:Put",
            "s3": {
                "bucket": {
                    "name": "testeventbucket"
                },
                "object": {
                    "key": "testeventkey"
                }
            }
        }]
    }
    mock_sns_data = {
        "Message": json.dumps(mock_s3_notification_data)
    }
    mock_avro_schema = {
        "namespace": "test",
        "type": "record",
        "name": "Event",
        "fields": [
            {"name": "course_id", "type": "long"},
            {"name": "source_scheme", "type": "string"},
            {"name": "source_host", "type": "string"},
            {"name": "source_path", "type": "string"},
            {"name": "source_query", "type": "string"},
        ]
    }
    parsed_schema = parse_schema(mock_avro_schema)
    mock_avro_data = [
        {
            "course_id": 1,
            "source_scheme": "scheme",
            "source_host": "host",
            "source_path": "path",
            "source_query": "query"
        },
        {
            "course_id": 2,
            "source_scheme": "scheme",
            "source_host": "host",
            "source_path": "path",
            "source_query": "query"
        }
    ]
    mock_avro_bytes = io.BytesIO()
    writer(mock_avro_bytes, parsed_schema, mock_avro_data, codec="snappy")
    mock_avro_bytes.seek(0)
    expected_put_data = {
            "data_sources": [
                "s3://testeventbucket/testeventkey"
            ],
            "data": [
                {"course_id": 1},
                {"course_id": 2}
            ]
    }

    sqs_stubber.add_response(
        "get_queue_url",
        {
            "QueueUrl": "https://testqueue"
        },
        expected_params={"QueueName": "testqueue"}
    )
    sqs_stubber.add_response(
        "receive_message",
        {
            "Messages": [{
                "ReceiptHandle": "message1",
                "Body": json.dumps(mock_sns_data)
            }]
        },
        expected_params={
            "QueueUrl": "https://testqueue",
            "MaxNumberOfMessages": 10,
            "WaitTimeSeconds": 20
        }
    )
    sqs_stubber.add_response(
        "delete_message",
        {},
        expected_params={
            "QueueUrl": "https://testqueue",
            "ReceiptHandle": "message1"
        }
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
        {
            "Body": mock_avro_bytes
        },
        expected_params={
            "Bucket": "testeventbucket",
            "Key": "testeventkey",
        }
    )
    s3_stubber.add_response(
        "put_object",
        {},
        {
            "Bucket": "testdatabucket",
            "Body": json.dumps(expected_put_data).encode("utf-8"),
            "Key": "testdatakey"
        }
    )

    s3_stubber.activate()
    sqs_stubber.activate()
    mocker_map = {
        "s3": s3_client,
        "sqs": sqs_client
    }
    mocker.patch("boto3.client", lambda client: mocker_map[client])
    mocker.patch(
        "os.environ",
        {
            "SQS_QUEUE": "testqueue",
            "POLL_INTERVAL_MINS": "1",
            "JSON_OUTPUT_S3_BUCKET": "testdatabucket",
            "JSON_OUTPUT_S3_KEY": "testdatakey"
        }
    )
    mocker.patch("sys.argv", [""])
    events_enclave_processor.main()

    s3_stubber.assert_no_pending_responses()
    sqs_stubber.assert_no_pending_responses()


def test_process_single_message_duplicate_data(mocker):
    s3_client = boto3.client("s3")
    sqs_client = boto3.client("sqs", region_name="tatooine")
    s3_stubber = botocore.stub.Stubber(s3_client)
    sqs_stubber = botocore.stub.Stubber(sqs_client)

    mock_s3_notification_data = {
        "Records": [{
            "eventName": "ObjectCreated:Put",
            "s3": {
                "bucket": {
                    "name": "testeventbucket"
                },
                "object": {
                    "key": "testeventkey"
                }
            }
        }]
    }
    mock_sns_data = {
        "Message": json.dumps(mock_s3_notification_data)
    }
    mock_event_data = {
        "data_sources": [
            "s3://testeventbucket/testeventkey"
        ],
        "data": [
            {"course_id": 1},
            {"course_id": 2}
        ]
    }

    expected_put_data = {
            "data_sources": [
                "s3://testeventbucket/testeventkey"
            ],
            "data": [
                {"course_id": 1},
                {"course_id": 2}
            ]
    }

    sqs_stubber.add_response(
        "get_queue_url",
        {
            "QueueUrl": "https://testqueue"
        },
        expected_params={"QueueName": "testqueue"}
    )
    sqs_stubber.add_response(
        "receive_message",
        {
            "Messages": [{
                "ReceiptHandle": "message1",
                "Body": json.dumps(mock_sns_data)
            }]
        },
        expected_params={
            "QueueUrl": "https://testqueue",
            "MaxNumberOfMessages": 10,
            "WaitTimeSeconds": 20
        }
    )
    sqs_stubber.add_response(
        "delete_message",
        {},
        expected_params={
            "QueueUrl": "https://testqueue",
            "ReceiptHandle": "message1"
        }
    )

    s3_stubber.add_response(
        "get_object",
        {
            "Body": io.BytesIO(json.dumps(mock_event_data).encode('utf-8'))
        },
        expected_params={
            "Bucket": "testdatabucket",
            "Key": "testdatakey",
        }
    )
    s3_stubber.add_response(
        "put_object",
        {},
        {
            "Bucket": "testdatabucket",
            "Body": json.dumps(expected_put_data).encode("utf-8"),
            "Key": "testdatakey"
        }
    )

    s3_stubber.activate()
    sqs_stubber.activate()
    mocker_map = {
        "s3": s3_client,
        "sqs": sqs_client
    }
    mocker.patch("boto3.client", lambda client: mocker_map[client])
    mocker.patch(
        "os.environ",
        {
            "SQS_QUEUE": "testqueue",
            "POLL_INTERVAL_MINS": "1",
            "JSON_OUTPUT_S3_BUCKET": "testdatabucket",
            "JSON_OUTPUT_S3_KEY": "testdatakey"
        }
    )
    mocker.patch("sys.argv", [""])
    events_enclave_processor.main()

    s3_stubber.assert_no_pending_responses()
    sqs_stubber.assert_no_pending_responses()


def test_process_single_message_bad_event(mocker):
    s3_client = boto3.client("s3")
    sqs_client = boto3.client("sqs", region_name="tatooine")
    s3_stubber = botocore.stub.Stubber(s3_client)
    sqs_stubber = botocore.stub.Stubber(sqs_client)

    mock_s3_notification_data = {
        "Records": [{
            "eventName": "ObjectSomething",
            "s3": {
                "bucket": {
                    "name": "testeventbucket"
                },
                "object": {
                    "key": "testeventkey"
                }
            }
        }]
    }
    mock_sns_data = {
        "Message": json.dumps(mock_s3_notification_data)
    }

    sqs_stubber.add_response(
        "get_queue_url",
        {
            "QueueUrl": "https://testqueue"
        },
        expected_params={"QueueName": "testqueue"}
    )
    sqs_stubber.add_response(
        "receive_message",
        {
            "Messages": [{
                "ReceiptHandle": "message1",
                "Body": json.dumps(mock_sns_data)
            }]
        },
        expected_params={
            "QueueUrl": "https://testqueue",
            "MaxNumberOfMessages": 10,
            "WaitTimeSeconds": 20
        }
    )

    s3_stubber.add_client_error(
        "get_object",
        service_error_code="NoSuchKey",
        expected_params={
            "Bucket": "testdatabucket",
            "Key": "testdatakey",
        },
    )

    s3_stubber.activate()
    sqs_stubber.activate()
    mocker_map = {
        "s3": s3_client,
        "sqs": sqs_client
    }
    mocker.patch("boto3.client", lambda client: mocker_map[client])
    mocker.patch(
        "os.environ",
        {
            "SQS_QUEUE": "testqueue",
            "POLL_INTERVAL_MINS": "1",
            "JSON_OUTPUT_S3_BUCKET": "testdatabucket",
            "JSON_OUTPUT_S3_KEY": "testdatakey"
        }
    )
    mocker.patch("sys.argv", [""])
    events_enclave_processor.main()

    s3_stubber.assert_no_pending_responses()
    sqs_stubber.assert_no_pending_responses()
