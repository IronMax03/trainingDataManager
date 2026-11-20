import os

import psycopg
import pytest

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
