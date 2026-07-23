import json
from pathlib import Path

# Expansion order per CONTEXT.md's Universe scope definition: owned_themes is
# the narrowest starting point, all is the whole Rebrickable catalog.
ALLOWED_UNIVERSE_SCOPES = ("owned_themes", "retail", "all")


def load_universe_scope(scope_config_path: Path) -> str:
    universe_scope = json.loads(scope_config_path.read_text())["universe_scope"]
    if universe_scope not in ALLOWED_UNIVERSE_SCOPES:
        raise ValueError(
            f"config/scope.json: unknown universe_scope {universe_scope!r}, "
            f"expected one of {ALLOWED_UNIVERSE_SCOPES}"
        )
    return universe_scope


def load_render_candidates(scope_config_path: Path) -> bool:
    """Whether the image-resolution pipeline (OMR/procedural render) also
    runs for Candidate sets, not just owned ones — see CONTEXT.md's Candidate
    set definition and INITIAL_PROJECT_SPEC.md §10's "Scope toggle". Defaults
    to false (link-out only) both as the documented starting value and so a
    config/scope.json predating this flag keeps its old behavior.
    """
    return bool(json.loads(scope_config_path.read_text()).get("render_candidates", False))


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
