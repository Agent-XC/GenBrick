# Add Playwright frontend integration tests

Issue #1's spec scoped "Automated frontend testing" out in favor of manual verification against a fixture-built SQLite DB, which in practice meant re-deriving the same ad hoc steps from scratch each time a page changed, with no repeatable pass/fail signal.

Reversed that decision: added `tests/test_site.py` (Python Playwright, via `pytest-playwright`) plus a `site_url` fixture in `tests/conftest.py` that serves a staged copy of `site/` with a fixture-built `data/lego.sqlite` over real local HTTP. Chose Python Playwright over `@playwright/test`/Node so it slots into the existing `.venv`/`pytest` setup rather than introducing a second package manager to a repo with no `package.json`. See `docs/agents/frontend-testing.md` for how to run/extend these tests and their limitations.
