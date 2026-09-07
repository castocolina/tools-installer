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

### Revision Note (post cycle 2)

A full revision pass rewrote all four plan files (`11-01-PLAN.md` through `11-04-PLAN.md`) in
place to address every cycle 2 finding above. The plans' own `<source_audit>`/`<design_decisions>`
sections cite a single global numbering for this pass — #1-#4 (11-01's own four findings), #5-#9
(11-02's first five), #10-#12 (11-03's three), and #13-#20 (11-04's eight, of which #13 is
resolved inside 11-02 since it names a new `Policy` field 11-04 only consumes):

- **11-01** (core mechanism): `render_plist`/`write_plist` now also resolve and validate a
  non-empty, absolute `home` value (mirroring `tmpdir`'s own treatment exactly) and emit it into
  the plist's `EnvironmentVariables` alongside `PATH`/`TMPDIR` (#1); `record_decided`'s marker
  write now commits through the SAME sibling-temp-file-plus-`os.replace` atomic shape `write_plist`
  already uses (a local re-implementation of the pattern, never a private cross-module import of
  `installer/omz.py::_atomic_write`), so a crash mid-write can never half-write the shared
  `~/.myshellrc` file (#2); `read_schedule` now catches `(KeyError, TypeError, ValueError)` around
  its own `plistlib.loads` call (`plistlib.InvalidFileException` is a `ValueError` subclass, not an
  `OSError` — re-verified live this session, see below) and returns `None` for a byte-corrupt plist
  exactly like the already-handled missing-key case; `last_run_summary` and the truncation routine
  now decode with `errors="replace"` instead of `Path.read_text()`'s strict decode (#3); and
  `decided`'s marker parser gains dedicated orphan-marker and reversed-marker test cases mirroring
  `installer/omz.py`'s own coverage for the same shape (#4). A new `clear_decided(state_path)`
  function (mirroring `installer/omz.py::_clear_owned`) is added but deliberately given zero
  callers in this plan — its one production caller is 11-04's full-uninstall wiring (finding #17).
- **11-02** (policy model + factory): `.apply()`'s reapply-failure rollback now makes a best-effort
  RE-BOOTSTRAP of the restored (old) plist content when a prior snapshot existed, correcting the
  cycle-1 assumption that restoring the plist bytes alone was sufficient — re-reading `bootstrap`'s
  own 11-01 implementation shows it ALWAYS runs its own unconditional `bootout` pre-clear first, on
  every call, so a reapply's failed second `bootstrap` leaves NOTHING registered, not merely the
  old config (#5); the shared apply helper now calls `daemon.render_plist(...)` as a pure
  validation gate BEFORE `install_wrapper`/`ensure_log_path` run, not only inside `write_plist`
  itself, so an invalid environment produces genuinely zero filesystem side effects as the plan's
  own text already claimed (#6); a marker-write failure AFTER a successful `bootstrap`/`bootout`
  no longer propagates as an exception — `.apply()` now catches it and returns its normal
  successful `PolicyResult` with `.warning` set, since `action_toggle_policy` (re-read live this
  session, `installer/wizard_app.py:1038`-`:1043`) only updates `active_state` when the result is
  non-`None`, and a propagated failure here would have shown the daemon as OFF while it is actually
  ON (#7); `.remove()`'s own plist unlink is now guarded, making a best-effort re-bootstrap of the
  still-on-disk plist on a real unlink failure (mirroring `.apply()`/`.set_schedule()`'s own
  rollback shape), and `.remove()` now also calls `daemon.remove_wrapper(wrapper_bin_dir)` — which
  had no production caller anywhere in the pre-cycle-2 plan set, the exact "no orphan helpers" gap
  `.claude/architecture.md` rule 5 flags (#8, #9; #9 also auto-resolves 11-04's own finding #16,
  since 11-04's full-uninstall teardown reuses this SAME `.remove()` closure, so no separate 11-04
  code change was needed for #16). `Policy` gains a fifth new field, `is_active: Callable[[], bool]
  | None = None`, a live re-check closure (`lambda: plist_path.exists()`), `None` for every other
  policy — consumed by 11-04's `active_policies` fix so a daemon enabled by the on-by-default
  worker AFTER `Policy` construction is never invisible to a later Uninstall visit (#13, a Plan
  11-04 finding resolved here since it is fundamentally a `Policy`-shape gap).
- **11-03** (detail panel + time picker): `_policy_detail`'s NORMAL render path (mount,
  row-highlight — not only the `l` log-toggle action) now wraps BOTH its `daemon.
  last_run_summary(...)` and `policy.read_schedule()` calls in a local `try/except (OSError,
  ValueError, UnicodeDecodeError)`, a second, independent guard on top of 11-01's own
  mechanism-tier total-ness fix, so a corrupted plist/log file can never crash the whole screen
  before a user ever presses `l` (#10); `space`/`t` (toggle/reschedule) remain synchronous through
  `run_live`, an explicit ACCEPT decision (not a code fix) — re-reading `installer/wizard_app.py::
  action_toggle_policy` live confirms every OTHER existing policy (`ban`, every `tweak:*`,
  `omz-plugins`) already runs this way with zero worker infrastructure; giving the daemon a worker
  here alone would be an unexplained, one-off exception to this codebase's own single "apply
  workflow" architecture rule, a hang here is directly attributable to the key the user just
  pressed (unlike 11-04's unattended startup auto-apply, which DOES get worker treatment for
  exactly that reason), and `launchctl bootstrap`/`bootout` are sub-second, kernel-level operations
  per 11-RESEARCH.md's own already-live-verified transcript (#11); and `PoliciesScreen.__init__`
  now explicitly initializes `self._log_view: bool = False` rather than relying solely on the
  row-highlight handler ever having fired first (#12).
- **11-04** (composition + on-by-default): the Uninstall sweep's daemon-inclusion predicate in
  `active_policies` now reads `daemon_policy.is_active()` when that closure is present (11-02's new
  field), falling back to the frozen `.active` snapshot only when it is not — every other policy is
  unaffected, since `is_active` stays `None` for them (#13); the auto-apply gate is now an explicit
  `apply_daemon_default: bool = False` ALLOWLIST parameter threaded through `_build_app`, replacing
  the pre-cycle-2 `initial_view != "uninstall"` BLOCKLIST — re-reading `setup.py` live this session
  confirms `initial_view` also takes the values `"doctor"` (both `_run_doctor`'s and `_run_fix`'s
  interactive branches) and `"policies"` (the `--guard`/`--unguard` branch), neither of which the
  old blocklist excluded, meaning simply running `make doctor` — documented read-only at
  `Makefile:19` — would have silently registered and started the daemon; only `_select_catalog`'s
  own call site (the genuine interactive `make setup` wizard flow) now passes
  `apply_daemon_default=True` (#14); a new `UnifiedApp._daemon_default_in_flight` boolean, `True`
  from `__init__` whenever a real auto-apply callback is wired and cleared unconditionally the
  moment the worker's completion message is handled, gates `action_toggle_policy` and
  `UninstallScreen._apply_removal` against acting on the daemon's own policy id while the
  background worker may still be mid-`bootstrap`/`bootout` on a separate thread — the worker itself
  now ALWAYS posts its `DaemonDefaultApplied` completion message regardless of the boolean outcome
  (the pre-cycle-2 design posted only on success, leaving the in-flight flag with no deterministic
  clearing point on a no-op or failed auto-apply), which is what makes the flag's clearing correct
  in every case (#15); 11-02's own `remove_wrapper` fix (#9) closes the "full uninstall leaves the
  wrapper behind" gap with zero additional code needed here, pinned by a new regression test (#16);
  a new `clear_decided(state_path)` call, added to `run_uninstall`/`perform_uninstall`, fires ONLY
  after their respective sweep completes and ONLY when the daemon's id is actually present in that
  sweep's own `SweepResult.swept` — never before the sweep, since `daemon_policy.remove()` itself
  still calls `record_decided` as part of that same sweep call, and never on a failed removal — so
  a full uninstall+reinstall is treated as genuinely fresh without touching the ordinary
  toggle-off's permanent marker (#17); `tests/test_uninstall_e2e.py`'s two pre-existing
  `perform_uninstall(...)` call sites (inside `_build_real_app`'s and `_build_real_app_with_tweaks`'s
  own `_remove` closures) now pass `daemon_policy=None`, fixing a `TypeError` these Linux-platform
  tests would otherwise raise the moment `daemon_policy` becomes a required parameter — this file
  was genuinely absent from the pre-cycle-2 plan's own modified-file list and is now added to
  11-04's `files_modified` (#18); `UninstallScreen._applied_summary` and `run_uninstall`'s own CLI
  success line (re-read live this session, `installer/wizard_app.py:841`-`:847` and
  `installer/app.py:427`) are now ALSO made daemon-aware, keyed off the sweep's own
  `SweepResult.swept` — the pre-cycle-2 design fixed only the PREVIEW row, missing the
  SUCCESS-reporting strings shown after confirmation (#19); and the auto-apply-suppression test now
  asserts against `_capture_app`'s own captured `_build_app` kwargs (re-confirmed live this session
  at `tests/test_setup.py:93`) across every `initial_view` entry point, rather than only proving an
  injected callback was never invoked — the composition-wiring bug finding #14 identifies would
  have passed the pre-cycle-2 test's own assertions completely undetected, since `_capture_app`'s
  stub never runs `on_mount` at all (#20).

Live verification performed this session, on this machine, before writing any fix touching real
system/library behavior, and re-confirmed a second time immediately before writing this note:
`python3 -c "import plistlib; print(plistlib.InvalidFileException.__mro__)"` confirms
`plistlib.InvalidFileException` is a `ValueError` subclass (`(InvalidFileException, ValueError,
Exception, BaseException, object)`), NOT an `OSError` — grounding 11-01 finding #3's exact `except`
clause. `env -u HOME TMPDIR=/tmp bash scripts/prune-user-tmpdir.sh --dry-run` fails immediately with
`line 71: HOME: unbound variable`, confirming the script itself genuinely requires `HOME` to be set
— grounding finding #1's mechanism-tier motivation. `launchctl bootout gui/$(id -u)/com.tools-
installer.nonexistent-test-<n> ; launchctl error 3` re-confirms exit code `3` decodes as `"3: No
such process"` (Darwin's ESRCH) — the same "already absent" fact cycle 1 established, reused
(not re-derived) as the grounding for 11-02 findings #5/#7/#8's ordering logic. A SEPARATE real
test performed during this revision — bootstrapping a genuine, self-torn-down `gui/<uid>`
LaunchAgent on this machine, once with no `EnvironmentVariables` key at all and once with an
explicit `EnvironmentVariables={PATH, TMPDIR}` override — showed `HOME` (along with `SHELL`/`USER`/
`LOGNAME`/`SSH_AUTH_SOCK`) already inherited from the login session's own environment in BOTH
cases; `HOME` was never actually observed missing from a real bootstrapped LaunchAgent's
environment on this machine/session, in contrast to what finding #1's report text might otherwise
suggest. Finding #1's fix is implemented in full anyway, exactly as the finding requests, as a
defensive, version-independent guarantee that does not depend on undocumented launchd
session-inheritance behavior holding across every macOS version or session state — this nuance is
recorded here, and in 11-01's own `<design_decisions>`, rather than silently treated as if the
missing-`HOME` failure mode had been reproduced on this machine. Findings #5/#6/#7/#8 (11-02's
apply/remove ordering and rollback corrections) were verified by re-reading 11-01's own
already-live-verified `bootstrap`/`bootout` implementations directly against 11-02's own draft
logic, rather than re-deriving new system-level facts these fixes did not depend on; `installer/
wizard_app.py::action_toggle_policy`, `UninstallScreen._applied_summary`, `run_uninstall`'s CLI
success line, and `tests/test_setup.py::_capture_app` were all re-read from the actual current
source (not from memory of the earlier research/review passes) immediately before citing their
exact line numbers above. Cycle 1 and cycle 2's findings above are left unmodified; this note is an
append, not a rewrite.

## Cycle 3 (codex-sol-high)

**Reviewer:** codex CLI, model `gpt-5.6-sol (reasoning=high)`
**Commit reviewed:** `c17609a` (post cycle-2 revision, all 4 plan files)
**Risk assessment:** HIGH (all 4 plans)

### Overall Assessment

"Request changes before execution. Overall risk: HIGH." The plans are unusually thorough and
source-aware, but several lifecycle bugs remain, concentrated in partial-failure/state-transition
edge cases. Most severe: Plan 11-02 can leave daemon-owned artifacts after a failed first
bootstrap and can re-enable a daemon after an explicit disable if recording the decision fails;
Plan 11-04 confuses "default application occurred" with "policy is currently active," contains an
uninstall/auto-apply race the cycle-2 guard doesn't actually close, and fails to clear the decision
marker when uninstalling an already-disabled daemon; Plan 11-01 specifies an integration test that
cannot use the production `render_plist` API as written.

### Plan 11-01 — Core daemon mechanism (HIGH until fixed, MEDIUM after)

1. **HIGH — the real integration test is incompatible with the specified API.** `render_plist`
   fixes `ProgramArguments` to the `uv`/wrapper invocation, but the live test says to build the
   plist "via `render_plist`/`write_plist`" with `["/bin/echo", "hello"]` instead
   (`11-01-PLAN.md:291`, `:339`) — no parameter permits that override.
2. **MEDIUM — the truncation algorithm does not enforce the stated cap.** It retains complete
   lines until the accumulated size is already at or over the cap, so a single long line can
   remain substantially larger than 256 KB; `"\n".join(kept)` may also drop the final newline,
   concatenating the next header with prior content (`11-01-PLAN.md:455`).
3. **MEDIUM — `_truncate` has conflicting ownership.** Assigned to `installer/daemon.py`, but the
   standalone wrapper launched via `uv run --no-project --script` from `~/.local/bin` cannot
   safely assume the repository's `installer` package is importable (`11-01-PLAN.md:486`).
4. **MEDIUM — one shared atomic-write helper has incompatible permission requirements** — plist
   writes must force `0644` while `.myshellrc` writes must preserve existing mode
   (`11-01-PLAN.md:306`, `:558`); the existing OMZ helper always preserves the target mode
   (`installer/omz.py:190`, `:217`).

### Plan 11-02 — Policy model and daemon factory (HIGH)

1. **HIGH — a failed first bootstrap leaves owned artifacts behind.** The shared helper installs
   the wrapper and creates the log before bootstrap; on first-bootstrap failure, rollback removes
   only the plist (`11-02-PLAN.md:620`, `:629`) — since activity is defined by plist presence,
   later uninstall discovery never sees the orphan wrapper, violating the "no orphan helpers" rule
   (`.claude/architecture.md:23`).
2. **HIGH — decision-marker failure after removal breaks user intent.** Removal unregisters the
   job, deletes the plist/wrapper, and only then calls `record_decided` without the apply path's
   warning handling (`11-02-PLAN.md:653`) — a write failure here reports the whole operation
   failed even though the daemon is already off, and more importantly an absent marker lets the
   next setup auto-enable it again, silently reversing an explicit disable.
3. **MEDIUM — `remove_wrapper` is treated as infallible** — an owned-file `unlink()` failure after
   plist removal isn't guarded, creating the same UI/reality mismatch pattern as other findings.
4. **MEDIUM — rollback bypasses the atomic plist writer**, restoring old bytes via
   `plist_path.write_bytes(previous)` (`11-02-PLAN.md:636`) instead of through the same
   crash-safe/permission-preserving writer 11-01 establishes.
5. **MEDIUM — `set_schedule` can create an inactive policy's plist** — the core closure accepts a
   missing snapshot and proceeds even though the UI intends to guard this (`11-02-PLAN.md:669`).

### Plan 11-03 — Policies UI and time picker (MEDIUM)

1. **MEDIUM — toggle and reschedule can freeze the TUI.** The plan keeps both synchronous on the
   event loop (`11-03-PLAN.md:213`); `run_captured` still has no timeout. (Reviewer acknowledges
   this is an explicit, reasoned ACCEPT decision from cycle 2, not an oversight — still flags it
   as a residual reliability risk worth a bounded worker/timeout if feasible.)
2. **LOW — the new modal doesn't inherit `NavScreen`'s class-specific CSS** (`installer/wizard_app.py:1111`
   targets `NavScreen > ListView` specifically) — a 48-row `TimePickerScreen` needs its own
   bounded/centered styling.

### Plan 11-04 — Composition, default enablement, and uninstall (HIGH)

1. **HIGH — `applied` is not the same as `active`.** `ensure_daemon_default` returns `False` when
   the decision marker already exists; the handler passes that to
   `refresh_daemon_state(..., active=False)` (`11-04-PLAN.md:760`, `:787`) — on a normal second run
   where the marker exists AND the daemon is active, the UI flips from its correct construction-time
   `True` snapshot to `False`. Tests cover decided-and-disabled but not decided-and-enabled.
2. **HIGH — the uninstall race guard misses the dangerous case.** It blocks only when `_tweak_ids`
   already contains a `daemon:` ID (`11-04-PLAN.md:824`) — during first-run auto-apply the daemon
   starts inactive, so the uninstall screen's live snapshot may contain no daemon ID at all
   (`installer/wizard_app.py:718`); uninstall can finish, then the worker registers the daemon
   afterward.
3. **HIGH — full uninstall does not clear an explicit-disable marker.** `clear_decided` runs only
   if the daemon was actually in `SweepResult.swept` (`11-04-PLAN.md:985`) — if the user previously
   disabled the daemon, the plist is already absent, so sweep sweeps nothing and the marker
   survives, meaning reinstall is not "genuinely fresh" as claimed.
4. **MEDIUM — required-argument migration is underspecified** — `tests/test_app.py` alone has 15
   `run_uninstall` calls and several `perform_uninstall` calls beyond the two e2e calls the plan
   names explicitly (`tests/test_app.py:355`, `:1201`; `tests/test_uninstall_e2e.py:53`).
5. **MEDIUM — an unexpected worker exception leaves the in-flight flag stuck** — completion is only
   posted from the expected `OSError`/`CommandError` paths, not a `finally` block.
6. **MEDIUM — "fresh install" vs. "first run after upgrade" is unresolved** — an existing
   installation with no daemon decision marker will be treated as fresh on its next ordinary setup
   run and silently enable the daemon; needs an explicit migration decision and test.

### Recommended execution gate (per reviewer)

1. Fix Plan 11-01's integration-test API contradiction.
2. Make Plan 11-02 roll back wrapper/log side effects on failed first bootstrap, and make
   explicit-disable recording durable even if the marker write fails.
3. Make Plan 11-04 communicate live active state (not "applied"), block uninstall for the full
   duration of auto-apply regardless of the `_tweak_ids` snapshot, and clear the marker on full
   uninstall even when the daemon was already disabled.
4. Add decided-and-active, uninstall-during-first-apply, failed-first-bootstrap-orphan, and
   disabled-daemon-full-uninstall regression tests.

### Disposition

This is cycle 3 of 3 — the hard cap per `.planning/ONESHOT-RULES.md` Rule 10. 6 HIGH + 9 MEDIUM +
1 LOW findings remain, source-grounded with exact file:line citations. These are real,
substantive edge-case defects (state-machine correctness under partial failure, not review noise),
but narrower in scope than cycle 2's 9 HIGH findings, and every "Strengths" section confirms the
core cycle-1/cycle-2 architecture (uv invocation, atomic writes, transactional apply/remove intent,
`apply_daemon_default` allowlist, worker-based defaulting) is sound. Per the 3-cycle cap, no
further review cycle will be dispatched. Proceeding to ONE final direct fix pass (not a 4th review
cycle) addressing every finding above, then to execution regardless of any residual finding this
final pass cannot fully close — any such residual will be carried forward as a documented known
limitation in the phase's SUMMARY/VERIFICATION rather than silently dropped.

### Revision Note (post cycle 3 — final)

A full direct fix pass edited all four plan files (`11-01-PLAN.md` through `11-04-PLAN.md`) in
place to address every cycle 3 finding above. **This is the final revision pass per the 3-cycle
cap — no cycle 4 review will be dispatched; the plans proceed to execution after this pass.**

- **11-01** (core mechanism): the live `launchctl bootstrap`/`print`/`bootout` round-trip test no
  longer claims to build its plist via `render_plist`/`write_plist` (which hard-codes
  `ProgramArguments` to the uv-routed wrapper invocation with no override) — it now builds a
  throwaway plist dict by hand and writes it via a NEW, shared private
  `_atomic_write(path: Path, data: bytes, *, mode: int | None = None) -> None` helper, called with
  `mode=0o644` for this test exactly as `write_plist` itself now calls it internally (#1). Log
  truncation (moved, see #3 below) now enforces its `cap_bytes` cap as a genuine hard ceiling: an
  oversized single line is hard-truncated to its own trailing `cap_bytes - 1` bytes
  (decode-recovered with `errors="ignore"` at the cut point), an oversized single run is capped
  after the header-boundary snap rather than left as large as whatever was accumulated, and the
  result always ends with exactly one re-added trailing newline regardless of the original file's
  own trailing-newline state, so a truncated file's next appended header can never concatenate
  onto prior content (#2). `_truncate` moves out of `installer/daemon.py` into
  `installer/helper_assets/prune_daemon_runner.py` itself — self-contained, standard-library-only
  — since the standalone wrapper (invoked via `uv run --no-project --script`) cannot assume the
  `installer` package is importable; this plan's own tests now import it via
  `from installer.helper_assets import prune_daemon_runner`, mirroring `tests/test_wait_time.py`'s
  own existing import of `wait_time` for the SAME reason (#3). The new `_atomic_write` helper
  takes an explicit `mode` parameter reconciling a genuine conflict the pre-cycle-3 text left
  unresolved: `write_plist` calls it with `mode=0o644` (forced, unconditional, matching
  `installer/omz.py::_atomic_write`'s Tampering-mitigation posture for a LaunchAgent config), while
  Task 3's `record_decided`/`clear_decided` call the SAME function with `mode=None` (preserving
  the target's existing mode via `shutil.copymode` when present, no chmod otherwise) — an exact
  mirror of `installer/omz.py::_atomic_write`'s own mode-preservation behavior for `~/.myshellrc`,
  re-read live this session (`installer/omz.py:190`-`:223`) to confirm it never chmods a
  newly-created file and only ever `copymode`s an existing one (#4).
- **11-02** (policy model + factory): `.apply()` now snapshots `wrapper_present(wrapper_bin_dir)`
  and `log_path.exists()` BEFORE calling the shared validation-plus-write helper, so a FIRST-EVER
  (`had_prior_plist is False`) `bootstrap` failure rolls back the wrapper/log THIS call newly
  created (via `remove_wrapper`/`unlink`), not only the plist — a reapply's failure still leaves
  the wrapper/log untouched, since they legitimately predate that call (#1). `.remove()` now
  collects wrapper-removal and marker-write failures into a `warnings: list[str]`, guarding BOTH
  `daemon.remove_wrapper` and `daemon.record_decided` in `try/except OSError`, joining any
  non-empty result into `PolicyResult.warning` rather than ever propagating either as a removal
  failure — mirroring `.apply()`'s own cycle-2 marker-write-as-warning fix, and closing the
  specific risk that a marker-write failure after a genuinely successful removal would leave
  `decided()` reading `False`, silently letting the next `make setup` run re-enable a daemon the
  user just explicitly disabled (#2, #3). Every plist-bytes rollback (`.apply()`'s reapply path,
  `.set_schedule()`'s own rollback) now writes through the SAME `_atomic_write(plist_path,
  previous, mode=0o644)` helper 11-01 established, never a raw `write_bytes` call (#4).
  `.set_schedule(hour, minute)` now raises `DaemonScheduleError` immediately when
  `not plist_path.exists()`, a core-layer guard against creating a plist for a policy the user
  never enabled, alongside (not instead of) 11-03's own UI-layer gate (#5).
- **11-03** (Policies UI + time picker): `TimePickerScreen` now defines its own `DEFAULT_CSS`
  (`align: center middle`, a BOUNDED `height` on its `ListView` — never `auto` — sized inside this
  project's own smallest tested terminal height, re-confirmed live this session via
  `grep -rn "run_test(size="` across `tests/test_wizard_app.py`/`tests/test_tool_browser.py`,
  which consistently use `size=(100, 30)`/`size=(80, 20)`), since Textual's CSS selectors are
  scoped by exact class name and `TimePickerScreen` never inherited `NavScreen`'s own
  `NavScreen > ListView` rule (#10). Finding #1 (toggle/reschedule staying synchronous) was
  re-raised by the reviewer but explicitly confirmed as this plan's own reasoned, already-documented
  cycle-2 ACCEPT decision, not a defect — a one-line acknowledgment was added to
  `<design_decisions>` per the reviewer's own instruction; no code change accompanies it.
- **11-04** (composition, on-by-default, uninstall): `PoliciesScreen.refresh_daemon_state` (its
  second parameter renamed `active` → `applied` to name what it actually represents) now looks up
  the matching `Policy` from `self._policies` (confirmed live this session,
  `installer/wizard_app.py:881`, `self._policies = inputs.policies`) and resolves its new value via
  `policy.is_active()` when present, COMPLETELY IGNORING the worker's own `applied` boolean, which
  only ever means "no `.apply()` call was made this run" — equally true whether the daemon is
  already active-and-decided or already disabled-and-decided; the pre-cycle-3 code conflated the
  two, incorrectly flipping an already-on daemon's row to OFF on every ordinary second run (#11).
  `UninstallScreen._apply_removal`'s in-flight guard drops its own `self._tweak_ids` membership
  check entirely, gating purely on `self.remove_tweaks` selected AND
  `self.app._daemon_default_in_flight` — during first-run auto-apply the daemon `Policy` is
  constructed inactive, so the screen's own construction-time snapshot may contain no daemon id at
  all yet even while the worker is actively racing to register it (#12). The `clear_decided`
  condition in both `run_uninstall`/`perform_uninstall` changes from "daemon id present in
  `SweepResult.swept`" to "daemon id NOT present in `SweepResult.failed`" (`SweepResult`'s exact
  `swept`/`failed` tuple shape re-confirmed live this session, `installer/uninstall.py:253`-`:263`)
  — so a full uninstall now clears the marker whenever the daemon was not left in a genuinely
  FAILED state, including when it was already disabled and contributed nothing to the sweep, while
  still preserving the marker on an actual removal failure (#13). `tests/test_app.py`'s own 17
  pre-existing `run_uninstall`/`perform_uninstall` call sites (14 + 3, live-grepped this session)
  — not only the two `tests/test_uninstall_e2e.py` calls the pre-cycle-3 plan already named — are
  now enumerated and added to Task 3's own migration/verification scope (this file was already
  present in the frontmatter `files_modified` list, but the task body had not accounted for its own
  call sites) (#14). The on-by-default worker's body is now wrapped in `try/finally`
  (`applied = False` initialized before the `try`), so its completion message is always posted —
  and `_daemon_default_in_flight` therefore always eventually cleared — even for an exception
  outside `ensure_daemon_default`'s own `except (OSError, CommandError)` tuple (#15). The
  "fresh install vs. first run after upgrade" ambiguity is resolved as an explicit, documented,
  ACCEPTED consequence of CONTEXT.md's own D-01 decision: `decided(state_path)` answers a
  per-POLICY question, not a per-installation-age one, so an existing installation with no daemon
  marker is intentionally treated identically to a fresh one — a migration-specific marker was
  considered and rejected as an unrequested scope expansion; a regression test locks the chosen
  behavior in (#16).

Live verification performed this session, before writing any fix that depends on real source
shapes: `installer/omz.py::_atomic_write` (lines 190-223) was re-read to confirm its exact
`shutil.copymode`-when-present / no-chmod-otherwise behavior, grounding 11-01 finding #4's `mode`
parameter design. `tests/test_wait_time.py` was re-read to confirm its
`from installer.helper_assets import wait_time` import shape, grounding 11-01 finding #3's
test-import approach for the relocated `_truncate`. `grep -n "run_uninstall(\|perform_uninstall("
tests/test_app.py` was run live, returning 17 matches (14 `run_uninstall(`, 3
`perform_uninstall(`), grounding 11-04 finding #14's exact scope. `installer/uninstall.py`'s
`SweepResult` dataclass (lines 253-263) was re-read to confirm its exact `swept`/`failed` tuple
shape, grounding 11-04 finding #13's corrected `clear_decided` condition. `installer/wizard_app.py`'s
`PoliciesScreen.__init__` (`self._policies = inputs.policies`), `NavScreen`/`ConfirmUninstall`'s
own `DEFAULT_CSS` blocks, and `installer/run.py`'s `CommandError` shape were all re-read live this
session before being cited by file:line. `grep -rn "run_test(size="` was run across
`tests/test_wizard_app.py`/`tests/test_tool_browser.py`/`tests/test_policies_e2e.py`, confirming
this project's own tested terminal-size conventions (`size=(100, 30)`, `size=(80, 20)`, `size=(80,
30)`), grounding 11-03 finding #10's CSS-sizing rationale. No claim in this pass rests on an
unverified assumption about `plistlib`, Textual, or `launchctl` behavior beyond what cycles 1 and 2
already live-verified and recorded above; this pass introduced no new claims of that kind, since
its own fixes (a hard truncation cap, an explicit `mode` parameter, a `try/finally` wrapper, a
`SweepResult.failed`-based condition, an `is_active()`-based UI refresh) rest on ordinary,
well-documented Python/dataclass semantics rather than undocumented system behavior.

Every one of the 16 numbered cycle-3 findings across all four plans was closed with a concrete
plan-text fix in this pass — none was silently dropped or deferred. The one item NOT treated as a
code-level fix is finding #16 (fresh-install-vs-upgrade): per the reviewer's own framing ("decide
whether that's acceptable... or whether a migration-specific marker/check is needed"), this pass
made an explicit DECISION (accept, matching D-01's plain language) rather than adding new
migration-tracking machinery, and recorded the reasoning plus a locking-in regression test in
11-04's own `<design_decisions>` and `<must_haves>` — this is a decision made under this final
pass's own authority in the absence of a user to consult mid-session, documented here for
visibility rather than presented as equivalent to the other, code-level fixes. The one OTHER
carried-forward item is not a gap this pass left open but a pre-existing, reviewer-reaffirmed
ACCEPT: 11-03's synchronous `run_live`-routed toggle/reschedule (cycle 2's own finding #11)
remains a documented, reasoned residual reliability risk — the cycle 3 reviewer explicitly
confirmed this is not a defect requiring a fix, only re-flagging it for visibility, so no code
change was made and none was warranted. Cycles 1, 2, and 3's findings above are left unmodified;
this note is an append, not a rewrite. Per the 3-cycle cap (`.planning/ONESHOT-RULES.md` Rule 10),
no cycle 4 review will be dispatched — these four plan files are now ready for execution.
