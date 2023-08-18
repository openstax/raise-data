from raise_data.loaders import course_meta_loader
import boto3
import pytest
import botocore.stub
import csv
from io import StringIO, BytesIO
from sqlalchemy.dialects.postgresql import insert
from raise_data.dashboard.schema import Course


@pytest.fixture(autouse=True)
def setup_database_table():
    """This fixture clears and populates the Course table before each test
    run in this file
    """
    with course_meta_loader.session_factory.begin() as session:
        session.query(Course).delete()
        insert_stmt = insert(Course).values(
            [
                {'id': 1, 'name': 'Name 1', 'term': 'term1', 'district': ''},
                {'id': 2, 'name': 'Name 2', 'term': 'term1', 'district': None}
            ]
        )
        session.execute(insert_stmt)


def test_course_meta_loader(mocker):

    s3_client = boto3.client("s3")
    s3_stubber = botocore.stub.Stubber(s3_client)

    mock_dict_writer_data_1 = [
        {
            "course_id": 1,
            "district": "Halo School District",
        },
        {
            "course_id": 2,
            "district": "Azeroth School District",
        },
        {
            "course_id": 3,
            "district": "Faerun School District"
        }
    ]

    mock_course_metadata_bytes = StringIO()
    mock_fieldnames = mock_dict_writer_data_1[0].keys()
    writer = csv.DictWriter(
        mock_course_metadata_bytes, fieldnames=mock_fieldnames
        )
    writer.writeheader()
    writer.writerows(mock_dict_writer_data_1)
    mock_course_metadata_bytes.seek(0)

    mock_bytes_1 = BytesIO(mock_course_metadata_bytes.read().encode("utf-8"))

    s3_stubber.add_response(
            "get_object",
            {"Body": mock_bytes_1},
            expected_params={
                "Bucket": "testbucket",
                "Key": "course/term1/automation/courses.csv",
            }
    )

    s3_stubber.activate()
    mocker_map = {
        "s3": s3_client,
    }
    mocker.patch("boto3.client", lambda client: mocker_map[client])

    mocker.patch(
        "sys.argv",
        ["", "testbucket", "course/term1/automation/courses.csv"]
        )
    course_meta_loader.main()

    with course_meta_loader.session_factory.begin() as session:
        course_metadata = session.query(Course).all()
        assert course_metadata[0].district == "Halo School District"
        assert course_metadata[1].district == "Azeroth School District"

    # Run a second pass with the similar data to be sure we process properly

    mock_dict_writer_data_2 = [
        {
            "course_id": 1,
            "district": "Runeterra School District",
        },
        {
            "course_id": 2,
            "district": "Continent School District",
        }
    ]

    writer.writerows(mock_dict_writer_data_2)
    mock_course_metadata_bytes.seek(0)

    mock_bytes_2 = BytesIO(mock_course_metadata_bytes.read().encode("utf-8"))

    s3_stubber.add_response(
        "get_object",
        {"Body": mock_bytes_2},
        expected_params={
            "Bucket": "testbucket",
            "Key": "course/term1/automation/courses.csv",
        }
    )
    mocker.patch(
        "sys.argv",
        ["", "testbucket", "course/term1/automation/courses.csv"]
        )
    course_meta_loader.main()

    with course_meta_loader.session_factory.begin() as session:
        course_metadata = session.query(Course).all()

        assert len(course_metadata) == 2
        assert course_metadata[0].district == "Runeterra School District"
        assert course_metadata[1].district == "Continent School District"

    s3_stubber.assert_no_pending_responses()
