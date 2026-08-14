"""Compare generation output across adapter stacks, for the same caption and
seed (issue #26) — the follow-up comparison issue #25's local generation was
built for, investigating issue #24's open question 1 (whether the PT/SFT
LoRA adapters are actually effective).

If PT+SFT output differs meaningfully from PT-only and from no-adapter for
the same seed (and parses more reliably via `bricknet.tree.parse_sample`),
the adapters are doing real work; if it looks the same as PT-only or
no-adapter, that's evidence the SFT (or both) adapter isn't taking effect.
"""

import html
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from bricknet.tree import parse_sample

from space.predict import ADAPTER_STACKS, generate_path_text_locally


@dataclass
class ComparisonResult:
    caption: str
    stack_name: str
    seed: int
    path_text: str
    parse_error: str | None

    @property
    def parsed_ok(self) -> bool:
        return self.parse_error is None


def compare_adapter_stacks(
    captions: Sequence[str],
    seeds: Mapping[str, int],
    adapter_stacks: Mapping[str, Sequence[str]] = ADAPTER_STACKS,
    generate: Callable[[str, Sequence[str], int], str] = generate_path_text_locally,
) -> list[ComparisonResult]:
    """Runs every caption through every adapter stack, holding `seeds[caption]`
    constant across all of that caption's stacks — so any difference in
    output between stacks is attributable to the adapter stack itself,
    isolated from `do_sample=True`'s own sampling noise (see #25).
    """
    results = []
    for caption in captions:
        seed = seeds[caption]
        for stack_name, adapter_ids in adapter_stacks.items():
            path_text = generate(caption, adapter_ids, seed)
            parse_error = parse_sample(path_text).error
            results.append(ComparisonResult(caption, stack_name, seed, path_text, parse_error))
    return results


def render_report(results: Sequence[ComparisonResult]) -> str:
    """Markdown report, one section per caption, tabulating each adapter
    stack's raw generated path text and bricknet parse result side by side.
    """
    lines = ["# Adapter stack comparison (issue #26)", ""]
    captions = list(dict.fromkeys(r.caption for r in results))
    for caption in captions:
        caption_results = [r for r in results if r.caption == caption]
        lines.append(f'## "{caption}" (seed={caption_results[0].seed})')
        lines.append("")
        lines.append("| Adapter stack | Parses? | Path text |")
        lines.append("|---|---|---|")
        for r in caption_results:
            status = "yes" if r.parsed_ok else f"no — {_escape_cell(r.parse_error)}"
            lines.append(f"| {r.stack_name} | {status} | <code>{_escape_cell(r.path_text)}</code> |")
        lines.append("")
    return "\n".join(lines)


def _escape_cell(text: str) -> str:
    """Markdown table cells break on a literal newline or an unescaped `|`,
    and raw LLM output may contain either. Wraps in `<code>` rather than a
    backtick span so the `\\n` -> `<br>` conversion below actually renders
    as a line break instead of literal text (backtick spans render their
    contents as-is, HTML tags included) — HTML-escaped first so any `<`/`&`
    in the raw text can't be misread as markup once wrapped in `<code>`.
    """
    return html.escape(text, quote=False).replace("|", "\\|").replace("\n", "<br>")
