# RAISE Data Dashboard

## Local developer environment

A local developer environment can be launched via `docker`:

```bash
$ docker compose up -d
```

You can then navigate to [http://localhost:3000](http://localhost:3000) and access an instance of Metabase. The database is also exposed on port `5432` to make it easier to test schema migrations.

## Database migrations

We use [alembic](https://alembic.sqlalchemy.org/) to manage migrations for the metrics database that backs Metabase. A migration can be auto generated using the following after updating the schema definition in this directory:

```bash
$ alembic revision --autogenerate -m "Message string"
```

If you have not alread, create a `raisemetrics` database for testing migrations:

```bash
$ docker compose exec postgres psql -U pguser postgres -c "CREATE DATABASE raisemetrics"
```

You can test the migration locally by then running:

```bash
$ alembic upgrade head
```
