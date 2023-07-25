import time
import logging
from sqlalchemy.exc import IntegrityError
from psycopg2.errors import UniqueViolation

SQS_WAIT_TIME_SECS = 20
SQS_MAX_MESSAGES = 10

logger = logging.getLogger(__name__)


class ProcessorException(Exception):
    pass


def get_sqs_messages(sqs_client, queue_url):
    res = sqs_client.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=SQS_MAX_MESSAGES,
        WaitTimeSeconds=SQS_WAIT_TIME_SECS
    )
    return res.get("Messages", [])


def processor_runner(
    sqs_client, sqs_queue_name, processor, poll_interval_mins, daemonize
):
    queue_url_data = sqs_client.get_queue_url(
        QueueName=sqs_queue_name
    )
    queue_url = queue_url_data["QueueUrl"]

    while True:
        sqs_messages = get_sqs_messages(sqs_client, queue_url)
        for message in sqs_messages:
            receipt_handle = message["ReceiptHandle"]

            try:
                processor(message)

                # Message processed successfully. Delete from SQS.
                sqs_client.delete_message(
                    QueueUrl=queue_url,
                    ReceiptHandle=receipt_handle
                )
            except ProcessorException as e:
                logger.error(f"Failed processing SQS message: {e}")

        if not daemonize:
            break

        # Only sleep if the long polling request didn't return any messages.
        # Otherwise we should keep trying to retrieve messages in order to
        # drain the queue as SQS may not have returned all available / max
        # requested. Even an empty response doesn't guarantee the queue
        # is empty, so this is just a heuristic to balance timely processing
        # with SQS requests when the polling interval is non-zero.
        if len(sqs_messages) == 0:  # pragma: no cover
            time.sleep(poll_interval_mins*60)
        else:  # pragma: no cover
            logger.info(f"Received {len(sqs_messages)} messages")


def commit_ignoring_unique_violations(session):
    """This function expects a sqlalchemy session which it will try to
    commit while ignoring errors related to unique constraint violations.
    Any other errors will be propagated.
    """

    try:
        session.commit()
    except IntegrityError as e:
        if isinstance(e.orig, UniqueViolation):
            session.rollback()
        else:
            raise e  # pragma: no cover
