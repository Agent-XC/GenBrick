from pipeline.omr import resolve_ldraw_omr_render
from tests.conftest import FakeRenderer

OMR_URL = "https://library.ldraw.org/library/omr/8094-1_Robotic-Arm.mpd"


def _fake_fetch(bytes_by_url: dict[str, bytes]):
    def fetch(url: str) -> bytes:
        return bytes_by_url[url]

    return fetch


def _failing_fetch(url: str) -> bytes:
    raise OSError("network unreachable")


def test_resolve_ldraw_omr_render_succeeds_when_the_crosswalk_has_an_exact_match(tmp_path):
    renderer = FakeRenderer()

    row = resolve_ldraw_omr_render(
        "8094-1",
        {"8094-1": OMR_URL},
        tmp_path,
        "2024-01-01T00:00:00Z",
        render=renderer,
        fetch=_fake_fetch({OMR_URL: b"model bytes"}),
    )

    assert row["set_num"] == "8094-1"
    assert row["image_source"] == "ldraw_omr"
    assert row["render_coverage_pct"] == 100.0
    assert row["image_path"].startswith("assets/ldraw-renders/8094-1/")
    assert row["image_path"].endswith(".png")
    assert len(renderer.calls) == 1


def test_resolve_ldraw_omr_render_returns_none_when_the_crosswalk_has_no_match_for_this_set(tmp_path):
    """The no-match case: the caller (pipeline/primary.py) falls through to
    the procedural renderer when this returns None.
    """
    renderer = FakeRenderer()

    row = resolve_ldraw_omr_render(
        "99999-1", {}, tmp_path, "2024-01-01T00:00:00Z", render=renderer, fetch=_fake_fetch({})
    )

    assert row is None
    assert renderer.calls == []


def test_resolve_ldraw_omr_render_returns_none_without_crashing_when_the_renderer_fails(tmp_path):
    renderer = FakeRenderer(should_fail=True)

    row = resolve_ldraw_omr_render(
        "8094-1",
        {"8094-1": OMR_URL},
        tmp_path,
        "2024-01-01T00:00:00Z",
        render=renderer,
        fetch=_fake_fetch({OMR_URL: b"model bytes"}),
    )

    assert row is None
    assert len(renderer.calls) == 1


def test_resolve_ldraw_omr_render_returns_none_without_crashing_when_the_download_fails(tmp_path):
    row = resolve_ldraw_omr_render(
        "8094-1",
        {"8094-1": OMR_URL},
        tmp_path,
        "2024-01-01T00:00:00Z",
        render=FakeRenderer(),
        fetch=_failing_fetch,
    )

    assert row is None


def test_resolve_ldraw_omr_render_skips_a_second_fetch_and_render_when_the_url_is_unchanged(tmp_path):
    renderer = FakeRenderer()
    fetch = _fake_fetch({OMR_URL: b"model bytes"})

    first = resolve_ldraw_omr_render(
        "8094-1", {"8094-1": OMR_URL}, tmp_path, "2024-01-01T00:00:00Z", render=renderer, fetch=fetch
    )
    second = resolve_ldraw_omr_render(
        "8094-1", {"8094-1": OMR_URL}, tmp_path, "2024-02-01T00:00:00Z", render=renderer, fetch=fetch
    )

    assert len(renderer.calls) == 1
    assert first["image_path"] == second["image_path"]


def test_resolve_ldraw_omr_render_re_renders_when_the_crosswalks_url_changes(tmp_path):
    renderer = FakeRenderer()
    fetch = _fake_fetch(
        {
            OMR_URL: b"model bytes",
            "https://library.ldraw.org/library/omr/8094-1_Plotter.mpd": b"other model bytes",
        }
    )

    first = resolve_ldraw_omr_render(
        "8094-1", {"8094-1": OMR_URL}, tmp_path, "2024-01-01T00:00:00Z", render=renderer, fetch=fetch
    )
    second = resolve_ldraw_omr_render(
        "8094-1",
        {"8094-1": "https://library.ldraw.org/library/omr/8094-1_Plotter.mpd"},
        tmp_path,
        "2024-02-01T00:00:00Z",
        render=renderer,
        fetch=fetch,
    )

    assert len(renderer.calls) == 2
    assert first["image_path"] != second["image_path"]
