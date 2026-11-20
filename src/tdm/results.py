"""Query results as tables: printed on screen, or saved to a file."""

from pathlib import Path

import polars as pl
import psycopg

SCREEN_ROWS = 50   # longer results show their first and last rows; save them to see everything


def to_table(cursor: psycopg.Cursor) -> pl.DataFrame:
    """The rows of the cursor's current result, as a polars table."""
    columns = _unique([column.name for column in cursor.description])
    rows = cursor.fetchall()
    try:
        table = pl.DataFrame(rows, schema=columns, orient="row", infer_schema_length=None)
    except (pl.exceptions.PolarsError, TypeError, ValueError, OverflowError):   # e.g. mixed JSON values
        text_rows = [[_text(value) for value in row] for row in rows]
        return pl.DataFrame(text_rows, schema=columns, orient="row")

    # Types polars only stores as Python objects (ranges, IP addresses, UUIDs...) become text,
    # so they print nicely and can be saved.
    unknown = [name for name, dtype in table.schema.items() if dtype == pl.Object]
    return table.with_columns(pl.Series(name, [_text(value) for value in table[name]]) for name in unknown)


def format_table(table: pl.DataFrame) -> str:
    with pl.Config(
        tbl_hide_column_data_types=True,
        tbl_hide_dataframe_shape=True,
        tbl_rows=SCREEN_ROWS,
        tbl_cols=-1,          # all columns
        fmt_str_lengths=60,   # cut very long text
    ):
        text = str(table)
    rows = table.height
    return f"{text}\n({rows} row{'' if rows == 1 else 's'})"


def save_table(table: pl.DataFrame, path: Path) -> None:
    if path.suffix == ".csv":
        # CSV holds text only, so binary columns (like encrypted data) are written as hex
        table.with_columns(pl.col(pl.Binary).bin.encode("hex")).write_csv(path)
    elif path.suffix == ".parquet":
        table.write_parquet(path)
    else:
        raise ValueError("use a file name ending in .csv or .parquet")


def _text(value: object) -> str | None:
    return None if value is None else str(value)


def _unique(names: list[str]) -> list[str]:
    """Polars needs different column names: "SELECT 1, 2" gives ?column? and ?column?_2."""
    seen: dict[str, int] = {}
    unique = []
    for name in names:
        seen[name] = seen.get(name, 0) + 1
        unique.append(name if seen[name] == 1 else f"{name}_{seen[name]}")
    return unique
