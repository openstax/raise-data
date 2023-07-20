import os
import argparse
import boto3
import json
import logging
from datetime import datetime, timezone, timedelta
from urllib.parse import unquote
import hashlib
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import sessionmaker
from .common import ProcessorException, processor_runner, \
    commit_ignoring_unique_violations
from raise_data.dashboard.schema import Course, EventUserEnrollment, \
    CourseActivityStat, CourseQuizStat


logging.basicConfig(level=logging.INFO)

# We setup the sqlalchemy resources at global scope and so read some expected
# environment variables here. If they end up being missing, we'll fail later
# anyways.
pg_server = os.getenv('POSTGRES_SERVER', '')
pg_db = os.getenv('POSTGRES_DB', '')
pg_user = os.getenv('POSTGRES_USER', '')
pg_password = os.getenv('POSTGRES_PASSWORD', '')
sqlalchemy_url = f"postgresql://{pg_user}:{pg_password}@{pg_server}/{pg_db}"

engine = create_engine(sqlalchemy_url)
session_factory = sessionmaker(engine)


def get_config():
    try:
        return {
            "consumer_queue": os.environ["SQS_QUEUE"],
            "poll_interval_mins": int(os.environ["POLL_INTERVAL_MINS"]),
            "data_type": os.environ["DATA_TYPE"],
            "postgres_server": os.environ["POSTGRES_SERVER"],
            "postgres_db": os.environ["POSTGRES_DB"],
            "postgres_user": os.environ["POSTGRES_USER"],
            "postgres_password": os.environ["POSTGRES_PASSWORD"]
        }
    except KeyError as e:
        raise ProcessorException(f"Missing expected environment variable: {e}")


def process_moodle_users_data(
    course_id, course_term, users_data, data_timestamp_utc
):
    def get_course_data():
        # Parse out course name. We should be able to find the target course in
        # any user, so the first is as good as any
        enrolled_courses = users_data[0]["enrolledcourses"]
        for course in enrolled_courses:
            if str(course["id"]) == course_id:
                return {
                    "id": course_id,
                    "name": course["fullname"],
                    "term": course_term
                }

        raise ProcessorException(
            f"Could not find course name for {course_id} in users data"
        )

    def count_enrolled_students():
        enrolled_students = 0
        for user in users_data:
            user_role = user["roles"][0]["shortname"]
            if user_role == "student":
                enrolled_students += 1
        return enrolled_students

    def count_active_users():
        weekly_active_users = 0
        daily_active_users = 0
        for user in users_data:
            # This is a unix timestamp or 0
            lastaccess = user["lastcourseaccess"]
            lastaccess_utc = datetime.fromtimestamp(lastaccess, timezone.utc)

            access_time_delta = data_timestamp_utc - lastaccess_utc
            if access_time_delta < timedelta(days=7):
                weekly_active_users += 1
            if access_time_delta < timedelta(days=1):
                daily_active_users += 1
        return {
            "weekly_active_users": weekly_active_users,
            "daily_active_users": daily_active_users
        }

    def get_event_user_enrollments():
        res = []
        for user in users_data:
            # Old JSON files may not have a UUID field, and in new ones it
            # will be null if a user has not generated events
            maybe_user_uuid = user.get("uuid")
            if maybe_user_uuid is not None:
                role = user["roles"][0]["shortname"]
                user_uuid_md5 = hashlib.md5(
                    maybe_user_uuid.encode("utf-8")
                ).hexdigest()
                res.append({
                    "course_id": course_id,
                    "role": role,
                    "user_uuid_md5": user_uuid_md5
                })

        return res

    course_data = get_course_data()
    enrolled_students = count_enrolled_students()
    active_users = count_active_users()
    course_activity_stats = {
        "course_id": course_id,
        "date": data_timestamp_utc.date(),
        "enrolled_students": enrolled_students,
        "weekly_active_users": active_users["weekly_active_users"],
        "daily_active_users": active_users["daily_active_users"]
    }
    event_user_enrollments = get_event_user_enrollments()

    with session_factory() as session:
        session.add(CourseActivityStat(**course_activity_stats))
        commit_ignoring_unique_violations(session)
        session.add(Course(**course_data))
        commit_ignoring_unique_violations(session)

        # Since the event user enrollment rows are cumulative, we'll query
        # existing course entries first so the steady-state has no new inserts
        # being attempted
        existing_enrollment_users = session.scalars(
            select(EventUserEnrollment.user_uuid_md5).filter_by(
                course_id=course_id
            )
        ).all()

        for item in event_user_enrollments:
            if item["user_uuid_md5"] not in existing_enrollment_users:
                session.add(EventUserEnrollment(**item))
                commit_ignoring_unique_violations(session)


def process_moodle_grades_data(course_id, grades_data):
    attempts_by_date = {}

    # This check is here because legacy grades JSON files don't have this data
    maybe_attempts_data = grades_data.get("attempts")
    quiz_data = grades_data.get("quizzes")
    if maybe_attempts_data is None or quiz_data is None:
        return

    quiz_name_by_id = {}
    for quiz in quiz_data:
        quiz_name_by_id[quiz["id"]] = quiz["name"]

    for _, user_data in maybe_attempts_data.items():
        for _, attempt_data in user_data.items():
            for attempt in attempt_data["summaries"]:
                quiz_name = quiz_name_by_id[attempt["quiz"]]
                date_utc = datetime.fromtimestamp(
                    attempt["timefinish"],
                    timezone.utc
                ).date()
                attempts_by_quiz = attempts_by_date.setdefault(date_utc, {})
                attempts_by_quiz_count = attempts_by_quiz.get(quiz_name, 0)
                attempts_by_quiz[quiz_name] = attempts_by_quiz_count + 1

    results = []

    # We're going to attempt an "upsert" for every item. If this ends up
    # being a performance issue, we can filter to only recent dates relative
    # to data_timestamp here.
    for date, attempts_by_quiz in attempts_by_date.items():
        for quiz_name, count in attempts_by_quiz.items():
            results.append({
                "course_id": course_id,
                "date": date,
                "quiz_name": quiz_name,
                "quiz_attempts": count
            })

    with session_factory.begin() as session:
        for item in results:
            insert_stmt = insert(CourseQuizStat).values(**item)
            do_update_stmt = insert_stmt.on_conflict_do_update(
                index_elements=['course_id', 'date', 'quiz_name'],
                set_=dict(
                    quiz_attempts=item["quiz_attempts"],
                    updated_at=datetime.utcnow()
                )
            )
            session.execute(do_update_stmt)


def process_s3_notification(s3_client, s3_notification, data_type):
    for record in s3_notification["Records"]:
        event_name = record["eventName"]

        if not event_name.startswith("ObjectCreated:"):
            raise ProcessorException(f"Unexpected S3 event: {event_name}")

        s3_data = record["s3"]
        bucket = s3_data["bucket"]["name"]
        object_key = unquote(s3_data["object"]["key"])
        object_version_id = s3_data["object"]["versionId"]

        # Parse course_id out of the filename convention since it isn't
        # consistently contained in all data files
        course_id = object_key.split("/")[-1].split(".json")[0]
        course_term = object_key.split('/moodle')[0].split('/')[-1]

        data = s3_client.get_object(
            Bucket=bucket,
            Key=object_key,
            VersionId=object_version_id
        )
        data_contents = data["Body"].read()
        json_data = json.loads(data_contents)

        # This should be a tz aware timestamp that is already UTC, but
        # we'll convert just to be sure
        data_timestamp = data["LastModified"]
        data_timestamp_utc = data_timestamp.astimezone(timezone.utc)

        if data_type == 'users':
            process_moodle_users_data(
                course_id,
                course_term,
                json_data,
                data_timestamp_utc
            )
        elif data_type == 'grades':
            process_moodle_grades_data(
                course_id,
                json_data
            )
        else:
            raise ProcessorException(f"Unexpected data type {data_type}")


def get_sqs_message_processor(s3_client, data_type):

    def inner(sqs_message):
        sns_data = json.loads(sqs_message["Body"])
        s3_notification = json.loads(sns_data["Message"])

        process_s3_notification(s3_client, s3_notification, data_type)

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
        data_type=config["data_type"]
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
