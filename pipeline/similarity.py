from collections.abc import Mapping


def compute_similarity_score(
    pool_a: Mapping[tuple[str, int], int], pool_b: Mapping[tuple[str, int], int]
) -> float:
    """Weighted Jaccard (Ruzicka) similarity between two Sets' own
    (part_num, color_id) quantity multisets, as a percentage: the sum of
    per-key mins (the overlap) over the sum of per-key maxes (the combined
    footprint). Symmetric and independent of ownership — unlike
    Buildability's compute_coverage_pct, which is directional (one pool
    covering one candidate's required quantities) and doesn't penalize
    whatever else the pool happens to hold. See CONTEXT.md's Similarity
    definition.
    """
    keys = pool_a.keys() | pool_b.keys()
    if not keys:
        return 0.0
    union = sum(max(pool_a.get(key, 0), pool_b.get(key, 0)) for key in keys)
    if union == 0:
        return 0.0
    intersection = sum(min(pool_a.get(key, 0), pool_b.get(key, 0)) for key in keys)
    return intersection / union * 100


def compute_similarity_topk(
    pools_by_set_num: Mapping[str, Mapping[tuple[str, int], int]], k: int = 10
) -> dict[str, list[tuple[str, float]]]:
    """The top-k most-similar other Sets per Set, not a full dense matrix —
    only similarity_topk is persisted (see CONTEXT.md's Similarity
    definition). Ties are broken by other_set_num ascending, so both
    truncation and ordering are deterministic.
    """
    set_nums = sorted(pools_by_set_num)
    scores: dict[str, list[tuple[str, float]]] = {set_num: [] for set_num in set_nums}
    for i, set_num_a in enumerate(set_nums):
        for set_num_b in set_nums[i + 1 :]:
            score = compute_similarity_score(pools_by_set_num[set_num_a], pools_by_set_num[set_num_b])
            scores[set_num_a].append((set_num_b, score))
            scores[set_num_b].append((set_num_a, score))

    return {
        set_num: sorted(candidates, key=lambda pair: (-pair[1], pair[0]))[:k]
        for set_num, candidates in scores.items()
    }
