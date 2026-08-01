import json
import re
from pathlib import Path

# A standard retail set_num's base (before the "-N" version suffix) is 5-6
# digits (issue #16) — non-numeric formats like "BONSAI-1" or "L0002198-1"
# tend to be small-batch/promotional releases instead.
_NUMERIC_SET_NUM_BASE = re.compile(r"^\d{5,6}$")

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


def load_render_parts(scope_config_path: Path) -> bool:
    """Whether the per-(part_num, color_id) thumbnail render step (issue
    #33) runs at all, mirroring load_render_candidates' gate above. Defaults
    to false: issue #29's go-ahead for this feature was conditional on "a
    deliberate one-time backfill strategy rather than folding the full
    backfill into a regular weekly run" (~10,410 pairs, ~4.4h at a naive
    1.7s/render) — this key stays off in config/scope.json until that
    backfill is triggered on purpose, after which per-pair content-hash
    caching keeps steady-state weekly cost under a minute.
    """
    return bool(_load_scope_config(scope_config_path).get("render_parts", False))


# Every min_* floor below defaults to 0 (no floor), both as the documented
# starting value and so a config/scope.json predating that key keeps its old
# behavior — same backward-compat rule as load_render_candidates above.


def load_require_numeric_candidate_set_num(scope_config_path: Path) -> bool:
    """Config-driven set_num format restriction for Candidate sets (issue
    #16): off by default so a config/scope.json predating this key keeps its
    old (wider) behavior, same backward-compat rule as load_render_candidates.
    """
    return bool(_load_scope_config(scope_config_path).get("require_numeric_candidate_set_num", False))


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

    Issue #16 flagged the original 30% starting value as skewing results
    toward small boxes matching mostly on minifigs/small vehicles, without
    proposing a replacement number of its own ("needs a decision, not just a
    number swap"). config/scope.json now sets this to 15% as that decision —
    still just a starting value, not a claim that 15% is the right number
    long-term, but a deliberate answer rather than a default left untouched.
    """
    return float(_load_scope_config(scope_config_path).get("min_buildability_coverage_pct", 0))


def load_min_similarity_score_pct(scope_config_path: Path) -> float:
    """Config-driven Similarity floor (issue #15): a pair scoring below this
    `similarity_topk.score` isn't written to the similarity_topk table at
    all, so it drops out of the Similarity page's results.

    Lowered from 30% to 15% in config/scope.json for the same issue #16
    reason as load_min_buildability_coverage_pct above — see its docstring.
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
        # itself no longer serves a product page for that set. Deliberately
        # inline rather than calling filter_candidates_by_retired_status
        # below: that function runs post-hoc, after determine_candidate_set_nums
        # has already returned, on official_url_status resolved for the
        # already-determined candidate set (see primary.py's
        # visible_candidate_set_nums) — here, "retail" needs the same check
        # baked into candidate determination itself, on the whole catalog's
        # eagerly-resolved status (see primary.py's resolve_links_eagerly).
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


def filter_candidates_by_numeric_set_num(
    candidate_set_nums: set[str], require_numeric_set_num: bool
) -> set[str]:
    """Applies config/scope.json's require_numeric_candidate_set_num toggle
    (issue #16) to an already-determined candidate set. Never applied to
    owned Boxes — an owned Box stays a Box regardless of its set_num's shape.
    """
    if not require_numeric_set_num:
        return candidate_set_nums
    return {
        set_num for set_num in candidate_set_nums if _NUMERIC_SET_NUM_BASE.match(set_num.split("-")[0])
    }


def filter_candidates_by_retired_status(candidate_set_nums: set[str], sets_rows: list[dict]) -> set[str]:
    """Drops official_url_status == 'retired' Candidates (issue #16): a
    retired set can't actually be bought, so it doesn't fit Discover's or
    Similarity's purpose. Unlike the two filters above, this isn't
    config-gated — it's a correctness fix for what "Candidate" means, not a
    tunable noise floor. Never applied to owned Boxes, which stay Boxes
    regardless of whether LEGO.com still sells them.
    """
    retired_set_nums = {row["set_num"] for row in sets_rows if row["official_url_status"] == "retired"}
    return candidate_set_nums - retired_set_nums
