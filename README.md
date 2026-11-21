# trainingDataManager

## Runing the project (macOS)
Create and activate a python virtual envirement (Python 3.11 or newer):
```bash
python -m venv venv
source venv/bin/activate
```
If your Python is older (`python3 --version`), create the environment with uv instead:
```bash
brew install uv
uv venv venv --python 3.12 --seed
source venv/bin/activate
```

Install requirements:
``` bash
pip install -r requirements.txt
```

To connect to the postgre server create a file named `.env` with your credential:
``` bash
# Postgres — your database connection
DATABASE_URL="..."
DATABASE_URL_POOLED="..."
```
(if you dont have those url ask them to the neon ai assistante)

Admins and medical users also need the team's key that encrypts patients' personal data, in the same `.env`:
``` bash
TDM_DATA_KEY="..."
```
Everyone uses the same key: share it privately, never in the repo. Without it the personal data can't be read again, so keep a copy somewhere safe. To make a new one: `python -c "import secrets; print(secrets.token_urlsafe(32))"`. Developers don't need it.

## CLI (work in progress)
Install the `tdm` command once, inside the virtual environment:
```bash
pip install -e .
tdm
```
`tdm` takes the database address from `DATABASE_URL` in `.env`, then asks for your own PostgreSQL username and password (the ones inside the URL are not used). Type `help` to see the commands.

Users are managed inside `tdm` by an admin: `users`, `adduser <name> <group>`, `setgroup <name> <group>`, `removeuser <name>` (groups: `admin`, `medical_user`, `developer`).

Setting up user management on a new database (once, after the groups exist):
1. Log in to `tdm` as `neondb_owner` (its password is in the Neon console, under Connect).
2. Type `script sql/03_user_management.sql`.
3. Make yourself admin: `adduser <your name> admin`. Then log in as yourself from now on.

Admins and medical users add patients with `addpatient`. It asks for the sex (stored as is, for machine learning) and the personal details: name, address, date of birth, hospital number (stored encrypted with `TDM_DATA_KEY`).

How the CLI works: [docs/cli.md](docs/cli.md). What it needs from the database, the .edf conversion and Hugging Face: [docs/cli-interfaces.md](docs/cli-interfaces.md).

## Running the tests
Some tests need a throwaway PostgreSQL running in Docker. They never touch the Neon database.
```bash
docker compose up -d   # start the test database
pytest
docker compose down    # stop it (its data is deleted)
```
Without Docker those tests are skipped. GitHub runs all the tests on every push, on any branch.
