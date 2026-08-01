import re

import pytest
import torch

import space.predict as predict_module
from space.predict import generate_path_text, path_text_to_ldr, predict

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


class _FakeTokenizer:
    def encode(self, text, add_special_tokens=False):
        return [1]

    def decode(self, ids, skip_special_tokens=True):
        return VALID_PATH_TEXT


class _FakeModel:
    def __init__(self, call_order):
        self._call_order = call_order

    def generate(self, input_ids, **kwargs):
        self._call_order.append("generate")
        return torch.tensor([[1, 1, 2]])


def test_generate_path_text_reseeds_torch_rng_before_sampling(monkeypatch):
    # Regression test for issue #24: a ZeroGPU worker forked from a stale
    # parent RNG state must not sample from that inherited state.
    call_order = []
    monkeypatch.setattr(torch, "seed", lambda: call_order.append("seed"))
    monkeypatch.setattr(
        predict_module,
        "_get_model_and_tokenizer",
        lambda: (_FakeModel(call_order), _FakeTokenizer()),
    )

    generate_path_text("a red brick")

    assert call_order == ["seed", "generate"]
