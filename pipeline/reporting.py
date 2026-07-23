import sqlite3
from collections.abc import Callable
from pathlib import Path

from pipeline.csvutil import read_csv

SCHEMA = """
CREATE TABLE themes (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    parent_id INTEGER
);

CREATE TABLE sets (
    set_num TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    year INTEGER NOT NULL,
    theme_id INTEGER NOT NULL,
    num_parts INTEGER NOT NULL,
    official_url TEXT,
    official_url_status TEXT NOT NULL
);

CREATE TABLE owned_boxes (
    set_num TEXT PRIMARY KEY,
    date_acquired TEXT,
    notes TEXT
);
"""


def primary_to_reporting(primary_dir: Path, db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.unlink(missing_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)

        _insert_csv(
            conn,
            primary_dir / "themes.csv",
            table="themes",
            columns=["id", "name", "parent_id"],
            to_row=lambda r: (int(r["id"]), r["name"], int(r["parent_id"]) if r["parent_id"] else None),
        )
        _insert_csv(
            conn,
            primary_dir / "sets.csv",
            table="sets",
            columns=["set_num", "name", "year", "theme_id", "num_parts", "official_url", "official_url_status"],
            to_row=lambda r: (
                r["set_num"],
                r["name"],
                int(r["year"]),
                int(r["theme_id"]),
                int(r["num_parts"]),
                r["official_url"],
                r["official_url_status"],
            ),
        )
        _insert_csv(
            conn,
            primary_dir / "owned_boxes.csv",
            table="owned_boxes",
            columns=["set_num", "date_acquired", "notes"],
            to_row=lambda r: (r["set_num"], r["date_acquired"], r["notes"]),
        )

        conn.commit()
    finally:
        conn.close()


def _insert_csv(
    conn: sqlite3.Connection,
    csv_path: Path,
    *,
    table: str,
    columns: list[str],
    to_row: Callable[[dict], tuple],
) -> None:
    placeholders = ", ".join("?" * len(columns))
    sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
    conn.executemany(sql, [to_row(r) for r in read_csv(csv_path)])
