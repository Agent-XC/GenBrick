import re

import pytest

from space.predict import path_text_to_ldr, predict

# A minimal, valid single-node path-text sample (bricknet's grammar: a
# "node" line alone is a complete sample) — stands in for a real model's
# stochastic output so path2ldr conversion and response shaping are
# exercised without loading Qwen3-0.6B + LoRA adapters in routine test runs.
VALID_PATH_TEXT = "a brick 2x4 | red\n"

LDR_PART_LINE = re.compile(r"^1 \d+ .+\.dat$")


def _fake_generate(caption: str) -> str:
    return VALID_PATH_TEXT


def test_predict_returns_non_empty_ldr_text_with_a_plausible_header():
    result = predict("a red brick", generate=_fake_generate)

    assert result["ldr"]
    assert LDR_PART_LINE.match(result["ldr"].splitlines()[0])


def test_predict_passes_the_caption_through_to_the_generate_seam():
    seen = []

    def recording_generate(caption: str) -> str:
        seen.append(caption)
        return VALID_PATH_TEXT

    predict("a small blue car", generate=recording_generate)

    assert seen == ["a small blue car"]


def test_predict_propagates_a_parse_error_from_unparseable_path_text():
    with pytest.raises(ValueError, match="could not parse generated path text"):
        predict("a caption", generate=lambda caption: "not valid path text")


def test_path_text_to_ldr_converts_a_single_node_sample():
    ldr_text = path_text_to_ldr(VALID_PATH_TEXT)

    assert LDR_PART_LINE.match(ldr_text.splitlines()[0])
    assert ldr_text.endswith(".dat\n")
