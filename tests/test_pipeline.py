import sqlite3

import pytest

from pipeline.run import run_pipeline
from tests.conftest import FIXTURE_OWNED_SETS, FIXTURE_RAW, _fake_resolve_official_link


def _run(tmp_path, owned_sets_path=FIXTURE_OWNED_SETS, resolve_official_link=_fake_resolve_official_link):
    db_path = tmp_path / "lego.sqlite"
    run_pipeline(
        raw_dir=FIXTURE_RAW,
        owned_sets_path=owned_sets_path,
        intermediate_dir=tmp_path / "02_intermediate",
        primary_dir=tmp_path / "03_primary",
        db_path=db_path,
        resolve_official_link=resolve_official_link,
    )
    return db_path


def test_owned_boxes_are_seeded_from_owned_sets_csv(tmp_path):
    conn = sqlite3.connect(_run(tmp_path))
    rows = conn.execute(
        "SELECT set_num, date_acquired, notes FROM owned_boxes ORDER BY set_num"
    ).fetchall()
    conn.close()

    assert rows == [
        ("10281-1", "2022-06-01", ""),
        ("75192-1", "2023-12-25", "Holiday gift"),
    ]


def test_sets_table_carries_every_catalog_set_with_a_resolved_official_link(tmp_path):
    conn = sqlite3.connect(_run(tmp_path))
    rows = conn.execute(
        "SELECT set_num, name, year, official_url, official_url_status FROM sets ORDER BY set_num"
    ).fetchall()
    conn.close()

    assert rows == [
        ("10281-1", "Bonsai Tree", 2021, "https://www.lego.com/en-us/product/10281", "ok"),
        ("21331-1", "Ship in a Bottle", 2022, "https://www.lego.com/en-us/product/21331", "ok"),
        ("75192-1", "Millennium Falcon", 2017, "https://www.lego.com/en-us/product/75192", "ok"),
    ]


def test_themes_table_is_carried_through(tmp_path):
    conn = sqlite3.connect(_run(tmp_path))
    rows = conn.execute("SELECT id, name, parent_id FROM themes ORDER BY id").fetchall()
    conn.close()

    assert rows == [(1, "Star Wars", None), (158, "Icons", None)]


def test_inventory_parts_and_minifigs_are_materialized_for_owned_boxes_only(tmp_path):
    conn = sqlite3.connect(_run(tmp_path))

    # 21331-1 (Ship in a Bottle) isn't owned, so its inventory (id 3 in the
    # fixture) is excluded entirely: only owned Boxes get per-set inventory
    # data materialized.
    inventories = conn.execute("SELECT id, version, set_num FROM inventories ORDER BY id").fetchall()
    assert inventories == [(1, 1, "75192-1"), (4, 2, "10281-1")]

    parts = conn.execute(
        "SELECT inventory_id, part_num, color_id, quantity FROM inventory_parts ORDER BY inventory_id, part_num, color_id"
    ).fetchall()
    # 10281-1's older inventory (id 2, version 1) is superseded by its latest
    # (id 4, version 2) — a Box's contents come from its latest version only.
    assert parts == [
        (1, "3001", 0, 10),
        (1, "3020", 1, 4),
        (4, "3001", 0, 15),
        (4, "3001", 15, 25),
    ]

    minifigs = conn.execute(
        "SELECT inventory_id, fig_num, quantity FROM inventory_minifigs ORDER BY inventory_id, fig_num"
    ).fetchall()
    assert minifigs == [
        (1, "fig-000001", 1),
        (1, "fig-000002", 1),
        (4, "fig-000001", 1),
    ]

    conn.close()


def test_a_boxs_parts_and_minifigs_resolve_to_names_and_colors_via_metadata_tables(tmp_path):
    """Metadata tables (colors, parts, minifigs) are loaded in full so the Box
    detail page can join a Box's inventory rows to human-readable names and
    colors, not just raw part_num/color_id/fig_num ids.
    """
    conn = sqlite3.connect(_run(tmp_path))

    parts = conn.execute(
        """
        SELECT parts.name, colors.name, colors.rgb, inventory_parts.quantity
        FROM inventory_parts
        JOIN inventories ON inventories.id = inventory_parts.inventory_id
        JOIN parts ON parts.part_num = inventory_parts.part_num
        JOIN colors ON colors.id = inventory_parts.color_id
        WHERE inventories.set_num = '75192-1'
        ORDER BY parts.name, colors.name
        """
    ).fetchall()
    assert parts == [
        ("Brick 2 x 4", "Black", "05131D", 10),
        ("Plate 2 x 4", "Blue", "0055BF", 4),
    ]

    minifigs = conn.execute(
        """
        SELECT minifigs.name, inventory_minifigs.quantity
        FROM inventory_minifigs
        JOIN inventories ON inventories.id = inventory_minifigs.inventory_id
        JOIN minifigs ON minifigs.fig_num = inventory_minifigs.fig_num
        WHERE inventories.set_num = '75192-1'
        ORDER BY minifigs.name
        """
    ).fetchall()
    assert minifigs == [("Han Solo", 1), ("Luke Skywalker", 1)]

    conn.close()


def test_owned_brick_pool_sums_inventory_parts_across_boxes_sharing_the_same_part_and_color(tmp_path):
    """75192-1 and 10281-1 both own part 3001 in color 0 (Black) — the Owned
    brick pool treats the collection as one pooled, disassembled whole, so
    their quantities sum rather than staying scoped per-Box.
    """
    conn = sqlite3.connect(_run(tmp_path))
    rows = conn.execute(
        "SELECT part_num, color_id, quantity FROM owned_brick_pool ORDER BY part_num, color_id"
    ).fetchall()
    conn.close()

    assert rows == [
        ("3001", 0, 25),  # 10 (75192-1) + 15 (10281-1)
        ("3001", 15, 25),  # 10281-1 only
        ("3020", 1, 4),  # 75192-1 only
    ]


def test_owned_minifigs_sums_inventory_minifigs_across_boxes_sharing_the_same_fig_num(tmp_path):
    """75192-1 and 10281-1 both own fig-000001 (Han Solo) — the Figurines page
    aggregates minifigs across the whole collection the same way the Owned
    brick pool aggregates parts, so their quantities sum rather than staying
    scoped per-Box.
    """
    conn = sqlite3.connect(_run(tmp_path))
    rows = conn.execute("SELECT fig_num, quantity FROM owned_minifigs ORDER BY fig_num").fetchall()
    conn.close()

    assert rows == [
        ("fig-000001", 2),  # 1 (75192-1) + 1 (10281-1)
        ("fig-000002", 1),  # 75192-1 only
    ]


def test_owned_sets_seed_referencing_an_unknown_set_num_is_rejected(tmp_path):
    bad_owned_sets = tmp_path / "owned_sets.csv"
    bad_owned_sets.write_text("set_num,date_acquired,notes\n99999-1,2024-01-01,\n")

    with pytest.raises(ValueError, match="99999-1"):
        _run(tmp_path, owned_sets_path=bad_owned_sets)
