"""The interactive `tdm>` prompt. Each command is a `do_<name>` method."""

import cmd
from typing import TextIO

import psycopg

from tdm.db import project_role


class Shell(cmd.Cmd):
    prompt = "tdm> "
    doc_header = "Commands (type help <command> for details):"

    def __init__(self, conn: psycopg.Connection, stdout: TextIO | None = None) -> None:
        super().__init__(stdout=stdout)   # all output goes to self.stdout (the screen, or a test's buffer)
        self.conn = conn

    def say(self, text: str) -> None:
        print(text, file=self.stdout)

    def onecmd(self, line: str) -> bool:
        if line == "EOF":   # Ctrl+D
            self.say("")
            return True
        try:
            return super().onecmd(line)
        except psycopg.Error as error:
            if self.conn.closed or self.conn.broken:
                self.say("Lost the connection to the database. Type exit and log in again.")
            else:
                self.say(f"Error: {error.diag.message_primary or error}")
            return False

    def emptyline(self) -> bool:
        return False   # by default cmd would repeat the last command

    def default(self, line: str) -> None:
        self.say(f"Unknown command: {line.split()[0]}. Type help to see the commands.")

    def do_whoami(self, arg: str) -> None:
        """Show who you are logged in as, your project role, and which database you are on."""
        user = self.conn.execute("SELECT current_user").fetchone()[0]
        self.say(f"{user} ({project_role(self.conn)}) on {self.conn.info.host}/{self.conn.info.dbname}")

    def do_exit(self, arg: str) -> bool:
        """Leave tdm."""
        return True

    do_quit = do_exit
