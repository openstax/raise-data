from raise_data.loaders import course_content_loader
import boto3
import pytest
import botocore.stub
import csv
from io import StringIO, BytesIO
from raise_data.dashboard.schema import CourseContent


@pytest.fixture(autouse=True)
def clear_database_table():
    """This fixture is setup to clear the table before each test run in
    this file
    """
    with course_content_loader.session_factory.begin() as session:
        session.query(CourseContent).delete()


def test_course_content_loader(mocker):

    s3_client = boto3.client("s3")
    s3_stubber = botocore.stub.Stubber(s3_client)

    mock_dict_writer_data = [
        {
            "content_id": "95b56d4f-e11e-4704-a2c7-92851aca4464",
            "section": "Section 1",
            "activity_name": "Activity Name 1",
            "lesson_page": "Lesson Page 1",
            "visible": '1'
        },
        {
            "content_id": "12a34b5c-e11e-4704-a2c7-92851aca4464",
            "section": "Section 2",
            "activity_name": "Activity Name 2",
            "lesson_page": "Lesson Page 2",
            "visible": '0'
        }
    ]
    for _ in range(2):
        mock_course_content_bytes = StringIO()
        mock_fieldnames = mock_dict_writer_data[0].keys()
        writer = csv.DictWriter(
            mock_course_content_bytes, fieldnames=mock_fieldnames
            )
        writer.writeheader()
        writer.writerow(mock_dict_writer_data[0])
        writer.writerow(mock_dict_writer_data[1])
        mock_course_content_bytes.seek(0)

        mock_bytes = BytesIO(mock_course_content_bytes.read().encode('utf-8'))

        s3_stubber.add_response(
                "get_object",
                {"Body": mock_bytes},
                expected_params={
                    "Bucket": "testbucket",
                    "Key": "course/term/content/course_contents.csv",
                }
        )

    s3_stubber.activate()
    mocker_map = {
        "s3": s3_client,
    }
    mocker.patch("boto3.client", lambda client: mocker_map[client])

    mocker.patch(
        "sys.argv",
        ["", "testbucket", "course/term/content/course_contents.csv"]
        )
    course_content_loader.main()

    with course_content_loader.session_factory.begin() as session:
        course_content = session.query(CourseContent).all()

        assert (
            str(course_content[0].content_id) ==
            "95b56d4f-e11e-4704-a2c7-92851aca4464"
        )
        assert course_content[0].section == 'Section 1'
        assert course_content[0].activity_name == 'Activity Name 1'
        assert course_content[0].lesson_page == 'Lesson Page 1'
        assert course_content[0].visible
        assert (
            str(course_content[1].content_id) ==
            "12a34b5c-e11e-4704-a2c7-92851aca4464"
        )
        assert course_content[1].section == 'Section 2'
        assert course_content[1].activity_name == 'Activity Name 2'
        assert course_content[1].lesson_page == 'Lesson Page 2'
        assert not course_content[1].visible

    # Run a second pass with the same data to be sure we process properly
    mocker.patch(
        "sys.argv",
        ["", "testbucket", "course/term/content/course_contents.csv"]
        )
    course_content_loader.main()

    with course_content_loader.session_factory.begin() as session:
        course_content = session.query(CourseContent).all()

        assert len(course_content) == 2

    s3_stubber.assert_no_pending_responses()
