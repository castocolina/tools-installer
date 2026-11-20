# Phase 35: Opt-in auto-update, package managers first - Context

**Gathered:** 2026-11-19 (assumptions mode, after 35-SPEC.md)
**Status:** Ready for planning

<domain>
## Phase Boundary

An opt-in `update-all` Schedules row (off by default) runs nightly: a pure planner orders package managers first and their dependents after, a runner executes the plan through the existing per-tool update path with refusal, lock and failure-skip rules, a plan-only mode prints the same plan, and one summary notification follows a non-empty run. Phase 34 must be executed first: this phase consumes its notifier, outdated-set function, `stale_after` window, `Schedule.daily` field and `JobKind.CHECK_UPDATES`.
</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**10 requirements are locked.** See `35-SPEC.md` for full requirements, boundaries, and acceptance criteria.

Downstream agents MUST read `35-SPEC.md` before planning or implementing. Requirements are not duplicated here.

**In scope (from SPEC.md):** the `update-all` row with a per-row default, the planner, the runner with skip rules, plan-only mode, the run log, the once-a-day rule, the post-run notification, unit templates, a container end-to-end run, and the 24.2 SCHED-01 amendment record. *Amended 2026-11-19 (35 D-02, D-11, D-12, D-13, D-16):* a new `JobKind.UPDATE_ALL`, widened `--run-schedule` choices, a per-job runner timeout, `update-all.log` and `updated-today.json` (both swept on uninstall), and `stdin=DEVNULL` in the runner's child.
**Out of scope (from SPEC.md):** updating casks by default; merging the five per-tool rows; sudo, pkexec, doas; a Policies row; real-Mac checks.

</spec_lock>

<decisions>
## Implementation Decisions

### The row
- **D-01: A per-row default:** `default_on: bool = True` on `Schedule`; `update-all` has `default_on=False`. One seeding line changes: in `_row_action`, `decided is None` returns `"turn-on"` only when `schedule.default_on`, else `"none"` (`installer/schedules.py:1548-1562`; `record_for` `:236-241`; `_reconcile_pass` `:1692-1712`; `ensure_schedule_defaults` `:1715-1721`). `_RECORD_KEYS` (`:258`) and the schemas stay unchanged: `decided` already has three values (None, False, True), and a new state key would trip `_StateError` on older readers and the sticky damage warning. An off row never appears in `turned_on`, so `tests/test_schedules_lifecycle.py:107,152` and `tests/test_schedules_handover.py:493` stay unedited.
- **D-02: A new `JobKind.UPDATE_ALL = "update-all"`, `target=None`, appended after 34's `check-updates`;** not an `UPDATE` row with an empty target, because several paths assume an `UPDATE` row has a present target: `_require_available` (`schedules.py:710-714`), `row_state` (`:1488-1492`), the gone-target drop in `_reconcile_pass` (`:1701-1704`, which would delete the units every pass), `UPDATE_SCHEDULE_IDS` (`:94-96`), `run_schedule`'s kind gate (`installer/schedule_run.py:131-133`). It needs its own `runner_argv` branch (`schedules.py:853-888`). `installer/cli.py:56-62` builds the `--run-schedule` choices from `UPDATE_SCHEDULE_IDS`, so the choices are widened for both `check-updates` (34) and `update-all` (35) *(amended 2026-11-19, 35 D-02, in 34-CONTEXT D-02)*.
- **D-03: The row is daily** (`daily=True`, interval hidden) **starting at 03:00:** off the 00:00/06:00/12:00/18:00 update grid and before 34's 09:00 check, so the check sees the result; the once-a-day rule makes more frequent runs useless. **Own reasoning** (jev first rung low 0.59; TypeSafe none_of_these low 0.48). Ledger.
- **D-04: The view needs no new mechanism:** an undecided `update-all` has no files and renders `off` (`schedules.py:1493-1497`); `space` calls `schedules.turn_on` (`installer/schedules_screen.py:629`), recording `decided=True`; only `what` (`:458-466`) and `_target` (`:430-435`) get a branch. It is not a Policies row, but `sweep_adapters` (`schedules.py:1900-1935`) yields a `schedule:update-all` uninstall adapter (a teardown extra, `installer/compose.py:626-629`, `setup.py:493`), so the "no Policies row" test must look at the Policies view rows, not at ids starting with `schedule:`.

### The planner
- **D-05: "Package manager" means a catalog tool named by an `Owner` value** (`installer/ownership.py:82-97`): brew (which also owns `cask`), uv, bun, pnpm, sdkman, volta; not the registry `category` (`pkg-mgr` covers only uv, brew, pnpm and volta, `registry.toml:63,164,2229,2291`; bun and sdkman are `runtime`). Managers are ordered deps-first over who owns whom: a manager installed by another manager comes after it (a brew-owned uv, bun, pnpm or volta follows brew), ties by tool id. `resolve._RANK` cannot do this: it ranks the install-method kind (`installer/resolve.py:15-31`), brew itself is a `script` method (rank 10) while a brew-owned tool's kind `brew` is rank 5, `_RANK` has no `volta` key and ranks `sdkman` after `script`. This **amends ROADMAP criterion 2 and AUTOUPD-02** ("ranked by `resolve._RANK`"); **flagged: needs confirmation**. **Own reasoning** (jev install_preference_rank low 0.51 and 0.63, rejected by the evidence). Ledger.
- **D-06: A dependent's owner is its `ToolState.ownership.owner` mapped to its manager (`cask` to brew);** groups follow the manager order; non-manager owners (`installer`) form one final group. Within a group, `deps.resolve_dependencies(selected=<group sorted by id>, catalog=<all tools>)` gives the order and its closure is filtered back to the group's members (the closure drags in `requires` from outside the group: unzip, zip, puppeteer; `installer/deps.py:40-155`). A dependent is skipped as `skipped: <manager> failed` when its owner's manager failed or any manager in its transitive `requires` failed (mmdc is pnpm-owned but `requires = ["bun","puppeteer"]`); the failure set lives in memory for the one run and is never persisted. **Own reasoning** (jev owned_and_needing low 0.58; first rung none_of_these 0.85 contradicted the evidence). Ledger.
- **D-07: Managers always run their own self-update; a dependent enters the plan only when 34's `outdated_ids(states)` lists it,** on a forced refresh with 34's `stale_after` window; tools with an unknown version are not planned. An installer-owned download update always re-downloads (`installer/download.py:437-465`) and a script without a declared `update` re-runs the vendor installer (`installer/update.py:503-505`), while manager updaters (`brew update`, `uv self update`, `bun upgrade`, `sdk selfupdate`, `pnpm self-update`) are cheap no-ops when current; filtering managers by version would skip `brew update`, whose metadata refresh lets `brew upgrade` see new formulae. Plan mode uses the cached pass without forcing a refresh, so it writes nothing, not even the version cache. **Own reasoning** (jev outdated_only low 0.32 and 0.42). Ledger.
- **D-08: The planner is a pure module** (`installer/update_all.py`): inputs are the catalog tools, `(tool, ownership)` pairs from one pass, the outdated set, the updated-today map and `platform_os`; it returns an ordered tuple of entries, each `update` or `skip <reason>`. It calls `update_refusal` (`installer/update.py:283`, zero subprocess) so the plan and a real run share the skip texts; macOS `cask` owners plan as `skipped: cask excluded`; `schedule_run.py` only dispatches to it. Planning through `version_refresh.resolve_owner` per tool would run the brew/uv/bun inventory queries about 100 times (`version_status.py:1639-1660`), so the plan takes one pass and the real run re-resolves per tool inside `UpdateService.run` (`update.py:650-660`). jev first rung none_of_these 0.98 contradicted the evidence; second opinion only_while_running low 0.65, which would break R9's plan-equals-run acceptance. **jev overridden / Own reasoning.** Ledger.
- **D-09: `update-all` skips a script tool that has no declared `update` argv** as `skipped: no unattended update path`; today that is Volta (`registry.toml:2310-2320`: `get.volta.sh` runs `volta setup`, which rewrites `~/.profile`, `~/.zshrc`, `~/.bashrc` and `~/.bash_profile`; `update.py:503-505`); AGENTS.md treats rc edits as host mutation. Volta stays in the manager order; the interactive `u` is unchanged. This amends SPEC R2 ("covers ... Volta": Volta is ordered, not updated); **flagged: needs confirmation** (the owner named volta among the managers). **Own reasoning** (jev skip_with_reason low 0.62; first rung none_of_these 0.91 contradicted the evidence). Ledger.

### The runner
- **D-10: The runner gets an `update-all --installer CHECKOUT --uv UV` job reusing `_update("update-all", installer, uv)`** (`installer/helper_assets/schedule_runner.py:320-358`; `_parse` jobs `:437-490`). On the installer side each `update` entry calls the existing per-tool path (`_run_unlocked`'s dispatch, `schedule_run.py:120-123`), so `cursor-agent` still gets its shim refresh and `UpdateService.run` supplies the fresh ownership, refusal and pnpm replay; the lock is `run_schedule`'s (parent holds, or `try_acquire`, or `skipped: busy`); children run with `CHILD_ENV` (`HOMEBREW_NO_SUDO`) and stdin `/dev/null` (`installer/run.py:50,184-191`).
- **D-11: A per-job timeout:** `update-all` gets a longer bound than 1800 s (2 to 3 h), each per-tool command inside the child gets its own bound (`run_captured_in_group` passes `timeout=None` today), and `_WAIT_BOUND` (7200 s) and its comment are re-derived (`schedule_runner.py:51,62-69` assume every holder lives at most `_UPDATE_TIMEOUT`). **Own reasoning** (jev stop_starting_new low 0.38; first rung low 0.62). Ledger.
- **D-12: The run log is `update-all.log` next to `schedules.log`** (`ctx.log_path.with_name(...)`), written by the installer child, never the runner (the runner keeps only the child's last `ok:`/`skipped:`/`failed:` line); truncated at run start with one line appended per tool (a killed run keeps its partial lines); last run only; it joins `_state_artifacts` (`schedules.py:1803-1811`); plan mode never writes it. The shared log keeps the one summary line. **Own reasoning** (jev every_run_capped low 0.73; first rung low 0.63). Ledger.
- **D-13: The once-a-day store is `updated-today.json`** (derived from `ctx.state_path.with_name`): `{"version":1,"updated":{"<tool id>":{"date":"YYYY-MM-DD","by":"update-all"|"update-claude"}}}` with local calendar dates, written with `atomic_write_text`, read with `read_capped(..., follow_symlinks=False)`, a corrupt file reads as empty; written only while the run lock is held (every runner holds it, so the two rows cannot race); a tool is recorded when `UpdateOutcome.status == "updated"`, which includes "up to date" (`update.py:176-185`; `schedules.py:477-488`); swept on uninstall. jev dedicated_state_file 0.93 (TypeSafe).
- **D-14: The per-tool rows skip a tool only if `update-all` updated it today;** `update-all` skips a tool either runner updated today. This keeps the five rows' 6 h cadence (`schedules.py:56-65`) and satisfies R7's acceptance in both directions; a global once-a-day rule would turn `update-claude`'s 06:00, 12:00 and 18:00 runs into skips. **Own reasoning** (jev one_per_day_everywhere low 0.71; first rung low 0.47). Ledger.
- **D-15: The summary line is `ok: N updated, M skipped`** when nothing failed and `failed: K failed (<first tool>), N updated, M skipped` with exit 1 when any tool failed (`_locked_run` maps `failed:` to exit 1, `schedule_runner.py:509-527`); extra clauses follow 34 D-21; a held lock gives `skipped: busy`; an empty plan gives `ok: 0 updated`. Refused tools and tools updated today count as skipped. jev failure_line 0.78 (Laya).
- **D-16: The runner's `_run_child` gets `stdin=subprocess.DEVNULL`** (`schedule_runner.py:226-233` relies on the service manager's default today); the installer's children already use `/dev/null` (`run.py:117,338`). jev close_explicitly 0.87 (Laya).

### Notification and plan-only mode
- **D-17: After a real run with a non-empty plan, the installer child calls 34's `Notifier` once with the counts;** a returned reason or an exception appends `; notify skipped: <reason>` and does not change the exit code; an empty run sends nothing; the notifier is injected through `RunDeps` (built by `notify.notifier_for` in `setup.py:529-544`) so tests pass a fake. Notifying from the stdlib runner would duplicate the logic where `installer` cannot be imported (`schedule_runner.py:26-29`).
- **D-18: Plan-only mode:** `cli.Options` gains `plan: bool` (`installer/cli.py:10-90`); `--plan` is valid only with `--run-schedule update-all` (any other combination is a `parser.error`); it takes no run lock, writes no log, store or notification, spawns no update and forces no refresh; it prints one line per entry in run order (`<tool> (<group>): would update` or `<tool>: skipped: <reason>`) then `ok: plan N to update, M skipped`; run-dependent skips (`<manager> failed`, `busy`) cannot appear in a plan; a manual real `--run-schedule update-all` without `--plan` is allowed while the row is off (the container e2e needs it). jev lock_free_preview_manual_run_allowed 0.80 (TypeSafe).

### Tests and the container proof
- **D-19: Existing tests that change:** `tests/test_schedules.py:105-140` (ids, labels, targets gain `update-all`; `UPDATE_SCHEDULE_IDS` stays), `tests/test_schedules_view.py:240-248` (gains `"never"`), `tests/test_cli.py:114-125` (choices; new `--plan` cases), `tests/test_schedule_runner.py` (jobs, per-job timeout, stdin), and the `runner_argv` and unit-template tests. Unchanged: `tests/test_schedules_lifecycle.py:107,152,256,441`, `tests/test_schedules_handover.py:493`, `tests/test_container_e2e_schedules.py:174` and `tests/e2e_schedules_driver.py:49,81` (derived from `SCHEDULES`), `tests/test_schedule_update.py:180-187`. New unit tests (scratch HOME, fakes only): planner fixtures (brew + uv + two dependents, one brew-owned and one uv-tool owned; bun + sdkman + pi/mmdc/java; ties by id; a brew-owned manager after brew; empty and managers-only plans; a macOS cask), a failing fake manager with an executor spy, each refusal text, a held lock, an AST/grep test for `sudo`/`pkexec`/`doas`, the child environment and stdin, the run log versus the shared log through `schedule_runner.main([...])`, the store in both directions with a corrupt file, the notifier counts, plan equals run, and a `_row_action` truth table.
- **D-20: The container e2e is a dedicated `update-all` target** in `scripts/container-e2e-verify.sh`, modeled on `schedules --direct` (`:2627-2690`) and `cmd_bun_lifecycle` (`:2864`): no systemd, an EXIT-trap teardown that removes the container; bootstrap with `bootstrap_homebrew_and_uv` (`:332-336`); install through the installer's own code via a driver like `tests/e2e_landing_driver.py` (brew, uv, bun; one brew formula dependent; one uv-tool dependent pinned older; sdkman and java for the refusal); run `--run-schedule update-all --plan`, then the real run through `uv run --script runner.py update-all ...` so `uv self update` runs inside the real `uv run` chain; capture `uv --version` before and after and the command output into the phase verification; a static test `tests/test_container_e2e_update_all.py` pins the script's constants and verdict markers. jev first rung none_of_these 0.91 contradicted the evidence; second opinion dedicated_run_real_installs 0.89. **jev overridden.**
- **D-21: Dependencies:** phase 35 depends on phase 34 being executed (34 currently has only a CONTEXT): `installer/notify.py` (`Notifier`), `outdated_ids`, `stale_after`, `Schedule.daily`, `JobKind.CHECK_UPDATES`, `DBUS_SESSION_BUS_ADDRESS` in the runner's `_PASSED_ENV`. The SPEC's "seven existing rows" is eight once `check-updates` exists.

### Claude's Discretion
- Module and helper names, the exact plan-line wording, the per-tool command bound, and the notification text.

### Folded Todos
- `.planning/todos/pending/2026-11-17-opt-in-auto-update-policy-managers-first.md` (the phase's own source todo).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `.planning/phases/35-opt-in-auto-update-package-managers-first/35-SPEC.md` — Locked requirements — MUST read before planning
- `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-CONTEXT.md`, `.planning/milestones/v0.50.0-phases/24.2-schedules-view/24.2-CONTEXT.md`
- `installer/schedules.py`, `installer/schedule_run.py`, `installer/helper_assets/schedule_runner.py`, `installer/update.py`, `installer/resolve.py`, `installer/deps.py`, `installer/ownership.py`, `installer/cli.py`, `setup.py`, `installer/run.py`
- `scripts/container-e2e-verify.sh`, `tests/e2e_landing_driver.py`, `.planning/research/2026-11-17-update-automation.md` (feature 2)
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `UpdateService`, `update_refusal`, the per-tool `_run_unlocked` path, `CHILD_ENV`, the run lock, `resolve_dependencies`, `atomic_write_text`, the container e2e harness.

### Established Patterns
- Schedule state in one directory with swept artifacts; one result line per run; refusals are zero-subprocess predicates shared by preview and run.

### Integration Points
- `SCHEDULES`, `_row_action`, `runner_argv`, the runner's job table and timeouts, `cli.Options`, `RunDeps`.
</code_context>

<specifics>
## Specific Ideas

Live facts that changed the SPEC (amended in this commit): `_RANK` cannot order managers; Volta's only update path rewrites shell rc files; a global once-a-day rule would change the per-tool rows' cadence; `update-all` must be its own job kind; the SPEC's "seven existing rows" is eight after phase 34.
</specifics>

<deferred>
## Deferred Ideas

- To confirm in the container or planning: whether `uv self update` is safe while two uv processes from the same binary run (R8); whether `sdk selfupdate`, `bun upgrade` and `pnpm self-update` are non-interactive and what they exit with when current; whether `get.volta.sh` has a flag that skips the rc rewrite (only matters if Volta is later updated); whether `brew upgrade <formula>` auto-updates again after `brew update` in the same run.

### Reviewed Todos (not folded)
None other matched.
</deferred>
