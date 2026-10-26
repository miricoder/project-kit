# Remediation log: Dumpit

## Iteration 1 — 2026-10-26

- **Check:** `pk qa` after `/design` wrote `docs/spec.md` and `docs/acceptance.feature`.
- **lint:** passed (0 problems): 9 spec sections, 22 failure modes each mapped to a scenario, 52 scenarios across 10 features, rollback covers code and data.
- **a11y:** passed (0 problems) on all five `ui/*.dc.html` artboards.
- **judge:** not run. `pk gate phase handover` refused: `judge panel: 0/3 seats configured: none. Fix: add a third family key to /root/.claude/project-kit/.env (chmod 600), or name a family you will paste by hand: PROJECT_KIT_PASTE_SEATS=google`.
- **Changed:** nothing; no lint or a11y failures to fix.
- **Stopped:** Step 5, "the panel cannot sit". Needs three non-Anthropic judge keys or paste seats.
