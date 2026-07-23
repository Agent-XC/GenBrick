from pathlib import Path

from pipeline.csvutil import read_csv, write_csv
from pipeline.links import construct_official_url


def intermediate_to_primary(intermediate_dir: Path, owned_sets_path: Path, primary_dir: Path) -> None:
    primary_dir.mkdir(parents=True, exist_ok=True)

    themes_rows = read_csv(intermediate_dir / "themes.csv")
    write_csv(primary_dir / "themes.csv", ["id", "name", "parent_id"], themes_rows)

    sets_rows = read_csv(intermediate_dir / "sets.csv")
    known_set_nums = {row["set_num"] for row in sets_rows}
    for row in sets_rows:
        row["official_url"] = construct_official_url(row["set_num"])
        row["official_url_status"] = "unchecked"
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
