"""Compare the three PT/SFT adapter stacks side by side for the same
captions (issue #26) — the follow-up comparison issue #25's local
generation was built for, answering issue #24's open question 1 (whether
the PT/SFT LoRA adapters are actually effective).

Runs entirely on CPU via `space.predict.generate_path_text_locally`, no
ZeroGPU quota or `HF_TOKEN` needed. Reruns the three captions #24 already
reported ("a small red car", "a flying red boat", "a red dragon") across all
three adapter stacks (none / pt / pt+sft), holding the seed constant per
caption across its three stacks (a different seed per caption, so results
aren't an artifact of one seed's own quirks) so any difference in output is
attributable to the adapter stack rather than `do_sample=True`'s own
sampling noise. Writes a Markdown report to `docs/research/` (gitignored —
see that directory's own note) so the finding can be cited back on #24.

Usage:
    .venv/bin/python scripts/compare_adapter_stacks.py
"""

import argparse
from pathlib import Path

from space.compare_adapters import compare_adapter_stacks, render_report

CAPTIONS = ("a small red car", "a flying red boat", "a red dragon")

REPORT_PATH = Path(__file__).parent.parent / "docs" / "research" / "issue-26-adapter-stack-comparison.md"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--seed-base",
        type=int,
        default=0,
        help="Base seed; caption N uses seed-base + N, held constant across that caption's three stacks (default: 0)",
    )
    parser.add_argument("--output", type=Path, default=REPORT_PATH, help=f"Report path (default: {REPORT_PATH})")
    args = parser.parse_args()

    seeds = {caption: args.seed_base + index for index, caption in enumerate(CAPTIONS)}
    results = compare_adapter_stacks(CAPTIONS, seeds)
    report = render_report(results)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
