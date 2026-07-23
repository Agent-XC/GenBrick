import hashlib
import os
import subprocess
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path

# Relative to site/ — where every generated render is served from, alongside
# owned_box_photos' assets/owned-photos/ (see primary.py's set_renders resolution).
RENDER_WEB_ROOT = "assets/ldraw-renders"


def resolve_ldraw_lines(
    inventory_parts_rows: Iterable[Mapping],
    ldraw_part_id_by_part_num: Mapping[str, str | None],
    ldraw_color_id_by_color_id: Mapping[int, int | None],
) -> tuple[list[tuple[str, int, int]], int, int]:
    """A Set's (part_num, color_id, quantity) rows -> resolved
    (ldraw_part_id, ldraw_color_id, quantity) triples, plus (resolved_quantity,
    total_quantity) for render_coverage_pct.

    A row is dropped, not guessed at, when either half of the crosswalk
    misses — INITIAL_PROJECT_SPEC.md §10 point 3 ("parts without a crosswalk
    hit are simply omitted, not guessed at").
    """
    resolved: list[tuple[str, int, int]] = []
    resolved_quantity = 0
    total_quantity = 0
    for row in inventory_parts_rows:
        quantity = int(row["quantity"])
        total_quantity += quantity
        ldraw_part_id = ldraw_part_id_by_part_num.get(row["part_num"])
        ldraw_color_id = ldraw_color_id_by_color_id.get(int(row["color_id"]))
        if ldraw_part_id is None or ldraw_color_id is None:
            continue
        resolved.append((ldraw_part_id, ldraw_color_id, quantity))
        resolved_quantity += quantity
    return resolved, resolved_quantity, total_quantity


def render_coverage_pct(resolved_quantity: int, total_quantity: int) -> float:
    if total_quantity == 0:
        return 0.0
    return resolved_quantity / total_quantity * 100


def content_hash(resolved: list[tuple[str, int, int]]) -> str:
    """Hash of a Set's resolved part list — the cache key. Two runs that
    resolve to the same parts/colors/quantities (a set's contents haven't
    changed, and neither has the crosswalk) hash identically, so
    resolve_ldraw_procedural_render can skip the actual render call —
    INITIAL_PROJECT_SPEC.md §7 step 8 / §10 "Caching".
    """
    canonical = "\n".join(f"{part_id}:{color_id}:{quantity}" for part_id, color_id, quantity in sorted(resolved))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def build_ldr_layout(resolved: list[tuple[str, int, int]], *, spacing: float = 40.0, columns: int = 10) -> str:
    """A synthetic .ldr file: one instance of each resolved part placed on a
    flat, spaced-out grid in its actual color — not assembled, just a pile of
    the set's actual pieces (INITIAL_PROJECT_SPEC.md §10 point 3).

    LDraw line type 1: `1 <colour> x y z a b c d e f g h i <file>`, using the
    identity rotation matrix since nothing here needs to be oriented.
    """
    lines = ["0 GenBrick procedural render", "0 Unofficial Model"]
    index = 0
    for ldraw_part_id, ldraw_color_id, quantity in sorted(resolved):
        for _ in range(quantity):
            row, col = divmod(index, columns)
            x = col * spacing
            z = row * spacing
            lines.append(f"1 {ldraw_color_id} {x} 0 {z} 1 0 0 0 1 0 0 0 1 {ldraw_part_id}.dat")
            index += 1
    return "\n".join(lines) + "\n"


class RenderError(Exception):
    """Raised by a renderer callable to signal it failed to produce a PNG —
    caught by resolve_ldraw_procedural_render, which falls back to no image
    rather than letting one set's render failure crash the whole pipeline."""


def render_with_ldview(ldr_path: Path, png_path: Path) -> None:
    """The real, production renderer: shells out to LDView's CLI.

    Assumes the `ldview-osmesa` build (an official LDView release asset —
    see https://github.com/tcobbs/ldview/releases) rather than the regular
    Qt/OpenGL build: it's linked against OSMesa, so it renders fully
    offscreen with no X server / GPU / Xvfb needed at all — a better fit for
    a CI runner than fighting Xvfb + Mesa llvmpipe for a real GL context (the
    approach INITIAL_PROJECT_SPEC.md §10 "Renderer choice" originally
    proposed; L3P + POV-Ray remains the documented fallback if this build
    ever proves troublesome). See .github/workflows/ldview-render-smoke-test.yml
    for the CI wiring, including how the LDraw parts library itself
    (https://library.ldraw.org/library/updates/complete.zip) is fetched.

    Requires the LDRAWDIR environment variable to point at an extracted
    LDraw parts library (the directory containing LDConfig.ldr, parts/, p/,
    ...) — passed through explicitly as -LDrawDir rather than relying on
    LDView's persisted-preference fallback, since CI runners start clean
    each time.

    Wrapped in try/except by the caller, so a missing binary, a missing
    parts library, or a renderer crash degrades to "no image" rather than
    crashing the pipeline.

    A zero exit code from ldview doesn't guarantee png_path was written —
    seen on ldview-osmesa in CI, exit 0 with no file and no clue why since
    stdout/stderr are otherwise captured and discarded — so that's checked
    explicitly and folded into the RenderError alongside the captured output.
    """
    ldraw_dir = os.environ.get("LDRAWDIR")
    ldraw_dir_args = [f"-LDrawDir={ldraw_dir}"] if ldraw_dir else []
    try:
        result = subprocess.run(
            [
                "ldview",
                str(ldr_path),
                f"-SaveSnapshot={png_path}",
                "-SaveWidth=400",
                "-SaveHeight=400",
                "-SaveAlpha=1",
                *ldraw_dir_args,
            ],
            capture_output=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise RenderError(f"ldview failed to render {ldr_path}") from error

    if result.returncode != 0 or not png_path.exists():
        stdout = result.stdout.decode(errors="replace")
        stderr = result.stderr.decode(errors="replace")
        raise RenderError(
            f"ldview failed to render {ldr_path} (exit {result.returncode}, "
            f"png exists: {png_path.exists()})\nstdout: {stdout}\nstderr: {stderr}"
        )


def _none_row(set_num: str, rendered_at: str) -> dict:
    return {
        "set_num": set_num,
        "image_source": "none",
        "image_path": None,
        "render_coverage_pct": None,
        "rendered_at": rendered_at,
    }


def resolve_ldraw_procedural_render(
    set_num: str,
    inventory_parts_rows: Iterable[Mapping],
    ldraw_part_id_by_part_num: Mapping[str, str | None],
    ldraw_color_id_by_color_id: Mapping[int, int | None],
    render_dir: Path,
    rendered_at: str,
    render: Callable[[Path, Path], None] = render_with_ldview,
) -> dict:
    """Resolve one owned Set's procedural render and return the set_renders
    row to write. Only called when the set has neither a user photo nor an
    LDraw OMR render (INITIAL_PROJECT_SPEC.md §10 priority order) — this is
    step 3, the fallback.

    Falls back to the 'none' row (not a crash, not a guess) when either zero
    parts resolved via the crosswalk, or the renderer itself fails.
    """
    resolved, resolved_quantity, total_quantity = resolve_ldraw_lines(
        inventory_parts_rows, ldraw_part_id_by_part_num, ldraw_color_id_by_color_id
    )
    if not resolved:
        return _none_row(set_num, rendered_at)

    digest = content_hash(resolved)
    set_render_dir = render_dir / set_num
    png_path = set_render_dir / f"{digest}.png"

    if not png_path.exists():
        set_render_dir.mkdir(parents=True, exist_ok=True)
        ldr_path = set_render_dir / f"{digest}.ldr"
        ldr_path.write_text(build_ldr_layout(resolved))
        try:
            render(ldr_path, png_path)
        except Exception:
            return _none_row(set_num, rendered_at)
        if not png_path.exists():
            return _none_row(set_num, rendered_at)

    return {
        "set_num": set_num,
        "image_source": "ldraw_procedural",
        "image_path": f"{RENDER_WEB_ROOT}/{set_num}/{digest}.png",
        "render_coverage_pct": render_coverage_pct(resolved_quantity, total_quantity),
        "rendered_at": rendered_at,
    }
