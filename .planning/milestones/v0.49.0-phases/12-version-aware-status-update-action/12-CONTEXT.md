# Phase 12: Version-Aware Status & Update Action - Context

**Gathered:** 2026-09-04
**Status:** Ready for planning

<domain>
## Phase Boundary

The catalog can answer "what's out of date" (current vs. latest, cached
with a `checked_at` timestamp, refreshed via a background Textual
`Worker`) and act on it through a manual "update" action that delegates
to the tool's actual owning manager (this installer's own path, brew,
pnpm, or uv tool) rather than assuming a single executor owns every tool.
Depends on nothing structurally — `REQ-pnpm-global-reinstall-mitigation`
no longer sequences after this phase (moved to Phase 4). Manager-drift
alerting (SC#5) is stretch/non-MVP.

</domain>

<decisions>
## Implementation Decisions

### Update action confirmation
- **D-01:** The "update" action runs immediately when triggered, with no extra confirmation prompt — same UX as install today. Consistent with this project's existing apply-workflow convention (one action, one keypress, live output); update is not treated as more dangerous than install even though it may invoke brew/pnpm/uv directly.

### Manager-drift alerting scope
- **D-02:** SC#5 (manager-drift alerting) stays deferred/stretch, but the user wants a minimal version attempted if scope allows within this phase — not guaranteed to ship, not blocking the other 4 MVP success criteria (SC#1-4). Planner should treat it as an optional/stretch task at the end of the plan, sequenced after REQ-manager-version-resolution (its own stated dependency) and only attempted if the MVP pieces land with room to spare. Amended into ROADMAP.md's Phase 12 SC#5 wording (2026-09-04).

### Claude's Discretion
- Exact per-manager version-check commands (`brew outdated`, `pnpm outdated -g`, `uv tool list --outdated` or equivalents) — REQ-manager-version-resolution explicitly says "verify exact commands, not assumed"; research question at planning/implementation time.
- Whether the stretch manager-drift alert (D-02) gets attempted at all within this phase's time/scope budget — planner's call, informed by how much room remains after the 4 MVP pieces.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements source
- `.planning/REQUIREMENTS.md` — REQ-version-aware-status-github, REQ-cached-timestamped-version-state, REQ-background-version-refresh-worker, REQ-manager-version-resolution, REQ-update-action-manager-delegation, REQ-manager-drift-alerting full text
- `.planning/ROADMAP.md` Phase 12 section — goal, "Depends on: Nothing structurally", 5 numbered success criteria (SC#5 wording amended 2026-09-04)

### Existing pattern to mirror
- The already-working `resolve_github_tag` resolver — reused as-is for `github_release`-kind tools' version resolution (SC#1)
- The existing `run_live` async pattern — the template for the new Textual `Worker`-based background version-refresh (REQ-background-version-refresh-worker)
- `UninstallState`'s existing "managed elsewhere" concept — reused, not reinvented, for REQ-update-action-manager-delegation's manager-ownership delegation
- This project's existing apply-workflow convention (no extra confirmation beyond the normal install flow) — the template for D-01's update-action UX

</canonical_refs>

<specifics>
## Specific Ideas

None beyond the two locked decisions above — this phase's gray areas were narrowly about update-action UX and stretch-goal scope, both resolved.

</specifics>

<deferred>
## Deferred Ideas

- Auto-remediation for manager drift (auto-updating the registry + filing a GitHub issue) — already explicitly out of scope per REQ-manager-drift-alerting's own text (needs a GitHub API/auth story this project doesn't have); not revisited in this discussion.

</deferred>

---

*Phase: 12-version-aware-status-update-action*
*Context gathered: 2026-09-04*
