# RAISE Data

This repo includes backend code used to process / wrangle RAISE data. We utilize an event-driven producer-consumer architecture backed by SNS and SQS. The consumers are realized via simple processors that pull messages from SQS and transform data in a consumer specific manner (e.g. for enclaves, dashboards, etc.). The repo also contains loaders that can be used by devs to "replay" historical messages (typically this is used to backfill data for new consumers).

## Developers

When developing code for this repo, developers may want to install the project in editable mode:

```bash
$ pip install -e .
```

The code can be linted and tested locally as well:

```bash
$ pip install .[test]
$ flake8
$ pytest
```

Code coverage reports can be generated when running tests:

```bash
$ pytest --cov=raise_data --cov-report=term --cov-report=html
```
