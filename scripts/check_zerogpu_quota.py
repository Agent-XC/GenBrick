"""Check the live Space's ZeroGPU quota (issue #21) without guessing at the
Hugging Face UI.

There's no read-only "check my quota" endpoint — the `spaces` package (see
its zero/client.py) only reports `left`/`wait` as a side effect of an actual
schedule attempt, which happens inside the Space when its @spaces.GPU
function is called. This script makes that call:

- If quota is exhausted, the rejection is free (no GPU is ever granted) and
  its error message contains exactly the numbers we want.
- If quota is NOT exhausted, this call succeeds and actually runs a real
  generation, consuming real GPU time — that's unavoidable from outside the
  Space, not a bug in this script.

Requires `gradio_client` (`.venv/bin/pip install gradio_client`) — not added
to this repo's own dependencies since it's only needed for this occasional
manual check, not for routine test/pipeline runs.

Usage:
    .venv/bin/python scripts/check_zerogpu_quota.py [--space XCoubez/GenBrick]
"""

import argparse
import re
import sys

from gradio_client import Client
from gradio_client.exceptions import AppError

QUOTA_RE = re.compile(r"\((\d+)s requested vs\. (\d+)s left\)\. Try again in ([\d:]+)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--space", default="XCoubez/GenBrick", help="owner/space-name")
    parser.add_argument("--caption", default="a small red car")
    args = parser.parse_args()

    client = Client(args.space)
    try:
        result = client.predict(args.caption, api_name="/_generate")
    except AppError as e:
        message = str(e)
        match = QUOTA_RE.search(message)
        if match is None:
            sys.exit(f"Call failed, but not on quota — real error:\n{message}")
        requested, left, wait = match.groups()
        print(f"requested={requested}s left={left}s wait={wait}")
        return

    print(f"Quota was available — this call ran for real. Result: {str(result)[:200]}")


if __name__ == "__main__":
    main()
