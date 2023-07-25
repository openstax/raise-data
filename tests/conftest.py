import os

# Set variables so tests appropriately access the dev database
os.environ["POSTGRES_SERVER"] = "localhost"
os.environ["POSTGRES_USER"] = "pguser"
os.environ["POSTGRES_PASSWORD"] = "pgpassword"
os.environ["POSTGRES_DB"] = "raisemetrics"
