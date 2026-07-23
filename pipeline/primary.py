from collections.abc import Callable
from pathlib import Path

from pipeline.csvutil import read_csv, write_csv
from pipeline.links import resolve_official_link as _resolve_official_link


def intermediate_to_primary(
    intermediate_dir: Path,
    owned_sets_path: Path,
    primary_dir: Path,
    resolve_official_link: Callable[[str], tuple[str, str]] = _resolve_official_link,
) -> None:
    primary_dir.mkdir(parents=True, exist_ok=True)

    themes_rows = read_csv(intermediate_dir / "themes.csv")
    write_csv(primary_dir / "themes.csv", ["id", "name", "parent_id"], themes_rows)

    # Metadata tables are loaded in full regardless of universe_scope — only
    # per-set inventory data below is materialized for owned Boxes only.
    colors_rows = read_csv(intermediate_dir / "colors.csv")
    write_csv(primary_dir / "colors.csv", ["id", "name", "rgb", "is_trans"], colors_rows)

    parts_rows = read_csv(intermediate_dir / "parts.csv")
    write_csv(primary_dir / "parts.csv", ["part_num", "name", "part_cat_id"], parts_rows)

    minifigs_rows = read_csv(intermediate_dir / "minifigs.csv")
    write_csv(primary_dir / "minifigs.csv", ["fig_num", "name", "num_parts"], minifigs_rows)

    sets_rows = read_csv(intermediate_dir / "sets.csv")
    known_set_nums = {row["set_num"] for row in sets_rows}
    for row in sets_rows:
        row["official_url"], row["official_url_status"] = resolve_official_link(row["set_num"])
    write_csv(
        primary_dir / "sets.csv",
        ["set_num", "name", "year", "theme_id", "num_parts", "official_url", "official_url_status"],
        sets_rows,
    )

    owned_rows = read_csv(owned_sets_path)
    for row in owned_rows:
        if row["set_num"] not in known_set_nums:
            raise ValueError(
                f"owned_sets seed references set_num {row['set_num']!r}, "
                "which isn't in the Rebrickable catalog dump"
            )
    write_csv(primary_dir / "owned_boxes.csv", ["set_num", "date_acquired", "notes"], owned_rows)

    owned_set_nums = {row["set_num"] for row in owned_rows}
    owned_inventories_rows = _latest_inventory_per_set(
        read_csv(intermediate_dir / "inventories.csv"), owned_set_nums
    )
    write_csv(primary_dir / "inventories.csv", ["id", "version", "set_num"], owned_inventories_rows)

    owned_inventory_ids = {row["id"] for row in owned_inventories_rows}
    write_csv(
        primary_dir / "inventory_parts.csv",
        ["inventory_id", "part_num", "color_id", "quantity", "is_spare"],
        _rows_for_owned_inventories(read_csv(intermediate_dir / "inventory_parts.csv"), owned_inventory_ids),
    )
    write_csv(
        primary_dir / "inventory_minifigs.csv",
        ["inventory_id", "fig_num", "quantity"],
        _rows_for_owned_inventories(read_csv(intermediate_dir / "inventory_minifigs.csv"), owned_inventory_ids),
    )


def _rows_for_owned_inventories(rows: list[dict], owned_inventory_ids: set[str]) -> list[dict]:
    return [row for row in rows if row["inventory_id"] in owned_inventory_ids]


def _latest_inventory_per_set(inventories_rows: list[dict], owned_set_nums: set[str]) -> list[dict]:
    """Rebrickable can carry multiple inventory versions per set_num; a Box's
    contents are its latest version only, and only for owned Boxes — expensive
    per-set inventory data isn't materialized for the whole catalog.
    """
    latest_by_set: dict[str, dict] = {}
    for row in inventories_rows:
        if row["set_num"] not in owned_set_nums:
            continue
        current = latest_by_set.get(row["set_num"])
        if current is None or int(row["version"]) > int(current["version"]):
            latest_by_set[row["set_num"]] = row
    return list(latest_by_set.values())
