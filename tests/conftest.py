import io
import os

import psycopg
import pytest

from tdm.db import login, server_address
from tdm.shell import Shell

# Tests use the throwaway PostgreSQL from compose.yaml, never the shared Neon database.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/postgres"
)


@pytest.fixture(scope="session")
def test_db_url() -> str:
    try:
        with psycopg.connect(TEST_DATABASE_URL, connect_timeout=3):
            pass
    except psycopg.OperationalError:
        if os.environ.get("CI"):   # on GitHub the database must be there
            raise
        pytest.skip("test database not running, start it with: docker compose up -d")

    return TEST_DATABASE_URL


@pytest.fixture(autouse=True)
def no_neon(monkeypatch):
    """Every test sees the test database as DATABASE_URL, so the CLI can never reach Neon.
    (load_dotenv() doesn't override a variable that is already set.)"""
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)


@pytest.fixture
def alice(test_db_url: str):
    """A login role `alice` in the group `medical_user`. Gives (user, password)."""
    with psycopg.connect(test_db_url, autocommit=True) as conn:
        conn.execute("DROP ROLE IF EXISTS alice")
        conn.execute("DROP ROLE IF EXISTS medical_user")
        conn.execute("CREATE ROLE medical_user NOLOGIN")
        conn.execute("CREATE ROLE alice LOGIN PASSWORD 'alice-pw' IN ROLE medical_user")

    yield "alice", "alice-pw"

    with psycopg.connect(test_db_url, autocommit=True) as conn:
        conn.execute("DROP ROLE alice")
        conn.execute("DROP ROLE medical_user")


@pytest.fixture
def shell(alice):
    """A tdm shell logged in as alice. What it prints goes to shell.stdout (a text buffer)."""
    user, password = alice
    conn = login(server_address(), user, password)
    yield Shell(conn, stdout=io.StringIO())
    conn.close()


@pytest.fixture
def run(shell):
    """run("whoami") types one line into the shell and gives back what it printed."""
    def type_line(line: str) -> str:
        shell.stdout.seek(0)
        shell.stdout.truncate()
        shell.onecmd(line)
        return shell.stdout.getvalue()

    return type_line


@pytest.fixture
def numbers(alice, test_db_url: str):
    """A table `numbers (n int primary key)` that medical_user may read and change.
    Gives a function that returns the numbers saved in it, as other connections see them."""
    with psycopg.connect(test_db_url, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS numbers")
        conn.execute("CREATE TABLE numbers (n int PRIMARY KEY)")
        conn.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON numbers TO medical_user")

    def saved() -> list[int]:
        with psycopg.connect(test_db_url) as conn:
            return [n for (n,) in conn.execute("SELECT n FROM numbers ORDER BY n")]

    yield saved

    with psycopg.connect(test_db_url, autocommit=True) as conn:
        conn.execute("DROP TABLE numbers")
