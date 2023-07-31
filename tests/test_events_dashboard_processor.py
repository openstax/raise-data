from raise_data.processors import events_dashboard_processor, common
import pytest
import json
import io
import os
import boto3
import botocore.stub
from fastavro import writer, parse_schema
from datetime import datetime
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


def test_process_content_loaded_event_data(mocker):
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
    first_data_timestamp_utc = datetime(2022, 12, 17, 19, 40, 33)
    second_data_timestamp_utc = datetime(2022, 12, 17, 19, 45, 38)

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
            {"name": "timestamp", "type": "int"},
            {"name": "content_id", "type": "string"},
            {"name": "variant", "type": "string"},
        ],
    }
    parsed_schema = parse_schema(mock_avro_schema)
    mock_avro_data = [
        {
            "user_uuid": "629f56a3-4ddc-4603-a860-89bdcdc04554",
            "course_id": 1,
            "impression_id": "0ee17feb-1883-4889-9cd9-81ee541d28a9",
            "source_scheme": "scheme",
            "source_host": "host",
            "source_path": "path",
            "source_query": "query",
            "timestamp": 1671306033221,
            "content_id": "c16c2d65-b03d-4769-bd57-aca27af11fc0",
            "variant": "main",
        },
        {
            "user_uuid": "c7c2a07f-bf25-40e0-b497-4823579aea10",
            "course_id": 2,
            "impression_id": "cca39565-231f-444a-b08a-2423b8411478",
            "source_scheme": "scheme",
            "source_host": "host",
            "source_path": "path",
            "source_query": "query",
            "timestamp": 1671306338950,
            "content_id": "c64e158e-7168-4438-bd16-565adeeb87fd",
            "variant": "main",
        },
    ]
    mock_avro_bytes = io.BytesIO()
    writer(mock_avro_bytes, parsed_schema, mock_avro_data, codec="snappy")
    mock_avro_bytes.seek(0)

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
    s3_stubber.add_response(
        "get_object",
        {"Body": mock_avro_bytes},
        expected_params={
            "Bucket": "testeventbucket",
            "Key": "testeventkey",
        },
    )

    s3_stubber.activate()
    sqs_stubber.activate()
    mocker_map = {"s3": s3_client, "sqs": sqs_client}
    mocker.patch("boto3.client", lambda client: mocker_map[client])
    mocker.patch(
        "os.environ",
        {
            **os.environ,
            **{
                "SQS_QUEUE": "testqueue",
                "POLL_INTERVAL_MINS": "1",
                "EVENT_TYPE": "content_loaded_event",
            },
        },
    )
    mocker.patch("sys.argv", [""])
    events_dashboard_processor.main()

    with events_dashboard_processor.session_factory.begin() as session:
        content_loaded_event = session.query(ContentLoadedEvent).all()

        assert (
            content_loaded_event[0].user_uuid_md5 == "380745a431c61d0b5747dd351fce7b2d"
        )
        assert content_loaded_event[0].course_id == 1
        assert (
            str(
                content_loaded_event[0].impression_id
            )  # without the string conversion the return value is UUID('string here')
            == "0ee17feb-1883-4889-9cd9-81ee541d28a9"
        )
        assert content_loaded_event[0].timestamp == first_data_timestamp_utc
        assert (
            str(content_loaded_event[0].content_id)
            == "c16c2d65-b03d-4769-bd57-aca27af11fc0"
        )
        assert content_loaded_event[0].variant == "main"
        assert (
            content_loaded_event[1].user_uuid_md5 == "a6f9ae229ed5ac799b8cf34065046b36"
        )
        assert content_loaded_event[1].course_id == 2
        assert (
            str(content_loaded_event[1].impression_id)
            == "cca39565-231f-444a-b08a-2423b8411478"
        )
        assert content_loaded_event[1].timestamp == second_data_timestamp_utc
        assert (
            str(content_loaded_event[1].content_id)
            == "c64e158e-7168-4438-bd16-565adeeb87fd"
        )
        assert content_loaded_event[1].variant == "main"

    s3_stubber.assert_no_pending_responses()
    sqs_stubber.assert_no_pending_responses()


def test_process_input_submitted_event_data(mocker):
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
    first_data_timestamp_utc = datetime(2022, 12, 17, 19, 40, 33)
    second_data_timestamp_utc = datetime(2022, 12, 17, 19, 45, 38)

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
            {"name": "response", "type": "string"},
            {"name": "timestamp", "type": "int"},
            {"name": "content_id", "type": "string"},
            {"name": "variant", "type": "string"},
            {"name": "input_content_id", "type": "string"},
        ],
    }
    parsed_schema = parse_schema(mock_avro_schema)
    mock_avro_data = [
        {
            "user_uuid": "629f56a3-4ddc-4603-a860-89bdcdc04554",
            "course_id": 1,
            "impression_id": "0ee17feb-1883-4889-9cd9-81ee541d28a9",
            "source_scheme": "scheme",
            "source_host": "host",
            "source_path": "path",
            "source_query": "query",
            "response": "response",
            "timestamp": 1671306033221,
            "content_id": "c16c2d65-b03d-4769-bd57-aca27af11fc0",
            "variant": "main",
            "input_content_id": "9faec566-623f-446c-9b58-11f1ae11aca1",
        },
        {
            "user_uuid": "c7c2a07f-bf25-40e0-b497-4823579aea10",
            "course_id": 2,
            "impression_id": "cca39565-231f-444a-b08a-2423b8411478",
            "source_scheme": "scheme",
            "source_host": "host",
            "source_path": "path",
            "source_query": "query",
            "response": "response",
            "timestamp": 1671306338950,
            "content_id": "c64e158e-7168-4438-bd16-565adeeb87fd",
            "variant": "main",
            "input_content_id": "a05abdf2-8792-4e8c-8a33-4d0950a1e20d",
        },
    ]
    mock_avro_bytes = io.BytesIO()
    writer(mock_avro_bytes, parsed_schema, mock_avro_data, codec="snappy")
    mock_avro_bytes.seek(0)

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
    s3_stubber.add_response(
        "get_object",
        {"Body": mock_avro_bytes},
        expected_params={
            "Bucket": "testeventbucket",
            "Key": "testeventkey",
        },
    )

    s3_stubber.activate()
    sqs_stubber.activate()
    mocker_map = {"s3": s3_client, "sqs": sqs_client}
    mocker.patch("boto3.client", lambda client: mocker_map[client])
    mocker.patch(
        "os.environ",
        {
            **os.environ,
            **{
                "SQS_QUEUE": "testqueue",
                "POLL_INTERVAL_MINS": "1",
                "EVENT_TYPE": "input_submitted_event",
            },
        },
    )
    mocker.patch("sys.argv", [""])
    events_dashboard_processor.main()

    with events_dashboard_processor.session_factory.begin() as session:
        input_submitted_event = session.query(InputSubmittedEvent).all()

        assert (
            input_submitted_event[0].user_uuid_md5 == "380745a431c61d0b5747dd351fce7b2d"
        )
        assert input_submitted_event[0].course_id == 1
        assert (
            str(
                input_submitted_event[0].impression_id
            )  # without the string conversion the return value is UUID('string here')
            == "0ee17feb-1883-4889-9cd9-81ee541d28a9"
        )
        assert input_submitted_event[0].timestamp == first_data_timestamp_utc
        assert (
            str(input_submitted_event[0].content_id)
            == "c16c2d65-b03d-4769-bd57-aca27af11fc0"
        )
        assert str(
            input_submitted_event[0].input_content_id
            == "9faec566-623f-446c-9b58-11f1ae11aca1"
        )
        assert input_submitted_event[0].variant == "main"
        assert (
            input_submitted_event[1].user_uuid_md5 == "a6f9ae229ed5ac799b8cf34065046b36"
        )
        assert input_submitted_event[1].course_id == 2
        assert (
            str(input_submitted_event[1].impression_id)
            == "cca39565-231f-444a-b08a-2423b8411478"
        )
        assert input_submitted_event[1].timestamp == second_data_timestamp_utc
        assert (
            str(input_submitted_event[1].content_id)
            == "c64e158e-7168-4438-bd16-565adeeb87fd"
        )
        assert str(
            input_submitted_event[1].input_content_id
            == "a05abdf2-8792-4e8c-8a33-4d0950a1e20d"
        )
        assert input_submitted_event[1].variant == "main"

    s3_stubber.assert_no_pending_responses()
    sqs_stubber.assert_no_pending_responses()


def test_process_pset_problem_attempted_event_data(mocker):
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
    first_data_timestamp_utc = datetime(2022, 12, 17, 19, 40, 33)
    second_data_timestamp_utc = datetime(2022, 12, 17, 19, 45, 38)

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
            {"name": "response", "type": "string"},
            {"name": "timestamp", "type": "int"},
            {"name": "content_id", "type": "string"},
            {"name": "variant", "type": "string"},
            {"name": "problem_type", "type": "string"},
            {"name": "correct", "type": "boolean"},
            {"name": "attempt", "type": "int"},
            {"name": "final_attempt", "type": "boolean"},
            {"name": "pset_content_id", "type": "string"},
            {"name": "pset_problem_content_id", "type": "string"},
        ],
    }
    parsed_schema = parse_schema(mock_avro_schema)
    mock_avro_data = [
        {
            "user_uuid": "5d102aa1-e0e3-4552-915c-6a8db26e1b63",
            "course_id": 1,
            "impression_id": "e666aa69-3ccf-420b-a53e-cbccc829f04d",
            "source_scheme": "scheme",
            "source_host": "host",
            "source_path": "path",
            "source_query": "query",
            "response": "response",
            "timestamp": 1671306033221,
            "content_id": "28363137-5337-40dd-a70d-ab54b6771119",
            "variant": "main",
            "problem_type": "dropdown",
            "correct": False,
            "attempt": 1,
            "final_attempt": False,
            "pset_content_id": "e3ab7105-f1dd-4e70-9a89-01793081038b",
            "pset_problem_content_id": "ed4596cc-70ed-4985-ba75-5938b765742d",
        },
        {
            "user_uuid": "c7c2a07f-bf25-40e0-b497-4823579aea10",
            "course_id": 2,
            "impression_id": "cca39565-231f-444a-b08a-2423b8411478",
            "source_scheme": "scheme",
            "source_host": "host",
            "source_path": "path",
            "source_query": "query",
            "response": "response",
            "timestamp": 1671306338950,
            "content_id": "c64e158e-7168-4438-bd16-565adeeb87fd",
            "variant": "main",
            "problem_type": "dropdown",
            "correct": True,
            "attempt": 2,
            "final_attempt": True,
            "pset_content_id": "d3ab7105-f1dd-4e70-9a89-01793081038b",
            "pset_problem_content_id": "fd4596cc-70ed-4985-ba75-5938b765742d",
        },
    ]
    mock_avro_bytes = io.BytesIO()
    writer(mock_avro_bytes, parsed_schema, mock_avro_data, codec="snappy")
    mock_avro_bytes.seek(0)

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
    s3_stubber.add_response(
        "get_object",
        {"Body": mock_avro_bytes},
        expected_params={
            "Bucket": "testeventbucket",
            "Key": "testeventkey",
        },
    )

    s3_stubber.activate()
    sqs_stubber.activate()
    mocker_map = {"s3": s3_client, "sqs": sqs_client}
    mocker.patch("boto3.client", lambda client: mocker_map[client])
    mocker.patch(
        "os.environ",
        {
            **os.environ,
            **{
                "SQS_QUEUE": "testqueue",
                "POLL_INTERVAL_MINS": "1",
                "EVENT_TYPE": "pset_problem_attempted_event",
            },
        },
    )
    mocker.patch("sys.argv", [""])
    events_dashboard_processor.main()

    with events_dashboard_processor.session_factory.begin() as session:
        pset_problem_attempted_event = session.query(PsetProblemAttemptedEvent).all()

        assert (
            pset_problem_attempted_event[0].user_uuid_md5
            == "060a293298d8809a908bd3daf34ba712"
        )
        assert pset_problem_attempted_event[0].course_id == 1
        assert (
            str(
                pset_problem_attempted_event[0].impression_id
            )  # without the string conversion the return value is UUID('string here')
            == "e666aa69-3ccf-420b-a53e-cbccc829f04d"
        )
        assert pset_problem_attempted_event[0].timestamp == first_data_timestamp_utc
        assert (
            str(pset_problem_attempted_event[0].content_id)
            == "28363137-5337-40dd-a70d-ab54b6771119"
        )
        assert pset_problem_attempted_event[0].variant == "main"
        assert pset_problem_attempted_event[0].problem_type == "dropdown"
        assert pset_problem_attempted_event[0].correct == False
        assert pset_problem_attempted_event[0].attempt == 1
        assert pset_problem_attempted_event[0].final_attempt == False
        assert (
            str(pset_problem_attempted_event[0].pset_content_id)
            == "e3ab7105-f1dd-4e70-9a89-01793081038b"
        )
        assert (
            str(pset_problem_attempted_event[0].pset_problem_content_id)
            == "ed4596cc-70ed-4985-ba75-5938b765742d"
        )
        assert (
            pset_problem_attempted_event[1].user_uuid_md5
            == "a6f9ae229ed5ac799b8cf34065046b36"
        )
        assert pset_problem_attempted_event[1].course_id == 2
        assert (
            str(pset_problem_attempted_event[1].impression_id)
            == "cca39565-231f-444a-b08a-2423b8411478"
        )
        assert pset_problem_attempted_event[1].timestamp == second_data_timestamp_utc
        assert (
            str(pset_problem_attempted_event[1].content_id)
            == "c64e158e-7168-4438-bd16-565adeeb87fd"
        )
        assert pset_problem_attempted_event[1].variant == "main"
        assert pset_problem_attempted_event[1].problem_type == "dropdown"
        assert pset_problem_attempted_event[1].correct == True
        assert pset_problem_attempted_event[1].attempt == 2
        assert pset_problem_attempted_event[1].final_attempt == True
        assert (
            str(pset_problem_attempted_event[1].pset_content_id)
            == "d3ab7105-f1dd-4e70-9a89-01793081038b"
        )
        assert (
            str(pset_problem_attempted_event[1].pset_problem_content_id)
            == "fd4596cc-70ed-4985-ba75-5938b765742d"
        )

    s3_stubber.assert_no_pending_responses()
    sqs_stubber.assert_no_pending_responses()


def test_missing_config(mocker):
    mocker.patch("sys.argv", [""])
    with pytest.raises(common.ProcessorException):
        events_dashboard_processor.main()
