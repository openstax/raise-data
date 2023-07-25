from raise_data.loaders import moodle_loader
import json
import boto3
import botocore.stub


def test_load_moodle_data(mocker):
    s3_client = boto3.client("s3")
    sqs_client = boto3.client("sqs", region_name="endor")
    s3_stubber = botocore.stub.Stubber(s3_client)
    sqs_stubber = botocore.stub.Stubber(sqs_client)

    list_objects_response = {
        "Contents": [
            {
                "Key": "course/term/moodle/type/1.json"
            },
            {
                "Key": "course/term/moodle/type/2.json"
            },
            {
                "Key": "topics/term/moodle/type/unexpected.txt"
            }
        ]
    }

    list_object_versions_1_response = {
        "Versions": [
            {
                'VersionId': 'v1'
            },
            {
                'VersionId': 'v2'
            }
        ]
    }

    list_object_versions_2_response = {
        "Versions": [
            {
                'VersionId': 'v1'
            }
        ]
    }

    file_1_send_request_expect = {
        "Message": json.dumps({
            "Records": [{
                "eventName": "ObjectCreated:Put",
                "s3": {
                    "bucket": {
                        "name": "testbucket"
                    },
                    "object": {
                        "key": "course/term/moodle/type/1.json",
                        "versionId": "v1"
                    }
                }
            }]
        })
    }

    file_2_send_request_expect = {
        "Message": json.dumps({
            "Records": [{
                "eventName": "ObjectCreated:Put",
                "s3": {
                    "bucket": {
                        "name": "testbucket"
                    },
                    "object": {
                        "key": "course/term/moodle/type/1.json",
                        "versionId": "v2"
                    }
                }
            }]
        })
    }

    file_3_send_request_expect = {
        "Message": json.dumps({
            "Records": [{
                "eventName": "ObjectCreated:Put",
                "s3": {
                    "bucket": {
                        "name": "testbucket"
                    },
                    "object": {
                        "key": "course/term/moodle/type/2.json",
                        "versionId": "v1"
                    }
                }
            }]
        })
    }

    s3_stubber.add_response(
        "list_objects",
        list_objects_response,
        expected_params={
            "Bucket": "testbucket",
            "Prefix": "testprefix",
        }
    )

    s3_stubber.add_response(
        "list_object_versions",
        list_object_versions_1_response,
        expected_params={
            "Bucket": "testbucket",
            "Prefix": "course/term/moodle/type/1.json",
        }
    )

    s3_stubber.add_response(
        "list_object_versions",
        list_object_versions_2_response,
        expected_params={
            "Bucket": "testbucket",
            "Prefix": "course/term/moodle/type/2.json",
        }
    )

    sqs_stubber.add_response(
        "get_queue_url",
        {
            "QueueUrl": "https://testqueue"
        },
        expected_params={"QueueName": "testqueue"}
    )

    sqs_stubber.add_response(
        "send_message",
        {},
        expected_params={
            "QueueUrl": "https://testqueue",
            "MessageBody": json.dumps(file_1_send_request_expect)
        }
    )

    sqs_stubber.add_response(
        "send_message",
        {},
        expected_params={
            "QueueUrl": "https://testqueue",
            "MessageBody": json.dumps(file_2_send_request_expect)
        }
    )

    sqs_stubber.add_response(
        "send_message",
        {},
        expected_params={
            "QueueUrl": "https://testqueue",
            "MessageBody": json.dumps(file_3_send_request_expect)
        }
    )

    s3_stubber.activate()
    sqs_stubber.activate()
    mocker_map = {
        "s3": s3_client,
        "sqs": sqs_client
    }
    mocker.patch("boto3.client", lambda client: mocker_map[client])

    mocker.patch("sys.argv", ["", "testbucket", "testprefix", "testqueue"])
    moodle_loader.main()

    s3_stubber.assert_no_pending_responses()
    sqs_stubber.assert_no_pending_responses()


def test_load_moodle_data_latest_only(mocker):
    s3_client = boto3.client("s3")
    sqs_client = boto3.client("sqs", region_name="endor")
    s3_stubber = botocore.stub.Stubber(s3_client)
    sqs_stubber = botocore.stub.Stubber(sqs_client)

    list_objects_response = {
        "Contents": [
            {
                "Key": "course/term/moodle/type/1.json"
            }
        ]
    }

    list_object_versions_1_response = {
        "Versions": [
            {
                "VersionId": "v2",
                "IsLatest": True
            },
            {
                "VersionId": "v1",
                "IsLatest": False
            }
        ]
    }

    file_1_send_request_expect = {
        "Message": json.dumps({
            "Records": [{
                "eventName": "ObjectCreated:Put",
                "s3": {
                    "bucket": {
                        "name": "testbucket"
                    },
                    "object": {
                        "key": "course/term/moodle/type/1.json",
                        "versionId": "v2"
                    }
                }
            }]
        })
    }

    s3_stubber.add_response(
        "list_objects",
        list_objects_response,
        expected_params={
            "Bucket": "testbucket",
            "Prefix": "testprefix",
        }
    )

    s3_stubber.add_response(
        "list_object_versions",
        list_object_versions_1_response,
        expected_params={
            "Bucket": "testbucket",
            "Prefix": "course/term/moodle/type/1.json",
        }
    )

    sqs_stubber.add_response(
        "get_queue_url",
        {
            "QueueUrl": "https://testqueue"
        },
        expected_params={"QueueName": "testqueue"}
    )

    sqs_stubber.add_response(
        "send_message",
        {},
        expected_params={
            "QueueUrl": "https://testqueue",
            "MessageBody": json.dumps(file_1_send_request_expect)
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
        "sys.argv",
        ["", "--latest-only", "testbucket", "testprefix", "testqueue"]
    )
    moodle_loader.main()

    s3_stubber.assert_no_pending_responses()
    sqs_stubber.assert_no_pending_responses()
