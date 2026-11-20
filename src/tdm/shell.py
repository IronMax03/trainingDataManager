"""The interactive `tdm>` prompt.

A line that starts with a tdm command (help, begin, commit, ...) runs that command's `do_<name>` method.
Anything else that looks like SQL is sent to PostgreSQL. SQL can take several lines and ends with ";".
"""

import cmd
from pathlib import Path
from typing import TextIO

import polars as pl
import psycopg
from psycopg import sql
from psycopg.pq import TransactionStatus

from tdm.db import project_role
from tdm.results import format_table, save_table, to_table

ISOLATION_LEVELS = ["read committed", "repeatable read", "serializable"]

# First words that mark a line as SQL even before its closing ";"
SQL_WORDS = {
    "select", "insert", "update", "delete", "with", "create", "alter", "drop", "grant", "revoke",
    "truncate", "explain", "show", "set", "reset", "values", "table", "call", "do", "analyze",
    "vacuum", "comment", "lock", "refresh",
}


class Shell(cmd.Cmd):
    doc_header = "Commands (type help <command> for details):"

    def __init__(self, conn: psycopg.Connection, stdout: TextIO | None = None) -> None:
        super().__init__(stdout=stdout)   # all output goes to self.stdout (the screen, or a test's buffer)
        self.conn = conn
        self.conn.add_notice_handler(self.show_notice)
        self.sql_lines: list[str] = []      # SQL being typed, until a line ends with ";"
        self.isolation = "read committed"   # PostgreSQL's default
        self.read_only = False
        self.last_result: pl.DataFrame | None = None   # what the save command writes
        self.update_prompt()

    def say(self, text: str) -> None:
        print(text, file=self.stdout)

    # ---- Reading what the user types

    def run(self) -> None:
        """Show the prompt until exit. Ctrl+C drops a half-typed line instead of quitting, like psql."""
        while True:
            try:
                self.cmdloop()
                return
            except KeyboardInterrupt:
                self.say("")
                self.sql_lines.clear()
                self.update_prompt()

    def onecmd(self, line: str) -> bool:
        if line == "EOF":   # Ctrl+D
            self.say("")
            return self.do_exit("")
        try:
            command = None if self.sql_lines else self.as_command(line)
            if command:
                stop = super().onecmd(command)
            elif self.sql_lines or self.is_sql(line):
                stop = self.add_sql_line(line)
            else:
                stop = super().onecmd(line)   # an empty line, or an unknown command
        except psycopg.Error as error:
            self.report(error)
            stop = False
        self.update_prompt()
        return stop

    def as_command(self, line: str) -> str | None:
        """The line with its first word in lowercase, if that word is a tdm command ("COMMIT;" -> "commit;")."""
        first, _, rest = line.strip().partition(" ")
        if first and hasattr(self, f"do_{first.rstrip(';').lower()}"):
            return f"{first.lower()} {rest}".strip()
        return None

    def is_sql(self, line: str) -> bool:
        words = line.split()
        return bool(words) and (words[0].lower() in SQL_WORDS or line.rstrip().endswith(";"))

    def add_sql_line(self, line: str) -> bool:
        self.sql_lines.append(line)
        if line.rstrip().endswith(";"):
            text = "\n".join(self.sql_lines)
            self.sql_lines.clear()
            self.run_sql(text)
        return False

    def emptyline(self) -> bool:
        return False   # by default cmd would repeat the last command

    def default(self, line: str) -> None:
        self.say(f"Unknown command: {line.split()[0]}. Type help to see the commands (and end SQL with ;).")

    # ---- Running SQL

    def run_sql(self, text: str) -> None:
        """Run SQL inside a transaction: the one the user opened with begin, or else a new one
        that is committed at the end. If anything fails, that new transaction is rolled back."""
        own_transaction = not self.in_transaction()
        if own_transaction:
            self.conn.execute(self.begin_sql())

        try:
            cursor = self.conn.execute(text)
        except (psycopg.Error, KeyboardInterrupt) as problem:   # KeyboardInterrupt = Ctrl+C
            if own_transaction and self.connected():
                self.conn.execute("ROLLBACK")
            self.report(problem)
            if own_transaction and self.connected():
                self.say("Rolled back: nothing was saved.")
            return

        if own_transaction:
            try:
                self.conn.execute("COMMIT")
            except psycopg.Error as error:   # e.g. a serializable transaction that conflicts with another
                self.report(error)
                self.say("Nothing was saved.")
                return
        self.show(cursor)

    def show(self, cursor: psycopg.Cursor) -> None:
        """Print each result: a table when there are rows, otherwise what PostgreSQL did ("INSERT 0 1")."""
        while True:
            if cursor.description is not None:
                self.last_result = to_table(cursor)
                self.say(format_table(self.last_result))
            elif cursor.statusmessage:
                self.say(cursor.statusmessage)
            if not cursor.nextset():
                return

    def report(self, problem: BaseException) -> None:
        """Explain what went wrong in a line or two, never a stack trace."""
        if not self.connected():
            self.say("Lost the connection to the database. Type exit and log in again.")
            return
        if isinstance(problem, psycopg.Error):
            self.say(f"Error: {problem.diag.message_primary or problem}")
            if problem.diag.message_hint:
                self.say(f"Hint: {problem.diag.message_hint}")
        else:
            self.say("Query cancelled.")
        if self.conn.info.transaction_status == TransactionStatus.INERROR:
            self.say("The transaction failed: type rollback (or rollback to <savepoint>) to go on.")

    def show_notice(self, notice: psycopg.errors.Diagnostic) -> None:
        self.say(f"{notice.severity}: {notice.message_primary}")   # e.g. NOTICE: table "x" does not exist, skipping

    # ---- Transaction state

    def connected(self) -> bool:
        return not (self.conn.closed or self.conn.broken)

    def in_transaction(self) -> bool:
        return self.conn.info.transaction_status in (TransactionStatus.INTRANS, TransactionStatus.INERROR)

    def begin_sql(self) -> str:
        access = "READ ONLY" if self.read_only else "READ WRITE"
        return f"BEGIN ISOLATION LEVEL {self.isolation.upper()} {access}"

    def mode(self) -> str:
        return self.isolation + (", read only" if self.read_only else "")

    def update_prompt(self) -> None:
        if self.sql_lines:
            self.prompt = "...> "   # waiting for the rest of the SQL
        else:
            status = self.conn.info.transaction_status
            mark = {TransactionStatus.INTRANS: "*", TransactionStatus.INERROR: "!"}.get(status, "")
            self.prompt = f"tdm{mark}> "

    # ---- Commands

    def do_help(self, arg: str) -> None:
        """Show the commands, or details about one: help <command>"""
        super().do_help(arg)
        if not arg:
            self.say("To run SQL, type it and end it with ; (it can take several lines).\n")

    def do_begin(self, arg: str) -> None:
        """Start a transaction. Nothing is saved until commit, and rollback undoes it all."""
        if self.in_transaction():
            self.say("A transaction is already open: commit or rollback it first.")
            return
        self.conn.execute(self.begin_sql())
        self.say(f"Transaction started ({self.mode()}).")

    def do_commit(self, arg: str) -> None:
        """Save everything done since begin."""
        if not self.in_transaction():
            self.say("No transaction is open.")
            return
        failed = self.conn.info.transaction_status == TransactionStatus.INERROR
        self.conn.execute("COMMIT")   # PostgreSQL rolls back instead if the transaction had an error
        if failed:
            self.say("Rolled back: the transaction had an error, so nothing was saved.")
        else:
            self.say("Committed: changes saved.")

    def do_rollback(self, arg: str) -> None:
        """Undo everything since begin. "rollback to <name>" only undoes what came after savepoint <name>."""
        words = _words(arg)
        if words[1:2] and words[1].lower() == "savepoint":   # also accept SQL's "rollback to savepoint <name>"
            del words[1]
        if not self.in_transaction():
            self.say("No transaction is open.")
        elif not words:
            self.conn.execute("ROLLBACK")
            self.say("Rolled back: nothing was saved.")
        elif len(words) == 2 and words[0].lower() == "to":
            self.conn.execute(sql.SQL("ROLLBACK TO SAVEPOINT {}").format(sql.Identifier(words[1])))
            self.say(f"Rolled back to savepoint {words[1]}.")
        else:
            self.say("Usage: rollback   or   rollback to <savepoint>")

    def do_savepoint(self, arg: str) -> None:
        """Mark a point in the transaction to come back to with "rollback to <name>". Usage: savepoint <name>"""
        words = _words(arg)
        if len(words) != 1:
            self.say("Usage: savepoint <name>")
        elif not self.in_transaction():
            self.say("Savepoints only work inside a transaction: type begin first.")
        else:
            self.conn.execute(sql.SQL("SAVEPOINT {}").format(sql.Identifier(words[0])))
            self.say(f"Savepoint {words[0]} set.")

    def do_isolation(self, arg: str) -> None:
        """Isolation level of the next transactions: read committed (default), repeatable read or serializable."""
        level = " ".join(_words(arg)).lower()
        if level and level not in ISOLATION_LEVELS:
            self.say(f"Choose one of: {', '.join(ISOLATION_LEVELS)}.")
            return
        if level:
            self.isolation = level
        self.say(f"Next transactions: {self.mode()}.")

    def do_readonly(self, arg: str) -> None:
        """Make the next transactions read-only (readonly on) or normal again (readonly off)."""
        choice = " ".join(_words(arg)).lower()
        if choice not in ("", "on", "off"):
            self.say("Usage: readonly on   or   readonly off")
            return
        if choice:
            self.read_only = choice == "on"
        self.say(f"Next transactions: {self.mode()}.")

    def do_script(self, arg: str) -> None:
        """Run an SQL file as one transaction: everything in it is saved, or nothing. Usage: script <file.sql>"""
        name = arg.strip().rstrip(";")
        if not name:
            self.say("Usage: script <file.sql>")
            return
        path = Path(name).expanduser()
        try:
            text = path.read_text()
        except OSError as error:
            self.say(f"Can't read {path}: {error.strerror}.")
            return
        if not text.strip():
            self.say(f"{path} is empty.")
            return
        self.run_sql(text)

    def do_save(self, arg: str) -> None:
        """Save the last query result to a file. Usage: save <file.csv>  or  save <file.parquet>"""
        name = arg.strip().rstrip(";")
        if not name:
            self.say("Usage: save <file.csv>  or  save <file.parquet>")
            return
        if self.last_result is None:
            self.say("Nothing to save yet: run a query first.")
            return
        path = Path(name).expanduser()
        try:
            save_table(self.last_result, path)
        except (ValueError, OSError, pl.exceptions.PolarsError) as error:
            self.say(f"Can't save: {error}")
            return
        self.say(f"Saved {self.last_result.height} rows to {path}.")

    def do_whoami(self, arg: str) -> None:
        """Show who you are logged in as, your project role, and which database you are on."""
        user = self.conn.execute("SELECT current_user").fetchone()[0]
        self.say(f"{user} ({project_role(self.conn)}) on {self.conn.info.host}/{self.conn.info.dbname}")

    def do_exit(self, arg: str) -> bool:
        """Leave tdm. A transaction that is still open is rolled back."""
        if self.in_transaction() and self.connected():
            self.conn.execute("ROLLBACK")
            self.say("The open transaction was rolled back.")
        return True

    do_quit = do_exit


def _words(arg: str) -> list[str]:
    return arg.replace(";", " ").split()
