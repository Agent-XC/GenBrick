import gzip
import os
import urllib.request
from collections.abc import Callable
from pathlib import Path

from pipeline.intermediate import RAW_TABLES

REBRICKABLE_DOWNLOAD_BASE_URL = "https://cdn.rebrickable.com/media/downloads"

# The tables pipeline.intermediate.RAW_TABLES reads, derived rather than
# re-listed by hand so the two can't drift — Rebrickable's dump has other
# tables (part_categories, inventory_sets, part_relationships, ...) this
# project never uses, so they're never fetched.
RAW_TABLE_NAMES = tuple(RAW_TABLES.keys())


def fetch_and_gunzip(url: str, api_token: str | None = None) -> bytes:
    """Real HTTP GET of a gzip-compressed Rebrickable bulk-download CSV — the
    network I/O boundary fetch_rebrickable_dump wraps so it can be faked in
    tests.

    Rebrickable's bulk downloads (cdn.rebrickable.com/media/downloads/) are
    public and don't require a key, but `api_token` — read from the
    REBRICKABLE_API_TOKEN GitHub Actions secret, never committed — is sent as
    an Authorization header when set, in case that ever changes.
    """
    request = urllib.request.Request(url)
    if api_token:
        request.add_header("Authorization", f"key {api_token}")
    with urllib.request.urlopen(request, timeout=60) as response:
        return gzip.decompress(response.read())


def fetch_rebrickable_dump(
    raw_dir: Path,
    api_token: str | None = None,
    fetch: Callable[[str, str | None], bytes] = fetch_and_gunzip,
) -> None:
    """Download Rebrickable's latest CSV dump into 01_raw — INITIAL_PROJECT_SPEC.md
    §7 step 2 / §12's fetch_rebrickable.py. Overwrites each of RAW_TABLE_NAMES'
    CSVs with this week's dump; §3's "raw data is immutable" means never
    hand-patched by downstream layers, not never-refreshed — 01_raw itself
    isn't committed to version control (see .gitignore), so there's no history
    to disturb.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    for table in RAW_TABLE_NAMES:
        csv_bytes = fetch(f"{REBRICKABLE_DOWNLOAD_BASE_URL}/{table}.csv.gz", api_token)
        (raw_dir / f"{table}.csv").write_bytes(csv_bytes)


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent.parent
    fetch_rebrickable_dump(
        raw_dir=repo_root / "data" / "01_raw",
        api_token=os.environ.get("REBRICKABLE_API_TOKEN"),
    )
