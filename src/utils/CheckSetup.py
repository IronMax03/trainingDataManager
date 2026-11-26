"""This file is used to check the server connexion by sending the query SELECT version(), along side that this script output the version of major dependencies."""

from huggingface_hub import list_repo_files
from config_manager import ConfigManager
from dotenv import load_dotenv
from yaml import safe_load
import psycopg
import time
import os

from huggingface_hub import __version__ as hfV
from psycopg import __version__ as psycopgV
from pytest import __version__ as pytestV
from polars import __version__ as plV

load_dotenv()                   # reads .env and puts DATABASE_URL into the environment
dsn = os.environ["DATABASE_URL"]

print("polars version: ", plV)
print("pytest version: ", pytestV)
print("psycopg version: ", psycopgV)
print("huggingface_hub version: ", hfV)

config = ConfigManager("connections.yaml")
print("[connections.yaml successfully loaded]")

# Check server connection
with psycopg.connect(dsn) as conn:
    print(time.strftime("%H:%M:%S"), "SELECT version()")
    row = conn.execute("SELECT version();").fetchone()
    print("     ", row[0])

# Check hugging face read token
files = list_repo_files(config["HF_REPO_ADDRESS"],
                        repo_type="dataset",
                        token=os.environ["HUGGINGFACE_READ_TOKEN"])
print(time.strftime("%H:%M:%S"), " huging face repository content:", files)
