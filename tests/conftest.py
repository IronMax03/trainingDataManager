import io
import os
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

from tdm.db import PROJECT_ROLES, login, server_address
from tdm.shell import Shell

USER_FUNCTIONS = Path(__file__).parent.parent / "sql" / "03_user_management.sql"
PLACEHOLDER_TABLES = Path(__file__).parent / "placeholder_tables.sql"

# Tests use the throwaway PostgreSQL from compose.yaml, never the shared Neon database.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/postgres"
)


@pytest.fixture(scope="session")
def test_db_url() -> str:
    settings = conninfo_to_dict(TEST_DATABASE_URL)
    host = settings.get("host")
    if host not in ("localhost", "127.0.0.1", "::1") or "hostaddr" in settings:   # the tests drop roles and tables
        pytest.fail(f"Tests only run on a local test database, not on {host}.")
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
def groups(test_db_url: str):
    """The groups admin, medical_user and developer, and the user functions from sql/. All made by
    `tdm_owner` (password owner-pw): a database owner that is not a superuser, like neondb_owner on Neon."""
    with psycopg.connect(test_db_url, autocommit=True) as conn:
        remove_test_roles(conn)   # in case an earlier run was stopped halfway
        conn.execute("CREATE ROLE tdm_owner LOGIN CREATEROLE PASSWORD 'owner-pw'")
        conn.execute("GRANT CREATE ON SCHEMA public TO tdm_owner")
        conn.execute("SET ROLE tdm_owner")
        for group in PROJECT_ROLES:
            conn.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(group)))
        conn.execute(USER_FUNCTIONS.read_text())

    yield

    with psycopg.connect(test_db_url, autocommit=True) as conn:
        remove_test_roles(conn)


def remove_test_roles(conn: psycopg.Connection) -> None:
    """Drop every role the tests made: all but postgres and PostgreSQL's own pg_ roles."""
    names = [name for (name,) in conn.execute(
        "SELECT rolname FROM pg_roles WHERE rolname <> 'postgres' AND rolname NOT LIKE 'pg\\_%'"
        " ORDER BY rolname = 'tdm_owner'"   # the owner last: it gave the others their groups
    )]
    for name in names:
        conn.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(name)))
    for name in names:
        conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(name)))


def add_user(test_db_url: str, name: str, group: str) -> tuple[str, str]:
    """A user made by tdm_owner, the way create_user() makes them. Gives (name, password)."""
    password = f"{name}-pw"
    with psycopg.connect(test_db_url, autocommit=True) as conn:
        conn.execute("SET ROLE tdm_owner")
        conn.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} IN ROLE {}").format(
            sql.Identifier(name), sql.Literal(password), sql.Identifier(group)
        ))
    return name, password


@pytest.fixture
def alice(groups, test_db_url: str) -> tuple[str, str]:
    """A user `alice` in the group medical_user. Gives (user, password)."""
    return add_user(test_db_url, "alice", "medical_user")


@pytest.fixture
def ada(groups, test_db_url: str) -> tuple[str, str]:
    """A user `ada` in the group admin."""
    return add_user(test_db_url, "ada", "admin")


@pytest.fixture
def dave(groups, test_db_url: str) -> tuple[str, str]:
    """A user `dave` in the group developer."""
    return add_user(test_db_url, "dave", "developer")


@pytest.fixture
def patient_tables(groups, test_db_url: str):
    """The patient tables (stand-ins from placeholder_tables.sql, with their permissions) and pgcrypto."""
    with psycopg.connect(test_db_url, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS patient_identity, patient")   # in case an earlier run was stopped
        conn.execute(PLACEHOLDER_TABLES.read_text())

    yield

    with psycopg.connect(test_db_url, autocommit=True) as conn:
        conn.execute("SET lock_timeout = '5s'")   # fail, don't hang, if a test left a transaction open
        conn.execute("DROP TABLE patient_identity, patient")


@pytest.fixture
def open_shell(groups):
    """open_shell(user, password) logs in and gives a tdm shell. What it prints goes to shell.stdout
    (a text buffer)."""
    conns = []

    def open_as(user: str, password: str) -> Shell:
        conn = login(server_address(), user, password)
        conns.append(conn)
        return Shell(conn, stdout=io.StringIO())

    yield open_as
    for conn in conns:
        conn.close()


def typing_into(shell: Shell):
    """type_line("whoami") types one line into the shell and gives back what it printed."""
    def type_line(line: str) -> str:
        shell.stdout.seek(0)
        shell.stdout.truncate()
        shell.onecmd(line)
        return shell.stdout.getvalue()

    return type_line


@pytest.fixture
def run_as(open_shell):
    """run_as(user, password) logs in and gives a function that types lines as that user."""
    return lambda user, password: typing_into(open_shell(user, password))


@pytest.fixture
def shell(open_shell, alice) -> Shell:
    """A tdm shell logged in as alice (medical_user)."""
    return open_shell(*alice)


@pytest.fixture
def run(shell):
    """run("whoami") types a line as alice and gives back what tdm printed."""
    return typing_into(shell)


@pytest.fixture
def admin_shell(open_shell, ada) -> Shell:
    """A tdm shell logged in as ada (admin)."""
    return open_shell(*ada)


@pytest.fixture
def run_admin(admin_shell):
    """run_admin("users") types a line as ada (admin) and gives back what tdm printed."""
    return typing_into(admin_shell)


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
        conn.execute("SET lock_timeout = '5s'")
        conn.execute("DROP TABLE numbers")
