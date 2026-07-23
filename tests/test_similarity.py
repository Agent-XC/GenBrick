import pytest

from pipeline.buildability import compute_coverage_pct
from pipeline.similarity import compute_similarity_score, compute_similarity_topk


def test_identical_composition_multisets_score_100():
    pool = {("3001", 0): 10, ("3020", 1): 4}

    assert compute_similarity_score(pool, pool) == pytest.approx(100.0)


def test_disjoint_composition_multisets_score_zero():
    a = {("3001", 0): 10}
    b = {("3020", 1): 4}

    assert compute_similarity_score(a, b) == pytest.approx(0.0)


def test_score_is_symmetric_and_weighted_by_shared_and_exclusive_quantity():
    """Weighted Jaccard (Ruzicka): sum of per-key mins over sum of per-key
    maxes. (3001, 0) contributes min(10, 4)=4 to the intersection and
    max(10, 4)=10 to the union; (3020, 1) is exclusive to a and contributes
    0 to the intersection but 5 to the union.
    """
    a = {("3001", 0): 10, ("3020", 1): 5}
    b = {("3001", 0): 4}

    assert compute_similarity_score(a, b) == pytest.approx(4 / 15 * 100)
    assert compute_similarity_score(b, a) == pytest.approx(compute_similarity_score(a, b))


def test_two_empty_multisets_score_zero_rather_than_dividing_by_zero():
    assert compute_similarity_score({}, {}) == 0.0


def test_similarity_is_distinct_from_buildability_two_sets_can_overlap_without_either_being_buildable():
    """Similarity is symmetric and independent of ownership; Buildability is
    directional (one pool covering one candidate's required quantities) and
    ignores whatever else the pool holds. A's pool: 10 of a shared part plus
    5 of a part exclusive to A. B's pool: 5 of the shared part plus 5 of a
    part exclusive to B — real overlap on the shared part, but each also
    carries its own exclusive part the other lacks entirely.
    """
    pool_a = {("3001", 0): 10, ("3010", 5): 5}
    pool_b = {("3001", 0): 5, ("3020", 1): 5}

    similarity = compute_similarity_score(pool_a, pool_b)
    # min(10,5) + min(5,0) + min(0,5) = 5, over max(10,5) + 5 + 5 = 20
    assert similarity == pytest.approx(25.0)

    # Neither Set is fully buildable from the other, despite the nonzero
    # composition overlap Similarity reports above.
    buildability_of_b_from_a = compute_coverage_pct(pool_b, pool_a)
    buildability_of_a_from_b = compute_coverage_pct(pool_a, pool_b)
    assert buildability_of_b_from_a == pytest.approx(50.0)
    assert buildability_of_a_from_b == pytest.approx(100 / 3)
    assert buildability_of_b_from_a < 100.0
    assert buildability_of_a_from_b < 100.0
    assert similarity != pytest.approx(buildability_of_b_from_a)
    assert similarity != pytest.approx(buildability_of_a_from_b)


def test_topk_is_sorted_by_score_descending_then_other_set_num_ascending_on_ties():
    pools = {"S0": {("p", 0): 100}}
    # S1..S9: distinct descending scores 99%..91%.
    for i in range(1, 10):
        pools[f"S{i}"] = {("p", 0): 100 - i}
    # S10 and S11 tie at 89% (would-be rank 10 and 11) — S10 wins the tie by
    # sorting first alphabetically.
    pools["S10"] = {("p", 0): 89}
    pools["S11"] = {("p", 0): 89}
    # S12 scores lower than every tied/untied entry above and is truncated.
    pools["S12"] = {("p", 0): 80}

    topk = compute_similarity_topk(pools, k=10)

    assert [other for other, _score in topk["S0"]] == [
        "S1",
        "S2",
        "S3",
        "S4",
        "S5",
        "S6",
        "S7",
        "S8",
        "S9",
        "S10",
    ]


def test_topk_is_computed_for_every_set_not_just_one_anchor():
    pools = {
        "A": {("p", 0): 10},
        "B": {("p", 0): 10},
        "C": {("p", 0): 1},
    }

    topk = compute_similarity_topk(pools, k=10)

    assert topk["A"] == [("B", pytest.approx(100.0)), ("C", pytest.approx(10.0))]
    assert topk["B"] == [("A", pytest.approx(100.0)), ("C", pytest.approx(10.0))]
    assert topk["C"] == [("A", pytest.approx(10.0)), ("B", pytest.approx(10.0))]


def test_topk_of_a_single_set_universe_is_empty():
    assert compute_similarity_topk({"A": {("p", 0): 10}}, k=10) == {"A": []}
