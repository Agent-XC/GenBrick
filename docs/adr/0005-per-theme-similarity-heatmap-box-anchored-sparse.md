---
status: proposed — implementation ticket #35 not yet built
---

# Per-theme Similarity heatmap: Box-anchored, built from existing sparse `similarity_topk`, no new dense table

`INITIAL_PROJECT_SPEC.md` §8/§11 frame Similarity as a "similarity matrix" /
"pairwise similarity view/matrix". Issue #31 asked for a design decision before
#35 (blocked on this ADR) implements it, since the current ranked-list
`similarity.html` doesn't match that framing and #17's redesign ask singled it
out as needing its own design pass first.

## What the real data looks like

Queried the current production `site/data/lego.sqlite` (per-theme scope =
owned Boxes ∪ everything materialized into `inventories`, i.e. the full
`owned_themes` universe, not just Candidates that cleared the Buildability
floor):

| Theme | Sets in theme scope | Owned Boxes |
|---|---:|---:|
| Star Wars | 574 | 2 |
| Ninjago | 369 | 11 |
| Icons | 81 | 1 |
| Botanicals | 39 | 1 |

`similarity_topk` currently holds 570 rows total, covering only 175 of the
1,063 in-scope sets as an anchor (everyone else's every pairing scored below
`config/scope.json`'s `min_similarity_score_pct` floor, currently 15) — and
566 of those 570 rows are already same-theme (only 4 cross-theme rows exist).

Two things follow directly from this:

1. **A literal theme × theme dense grid is off the table regardless of the
   storage question.** A 574×574 (or even 369×369) grid is neither renderable
   as HTML nor readable by a person — this was never really about whether
   `similarity_topk`'s top-10-per-set cap has "gaps," it's that the naive
   reading of "matrix across a theme" doesn't scale to this project's actual
   theme sizes once `universe_scope: owned_themes` pulls in every set in an
   owned theme, not just the Candidates that already cleared Buildability's
   floor.
2. **The existing sparse top-10 data is already overwhelmingly same-theme in
   practice** (566/570 rows) and already concentrates on a small set of
   anchors. There's no evidence a dense per-theme computation would surface
   meaningfully more real signal than what's already being computed and
   thrown away at export time — it would mostly add zero/near-zero cells.

## Decision

**Box-anchored sparse matrix, reusing `similarity_topk` as-is — no new table,
no pipeline change.**

Per theme, the row axis is that theme's **owned Boxes only** (bounded: 1–11
today, grows only as slowly as the collection itself — never theme-sized).
The column axis is the **union of each row-Box's same-theme
`similarity_topk` matches**, looked up **bidirectionally** (a pair can be
stored from either set's top-10, not both — see Implementation notes),
deduplicated, sorted by best score descending. This bounds columns to at most
`10 × (owned Boxes in theme)` — 110 in Ninjago's worst case today, realistically
fewer once duplicate matches across rows collapse — and answers acceptance
criterion 2 as **(a) top-10-sparse is acceptable**, with uncovered cells left
blank rather than computed.

This directly resolves the "dense theme × theme matrix" framing in the
original spec/issue: the achievable, useful shape is a Box × relevant-matches
grid, not a full theme × theme grid, and that shape falls out of data already
computed and exported today.

### Wireframe

```
Theme: Ninjago
                     71768         71767        71769        71765
                   Cole's Dr…    Kai's Fire…    (Cand.)      (Cand.)
  71768 Cole's Dr…     —            42.1%         61.0%         —
  71767 Kai's Fire…  42.1%            —             —          38.4%

Theme: Icons
                     10281
                   Bonsai Tree
  10281 Bonsai Tree     —

Theme: Botanicals
  (no theme section — lone Box's every same-theme pairing scored below the
   15% floor, mirrors similarity.js's existing "skip anchor with zero
   matches" behavior)
```

Cell shading: a light→saturated color scale from the `min_similarity_score_pct`
floor (currently 15%) to 100%. Blank cells (`—`) are pairs with no stored
`similarity_topk` row in either direction — below the floor, or simply never
in either set's top-10 — shown identically to how similarity.js already drops
sub-floor matches today, not as a fake "0%".

### Interaction

- **Row/column headers are the click-throughs, not cells.** Each header is
  the set's name, linking to:
  - `box.html?set_num=…` if the set is an owned Box.
  - `candidate.html?set_num=…` if the set is a Candidate **present in
    `buildability`** (cleared `min_buildability_coverage_pct`).
  - Plain text (no internal link) with `officialLinkMarkup`'s existing
    official-link fallback if it's a Candidate in Similarity's wider scope
    but *not* in `buildability` — this scope gap already exists today
    (`similarity.js` currently links every match to `box.html?set_num=…`
    unconditionally, which 404s via box.js's "not found" branch for any
    non-owned match); the heatmap should fix it rather than carry it
    forward.
  - Cells themselves are inert except for a title/tooltip
    (`"71768 × 71767: 42.1%"`) — a cell sits between two sets and there's no
    single obviously-correct navigation target for it, whereas each header
    already has one.

- **Single-Box themes** (Icons, Botanicals today) can't show a Box×Box pair.
  Render the same grid component degenerate to one row (the lone Box) ×
  its same-theme Candidate matches — not a different UI. If that row would
  be entirely blank (as Botanicals is today), omit the theme's section
  entirely, mirroring `similarity.js`'s existing per-anchor empty-skip.

### Scope

One page (`similarity.html`), one section per theme in the same
group-and-loop shape `themes.js` already uses — **not** a separate page per
theme. This keeps the redesign a like-for-like replacement for the single nav
entry #27 removed and #35 restores, and reuses an established layout pattern
instead of inventing a second one.

## Implementation notes for #35 (non-binding, but should save a round-trip)

- The anchor query needs `similarity_topk` read bidirectionally per pair —
  `(set_num = box, other_set_num = match) OR (set_num = match, other_set_num
  = box)` — since a pair can be truncated out of one side's top-10 while
  surviving in the other's. A small `UNION`-based view mirroring the shape of
  `owned_brick_pool`/`owned_minifigs` in `reporting.py` would keep this out
  of hand-written JS SQL, but that's an implementation choice for #35, not
  fixed here.
- Reuse `themes.js`'s theme-grouping query shape (owned Boxes ∪ Candidates,
  joined through `sets`/`themes`) rather than re-deriving scope logic.
- No change to `pipeline/similarity.py`, `pipeline/primary.py`, or the
  `similarity_topk` schema — this ADR's entire point is that the existing
  export already carries what the heatmap needs.

## Rejected alternative

**New theme-scoped dense similarity table** (acceptance criterion 2's option
b): rejected. `compute_similarity_topk` already computes the full O(n²)
pairwise matrix in memory before truncating to top-k, so a dense table
wouldn't need new *computation* — but it would need new *storage and
rendering* for ~236,000 same-theme pairs across just these four themes
(`C(574,2) + C(369,2) + C(81,2) + C(39,2)`), almost all of it below the
existing similarity floor and never going to be looked at, to solve a
rendering problem (theme size) that a dense table doesn't actually fix. The
Box-anchored shape above gets the same "is there a real per-theme heatmap"
outcome the spec asked for at a size that's actually renderable.
