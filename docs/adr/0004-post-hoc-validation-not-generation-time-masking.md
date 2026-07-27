---
status: proposed — Phase 2 is not yet implemented (see PHASE2_PROJECT_SPEC.md)
---

# Score generated Graphs against the owned pool after generation, not by masking BrickNet's vocabulary during generation

`PHASE2_PROJECT_SPEC.md` §4/§5 left open whether "buildable from what you
own" for a BrickNet-generated design would be enforced by masking
`available_parts.json`'s part/color vocabulary into generation itself
(constrained decoding), or by generating freely and scoring the result
against the owned pool afterward.

Chose post-hoc scoring. Masking would require reverse-engineering how
BrickNet's Tree/path-text vocabulary maps to `ldraw_part_id`/
`ldraw_color_id` and hooking constraints into a third-party 0.6B model's
internals — a lot of undocumented surface area to take on for a fine-tune
this project didn't train. It also fails ungracefully: the reference
design's cost model budgets one CPU sample per request with no retry
loop, so an owned pool too restrictive for what the SFT adapter learned to
produce would degrade to an opaque bad/empty output. Post-hoc scoring
degrades gracefully instead — always producing *some* score, the same way
Phase 1's `Buildability` already works — and keeps the backend a single
`predict()` call as scoped.

The resulting score is a distinct concept from `Buildability` (see
`CONTEXT.md`) — it scores a one-off generated Graph, not a stable catalog
Set — and is deliberately left unnamed until Phase 2 is actually scoped.
