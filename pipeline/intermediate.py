from pathlib import Path

from pipeline.csvutil import parse_bool, parse_int, parse_optional_int, parse_str, read_typed_csv, write_csv

# Typed mirror of Rebrickable's raw tables — still source-shaped, no project-specific
# logic. Column sets kept intentionally narrow to what this project ever reads;
# unused Rebrickable columns (e.g. sets.img_url) are dropped here, not carried
# forward as dead weight.
RAW_TABLES: dict[str, dict[str, object]] = {
    "themes": {"id": parse_int, "name": parse_str, "parent_id": parse_optional_int},
    "sets": {
        "set_num": parse_str,
        "name": parse_str,
        "year": parse_int,
        "theme_id": parse_int,
        "num_parts": parse_int,
    },
    "colors": {"id": parse_int, "name": parse_str, "rgb": parse_str, "is_trans": parse_bool},
    "parts": {"part_num": parse_str, "name": parse_str, "part_cat_id": parse_int},
    "minifigs": {"fig_num": parse_str, "name": parse_str, "num_parts": parse_int},
    "inventories": {"id": parse_int, "version": parse_int, "set_num": parse_str},
    "inventory_parts": {
        "inventory_id": parse_int,
        "part_num": parse_str,
        "color_id": parse_int,
        "quantity": parse_int,
        "is_spare": parse_bool,
    },
    "inventory_minifigs": {"inventory_id": parse_int, "fig_num": parse_str, "quantity": parse_int},
}


def raw_to_intermediate(raw_dir: Path, intermediate_dir: Path) -> None:
    intermediate_dir.mkdir(parents=True, exist_ok=True)
    for table, types in RAW_TABLES.items():
        rows = read_typed_csv(raw_dir / f"{table}.csv", types)
        write_csv(intermediate_dir / f"{table}.csv", types.keys(), rows)
