"""Connecting to PostgreSQL, and turning connection errors into short, clear messages."""

import os

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo

# The project's group roles (docs/cli-interfaces.md). PostgreSQL decides what each one may do.
PROJECT_ROLES = ["admin", "medical_user", "developer"]


class LoginError(Exception):
    """Login failed. The message is written for the user."""


def server_address() -> str:
    """Where the database is: DATABASE_URL without its user and password, which are typed at login."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise LoginError("No database address: put DATABASE_URL in the .env file (see README).")

    settings = conninfo_to_dict(url)
    settings.pop("user", None)
    settings.pop("password", None)
    return make_conninfo(**settings)


def host_of(address: str) -> str:
    return conninfo_to_dict(address).get("host", "localhost")


def login(address: str, user: str, password: str) -> psycopg.Connection:
    try:
        return psycopg.connect(
            address,
            user=user,
            password=password,
            autocommit=True,       # tdm opens transactions itself, only when asked to
            connect_timeout=15,    # Neon can need a few seconds to wake up
            application_name="tdm",
        )
    except psycopg.OperationalError as error:
        if "password authentication failed" in str(error):
            raise LoginError("Wrong username or password.") from None
        raise LoginError(f"Can't connect to {host_of(address)}: {_problem(error)}") from None


def project_role(conn: psycopg.Connection) -> str:
    """The project role the logged-in user acts as, e.g. "medical_user"."""
    rows = conn.execute(
        "SELECT rolname FROM pg_roles"
        " WHERE rolname = ANY(%s) AND pg_has_role(current_user, oid, 'USAGE')"
        " ORDER BY rolname",
        [PROJECT_ROLES],
    ).fetchall()
    return ", ".join(name for (name,) in rows) or "no project role"


def _problem(error: psycopg.OperationalError) -> str:
    # 'connection failed: connection to server at "::1", port 1 failed: Connection refused\n...'
    #   -> 'Connection refused'
    first_line = str(error).splitlines()[0]
    return first_line.rsplit("failed: ", 1)[-1].removeprefix("FATAL:  ").removeprefix("ERROR:  ")
