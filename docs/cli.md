# The CLI (`tdm`)

One prompt for everyone: log in with your own PostgreSQL account, then type commands or SQL at `tdm>`. **PostgreSQL decides who may do what**, not the CLI.

Setup: [README](../README.md). What the CLI needs from the database, conversion and Hugging Face: [cli-interfaces.md](cli-interfaces.md).

## Status

| Step | | |
|---|---|---|
| 1–3 | Setup, login, SQL and transactions | done |
| 4 | User management | done |
| 5 | Add patients (personal data encrypted) | done, on stand-in tables for now |
| 6–8 | `.edf` recordings, `.npy` files, downloads | waiting for conversion + Hugging Face code |

## Commands

| Command | Who |
|---|---|
| SQL ending with `;` (runs as one transaction) | everyone |
| `begin`, `commit`, `rollback`, `savepoint`, `isolation`, `readonly`, `script`, `save`, `whoami`, `users` | everyone |
| `adduser`, `setgroup`, `removeuser` | admin |
| `addpatient` | admin, medical_user |

`help` lists them all. Prompt: `tdm*>` = in a transaction, `tdm!>` = transaction failed, type `rollback`.

## How it works

- **Login:** address from `DATABASE_URL` in `.env`; username and password typed by each person.
- **SQL:** each line is its own transaction (all saved, or nothing), unless you type `begin`.
- **Users:** `sql/03_user_management.sql` has three functions that run with the owner's rights, callable only by `admin` (needed since PostgreSQL 16).
- **Patients:** sex goes to `patient`; name, address, birth date and hospital number go to `patient_identity`, encrypted with pgcrypto. The key is `TDM_DATA_KEY` in `.env`, shared privately, never in the repo.

## Files

- `src/tdm/`: `__main__.py` (start), `db.py` (connection), `shell.py` (commands), `results.py` (tables, CSV/parquet)
- `sql/03_user_management.sql`: user functions
- `tests/`: run with `pytest` (needs `docker compose up -d`); stand-in tables in `tests/placeholder_tables.sql`

## Rules

- Never commit `.env`.
- Create users with `adduser`, not in the Neon console.
