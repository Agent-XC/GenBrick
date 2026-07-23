"""Stage a preview copy of site/ with a freshly-built DB and serve it over
local HTTP — for a human (or an agent) to look at the site without touching
the real site/data/lego.sqlite or site/assets/ldraw-renders/.

Why this exists: serving the site requires a real HTTP server (not file://
— see docs/agents/frontend-testing.md's "Limitations" section), and this
dev machine doesn't have LDView installed, so the real procedural renderer
(pipeline.ldraw.render_with_ldview) would silently degrade every owned Set
to image_source='none'. By default this script swaps in a placeholder PNG
generator instead, so the site actually has something to show. Pass
--real-renderer if LDView is installed and you want to exercise it for real.

See docs/agents/local-preview.md for the full write-up (why a temp staging
dir, why the server must be launched as its own foreground process rather
than backgrounded with `&` inside a longer command, etc.) — this script is
the frozen, reproducible answer to that doc; prefer running it over
re-deriving the steps by hand.

Usage:
    .venv/bin/python scripts/preview_site.py [--port 8743] [--real-renderer]
"""

import argparse
import http.server
import shutil
import socketserver
import struct
import sys
import zlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline.ldraw import render_with_ldview  # noqa: E402
from pipeline.run import run_pipeline  # noqa: E402

STAGING_DIR = REPO_ROOT / ".preview"

_STATIC_ENTRIES = (
    "index.html",
    "box.html",
    "collection.html",
    "figurines.html",
    "discover.html",
    "similarity.html",
    "themes.html",
    "assets",
    "vendor",
)


def _write_placeholder_png(path: Path, size: int = 400, rgb: tuple[int, int, int] = (0x2E, 0x86, 0xC1)) -> None:
    """A minimal valid solid-color PNG, pure stdlib (no Pillow dependency) —
    stands in for a real LDView render so the box detail page has something
    real to load in a browser.
    """

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    row = bytes([0]) + bytes(rgb) * size  # filter byte 0 + RGB pixels
    raw = row * size
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    path.write_bytes(png)


def _placeholder_render(ldr_path: Path, png_path: Path) -> None:
    _write_placeholder_png(png_path)


def stage(staging: Path, *, real_renderer: bool) -> Path:
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    for name in _STATIC_ENTRIES:
        src = REPO_ROOT / "site" / name
        dst = staging / name
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy(src, dst)

    work = staging / "_pipeline_work"
    db_path = work / "lego.sqlite"
    run_pipeline(
        raw_dir=REPO_ROOT / "data" / "01_raw",
        owned_sets_path=REPO_ROOT / "data" / "owned_sets.txt",
        owned_box_photos_path=REPO_ROOT / "data" / "owned_box_photos.csv",
        ldraw_parts_crosswalk_path=REPO_ROOT / "data" / "ldraw_parts_crosswalk.csv",
        ldraw_colors_crosswalk_path=REPO_ROOT / "data" / "ldraw_colors_crosswalk.csv",
        ldraw_omr_crosswalk_path=REPO_ROOT / "data" / "ldraw_omr_crosswalk.csv",
        render_dir=staging / "assets" / "ldraw-renders",
        intermediate_dir=work / "02_intermediate",
        primary_dir=work / "03_primary",
        db_path=db_path,
        render=render_with_ldview if real_renderer else _placeholder_render,
    )
    (staging / "data").mkdir()
    shutil.copyfile(db_path, staging / "data" / "lego.sqlite")
    shutil.rmtree(work)

    return staging


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".wasm": "application/wasm"}


def serve(staging: Path, port: int) -> None:
    handler = lambda *args, **kwargs: _QuietHandler(*args, directory=str(staging), **kwargs)  # noqa: E731
    with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
        print(f"Serving preview at http://127.0.0.1:{port}/index.html (Ctrl-C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8743)
    parser.add_argument("--real-renderer", action="store_true", help="Use the real LDView renderer instead of the placeholder PNG generator (requires ldview on PATH).")
    args = parser.parse_args()

    staging = stage(STAGING_DIR, real_renderer=args.real_renderer)
    serve(staging, args.port)


if __name__ == "__main__":
    main()
