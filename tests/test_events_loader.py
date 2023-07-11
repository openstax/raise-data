from raise_data.loaders import events_loader
import json
import boto3
import botocore.stub


def test_process_single_message_new_data(mocker):
    s3_client = boto3.client("s3")
    sqs_client = boto3.client("sqs", region_name="endor")
    s3_stubber = botocore.stub.Stubber(s3_client)
    sqs_stubber = botocore.stub.Stubber(sqs_client)

    list_objects_response = {
        "Contents": [
            {
                "Key": "topics/1.avro"
            },
            {
                "Key": "topics/2.avro"
            },
            {
                "Key": "topics/unexpected.json"
            }
        ]
    }

    file_1_send_request_expect = {
        "Message": json.dumps({
            "Records": [{
                "eventName": "ObjectCreated:Post",
                "s3": {
                    "bucket": {
                        "name": "testbucket"
                    },
                    "object": {
                        "key": "topics/1.avro"
                    }
                }
            }]
        })
    }

    file_2_send_request_expect = {
        "Message": json.dumps({
            "Records": [{
                "eventName": "ObjectCreated:Post",
                "s3": {
                    "bucket": {
                        "name": "testbucket"
                    },
                    "object": {
                        "key": "topics/2.avro"
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

    s3_stubber.activate()
    sqs_stubber.activate()
    mocker_map = {
        "s3": s3_client,
        "sqs": sqs_client
    }
    mocker.patch("boto3.client", lambda client: mocker_map[client])

    mocker.patch("sys.argv", ["", "testbucket", "testprefix", "testqueue"])
    events_loader.main()

    s3_stubber.assert_no_pending_responses()
    sqs_stubber.assert_no_pending_responses()
