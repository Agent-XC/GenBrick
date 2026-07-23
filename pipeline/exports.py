import json
import sqlite3
from pathlib import Path

AVAILABLE_PARTS_QUERY = """
SELECT
    owned_brick_pool.part_num,
    owned_brick_pool.color_id,
    owned_brick_pool.quantity,
    parts.ldraw_part_id,
    colors.ldraw_color_id
FROM owned_brick_pool
JOIN parts ON parts.part_num = owned_brick_pool.part_num
JOIN colors ON colors.id = owned_brick_pool.color_id
ORDER BY owned_brick_pool.part_num, owned_brick_pool.color_id
"""

OWNED_SETS_QUERY = """
SELECT
    owned_boxes.set_num,
    sets.name,
    sets.year,
    sets.theme_id,
    sets.num_parts,
    owned_boxes.date_acquired,
    owned_boxes.notes
FROM owned_boxes
JOIN sets ON sets.set_num = owned_boxes.set_num
ORDER BY owned_boxes.set_num
"""


def reporting_to_exports(db_path: Path, exports_dir: Path) -> None:
    """Produce the Phase-2-facing data contract (INITIAL_PROJECT_SPEC.md §15,
    README's Phase-2 export contract section): exports/available_parts.json
    (the Owned brick pool, crosswalked to LDraw ids) and exports/owned_sets.json
    (owned_boxes plus basic Set metadata), read from the reporting-layer
    SQLite DB after primary_to_reporting has built it.
    """
    exports_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        available_parts = [dict(row) for row in conn.execute(AVAILABLE_PARTS_QUERY)]
        owned_sets = [dict(row) for row in conn.execute(OWNED_SETS_QUERY)]
    finally:
        conn.close()

    _write_json(exports_dir / "available_parts.json", available_parts)
    _write_json(exports_dir / "owned_sets.json", owned_sets)


def _write_json(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps(rows, indent=2) + "\n")
