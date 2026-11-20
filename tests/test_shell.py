import psycopg


def test_whoami(run):
    assert run("whoami") == "alice (medical_user) on localhost/postgres\n"


def test_help_lists_commands(run):
    out = run("help")

    assert "whoami" in out and "begin" in out and "exit" in out
    assert "end it with ;" in out


def test_unknown_command(run):
    assert run("dance now").startswith("Unknown command: dance.")


def test_commands_ignore_case_and_semicolon(run):
    assert run("WHOAMI;").startswith("alice (medical_user)")


def test_empty_line_does_not_repeat_last_command(run):
    run("whoami")

    assert run("") == ""


def test_exit_quit_and_ctrl_d_stop_the_shell(shell):
    assert shell.onecmd("exit") is True
    assert shell.onecmd("quit") is True
    assert shell.onecmd("EOF") is True


def test_lost_connection_is_one_clear_line(shell, run, test_db_url):
    with psycopg.connect(test_db_url, autocommit=True) as admin:   # cut alice's connection
        admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE usename = 'alice'")

    assert run("whoami") == "Lost the connection to the database. Type exit and log in again.\n"
    assert shell.onecmd("whoami") is False   # the shell keeps running
