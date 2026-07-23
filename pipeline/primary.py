from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from pipeline.buildability import compute_coverage_pct, pool_quantities
from pipeline.csvutil import read_csv, write_csv
from pipeline.links import resolve_official_link as _resolve_official_link
from pipeline.scope import determine_candidate_set_nums
from pipeline.similarity import compute_similarity_topk


def intermediate_to_primary(
    intermediate_dir: Path,
    owned_sets_path: Path,
    primary_dir: Path,
    resolve_official_link: Callable[[str], tuple[str, str]] = _resolve_official_link,
    universe_scope: str = "owned_themes",
) -> None:
    primary_dir.mkdir(parents=True, exist_ok=True)

    themes_rows = read_csv(intermediate_dir / "themes.csv")
    write_csv(primary_dir / "themes.csv", ["id", "name", "parent_id"], themes_rows)

    # Metadata tables are loaded in full regardless of universe_scope — only
    # per-set inventory data below is materialized for owned ∪ Candidate sets.
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

    candidate_set_nums = determine_candidate_set_nums(universe_scope, sets_rows, owned_set_nums)

    # inventory_parts/inventory_minifigs are expensive at full-catalog scale,
    # so only owned ∪ Candidate sets get per-set inventory data materialized.
    materialized_set_nums = owned_set_nums | candidate_set_nums
    materialized_inventories_rows = _latest_inventory_per_set(
        read_csv(intermediate_dir / "inventories.csv"), materialized_set_nums
    )
    write_csv(primary_dir / "inventories.csv", ["id", "version", "set_num"], materialized_inventories_rows)

    inventory_id_by_set_num = {row["set_num"]: row["id"] for row in materialized_inventories_rows}
    materialized_inventory_ids = {row["id"] for row in materialized_inventories_rows}

    materialized_inventory_parts_rows = _rows_for_inventories(
        read_csv(intermediate_dir / "inventory_parts.csv"), materialized_inventory_ids
    )
    write_csv(
        primary_dir / "inventory_parts.csv",
        ["inventory_id", "part_num", "color_id", "quantity", "is_spare"],
        materialized_inventory_parts_rows,
    )
    write_csv(
        primary_dir / "inventory_minifigs.csv",
        ["inventory_id", "fig_num", "quantity"],
        _rows_for_inventories(read_csv(intermediate_dir / "inventory_minifigs.csv"), materialized_inventory_ids),
    )

    inventory_parts_by_inventory_id = _group_by_inventory_id(materialized_inventory_parts_rows)
    owned_inventory_ids = {
        inventory_id_by_set_num[set_num] for set_num in owned_set_nums if set_num in inventory_id_by_set_num
    }
    owned_pool = pool_quantities(
        row for inventory_id in owned_inventory_ids for row in inventory_parts_by_inventory_id.get(inventory_id, [])
    )

    def _own_pool(set_num: str) -> dict[tuple[str, int], int]:
        """A Set's own (part_num, color_id) quantities, via its materialized
        inventory — the two-hop set_num -> inventory_id -> parts lookup
        shared by both Buildability's required-quantities below and
        Similarity's per-set pools further down.
        """
        inventory_id = inventory_id_by_set_num.get(set_num)
        return pool_quantities(inventory_parts_by_inventory_id.get(inventory_id, []))

    computed_at = datetime.now(UTC).isoformat()
    buildability_rows = []
    for set_num in sorted(candidate_set_nums):
        buildability_rows.append(
            {
                "set_num": set_num,
                "coverage_pct": compute_coverage_pct(_own_pool(set_num), owned_pool),
                "computed_at": computed_at,
            }
        )
    write_csv(primary_dir / "buildability.csv", ["set_num", "coverage_pct", "computed_at"], buildability_rows)

    # Similarity is symmetric and independent of ownership, so it's computed
    # across owned ∪ Candidate sets (materialized_set_nums) rather than
    # owned-pool-vs-candidate like Buildability above.
    pools_by_set_num = {set_num: _own_pool(set_num) for set_num in materialized_set_nums}
    similarity_topk_rows = []
    for set_num, topk in compute_similarity_topk(pools_by_set_num).items():
        for rank, (other_set_num, score) in enumerate(topk, start=1):
            similarity_topk_rows.append(
                {
                    "set_num": set_num,
                    "other_set_num": other_set_num,
                    "rank": rank,
                    "score": score,
                    "computed_at": computed_at,
                }
            )
    write_csv(
        primary_dir / "similarity_topk.csv",
        ["set_num", "other_set_num", "rank", "score", "computed_at"],
        similarity_topk_rows,
    )


def _rows_for_inventories(rows: list[dict], inventory_ids: set[str]) -> list[dict]:
    return [row for row in rows if row["inventory_id"] in inventory_ids]


def _group_by_inventory_id(inventory_parts_rows: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for row in inventory_parts_rows:
        grouped.setdefault(row["inventory_id"], []).append(row)
    return grouped


def _latest_inventory_per_set(inventories_rows: list[dict], set_nums: set[str]) -> list[dict]:
    """Rebrickable can carry multiple inventory versions per set_num; a Box's
    (or Candidate's) contents are its latest version only, and only for
    owned ∪ Candidate sets — expensive per-set inventory data isn't
    materialized for the whole catalog.
    """
    latest_by_set: dict[str, dict] = {}
    for row in inventories_rows:
        if row["set_num"] not in set_nums:
            continue
        current = latest_by_set.get(row["set_num"])
        if current is None or int(row["version"]) > int(current["version"]):
            latest_by_set[row["set_num"]] = row
    return list(latest_by_set.values())
