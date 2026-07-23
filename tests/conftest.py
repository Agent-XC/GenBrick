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
SITE_DIR = Path(__file__).parent.parent / "site"

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


@pytest.fixture(scope="session")
def site_url(tmp_path_factory):
    """Serves a staged copy of site/ over real HTTP, with data/lego.sqlite
    swapped for one built fresh from the shared pipeline test fixtures.

    A real HTTP server is required, not just opening the HTML file with a
    file:// URL: shared.js's loadDatabase() calls fetch() for both
    sql-wasm.wasm and data/lego.sqlite, and Chromium refuses fetch() under
    file:// (no origin to apply CORS to). See docs/agents/frontend-testing.md
    for the full limitations list this fixture works around.

    Session-scoped: the pipeline run and browser-visible static files don't
    change per test, so every test in the session shares one server and one
    fixture-built database.
    """
    staging = tmp_path_factory.mktemp("site")
    for name in ("index.html", "box.html", "collection.html", "figurines.html", "discover.html", "assets", "vendor"):
        src = SITE_DIR / name
        dst = staging / name
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy(src, dst)

    db_path = tmp_path_factory.mktemp("db") / "lego.sqlite"
    run_pipeline(
        raw_dir=FIXTURE_RAW,
        owned_sets_path=FIXTURE_OWNED_SETS,
        intermediate_dir=tmp_path_factory.mktemp("intermediate"),
        primary_dir=tmp_path_factory.mktemp("primary"),
        db_path=db_path,
        resolve_official_link=_fake_resolve_official_link,
    )
    (staging / "data").mkdir()
    shutil.copyfile(db_path, staging / "data" / "lego.sqlite")

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
