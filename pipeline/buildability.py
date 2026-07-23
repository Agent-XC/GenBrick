from collections.abc import Iterable, Mapping


def pool_quantities(inventory_parts_rows: Iterable[Mapping]) -> dict[tuple[str, int], int]:
    """Sum inventory_parts-shaped rows into a (part_num, color_id) -> quantity
    pool. Shared by both the owned pool and a candidate's required quantities
    below — the same aggregation, just over a different row subset.
    """
    pool: dict[tuple[str, int], int] = {}
    for row in inventory_parts_rows:
        key = (row["part_num"], int(row["color_id"]))
        pool[key] = pool.get(key, 0) + int(row["quantity"])
    return pool


def compute_coverage_pct(
    required: Mapping[tuple[str, int], int], owned_pool: Mapping[tuple[str, int], int]
) -> float:
    """Buildability: min(owned_qty, required_qty) summed over a candidate's
    required (part_num, color_id) quantities, divided by total required
    quantity. A (part_num, color_id) absent from `owned_pool` counts as zero
    owned. See CONTEXT.md's Buildability definition.
    """
    total_required = sum(required.values())
    if total_required == 0:
        return 0.0
    covered = sum(min(owned_pool.get(key, 0), quantity) for key, quantity in required.items())
    return covered / total_required * 100
