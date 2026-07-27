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
- **BrickGPT / LegoGPT** ([Pun et al., Carnegie Mellon — "Generating Physically
  Stable and Buildable Brick Structures from Text," ICCV
  2025](https://openaccess.thecvf.com/content/ICCV2025/papers/Pun_Generating_Physically_Stable_and_Buildable_Brick_Structures_from_Text_ICCV_2025_paper.pdf))
  and **BrickNet** ([Kulits & Schmid — "BrickNet: Graph-Backed Generative
  Brick Assembly," CVPR
  2026](https://openaccess.thecvf.com/content/CVPR2026/papers/Kulits_BrickNet_Graph-Backed_Generative_Brick_Assembly_CVPR_2026_paper.pdf))
  — the published research a future generative phase of this project is
  designed to build on or benchmark against.

See [`INITIAL_PROJECT_SPEC.md`](./INITIAL_PROJECT_SPEC.md) for the full design.

## Forking this for your own collection

This is built so anyone can fork it, point it at their own LEGO collection, and
get a working site with no code changes.

1. **Fork the repo** on GitHub, then clone your fork locally.

2. **Load your own Owned sets.** Edit [`data/owned_sets.txt`](./data/owned_sets.txt),
   a small CSV with one row per Box you own:

   ```csv
   set_num,date_acquired,notes
   10281-1,2022-06-01,
   71850-1,,
   ```

   `set_num` must match Rebrickable's format (the numeric id plus its `-N`
   version suffix, e.g. `10281-1`) — look it up on
   [Rebrickable](https://rebrickable.com/) if you're not sure. `date_acquired`
   and `notes` are optional. If you want to show your own photo instead of a
   generated render for a Box, add a row to
   [`data/owned_box_photos.csv`](./data/owned_box_photos.csv) and drop the
   image file under `data/`.

   Optionally, adjust [`config/scope.json`](./config/scope.json) —
   `universe_scope` controls which Sets outside your own collection are
   eligible as Candidates (`owned_themes` by default, widen to `retail` or
   `all` later), and the `min_*` fields tune the Buildability/Similarity
   floors.

3. **Set up the weekly update.** The refresh in
   [`.github/workflows/update-data.yml`](./.github/workflows/update-data.yml)
   runs automatically once GitHub Actions are enabled on your fork (GitHub
   disables Actions on forks by default — enable them under the **Actions**
   tab). It pulls the latest Rebrickable catalog dump, rebuilds the site's
   data from your `owned_sets.txt`, and deploys the result. No Rebrickable API
   token is required — the bulk CSV downloads it fetches are public — but if
   you ever add one, set it as a repo secret named `REBRICKABLE_API_TOKEN`
   (**Settings → Secrets and variables → Actions**), never committed to the
   repo.

   You also need to point GitHub Pages at the workflow's output once: go to
   **Settings → Pages → Build and deployment → Source**, and select
   **GitHub Actions** (not "Deploy from a branch").

4. **Create the website by manually launching the Action.** Rather than
   waiting for the Monday 06:00 UTC cron, trigger the first run yourself: go
   to the **Actions** tab, select **Weekly data refresh** in the left
   sidebar, click **Run workflow**, then **Run workflow** again to confirm.
   Once it finishes (the `deploy` job at the bottom of the run), your site is
   live at `https://<your-username>.github.io/<repo-name>/`.

   If you have the `gh` CLI installed and authenticated against your fork,
   [`scripts/trigger_data_refresh.py`](./scripts/trigger_data_refresh.py) does
   the same thing from the command line:

   ```sh
   .venv/bin/python scripts/trigger_data_refresh.py --watch
   ```

   See [`docs/agents/local-preview.md`](./docs/agents/local-preview.md) if you
   want to preview the site locally before pushing.

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
