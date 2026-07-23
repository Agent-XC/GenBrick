import sqlite3

import pytest

from pipeline.run import run_pipeline
from tests.conftest import (
    FIXTURE_LDRAW_COLORS_CROSSWALK,
    FIXTURE_LDRAW_PARTS_CROSSWALK,
    FIXTURE_OWNED_BOX_PHOTOS,
    FIXTURE_OWNED_SETS,
    FIXTURE_RAW,
    _fake_render,
    _fake_resolve_official_link,
)


def _run(
    tmp_path,
    owned_sets_path=FIXTURE_OWNED_SETS,
    owned_box_photos_path=FIXTURE_OWNED_BOX_PHOTOS,
    ldraw_parts_crosswalk_path=FIXTURE_LDRAW_PARTS_CROSSWALK,
    ldraw_colors_crosswalk_path=FIXTURE_LDRAW_COLORS_CROSSWALK,
    resolve_official_link=_fake_resolve_official_link,
    render=_fake_render,
    universe_scope="owned_themes",
):
    db_path = tmp_path / "lego.sqlite"
    run_pipeline(
        raw_dir=FIXTURE_RAW,
        owned_sets_path=owned_sets_path,
        owned_box_photos_path=owned_box_photos_path,
        ldraw_parts_crosswalk_path=ldraw_parts_crosswalk_path,
        ldraw_colors_crosswalk_path=ldraw_colors_crosswalk_path,
        render_dir=tmp_path / "ldraw-renders",
        intermediate_dir=tmp_path / "02_intermediate",
        primary_dir=tmp_path / "03_primary",
        db_path=db_path,
        resolve_official_link=resolve_official_link,
        render=render,
        universe_scope=universe_scope,
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

    # Metadata (sets, themes, ...) is loaded in full regardless of
    # universe_scope — 42100-1's theme isn't owned, so it never becomes a
    # Candidate (see test_candidate_sets_* below), but it still appears here.
    assert rows == [
        ("10281-1", "Bonsai Tree", 2021, "https://www.lego.com/en-us/product/10281", "ok"),
        ("21331-1", "Ship in a Bottle", 2022, "https://www.lego.com/en-us/product/21331", "ok"),
        ("42100-1", "Liebherr R 9800", 2019, "https://www.lego.com/en-us/product/42100", "ok"),
        ("75192-1", "Millennium Falcon", 2017, "https://www.lego.com/en-us/product/75192", "ok"),
    ]


def test_themes_table_is_carried_through(tmp_path):
    conn = sqlite3.connect(_run(tmp_path))
    rows = conn.execute("SELECT id, name, parent_id FROM themes ORDER BY id").fetchall()
    conn.close()

    assert rows == [(1, "Star Wars", None), (158, "Icons", None), (200, "Technic", None)]


def test_inventory_parts_and_minifigs_are_materialized_for_owned_and_candidate_sets_only(tmp_path):
    conn = sqlite3.connect(_run(tmp_path))

    # Default universe_scope is owned_themes: 21331-1 (Ship in a Bottle)
    # isn't owned but shares 10281-1's theme, so it's a Candidate and its
    # inventory (id 3) is materialized. 42100-1 sits in an unowned theme, so
    # it's excluded entirely — no per-set inventory data for out-of-scope sets.
    inventories = conn.execute("SELECT id, version, set_num FROM inventories ORDER BY id").fetchall()
    assert inventories == [(1, 1, "75192-1"), (3, 1, "21331-1"), (4, 2, "10281-1")]

    parts = conn.execute(
        "SELECT inventory_id, part_num, color_id, quantity FROM inventory_parts ORDER BY inventory_id, part_num, color_id"
    ).fetchall()
    # 10281-1's older inventory (id 2, version 1) is superseded by its latest
    # (id 4, version 2) — a Box's contents come from its latest version only.
    assert parts == [
        (1, "3001", 0, 10),
        (1, "3020", 1, 4),
        (3, "3001", 0, 5),
        (3, "3001", 71, 5),
        (3, "3020", 1, 10),
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


def test_candidate_sets_are_determined_per_universe_scope(tmp_path):
    """buildability holds exactly one row per Candidate — there's no separate
    candidate_sets table, so this is the "which sets are Candidates" signal.
    """
    conn = sqlite3.connect(_run(tmp_path))
    rows = conn.execute("SELECT set_num FROM buildability ORDER BY set_num").fetchall()
    conn.close()

    assert rows == [("21331-1",)]


def test_widening_universe_scope_grows_the_candidate_set_with_no_schema_change(tmp_path):
    """Changing universe_scope and re-running the pipeline widens the
    candidate set: moving from owned_themes to all picks up 42100-1 (an
    out-of-theme set) without any new tables/columns — same schema, more rows.
    """
    conn = sqlite3.connect(_run(tmp_path, universe_scope="all"))
    rows = conn.execute("SELECT set_num FROM buildability ORDER BY set_num").fetchall()
    conn.close()

    assert rows == [("21331-1",), ("42100-1",)]


def test_buildability_is_computed_per_candidate_from_the_owned_brick_pool(tmp_path):
    """21331-1's required parts blend full coverage (3001/0), zero coverage
    (3001/71 — not in the owned pool at all) and partial coverage (3020/1,
    needing more than owned) — see tests/fixtures/raw/inventory_parts.csv.
    """
    conn = sqlite3.connect(_run(tmp_path))
    rows = conn.execute("SELECT set_num, coverage_pct FROM buildability ORDER BY set_num").fetchall()
    conn.close()

    assert rows == [("21331-1", pytest.approx(45.0))]


def test_owned_brick_pool_excludes_a_candidates_materialized_inventory(tmp_path):
    """21331-1 is a Candidate (not owned) but its inventory is now
    materialized alongside owned Boxes' — owned_brick_pool must still filter
    through owned_boxes rather than pooling the whole inventory_parts table,
    or a Candidate's parts would leak into "owned" totals.
    """
    conn = sqlite3.connect(_run(tmp_path))
    rows = conn.execute(
        "SELECT part_num, color_id, quantity FROM owned_brick_pool ORDER BY part_num, color_id"
    ).fetchall()
    conn.close()

    # Unchanged from before candidates existed: no contribution from 21331-1's
    # inventory (id 3), e.g. no (3001, 71) row despite it now being materialized.
    assert rows == [
        ("3001", 0, 25),
        ("3001", 15, 25),
        ("3020", 1, 4),
    ]


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


def test_similarity_topk_is_computed_across_owned_and_candidate_sets_ranked_by_score(tmp_path):
    """Under the default owned_themes scope the materialized universe is
    75192-1, 10281-1 (both owned) and 21331-1 (Candidate) — 42100-1 sits
    outside scope entirely and never gets its inventory materialized (see
    test_inventory_parts_and_minifigs_are_materialized_for_owned_and_candidate_sets_only),
    so it can have no similarity_topk rows either. Similarity is symmetric
    and independent of ownership: 21331-1 (not owned) gets full anchor rows
    just like the owned sets do, unlike buildability which only scores
    Candidates.
    """
    conn = sqlite3.connect(_run(tmp_path))
    rows = conn.execute(
        "SELECT set_num, other_set_num, rank, score FROM similarity_topk ORDER BY set_num, rank"
    ).fetchall()
    conn.close()

    # Weighted Jaccard over each set's own (part_num, color_id) quantities:
    # 75192-1 {(3001,0):10, (3020,1):4}, 10281-1 {(3001,15):25, (3001,0):15},
    # 21331-1 {(3020,1):10, (3001,71):5, (3001,0):5}.
    assert rows == [
        ("10281-1", "75192-1", 1, pytest.approx(10 / 44 * 100)),
        ("10281-1", "21331-1", 2, pytest.approx(5 / 55 * 100)),
        ("21331-1", "75192-1", 1, pytest.approx(9 / 25 * 100)),
        ("21331-1", "10281-1", 2, pytest.approx(5 / 55 * 100)),
        ("75192-1", "21331-1", 1, pytest.approx(9 / 25 * 100)),
        ("75192-1", "10281-1", 2, pytest.approx(10 / 44 * 100)),
    ]


def test_widening_universe_scope_adds_the_newly_materialized_set_to_similarity_topk(tmp_path):
    """Moving from owned_themes to all picks up 42100-1 — Similarity widens
    with the same materialized-set universe Buildability uses, with no
    schema change (mirrors test_widening_universe_scope_grows_the_candidate_set_with_no_schema_change).
    """
    conn = sqlite3.connect(_run(tmp_path, universe_scope="all"))
    rows = conn.execute("SELECT DISTINCT set_num FROM similarity_topk ORDER BY set_num").fetchall()
    conn.close()

    assert rows == [("10281-1",), ("21331-1",), ("42100-1",), ("75192-1",)]


def test_owned_sets_seed_referencing_an_unknown_set_num_is_rejected(tmp_path):
    bad_owned_sets = tmp_path / "owned_sets.csv"
    bad_owned_sets.write_text("set_num,date_acquired,notes\n99999-1,2024-01-01,\n")

    with pytest.raises(ValueError, match="99999-1"):
        _run(tmp_path, owned_sets_path=bad_owned_sets)


def test_owned_box_photos_are_seeded_from_csv(tmp_path):
    """See tests/fixtures/owned_box_photos.csv: 75192-1 has an uploaded photo,
    10281-1 doesn't (covered by test_set_renders_* below).
    """
    conn = sqlite3.connect(_run(tmp_path))
    rows = conn.execute(
        "SELECT set_num, filename, caption, uploaded_at FROM owned_box_photos ORDER BY set_num"
    ).fetchall()
    conn.close()

    assert rows == [("75192-1", "falcon.jpg", "My own copy", "2024-01-01T00:00:00Z")]


def test_owned_box_photos_seed_referencing_a_set_num_that_isnt_owned_is_rejected(tmp_path):
    """A photo is only meaningful for a Box you actually own (INITIAL_PROJECT_SPEC.md
    §10: "User's own photo (owned sets only)") — 21331-1 exists in the catalog
    and is even a Candidate under owned_themes, but it isn't owned.
    """
    bad_owned_box_photos = tmp_path / "owned_box_photos.csv"
    bad_owned_box_photos.write_text("set_num,filename,caption,uploaded_at\n21331-1,ship.jpg,,2024-01-01T00:00:00Z\n")

    with pytest.raises(ValueError, match="21331-1"):
        _run(tmp_path, owned_box_photos_path=bad_owned_box_photos)


def test_set_renders_records_user_photo_as_the_image_source_when_a_photo_exists(tmp_path):
    conn = sqlite3.connect(_run(tmp_path))
    row = conn.execute(
        "SELECT image_source, image_path, render_coverage_pct FROM set_renders WHERE set_num = '75192-1'"
    ).fetchone()
    conn.close()

    # 100% render_coverage_pct for a user photo — nothing was procedurally
    # resolved/omitted, per INITIAL_PROJECT_SPEC.md §9's set_renders comment
    # ("100 for user_photo / ldraw_omr").
    assert row == ("user_photo", "assets/owned-photos/75192-1/falcon.jpg", pytest.approx(100.0))


def test_set_renders_falls_through_to_ldraw_procedural_for_an_owned_box_without_a_photo(tmp_path):
    """10281-1 is owned but has no row in tests/fixtures/owned_box_photos.csv,
    so it falls through to the procedural renderer (LDraw OMR isn't built
    yet). Its latest inventory (id 4) is (3001, 15, qty 25) + (3001, 0, qty
    15) — tests/fixtures/ldraw_colors_crosswalk.csv deliberately omits color
    15, so only the qty-15 row resolves: 15 / 40 = 37.5% render_coverage_pct.
    """
    conn = sqlite3.connect(_run(tmp_path))
    row = conn.execute(
        "SELECT image_source, image_path, render_coverage_pct FROM set_renders WHERE set_num = '10281-1'"
    ).fetchone()
    conn.close()

    assert row[0] == "ldraw_procedural"
    assert row[1].startswith("assets/ldraw-renders/10281-1/")
    assert row[2] == pytest.approx(37.5)


def test_set_renders_falls_back_to_none_when_zero_parts_resolve_via_the_crosswalk(tmp_path):
    """With an empty LDraw crosswalk, nothing resolves for any owned Box
    without a user photo — 10281-1 must fall all the way through to 'none'
    rather than a broken or empty image.
    """
    empty_parts_crosswalk = tmp_path / "empty_ldraw_parts_crosswalk.csv"
    empty_parts_crosswalk.write_text("part_num,ldraw_part_id\n")
    empty_colors_crosswalk = tmp_path / "empty_ldraw_colors_crosswalk.csv"
    empty_colors_crosswalk.write_text("color_id,ldraw_color_id\n")

    conn = sqlite3.connect(
        _run(
            tmp_path,
            ldraw_parts_crosswalk_path=empty_parts_crosswalk,
            ldraw_colors_crosswalk_path=empty_colors_crosswalk,
        )
    )
    row = conn.execute(
        "SELECT image_source, image_path, render_coverage_pct FROM set_renders WHERE set_num = '10281-1'"
    ).fetchone()
    conn.close()

    assert row == ("none", None, None)


def test_ldraw_crosswalk_is_populated_opportunistically_and_null_where_missing(tmp_path):
    """tests/fixtures/ldraw_colors_crosswalk.csv deliberately omits color 15
    (White) to exercise the "NULL where not available" half of
    INITIAL_PROJECT_SPEC.md §9's crosswalk note; every fixture part has an entry.
    """
    conn = sqlite3.connect(_run(tmp_path))
    colors = dict(conn.execute("SELECT id, ldraw_color_id FROM colors").fetchall())
    parts = dict(conn.execute("SELECT part_num, ldraw_part_id FROM parts").fetchall())
    conn.close()

    assert colors == {0: 0, 1: 1, 15: None, 71: 71}
    assert parts == {"3001": "3001", "3020": "3020"}


def test_set_renders_has_no_row_for_a_candidate_set(tmp_path):
    """User photos are owned-sets-only (see above) and later render stages
    aren't implemented yet, so set_renders — unlike buildability/similarity_topk
    — doesn't cover Candidates at this stage; 21331-1 is a Candidate here.
    """
    conn = sqlite3.connect(_run(tmp_path))
    row = conn.execute("SELECT * FROM set_renders WHERE set_num = '21331-1'").fetchone()
    conn.close()

    assert row is None
