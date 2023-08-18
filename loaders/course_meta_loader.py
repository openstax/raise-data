import argparse
import boto3
import csv
import os
from io import StringIO
from datetime import datetime
from sqlalchemy import create_engine, update
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

    term = s3_prefix.split('/')[1]

    s3_client = boto3.client('s3')
    course_metadata_stream = s3_client.get_object(
        Bucket=s3_bucket,
        Key=s3_prefix)
    course_metadata = StringIO(
        course_metadata_stream['Body'].read().decode('utf-8')
        )
    records = csv.DictReader(course_metadata)

    with session_factory.begin() as session:
        existing_courses = session.query(Course).filter_by(term=term).all()
        csv_district_data = {}

        for eachRecord in records:
            csv_district_data[eachRecord['course_id']] = eachRecord['district']

        for course in existing_courses:
            course_id_str = str(course.id)
            csv_district_name = csv_district_data.get(course_id_str)
            if course_id_str in csv_district_data and \
                    csv_district_name != course.district:
                update_stmt = (
                    update(Course)
                    .where(Course.id == course.id)
                    .values(
                        district=csv_district_name,
                        updated_at=datetime.utcnow()
                    )
                )
                session.execute(update_stmt)


if __name__ == "__main__":  # pragma: no cover
    main()
