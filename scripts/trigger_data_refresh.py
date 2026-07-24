"""Manually dispatch the "Weekly data refresh" GitHub Action
(.github/workflows/update-data.yml) instead of waiting for its Monday 06:00
UTC cron — useful right after a pipeline/site change to confirm it behaves
correctly against the real Rebrickable data before the next scheduled run.

Requires the GitHub CLI (`gh`), authenticated (`gh auth status`). Repo is
inferred from the git remote, same as docs/agents/issue-tracker.md's
convention for `gh` elsewhere in this repo — not hardcoded here.

Usage:
    .venv/bin/python scripts/trigger_data_refresh.py [--watch]
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = "update-data.yml"


def _gh(*args: str) -> str:
    result = subprocess.run(["gh", *args], cwd=REPO_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(result.stderr.strip() or f"gh {' '.join(args)} failed")
    return result.stdout


def trigger() -> str:
    """Dispatches the workflow and returns its run id. workflow_dispatch
    itself gives back no run id, so this polls `gh run list` briefly for the
    run it just created.
    """
    _gh("workflow", "run", WORKFLOW)
    for _ in range(10):
        time.sleep(2)
        runs = json.loads(
            _gh(
                "run", "list",
                "--workflow", WORKFLOW,
                "--event", "workflow_dispatch",
                "--limit", "1",
                "--json", "databaseId,status",
            )
        )
        if runs:
            return str(runs[0]["databaseId"])
    sys.exit("Dispatched, but couldn't find the new run — check `gh run list` manually.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--watch", action="store_true", help="Block and stream the run's status until it finishes."
    )
    args = parser.parse_args()

    run_id = trigger()
    url = _gh("run", "view", run_id, "--json", "url", "--jq", ".url").strip()
    print(f"Triggered: {url}")

    if args.watch:
        subprocess.run(["gh", "run", "watch", run_id, "--exit-status"], cwd=REPO_ROOT)


if __name__ == "__main__":
    main()
