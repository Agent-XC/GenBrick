## Agent skills

### Issue tracker

Issues live in GitHub Issues (Agent-XC/GenBrick), via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five-role vocabulary (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`), unchanged. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

### Local site preview

To look at `site/` in a browser, run `.venv/bin/python scripts/preview_site.py` — don't re-derive the staging/serving steps by hand. See `docs/agents/local-preview.md`.
