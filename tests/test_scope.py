import json

import pytest

from pipeline.scope import (
    determine_candidate_set_nums,
    filter_candidates_by_min_num_parts,
    load_min_buildability_coverage_pct,
    load_min_candidate_num_parts,
    load_min_similarity_score_pct,
    load_render_candidates,
)

# Mirrors tests/fixtures/raw/sets.csv: 75192-1 (theme 1) and 10281-1 (theme
# 158) are owned; 21331-1 shares 10281-1's theme (158); 42100-1 sits in an
# unowned theme (200).
SETS_ROWS = [
    {"set_num": "75192-1", "theme_id": "1", "official_url_status": "ok"},
    {"set_num": "10281-1", "theme_id": "158", "official_url_status": "ok"},
    {"set_num": "21331-1", "theme_id": "158", "official_url_status": "ok"},
    {"set_num": "42100-1", "theme_id": "200", "official_url_status": "retired"},
]
OWNED_SET_NUMS = {"75192-1", "10281-1"}


def test_owned_themes_scope_includes_a_non_owned_set_sharing_an_owned_theme():
    candidates = determine_candidate_set_nums("owned_themes", SETS_ROWS, OWNED_SET_NUMS)

    assert "21331-1" in candidates


def test_owned_themes_scope_excludes_a_set_in_a_theme_the_owner_doesnt_own():
    """universe_scope filtering excluding an out-of-theme Set: 42100-1's
    theme (200) has no owned Box, so it isn't a Candidate under owned_themes.
    """
    candidates = determine_candidate_set_nums("owned_themes", SETS_ROWS, OWNED_SET_NUMS)

    assert "42100-1" not in candidates
    assert candidates == {"21331-1"}


def test_owned_set_nums_are_never_candidates_regardless_of_scope():
    for universe_scope in ("owned_themes", "retail", "all"):
        candidates = determine_candidate_set_nums(universe_scope, SETS_ROWS, OWNED_SET_NUMS)
        assert candidates.isdisjoint(OWNED_SET_NUMS)


def test_all_scope_includes_every_non_owned_set_widening_beyond_owned_themes():
    candidates = determine_candidate_set_nums("all", SETS_ROWS, OWNED_SET_NUMS)

    assert candidates == {"21331-1", "42100-1"}


def test_retail_scope_excludes_sets_whose_official_link_resolved_as_retired():
    candidates = determine_candidate_set_nums("retail", SETS_ROWS, OWNED_SET_NUMS)

    assert candidates == {"21331-1"}
    assert "42100-1" not in candidates  # official_url_status == "retired"


def test_an_unknown_universe_scope_is_rejected():
    with pytest.raises(ValueError, match="bogus_scope"):
        determine_candidate_set_nums("bogus_scope", SETS_ROWS, OWNED_SET_NUMS)


def test_load_render_candidates_defaults_false_when_key_is_absent(tmp_path):
    """config/scope.json shipped before this flag existed had no
    render_candidates key at all — an old config on disk must still resolve
    to the documented starting default (false) rather than raising.
    """
    scope_config = tmp_path / "scope.json"
    scope_config.write_text(json.dumps({"universe_scope": "owned_themes"}))

    assert load_render_candidates(scope_config) is False


def test_load_render_candidates_reads_true_when_flipped_on(tmp_path):
    scope_config = tmp_path / "scope.json"
    scope_config.write_text(json.dumps({"universe_scope": "owned_themes", "render_candidates": True}))

    assert load_render_candidates(scope_config) is True


@pytest.mark.parametrize(
    "loader",
    [load_min_candidate_num_parts, load_min_buildability_coverage_pct, load_min_similarity_score_pct],
)
def test_min_floor_loaders_default_to_zero_when_key_is_absent(tmp_path, loader):
    """A config/scope.json predating these floors had none of these keys —
    each loader must resolve to 0 (no floor) rather than raising, mirroring
    load_render_candidates' own backward-compat default.
    """
    scope_config = tmp_path / "scope.json"
    scope_config.write_text(json.dumps({"universe_scope": "owned_themes"}))

    assert loader(scope_config) == 0


@pytest.mark.parametrize(
    ("loader", "key", "value"),
    [
        (load_min_candidate_num_parts, "min_candidate_num_parts", 15),
        (load_min_buildability_coverage_pct, "min_buildability_coverage_pct", 30),
        (load_min_similarity_score_pct, "min_similarity_score_pct", 30),
    ],
)
def test_min_floor_loaders_read_the_configured_value(tmp_path, loader, key, value):
    scope_config = tmp_path / "scope.json"
    scope_config.write_text(json.dumps({"universe_scope": "owned_themes", key: value}))

    assert loader(scope_config) == value


def test_filter_candidates_by_min_num_parts_drops_candidates_below_the_floor():
    sets_rows = [
        {"set_num": "21331-1", "num_parts": 10},
        {"set_num": "42100-1", "num_parts": 4108},
    ]
    candidates = {"21331-1", "42100-1"}

    assert filter_candidates_by_min_num_parts(candidates, sets_rows, 15) == {"42100-1"}


def test_filter_candidates_by_min_num_parts_is_a_no_op_when_the_floor_is_zero():
    sets_rows = [{"set_num": "21331-1", "num_parts": 10}]
    candidates = {"21331-1"}

    assert filter_candidates_by_min_num_parts(candidates, sets_rows, 0) == {"21331-1"}
