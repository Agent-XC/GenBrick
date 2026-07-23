# LEGO Collection, Discovery & Generative Design — Project Spec

## 1. Purpose & phased roadmap

A personal project with two phases:

- **Phase 1 (build now)**: a static website (GitHub Pages) that catalogs a set of
  owned LEGO boxes, shows what's in them (parts, colors, minifigs), aggregates the
  owned collection into one "brick pool," and surfaces which *other* official LEGO
  sets could plausibly be built from that pool or are compositionally similar to
  what's owned.
- **Phase 2 (reference design only, not built now)**: a "prompt + available bricks
  → generated creation" feature. This section of the spec documents *how it would
  plug in* and what prior art it would build on, so Phase 1's data layer is designed
  compatibly — but no model training or live generation happens as part of this
  work. It's being developed independently later.

This is a **fan project, not affiliated with or endorsed by the LEGO Group**. That
disclaimer must appear on every page. LEGO® is a trademark of the LEGO Group.

## 2. README & attribution (write this early, before the pipeline)

Add a `README.md` at the repo root as one of the **first commits** — before the
data pipeline is built out, not as an afterthought once the site works. Its job
is to make a few things unambiguous from day one, stated plainly rather than
buried in a footer link:

- **This is a personal, non-commercial exploration project.** The goal is to
  dig into an interesting data/ML problem as a hobby, not to build a product,
  compete with Rebrickable/BrickLink/LEGO's own tools, or represent this as
  anything official.
- **Named credit for everyone this project stands on**, not just a passing
  link:
  - **Rebrickable** — source of the entire structured catalog (sets, parts,
    colors, themes, minifigs, inventories) that Phase 1 is built from.
  - **LDraw.org and its parts-library contributors** — source of the open 3D
    parts geometry, file format, and Official Model Repository used for
    rendering (§10) and as Phase 2's intended representation (§13).
  - **The authors of BrickGPT / LegoGPT** (Carnegie Mellon, ICCV 2025) **and
    BrickNet** (Kulits & Schmid et al., CVPR 2026) — credited by name as the
    published research Phase 2 is designed to build on or benchmark against,
    even though no Phase 2 code exists in this repo yet.
- **The LEGO Group trademark disclaimer** from §1 — repeated in the README
  itself, not only in page footers.

This is cheap to write and costs nothing to do first — it sets expectations
correctly for anyone who finds the repo mid-build, and it's easier to get right
before the project has momentum than to retrofit later.

---

# Phase 1 — Catalog & Discovery Site

## 3. Data engineering conventions (layered pipeline)

The pipeline follows the **layered data engineering convention** described by
Joel Schwarzmann for QuantumBlack's Kedro framework, itself built on Cookiecutter
Data Science's opinions.[^1] Adapted to this project's much smaller scope (no
trained models running in Phase 1), the core ideas are:

- **Raw data is immutable.** The Rebrickable dump, exactly as downloaded, is
  never edited or overwritten in place — only read from. Every derived table or
  file downstream is a regenerable transformation, not something hand-patched.
- **The pipeline is a one-directional DAG.** Each layer reads only from the
  layer(s) before it and writes only to the layer after. If a bug surfaces in a
  later stage, fix the transformation logic and regenerate downstream — don't
  reach back and patch an earlier layer's output by hand.
- **Source data model vs. domain data model.** Rebrickable's tables are shaped
  for its own purpose (a general parts catalog), not this project's specific
  questions (what's owned, what's buildable, what's similar). The pipeline's
  job is to progressively reshape "source-shaped" data into "domain-shaped"
  data — this is exactly what §9's schema (`owned_boxes`, `similarity_topk`,
  `buildability`, etc.) is for.
- **Notebooks/ad-hoc exploration stay exploration-only.** Anything that runs
  weekly in CI belongs in a proper script under `pipeline/`, not a notebook.
- **Secrets and config stay out of version control.** Any Rebrickable API token
  (see §13's open item) goes in GitHub Actions secrets, never committed.

**Layers, mapped onto this project** — adopting Kedro's numbered-folder
convention, but only populating the layers actually needed right now (see the
repo structure in §12 for exact paths):

| Layer | Kedro's term | What it holds here |
|---|---|---|
| `01_raw` | Raw | The Rebrickable CSV dump exactly as downloaded, timestamped, untouched. |
| `02_intermediate` | Intermediate | A typed, cleaned mirror of the raw dump — parsed types, dropped null columns, consistent naming — still shaped like Rebrickable's source tables, no project-specific logic yet. |
| `03_primary` | Primary | This project's own domain model: owned brick pool, candidate scoping, buildability and similarity computations (§9's schema) — where "Rebrickable's shape" becomes "this project's shape." |
| `08_reporting` | Reporting | The derived outputs actually served to the site — the exported SQLite/JSON, `set_renders`, and anything display-ready. |
| `04`–`07` (reserved, unused for now) | Feature / Model input / Models / Model output | Deliberately left unpopulated in Phase 1. This is where Phase 2's LDraw-part feature encodings, trained model artifacts, and generated designs would naturally land later, without inventing a new convention at that point. |

This gives the weekly pipeline (§7) a consistent, regenerable home for each
transformation step, and gives Phase 2 a pre-agreed place to slot into later
rather than a layering decision to make from scratch.

[^1]: Joel Schwarzmann, "The importance of layered thinking in data
engineering," *Towards Data Science*, 2021.

## 4. Data source

Do **not** scrape LEGO.com for catalog data. Use **Rebrickable's LEGO catalog
database downloads** (https://rebrickable.com/downloads/) as the primary source:

- Free CSV dumps, refreshed regularly, explicitly licensed for reuse for any purpose.
- Covers official LEGO sets/parts/colors/minifigs/themes/inventories only (no MOCs) —
  exactly the scope of this project.
- Files of interest: `sets.csv`, `themes.csv`, `colors.csv`, `parts.csv`,
  `minifigs.csv`, `inventories.csv`, `inventory_parts.csv`, `inventory_minifigs.csv`.

Credit Rebrickable as the data source in the site footer, in addition to the LEGO
trademark disclaimer.

**Official LEGO.com links:** for each set, attempt to link to its official LEGO.com
product page.
- For currently retail-available sets this should generally resolve.
- Retired/discontinued sets frequently have **no live official page**. Do not assume
  one exists — check at build time, and if none resolves, show "Retired — no current
  official LEGO.com page" instead of a broken or guessed link. Do not silently fall
  back to a fan-site link and label it as "official."

## 5. Hosting & architecture constraint

GitHub Pages serves static files only — there is no live backend to query a database
at request time. Architecture:

- Ship the compiled catalog as a **SQLite file queried client-side via `sql.js`**
  (SQLite compiled to WASM), so the "small SQLite database" requirement is satisfied
  while staying fully static. (Alternative if this proves awkward: precompute to
  static JSON files instead — acceptable fallback, note the tradeoff in the repo
  README if taken.)
- All "freshness" (weekly refresh) happens **at build time**, via a scheduled
  **GitHub Actions workflow**, not at request time:
  1. Pull latest Rebrickable CSV dump.
  2. Rebuild the derived SQLite DB / JSON exports per the pipeline in §7.
  3. Re-check official LEGO.com links for owned + candidate sets (§4).
  4. Commit the updated data files and let GitHub Pages redeploy.
  - Trigger: weekly cron + manual `workflow_dispatch`.

## 6. Universe scope (modular, expand later without redesign)

The comparison universe for "what else could I build / what's similar" starts
narrow and must be trivially expandable later. Implement as a single config value,
e.g. `config/scope.json`:

```json
{ "universe_scope": "owned_themes" }
```

Allowed values, in expansion order:
1. `owned_themes` **(start here)** — candidate sets limited to themes the owner
   already has at least one set in.
2. `retail` — candidate sets limited to currently buyable sets.
3. `all` — every set in the Rebrickable catalog.

Implementation requirement: metadata tables (`sets`, `themes`, `colors`, `parts`,
`minifigs`) are loaded in full regardless of scope — they're small. Only the
expensive per-set inventory data (`inventory_parts`, `inventory_minifigs`) is
materialized for **owned sets ∪ candidate sets under current scope**. Changing
`universe_scope` and re-running the pipeline should be sufficient to widen the
comparison set — no schema change should be required. Flag file-size limits
(GitHub's soft ~50MB / hard 100MB per-file limits) as a re-check item when moving
to `all`, since full inventories at catalog scale are much larger.

## 7. Data pipeline (weekly GitHub Action)

1. Read the owned-sets list from `data/owned_sets.txt` (one LEGO set number per
   line — this is the original seed input, e.g. `72831`, `71826`, ...).
2. Download latest Rebrickable CSV dump.
3. Load full `sets`, `themes`, `colors`, `parts`, `minifigs` into the working DB.
4. Determine candidate set list per `config/scope.json`.
5. Load `inventory_parts` / `inventory_minifigs` only for owned ∪ candidate sets.
6. Compute the **owned brick pool**: sum of `inventory_parts` across all owned
   boxes, grouped by `(part_num, color_id)` — total quantity available. Assume all
   owned pieces are pooled/loose (not "currently built into another set") — see §8
   assumption note.
7. Compute a **buildability score** per candidate set = coverage of the candidate's
   required `(part_num, color_id, quantity)` by the owned pool (see §8).
8. Resolve each set's image per the priority order in §10 (user photo → LDraw OMR
   render → LDraw procedural render → none), respecting `render_candidates`.
   Skip re-rendering a set whose resolved part list hasn't changed since the last
   run (cache by content hash) — this is the only pipeline step with meaningful
   per-item wall-clock cost, so avoiding redundant renders matters.
9. Compute **box-to-box similarity** for pairs within owned ∪ candidate sets (see
   §8) — store only **top-N most-similar per set**, not a full dense matrix, to
   keep output size bounded as scope widens.
10. Check official LEGO.com link resolution for owned + candidate sets (§4).
11. Export: SQLite DB (or JSON) to the Pages-served directory, plus the Phase-2-
    facing exports in §15.
12. Commit and push.

## 8. Two distinct computations (don't conflate them)

- **Buildability / coverage** (owned pool → one candidate set): for each required
  `(part_num, color_id)` in the candidate, `min(owned_qty, required_qty)`, summed
  and divided by total required quantity → a 0–100% "how much of this could you
  build" score. This answers the "not yet bought, most buildable" feature.
- **Box-to-box similarity** (set → set, independent of ownership): a similarity
  metric (e.g. weighted Jaccard/cosine over `(part_num, color_id)` multisets)
  between any two sets in the current universe scope. This answers the
  "similarity matrix" feature and is a different question from buildability —
  two sets can be very similar in composition without either being "buildable"
  from the other.
- **Assumption to document in the repo**: owned pieces are treated as one pooled,
  disassembled collection for buildability purposes (not accounting for pieces
  currently assembled into another owned set). State this on the relevant page
  so it's not misread as "you can build these simultaneously without taking
  anything apart."

## 9. Database schema

```
themes(id, name, parent_id)                      -- "universe" (Star Wars, City, ...)
sets(set_num, name, year, theme_id, num_parts,
     official_url, official_url_status)          -- status: ok | retired | unchecked
parts(part_num, name, category_id, ldraw_part_id) -- ldraw_part_id: see §13
colors(id, name, rgb, is_trans, ldraw_color_id)   -- ldraw_color_id: see §13
inventories(id, set_num, version)
inventory_parts(inventory_id, part_num, color_id, quantity, is_spare)
minifigs(fig_num, name, num_parts)
inventory_minifigs(inventory_id, fig_num, quantity)

owned_boxes(set_num, date_acquired, notes)        -- assume complete-as-sold contents
owned_box_photos(set_num, filename, caption,
                  uploaded_at)                     -- user's own photos only

set_renders(set_num, image_source, image_path,
            coverage_pct, rendered_at)
  -- image_source: 'user_photo' | 'ldraw_omr' | 'ldraw_procedural' | 'none'
  -- coverage_pct: % of the set's parts resolved to LDraw geometry
  --               (100 for user_photo / ldraw_omr); see §10
  -- the resolved, "what to actually display" row per set — see §10's priority order

similarity_topk(set_num_a, set_num_b, score,
                computed_at)                       -- sparse, precomputed
buildability(set_num, coverage_pct, computed_at)   -- candidate sets only
```

`ldraw_part_id` / `ldraw_color_id` are cheap additions now (see §13 for why) —
populate opportunistically wherever the crosswalk is available; leave `NULL`
where it isn't. Nothing in Phase 1 reads these columns.

## 10. Images policy

Default image for any set (owned, and candidate if enabled — see the scope
toggle below) is resolved in this priority order, computed during the weekly
pipeline and stored in `set_renders`:

1. **User's own photo** (owned sets only) — if one has been uploaded to
   `owned_box_photos`, it always wins. This stays the way to show your actual,
   physical copy (wear, an alternate color run, etc.) — it's an optional
   override, not a requirement.
2. **LDraw OMR render** — if the LDraw Official Model Repository (§13) has a
   community-submitted full 3D model for that exact set, render it. This is a
   real assembled-model image, not a pile of parts, and is the best
   auto-generated option when it exists — but coverage across the catalog is
   whatever the OMR community has submitted, not universal.
3. **LDraw procedural partial render (the new default)** — for anything without
   (1) or (2). Build a synthetic `.ldr` file that lays out every part in the set
   with a resolved `ldraw_part_id`/`ldraw_color_id` (§13) — not assembled, just a
   flat, spaced-out layout of the set's actual pieces in their actual colors —
   and render it with a headless CLI LDraw renderer. Store what fraction of the
   set's parts actually resolved as `coverage_pct`; this is why it's *partial* —
   parts without a crosswalk hit are simply omitted, not guessed at.
4. **None** — only for candidate sets while rendering is disabled for them (see
   below), or the rare set with zero resolved parts.

**Renderer choice**: **LDView** is the natural first choice — it's native to
Linux, scriptable from the command line, and exports PNG snapshots directly, so
it drops cleanly into a GitHub Actions `ubuntu-latest` job. Caveat: LDView wants
an OpenGL context; on a headless runner that means running it under Xvfb with
Mesa software rendering (`llvmpipe`) rather than hardware acceleration — this
works (LDView explicitly supports software OpenGL, just slower) but is worth
confirming early. If OpenGL-in-CI proves troublesome, the fallback is **L3P
(LDraw→POV-Ray conversion) + POV-Ray**, which is pure CPU raytracing with no
GPU/OpenGL dependency at all, at the cost of chaining two tools and slower
per-image render times.

**Legal basis**: per LDraw's own stated policy, rendered images generated from
the LDraw parts library are not treated as a derivative work requiring separate
permission from the library's copyright holders — this is why the render option
is available at all without reopening the LEGO product-photo concerns raised
earlier in this doc. (Crediting LDraw in the footer, alongside Rebrickable, is
still good practice.)

**Scope toggle** (mirrors §6's modular pattern): a config flag,
`config/scope.json: { "render_candidates": false }`, controls whether steps 2–3
also run for candidate (non-owned) sets.
- `false` **(start here)** — owned sets get a real photo or an auto-render;
  candidate sets keep the original link-out-only treatment (no hosted image,
  just a link to the official/source page), since rendering the full candidate
  universe adds real per-item CI time as `universe_scope` (§6) widens.
- `true` — extends the same rendering pipeline to candidates too, so every set
  gets a visual instead of a bare link. Flip this once owned-set rendering is
  verified and the CI time cost at the current `universe_scope` has been
  measured (see §17).

**Caching**: render once per set and cache by a hash of its resolved part list;
only re-render when that list changes (new set, or an upstream data
correction), not on every weekly run.

## 11. Website — pages/features

- **Home**: owned boxes, with photo if available, basic info, link to official page.
- **Box detail**: full contents (parts w/ color + qty, minifigs), source/official
  link, retired status if applicable.
- **Collection / brick pool**: aggregated unique parts+colors across the whole
  owned collection, with total quantities.
- **Figurines**: all minifigs across owned boxes.
- **Discover** (not-yet-bought): candidate sets ranked by buildability score,
  scoped per §6, each linking to its detail/official page.
- **Similarity**: pairwise similarity view/matrix across owned (+ candidate) sets.
- **Themes / universe** browse view.
- Footer on every page: fan-project disclaimer + Rebrickable data credit.

Front end: plain static HTML/CSS/JS + `sql.js` is sufficient given the project's
size; a lightweight static-site generator is fine too if it simplifies templating
across set/box detail pages. Leave exact framework choice to implementation.

## 12. Suggested repo structure

```
/
├── .github/workflows/update-data.yml   -- weekly + manual trigger
├── config/scope.json                   -- universe_scope, render_candidates
├── data/
│   ├── owned_sets.txt                   -- seed input (manually maintained,
│   │                                       not part of the layered pipeline)
│   ├── 01_raw/                          -- Rebrickable dump, exactly as
│   │                                       downloaded, immutable (§3)
│   ├── 02_intermediate/                 -- typed/cleaned mirror, still
│   │                                       source-shaped (§3)
│   ├── 03_primary/                      -- this project's domain model:
│   │                                       owned pool, buildability,
│   │                                       similarity (§3, §9)
│   └── 08_reporting/                    -- derived, display-ready outputs
│                                            (sqlite/json, set_renders) (§3)
├── pipeline/
│   ├── fetch_rebrickable.py             -- writes 01_raw
│   ├── build_db.py                      -- 01_raw → 02_intermediate → 03_primary
│   ├── compute_similarity.py            -- 03_primary → 08_reporting
│   ├── check_official_links.py          -- 03_primary → 08_reporting
│   └── export_json.py                   -- 08_reporting → docs/
├── docs/                                -- GitHub Pages root, serves
│   │                                       data/08_reporting's output
│   ├── index.html
│   ├── assets/owned-photos/{set_num}/...
│   └── data/lego.sqlite (+ generated JSON)
├── exports/                             -- Phase-2-facing data contract (§15);
│                                            conceptually sits alongside the
│                                            reserved 04-07 layers from §3
└── README.md                           -- attribution, disclaimer, schema docs
                                          -- (write early — see §2)
```

---

# Phase 2 — Generative Component (reference design, not built now)

This phase is **out of scope for implementation** in this repo. It's documented
here so Phase 1's data model doesn't have to be reworked when Phase 2 starts.

## 13. Representation: LDraw

**LDraw** (https://www.ldraw.org/) is an open, community-run standard for LEGO CAD
— a plain-text file format (`.ldr`/`.mpd`) that describes exact 3D placement
(part, color, position, rotation) of every piece in a model, plus an openly
licensed 3D parts library (CCAL 2.0 — free to use, redistribute, and modify
commercially, with attribution). It is unaffiliated with LEGO; its own trademark
is held separately by its creator's estate.

Two things make it the natural choice for Phase 2's output representation:

1. **It's already the standard output format in the relevant published research**
   (§14) — using it isn't a novel integration, it's following existing practice.
2. **The LEGO-part ↔ LDraw-part crosswalk already exists.** Rebrickable maintains
   a mapping between official LEGO part/color numbers and LDraw part IDs (this is
   what powers LDraw.org's own "Set → LDraw" generator tool, which converts any
   official set number into LDraw format by pulling Rebrickable's inventory data).
   **Open item:** confirm whether this mapping ships in Rebrickable's bulk CSV
   downloads or requires the rate-limited API (1 request/sec) per part. If it's
   API-only, fetch it once and cache it, updating only for newly-added parts —
   don't re-fetch the whole crosswalk on every weekly Phase 1 rebuild.

## 14. Candidate reference implementations

Both projects generate LEGO/brick structures from a text prompt and both use
LDraw as (at least one) output serialization. Treat them as reference
implementations / fine-tuning starting points for the eventual Phase 2 work,
not as something to integrate today.

| | **BrickGPT** (a.k.a. LegoGPT) | **BrickNet** |
|---|---|---|
| Authors / venue | Carnegie Mellon University — **ICCV 2025 Best Paper (Marr Prize)** | Peter Kulits & Cordelia Schmid (Inria/ENS/CNRS, MPI) — **CVPR 2026** |
| Base model | Fine-tuned Llama-3.2-1B-Instruct (gated on Hugging Face — requires access request) | Qwen3-0.6B + LoRA adapters (pretrain + caption-conditioned SFT) — lighter footprint |
| Part vocabulary | Small set of generic axis-aligned brick/plate shapes on a discrete grid — **not** full real-world part diversity | Thousands of distinct real-world LDraw part types with typed connectors — much closer to an actual owned collection |
| Structure representation | Raw brick poses (`hxw (x,y,z)`) | Graph of typed connectors + a quantized spanning-tree "build order" serialization |
| Physical validity check | Physics-aware rollback using Gurobi for stability analysis (optional; simpler connectivity-based fallback without Gurobi) | Collision checking via per-part collision meshes (~1.6GB download) |
| Training data | ~47,000 physically-stable structures with captions (StableText2Brick, MIT-licensed) | 100,000+ human-designed LDraw objects/scenes |
| Outputs | Rendered PNG, brick-by-brick text, native `.ldr` file; also supports texturing/coloring and mesh-to-brick conversion | LDR, Graph (`.npz`), and Tree (path text) representations, interconvertible |
| License | MIT (code, weights, dataset) | Not confirmed — check at implementation time |
| Maturity | Public, stable release; ~1.7k GitHub stars; documented install/fine-tune/inference (incl. a Gradio demo) | Very new (weeks old at time of writing); sources disagree on release state — GitHub showed a "code/models releasing end of May" placeholder in one fetch, while other indexed results show a working `pip install bricknet` package with published LoRA adapters. **Re-verify current state before relying on it.** |

**Read on this:** BrickNet is the closer architectural fit for "generate something
buildable from *my actual, heterogeneous* collection of specific parts," since it
natively handles real-world part diversity instead of a small generic vocabulary.
BrickGPT/LegoGPT is the more mature, better-documented starting point if a working
baseline sooner is preferred. Either is a more realistic starting point than
training from scratch.

One incidental data point worth noting: the paper's own dataset/repo naming
moved from "LegoGPT"/"StableText2Lego" to "BrickGPT"/"StableText2Brick" between
early and official releases — consistent with the same trademark-carefulness this
project already applies to its own naming and disclaimers.

## 15. Integration point with Phase 1

When Phase 2 is actually built, it consumes a stable, versioned export produced
by the *same* weekly Phase 1 pipeline — no backend changes needed later:

```
exports/available_parts.json   -- [{part_num, color_id, quantity, ldraw_part_id, ldraw_color_id}, ...]
exports/owned_sets.json        -- snapshot of owned_boxes + basic set metadata
```

The intended (future) usage: mask/filter candidate LDraw parts+colors during
generation to only those present in `available_parts.json`'s owned pool, then
validate the finished design's part+color usage against the pool before calling
a result "buildable from what you own." This masking/validation logic is a
Phase 2 implementation detail — not built now.

Treat the export schema as a public data contract — document it in the repo
README and version it if it changes.

## 16. Explicit non-goals for this phase

- No model training, fine-tuning, or inference runs as part of this repo's work.
- No live "prompt → creation" feature on the website.
- No commitment yet to BrickGPT vs. BrickNet vs. something else — §14 is a
  starting point for research, not a final decision.

---

## 17. Open items to confirm during implementation

- Exact mechanism for sourcing/verifying `official_url` per set (Rebrickable dump
  may not include a ready-made LEGO.com URL — may need a small supplemental
  lookup/construction step, with the retired-set fallback from §4).
- Re-verify file-size limits when `universe_scope` moves beyond `owned_themes`.
- Whether to serve Pages from `/docs` on `main` (simplest) vs. a `gh-pages` branch.
- Whether the LEGO↔LDraw crosswalk (§13) is bulk-downloadable or API-only.
- BrickNet's actual current release/license state (§14) — treat the comparison
  table as directional, not final, given how new and fast-moving it is.
