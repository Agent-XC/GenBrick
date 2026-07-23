# Local site preview

To actually look at `site/` in a browser (not just pass `pytest tests/test_site.py`), run:

```sh
.venv/bin/python scripts/preview_site.py
```

Then open `http://127.0.0.1:8743/index.html`. Stop it with Ctrl-C (foreground) or `pkill -f "scripts/preview_site.py"` (backgrounded).

This is the frozen, reproducible answer — prefer running it over re-deriving these steps by hand. It exists because a first attempt at this got there by trial and error (wrong server lifecycle, no valid image bytes, almost regenerating the real committed DB); the reasoning below is why it looks like this, in case it ever needs to change.

## Why not just open `site/index.html` or reuse `site/data/lego.sqlite`

- **Must be served over real HTTP, not `file://`.** Same reason as `tests/test_site.py` (see `docs/agents/frontend-testing.md`'s Limitations section) — `shared.js`'s `loadDatabase()` calls `fetch()` for `sql-wasm.wasm` and `data/lego.sqlite`, and browsers refuse `fetch()` under `file://`.
- **Never touch the real `site/data/lego.sqlite` or `site/assets/ldraw-renders/` for a one-off look.** Those are the actually-published, git-committed artifacts. `scripts/preview_site.py` stages a full copy of `site/` plus a freshly-built DB under `.preview/` (gitignored) and serves *that*, mirroring how `tests/conftest.py`'s `site_url` fixture stages a copy for Playwright rather than touching the real site data.
- **LDView isn't installed on this dev machine.** `pipeline.ldraw.render_with_ldview` (the real renderer — see issue #10) would shell out to a missing `ldview` binary, fail, and silently degrade every owned Set to `image_source='none'` (by design — see `pipeline/ldraw.py`'s `RenderError` handling, which never crashes the pipeline). That's technically correct but shows nothing interesting. `scripts/preview_site.py` defaults to a placeholder-PNG renderer instead (a minimal valid solid-color PNG built from pure stdlib `zlib`/`struct` — no Pillow dependency) so the box detail page has a real image to load. Pass `--real-renderer` to use the actual `render_with_ldview` if LDView is ever installed here.

## The background-process gotcha that caused the trial and error

Don't chain a long-running server with other commands in one `run_in_background` call, e.g.:

```sh
# Don't do this — the server dies once the wrapper command "completes":
cd site_preview && python3 -m http.server 8743 & sleep 1 && curl ...
```

The `&`-detached server is still a child of that one backgrounded shell invocation; once the shell finishes running the rest of the line (the `curl`), the whole invocation is reported "completed" and the detached server goes down with it.

Instead, launch the server as the **entire, sole command** of its own `run_in_background` call (this is exactly what `scripts/preview_site.py` does — `serve_forever()` blocks in the foreground of that one process), then verify it with a separate, ordinary (foreground) `curl` call once it's up.

## If `data/01_raw/` is missing

`data/01_raw/` isn't committed (see `.gitignore` and issue #14) — it's the
Rebrickable dump, refetched weekly by `.github/workflows/update-data.yml`. On
a fresh clone with no local `data/01_raw/`, run `pipeline/fetch_rebrickable.py`
once before `scripts/preview_site.py`:

```sh
.venv/bin/python -m pipeline.fetch_rebrickable
```

This pulls the real, full-size Rebrickable dump straight from
`cdn.rebrickable.com` (no API token needed for the public bulk downloads) —
expect it to take longer and produce far larger files than the tiny
walking-skeleton stubs earlier commits used to check in directly.

## If the preview looks stale

`scripts/preview_site.py` wipes and rebuilds `.preview/` on every run (`stage()` calls `shutil.rmtree` first), so re-running it after a `pipeline/` or `site/` change is enough — no manual cleanup needed. If a port is already in use from a previous session, `pkill -f "scripts/preview_site.py"` first, or pass a different `--port`.
