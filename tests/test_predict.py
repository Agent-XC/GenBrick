import re

import peft
import pytest
import torch
import transformers

import space.predict as predict_module
from space.predict import (
    PT_ADAPTER_ID,
    SFT_ADAPTER_ID,
    generate_path_text,
    generate_path_text_locally,
    path_text_to_ldr,
    predict,
)

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


class _FakeGenerationConfig:
    def __init__(self):
        self.pad_token_id = None


class _FakeBaseModel:
    def __init__(self, tag="base"):
        self.tag = tag
        self.generation_config = _FakeGenerationConfig()

    def eval(self):
        return self


class _FakePeftWrapper:
    def __init__(self, base_model, adapter_id):
        self._base_model = base_model
        self._adapter_id = adapter_id

    def merge_and_unload(self):
        return _FakeBaseModel(tag=f"{self._base_model.tag}+{self._adapter_id}")


class _FakeHFTokenizer:
    def __init__(self):
        self.eos_token = "<eos>"
        self.pad_token = None
        self.pad_token_id = 0


def _patch_fake_hf_loading(monkeypatch, merge_calls):
    monkeypatch.setattr(
        transformers.AutoModelForCausalLM,
        "from_pretrained",
        lambda model_id, **kwargs: _FakeBaseModel(),
    )
    monkeypatch.setattr(
        transformers.AutoTokenizer,
        "from_pretrained",
        lambda model_id, **kwargs: _FakeHFTokenizer(),
    )

    def fake_peft_from_pretrained(model, adapter_id):
        merge_calls.append(adapter_id)
        return _FakePeftWrapper(model, adapter_id)

    monkeypatch.setattr(peft.PeftModel, "from_pretrained", fake_peft_from_pretrained)


def test_load_model_and_tokenizer_merges_exactly_the_given_adapters(monkeypatch):
    merge_calls = []
    _patch_fake_hf_loading(monkeypatch, merge_calls)

    model, _ = predict_module._load_model_and_tokenizer(())
    assert merge_calls == []
    assert model.tag == "base"

    merge_calls.clear()
    model, _ = predict_module._load_model_and_tokenizer((PT_ADAPTER_ID,))
    assert merge_calls == [PT_ADAPTER_ID]
    assert model.tag == f"base+{PT_ADAPTER_ID}"

    merge_calls.clear()
    model, _ = predict_module._load_model_and_tokenizer((PT_ADAPTER_ID, SFT_ADAPTER_ID))
    assert merge_calls == [PT_ADAPTER_ID, SFT_ADAPTER_ID]
    assert model.tag == f"base+{PT_ADAPTER_ID}+{SFT_ADAPTER_ID}"


def test_load_model_and_tokenizer_defaults_to_the_deployed_pt_plus_sft_stack(monkeypatch):
    merge_calls = []
    _patch_fake_hf_loading(monkeypatch, merge_calls)

    predict_module._load_model_and_tokenizer()

    assert merge_calls == [PT_ADAPTER_ID, SFT_ADAPTER_ID]


def test_generate_path_text_locally_seeds_deterministically_from_the_given_seed(monkeypatch):
    # The opposite of generate_path_text's #24 reseed-per-call fix: this
    # local variant is used for adapter-stack comparisons that need the same
    # seed to produce the same output across different adapter stacks, to
    # isolate the adapter's effect from do_sample=True sampling noise.
    events = []
    monkeypatch.setattr(torch, "manual_seed", lambda seed: events.append(("seed", seed)))

    def fake_load(adapter_ids):
        events.append(("load", tuple(adapter_ids)))
        return _FakeModel(events), _FakeTokenizer()

    monkeypatch.setattr(predict_module, "_load_model_and_tokenizer", fake_load)

    result = generate_path_text_locally("a red brick", adapter_ids=(PT_ADAPTER_ID,), seed=42)

    assert events == [("seed", 42), ("load", (PT_ADAPTER_ID,)), "generate"]
    assert result == VALID_PATH_TEXT
