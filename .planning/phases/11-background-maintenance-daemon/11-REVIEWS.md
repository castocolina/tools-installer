# Phase 11 Cross-AI Plan Reviews

## Cycle 1 (codex-sol-high)

**Reviewer:** codex CLI, model `gpt-5.6-sol (reasoning=high)`
**Commit reviewed:** `f9b11a8` (initial 4-plan, 4-wave phase plan)
**Risk assessment:** HIGH (all 4 plans)

### Overall Assessment

Revision required before execution. The four-wave dependency order is sound, the research is
unusually thorough, and the test seams fit the codebase. However, the plans contain several
release blockers: the scheduled wrapper bypasses uv-managed Python, soft dependencies retain
hard-dependency copy, the time picker uses invalid Textual widget IDs, auto-apply leaves the
Policies UI stale, and opening the interactive uninstall flow can install the daemon being
uninstalled.

### Plan 11-01 — Core daemon mechanism (HIGH)

1. **HIGH — wrapper may not start on a bare macOS machine.** Plan executes `#!/usr/bin/env
   python3` directly via `ProgramArguments`, but this project guarantees only `uv` (per
   `install.sh:47`); the existing Python helper pattern is invoked through `uv run --no-project
   --script` (`installer/tweaks.py:64`).
2. **HIGH — log directory created too late.** launchd must open `StandardOutPath`/
   `StandardErrorPath` before executing the wrapper; the plan creates `log_path.parent` inside
   the wrapper itself, after launchd has already needed it to exist.
3. **MEDIUM — the real `launchctl` round-trip test mutates the developer's GUI launchd domain**
   and isn't sandboxed for deterministic CI per this project's own testing conventions.
4. **MEDIUM — byte-window log truncation can produce invalid UTF-8** when no header exists in
   the retained window; later code uses `Path.read_text()` which can raise `UnicodeDecodeError`.
5. **MEDIUM — `TMPDIR=""` is written as a "valid" plist value** instead of being rejected before
   registration, causing a daily silent failure.

### Plan 11-02 — Policy model and daemon factory (HIGH)

1. **HIGH — soft-dependency copy still says the tool is required** ("Missing required tool(s)…
   Install … before enabling") even when `hard_requires=False` — this is literally false.
2. **HIGH — apply is non-transactional.** Writes plist, attempts bootstrap, then records the
   marker; a mid-sequence failure leaves artifacts while `active` can still report ON.
3. **HIGH — remove can report success while the daemon remains loaded.** `bootout`'s
   `CommandError` is swallowed unconditionally before the plist is deleted and "decided" is
   recorded, stranding an invisible running service on a real failure.
4. **HIGH — rescheduling has the same partial-failure problem** — old service booted out before
   new bootstrap; a failed new bootstrap leaves the plist with the new schedule but no running job.
5. **MEDIUM — tests cover only successful runner calls**, no bootstrap/marker/bootout failure or
   rollback paths.

### Plan 11-03 — Detail panel and time picker (HIGH)

1. **HIGH — every proposed time-slot widget ID is invalid.** `ListItem(..., id="00:00")` through
   `"23:30"` — Textual `BadIdentifier`: IDs may not begin with a number or contain `:`.
2. **HIGH — `set_schedule` must go through `run_live`**, not be called directly from the modal
   callback, per this project's own screen-triggered-live-mutation architecture rule.
3. **MEDIUM — no schedule getter/value on `Policy`** — the promised detail-panel schedule refresh
   has no data source to read from.
4. **MEDIUM — existing Policies copy misclassifies the daemon** as "shell config" / "reversible
   shell policy" (hardcoded generic copy, not daemon-aware).
5. **MEDIUM — raw log reads handle only file-absence**, not `OSError`/`UnicodeDecodeError` (the
   latter is the truncation scheme's own possible output per finding 11-01 #4).

### Plan 11-04 — Composition and on-by-default behavior (HIGH)

1. **HIGH — auto-apply leaves the Policies UI stale.** `PoliciesScreen` snapshots `policy.active`
   at construction, which happens before `on_mount`; the plan calls the default-apply callback
   after screen construction and ignores its boolean result — the UI can never reflect a
   successful auto-apply without an explicit state refresh.
2. **HIGH — running interactive uninstall can install the daemon.** The plan wires the
   default-apply callback into every macOS `_build_app`, including the real `UnifiedApp` built
   for `initial_view="uninstall"` — an undecided user launching uninstall triggers auto-apply
   before ever seeing the uninstall screen.
3. **HIGH — the synchronous on-mount subprocess can freeze the entire TUI.** `run_captured` has
   no timeout; the app already runs subprocess-backed audits in a worker for exactly this reason,
   but this plan's default-apply runs synchronously.
4. **HIGH — full uninstall deliberately leaves an unattended deletion daemon running.** Plan
   11-01 excludes the daemon from teardown; existing full-uninstall snapshots and removes every
   active policy — leaving this one running breaks that lifecycle invariant.
5. **HIGH — empty `TMPDIR` remains a real production path** — the plan passes
   `os.environ.get("TMPDIR", "")` even though the scheduled script itself rejects an empty value.
6. **MEDIUM — setup tests avoid the actual integration seam** — `_capture_app` never runs
   `on_mount`, so no test proves `_build_app` passed the right callback or suppressed it for
   uninstall/Linux.

### Recommended Replanning Order (per reviewer)

1. Fix the production runtime: uv invocation, safe TMPDIR resolution, pre-created log path.
2. Specify transactional apply/remove/reschedule semantics and failure tests.
3. Correct soft-dependency copy.
4. Repair the picker IDs and route schedule changes through `run_live`.
5. Redesign auto-apply around worker completion and explicit UI-state synchronization.
6. Add daemon teardown to both uninstall paths and prohibit auto-apply during uninstall.

### Disposition

12 HIGH + 7 MEDIUM findings, all source-grounded with exact file:line citations, spanning
correctness (Textual `BadIdentifier` crash, non-transactional state, TUI freeze), safety
(install-during-uninstall, orphaned daemon after full teardown), and copy accuracy. This is a
substantial, genuine defect set — not review noise. Proceeding to a full revision pass (not a
partial patch) addressing all 19 findings before cycle 2, following the reviewer's own
recommended replanning order.
