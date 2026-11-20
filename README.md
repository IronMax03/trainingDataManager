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

## CLI (work in progress)
Install the `tdm` command once, inside the virtual environment:
```bash
pip install -e .
tdm
```
What the CLI needs from the database, the .edf conversion and Hugging Face: [docs/cli-interfaces.md](docs/cli-interfaces.md).

## Running the tests
Some tests need a throwaway PostgreSQL running in Docker. They never touch the Neon database.
```bash
docker compose up -d   # start the test database
pytest
docker compose down    # stop it (its data is deleted)
```
Without Docker those tests are skipped. GitHub runs all the tests on every push, on any branch.
