from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from pipeline.buildability import compute_coverage_pct, pool_quantities
from pipeline.csvutil import read_csv, write_csv
from pipeline.ldraw import render_with_ldview as _render_with_ldview
from pipeline.ldraw import resolve_ldraw_procedural_render
from pipeline.links import construct_official_url
from pipeline.links import resolve_official_link as _resolve_official_link
from pipeline.omr import fetch_omr_model_bytes as _fetch_omr_model_bytes
from pipeline.omr import resolve_ldraw_omr_render
from pipeline.scope import determine_candidate_set_nums, filter_candidates_by_min_num_parts
from pipeline.similarity import compute_similarity_topk


def intermediate_to_primary(
    intermediate_dir: Path,
    owned_sets_path: Path,
    owned_box_photos_path: Path,
    ldraw_parts_crosswalk_path: Path,
    ldraw_colors_crosswalk_path: Path,
    ldraw_omr_crosswalk_path: Path,
    render_dir: Path,
    primary_dir: Path,
    resolve_official_link: Callable[[str], tuple[str, str]] = _resolve_official_link,
    render: Callable[[Path, Path], None] = _render_with_ldview,
    fetch_omr_model: Callable[[str], bytes] = _fetch_omr_model_bytes,
    universe_scope: str = "owned_themes",
    render_candidates: bool = False,
    min_candidate_num_parts: int = 0,
    min_buildability_coverage_pct: float = 0.0,
    min_similarity_score_pct: float = 0.0,
) -> None:
    primary_dir.mkdir(parents=True, exist_ok=True)
    # Shared by every derived table below that stamps when it was computed —
    # buildability/similarity_topk's computed_at and set_renders' rendered_at
    # column alike.
    computed_at = datetime.now(UTC).isoformat()

    themes_rows = read_csv(intermediate_dir / "themes.csv")
    write_csv(primary_dir / "themes.csv", ["id", "name", "parent_id"], themes_rows)

    # Metadata tables are loaded in full regardless of universe_scope — only
    # per-set inventory data below is materialized for owned ∪ Candidate sets.
    # ldraw_part_id / ldraw_color_id are populated opportunistically from a
    # separately-maintained crosswalk (INITIAL_PROJECT_SPEC.md §13 flags that
    # whether Rebrickable's own dump carries this in bulk is still unconfirmed),
    # left NULL wherever that crosswalk has no entry — nothing in Phase 1 reads
    # these columns except the procedural renderer below.
    ldraw_color_id_by_color_id = {
        int(row["color_id"]): int(row["ldraw_color_id"]) for row in read_csv(ldraw_colors_crosswalk_path)
    }
    ldraw_part_id_by_part_num = {
        row["part_num"]: row["ldraw_part_id"] for row in read_csv(ldraw_parts_crosswalk_path)
    }
    # Separately-maintained crosswalk of set_num -> OMR download URL, present
    # only for sets the LDraw Official Model Repository has an exact
    # community-submitted model for — absent otherwise (see pipeline/omr.py).
    omr_url_by_set_num = {row["set_num"]: row["omr_url"] for row in read_csv(ldraw_omr_crosswalk_path)}

    colors_rows = read_csv(intermediate_dir / "colors.csv")
    for row in colors_rows:
        row["ldraw_color_id"] = ldraw_color_id_by_color_id.get(int(row["id"]))
    write_csv(primary_dir / "colors.csv", ["id", "name", "rgb", "is_trans", "ldraw_color_id"], colors_rows)

    parts_rows = read_csv(intermediate_dir / "parts.csv")
    for row in parts_rows:
        row["ldraw_part_id"] = ldraw_part_id_by_part_num.get(row["part_num"])
    write_csv(primary_dir / "parts.csv", ["part_num", "name", "part_cat_id", "ldraw_part_id"], parts_rows)

    minifigs_rows = read_csv(intermediate_dir / "minifigs.csv")
    write_csv(primary_dir / "minifigs.csv", ["fig_num", "name", "num_parts"], minifigs_rows)

    sets_rows = read_csv(intermediate_dir / "sets.csv")
    known_set_nums = {row["set_num"] for row in sets_rows}

    owned_rows = read_csv(owned_sets_path)
    for row in owned_rows:
        if row["set_num"] not in known_set_nums:
            raise ValueError(
                f"owned_sets seed references set_num {row['set_num']!r}, "
                "which isn't in the Rebrickable catalog dump"
            )
    write_csv(primary_dir / "owned_boxes.csv", ["set_num", "date_acquired", "notes"], owned_rows)
    owned_set_nums = {row["set_num"] for row in owned_rows}

    owned_box_photos_rows = read_csv(owned_box_photos_path)
    for row in owned_box_photos_rows:
        if row["set_num"] not in owned_set_nums:
            raise ValueError(
                f"owned_box_photos seed references set_num {row['set_num']!r}, which isn't an owned Box"
            )
    write_csv(
        primary_dir / "owned_box_photos.csv",
        ["set_num", "filename", "caption", "uploaded_at"],
        owned_box_photos_rows,
    )

    # A Set can only have one row in owned_box_photos here (see reporting.py's
    # schema comment) — last one in the seed wins if the same set_num were
    # ever repeated, mirroring the seed's own manually-maintained-CSV nature.
    photo_by_set_num = {row["set_num"]: row for row in owned_box_photos_rows}

    # "retail" candidate determination reads official_url_status off every row
    # (pipeline/scope.py's only available "currently buyable" signal), so that
    # scope can't avoid a full-catalog link check — resolve eagerly only for
    # it. owned_themes/all decide candidacy from theme_id/ownership alone, so
    # for them the (real, HTTP HEAD, one-set-at-a-time) check below only ever
    # runs for owned ∪ Candidate sets, not the whole catalog — see issue #14.
    resolve_links_eagerly = universe_scope == "retail"
    if resolve_links_eagerly:
        for row in sets_rows:
            row["official_url"], row["official_url_status"] = resolve_official_link(row["set_num"])

    candidate_set_nums = determine_candidate_set_nums(universe_scope, sets_rows, owned_set_nums)
    # config/scope.json's noise floor (issue #15): drops gear, keychains and
    # micro battle-figure packs from the Candidate set before anything below
    # (rendering, Buildability, Similarity) ever sees them.
    candidate_set_nums = filter_candidates_by_min_num_parts(candidate_set_nums, sets_rows, min_candidate_num_parts)

    # inventory_parts/inventory_minifigs are expensive at full-catalog scale,
    # so only owned ∪ Candidate sets get per-set inventory data materialized.
    materialized_set_nums = owned_set_nums | candidate_set_nums

    if not resolve_links_eagerly:
        for row in sets_rows:
            if row["set_num"] in materialized_set_nums:
                row["official_url"], row["official_url_status"] = resolve_official_link(row["set_num"])
            else:
                # Never checked: out of scope for owned_themes/all, so no
                # live HTTP request is made for it — official_url is still
                # populated (naive construction, no network) so "unchecked"
                # never means "we have no idea what the URL might be."
                row["official_url"] = construct_official_url(row["set_num"])
                row["official_url_status"] = "unchecked"

    write_csv(
        primary_dir / "sets.csv",
        ["set_num", "name", "year", "theme_id", "num_parts", "official_url", "official_url_status"],
        sets_rows,
    )
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

    # Image priority order (INITIAL_PROJECT_SPEC.md §10): a user photo always
    # wins outright; failing that, an LDraw OMR render if the crosswalk has an
    # exact-set match; everything else falls through to the procedural
    # renderer, which itself falls back to 'none' when zero parts resolve via
    # the crosswalk or the renderer fails. render_candidates (config/scope.json,
    # starting false) extends this same treatment to Candidate sets — off by
    # default so the weekly pipeline's CI time doesn't blow up as the Universe
    # scope widens (INITIAL_PROJECT_SPEC.md §10's "Scope toggle" rationale);
    # Candidates never have a user photo (owned-sets-only), so they fall
    # straight to OMR/procedural.
    render_set_nums = owned_set_nums | candidate_set_nums if render_candidates else owned_set_nums
    set_renders_rows = []
    for set_num in sorted(render_set_nums):
        photo = photo_by_set_num.get(set_num)
        if photo is not None:
            set_renders_rows.append(
                {
                    "set_num": set_num,
                    "image_source": "user_photo",
                    "image_path": f"assets/owned-photos/{set_num}/{photo['filename']}",
                    # 100%: a user photo isn't a partial procedural render, so
                    # nothing was omitted the way ldraw_procedural's coverage tracks.
                    "render_coverage_pct": 100.0,
                    "rendered_at": computed_at,
                }
            )
            continue

        omr_row = resolve_ldraw_omr_render(
            set_num,
            omr_url_by_set_num,
            render_dir,
            computed_at,
            render=render,
            fetch=fetch_omr_model,
        )
        if omr_row is not None:
            set_renders_rows.append(omr_row)
            continue

        inventory_id = inventory_id_by_set_num.get(set_num)
        set_renders_rows.append(
            resolve_ldraw_procedural_render(
                set_num,
                inventory_parts_by_inventory_id.get(inventory_id, []),
                ldraw_part_id_by_part_num,
                ldraw_color_id_by_color_id,
                render_dir,
                computed_at,
                render=render,
            )
        )
    write_csv(
        primary_dir / "set_renders.csv",
        ["set_num", "image_source", "image_path", "render_coverage_pct", "rendered_at"],
        set_renders_rows,
    )

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

    # config/scope.json's min_buildability_coverage_pct floor (issue #15): a
    # Candidate below the floor gets no buildability row at all, the same
    # "isn't a Candidate for display purposes" signal absence already carries
    # elsewhere in this table (see reporting.py's schema comment) — so
    # Discover and Themes (which both derive their Candidate scope from this
    # table's presence) drop it automatically, with no separate JS filter.
    # Similarity does NOT derive its scope from this table — issue #15 only
    # asks it for a part-count and score floor, not this one — see
    # similarity.js's own comment on why it reads `inventories` instead.
    buildability_rows = []
    for set_num in sorted(candidate_set_nums):
        coverage_pct = compute_coverage_pct(_own_pool(set_num), owned_pool)
        if coverage_pct < min_buildability_coverage_pct:
            continue
        buildability_rows.append(
            {
                "set_num": set_num,
                "coverage_pct": coverage_pct,
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
            # config/scope.json's min_similarity_score_pct floor (issue #15):
            # a pair scoring below the floor is dropped from similarity_topk
            # entirely, so it never shows on the Similarity page. Rank keeps
            # its original (possibly gappy) value — it's only an ordering
            # key, never displayed — rather than being renumbered.
            if score < min_similarity_score_pct:
                continue
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
