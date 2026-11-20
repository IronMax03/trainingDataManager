def test_begin_then_commit_saves(shell, run, numbers):
    assert run("begin") == "Transaction started (read committed).\n"
    assert shell.prompt == "tdm*> "

    run("insert into numbers values (1);")
    assert numbers() == []   # other connections don't see it before commit

    assert run("commit") == "Committed: changes saved.\n"
    assert numbers() == [1]
    assert shell.prompt == "tdm> "


def test_rollback_undoes_everything(run, numbers):
    run("begin")
    run("insert into numbers values (1);")

    assert run("rollback") == "Rolled back: nothing was saved.\n"
    assert numbers() == []


def test_rollback_to_savepoint(run, numbers):
    run("begin")
    run("insert into numbers values (1);")
    assert run("savepoint a") == "Savepoint a set.\n"
    run("insert into numbers values (2);")

    assert run("rollback to a") == "Rolled back to savepoint a.\n"
    run("commit")
    assert numbers() == [1]


def test_sql_style_commands_work_too(run, numbers):
    run("BEGIN;")
    run("insert into numbers values (1);")
    run("SAVEPOINT a;")
    run("insert into numbers values (2);")
    run("ROLLBACK TO SAVEPOINT a;")
    run("COMMIT;")

    assert numbers() == [1]


def test_error_inside_a_transaction(shell, run, numbers):
    run("begin")
    run("insert into numbers values (1);")

    out = run("insert into numbers values (1);")
    assert out.startswith("Error: duplicate key")
    assert "type rollback" in out
    assert shell.prompt == "tdm!> "

    assert run("commit") == "Rolled back: the transaction had an error, so nothing was saved.\n"
    assert numbers() == []


def test_commands_that_need_a_transaction(run):
    assert run("commit") == "No transaction is open.\n"
    assert run("rollback") == "No transaction is open.\n"
    assert run("savepoint a") == "Savepoints only work inside a transaction: type begin first.\n"
    run("begin")
    assert run("begin") == "A transaction is already open: commit or rollback it first.\n"


def test_isolation_level_is_used(run):
    assert run("isolation serializable") == "Next transactions: serializable.\n"
    assert "serializable" in run("show transaction_isolation;")   # a single statement

    run("begin")
    assert "serializable" in run("show transaction_isolation;")   # a transaction opened by hand
    run("rollback")

    assert run("isolation sometimes") == "Choose one of: read committed, repeatable read, serializable.\n"


def test_read_only(run, numbers):
    assert run("readonly on") == "Next transactions: read committed, read only.\n"
    assert run("insert into numbers values (1);").startswith(
        "Error: cannot execute INSERT in a read-only transaction"
    )

    run("readonly off")
    run("insert into numbers values (1);")
    assert numbers() == [1]


def test_exit_rolls_back_an_open_transaction(shell, run, numbers):
    run("begin")
    run("insert into numbers values (1);")

    assert run("exit") == "The open transaction was rolled back.\n"
    assert numbers() == []
