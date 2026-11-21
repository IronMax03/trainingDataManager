"""tdm in a real terminal, typed into like a person would (pexpect starts it and types)."""

import io
import os
import sys
from pathlib import Path

import pexpect
import psycopg
import pytest

SRC = Path(__file__).parent.parent / "src"


def start_tdm(test_db_url: str, user: str, password: str) -> pexpect.spawn:
    env = dict(os.environ, DATABASE_URL=test_db_url, PYTHONPATH=str(SRC))
    child = pexpect.spawn(sys.executable, ["-m", "tdm"], env=env, encoding="utf-8", timeout=20)
    child.expect_exact("User: ")
    child.sendline(user)
    child.expect_exact("Password: ")
    child.sendline(password)
    child.expect_exact("tdm> ")
    return child


def wait_until_running(child: pexpect.spawn, test_db_url: str, query: str) -> None:
    """Wait until PostgreSQL runs the query. Meanwhile keep reading tdm's screen: the terminal
    library waits until what it printed has been read (a real terminal window always reads it)."""
    with psycopg.connect(test_db_url, autocommit=True) as conn:
        for _ in range(100):
            running = conn.execute(
                "SELECT count(*) FROM pg_stat_activity WHERE state = 'active' AND query = %s", [query]
            ).fetchone()[0]
            if running:
                return
            child.expect(pexpect.TIMEOUT, timeout=0.1)
    raise AssertionError(f"{query!r} never started")


@pytest.mark.filterwarnings("ignore:This process .* is multi-threaded")   # tdm is started right away
def test_ctrl_c_stops_a_slow_query(alice, test_db_url):
    child = start_tdm(test_db_url, *alice)

    child.sendline("begin")
    child.expect_exact("tdm*> ")
    child.sendline("select pg_sleep(30);")
    wait_until_running(child, test_db_url, "select pg_sleep(30);")
    child.sendintr()   # Ctrl+C

    child.expect_exact("Query cancelled.")
    child.expect_exact("tdm!> ")   # the transaction failed, the shell keeps going
    child.sendline("rollback")
    child.expect_exact("tdm> ")

    child.sendline("select 1 as one")   # Ctrl+C also drops a half-typed SQL statement
    child.expect_exact("...> ")
    child.sendintr()
    child.expect_exact("tdm> ")

    child.sendeof()   # Ctrl+D
    child.expect(pexpect.EOF)


@pytest.mark.filterwarnings("ignore:This process .* is multi-threaded")
def test_adduser_asks_the_password_without_showing_it(ada, test_db_url):
    child = start_tdm(test_db_url, *ada)
    screen = io.StringIO()
    child.logfile_read = screen   # everything tdm shows from now on

    child.sendline("adduser bob developer")
    child.expect_exact("Password for bob: ")
    child.sendline("bob-pw")
    child.expect_exact("Type it again: ")
    child.sendline("bob-pw")
    child.expect_exact("Added bob to developer.")
    child.expect_exact("tdm> ")
    child.sendline("exit")
    child.expect(pexpect.EOF)

    assert "adduser bob developer" in screen.getvalue()   # normal typing is shown...
    assert "bob-pw" not in screen.getvalue()              # ...the password is not
