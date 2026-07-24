import functools
import http.server
import shutil
import socketserver
import threading
from pathlib import Path

import pytest

from pipeline.run import run_pipeline

FIXTURE_RAW = Path(__file__).parent / "fixtures" / "raw"
FIXTURE_OWNED_SETS = Path(__file__).parent / "fixtures" / "owned_sets.csv"
FIXTURE_OWNED_BOX_PHOTOS = Path(__file__).parent / "fixtures" / "owned_box_photos.csv"
FIXTURE_LDRAW_PARTS_CROSSWALK = Path(__file__).parent / "fixtures" / "ldraw_parts_crosswalk.csv"
FIXTURE_LDRAW_COLORS_CROSSWALK = Path(__file__).parent / "fixtures" / "ldraw_colors_crosswalk.csv"
FIXTURE_LDRAW_OMR_CROSSWALK = Path(__file__).parent / "fixtures" / "ldraw_omr_crosswalk.csv"
FIXTURE_PHOTO = Path(__file__).parent / "fixtures" / "photos" / "falcon.jpg"
SITE_DIR = Path(__file__).parent.parent / "site"


def _fake_render(ldr_path: Path, png_path: Path) -> None:
    """Stands in for the real (subprocess/LDView) renderer in tests that
    aren't about the renderer seam itself — see test_ldraw.py for that.
    """
    png_path.write_bytes(b"fake-png-bytes")


class FakeRenderer:
    """Records calls and writes a marker PNG, standing in for the real
    (subprocess) LDView invocation in tests that are about the renderer seam
    itself — see test_ldraw.py (the procedural render) and test_omr.py (the
    OMR render), which both feed it a different kind of LDraw file but call
    it the same way.
    """

    def __init__(self, should_fail: bool = False):
        self.calls = []
        self.should_fail = should_fail

    def __call__(self, ldr_path, png_path):
        self.calls.append((ldr_path, png_path))
        if self.should_fail:
            raise RuntimeError("ldview crashed")
        png_path.write_bytes(b"fake-png-bytes")

# Served files whose extension isn't reliably mapped to the right MIME type
# by every OS's mimetypes database — most importantly .wasm, which needs
# "application/wasm" for WebAssembly.instantiateStreaming to succeed. sql.js
# falls back to a slower ArrayBuffer-based instantiation when streaming
# compile fails, so a wrong MIME type wouldn't break these tests, but it
# would silently take the slow path and log a console warning that a
# no-console-errors test would then have to know to ignore.
_EXTRA_MIME_TYPES = {".wasm": "application/wasm"}


class _SiteRequestHandler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, **_EXTRA_MIME_TYPES}

    def log_message(self, format, *args):
        pass  # Keep pytest output free of one HTTP access log line per asset.


def _fake_resolve_official_link(set_num: str) -> tuple[str, str]:
    """Stands in for the real (networked) link checker in tests that aren't
    about link-checking itself — see test_links.py for that seam's own tests.
    """
    base_set_number = set_num.split("-")[0]
    return f"https://www.lego.com/en-us/product/{base_set_number}", "ok"


def _fake_fetch_omr_model(url: str) -> bytes:
    """Stands in for the real (networked) OMR download in tests that aren't
    about that seam itself — see test_omr.py for that seam's own tests.
    """
    return b"fake-omr-model-bytes"


def _stage_site(tmp_path_factory, **run_pipeline_kwargs):
    """Shared by site_url and site_url_with_floors below: stages site/'s
    static files plus a fixture-built lego.sqlite and serves them over real
    HTTP. See site_url's own docstring for why a real HTTP server (not
    file://) is required.
    """
    staging = tmp_path_factory.mktemp("site")
    for name in (
        "index.html",
        "box.html",
        "collection.html",
        "figurines.html",
        "discover.html",
        "similarity.html",
        "themes.html",
        "assets",
        "vendor",
    ):
        src = SITE_DIR / name
        dst = staging / name
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy(src, dst)

    db_path = tmp_path_factory.mktemp("db") / "lego.sqlite"
    render_dir = staging / "assets" / "ldraw-renders"
    run_pipeline(
        raw_dir=FIXTURE_RAW,
        owned_sets_path=FIXTURE_OWNED_SETS,
        owned_box_photos_path=FIXTURE_OWNED_BOX_PHOTOS,
        ldraw_parts_crosswalk_path=FIXTURE_LDRAW_PARTS_CROSSWALK,
        ldraw_colors_crosswalk_path=FIXTURE_LDRAW_COLORS_CROSSWALK,
        ldraw_omr_crosswalk_path=FIXTURE_LDRAW_OMR_CROSSWALK,
        render_dir=render_dir,
        intermediate_dir=tmp_path_factory.mktemp("intermediate"),
        primary_dir=tmp_path_factory.mktemp("primary"),
        db_path=db_path,
        exports_dir=tmp_path_factory.mktemp("exports"),
        resolve_official_link=_fake_resolve_official_link,
        render=_fake_render,
        fetch_omr_model=_fake_fetch_omr_model,
        **run_pipeline_kwargs,
    )
    (staging / "data").mkdir()
    shutil.copyfile(db_path, staging / "data" / "lego.sqlite")

    # tests/fixtures/owned_box_photos.csv points 75192-1 at this filename —
    # staged separately from the real site/assets/owned-photos/ (which would
    # only ever hold the collector's actual photos), so the fixture DB's
    # image_path resolves to a real file instead of a broken image. 10281-1's
    # procedural render was written straight into render_dir (staging's own
    # assets/ldraw-renders/) by run_pipeline above, so it's already in place.
    photo_dir = staging / "assets" / "owned-photos" / "75192-1"
    photo_dir.mkdir(parents=True)
    shutil.copyfile(FIXTURE_PHOTO, photo_dir / "falcon.jpg")

    handler = functools.partial(_SiteRequestHandler, directory=str(staging))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()
        httpd.server_close()


@pytest.fixture(scope="session")
def site_url(tmp_path_factory):
    """Serves a staged copy of site/ over real HTTP, with data/lego.sqlite
    swapped for one built fresh from the shared pipeline test fixtures, at
    the default (no-floor) config.

    A real HTTP server is required, not just opening the HTML file with a
    file:// URL: shared.js's loadDatabase() calls fetch() for both
    sql-wasm.wasm and data/lego.sqlite, and Chromium refuses fetch() under
    file:// (no origin to apply CORS to). See docs/agents/frontend-testing.md
    for the full limitations list this fixture works around.

    Session-scoped: the pipeline run and browser-visible static files don't
    change per test, so every test in the session shares one server and one
    fixture-built database.
    """
    yield from _stage_site(tmp_path_factory)


@pytest.fixture(scope="session")
def site_url_with_floors(tmp_path_factory):
    """Same as site_url, but with config/scope.json's issue #15 floors
    engaged — a separate staged site + DB (its own tmp_path_factory temp
    dirs, own HTTP server) so it doesn't disturb site_url's shared session
    state. min_buildability_coverage_pct is set above 21331-1's own 45%
    coverage (see test_pipeline.py) so it drops out of buildability
    entirely, while staying above min_candidate_num_parts (962 parts) and
    clearing min_similarity_score_pct against 75192-1 (~36% score) — the
    scenario that exercises Similarity's scope being independent of
    Buildability's floor (see similarity.js's own comment on this).
    """
    yield from _stage_site(
        tmp_path_factory,
        min_candidate_num_parts=15,
        min_buildability_coverage_pct=50,
        min_similarity_score_pct=30,
    )
