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
