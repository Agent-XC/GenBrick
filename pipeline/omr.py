import hashlib
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path

from pipeline.ldraw import RENDER_WEB_ROOT
from pipeline.ldraw import render_with_ldview as _render_with_ldview


def fetch_omr_model_bytes(url: str) -> bytes:
    """Real HTTP GET of a community-submitted model file from LDraw's
    Official Model Repository — the network I/O boundary
    resolve_ldraw_omr_render wraps so it can be faked in tests.

    `url` comes from data/ldraw_omr_crosswalk.csv, a separately-maintained
    crosswalk of set_num -> OMR download URL (mirrors ldraw_parts_crosswalk.csv
    / ldraw_colors_crosswalk.csv: populated opportunistically, absent where no
    exact-set match exists in the OMR. The OMR has no documented bulk/API
    lookup by set_num — INITIAL_PROJECT_SPEC.md §17 flags this same
    undocumented-external-API shape for the LEGO<->LDraw crosswalk, though it
    doesn't name the OMR specifically — so this crosswalk is a manually-curated
    stand-in rather than a live search, consistent with how this codebase
    already treats the other two LDraw crosswalks.

    Raises on any network failure; the caller treats that the same as a
    renderer failure (falls through to the procedural render rather than
    crashing the pipeline).
    """
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read()


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def resolve_ldraw_omr_render(
    set_num: str,
    omr_url_by_set_num: Mapping[str, str],
    render_dir: Path,
    rendered_at: str,
    render: Callable[[Path, Path], None] = _render_with_ldview,
    fetch: Callable[[str], bytes] = fetch_omr_model_bytes,
) -> dict | None:
    """A Set's OMR match -> the set_renders row to write, or None when the
    OMR crosswalk has no exact-set match — the caller then falls through to
    the procedural renderer (INITIAL_PROJECT_SPEC.md §10's priority order,
    step 2, ahead of step 3).

    A download or render failure also returns None rather than raising, so a
    single bad OMR entry falls through to the procedural render the same way
    a no-match does, instead of crashing the pipeline or leaving a broken image.

    Cached by a hash of the OMR URL itself (mirrors resolve_ldraw_procedural_render's
    content-hash cache): re-fetches/re-renders only when the crosswalk's URL
    for this set_num changes, not on every weekly run.
    """
    omr_url = omr_url_by_set_num.get(set_num)
    if omr_url is None:
        return None

    digest = _url_hash(omr_url)
    set_render_dir = render_dir / set_num
    model_path = set_render_dir / f"{digest}.mpd"
    png_path = set_render_dir / f"{digest}.png"

    if not png_path.exists():
        set_render_dir.mkdir(parents=True, exist_ok=True)
        try:
            model_path.write_bytes(fetch(omr_url))
            render(model_path, png_path)
        except Exception:
            return None
        if not png_path.exists():
            return None

    return {
        "set_num": set_num,
        "image_source": "ldraw_omr",
        "image_path": f"{RENDER_WEB_ROOT}/{set_num}/{digest}.png",
        # 100%: a full assembled OMR model isn't a partial procedural render,
        # so nothing was omitted the way ldraw_procedural's coverage tracks.
        "render_coverage_pct": 100.0,
        "rendered_at": rendered_at,
    }
