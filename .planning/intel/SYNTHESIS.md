# Synthesis Summary

Mode: merge (ingest batch 2/7 — `package-manager-policy`)
Classifications consumed this run: 1 (from `.planning/intel/classifications/`)
Cumulative classifications synthesized so far: 2 (batch 1 archived to
`.planning/intel/classifications-archive/`, batch 2 this run)

## Doc counts by type (this run)

- ADR: 0
- SPEC: 0
- PRD: 1 — `docs/prds/2026-09-04-package-manager-policy-v1.0-prd.md` (confidence: high, manifest_override: true, locked: false)
- DOC: 0
- UNKNOWN: 0

## Decisions locked

- 0 this run (no ADRs in this batch). Cumulative: 0. See `decisions.md`.

## Requirements extracted (this run)

- 9, all sourced from the single classified PRD. See `requirements.md`.
  - REQ-npx-ban
  - REQ-npm-npx-redirect-policy (status: npx resolved, npm allowlist open — Open Question 2)
  - REQ-codegraph-github-release
  - REQ-mmdc-install-decision (status: unresolved — Open Question 3)
  - REQ-puppeteer-catalog-entries (status: chrome-headless-shell entry shape unresolved — Open Question 3a)
  - REQ-pnpm-global-reinstall-mitigation (status: depends on not-yet-ingested live-package-management PRD)
  - REQ-sdkman-exclusivity (status: already shipped in commit `0e05f50`, ahead of and outside GSD's flow — treat as prior art to verify/harden, not accept as-is; `java` version pin unresolved — Open Question 6a)
  - REQ-registry-authoring-verification-checklist (status: recording mechanism unresolved — Open Question 5)
  - REQ-brew-preference-guideline (status: enforcement mechanism unresolved — Open Question 4)

Cumulative requirements: 16 (7 from batch 1 + 9 from batch 2). See `requirements.md`.

## Constraints

- 0 this run (no SPECs in this batch). Cumulative: 0. See `constraints.md`.

## Context topics

- 0 this run (no DOCs in this batch). Cumulative: 0. See `context.md`.

## Conflicts (this run)

- 0 blockers, 0 competing-variants, 1 auto-resolved-adjacent WARNING.
- The one WARNING: batch 1's illustrative `mmdc`→`pnpm` cross-tier dependency
  example (ROADMAP.md Phase 1, REQ-dependency-chain-requires) may go stale if
  this batch's open `mmdc` install-method decision (REQ-mmdc-install-decision)
  resolves to brew instead of pnpm. Underlying requirement unaffected;
  `java`→`sdkman` remains a valid alternative proof case.
- Full detail: `.planning/INGEST-CONFLICTS.md`.
- A non-bucketed note documents that REQ-sdkman-exclusivity's implementation
  (commit `0e05f50`) shipped outside GSD's flow — surfaced for downstream
  visibility, not a cross-document conflict per the seven defined passes.

## Six PRDs of the 2026-09-04 batch not yet ingested

`postinstall-hooks`, `catalog-expansion`, `live-package-management`,
`background-maintenance-daemon`, `agent-cli-ergonomics` remain, plus this run
completes `package-manager-policy` (2/7). REQ-pnpm-global-reinstall-mitigation
in this run explicitly depends on `live-package-management`'s update
mechanism (not yet ingested) — flag for the roadmapper when sequencing.

## Out-of-scope items noted in the source PRD (not requirements, for roadmapper awareness)

- `installer/deps.py` / the dependency resolver: unchanged by this PRD.
- Auditing every other catalog tool for a "better" package manager — scoped
  to `codegraph` and `mmdc` only, plus the npm/npx ban itself.
- Fixing the upstream pnpm global-install bug (pnpm#11520, pnpm#11587) —
  explicitly not this project's to fix; only mitigations are in scope.

## Cross-cutting notes not captured as REQ entries

The source PRD's "Quality Standards" acceptance section states project-wide
gates applying across this batch's requirements (not requirement-specific, so
not duplicated per-REQ) — identical in substance to batch 1's cross-cutting
note:
- New and changed behavior covered by failing tests before implementation.
- `make validate` passes.
- `make test` passes at the project's current coverage gate.
- No quality gate is bypassed or silenced.

## Entry points for downstream consumers

- `.planning/intel/decisions.md`
- `.planning/intel/requirements.md`
- `.planning/intel/constraints.md`
- `.planning/intel/context.md`
- `.planning/INGEST-CONFLICTS.md`
