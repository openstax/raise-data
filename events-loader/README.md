# Events loader

This code includes a utility `loader.py` which can be used to "replay" S3 events by injecting synthetic SQS messages. Given our processors are idempotent, it can be used for things like backfilling historical data.

The tests for this processor can be run as follows:

```bash
$ pip install -r requirements.txt
$ pip install flake8 pytest pytest-mock
$ flake8
$ pytest
```
