# GenBrick

A personal, non-commercial project for cataloging an owned LEGO collection and
discovering what else could be built from it. Built as a hobby exploration of a
data/ML problem — not a product, and not a competitor to Rebrickable, BrickLink,
or LEGO's own tools.

This is a **fan project, not affiliated with or endorsed by the LEGO Group**.
LEGO® is a trademark of the LEGO Group.

## Credits

- **[Rebrickable](https://rebrickable.com/)** — source of the structured LEGO
  catalog (sets, parts, colors, themes, minifigs, inventories) this project is
  built from.
- **[LDraw.org](https://www.ldraw.org/)** and its parts-library contributors —
  source of the open 3D parts geometry, file format, and Official Model
  Repository used for rendering.
- **BrickGPT / LegoGPT** (Carnegie Mellon, ICCV 2025) and **BrickNet** (Kulits
  & Schmid et al., CVPR 2026) — the published research a future generative
  phase of this project is designed to build on or benchmark against.

See [`INITIAL_PROJECT_SPEC.md`](./INITIAL_PROJECT_SPEC.md) for the full design.

## Phase-2 export contract

Alongside the site's own SQLite DB, the weekly pipeline produces two
JSON files under [`exports/`](./exports/) — a versioned public data contract
for a future generative phase (Phase 2) to consume without any backend
changes. Both are regenerated in full on every pipeline run; there is no
incremental/append mode.

- **`available_parts.json`** — the Owned brick pool (see `CONTEXT.md`): one
  entry per unique `(part_num, color_id)` summed across every owned Box, with
  the opportunistic LDraw crosswalk ids alongside Rebrickable's own:

  ```json
  [{ "part_num": "3001", "color_id": 0, "quantity": 25, "ldraw_part_id": "3001", "ldraw_color_id": 0 }]
  ```

  `ldraw_part_id`/`ldraw_color_id` are `null` wherever the crosswalk has no
  entry for that part/color.

- **`owned_sets.json`** — a snapshot of `owned_boxes` joined to each Set's
  basic catalog metadata:

  ```json
  [{ "set_num": "10281-1", "name": "Bonsai Tree", "year": 2021, "theme_id": 158, "num_parts": 878, "date_acquired": "2022-06-01", "notes": "" }]
  ```

Both files list only owned Boxes/pool contents — Candidate sets (see
`CONTEXT.md`) never appear here, regardless of `universe_scope`.
