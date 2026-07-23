import sqlite3
from collections.abc import Callable
from pathlib import Path

from pipeline.csvutil import parse_bool, read_csv

SCHEMA = """
CREATE TABLE themes (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    parent_id INTEGER
);

CREATE TABLE colors (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    rgb TEXT NOT NULL,
    is_trans INTEGER NOT NULL
);

CREATE TABLE parts (
    part_num TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    part_cat_id INTEGER NOT NULL
);

CREATE TABLE minifigs (
    fig_num TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    num_parts INTEGER NOT NULL
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

CREATE TABLE inventories (
    id INTEGER PRIMARY KEY,
    version INTEGER NOT NULL,
    set_num TEXT NOT NULL
);

CREATE TABLE inventory_parts (
    inventory_id INTEGER NOT NULL,
    part_num TEXT NOT NULL,
    color_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    is_spare INTEGER NOT NULL
);

CREATE TABLE inventory_minifigs (
    inventory_id INTEGER NOT NULL,
    fig_num TEXT NOT NULL,
    quantity INTEGER NOT NULL
);

-- inventory_parts is already scoped to owned Boxes only (see
-- intermediate_to_primary's owned-inventory filtering), so the Owned brick
-- pool is just that table pooled and grouped — one disassembled collection,
-- not per-Box totals.
CREATE VIEW owned_brick_pool AS
SELECT part_num, color_id, SUM(quantity) AS quantity
FROM inventory_parts
GROUP BY part_num, color_id;
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
            primary_dir / "colors.csv",
            table="colors",
            columns=["id", "name", "rgb", "is_trans"],
            to_row=lambda r: (int(r["id"]), r["name"], r["rgb"], int(parse_bool(r["is_trans"]))),
        )
        _insert_csv(
            conn,
            primary_dir / "parts.csv",
            table="parts",
            columns=["part_num", "name", "part_cat_id"],
            to_row=lambda r: (r["part_num"], r["name"], int(r["part_cat_id"])),
        )
        _insert_csv(
            conn,
            primary_dir / "minifigs.csv",
            table="minifigs",
            columns=["fig_num", "name", "num_parts"],
            to_row=lambda r: (r["fig_num"], r["name"], int(r["num_parts"])),
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
        _insert_csv(
            conn,
            primary_dir / "inventories.csv",
            table="inventories",
            columns=["id", "version", "set_num"],
            to_row=lambda r: (int(r["id"]), int(r["version"]), r["set_num"]),
        )
        _insert_csv(
            conn,
            primary_dir / "inventory_parts.csv",
            table="inventory_parts",
            columns=["inventory_id", "part_num", "color_id", "quantity", "is_spare"],
            to_row=lambda r: (
                int(r["inventory_id"]),
                r["part_num"],
                int(r["color_id"]),
                int(r["quantity"]),
                int(parse_bool(r["is_spare"])),
            ),
        )
        _insert_csv(
            conn,
            primary_dir / "inventory_minifigs.csv",
            table="inventory_minifigs",
            columns=["inventory_id", "fig_num", "quantity"],
            to_row=lambda r: (int(r["inventory_id"]), r["fig_num"], int(r["quantity"])),
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
