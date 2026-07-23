import json
from pathlib import Path

from tests.test_pipeline import _run as _run_pipeline


def _run(tmp_path: Path) -> Path:
    """Runs the shared pipeline fixtures (see tests/test_pipeline.py's _run)
    and returns the exports dir it always writes to (tmp_path / "exports").
    """
    _run_pipeline(tmp_path)
    return tmp_path / "exports"


def test_available_parts_json_reflects_the_owned_brick_pool(tmp_path):
    """Mirrors test_pipeline.py's
    test_owned_brick_pool_sums_inventory_parts_across_boxes_sharing_the_same_part_and_color
    (25/25/4 quantities), plus the ldraw crosswalk ids from
    test_ldraw_crosswalk_is_populated_opportunistically_and_null_where_missing
    (color 15 has no crosswalk entry, so ldraw_color_id is null there).
    """
    available_parts = json.loads((_run(tmp_path) / "available_parts.json").read_text())

    assert available_parts == [
        {"part_num": "3001", "color_id": 0, "quantity": 25, "ldraw_part_id": "3001", "ldraw_color_id": 0},
        {"part_num": "3001", "color_id": 15, "quantity": 25, "ldraw_part_id": "3001", "ldraw_color_id": None},
        {"part_num": "3020", "color_id": 1, "quantity": 4, "ldraw_part_id": "3020", "ldraw_color_id": 1},
    ]


def test_available_parts_json_excludes_a_candidates_materialized_inventory(tmp_path):
    """21331-1 is a Candidate (not owned) under the default owned_themes
    scope — its materialized inventory (see
    test_owned_brick_pool_excludes_a_candidates_materialized_inventory) must
    not leak into the exported Owned brick pool either.
    """
    available_parts = json.loads((_run(tmp_path) / "available_parts.json").read_text())

    assert all(row["part_num"] != "3001" or row["color_id"] != 71 for row in available_parts)


def test_owned_sets_json_is_a_snapshot_of_owned_boxes_plus_set_metadata(tmp_path):
    owned_sets = json.loads((_run(tmp_path) / "owned_sets.json").read_text())

    assert owned_sets == [
        {
            "set_num": "10281-1",
            "name": "Bonsai Tree",
            "year": 2021,
            "theme_id": 158,
            "num_parts": 878,
            "date_acquired": "2022-06-01",
            "notes": "",
        },
        {
            "set_num": "75192-1",
            "name": "Millennium Falcon",
            "year": 2017,
            "theme_id": 1,
            "num_parts": 7541,
            "date_acquired": "2023-12-25",
            "notes": "Holiday gift",
        },
    ]


def test_owned_sets_json_excludes_a_candidate_set(tmp_path):
    """21331-1 is a Candidate under owned_themes, never an owned Box — it
    must not appear in the owned_sets.json snapshot.
    """
    owned_sets = json.loads((_run(tmp_path) / "owned_sets.json").read_text())

    assert {row["set_num"] for row in owned_sets} == {"10281-1", "75192-1"}
