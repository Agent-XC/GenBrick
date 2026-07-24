import csv
import io
import os
import re
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path

from pipeline.csvutil import write_csv
from pipeline.fetch_rebrickable import REBRICKABLE_DOWNLOAD_BASE_URL, fetch_and_gunzip

# Rebrickable appends a decoration suffix to a part's base mold number for
# printed ("pr"/"pb") and patterned ("pat") variants, and for composite
# multi-piece assemblies ("c01", "c02", ...). This project's LDraw render
# only ever resolves (part, colour) — INITIAL_PROJECT_SPEC.md §10 point 3,
# it never models prints/patterns — so the base mold is what a decorated
# part actually renders as.
_DECORATION_SUFFIX_RE = re.compile(r"(pr|pb|pat|c)\d+$")

# LDConfig.ldr's colour definitions look like:
#   0 !COLOUR Black    CODE     0   VALUE #1B2A34   EDGE #808080
# The separate `// LEGOID nn - Name` comment lines above each definition are
# the real official LEGO catalog colour number — a third, distinct numbering
# system from both Rebrickable's own `colors.id` and LDraw's own CODE — not
# useful for this crosswalk and deliberately not parsed here.
_LDCONFIG_COLOUR_RE = re.compile(r"0\s+!COLOUR\s+(\S+)\s+.*?CODE\s+(\d+)")


def normalize_color_name(name: str) -> str:
    """A LEGO colour's name, normalized enough to compare Rebrickable's naming
    (e.g. 'Trans-Red', 'Light Gray') against LDraw's (e.g. 'Trans_Red',
    'Light_Grey') and find they're the same colour."""
    normalized = re.sub(r"[-_]", " ", name.strip().lower())
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.replace("gray", "grey")


def parse_ldconfig_colors(ldconfig_text: str) -> dict[str, int]:
    """LDraw's official LDConfig.ldr -> {normalized colour name: LDraw CODE}.
    First definition wins where a name repeats."""
    colors: dict[str, int] = {}
    for match in _LDCONFIG_COLOUR_RE.finditer(ldconfig_text):
        name, code = match.group(1), int(match.group(2))
        colors.setdefault(normalize_color_name(name), code)
    return colors


def match_colors(rebrickable_colors: Iterable[Mapping], ldraw_colors_by_name: Mapping[str, int]) -> dict[int, int]:
    """Rebrickable colours -> {color_id: ldraw_color_id}, matched by
    normalized name. Rebrickable colours the LDraw colour library doesn't
    define (e.g. Duplo/HO/Modulex-specific colours) are simply omitted, not
    guessed at."""
    matched: dict[int, int] = {}
    for row in rebrickable_colors:
        ldraw_color_id = ldraw_colors_by_name.get(normalize_color_name(row["name"]))
        if ldraw_color_id is not None:
            matched[int(row["id"])] = ldraw_color_id
    return matched


def strip_decoration_suffix(part_num: str) -> str:
    return _DECORATION_SUFFIX_RE.sub("", part_num)


def list_ldraw_part_ids(parts_dir: Path) -> set[str]:
    """The real, current set of LDraw part ids — every `<id>.dat` filename
    directly under an extracted LDraw library's `parts/` directory (its
    subdirectories, e.g. `s/` sub-files and `48/` high-res primitives, aren't
    standalone real-world parts and are deliberately excluded by not
    recursing)."""
    return {path.stem for path in parts_dir.glob("*.dat")}


def match_parts(rebrickable_part_nums: Iterable[str], ldraw_part_ids: set[str]) -> dict[str, str]:
    """Rebrickable part numbers -> {part_num: ldraw_part_id}, for parts that
    are actually, verifiably present in the LDraw parts library — an exact
    filename hit first, falling back to the decoration-stripped base mold
    only when *that* is itself a real LDraw file. A part missing from LDraw
    even after stripping is omitted, not guessed at."""
    matched: dict[str, str] = {}
    for part_num in rebrickable_part_nums:
        if part_num in ldraw_part_ids:
            matched[part_num] = part_num
            continue
        base = strip_decoration_suffix(part_num)
        if base != part_num and base in ldraw_part_ids:
            matched[part_num] = base
    return matched


def build_colors_crosswalk(rebrickable_colors: Iterable[Mapping], ldconfig_text: str) -> list[dict]:
    ldraw_colors_by_name = parse_ldconfig_colors(ldconfig_text)
    matched = match_colors(rebrickable_colors, ldraw_colors_by_name)
    return [
        {"color_id": color_id, "ldraw_color_id": ldraw_color_id}
        for color_id, ldraw_color_id in sorted(matched.items())
    ]


def build_parts_crosswalk(rebrickable_part_nums: Iterable[str], ldraw_part_ids: set[str]) -> list[dict]:
    matched = match_parts(rebrickable_part_nums, ldraw_part_ids)
    return [
        {"part_num": part_num, "ldraw_part_id": ldraw_part_id} for part_num, ldraw_part_id in sorted(matched.items())
    ]


def fetch_ldraw_crosswalks(
    ldraw_dir: Path,
    data_dir: Path,
    api_token: str | None = None,
    fetch: Callable[[str, str | None], bytes] = fetch_and_gunzip,
) -> None:
    """Rebuild data/ldraw_parts_crosswalk.csv and ldraw_colors_crosswalk.csv
    from Rebrickable's bulk colour/part dumps and a real, already-extracted
    LDraw parts library (`ldraw_dir` — same LDRAWDIR convention render_with_ldview
    uses). The network I/O boundary this module's __main__ wraps, mirroring
    fetch_rebrickable.fetch_rebrickable_dump's fakeable-`fetch` pattern so it
    can be exercised in tests without a real network call.
    """
    colors_csv = fetch(f"{REBRICKABLE_DOWNLOAD_BASE_URL}/colors.csv.gz", api_token)
    rebrickable_colors = list(csv.DictReader(io.StringIO(colors_csv.decode())))

    parts_csv = fetch(f"{REBRICKABLE_DOWNLOAD_BASE_URL}/parts.csv.gz", api_token)
    rebrickable_part_nums = [row["part_num"] for row in csv.DictReader(io.StringIO(parts_csv.decode()))]

    ldconfig_text = (ldraw_dir / "LDConfig.ldr").read_text()
    ldraw_part_ids = list_ldraw_part_ids(ldraw_dir / "parts")

    data_dir.mkdir(parents=True, exist_ok=True)
    colors_rows = build_colors_crosswalk(rebrickable_colors, ldconfig_text)
    write_csv(data_dir / "ldraw_colors_crosswalk.csv", ["color_id", "ldraw_color_id"], colors_rows)

    parts_rows = build_parts_crosswalk(rebrickable_part_nums, ldraw_part_ids)
    write_csv(data_dir / "ldraw_parts_crosswalk.csv", ["part_num", "ldraw_part_id"], parts_rows)

    print(f"colors: {len(colors_rows)} matched / {len(rebrickable_colors)} total")
    print(f"parts: {len(parts_rows)} matched / {len(rebrickable_part_nums)} total")


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent.parent
    fetch_ldraw_crosswalks(
        ldraw_dir=Path(os.environ["LDRAWDIR"]),
        data_dir=repo_root / "data",
        api_token=os.environ.get("REBRICKABLE_API_TOKEN"),
    )
