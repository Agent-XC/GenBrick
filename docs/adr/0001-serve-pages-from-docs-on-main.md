---
status: superseded by ADR-0002
---

# Serve GitHub Pages from /docs on main

GitHub Pages is static-only (§5), so the weekly refresh Action needs to publish generated data (SQLite/JSON, renders) somewhere Pages serves from. Considered `/docs` on `main` vs. a separate `gh-pages` branch. Chose `/docs` on `main`: it matches the suggested repo structure (§12) and lets the weekly Action commit straight to `main` with no extra publish step. Trade-off: `main`'s history absorbs the weekly bot commits of regenerated data files, rather than isolating deploy artifacts on a separate branch.

**Superseded by [ADR-0002](./0002-serve-pages-from-a-github-actions-artifact.md):** `docs/` turned out to be needed for this repo's engineering documentation (ADRs, agent-skills config) — see that ADR for the replacement.
