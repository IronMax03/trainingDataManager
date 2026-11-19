import os

import psycopg
from psycopg import __version__ as psycopgV
from polars import __version__ as plV
from pytest import __version__ as pytestV

from dotenv import load_dotenv
import time

load_dotenv()                   # reads .env and puts DATABASE_URL into the environment
dsn = os.environ["DATABASE_URL"]

print("polars version: ", plV)
print("pytest version: ", pytestV)
print("psycopg version: ", psycopgV)

# 'with' opens the connection and closes it automatically at the end
with psycopg.connect(dsn) as conn:
    print(time.strftime("%H:%M:%S"), "SELECT version()")
    row = conn.execute("SELECT version();").fetchone()
    print("     ", row[0])
