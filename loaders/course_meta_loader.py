import argparse
import boto3
import csv
import os
from io import StringIO
from datetime import datetime
from sqlalchemy import create_engine, update, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import sessionmaker
from raise_data.dashboard.schema import (
     Course
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
        description="Load district identifier to database"
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


    s3_client = boto3.client('s3')
    course_metadata_stream = s3_client.get_object(
        Bucket=s3_bucket,
        Key=s3_prefix)
    course_metadata = StringIO(
        course_metadata_stream['Body'].read().decode('utf-8')
        )
    records = csv.DictReader(course_metadata)


    with session_factory.begin() as session:
        existing_courses = session.query(Course).all()

        for eachRecord in records:
            for course in existing_courses:
                if int(eachRecord['course_id']) == course.id:
                    if eachRecord['district'] != course.district:
                        update_stmt = (
                            update(Course)
                            .where(Course.id == int(eachRecord['course_id']))
                            .values(district=eachRecord['district'], updated_at=datetime.utcnow())
                        )
                        session.execute(update_stmt)


if __name__ == "__main__":  # pragma: no cover
    main()
