from pipeline.ldraw import (
    build_ldr_layout,
    content_hash,
    render_coverage_pct,
    resolve_ldraw_lines,
    resolve_ldraw_procedural_render,
)
from tests.conftest import FakeRenderer

INVENTORY_PARTS_ROWS = [
    {"part_num": "3001", "color_id": "0", "quantity": "10"},
    {"part_num": "3020", "color_id": "1", "quantity": "4"},
    # 9999 has no crosswalk entry at all — dropped, not guessed at.
    {"part_num": "9999", "color_id": "0", "quantity": "6"},
]
LDRAW_PART_ID_BY_PART_NUM = {"3001": "3001", "3020": "3020"}
LDRAW_COLOR_ID_BY_COLOR_ID = {0: 0, 1: 1}


def test_resolve_ldraw_lines_drops_rows_missing_either_half_of_the_crosswalk():
    resolved, resolved_quantity, total_quantity = resolve_ldraw_lines(
        INVENTORY_PARTS_ROWS, LDRAW_PART_ID_BY_PART_NUM, LDRAW_COLOR_ID_BY_COLOR_ID
    )

    assert sorted(resolved) == [("3001", 0, 10), ("3020", 1, 4)]
    assert resolved_quantity == 14
    assert total_quantity == 20


def test_resolve_ldraw_lines_drops_a_row_whose_color_has_no_crosswalk_entry():
    rows = [{"part_num": "3001", "color_id": "71", "quantity": "5"}]

    resolved, resolved_quantity, total_quantity = resolve_ldraw_lines(
        rows, LDRAW_PART_ID_BY_PART_NUM, LDRAW_COLOR_ID_BY_COLOR_ID
    )

    assert resolved == []
    assert resolved_quantity == 0
    assert total_quantity == 5


def test_render_coverage_pct_is_the_resolved_share_of_total_quantity():
    assert render_coverage_pct(14, 20) == 70.0


def test_render_coverage_pct_of_zero_total_quantity_is_zero_not_a_division_error():
    assert render_coverage_pct(0, 0) == 0.0


def test_content_hash_is_stable_regardless_of_input_order():
    a = [("3001", 0, 10), ("3020", 1, 4)]
    b = [("3020", 1, 4), ("3001", 0, 10)]

    assert content_hash(a) == content_hash(b)


def test_content_hash_changes_when_the_resolved_part_list_changes():
    a = [("3001", 0, 10)]
    b = [("3001", 0, 11)]

    assert content_hash(a) != content_hash(b)


def test_build_ldr_layout_places_one_line_per_part_instance():
    resolved = [("3001", 0, 2), ("3020", 1, 1)]

    ldr_text = build_ldr_layout(resolved)
    part_lines = [line for line in ldr_text.splitlines() if line.startswith("1 ")]

    assert len(part_lines) == 3
    assert all(line.endswith(".dat") for line in part_lines)
    assert any(line.startswith("1 0 ") and line.endswith("3001.dat") for line in part_lines)
    assert any(line.startswith("1 1 ") and line.endswith("3020.dat") for line in part_lines)


def test_resolve_ldraw_procedural_render_succeeds_and_reports_partial_coverage(tmp_path):
    renderer = FakeRenderer()

    row = resolve_ldraw_procedural_render(
        "10281-1",
        INVENTORY_PARTS_ROWS,
        LDRAW_PART_ID_BY_PART_NUM,
        LDRAW_COLOR_ID_BY_COLOR_ID,
        tmp_path,
        "2024-01-01T00:00:00Z",
        render=renderer,
    )

    assert row["set_num"] == "10281-1"
    assert row["image_source"] == "ldraw_procedural"
    assert row["render_coverage_pct"] == 70.0
    assert row["image_path"].startswith("assets/ldraw-renders/10281-1/")
    assert row["image_path"].endswith(".png")
    assert len(renderer.calls) == 1


def test_resolve_ldraw_procedural_render_falls_back_to_none_when_zero_parts_resolve(tmp_path):
    renderer = FakeRenderer()
    rows = [{"part_num": "9999", "color_id": "0", "quantity": "6"}]

    row = resolve_ldraw_procedural_render(
        "10281-1", rows, LDRAW_PART_ID_BY_PART_NUM, LDRAW_COLOR_ID_BY_COLOR_ID, tmp_path, "2024-01-01T00:00:00Z", render=renderer
    )

    assert row == {
        "set_num": "10281-1",
        "image_source": "none",
        "image_path": None,
        "render_coverage_pct": None,
        "rendered_at": "2024-01-01T00:00:00Z",
    }
    # Zero resolved parts means there's nothing to lay out — the renderer
    # is never even invoked.
    assert renderer.calls == []


def test_resolve_ldraw_procedural_render_falls_back_to_none_without_crashing_when_the_renderer_fails(tmp_path):
    renderer = FakeRenderer(should_fail=True)

    row = resolve_ldraw_procedural_render(
        "10281-1",
        INVENTORY_PARTS_ROWS,
        LDRAW_PART_ID_BY_PART_NUM,
        LDRAW_COLOR_ID_BY_COLOR_ID,
        tmp_path,
        "2024-01-01T00:00:00Z",
        render=renderer,
    )

    assert row["image_source"] == "none"
    assert row["image_path"] is None
    assert row["render_coverage_pct"] is None
    assert len(renderer.calls) == 1


def test_resolve_ldraw_procedural_render_skips_a_second_render_call_when_content_is_unchanged(tmp_path):
    """Caching: an unchanged resolved part list must not trigger a second,
    expensive render call on a later pipeline run — INITIAL_PROJECT_SPEC.md
    §7 step 8 / §10 "Caching".
    """
    renderer = FakeRenderer()

    first = resolve_ldraw_procedural_render(
        "10281-1",
        INVENTORY_PARTS_ROWS,
        LDRAW_PART_ID_BY_PART_NUM,
        LDRAW_COLOR_ID_BY_COLOR_ID,
        tmp_path,
        "2024-01-01T00:00:00Z",
        render=renderer,
    )
    second = resolve_ldraw_procedural_render(
        "10281-1",
        INVENTORY_PARTS_ROWS,
        LDRAW_PART_ID_BY_PART_NUM,
        LDRAW_COLOR_ID_BY_COLOR_ID,
        tmp_path,
        "2024-02-01T00:00:00Z",
        render=renderer,
    )

    assert len(renderer.calls) == 1
    assert first["image_path"] == second["image_path"]


def test_resolve_ldraw_procedural_render_re_renders_when_the_resolved_part_list_changes(tmp_path):
    renderer = FakeRenderer()
    changed_rows = [{"part_num": "3001", "color_id": "0", "quantity": "999"}]

    first = resolve_ldraw_procedural_render(
        "10281-1",
        INVENTORY_PARTS_ROWS,
        LDRAW_PART_ID_BY_PART_NUM,
        LDRAW_COLOR_ID_BY_COLOR_ID,
        tmp_path,
        "2024-01-01T00:00:00Z",
        render=renderer,
    )
    second = resolve_ldraw_procedural_render(
        "10281-1",
        changed_rows,
        LDRAW_PART_ID_BY_PART_NUM,
        LDRAW_COLOR_ID_BY_COLOR_ID,
        tmp_path,
        "2024-02-01T00:00:00Z",
        render=renderer,
    )

    assert len(renderer.calls) == 2
    assert first["image_path"] != second["image_path"]
