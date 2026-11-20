"""Entry point: run with `tdm` or `python -m tdm`."""

import getpass
import sys

from dotenv import load_dotenv

from tdm import __version__
from tdm.db import LoginError, host_of, login, project_role, server_address
from tdm.shell import Shell


def main() -> int:
    load_dotenv()   # puts DATABASE_URL from .env into the environment
    print(f"tdm {__version__}")

    try:
        address = server_address()
        user = input("User: ").strip()
        password = getpass.getpass("Password: ")
        print(f"Connecting to {host_of(address)}...")
        conn = login(address, user, password)
    except LoginError as error:
        print(error)
        return 1
    except (KeyboardInterrupt, EOFError):   # Ctrl+C or Ctrl+D while logging in
        print()
        return 1

    with conn:
        print(f"Logged in as {user} ({project_role(conn)}). Type help to see the commands.")
        shell = Shell(conn)
        while True:
            try:
                shell.cmdloop()
                break
            except KeyboardInterrupt:   # Ctrl+C clears the line instead of quitting, like psql
                print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
