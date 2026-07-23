# GenBrick

Catalogs an owned LEGO collection, aggregates it into one brick pool, and surfaces which other official sets are buildable from or compositionally similar to what's owned.

## Language

**Buildability**:
The % of a candidate set's required `(part_num, color_id, quantity)` covered by the owned brick pool. Schema field: `buildability.coverage_pct`.
_Avoid_: coverage (alone — ambiguous with render coverage)

**Render coverage**:
The % of a set's parts that resolved to LDraw geometry when generating its procedural image. Schema field: `set_renders.render_coverage_pct` (renamed from `coverage_pct` to avoid colliding with Buildability's coverage concept).
_Avoid_: coverage_pct

**Set**:
A catalog entry from Rebrickable — an official LEGO product identified by `set_num`. Exists in the catalog whether or not it's owned.
_Avoid_: kit, product

**Box**:
An owned Set — the physical copy sitting in the collection. Exactly one box per `set_num`; owning two physical copies of the same set isn't modeled (`owned_boxes` has no id or quantity column — a deliberate scope decision, not an oversight).
_Avoid_: kit, item

**Candidate set**:
A Set that isn't owned but falls within the current `universe_scope` — eligible to be scored for Buildability and compared for Similarity.
_Avoid_: suggestion, recommendation

**Owned brick pool**:
The sum of `inventory_parts` across all owned Boxes, grouped by `(part_num, color_id)`. Treated as one pooled, disassembled collection — does not account for pieces currently assembled into another owned Box.
_Avoid_: inventory, stash

**Similarity**:
A composition-based score between any two Sets in the current universe scope (e.g. weighted Jaccard/cosine over `(part_num, color_id)` multisets), independent of ownership. Stored sparse as the top 10 per set in `similarity_topk`. Distinct from Buildability, which is ownership-directional (pool → candidate) rather than symmetric.
_Avoid_: match, recommendation

**Universe scope**:
The config-selected boundary (`owned_themes` | `retail` | `all`) on which Sets are eligible to be Candidate sets.
_Avoid_: catalog (the full Rebrickable catalog is broader than the current scope)
