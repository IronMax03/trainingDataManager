import psycopg

from tdm.__main__ import main


def type_in(monkeypatch, *lines: str, password: str = "") -> None:
    """Pretend the user typed these lines (and this password) at the keyboard."""
    answers = iter(lines)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    monkeypatch.setattr("getpass.getpass", lambda prompt="": password)


def test_login_then_exit(alice, monkeypatch, capsys):
    user, password = alice
    type_in(monkeypatch, user, "whoami", "exit", password=password)

    assert main() == 0
    out = capsys.readouterr().out
    assert "Logged in as alice (medical_user)" in out
    assert "alice (medical_user) on localhost/postgres" in out


def test_wrong_password_is_one_clear_line(alice, monkeypatch, capsys):
    type_in(monkeypatch, "alice", password="wrong")

    assert main() == 1
    assert capsys.readouterr().out.endswith("Connecting to localhost...\nWrong username or password.\n")


def test_ctrl_d_at_login_quits_quietly(monkeypatch, capsys):
    def ctrl_d(prompt=""):
        raise EOFError

    monkeypatch.setattr("builtins.input", ctrl_d)

    assert main() == 1
    assert "Traceback" not in capsys.readouterr().out


def test_database_matches_neon(test_db_url: str):
    with psycopg.connect(test_db_url) as conn:
        version = int(conn.execute("SHOW server_version_num").fetchone()[0])
        pgcrypto = conn.execute(
            "SELECT 1 FROM pg_available_extensions WHERE name = 'pgcrypto'"
        ).fetchone()

    assert version // 10000 == 18   # same major version as Neon
    assert pgcrypto                 # needed to encrypt personal data
