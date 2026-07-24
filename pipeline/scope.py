import json
from pathlib import Path

# Expansion order per CONTEXT.md's Universe scope definition: owned_themes is
# the narrowest starting point, all is the whole Rebrickable catalog.
ALLOWED_UNIVERSE_SCOPES = ("owned_themes", "retail", "all")


def load_universe_scope(scope_config_path: Path) -> str:
    universe_scope = _load_scope_config(scope_config_path)["universe_scope"]
    if universe_scope not in ALLOWED_UNIVERSE_SCOPES:
        raise ValueError(
            f"config/scope.json: unknown universe_scope {universe_scope!r}, "
            f"expected one of {ALLOWED_UNIVERSE_SCOPES}"
        )
    return universe_scope


def _load_scope_config(scope_config_path: Path) -> dict:
    return json.loads(scope_config_path.read_text())


def load_render_candidates(scope_config_path: Path) -> bool:
    """Whether the image-resolution pipeline (OMR/procedural render) also
    runs for Candidate sets, not just owned ones — see CONTEXT.md's Candidate
    set definition and INITIAL_PROJECT_SPEC.md §10's "Scope toggle". Defaults
    to false (link-out only) both as the documented starting value and so a
    config/scope.json predating this flag keeps its old behavior.
    """
    return bool(_load_scope_config(scope_config_path).get("render_candidates", False))


# Every min_* floor below defaults to 0 (no floor), both as the documented
# starting value and so a config/scope.json predating that key keeps its old
# behavior — same backward-compat rule as load_render_candidates above.


def load_min_candidate_num_parts(scope_config_path: Path) -> int:
    """Config-driven part-count floor for Candidate sets (issue #15): drops
    gear, keychains, book/catalog entries and micro battle-figure packs from
    Discover/Similarity/Themes.
    """
    return int(_load_scope_config(scope_config_path).get("min_candidate_num_parts", 0))


def load_min_buildability_coverage_pct(scope_config_path: Path) -> float:
    """Config-driven Buildability floor (issue #15): a Candidate below this
    `buildability.coverage_pct` isn't written to the buildability table at
    all, so it drops out of Discover and Themes alike.
    """
    return float(_load_scope_config(scope_config_path).get("min_buildability_coverage_pct", 0))


def load_min_similarity_score_pct(scope_config_path: Path) -> float:
    """Config-driven Similarity floor (issue #15): a pair scoring below this
    `similarity_topk.score` isn't written to the similarity_topk table at
    all, so it drops out of the Similarity page's results.
    """
    return float(_load_scope_config(scope_config_path).get("min_similarity_score_pct", 0))


def determine_candidate_set_nums(
    universe_scope: str, sets_rows: list[dict], owned_set_nums: set[str]
) -> set[str]:
    """A Set that isn't owned but falls within `universe_scope` — see
    CONTEXT.md's Candidate set definition. Widens in the order
    owned_themes -> retail -> all with no schema change: every scope just
    changes which non-owned set_nums this returns.
    """
    if universe_scope not in ALLOWED_UNIVERSE_SCOPES:
        raise ValueError(
            f"unknown universe_scope {universe_scope!r}, expected one of {ALLOWED_UNIVERSE_SCOPES}"
        )

    non_owned_rows = [row for row in sets_rows if row["set_num"] not in owned_set_nums]

    if universe_scope == "all":
        return {row["set_num"] for row in non_owned_rows}

    if universe_scope == "retail":
        # No dedicated "currently buyable" flag in the Rebrickable dump — the
        # official_url_status resolved by pipeline/links.py (a real LEGO.com
        # check) is the closest available signal: "retired" means LEGO.com
        # itself no longer serves a product page for that set.
        return {row["set_num"] for row in non_owned_rows if row["official_url_status"] != "retired"}

    # owned_themes: candidates are limited to themes the owner already has at
    # least one Box in.
    owned_theme_ids = {row["theme_id"] for row in sets_rows if row["set_num"] in owned_set_nums}
    return {row["set_num"] for row in non_owned_rows if row["theme_id"] in owned_theme_ids}


def filter_candidates_by_min_num_parts(
    candidate_set_nums: set[str], sets_rows: list[dict], min_num_parts: int
) -> set[str]:
    """Applies config/scope.json's min_candidate_num_parts floor (issue #15)
    to an already-determined candidate set. Never applied to owned Boxes —
    only Candidates go through this noise filter, since an owned Box stays a
    Box regardless of its part count.
    """
    if min_num_parts <= 0:
        return candidate_set_nums
    num_parts_by_set_num = {row["set_num"]: int(row["num_parts"]) for row in sets_rows}
    return {
        set_num for set_num in candidate_set_nums if num_parts_by_set_num.get(set_num, 0) >= min_num_parts
    }
