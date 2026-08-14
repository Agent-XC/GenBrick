"""Generate one path-text sample locally, with a selectable PT/SFT adapter
stack (issue #25) — investigates issue #24's open question 1 (whether the
PT/SFT LoRA adapters are actually effective) without needing ZeroGPU quota
or `HF_TOKEN`.

Runs entirely on CPU against `space.predict`'s base-model + adapter loading
logic, generalized (this issue) to take a configurable adapter list instead
of always merging PT then SFT. The model + adapters (~1.6GB total) download
once via the standard Hugging Face cache and are reused across runs.

Pass the same --seed across separate runs (with different --adapters) for
the same --caption to isolate the adapter stack's effect from
do_sample=True's own sampling noise.

Usage:
    .venv/bin/python scripts/generate_local_sample.py "a small red car" --adapters pt+sft --seed 0
"""

import argparse

from space.predict import ADAPTER_STACKS, generate_path_text_locally


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("caption", help="Caption to condition generation on")
    parser.add_argument(
        "--adapters",
        choices=sorted(ADAPTER_STACKS),
        default="pt+sft",
        help="Adapter stack to merge onto the base model (default: pt+sft, the deployed config)",
    )
    parser.add_argument("--seed", type=int, required=True, help="Explicit torch RNG seed for reproducible sampling")
    args = parser.parse_args()

    path_text = generate_path_text_locally(args.caption, ADAPTER_STACKS[args.adapters], args.seed)
    print(path_text)


if __name__ == "__main__":
    main()
