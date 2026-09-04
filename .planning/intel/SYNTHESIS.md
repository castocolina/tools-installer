# Synthesis Summary

Mode: merge (ingest batch 3/7 — `catalog-expansion`, `postinstall-hooks`)
Classifications consumed this run: 2 (from `.planning/intel/classifications/`)
Cumulative classifications synthesized so far: 4 (batches 1-2 archived to
`.planning/intel/classifications-archive/`, batch 3 this run — 2 classifications
in one run).

## Doc counts by type (this run)

- ADR: 0
- SPEC: 0
- PRD: 2 — `docs/prds/2026-09-04-catalog-expansion-v1.0-prd.md` and
  `docs/prds/2026-09-04-postinstall-hooks-v1.0-prd.md` (both confidence: high,
  manifest_override: true, locked: false)
- DOC: 0
- UNKNOWN: 0

## Decisions locked

- 0 this run (no ADRs in this batch). Cumulative: 0. See `decisions.md`.

## Requirements extracted (this run)

- 12, sourced from the two classified PRDs. See `requirements.md`.
  - From `catalog-expansion` (7):
    - REQ-uv-tool-executor
    - REQ-system-tier-shell-container-entries (status: Apple Containers install-vs-nothing unresolved — Open Question 4)
    - REQ-terminal-emulator-entries
    - REQ-agent-host-entries (status: antigravity/cursor-agent install methods unverified — Open Question 2)
    - REQ-rtk-github-release
    - REQ-recommends-wiring-agent-hosts (instantiates batch 1's REQ-recommends-soft-dependency with concrete data)
    - REQ-linux-bazzite-shell-parity
  - From `postinstall-hooks` (5):
    - REQ-postinstall-field
    - REQ-postinstall-execution-timing
    - REQ-postinstall-idempotency-live-check
    - REQ-postinstall-noninteractive-only
    - REQ-codegraph-mcp-postinstall (status: per-tool non-interactive invocation research deferred to implementation — Open Question 3)

Cumulative requirements: 28 (7 from batch 1 + 9 from batch 2 + 12 from batch 3).
See `requirements.md`.

## Constraints

- 0 this run (no SPECs in this batch). Cumulative: 0. See `constraints.md`.

## Context topics

- 0 this run (no DOCs in this batch). Cumulative: 0. See `context.md`.

## Conflicts (this run)

- 0 blockers, 0 competing-variants, 1 new INFO (auto-resolved staleness in
  catalog-expansion's own Open Question 3 vs. its own Risks section and batch
  1's already-synthesized `REQ-oh-my-zsh-plugin-config`).
- 1 WARNING carried forward unchanged from batches 1-2 (the `mmdc`→`pnpm`
  illustrative-example staleness risk) — neither of this batch's two PRDs
  touches `mmdc`, so it remains open pending `REQ-mmdc-install-decision`.
- No cycle found: `catalog-expansion`'s `cross_refs` to the already-ingested
  `catalog-tiers`/`package-manager-policy` PRDs are prose references to
  archived (already-synthesized) docs, not nodes within this run's classified
  set; `postinstall-hooks`'s `cross_refs` is empty.
- No PRD-vs-PRD competing acceptance variants found — `catalog-expansion` and
  `postinstall-hooks` are cleanly complementary (the former explicitly scopes
  codegraph's MCP postinstall registration as out-of-scope, ceded to the
  latter).
- Full detail: `.planning/INGEST-CONFLICTS.md`.

## Three PRDs of the 2026-09-04 batch not yet ingested

`live-package-management`, `background-maintenance-daemon`,
`agent-cli-ergonomics` remain (batches 4-7... noting the original 7-PRD count
compressed to fewer remaining passes since this run ingested 2 PRDs together).
`REQ-pnpm-global-reinstall-mitigation` (batch 2) still explicitly depends on
`live-package-management`'s update mechanism (not yet ingested) — flag for the
roadmapper when sequencing.

## Out-of-scope items noted in the source PRDs (not requirements, for roadmapper awareness)

- A general audit of every existing catalog tool's Linux/Bazzite install path
  — `catalog-expansion` scopes Linux/Bazzite parity only to the tools it adds.
- A general plugin/scripting system for arbitrary user-authored postinstall
  hooks — `postinstall-hooks` is a registry-declared, single-command action
  per tool, same trust model as the rest of `registry.toml` (author-only).
- Postinstall actions that themselves install new tools — that remains
  `Tool.requires`' + the existing resolver's job.
- Uninstall-time symmetric cleanup of postinstall effects (e.g. de-registering
  the MCP server) — explicitly flagged as a follow-up, not blocking this PRD.
- Re-doing per-tool internal-dependency verification for `codegraph`/`graphify`
  already verified in the package-manager-policy PRD — `catalog-expansion`
  inherits those findings; every *other* tool it adds still needs its own
  verification pass.

## Cross-cutting notes not captured as REQ entries

Both source PRDs' "Quality Standards" acceptance sections state project-wide
gates applying across this batch's requirements (not requirement-specific, so
not duplicated per-REQ) — identical in substance to batches 1-2's cross-cutting
note:
- New and changed behavior covered by failing tests before implementation.
- `make validate` passes.
- `make test` passes at the project's current coverage gate.
- No quality gate is bypassed or silenced.
- `postinstall-hooks` additionally requires the postinstall command execution
  path be bandit-reviewed the same way every other subprocess-invoking path in
  `installer/` already is.

## Entry points for downstream consumers

- `.planning/intel/decisions.md`
- `.planning/intel/requirements.md`
- `.planning/intel/constraints.md`
- `.planning/intel/context.md`
- `.planning/INGEST-CONFLICTS.md`
