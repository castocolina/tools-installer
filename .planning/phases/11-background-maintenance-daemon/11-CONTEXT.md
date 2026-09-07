# Phase 11: Background Maintenance Daemon - Context

**Gathered:** 2026-09-04
**Status:** Ready for planning

<domain>
## Phase Boundary

The existing, already-safe `scripts/prune-user-tmpdir.sh` becomes a
toggleable, macOS-only LaunchAgent-backed background policy via a new
`daemon_policy` factory (parallel to `ban_policy`/`tweak_policy`),
independent of Phases 1-10. Scheduled runs write to a single log file
with truncation, surfaced in the Policies detail panel. `fd`/`rg` are
soft (`requires`) dependencies — the daemon still works via the script's
own find/grep fallback without them.

</domain>

<decisions>
## Implementation Decisions

### Default state — on, not opt-in
- **D-01:** The policy is ON by default on a fresh macOS install (not opt-in) — the user explicitly chose this over the initially-recommended opt-in default. Amended into ROADMAP.md's Phase 11 success criteria (2026-09-04).

### Schedule configurability — time-of-day only, recurrence stays fixed
- **D-02:** The policy's detail panel gains a time-of-day picker controlling the LaunchAgent's `StartCalendarInterval` hour/minute. Recurrence itself (daily) is NOT made configurable this phase — no weekly/custom-interval selector. This is a deliberately scoped-down version of the user's initial ask (which mentioned both "offset and recurrency as options"); the user agreed to the narrower time-picker-only option when presented with the tradeoff. Amended into ROADMAP.md's Phase 11 success criteria (2026-09-04) as new SC#5.

### Log truncation limit
- **D-03:** No specific size/day limit requested — planner picks a reasonable default (e.g. a few hundred KB or last-N-runs / last-30-days), consistent with how this codebase handles other log-like files. Not a locked number, just "simple size/age truncation" per the existing requirement text.

### Claude's Discretion
- Exact log truncation threshold (D-03) — planner's call, no user-specified number.
- Exact UI control shape for the time-of-day picker (e.g. a text-entry `HH:MM` field vs. a spinner) — planner's call, consistent with existing Policies detail-panel input patterns.
- Whether the time-of-day setting is stored in the LaunchAgent plist itself (regenerated on change) or in this project's own managed-state config and pushed into the plist at apply time — implementation detail, planner's call.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements source
- `.planning/REQUIREMENTS.md` — REQ-launchd-prune-policy, REQ-daemon-log-diagnostics, REQ-daemon-dependency-gating full text
- `.planning/ROADMAP.md` Phase 11 section — goal, "Depends on: Nothing", 5 numbered success criteria (SC#1 and SC#5 amended 2026-09-04 per this discussion), "Scope note (expanded 2026-09-04 discuss-phase)"

### Existing pattern to mirror
- `installer/policy.py`'s existing `ban_policy`/`tweak_policy` factories — the direct template for the new `daemon_policy` factory
- The `docker` tweak's `watch` dependency / `missing_requires` "recommended but not required" UI — the template for REQ-daemon-dependency-gating's `fd`/`rg` soft-dependency handling
- `scripts/prune-user-tmpdir.sh` — the existing, already-safe script this phase wraps in a LaunchAgent; no changes to its own logic/safety checks (dry-run default, `lsof` open-file skip)

</canonical_refs>

<specifics>
## Specific Ideas

- User's exact initial ask (2026-09-04): "On by default, offset and recurrency as options" — narrowed, with the user's agreement, to on-by-default plus a time-of-day picker only (recurrence stays fixed at daily) after a scope tradeoff was presented.

</specifics>

<deferred>
## Deferred Ideas

- Full recurrence control (weekly/custom interval, not just daily) — deferred; the user picked the narrower time-of-day-only option for this phase. Could be revisited later if daily-only proves too rigid in practice.

</deferred>

---

*Phase: 11-background-maintenance-daemon*
*Context gathered: 2026-09-04*
