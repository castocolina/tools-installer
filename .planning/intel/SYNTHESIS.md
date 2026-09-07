# Synthesis Summary

Mode: merge (ingest batch 4/4 — `agent-cli-ergonomics`, `background-maintenance-daemon`,
`live-package-management` — the final 3 of the 7-PRD 2026-09-04 planning batch)
Classifications consumed this run: 3 (from `.planning/intel/classifications/`)
Cumulative classifications synthesized so far: 7 (batches 1-3 archived to
`.planning/intel/classifications-archive/`; batch 4 this run — 3
classifications in one run). **All 7 PRDs from the 2026-09-04 planning batch
are now ingested.**

## Doc counts by type (this run)

- ADR: 0
- SPEC: 0
- PRD: 3 — `docs/prds/2026-09-04-agent-cli-ergonomics-v1.0-prd.md`,
  `docs/prds/2026-09-04-background-maintenance-daemon-v1.0-prd.md`, and
  `docs/prds/2026-09-04-live-package-management-v1.0-prd.md` (all confidence:
  high, manifest_override: true, locked: false)
- DOC: 0
- UNKNOWN: 0

## Decisions locked

- 0 this run (no ADRs in this batch). Cumulative: 0. See `decisions.md`.

## Requirements extracted (this run)

- 13, sourced from the three classified PRDs. See `requirements.md`.
  - From `agent-cli-ergonomics` (4):
    - REQ-codex-skip-tweak (status: codex's actual flag unverified — Open Question 2)
    - REQ-opencode-auto-tweak
    - REQ-cursor-agent-default-model-wrapper (status: exact model slug unverified — Open Question 1, narrowed)
    - REQ-agent-tweak-self-update-durability
  - From `background-maintenance-daemon` (3):
    - REQ-launchd-prune-policy
    - REQ-daemon-log-diagnostics
    - REQ-daemon-dependency-gating
  - From `live-package-management` (6):
    - REQ-version-aware-status-github (MVP piece #1)
    - REQ-cached-timestamped-version-state (MVP piece #2)
    - REQ-background-version-refresh-worker (MVP piece #3; Open Question 1 unresolved — on-load vs. explicit action)
    - REQ-manager-version-resolution (MVP piece #4)
    - REQ-update-action-manager-delegation (MVP piece #5 — unblocks batch 2's REQ-pnpm-global-reinstall-mitigation)
    - REQ-manager-drift-alerting (deferred, not MVP — depends on piece #4)

Cumulative requirements: 41 (7 from batch 1 + 9 from batch 2 + 12 from batch 3
+ 13 from batch 4). See `requirements.md`.

## Constraints

- 0 this run (no SPECs in this batch). Cumulative: 0. See `constraints.md`.

## Context topics

- 0 this run (no DOCs in this batch). Cumulative: 0. See `context.md`.

## Conflicts (this run)

- 0 blockers, 0 competing-variants, 2 new INFO entries:
  1. Batch 2's `REQ-pnpm-global-reinstall-mitigation` was blocked on
     `live-package-management`'s (not-yet-ingested) update mechanism — that
     PRD is ingested this run and defines exactly that mechanism
     (`REQ-update-action-manager-delegation`, MVP piece #5). The dependency is
     now unblocked/sequenceable; `requirements.md`'s status field for
     `REQ-pnpm-global-reinstall-mitigation` has been updated accordingly.
  2. All 7 PRDs from the 2026-09-04 planning batch are now ingested — no
     PRDs remain pending for this milestone.
- 1 WARNING carried forward unchanged from batches 1-3 (the `mmdc`→`pnpm`
  illustrative-example staleness risk) — none of this batch's three PRDs
  touch `mmdc`'s install-method decision directly, so it remains open pending
  `REQ-mmdc-install-decision`.
- No cycle found: all three of this run's classified docs' `cross_refs` name
  only source files (`installer/tweaks.py`, `scripts/prune-user-tmpdir.sh`,
  `installer/versions.py`/`catalog_tui.py`/`wizard_app.py`/`status.py`), never
  another doc node. No cross-doc references among this run's three PRDs.
- No PRD-vs-PRD competing acceptance variants found — this batch's three PRDs
  (agent CLI shell aliases, a scheduled cleanup daemon, and version-aware
  status/update) are cleanly non-overlapping in scope, and do not contradict
  any already-synthesized requirement from batches 1-3.
- Full detail: `.planning/INGEST-CONFLICTS.md`.

## Out-of-scope items noted in the source PRDs (not requirements, for roadmapper awareness)

- The third-party `mynameistito/opencode-dangerously-skip-permissions` patch —
  `agent-cli-ergonomics` explicitly flags this as a separate, distinct opt-in
  decision, not bundled into `REQ-opencode-auto-tweak`'s default scope.
- `cursor-agent` 1M-context, non-interactive use — confirmed unreachable
  (Max Mode is interactive-only via the in-app `/model` picker); the wrapper
  targets high-effort default model selection only, never context size.
- A Linux/`systemd --user` timer equivalent of the background maintenance
  daemon — explicitly scoped out of `background-maintenance-daemon` as
  macOS-only per the user, though the `Policy` abstraction should not
  preclude adding one later.
- A general "run arbitrary scripts on a schedule" framework —
  `background-maintenance-daemon` is scoped to this one script only, matching
  this repo's existing pattern of narrow, purpose-built policies.
- Version pinning or lockfile-style reproducibility, rewriting
  `installer/deps.py`'s resolver, and a general telemetry/analytics layer —
  all explicitly out of scope for `live-package-management`.
- Manager-drift **auto-remediation** (deferred item #7 in
  `live-package-management`: auto-updating the registry and filing a GitHub
  issue against this repo) — explicitly deferred by the source PRD as "a real
  new capability... worth a separate, explicit decision and likely its own
  PRD," requiring a GitHub API token/auth story this project does not
  currently have. Not captured as a requirement in `requirements.md` (only
  the alert-only half, `REQ-manager-drift-alerting`, is captured, itself
  deferred/not-MVP).
- Moving a tool from a suboptimal method (e.g. `pnpm`) to its preferred method
  as part of "updating" it — `live-package-management`'s Open Question 4
  leaves this an open policy question (always a separate, explicit registry
  change, or something update-time code could decide), not resolved by this
  PRD.

## Cross-cutting notes not captured as REQ entries

All three source PRDs' "Quality Standards" acceptance sections state
project-wide gates applying across this batch's requirements (not
requirement-specific, so not duplicated per-REQ) — identical in substance to
batches 1-3's cross-cutting note:
- New and changed behavior covered by failing tests before implementation.
- `make validate` passes.
- `make test` passes at the project's current coverage gate.
- No quality gate is bypassed or silenced.
- `background-maintenance-daemon` additionally requires plist
  generation/parsing be testable without an actual `launchd` install, via the
  same `Runner`-injection seam every other executor already uses.
- `live-package-management` additionally requires all live/network calls sit
  behind an injectable seam, mirroring `installer/versions.py`'s existing
  `Fetch` pattern.

## Entry points for downstream consumers

- `.planning/intel/decisions.md`
- `.planning/intel/requirements.md`
- `.planning/intel/constraints.md`
- `.planning/intel/context.md`
- `.planning/INGEST-CONFLICTS.md`
