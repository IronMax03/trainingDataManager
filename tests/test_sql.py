import polars as pl
import psycopg
import pytest


def test_select_shows_a_table(run, numbers):
    run("insert into numbers values (1), (2);")

    out = run("select n from numbers order by n;")

    assert "│ n │" in out and "│ 1 │" in out and "│ 2 │" in out
    assert out.endswith("(2 rows)\n")


def test_change_shows_what_postgresql_did(run, numbers):
    assert run("insert into numbers values (1);") == "INSERT 0 1\n"


def test_sql_over_several_lines(shell, run, numbers):
    assert run("select n") == ""
    assert shell.prompt == "...> "   # waiting for the ;

    assert run("from numbers;").endswith("(0 rows)\n")
    assert shell.prompt == "tdm> "


def test_error_rolls_back_everything_on_the_line(run, numbers):
    out = run("insert into numbers values (1); insert into numbers values (1);")

    assert out.startswith("Error: duplicate key value violates unique constraint")
    assert out.endswith("Rolled back: nothing was saved.\n")
    assert numbers() == []   # the first insert was undone too


def test_same_column_name_twice(run):
    assert "?column?_2" in run("select 1, 2;")


def test_notices_are_shown(run):
    assert run("drop table if exists not_here;") == (
        'NOTICE: table "not_here" does not exist, skipping\nDROP TABLE\n'
    )


@pytest.fixture
def secret(alice, test_db_url):
    """A table medical_user has no rights on."""
    with psycopg.connect(test_db_url, autocommit=True) as conn:
        conn.execute("CREATE TABLE secret (x int)")
    yield
    with psycopg.connect(test_db_url, autocommit=True) as conn:
        conn.execute("DROP TABLE secret")


def test_forbidden_query_is_refused_by_postgresql(run, secret):
    assert run("select * from secret;").startswith("Error: permission denied for table secret\n")


def test_script_is_all_or_nothing(run, numbers, tmp_path):
    good = tmp_path / "good.sql"
    good.write_text("insert into numbers values (1);\ninsert into numbers values (2);\n")
    bad = tmp_path / "bad.sql"
    bad.write_text("insert into numbers values (3);\ninsert into numbers values (1);\n")   # 1 is taken

    assert run(f"script {good}") == "INSERT 0 1\nINSERT 0 1\n"
    assert run(f"script {bad}").endswith("Rolled back: nothing was saved.\n")
    assert numbers() == [1, 2]   # 3 was not kept


def test_script_file_missing(run, tmp_path):
    assert run(f"script {tmp_path / 'nope.sql'}").startswith("Can't read")


def test_save_csv_and_parquet(run, numbers, tmp_path):
    run("insert into numbers values (1), (2);")
    run("select n from numbers order by n;")

    assert run(f"save {tmp_path / 'out.csv'}") == f"Saved 2 rows to {tmp_path / 'out.csv'}.\n"
    assert (tmp_path / "out.csv").read_text() == "n\n1\n2\n"

    run(f"save {tmp_path / 'out.parquet'}")
    assert pl.read_parquet(tmp_path / "out.parquet")["n"].to_list() == [1, 2]


def test_save_binary_column_as_csv(run, tmp_path):
    run("select '\\x00ff'::bytea as raw;")
    run(f"save {tmp_path / 'raw.csv'}")

    assert (tmp_path / "raw.csv").read_text() == "raw\n00ff\n"


def test_unusual_types_become_text(run, tmp_path):
    out = run("select int4range(1, 5) as r, '10.0.0.1'::inet as ip;")
    assert "[1, 5)" in out and "10.0.0.1" in out

    run(f"save {tmp_path / 'odd.csv'}")
    assert (tmp_path / "odd.csv").read_text() == "r,ip\n\"[1, 5)\",10.0.0.1\n"


def test_save_needs_a_result_and_a_known_file_type(run, tmp_path):
    assert run(f"save {tmp_path / 'out.csv'}") == "Nothing to save yet: run a query first.\n"
    run("select 1;")
    assert run(f"save {tmp_path / 'out.txt'}").startswith("Can't save: use a file name ending in .csv or .parquet")
