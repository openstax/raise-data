import argparse
import boto3
import csv
import os
from io import StringIO
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import sessionmaker
from raise_data.dashboard.schema import (
     CourseContent
)

pg_server = os.getenv("POSTGRES_SERVER", "")
pg_db = os.getenv("POSTGRES_DB", "")
pg_user = os.getenv("POSTGRES_USER", "")
pg_password = os.getenv("POSTGRES_PASSWORD", "")
sqlalchemy_url = f"postgresql://{pg_user}:{pg_password}@{pg_server}/{pg_db}"

engine = create_engine(sqlalchemy_url)
session_factory = sessionmaker(engine)


def main():
    parser = argparse.ArgumentParser(
        description="Load course_content data to database"
        )
    parser.add_argument(
        's3_bucket',
        type=str,
        help='S3 bucket name'
    )
    parser.add_argument(
        's3_prefix',
        type=str,
        help='S3 prefix for files'
    )

    args = parser.parse_args()
    s3_bucket = args.s3_bucket
    s3_prefix = args.s3_prefix

    term = s3_prefix.split('/')[1]

    s3_client = boto3.client('s3')
    course_content_stream = s3_client.get_object(
        Bucket=s3_bucket,
        Key=s3_prefix)
    course_content_data = StringIO(
        course_content_stream['Body'].read().decode('utf-8')
        )
    records = csv.DictReader(course_content_data)

    with session_factory.begin() as session:
        for eachRecord in records:
            visible = True if eachRecord['visible'] == '1' else False
            eachRecord['visible'] = visible
            eachRecord['term'] = term
            insert_stmt = insert(CourseContent).values(**eachRecord)
            do_update_stmt = insert_stmt.on_conflict_do_update(
                index_elements=['term', 'content_id'],
                set_=dict(
                    section=eachRecord['section'],
                    activity_name=eachRecord['activity_name'],
                    lesson_page=eachRecord['lesson_page'],
                    visible=visible,
                    updated_at=datetime.utcnow()
                )
            )
            session.execute(do_update_stmt)


if __name__ == "__main__":  # pragma: no cover
    main()
