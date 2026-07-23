# Frontend testing: Playwright against a fixture-built site

The frontend (`site/`) is zero-build static HTML/JS that queries a SQLite DB client-side via sql.js — there's no server to unit-test. `tests/test_site.py` drives the real pages in a real headless Chromium browser instead, via [Playwright](https://playwright.dev/python/) (`pytest-playwright` plugin). See `docs/adr/0003-add-playwright-frontend-integration-tests.md` for why this exists — it reverses issue #1's original "frontend has no automated test seam" decision.

## Running them

```sh
.venv/bin/pip install -e ".[test]"   # pytest, playwright, pytest-playwright
.venv/bin/playwright install chromium   # once per machine — browser binaries aren't in the repo
.venv/bin/pytest tests/test_site.py -v
```

They run inside the same `pytest tests/` invocation as the pipeline tests (`tests/test_pipeline.py`, `tests/test_links.py`) — no separate command needed day to day.

## How the harness works

`tests/conftest.py`'s session-scoped `site_url` fixture:

1. Copies `site/`'s static files (`*.html`, `assets/`, `vendor/`) into a temp directory.
2. Runs the real pipeline (`pipeline.run.run_pipeline`) against `tests/fixtures/raw/` + `tests/fixtures/owned_sets.csv` — **the same fixture catalog `test_pipeline.py` uses** — to build a fixture `lego.sqlite`, and drops it into the staged `data/` directory in place of the real one.
3. Serves the staged directory over a real local HTTP server (stdlib `http.server`, random free port) for the whole test session, and tears it down at the end.

Tests then do `page.goto(f"{site_url}/box.html?set_num=75192-1")` and assert against the fixture's known values (same numbers as the pipeline tests — e.g. Han Solo owned across two Boxes sums to 2).

Because the fixture catalog is shared with `test_pipeline.py`, changing `tests/fixtures/raw/*.csv` or `tests/fixtures/owned_sets.csv` affects both suites — check both when editing fixtures.

## Limitations

- **Must be served over HTTP, not `file://`.** `shared.js`'s `loadDatabase()` calls `fetch()` for both `sql-wasm.wasm` and `data/lego.sqlite`; Chromium refuses `fetch()` under `file://` (no origin for CORS). This is why the fixture spins up a real server rather than just opening the HTML file.
- **`.wasm` MIME type matters, but not fatally.** `WebAssembly.instantiateStreaming` requires a `application/wasm` Content-Type; stdlib `http.server`'s MIME guessing is OS-dependent and isn't guaranteed to map `.wasm` correctly everywhere. The test server's handler pins it explicitly. If it were wrong, sql.js's vendored loader falls back to a slower ArrayBuffer-based instantiation and logs a console warning rather than failing outright — which would otherwise be a confusing false failure in a "no console errors" test.
- **DOM/text/attribute coverage only, no visual regressions.** Assertions check rendered text, element counts, and attributes (`page.locator(...)`, `expect(...).to_have_text(...)`) — not pixels, layout, or CSS. A change that renders correct data with broken styling won't be caught here.
- **One browser (Chromium), one viewport.** No cross-browser or responsive/mobile-viewport coverage is set up. Playwright supports both (`--browser firefox`, `page.set_viewport_size(...)`) if that's ever needed — not wired up yet because nothing has asked for it.
- **Browser binaries aren't vendored or auto-installed.** `playwright install chromium` must be run once per machine/CI runner before these tests can pass. There's no GitHub Actions workflow in this repo yet — when one is added, it needs a `playwright install --with-deps chromium` step (or equivalent) before `pytest`.
- **Fixture data only.** These tests never touch `site/data/lego.sqlite` (the real, Rebrickable-sourced published DB) — only the small hand-authored fixture catalog. They prove the pages render fixture data correctly, not that the real weekly-refreshed catalog renders without surprises (e.g. an unexpected null, an unusually large collection). That's still worth a spot-check against `site/data/lego.sqlite` after a pipeline change, the way `pipeline/publish.py`'s output was checked before this harness existed.

## Adding a test for a new page

1. Add the page's path to `test_page_loads_without_console_errors`'s `@pytest.mark.parametrize` list — a cheap smoke check that it loads, finishes rendering (no `.loading` placeholder left in the DOM), and throws no JS errors.
2. Add a dedicated test asserting on the page's actual content via `page.locator(...)` + `expect(...)`, using known values from `tests/fixtures/`. Prefer asserting on a specific cell/locator over `to_contain_text` on a whole row when the expected value could be a substring of something else already in that row (e.g. a quantity like `4` inside a part name like "Plate 2 x 4").
