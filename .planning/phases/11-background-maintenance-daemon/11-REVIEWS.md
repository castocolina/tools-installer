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

### Revision Note (post cycle 1)

A full revision pass rewrote all four plan files (`11-01-PLAN.md` through `11-04-PLAN.md`) in
place to address every cycle 1 finding above, following the reviewer's own recommended
replanning order:

- **11-01** (core mechanism): the scheduled wrapper is now invoked through an apply-time-resolved,
  absolute `uv` executable via `uv run --no-project --script` (never a bare `python3` shebang,
  live-verified against `installer/tweaks.py:64`'s own invocation shape); a new
  `installer.daemon.ensure_log_path` creates the log directory/file at apply time, before
  `launchctl bootstrap`, not lazily inside the wrapper; the real `launchctl` round-trip test now
  requires an explicit `TOOLS_INSTALLER_RUN_LAUNCHCTL_TESTS=1` opt-in in addition to its existing
  `launchctl`-availability skip; log truncation decodes the whole file once and cuts only on `\n`
  line boundaries, never an arbitrary byte offset; and a new `DaemonScheduleError` (an `OSError`
  subclass mirroring `installer/omz.py::OmzPluginsError`) makes `render_plist`/`write_plist`
  reject an empty/invalid `TMPDIR`, `uv_path`, hour, minute, or `days` before any write.
- **11-02** (policy model + factory): the soft-dependency copy now branches on `hard_requires`
  ("recommended tool(s)... not required" for `hard_requires=False`, the unchanged hard-block
  copy otherwise); `daemon_policy`'s apply/remove/reschedule are now fully transactional,
  mirroring `installer/omz.py::write_plugins`'s reserve-and-rollback-on-failure pattern (a
  `bootstrap` failure rolls the plist back to its prior snapshot; a reschedule failure also makes
  a best-effort re-registration of the old, working schedule); `remove()`'s `bootout` now
  distinguishes the idempotent "already not loaded" outcome (live-verified: `launchctl bootout`
  against a nonexistent label exits `3`, decoded by `launchctl error 3` as `"3: No such
  process"`) from a real failure that must block removal; and a dedicated failure-injection test
  matrix covers every step of apply/remove/reschedule.
- **11-03** (detail panel + time picker): every time-slot `ListItem` id is now a valid Textual
  identifier (`"time-03-30"`, live-verified against a `BadIdentifier` crash on the raw `"03:30"`
  form), with the display value stored separately; `set_schedule` is now routed through
  `installer.ui_common.run_live`, this project's one apply-workflow seam, instead of being called
  directly from the modal's dismissal callback; a new `Policy.read_schedule` field (added in
  11-02) gives the detail panel a persistent value to render; the daemon's own detail-panel copy
  replaces the generic "shell config"/"reversible shell policy" fallback; and log reads for the
  `l` toggle are wrapped in `try/except (OSError, UnicodeDecodeError)`.
- **11-04** (composition + on-by-default): auto-apply now runs in a Textual worker (mirroring
  `DoctorScreen`'s existing subprocess-backed-audit pattern) and posts a message that explicitly
  refreshes `PoliciesScreen.active_state` via a new `refresh_daemon_state` method, so a
  successful auto-apply is never invisible to the UI; the auto-apply callback is never wired when
  `_build_app` is constructed for `initial_view="uninstall"`, while the `Policy` itself remains
  visible/toggleable there; both uninstall paths (CLI `run_uninstall`, TUI `perform_uninstall`)
  now tear down an active daemon policy through the existing `active_policies`/`sweep_policies`
  machinery, extended with a `daemon_policy` parameter (with `sweep_policies`'s own except clause
  widened to also catch `CommandError`, an own-finding gap this revision discovered while wiring
  the daemon into that sweep loop); and the real per-user `TMPDIR`/`uv` resolution is now named
  and commented at the composition-root call site itself, not only inside `installer/daemon.py`.

Every fix was verified live where it touched real system behavior before being written into the
plans — `uv run --no-project --script`'s argv-forwarding, `launchctl bootout`'s exit-code-3
"already absent" semantics, this project's installed Textual version's actual `BadIdentifier`
behavior, and this machine's real `TMPDIR` value — rather than trusting either the review's or
the original plans' claims blindly. Original findings above are left unmodified; this note is an
append, not a rewrite.

## Cycle 2 (codex-sol-high)

**Reviewer:** codex CLI, model `gpt-5.6-sol (reasoning=high)`
**Commit reviewed:** `42c4f49` (post cycle-1 revision, all 4 plan files)
**Risk assessment:** HIGH (all 4 plans)

### Overall Assessment

The cycle-1 revisions materially improve all four plans: absolute `uv` invocation, pre-bootstrap
log creation, opt-in launchd testing, soft-dependency wording, valid Textual IDs, `run_live`,
worker-based defaulting, and uninstall wiring are now explicitly planned and generally match
existing repository patterns. However, execution should remain blocked. Several cross-plan
defects remain, including a missing `HOME` environment variable, incomplete transactional
recovery, frozen daemon activity during live uninstall, auto-application from the read-only
Doctor flow, and races between the default worker and user actions. These can leave the daemon
unloaded while shown as active, running while absent from uninstall, or installed merely by
opening `make doctor`.

### Plan 11-01 — Core daemon mechanism (HIGH)

1. **HIGH — `HOME` is missing from the LaunchAgent environment.** The plan emits only `PATH` and
   `TMPDIR` in `EnvironmentVariables` (`11-01-PLAN.md:24`, `:277`). The script runs with `set -u`
   and expands `$HOME` in its safety guard (`scripts/prune-user-tmpdir.sh:20`, `:71`). launchd's
   default environment contains only its minimal `PATH` (`11-RESEARCH.md:374`) — a scheduled run
   can terminate on an unbound `HOME`.
2. **MEDIUM — the "decided" marker write does not use the atomic-write guarantee it claims to
   mirror.** `installer/omz.py::_atomic_write` (`installer/omz.py:284`) is the actual precedent; a
   partial write here could damage `~/.myshellrc`.
3. **MEDIUM — malformed plist/log files insufficiently handled.** `plistlib.InvalidFileException`
   is a `ValueError`, but `run_live` catches only `OSError`/`CommandError`
   (`installer/ui_common.py:41`); truncation assumes the whole log is valid UTF-8.
4. **LOW — marker parsing tests omit orphan and reversed markers** (cf.
   `installer/omz.py:239`'s own orphan-marker distinction).

**Risk:** HIGH — missing `HOME` can prevent every scheduled run from reaching the cleanup logic.

### Plan 11-02 — Policy model and daemon factory (HIGH)

1. **HIGH — failed reapply does not restore the previous live registration.** `.apply()` restores
   only prior plist bytes after `bootstrap` fails (`11-02-PLAN.md:419`), but `bootstrap` boots out
   the old service *first*. After a failed new bootstrap, the old service is gone; the restored
   plist then makes `active=plist_path.exists()` a false positive.
2. **HIGH — validation occurs after filesystem side effects.** The shared helper installs the
   wrapper and creates the log before calling `write_plist` validation (`11-02-PLAN.md:412`),
   contradicting the plan's own "zero filesystem side effects on invalid input" claim.
3. **HIGH — marker-write failure after successful bootstrap is treated as total apply failure.**
   The plan tests that `record_decided` may raise after a successful bootstrap while leaving the
   plist/registration in place (`11-02-PLAN.md:92`); `action_toggle_policy` only updates
   `active_state` when the closure returns a result (`installer/wizard_app.py:1038`) — the UI will
   show OFF and report failure while the daemon is actually ON. `PolicyResult.warning` already
   exists for exactly this (`installer/policy.py:73`).
4. **MEDIUM — remove is not transactional across plist deletion**: bootout happens before unlink
   (`11-02-PLAN.md:429`); a failed unlink leaves the service unloaded but the plist present.
5. **MEDIUM — `remove_wrapper` has no production caller** — daemon removal never calls it, unlike
   `tweak_policy.remove` (`installer/policy.py:224`); the architecture rejects orphan helpers
   (`.claude/architecture.md:23`).

**Risk:** HIGH — reapply and marker-failure paths can make UI, plist, and actual launchd
registration disagree.

### Plan 11-03 — Detail panel and time picker (MEDIUM)

1. **HIGH — the normal detail view still invokes unsafe file parsers.** `_policy_detail` calls
   `last_run_summary`/`read_schedule` directly (`11-03-PLAN.md:24`); the proposed exception guard
   covers only the `l` log-tail action, but normal detail rendering happens on mount and row
   highlight (`installer/wizard_app.py:908`, `:1021`) — a corrupt log or plist can crash the
   screen before `l` is ever pressed.
2. **MEDIUM — daemon schedule changes/toggles still run subprocesses synchronously on the event
   loop** — `run_live`'s closure runs inline (`installer/ui_common.py:47`) over `run_captured`'s
   still-timeout-free subprocess (`installer/run.py:36`); the same TUI-freeze risk Plan 11-04
   correctly worker-izes for auto-apply remains for user-triggered actions.
3. **LOW — `_log_view` initialization is implicit** rather than set explicitly in
   `PoliciesScreen.__init__`.

**Risk:** MEDIUM — happy path is coherent, but malformed managed files can crash ordinary
rendering.

### Plan 11-04 — Composition and on-by-default behavior (HIGH)

1. **HIGH — daemon activity remains a frozen snapshot, so live TUI uninstall can miss it.**
   `Policy` is a frozen dataclass with `active: bool` (`installer/policy.py:82`); the plan reuses
   one `Policy` instance everywhere (`11-04-PLAN.md:511`) and filters uninstall by
   `daemon_policy.active` (`:574`) — if constructed OFF and later enabled by the worker, `.active`
   never updates, so the Uninstall view silently omits a running daemon.
2. **HIGH — `make doctor` ceases to be read-only.** Auto-apply suppression only covers
   `initial_view == "uninstall"` (`11-04-PLAN.md:480`), but interactive Doctor builds the same app
   with `initial_view="doctor"` (`setup.py:317`) — the Makefile explicitly promises Doctor is
   read-only (`Makefile:19`); merely opening it would install a background deletion job.
3. **HIGH — the default worker can race manual toggle or uninstall navigation.** No shared
   lock/pending-state exists between the background apply and `action_toggle_policy`
   (`installer/wizard_app.py:1025`) — a user can disable or enter Uninstall mid-apply; the
   worker's later success message may overwrite newer UI state.
4. **HIGH — full uninstall does not remove every daemon artifact.** `daemon_policy.remove()` never
   calls Plan 11-01's `remove_wrapper`, unlike existing tweak removal (`installer/policy.py:224`).
5. **MEDIUM — full uninstall recreates/retains the "decided" marker.** CLI uninstall strips the
   managed block first (`installer/app.py:417`); daemon removal then calls `record_decided`,
   recreating `~/.myshellrc` with the permanent marker — a later reinstall won't be "fresh." The
   plan explicitly forbids `clear_decided` (`11-01-PLAN.md:195`).
6. **MEDIUM — `tests/test_uninstall_e2e.py` (lines 52, 109) needs updating** for the new
   `perform_uninstall(..., daemon_policy=...)` parameter but is absent from the plan's
   modified-file list.
7. **MEDIUM — uninstall copy remains inconsistent** — confirmation/success/CLI text still says
   "shell tweaks" (`installer/wizard_app.py:786`, `:841`; `installer/app.py:425`).
8. **MEDIUM — the uninstall-suppression test doesn't test setup wiring** — must assert against
   `_capture_app`'s captured `_build_app` kwargs (`tests/test_setup.py:93`), not just that `None`
   isn't called.

**Risk:** HIGH — frozen activity snapshot, Doctor mutation, and worker race directly undermine
the phase's on-by-default and safe-uninstall guarantees.

### Final recommendation (per reviewer)

1. Add `HOME` to the LaunchAgent environment.
2. Correct apply/remove transaction recovery and validate before creating artifacts.
3. Replace frozen daemon activity in uninstall with a live predicate.
4. Restrict auto-defaulting to the normal setup flow (new `apply_daemon_default` flag, not just
   an uninstall check).
5. Serialize the default worker with manual policy/uninstall actions.
6. Define complete uninstall semantics for wrapper, marker, and copy.
7. Make schedule/log reads total over malformed files, and defensively guard their calls in the
   normal detail-rendering path too.

### Disposition

9 HIGH + 6 MEDIUM + 2 LOW findings, all source-grounded with exact file:line citations. Cycle 1's
fixes were directionally correct (the reviewer explicitly credits them as "materially improving
all four plans") but incomplete in the failure-recovery, ordering, and cross-screen-consistency
details. This is cycle 2 of the 3-cycle cap (`.planning/ONESHOT-RULES.md` Rule 10) — a full
revision pass will address every finding above before a final cycle 3 review.
