import pytest

from tdm.db import LoginError, login, project_role, server_address


def test_address_keeps_server_but_drops_user_and_password(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://bob:secret@db.example.com/neondb?sslmode=require")

    address = server_address()

    assert "bob" not in address and "secret" not in address
    assert "host=db.example.com" in address and "sslmode=require" in address


def test_missing_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL")

    with pytest.raises(LoginError, match="put DATABASE_URL in the .env file"):
        server_address()


def test_login_finds_project_role(alice):
    user, password = alice

    with login(server_address(), user, password) as conn:
        assert project_role(conn) == "medical_user"


def test_wrong_password(alice):
    with pytest.raises(LoginError, match="^Wrong username or password.$"):
        login(server_address(), "alice", "wrong")


def test_unknown_user_looks_the_same_as_wrong_password(test_db_url):
    with pytest.raises(LoginError, match="^Wrong username or password.$"):
        login(server_address(), "nobody", "whatever")


def test_server_unreachable():
    with pytest.raises(LoginError, match="^Can't connect to localhost: .*refused"):
        login("host=localhost port=1 dbname=postgres", "x", "x")
