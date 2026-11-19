import os

import psycopg                  # pip install "psycopg[binary]" python-dotenv
from dotenv import load_dotenv
import time

load_dotenv()                   # reads .env and puts DATABASE_URL into the environment
dsn = os.environ["DATABASE_URL"]

# 'with' opens the connection and closes it automatically at the end
with psycopg.connect(dsn) as conn:
    print(time.strftime("%H:%M:%S"), "SELECT version()")
    row = conn.execute("SELECT version();").fetchone()
    print("     ", row[0])