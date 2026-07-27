# LEGO Collection, Discovery & Generative Design — Phase 2 Spec (Reference Design)

## Status

**Not built now.** This document supersedes §13–§16 of `INITIAL_PROJECT_SPEC.md`
with a more concrete reference design, based on subsequent research into
BrickNet as a candidate implementation. It remains, as before, a design
document only:

- No model training, fine-tuning, or inference runs as part of the current
  repo's work.
- No live "prompt → creation" feature is deployed as part of Phase 1.
- Nothing in this document authorizes starting implementation. It exists so
  that when Phase 2 *is* greenlit, the architecture, dependencies, and open
  items are already scoped rather than researched from scratch.

This is a **fan project, not affiliated with or endorsed by the LEGO Group**,
per §1 of the Phase 1 spec. That disclaimer applies to this document too.

## 1. Chosen candidate: BrickNet

Following the comparison in §14 of the Phase 1 spec, BrickNet (Kulits &
Schmid, CVPR 2026) is the working reference implementation this design is
built around, on the strength of its real-world part diversity and typed
connector graph — the better architectural fit for generating from an
*owned, heterogeneous* collection rather than a small generic brick
vocabulary. BrickGPT/LegoGPT remains the fallback if BrickNet's release
state or licensing turns out to be a blocker at implementation time (see §7).

### 1.1 What BrickNet actually is

- Base model: `Qwen/Qwen3-0.6B`, a 0.6B-parameter LLM — small by current
  standards, not a diffusion or 3D-native model.
- Two stacked LoRA adapters via `peft`: a pretrain (PT) adapter for
  unconditional generation, and a caption-conditioned SFT adapter that
  stacks on top of it for prompt-driven generation.
- Package: `pip install bricknet`. Core modules — `core`, `data`, `tree`,
  `collision`, `graph`, `score` — cover LDR ↔ Graph ↔ Tree conversion,
  collision checking, and scoring of generated samples.
- Representations: LDR (absolute part poses, standard LDraw text) ↔ Graph
  (typed connector edges, `.npz`) ↔ Tree (quantized spanning tree / "path
  text," the format the model is trained on).
- Optional collision checking requires ~1.6GB of per-part collision meshes,
  fetched separately (`python -m bricknet fetch-meshes`) — not required for
  generation or rendering, only for physical-validity scoring.

## 2. Reference architecture

A minimal split between a static frontend and a hosted inference backend:

```
GitHub Pages (static)              Hugging Face Space (Gradio, CPU)
┌─────────────────────┐            ┌──────────────────────────────┐
│ index.html           │  fetch()  │ app.py                        │
│ - caption input       │ ───────► │ - loads Qwen3-0.6B once at    │
│ - "Generate" button    │          │   startup                    │
│ - renders returned     │ ◄─────── │ - stacks PT + SFT LoRA        │
│   LDR / image          │  JSON    │   adapters via peft           │
└─────────────────────┘            │ - predict(caption):           │
                                    │   generate → path2ldr → return│
                                    └──────────────────────────────┘
```

- **Frontend (GitHub Pages):** a single static page — text input, submit
  button, a `fetch()` call to the Space's API, and a way to display the
  result (raw LDR text at minimum; an in-browser LDraw/3D viewer as a
  stretch goal). If the viewer is ever built, it renders client-side —
  Phase 1's existing procedural LDraw renderer (see `CONTEXT.md`'s
  `Render coverage`) is built for the offline weekly batch refresh, not
  this backend's interactive per-request path, and reusing it server-side
  is explicitly out of scope for this design (ADR-0004's reasoning
  applies to preview rendering too, though it wasn't judged surprising
  enough on its own to warrant a separate ADR).
- **Backend (Hugging Face Space):** a Gradio app on the **free CPU tier**
  (2 vCPU / 16GB RAM). At startup it loads the base model and both LoRA
  adapters once; each request runs one sample through `generate.py`'s
  logic (not the paper's batch settings of `num_samples=2048,
  batch_size=128` — just `num_samples=1` per caption) and converts the
  output path text to `.ldr` via `path2ldr`.
- **CORS** must be enabled on the Space so the `github.io` origin can call
  it.
- **Collision meshes are out of scope for the minimal version** — the
  1.6GB mesh download and `bricknet score` step are only needed for
  physical-validity checking, not for generation or LDR rendering. Skipping
  them keeps the Space's disk footprint and cold-start time small.

## 3. Cost model

| Tier | Cost | Notes |
|---|---|---|
| Free CPU Space | $0/month | Model + adapters are well under 1GB combined. Cold start after sleep (Space sleeps after ~48h inactivity): roughly 30–60s to reload model + adapters. Per-request generation: low single-digit seconds for one sample on CPU, since the model is only 0.6B parameters. |
| Paid always-on CPU | A few $/month | Only needed to eliminate cold-start latency for a public-facing demo. |
| GPU tier | Not expected to be needed | A 0.6B model does not require GPU inference for single-sample interactive use. |

No paid tier is required to make the reference design work; it's an
optional latency improvement, not a functional requirement.

## 4. Integration with Phase 1's data layer

Per §15 of the Phase 1 spec, when Phase 2 is actually built it consumes the
already-designed export contract:

```
exports/available_parts.json   -- [{part_num, color_id, quantity, ldraw_part_id, ldraw_color_id}, ...]
exports/owned_sets.json        -- snapshot of owned_boxes + basic set metadata
```

BrickNet-specific implication: `available_parts.json`'s `ldraw_part_id` /
`ldraw_color_id` fields are what the finished design's Graph
representation would be validated *against, after generation* — see ADR-0004
for why this is post-hoc scoring rather than masking BrickNet's part
vocabulary during generation. The concept that scoring produces is
deliberately unnamed and distinct from Phase 1's `Buildability` — see
`CONTEXT.md`. This validation logic remains a Phase 2 implementation
detail beyond the decision of *when* it runs; not designed in depth here.

## 5. Sample generation flow (reference, not implemented)

```
1. User submits a caption via the GitHub Pages form.
2. Space's predict(caption):
   a. Run BrickNet generation (Qwen3-0.6B + PT + SFT LoRA adapters,
      num_samples=1) → path text.
   b. Convert path text → .ldr via bricknet's path2ldr.
   c. (Optional, later) validate the resulting Graph against
      exports/available_parts.json — post-hoc, not as a generation-time
      mask (ADR-0004) — once the Phase 1 export contract is wired up.
3. Return the .ldr to the frontend as raw text — the minimal version does
   not render a preview server-side (see §2; a viewer, if built, is a
   client-side stretch goal, not part of this flow).
```

## 6. Explicit non-goals (unchanged from Phase 1 spec §16)

- No model training, fine-tuning, or inference runs as part of this repo's
  current work.
- No live "prompt → creation" feature on the website today.
- No commitment to BrickNet over BrickGPT/LegoGPT as a final decision —
  this remains a starting point for research, refined with more detail
  than §14's original comparison table, not a locked-in choice.

## 7. Open items to confirm before implementation

- **BrickNet's adapter license terms — still not confirmed, re-verify before implementation.**
  Re-verified 2026-07-27: `github.com/kulits/BrickNet` is live and
  functional (`pip install bricknet` works, MIT-licensed code repo, active
  maintenance) — the release-state volatility flagged below is resolved,
  the repo is real. However, the published LoRA adapters themselves
  (e.g. `kulits/BrickNet-0.6B-SFT` on Hugging Face) carry **no license
  field at all** — not research-only, not permissive, just unset. That is
  the actual open risk: a missing adapter license, not a missing repo.
  Confirm the adapter license (via the model card or directly with the
  authors) before treating a public demo as viable; per §7's fallback
  plan, an unresolved/restrictive adapter license is grounds to switch to
  BrickGPT/LegoGPT, but this has not been decided as of this writing —
  BrickNet remains primary pending that confirmation.
- **Data distribution terms** — BrickNet's training datasets are
  distributed via a request form, not bulk download; irrelevant to running
  inference with the published adapters, but relevant if fine-tuning on
  top of BrickNet is ever considered.
- **Fallback plan** — if BrickNet's license or release state is a blocker
  at implementation time, BrickGPT/LegoGPT (MIT-licensed, more mature,
  ~1.7k GitHub stars, documented Gradio demo) is the fallback per §14 of
  the Phase 1 spec, at the cost of its smaller, more generic part
  vocabulary.
