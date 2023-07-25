from raise_data.processors import moodle_dashboard_processor
import boto3
import pytest
import botocore.stub
import os
import io
import json
from datetime import datetime, timezone, timedelta
from raise_data.dashboard.schema import Course, EventUserEnrollment, \
    CourseActivityStat, CourseQuizStat


@pytest.fixture(autouse=True)
def clear_database_tables():
    """This fixture is setup to clear tables before each test run in
    this file
    """
    with moodle_dashboard_processor.session_factory.begin() as session:
        session.query(Course).delete()
        session.query(EventUserEnrollment).delete()
        session.query(CourseActivityStat).delete()
        session.query(CourseQuizStat).delete()


def test_process_users_data(mocker):
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
                    "key": "alg1/term/moodle/users/1.json",
                    "versionId": "testeventversionid"
                }
            }
        }]
    }

    mock_sns_data = {
        "Message": json.dumps(mock_s3_notification_data)
    }

    data_timestamp_utc = datetime(2022, 1, 1, 3, 0, 0, tzinfo=timezone.utc)
    data_timestamp_minus_1h = data_timestamp_utc - timedelta(hours=1)
    data_timestamp_minus_48h = data_timestamp_utc - timedelta(hours=48)
    data_timestamp_minus_10d = data_timestamp_utc - timedelta(days=10)

    mock_users_json = [
        {
            "enrolledcourses": [{
                "id": 1,
                "fullname": "Course full name"
            }],
            "roles": [{
                "shortname": "student"
            }],
            "lastcourseaccess": data_timestamp_minus_1h.timestamp(),
            "uuid": "5abd26c7-09ea-4b26-a35d-76cefef95cdc"
        },
        {
            "enrolledcourses": [{
                "id": 1,
                "fullname": "Course full name"
            }],
            "roles": [{
                "shortname": "student"
            }],
            "lastcourseaccess": data_timestamp_minus_48h.timestamp()
        },
        {
            "enrolledcourses": [{
                "id": 1,
                "fullname": "Course full name"
            }],
            "roles": [{
                "shortname": "teacher"
            }],
            "lastcourseaccess": data_timestamp_minus_10d.timestamp(),
            "uuid": "ea0e6385-01b7-43c8-a264-4a2f1ce96181"
        }
    ]

    # Setting up the sequence of stubs to be expected twice for multiple
    # invocations
    for _ in range(2):
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
                "Body": io.StringIO(json.dumps(mock_users_json)),
                "LastModified": data_timestamp_utc
            },
            expected_params={
                "Bucket": "testeventbucket",
                "Key": "alg1/term/moodle/users/1.json",
                "VersionId": "testeventversionid"
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
            **os.environ,
            **{
                "SQS_QUEUE": "testqueue",
                "POLL_INTERVAL_MINS": "1",
                "DATA_TYPE": "users"
            }
        }
    )
    mocker.patch("sys.argv", [""])
    moodle_dashboard_processor.main()

    with moodle_dashboard_processor.session_factory.begin() as session:
        courses = session.query(Course).all()
        enrollments = session.query(EventUserEnrollment).all()
        course_stats = session.query(CourseActivityStat).all()

        assert len(courses) == 1
        assert courses[0].name == "Course full name"
        assert courses[0].term == "term"
        assert courses[0].id == 1

        assert len(enrollments) == 2
        assert enrollments[0].role == "student"
        assert enrollments[0].user_uuid_md5 == \
            "a22d192fa5c34186186770b05e2dc327"
        assert enrollments[0].course_id == 1
        assert enrollments[1].role == "teacher"
        assert enrollments[1].user_uuid_md5 == \
            "ee4b98f73702ed8d756745db6a48235c"
        assert enrollments[1].course_id == 1

        assert len(course_stats) == 1
        assert course_stats[0].date == datetime(2022, 1, 1).date()
        assert course_stats[0].enrolled_students == 2
        assert course_stats[0].weekly_active_users == 2
        assert course_stats[0].daily_active_users == 1

    # Run a second pass with the same data to be sure we process properly

    mocker.patch("sys.argv", [""])
    moodle_dashboard_processor.main()

    with moodle_dashboard_processor.session_factory.begin() as session:
        courses = session.query(Course).all()
        enrollments = session.query(EventUserEnrollment).all()
        course_stats = session.query(CourseActivityStat).all()

        assert len(courses) == 1
        assert len(enrollments) == 2
        assert len(course_stats) == 1

    s3_stubber.assert_no_pending_responses()
    sqs_stubber.assert_no_pending_responses()


def test_process_grades_data(mocker):
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
                    "key": "alg1/term/moodle/grades/1.json",
                    "versionId": "testeventversionid"
                }
            }
        }]
    }

    mock_sns_data = {
        "Message": json.dumps(mock_s3_notification_data)
    }

    data_timestamp_utc = datetime(2022, 1, 1, 3, 0, 0, tzinfo=timezone.utc)
    data_timestamp_minus_1h = data_timestamp_utc - timedelta(hours=1)
    data_timestamp_minus_2h = data_timestamp_utc - timedelta(hours=2)
    data_timestamp_minus_48h = data_timestamp_utc - timedelta(hours=48)
    data_timestamp_minus_46h = data_timestamp_utc - timedelta(hours=46)

    mock_grades_json_1 = {
        "quizzes": [
            {
                "id": 1,
                "name": "Quiz 1"
            },
            {
                "id": 2,
                "name": "Quiz 2"
            }
        ],
        "attempts": {
            "10": {
                "1": {
                    "summaries": [
                        {
                            "quiz": 1,
                            "attempt": 1,
                            "timefinish": data_timestamp_minus_2h.timestamp()
                        },
                        {
                            "quiz": 1,
                            "attempt": 2,
                            "timefinish": data_timestamp_minus_1h.timestamp()
                        }
                    ]
                }
            },
            "11": {
                "2": {
                    "summaries": [
                        {
                            "quiz": 2,
                            "attempt": 1,
                            "timefinish": data_timestamp_minus_48h.timestamp()
                        }
                    ]
                }
            }
        }
    }

    def setup_sqs_stubs():
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

    setup_sqs_stubs()
    s3_stubber.add_response(
        "get_object",
        {
            "Body": io.StringIO(json.dumps(mock_grades_json_1)),
            "LastModified": data_timestamp_utc
        },
        expected_params={
            "Bucket": "testeventbucket",
            "Key": "alg1/term/moodle/grades/1.json",
            "VersionId": "testeventversionid"
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
            **os.environ,
            **{
                "SQS_QUEUE": "testqueue",
                "POLL_INTERVAL_MINS": "1",
                "DATA_TYPE": "grades"
            }
        }
    )
    mocker.patch("sys.argv", [""])
    moodle_dashboard_processor.main()

    with moodle_dashboard_processor.session_factory.begin() as session:
        quiz_stats = session.query(CourseQuizStat).all()

        assert len(quiz_stats) == 2
        assert quiz_stats[0].date == datetime(2022, 1, 1).date()
        assert quiz_stats[0].quiz_name == "Quiz 1"
        assert quiz_stats[0].quiz_attempts == 2
        assert quiz_stats[1].date == datetime(2021, 12, 30).date()
        assert quiz_stats[1].quiz_name == "Quiz 2"
        assert quiz_stats[1].quiz_attempts == 1

    # Run a second pass with slightly different data to confirm the
    # upsert works

    mock_grades_json_2 = {
        "quizzes": [
            {
                "id": 1,
                "name": "Quiz 1"
            },
            {
                "id": 2,
                "name": "Quiz 2"
            }
        ],
        "attempts": {
            "10": {
                "1": {
                    "summaries": [
                        {
                            "quiz": 1,
                            "attempt": 1,
                            "timefinish": data_timestamp_minus_2h.timestamp()
                        },
                        {
                            "quiz": 1,
                            "attempt": 2,
                            "timefinish": data_timestamp_minus_1h.timestamp()
                        }
                    ]
                }
            },
            "11": {
                "2": {
                    "summaries": [
                        {
                            "quiz": 2,
                            "attempt": 1,
                            "timefinish": data_timestamp_minus_48h.timestamp()
                        },
                        {
                            "quiz": 2,
                            "attempt": 2,
                            "timefinish": data_timestamp_minus_46h.timestamp()
                        }
                    ]
                }
            }
        }
    }

    setup_sqs_stubs()
    s3_stubber.add_response(
        "get_object",
        {
            "Body": io.StringIO(json.dumps(mock_grades_json_2)),
            "LastModified": data_timestamp_utc
        },
        expected_params={
            "Bucket": "testeventbucket",
            "Key": "alg1/term/moodle/grades/1.json",
            "VersionId": "testeventversionid"
        }
    )

    mocker.patch("sys.argv", [""])
    moodle_dashboard_processor.main()

    with moodle_dashboard_processor.session_factory.begin() as session:
        quiz_stats = session.query(CourseQuizStat).all()

        assert len(quiz_stats) == 2
        assert quiz_stats[0].date == datetime(2022, 1, 1).date()
        assert quiz_stats[0].quiz_name == "Quiz 1"
        assert quiz_stats[0].quiz_attempts == 2
        assert quiz_stats[1].date == datetime(2021, 12, 30).date()
        assert quiz_stats[1].quiz_name == "Quiz 2"
        assert quiz_stats[1].quiz_attempts == 2

    s3_stubber.assert_no_pending_responses()
    sqs_stubber.assert_no_pending_responses()
