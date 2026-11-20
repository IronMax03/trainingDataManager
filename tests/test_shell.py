import io

import psycopg
import pytest

from tdm.db import login, server_address
from tdm.shell import Shell


@pytest.fixture
def shell(alice):
    user, password = alice
    conn = login(server_address(), user, password)
    yield Shell(conn, stdout=io.StringIO())
    conn.close()


def run(shell: Shell, line: str) -> str:
    """Type one line into the shell and give back what it printed."""
    shell.stdout.seek(0)
    shell.stdout.truncate()
    shell.onecmd(line)
    return shell.stdout.getvalue()


def test_whoami(shell):
    assert run(shell, "whoami") == "alice (medical_user) on localhost/postgres\n"


def test_help_lists_commands(shell):
    out = run(shell, "help")

    assert "whoami" in out and "exit" in out


def test_unknown_command(shell):
    assert run(shell, "dance now") == "Unknown command: dance. Type help to see the commands.\n"


def test_empty_line_does_not_repeat_last_command(shell):
    run(shell, "whoami")

    assert run(shell, "") == ""


def test_exit_quit_and_ctrl_d_stop_the_shell(shell):
    assert shell.onecmd("exit") is True
    assert shell.onecmd("quit") is True
    assert shell.onecmd("EOF") is True


def test_lost_connection_is_one_clear_line(shell, test_db_url):
    with psycopg.connect(test_db_url, autocommit=True) as admin:   # cut alice's connection
        admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE usename = 'alice'")

    assert run(shell, "whoami") == "Lost the connection to the database. Type exit and log in again.\n"
    assert shell.onecmd("whoami") is False   # the shell keeps running
