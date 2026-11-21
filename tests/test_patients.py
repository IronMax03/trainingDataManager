"""addpatient: the clinical part goes to `patient`, the personal part is encrypted in `patient_identity`."""

import psycopg
import pytest

KEY = "test-key-0123456789"
JANE = ["f", "Jane Doe", "1 Main Street", "2012-03-04", "H-1001"]   # what the user types


@pytest.fixture(autouse=True)
def data_key(monkeypatch):
    monkeypatch.setenv("TDM_DATA_KEY", KEY)


@pytest.fixture
def typed(monkeypatch):
    """typed("F", "Jane Doe", ...): what the user types at the next prompts."""
    def answer(*lines: str) -> None:
        answers = iter(lines)
        monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))

    return answer


def saved_patients(test_db_url: str) -> list[tuple]:
    """The patients as they are saved, with the personal data decrypted with the key."""
    with psycopg.connect(test_db_url) as conn:
        return conn.execute(
            "SELECT patient_id, sex, pgp_sym_decrypt(name_enc, %(key)s), pgp_sym_decrypt(address_enc, %(key)s),"
            " pgp_sym_decrypt(birth_date_enc, %(key)s), pgp_sym_decrypt(hospital_no_enc, %(key)s)"
            " FROM patient JOIN patient_identity USING (patient_id) ORDER BY patient_id",
            {"key": KEY},
        ).fetchall()


def test_medical_user_adds_a_patient(run, typed, patient_tables, test_db_url):
    typed(*JANE)

    assert run("addpatient") == "Added patient 1. Their personal data is stored encrypted.\n"
    assert saved_patients(test_db_url) == [(1, "F", "Jane Doe", "1 Main Street", "2012-03-04", "H-1001")]


def test_personal_data_is_unreadable_without_the_key(run, typed, patient_tables, test_db_url):
    typed(*JANE)
    run("addpatient")

    with psycopg.connect(test_db_url) as conn:
        name_enc = conn.execute("SELECT name_enc FROM patient_identity").fetchone()[0]
        assert b"Jane" not in name_enc
        with pytest.raises(psycopg.Error, match="Wrong key"):
            conn.execute("SELECT pgp_sym_decrypt(name_enc, 'another-key-0123456') FROM patient_identity")


def test_optional_details_can_be_skipped(run, typed, patient_tables, test_db_url):
    typed("M", "John Roe", "", "", "")

    run("addpatient")

    assert saved_patients(test_db_url) == [(1, "M", "John Roe", None, None, None)]


@pytest.mark.parametrize("answers, problem", [
    (["X", "Jane Doe", "", "", ""], "Sex must be F, M or U."),
    (["F", "", "", "", ""], "The name can't be empty."),
    (["F", "Jane Doe", "", "4 March 2012", ""], "Write the date of birth as YYYY-MM-DD"),
    (["F", "Jane Doe", "", "2999-01-01", ""], "The date of birth is in the future."),
])
def test_mistakes_save_nothing(run, typed, patient_tables, test_db_url, answers, problem):
    typed(*answers)

    assert run("addpatient").startswith(problem)
    assert saved_patients(test_db_url) == []


def test_cancel(run, patient_tables, test_db_url, monkeypatch):
    def ctrl_d(prompt=""):
        raise EOFError

    monkeypatch.setattr("builtins.input", ctrl_d)

    assert run("addpatient") == "\nCancelled.\n"
    assert saved_patients(test_db_url) == []


def test_developers_cannot_add_patients(run_as, dave, typed, patient_tables):
    run_dave = run_as(*dave)
    typed()   # nothing may be asked

    assert run_dave("addpatient") == "Only admins and medical users can add patients.\n"
    assert run_dave("insert into patient (sex) values ('F');").startswith("Error: permission denied for table patient")
    assert run_dave("select * from patient_identity;").startswith("Error: permission denied for table patient_identity")


def test_a_key_is_needed(run, typed, patient_tables, monkeypatch):
    typed()   # nothing may be asked

    monkeypatch.delenv("TDM_DATA_KEY")
    assert run("addpatient").startswith("Put the team's encryption key in .env as TDM_DATA_KEY")
    monkeypatch.setenv("TDM_DATA_KEY", "short")
    assert run("addpatient").startswith("Put the team's encryption key in .env as TDM_DATA_KEY")


def test_key_and_name_never_appear_in_the_query_text(run, typed, patient_tables, test_db_url):
    typed(*JANE)
    run("begin")

    assert run("addpatient").endswith("It is saved when you commit.\n")
    with psycopg.connect(test_db_url) as conn:   # what PostgreSQL shows of alice's last query
        query = conn.execute("SELECT query FROM pg_stat_activity WHERE usename = 'alice'").fetchone()[0]
    assert "INSERT INTO public.patient" in query
    assert KEY not in query and "Jane" not in query

    run("rollback")
    assert saved_patients(test_db_url) == []
