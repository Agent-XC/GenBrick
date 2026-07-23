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

-- No separate candidate_sets table: buildability holds exactly one row per
-- Candidate (see intermediate_to_primary), so its presence there already is
-- the "is a Candidate" signal — a second table would just duplicate it.
CREATE TABLE buildability (
    set_num TEXT PRIMARY KEY REFERENCES sets (set_num),
    coverage_pct REAL NOT NULL,
    computed_at TEXT NOT NULL
);

-- Sparse top-10-per-set, not a full dense matrix (see CONTEXT.md's
-- Similarity definition). Symmetric and independent of ownership, so unlike
-- buildability this holds rows for owned Sets too, not just Candidates.
CREATE TABLE similarity_topk (
    set_num TEXT NOT NULL REFERENCES sets (set_num),
    other_set_num TEXT NOT NULL REFERENCES sets (set_num),
    rank INTEGER NOT NULL,
    score REAL NOT NULL,
    computed_at TEXT NOT NULL,
    PRIMARY KEY (set_num, other_set_num)
);

-- inventory_parts/inventory_minifigs are materialized for owned ∪ Candidate
-- sets (see intermediate_to_primary), so the Owned brick pool and Figurines
-- totals must filter through owned_boxes rather than pooling the whole
-- table — otherwise a Candidate's inventory would leak into "owned" totals.
CREATE VIEW owned_brick_pool AS
SELECT inventory_parts.part_num, inventory_parts.color_id, SUM(inventory_parts.quantity) AS quantity
FROM inventory_parts
JOIN inventories ON inventories.id = inventory_parts.inventory_id
JOIN owned_boxes ON owned_boxes.set_num = inventories.set_num
GROUP BY inventory_parts.part_num, inventory_parts.color_id;

CREATE VIEW owned_minifigs AS
SELECT inventory_minifigs.fig_num, SUM(inventory_minifigs.quantity) AS quantity
FROM inventory_minifigs
JOIN inventories ON inventories.id = inventory_minifigs.inventory_id
JOIN owned_boxes ON owned_boxes.set_num = inventories.set_num
GROUP BY inventory_minifigs.fig_num;
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
        _insert_csv(
            conn,
            primary_dir / "buildability.csv",
            table="buildability",
            columns=["set_num", "coverage_pct", "computed_at"],
            to_row=lambda r: (r["set_num"], float(r["coverage_pct"]), r["computed_at"]),
        )
        _insert_csv(
            conn,
            primary_dir / "similarity_topk.csv",
            table="similarity_topk",
            columns=["set_num", "other_set_num", "rank", "score", "computed_at"],
            to_row=lambda r: (
                r["set_num"],
                r["other_set_num"],
                int(r["rank"]),
                float(r["score"]),
                r["computed_at"],
            ),
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
