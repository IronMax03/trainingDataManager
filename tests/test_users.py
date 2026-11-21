"""User management: users, adduser, removeuser and setgroup (sql/03_user_management.sql)."""

import psycopg
import pytest

from tdm.db import LoginError, login, project_role, server_address


@pytest.fixture
def typed_passwords(monkeypatch):
    """typed_passwords("a", "a"): what the user types at the next password prompts."""
    def answer(*passwords: str) -> None:
        answers = iter(passwords)
        monkeypatch.setattr("getpass.getpass", lambda prompt="": next(answers))

    return answer


def group_of(user: str, password: str) -> str:
    """Log in as that user and ask PostgreSQL which group they are in."""
    with login(server_address(), user, password) as conn:
        return project_role(conn)


def cannot_log_in(user: str, password: str) -> bool:
    try:
        login(server_address(), user, password).close()
    except LoginError:
        return True
    return False


def test_admin_adds_a_user_who_can_log_in(run_admin, typed_passwords):
    typed_passwords("bob-pw", "bob-pw")

    assert run_admin("adduser bob developer") == "Added bob to developer.\n"
    assert group_of("bob", "bob-pw") == "developer"


def test_the_database_keeps_only_a_hash_of_the_password(run_admin, typed_passwords, test_db_url):
    run_admin("set password_encryption = 'md5';")   # a weaker hash than PostgreSQL's default: ignored
    typed_passwords("bob-pw", "bob-pw")
    run_admin("adduser bob developer")

    with psycopg.connect(test_db_url) as conn:
        stored = conn.execute("SELECT rolpassword FROM pg_authid WHERE rolname = 'bob'").fetchone()[0]
    assert stored.startswith("SCRAM-SHA-256$") and "bob-pw" not in stored


def test_adduser_mistakes_change_nothing(run_admin, typed_passwords):
    typed_passwords("one", "two")
    assert run_admin("adduser bob developer") == "The passwords don't match. Nothing changed.\n"
    assert cannot_log_in("bob", "one")

    assert run_admin("adduser bob boss") == "Choose a group: admin, medical_user, developer.\n"
    assert run_admin("adduser bob").startswith("Usage: adduser <name> <group>")


def test_setgroup_moves_a_user(run_admin, alice):
    assert run_admin("setgroup alice developer") == "alice is now in developer.\n"
    assert group_of(*alice) == "developer"   # and no longer medical_user


def test_removed_user_can_no_longer_log_in(run_admin, alice):
    assert run_admin("removeuser alice") == "Removed alice.\n"
    assert cannot_log_in(*alice)


def test_users_lists_everyone_with_their_group(run_admin, alice):
    lines = run_admin("users").splitlines()

    assert any("ada" in line and "admin" in line for line in lines)
    assert any("alice" in line and "medical_user" in line for line in lines)
    assert lines[-1] == "(2 rows)"   # not tdm_owner: it manages the groups but isn't in them


def test_only_admins_manage_users(run, typed_passwords):   # run types as alice, a medical_user
    typed_passwords("bob-pw", "bob-pw")

    assert run("adduser bob developer").startswith("Error: permission denied for function create_user")
    assert run("removeuser ada").startswith("Error: permission denied for function drop_user")
    assert run("setgroup alice admin").startswith("Error: permission denied for function change_group")
    assert cannot_log_in("bob", "bob-pw")


def test_admins_cannot_touch_themselves_or_special_roles(run_admin):
    """The functions run with the owner's rights, so they must not touch the owner or PostgreSQL's own roles."""
    assert run_admin("removeuser ada").startswith("Error: You can't remove your own account")
    assert run_admin("setgroup ada developer").startswith("Error: You can't change your own group")
    assert run_admin("removeuser tdm_owner").startswith('Error: There is no user called "tdm_owner".')
    assert run_admin("setgroup admin developer").startswith('Error: There is no user called "admin".')
    assert run_admin("select create_user('evil', 'pw', 'pg_write_all_data');").startswith(
        'Error: Unknown group "pg_write_all_data"'
    )


def test_names_cannot_smuggle_in_sql(run_admin, test_db_url):
    run_admin("""select create_user('x"; DROP ROLE ada; --', 'pw', 'developer');""")

    with psycopg.connect(test_db_url) as conn:
        names = [name for (name,) in conn.execute("SELECT rolname FROM pg_roles")]
    assert 'x"; DROP ROLE ada; --' in names   # just an odd name
    assert "ada" in names


def test_inside_a_transaction_it_waits_for_commit(run_admin, typed_passwords):
    typed_passwords("bob-pw", "bob-pw")
    run_admin("begin")

    assert run_admin("adduser bob developer") == "Added bob to developer. It is saved when you commit.\n"
    run_admin("rollback")
    assert cannot_log_in("bob", "bob-pw")


def test_database_owner_makes_the_first_admin(run_as, typed_passwords):
    """On a new database nobody is admin yet: the owner (neondb_owner on Neon) logs in and makes the first one."""
    run_owner = run_as("tdm_owner", "owner-pw")
    typed_passwords("first-pw", "first-pw")

    assert run_owner("adduser first admin") == "Added first to admin.\n"
    assert group_of("first", "first-pw") == "admin"


def test_setgroup_refuses_a_group_the_owner_did_not_give(run_admin, test_db_url):
    """PostgreSQL only lets the owner take back what the owner gave. Here a superuser made frank admin."""
    with psycopg.connect(test_db_url, autocommit=True) as conn:
        conn.execute("CREATE ROLE frank LOGIN PASSWORD 'frank-pw'")
        conn.execute("GRANT admin TO frank")

    out = run_admin("setgroup frank developer")

    assert "Error: Can't take \"frank\" out of admin: postgres put them there" in out
    assert group_of("frank", "frank-pw") == "admin"   # not admin and developer at once


def test_errors_do_not_repeat_the_password(ada):
    with login(server_address(), *ada) as conn, pytest.raises(psycopg.Error) as caught:
        conn.execute("SELECT public.create_user('ada', %s, 'developer')", ["Leak-Me-1234"])   # ada exists

    # what goes back to the user and into the server's log
    assert "Leak-Me-1234" not in f"{caught.value} {caught.value.diag.context}"
