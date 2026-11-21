# Phase 32 Review Disposition

Orchestrator triage of the read-only gates of 2026-11-21 (internal deep reviewer `32-REVIEW.md`: 0 critical, 5 warnings, 6 info; security auditor `32-SECURITY.md`: SECURED, 32 of 32 threats closed, 4 accepted, 9 residual risks logged; external lane `opencode-referee-one`: 4 findings). The triage table with the decision per item is at the end of `32-REVIEW.md`; the fixes are in `32-REVIEW-FIX.md`.

## Fixed

WR-01 (process group on interruption), WR-02 and IN-06 (hand-edited ledger), WR-03 and lane 1 (Codex customized server kept whole), WR-04 (no silent re-add of a deleted server), WR-05 (0600 for created files), lane 2 (plugin env offer), IN-02 (parity test), IN-03 (Bruno guards assert the registry), IN-04 (stale text), IN-05 (single pin extraction).

## Rejected, accepted or deferred, with reason

| Source | Finding | Disposition |
| ------ | ------- | ----------- |
| Lane 4 | `gh extension` data under a relocated GitHub CLI data directory is not detected | Accepted limit: the registry comment states the default path; deferred to backlog 999.32 |
| IN-01 | The launcher check refuses `owner/time` style tokens by basename | Accepted: it fails closed and no shipped row is affected; backlog 999.32 |
| Security AR-32-01..09 | No installer-side digest for the AWS script and the `gh extension install` fetch, no integrity digest for `@playwright/mcp`, Claude's live config rewrite, `CLAUDE_CONFIG_DIR`, user-writable ledger limited to allow-listed key paths, the landing-image `rmi`, the Bruno box options | Accepted risks, logged in `32-SECURITY.md`; the digest and limit items are in backlog 999.32 |
| WR-01 side effect | A cask's internal `sudo` prompt cannot read a password on the console route (no controlling terminal) | Accepted, provisional: the TUI routes already behave this way and the project rule is zero sudo with a hand-off; backlog 999.32 |
| Plan review cycle 3 | The shared landing helper's image-tag race | Rejected as inherited since phase 24 (every landing target); backlog 999.32 |
