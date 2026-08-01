"""Standalone caption -> LDR generation logic (PHASE2_PROJECT_SPEC.md §1/§5).

No Gradio wrapper and no live deployment here — this module is the seam a
future Space's app.py wraps (see issue #21). Collision-mesh fetching/scoring
(`bricknet fetch-meshes`, `bricknet score`) is deliberately not wired in.
"""

from collections.abc import Callable

from bricknet.graph import graph_to_ldr, tree_to_graph
from bricknet.tree import parse_sample

BASE_MODEL_ID = "Qwen/Qwen3-0.6B"
PT_ADAPTER_ID = "kulits/BrickNet-0.6B-PT"
SFT_ADAPTER_ID = "kulits/BrickNet-0.6B-SFT"

# scripts/generate.py's own defaults for its conditional (SFT, prompts_file)
# generation mode.
MAX_NEW_TOKENS = 4096
TEMPERATURE = 1.0
TOP_K = 20
TOP_P = 0.95

_model_and_tokenizer = None


def _load_model_and_tokenizer():
    """Loads the base model plus both LoRA adapters, PT then SFT, merging
    each in turn (scripts/generate.py's --lora order for conditional
    generation) so inference runs against a single merged model rather than
    paying PEFT's adapter-swap overhead per request.
    """
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    model = AutoModelForCausalLM.from_pretrained(BASE_MODEL_ID, dtype=torch.bfloat16)
    for adapter_id in (PT_ADAPTER_ID, SFT_ADAPTER_ID):
        model = PeftModel.from_pretrained(model, adapter_id)
        model = model.merge_and_unload()
    model.eval()

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_ID, padding_side="left")
    tokenizer.pad_token = tokenizer.eos_token
    model.generation_config.pad_token_id = tokenizer.pad_token_id
    return model, tokenizer


def _get_model_and_tokenizer():
    """Lazy process-wide singleton: the first call loads the model and both
    adapters, every later call (in this process) reuses them.
    """
    global _model_and_tokenizer
    if _model_and_tokenizer is None:
        _model_and_tokenizer = _load_model_and_tokenizer()
    return _model_and_tokenizer


def generate_path_text(caption: str) -> str:
    """One caption -> one generated path-text sample (num_samples=1): the
    conditional/SFT branch of scripts/generate.py's generation logic, minus
    the multi-GPU/multi-sample batching a live Space request doesn't need.
    """
    import torch

    # ZeroGPU (space/app.py's @spaces.GPU) runs each call in a forked worker
    # process, and forks inherit the parent's torch RNG state verbatim
    # rather than seeding fresh from OS entropy (spaces/zero/torch's own
    # worker init never reseeds). Left unseeded, every freshly-forked worker
    # starts do_sample=True generation from the same RNG state, so repeat
    # calls with the same caption produce byte-identical output (issue #24).
    # torch.seed() draws a real seed from the OS, breaking that inheritance.
    torch.seed()

    model, tokenizer = _get_model_and_tokenizer()
    newline_id = tokenizer.encode("\n", add_special_tokens=False)[0]
    prompt_ids = tokenizer.encode(caption, add_special_tokens=False) + [newline_id]
    input_ids = torch.tensor([prompt_ids])
    with torch.inference_mode():
        output = model.generate(
            input_ids,
            attention_mask=torch.ones_like(input_ids),
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=True,
            temperature=TEMPERATURE,
            top_k=TOP_K,
            top_p=TOP_P,
        )
    return tokenizer.decode(output[0][len(prompt_ids) :], skip_special_tokens=True)


def path_text_to_ldr(path_text: str) -> str:
    """bricknet's path2ldr conversion (mirrors `python -m bricknet
    path2ldr`'s own implementation): parse the generated path text into a
    Tree, realize it as a Graph, and serialize that Graph as LDR text.
    """
    result = parse_sample(path_text)
    if result.error is not None:
        raise ValueError(f"could not parse generated path text: {result.error}")
    return graph_to_ldr(tree_to_graph(result.tree))


def predict(caption: str, generate: Callable[[str], str] = generate_path_text) -> dict:
    """The backend's core generation entry point: caption in, LDR text out.

    `generate` defaults to the real (model-loading, heavy) generator but is
    overridable — e.g. by a test that wants to exercise path2ldr conversion
    and response shaping without loading the actual model.
    """
    path_text = generate(caption)
    return {"ldr": path_text_to_ldr(path_text)}
