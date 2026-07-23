import pytest

from pipeline.buildability import compute_coverage_pct, pool_quantities


def test_a_part_needed_beyond_what_is_owned_is_covered_only_up_to_the_owned_quantity():
    """A Candidate needing more of a part than owned: min(owned_qty,
    required_qty) caps coverage at what's actually in the pool.
    """
    required = {("3020", 1): 10}
    owned_pool = {("3020", 1): 4}

    assert compute_coverage_pct(required, owned_pool) == pytest.approx(40.0)


def test_a_required_part_color_absent_from_the_owned_pool_contributes_zero_coverage():
    """A part/color with zero owned quantity: absence from the pool means
    zero owned, not a KeyError or a skipped requirement.
    """
    required = {("3001", 71): 5}
    owned_pool = {("3001", 0): 25}

    assert compute_coverage_pct(required, owned_pool) == pytest.approx(0.0)


def test_coverage_pct_blends_full_partial_and_zero_coverage_across_required_lines():
    """21331-1's fixture shape from tests/fixtures/raw: fully covered
    (3001/0), zero coverage (3001/71), and partially covered (3020/1) lines
    combine into one overall percentage.
    """
    required = {("3020", 1): 10, ("3001", 71): 5, ("3001", 0): 5}
    owned_pool = {("3001", 0): 25, ("3001", 15): 25, ("3020", 1): 4}

    # covered = min(4,10) + min(0,5) + min(25,5) = 4 + 0 + 5 = 9, over 20 required
    assert compute_coverage_pct(required, owned_pool) == pytest.approx(45.0)


def test_a_candidate_with_no_required_parts_scores_zero_rather_than_dividing_by_zero():
    assert compute_coverage_pct({}, {("3001", 0): 25}) == 0.0


def test_pool_quantities_sums_duplicate_part_color_rows_and_casts_color_id_and_quantity():
    rows = [
        {"part_num": "3001", "color_id": "0", "quantity": "10"},
        {"part_num": "3001", "color_id": "0", "quantity": "15"},
        {"part_num": "3001", "color_id": "15", "quantity": "25"},
    ]

    assert pool_quantities(rows) == {("3001", 0): 25, ("3001", 15): 25}
