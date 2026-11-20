import psycopg

from tdm.__main__ import main


def test_main_runs(capsys):
    assert main() == 0
    assert "tdm" in capsys.readouterr().out


def test_database_matches_neon(test_db_url: str):
    with psycopg.connect(test_db_url) as conn:
        version = int(conn.execute("SHOW server_version_num").fetchone()[0])
        pgcrypto = conn.execute(
            "SELECT 1 FROM pg_available_extensions WHERE name = 'pgcrypto'"
        ).fetchone()

    assert version // 10000 == 18   # same major version as Neon
    assert pgcrypto                 # needed to encrypt personal data
