# Events enclave processor

This code / Docker image implements a processor that retrieves event data notifications from SQS and generates JSON data intended for enclaves.

The tests for this processor can be run as follows:

```bash
$ pip install -r requirements.txt
$ pip install flake8 pytest pytest-mock
$ flake8
$ pytest
```
