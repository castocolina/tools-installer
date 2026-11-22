# Phase 35: Opt-in auto-update, package managers first - Research

**Researched:** 2026-11-22
**Domain:** Python headless scheduler job (pure planner + runner child + Schedules row + container e2e) over the Phase 34 notifier and outdated-set seams
**Confidence:** HIGH for the code facts (every line cited was read this session, branch `gsd/phase-27-tool-onboarding-skill-terminal-defaults-as-rules` at `77af2bc2`); MEDIUM for the per-manager runtime behaviour (vendor docs and installer source, nothing executed); LOW for the `uv self update` safety verdict until the container run records it.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

(copied verbatim from `35-CONTEXT.md` `<decisions>`; line numbers inside the quoted text are the 2026-11-19 ones and are reconciled in `## CONTEXT Reconciliation`)

#### The row
- **D-01: A per-row default:** `default_on: bool = True` on `Schedule`; `update-all` has `default_on=False`. One seeding line changes: in `_row_action`, `decided is None` returns `"turn-on"` only when `schedule.default_on`, else `"none"` (`installer/schedules.py:1548-1562`; `record_for` `:236-241`; `_reconcile_pass` `:1692-1712`; `ensure_schedule_defaults` `:1715-1721`). `_RECORD_KEYS` (`:258`) and the schemas stay unchanged: `decided` already has three values (None, False, True), and a new state key would trip `_StateError` on older readers and the sticky damage warning. An off row never appears in `turned_on`, so `tests/test_schedules_lifecycle.py:107,152` and `tests/test_schedules_handover.py:493` stay unedited.
- **D-02: A new `JobKind.UPDATE_ALL = "update-all"`, `target=None`, appended after 34's `check-updates`;** not an `UPDATE` row with an empty target, because several paths assume an `UPDATE` row has a present target: `_require_available` (`schedules.py:710-714`), `row_state` (`:1488-1492`), the gone-target drop in `_reconcile_pass` (`:1701-1704`, which would delete the units every pass), `UPDATE_SCHEDULE_IDS` (`:94-96`), `run_schedule`'s kind gate (`installer/schedule_run.py:131-133`). It needs its own `runner_argv` branch (`schedules.py:853-888`). `installer/cli.py:56-62` builds the `--run-schedule` choices from `UPDATE_SCHEDULE_IDS`, so the choices are widened for both `check-updates` (34) and `update-all` (35) *(amended 2026-11-19, 35 D-02, in 34-CONTEXT D-02)*.
- **D-03: The row is daily** (`daily=True`, interval hidden) **starting at 03:00:** off the 00:00/06:00/12:00/18:00 update grid and before 34's 09:00 check, so the check sees the result; the once-a-day rule makes more frequent runs useless. **Own reasoning** (jev first rung low 0.59; TypeSafe none_of_these low 0.48). Ledger.
- **D-04: The view needs no new mechanism:** an undecided `update-all` has no files and renders `off` (`schedules.py:1493-1497`); `space` calls `schedules.turn_on` (`installer/schedules_screen.py:629`), recording `decided=True`; only `what` (`:458-466`) and `_target` (`:430-435`) get a branch. It is not a Policies row, but `sweep_adapters` (`schedules.py:1900-1935`) yields a `schedule:update-all` uninstall adapter (a teardown extra, `installer/compose.py:626-629`, `setup.py:493`), so the "no Policies row" test must look at the Policies view rows, not at ids starting with `schedule:`.

#### The planner
- **D-05: "Package manager" means a catalog tool named by an `Owner` value** (`installer/ownership.py:82-97`): brew (which also owns `cask`), uv, bun, pnpm, sdkman, volta; not the registry `category` (`pkg-mgr` covers only uv, brew, pnpm and volta, `registry.toml:63,164,2229,2291`; bun and sdkman are `runtime`). Managers are ordered deps-first over who owns whom: a manager installed by another manager comes after it (a brew-owned uv, bun, pnpm or volta follows brew), ties by tool id. `resolve._RANK` cannot do this: it ranks the install-method kind (`installer/resolve.py:15-31`), brew itself is a `script` method (rank 10) while a brew-owned tool's kind `brew` is rank 5, `_RANK` has no `volta` key and ranks `sdkman` after `script`. This **amends ROADMAP criterion 2 and AUTOUPD-02** ("ranked by `resolve._RANK`"); **flagged: needs confirmation**. **Own reasoning** (jev install_preference_rank low 0.51 and 0.63, rejected by the evidence). Ledger.
- **D-06: A dependent's owner is its `ToolState.ownership.owner` mapped to its manager (`cask` to brew);** groups follow the manager order; non-manager owners (`installer`) form one final group. Within a group, `deps.resolve_dependencies(selected=<group sorted by id>, catalog=<all tools>)` gives the order and its closure is filtered back to the group's members (the closure drags in `requires` from outside the group: unzip, zip, puppeteer; `installer/deps.py:40-155`). A dependent is skipped as `skipped: <manager> failed` when its owner's manager failed or any manager in its transitive `requires` failed (mmdc is pnpm-owned but `requires = ["bun","puppeteer"]`); the failure set lives in memory for the one run and is never persisted. **Own reasoning** (jev owned_and_needing low 0.58; first rung none_of_these 0.85 contradicted the evidence). Ledger.
- **D-07: Managers always run their own self-update; a dependent enters the plan only when 34's `outdated_ids(states)` lists it,** on a forced refresh with 34's `stale_after` window; tools with an unknown version are not planned. An installer-owned download update always re-downloads (`installer/download.py:437-465`) and a script without a declared `update` re-runs the vendor installer (`installer/update.py:503-505`), while manager updaters (`brew update`, `uv self update`, `bun upgrade`, `sdk selfupdate`, `pnpm self-update`) are cheap no-ops when current; filtering managers by version would skip `brew update`, whose metadata refresh lets `brew upgrade` see new formulae. Plan mode uses the cached pass without forcing a refresh, so it writes nothing, not even the version cache. **Own reasoning** (jev outdated_only low 0.32 and 0.42). Ledger.
- **D-08: The planner is a pure module** (`installer/update_all.py`): inputs are the catalog tools, `(tool, ownership)` pairs from one pass, the outdated set, the updated-today map and `platform_os`; it returns an ordered tuple of entries, each `update` or `skip <reason>`. It calls `update_refusal` (`installer/update.py:283`, zero subprocess) so the plan and a real run share the skip texts; macOS `cask` owners plan as `skipped: cask excluded`; `schedule_run.py` only dispatches to it. Planning through `version_refresh.resolve_owner` per tool would run the brew/uv/bun inventory queries about 100 times (`version_status.py:1639-1660`), so the plan takes one pass and the real run re-resolves per tool inside `UpdateService.run` (`update.py:650-660`). jev first rung none_of_these 0.98 contradicted the evidence; second opinion only_while_running low 0.65, which would break R9's plan-equals-run acceptance. **jev overridden / Own reasoning.** Ledger.
- **D-09: `update-all` skips a script tool that has no declared `update` argv** as `skipped: no unattended update path`; today that is Volta (`registry.toml:2310-2320`: `get.volta.sh` runs `volta setup`, which rewrites `~/.profile`, `~/.zshrc`, `~/.bashrc` and `~/.bash_profile`; `update.py:503-505`); AGENTS.md treats rc edits as host mutation. Volta stays in the manager order; the interactive `u` is unchanged. This amends SPEC R2 ("covers ... Volta": Volta is ordered, not updated); **flagged: needs confirmation** (the owner named volta among the managers). **Own reasoning** (jev skip_with_reason low 0.62; first rung none_of_these 0.91 contradicted the evidence). Ledger.

#### The runner
- **D-10: The runner gets an `update-all --installer CHECKOUT --uv UV` job reusing `_update("update-all", installer, uv)`** (`installer/helper_assets/schedule_runner.py:320-358`; `_parse` jobs `:437-490`). On the installer side each `update` entry calls the existing per-tool path (`_run_unlocked`'s dispatch, `schedule_run.py:120-123`), so `cursor-agent` still gets its shim refresh and `UpdateService.run` supplies the fresh ownership, refusal and pnpm replay; the lock is `run_schedule`'s (parent holds, or `try_acquire`, or `skipped: busy`); children run with `CHILD_ENV` (`HOMEBREW_NO_SUDO`) and stdin `/dev/null` (`installer/run.py:50,184-191`).
- **D-11: A per-job timeout:** `update-all` gets a longer bound than 1800 s (2 to 3 h), each per-tool command inside the child gets its own bound (`run_captured_in_group` passes `timeout=None` today), and `_WAIT_BOUND` (7200 s) and its comment are re-derived (`schedule_runner.py:51,62-69` assume every holder lives at most `_UPDATE_TIMEOUT`). **Own reasoning** (jev stop_starting_new low 0.38; first rung low 0.62). Ledger.
- **D-12: The run log is `update-all.log` next to `schedules.log`** (`ctx.log_path.with_name(...)`), written by the installer child, never the runner (the runner keeps only the child's last `ok:`/`skipped:`/`failed:` line); truncated at run start with one line appended per tool (a killed run keeps its partial lines); last run only; it joins `_state_artifacts` (`schedules.py:1803-1811`); plan mode never writes it. The shared log keeps the one summary line. **Own reasoning** (jev every_run_capped low 0.73; first rung low 0.63). Ledger.
- **D-13: The once-a-day store is `updated-today.json`** (derived from `ctx.state_path.with_name`): `{"version":1,"updated":{"<tool id>":{"date":"YYYY-MM-DD","by":"update-all"|"update-claude"}}}` with local calendar dates, written with `atomic_write_text`, read with `read_capped(..., follow_symlinks=False)`, a corrupt file reads as empty; written only while the run lock is held (every runner holds it, so the two rows cannot race); a tool is recorded when `UpdateOutcome.status == "updated"`, which includes "up to date" (`update.py:176-185`; `schedules.py:477-488`); swept on uninstall. jev dedicated_state_file 0.93 (TypeSafe).
- **D-14: The per-tool rows skip a tool only if `update-all` updated it today;** `update-all` skips a tool either runner updated today. This keeps the five rows' 6 h cadence (`schedules.py:56-65`) and satisfies R7's acceptance in both directions; a global once-a-day rule would turn `update-claude`'s 06:00, 12:00 and 18:00 runs into skips. **Own reasoning** (jev one_per_day_everywhere low 0.71; first rung low 0.47). Ledger.
- **D-15: The summary line is `ok: N updated, M skipped`** when nothing failed and `failed: K failed (<first tool>), N updated, M skipped` with exit 1 when any tool failed (`_locked_run` maps `failed:` to exit 1, `schedule_runner.py:509-527`); extra clauses follow 34 D-21; a held lock gives `skipped: busy`; an empty plan gives `ok: 0 updated`. Refused tools and tools updated today count as skipped. jev failure_line 0.78 (Laya).
- **D-16: The runner's `_run_child` gets `stdin=subprocess.DEVNULL`** (`schedule_runner.py:226-233` relies on the service manager's default today); the installer's children already use `/dev/null` (`run.py:117,338`). jev close_explicitly 0.87 (Laya).

#### Notification and plan-only mode
- **D-17: After a real run with a non-empty plan, the installer child calls 34's `Notifier` once with the counts;** a returned reason or an exception appends `; notify skipped: <reason>` and does not change the exit code; an empty run sends nothing; the notifier is injected through `RunDeps` (built by `notify.notifier_for` in `setup.py:529-544`) so tests pass a fake. Notifying from the stdlib runner would duplicate the logic where `installer` cannot be imported (`schedule_runner.py:26-29`).
- **D-18: Plan-only mode:** `cli.Options` gains `plan: bool` (`installer/cli.py:10-90`); `--plan` is valid only with `--run-schedule update-all` (any other combination is a `parser.error`); it takes no run lock, writes no log, store or notification, spawns no update and forces no refresh; it prints one line per entry in run order (`<tool> (<group>): would update` or `<tool>: skipped: <reason>`) then `ok: plan N to update, M skipped`; run-dependent skips (`<manager> failed`, `busy`) cannot appear in a plan; a manual real `--run-schedule update-all` without `--plan` is allowed while the row is off (the container e2e needs it). jev lock_free_preview_manual_run_allowed 0.80 (TypeSafe).

#### Tests and the container proof
- **D-19: Existing tests that change:** `tests/test_schedules.py:105-140` (ids, labels, targets gain `update-all`; `UPDATE_SCHEDULE_IDS` stays), `tests/test_schedules_view.py:240-248` (gains `"never"`), `tests/test_cli.py:114-125` (choices; new `--plan` cases), `tests/test_schedule_runner.py` (jobs, per-job timeout, stdin), and the `runner_argv` and unit-template tests. Unchanged: `tests/test_schedules_lifecycle.py:107,152,256,441`, `tests/test_schedules_handover.py:493`, `tests/test_container_e2e_schedules.py:174` and `tests/e2e_schedules_driver.py:49,81` (derived from `SCHEDULES`), `tests/test_schedule_update.py:180-187`. New unit tests (scratch HOME, fakes only): planner fixtures (brew + uv + two dependents, one brew-owned and one uv-tool owned; bun + sdkman + pi/mmdc/java; ties by id; a brew-owned manager after brew; empty and managers-only plans; a macOS cask), a failing fake manager with an executor spy, each refusal text, a held lock, an AST/grep test for `sudo`/`pkexec`/`doas`, the child environment and stdin, the run log versus the shared log through `schedule_runner.main([...])`, the store in both directions with a corrupt file, the notifier counts, plan equals run, and a `_row_action` truth table.
- **D-20: The container e2e is a dedicated `update-all` target** in `scripts/container-e2e-verify.sh`, modeled on `schedules --direct` (`:2627-2690`) and `cmd_bun_lifecycle` (`:2864`): no systemd, an EXIT-trap teardown that removes the container; bootstrap with `bootstrap_homebrew_and_uv` (`:332-336`); install through the installer's own code via a driver like `tests/e2e_landing_driver.py` (brew, uv, bun; one brew formula dependent; one uv-tool dependent pinned older; sdkman and java for the refusal); run `--run-schedule update-all --plan`, then the real run through `uv run --script runner.py update-all ...` so `uv self update` runs inside the real `uv run` chain; capture `uv --version` before and after and the command output into the phase verification; a static test `tests/test_container_e2e_update_all.py` pins the script's constants and verdict markers. jev first rung none_of_these 0.91 contradicted the evidence; second opinion dedicated_run_real_installs 0.89. **jev overridden.**
- **D-21: Dependencies:** phase 35 depends on phase 34 being executed (34 currently has only a CONTEXT): `installer/notify.py` (`Notifier`), `outdated_ids`, `stale_after`, `Schedule.daily`, `JobKind.CHECK_UPDATES`, `DBUS_SESSION_BUS_ADDRESS` in the runner's `_PASSED_ENV`. The SPEC's "seven existing rows" is eight once `check-updates` exists.

### Claude's Discretion
- Module and helper names, the exact plan-line wording, the per-tool command bound, and the notification text.

### Deferred Ideas (OUT OF SCOPE)
- To confirm in the container or planning: whether `uv self update` is safe while two uv processes from the same binary run (R8); whether `sdk selfupdate`, `bun upgrade` and `pnpm self-update` are non-interactive and what they exit with when current; whether `get.volta.sh` has a flag that skips the rc rewrite (only matters if Volta is later updated); whether `brew upgrade <formula>` auto-updates again after `brew update` in the same run.

*(Out of scope per SPEC: updating casks by default; merging the five per-tool rows; sudo, pkexec, doas; a Policies row; real-Mac checks.)*
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUTOUPD-01 | `update-all` row off by default, never a Policies row; installer never changes a recorded decision | `default_on` field + one `_row_action` branch (see Architecture Pattern 1); Policies view rows come from `tweaks.BUNDLES` (`installer/tweaks.py:148`), so the "no Policies row" test asserts on those, not on `schedule:` ids |
| AUTOUPD-02 | Managers first, then dependents grouped by owner, ordered by `deps.resolve_dependencies` | Pattern 2 (pure planner); `resolve_dependencies` needs the keyword-only `available` and `is_installed` callables (`installer/deps.py:40-47`), which CONTEXT D-06 omits |
| AUTOUPD-03 | A failed manager skips each dependent with one line | Pattern 3 (blocked-set propagation incl. manager-on-manager and transitive `requires`) |
| AUTOUPD-04 | Reuse `UpdateService`, `update_refusal`, closed stdin, `HOMEBREW_NO_SUDO`, run lock; no sudo path | Pattern 4; stdin is already closed in the runner (34 did D-16); AST test for `sudo`/`pkexec`/`doas` |
| AUTOUPD-05 | Casks excluded on macOS | planner branch before `update_refusal`; macOS fixture |
| AUTOUPD-06 | One run-log line per tool, one shared-log summary line | `update-all.log` written by the child; summary budget (300 chars) pitfall |
| AUTOUPD-07 | Tool updated at most once per day across both rows | `updated-today.json` (Pattern 5) with asymmetric read rule (D-14) |
| AUTOUPD-08 | Container e2e; `uv self update` verdict recorded | Container plan section; verdict cannot be asserted from research (see Open Questions) |
</phase_requirements>

## Project Constraints (from CLAUDE.md / AGENTS.md)

No `./CLAUDE.md` exists in the repo; the binding file is `AGENTS.md` plus `.claude/*.md` [VERIFIED: `AGENTS.md` read this session]. Directives the plans must honor:

- English only everywhere (identifiers, comments, log lines, commits).
- uv owns the environment; never pip/poetry/conda.
- Never bypass a gate or a hook; fix root causes. Coherent commits (amend/squash); changes reach `main` by branch push, green CI, fast-forward.
- Hooks are the gate: never run `make validate` or a single static gate by hand per commit; while working run only `uv run pytest <files> --no-cov -q` for the edited modules and the tests that import or read them (`rg -l '<file name>' tests/`); after a plan run `make validate` once and `make test` once.
- Never mutate the developer's host: no `make run/fix/doctor/uninstall/dev-setup`, no mutating `systemctl --user`; tests use a scratch HOME; real installs only in disposable containers; agents never run `make dev-setup`.
- Zero sudo: no `sudo`, `pkexec`, `doas` in any code path.
- `.claude/architecture.md` rules: one view registry, one nav path, one apply workflow (`ui_common.run_live`), **`setup.py` is wiring only** (decision functions live in `installer/`), **no orphan helpers** (every shared helper needs a production caller; vulture and `tests/test_reachability.py` enforce it).
- `.claude/testing.md`: no skip/xfail dodges, coverage floor untouched, xdist-safe tests (`tmp_path`, `monkeypatch`, no fixed paths), Textual pilots wait with `tests/screen_family.wait_until`, tests deterministic and offline, plans are `type: execute` with test-first inside one green commit, keep the RED output in the SUMMARY.
- Test sandbox: unit tests cannot launch `git` or `gh`; the host's real tools are injected as fakes. CI runs Python 3.15.2 while the local venv is 3.12.12 (`uv run --no-sync python --version` printed `Python 3.12.12`; `python3 --version` printed `Python 3.15.2`) [VERIFIED: shell this session; the CI claim is from the owner's brief], and CI runners carry tools the dev host lacks (aws, gh, node, notify-send, ...); this dev host itself carries real `brew`, `bun`, `pnpm`, `volta`, `uv`, `notify-send` on PATH [VERIFIED: `command -v`], so every test that could resolve a manager or notifier through PATH must inject fakes and isolate PATH.
- `.planning/config.json`: `security_enforcement: true`, `security_asvs_level: 1`, `security_block_on: high`, `nyquist_validation: true`, `tdd_mode: true` [VERIFIED: file read].

## Summary

Phase 34 is on the branch and exports almost everything Phase 35 needs: the `Notifier` seam (`installer/notify.py`), `outdated_ids`, per-call `stale_after` on the refresh service, `Schedule.daily`, `JobKind.CHECK_UPDATES`, `RUN_SCHEDULE_IDS`, `RunDeps(notify, refresh, git)`, the runner's `readonly` child mode (which already passes `DBUS_SESSION_BUS_ADDRESS` per job and uses `uv run --frozen`), a closed stdin in every runner child, and a contract test (`tests/test_update_check_contract.py`) that explicitly pins "the contract phase 35 inherits". The phase is therefore mostly additive: a ninth OFF-by-default row, one new job kind, one pure planner module, one executor loop in `schedule_run.py`, two small state files, `--plan`, and a dedicated container target.

Four findings change the plan and are not in CONTEXT. (1) `VersionRefreshService.refresh()` always persists the version cache and may query managers and fetch versions, so D-07/D-18's "plan mode writes nothing, not even the version cache" cannot be met through the shared service as written; (2) D-09's "script with no declared `update`" is not just Volta: eight catalog tools qualify (antigravity, codex, fnm, herdr-app, kitty, opencode, volta, xcode-clt), including `opencode`, which has its own per-tool row; (3) D-13 names `atomic_write_text`, which writes THROUGH a planted symlink (Phase 34 learned this and used `atomic_replace_entry`); (4) `brew update` runs after the pass that decides which brew dependents are outdated, so brew dependents newly outdated by that very `brew update` wait one night unless the run re-passes after the manager group (the refresh service already supports this through `invalidate`).

The per-manager safety picture: `uv self update` on Unix runs the cargo-dist installer script, which replaces the binary with `mv` (a rename), so replacing the `uv` that is running the chain is expected to be safe on Linux and macOS; the receipt's `modify_path` field decides whether the update touches shell rc files, which must be checked in the container. `pnpm self-update` rewrites a project manifest when run inside a project that pins pnpm, so the child's cwd matters (the checkout has no `package.json`, verified). `sdk selfupdate` and `bun upgrade` have no prompt in the parts of their code that could be read. Everything beyond that is `[ASSUMED]` and the container run is the arbiter.

**Primary recommendation:** Build `installer/update_all.py` as a pure planner (inputs: tools, the pass's `ToolState` map, `outdated_ids`, the updated-today map, `platform_os`; output: ordered `PlanEntry` tuple), put the executor loop, run log, store writes and notification in `installer/schedule_run.py` through the existing `_update` path refactored to take a `Tool`, reuse `readonly=True` for the runner child (it already carries the bus address and `--frozen`), give the real run the Phase 34 `CHECK_STALE_AFTER` window, and resolve the four findings above explicitly in the plan (see `## Open Questions`).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Seed the row OFF; never flip a recorded decision | Core table (`schedules.py`: `Schedule.default_on`, `_row_action`) | Engine (turn_on/off record `decided`) | One seeding line; the decision record already has three states |
| Timer registration, unit text | Core engine (`runner_argv`, `_linux_texts`, `_macos_plist`) | OS timer manager (systemd user / launchd) | Same path as every row; no new mechanism |
| Order and filter what to update | Pure planner (`installer/update_all.py`) | `deps.resolve_dependencies`, `update_refusal` | Pure so plan equals run and tests need no process |
| Execute the plan | Installer child (`schedule_run.py`) via `UpdateService` | Schedule runner (lock, log line, timeout) | The stdlib runner cannot import `installer` (`schedule_runner.py:27-29`) |
| Run lock, timeout, single result line | Stdlib runner (`helper_assets/schedule_runner.py`) | `runlock` in the child for manual runs | Runner owns the cross-process lock and the shared log |
| Per-tool run log, once-a-day store | Installer child | Uninstall sweep (`_state_artifacts`) | Child knows tools; sweep is the single deletion point |
| Notification | Installer child through `Notifier` | `notify.notifier_for` wired in `setup.py` | Runner cannot import `installer`; seam already injected via `RunDeps` |
| `--plan` output | CLI `Options` + `run_schedule` (returns multi-line text) | `setup.py` prints | `setup.py` stays wiring only |
| Container proof | `scripts/container-e2e-verify.sh` target + driver module | static pin test on the host | Orchestrator-run only; host never touched |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib (`dataclasses`, `datetime`, `json`, `enum`) | 3.12 local, 3.15.2 CI | planner, store codec, log lines | no new dependency; the repo is stdlib-first for the runner and `installer/` modules |
| `installer.update.UpdateService` / `update_refusal` | in repo (`update.py:590`, `:283`) | the one update implementation | AUTOUPD-04 forbids a second one |
| `installer.deps.resolve_dependencies` | in repo (`deps.py:40`) | dependency order within a group | AUTOUPD-02 names it |
| `installer.version_status.outdated_ids` + `VersionRefreshService.refresh` | in repo (`version_status.py:1079`, `:1845`) | the outdated set and the per-tool `ToolState.ownership` in one pass | Phase 34 contract |
| `installer.notify.Notifier` | in repo (`notify.py:19`) | one summary notification | Phase 34 seam |
| `installer.atomic.atomic_replace_entry` + `read_capped` | in repo (`atomic.py:58`, `:186`) | link-safe store and log writes/reads | what `update_check.write_notified` already does |
| pytest + pytest-xdist + Textual pilot | per `pyproject.toml` | tests | existing infrastructure |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `tests/update_check_doubles.py` (`FakeRefresher`, `FakeNotifier`, `tool_named`, `check_context`, `inert_run_deps`) | in repo | planner and executor fixtures | extend, do not duplicate; `tests/state_doubles.pass_state(tool, platform=, ownership=, version=)` builds a `ToolState` with any owner |
| `installer.update_check.oldest_checked_first`, `CHECK_STALE_AFTER` | in repo (`update_check.py:243`, `:38`) | fetch-cap fairness and the refresh window | the real run's refresh call |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| New `update_all.py` | extend `schedules.py` | `schedules.py` is already 1967 lines and imports `update`; a pure module keeps pyright/coverage focused and matches D-08 |
| `resolve._RANK` | ownership-edge depth (D-05) | `_RANK` ranks method kinds; verified it cannot order managers (see Reconciliation) |

**Installation:** none. No new package is recommended by this phase.

**Version verification:** not applicable (no external package). `uv 0.11.28` is what the dev host reports [VERIFIED: `uv --version`]; the container pins whatever `https://astral.sh/uv/install.sh` serves at run time.

## Package Legitimacy Audit

No external packages are installed or recommended by this phase, so the `gsd_run query package-legitimacy check` gate was not run (nothing to check).

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| none | — | — | — | — | — | — |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
timer (systemd user / launchd), daily 03:00, only when the user turned the row on
   |
   v
uv run --no-cache --no-project --script runner.py update-all --installer CO --uv UV --log --lock --cap-bytes
   |  runner: run lock (wait <= _WAIT_BOUND, else "skipped: busy"), append "<iso> update-all start"
   v
runner child: uv run --frozen --isolated --no-dev setup.py --run-schedule update-all --parent-holds-run-lock
   |  env = _PASSED_ENV + _CHILD_ENV(HOMEBREW_NO_SUDO=1) + DBUS_SESSION_BUS_ADDRESS(per job), stdin /dev/null,
   |  cwd = checkout, own session, killed as a group at the per-job timeout
   v
setup._run_schedule -> schedule_run.run_schedule("update-all", deps, plan=False)
   |
   +--> refresh.refresh(oldest_checked_first(tools), stale_after=CHECK_STALE_AFTER)  --> states{id: ToolState}
   |         (writes versions.json; may query brew/uv/pnpm, fetch <= 20 versions)
   +--> update_all.plan(tools, states, outdated_ids(states.values()), updated_today, platform_os)   [PURE]
   |         managers (ownership-edge order) -> dependents per manager group (deps order) -> installer group
   |         each entry: update | skip <reason>   (update_refusal, cask, no-update-argv, updated today)
   v
for entry in plan:                                         (blocked = failed managers, in memory)
   skip entry          -> one line in update-all.log
   update entry        -> _update_tool(tool, deps)  == per-tool path -> UpdateService.run(fresh owner, refusal, replay)
                          -> one line in update-all.log ; record updated-today.json on status "updated"
                          -> a failed MANAGER adds itself to `blocked`; dependents become "skipped: <mgr> failed"
   v
summary "ok: N updated, M skipped" | "failed: K failed (<first>), N updated, M skipped"  (+ "; notify skipped: <reason>")
   +--> Notifier(summary, body) once when the plan was non-empty ; reason -> clause, exit code unchanged
   v
stdout: summary line -> runner keeps the LAST ok:/skipped:/failed: line -> schedules.log (one line per schedule id)
```

`--plan` (no runner, no lock): the same `refresh` (against a scratch cache, see Open Question O2) and the same `plan(...)`, printed as `<tool> (<group>): would update` / `<tool>: skipped: <reason>` then `ok: plan N to update, M skipped`.

### Recommended Project Structure
```
installer/
├── update_all.py        # NEW pure: PlanEntry, plan(), manager order, summary_line(), store codec, run-log line
├── schedule_run.py      # + _update_tool(tool, deps) refactor, _run_update_all(), plan printing, per-tool-row store rule
├── schedules.py         # + JobKind.UPDATE_ALL, Schedule.default_on, row, runner_argv branch, RUN_SCHEDULE_IDS,
│                        #   updated_today_path()/update_all_log_path() (+ names), _state_artifacts, _row_action
├── cli.py               # + Options.plan, --plan, parser.error combinations
├── compose.py           # + optional cache_path for _build_services (plan mode's scratch cache)
├── schedules_screen.py  # + _target/_detail/_extra_lines branches, CSS max-height 10
└── helper_assets/schedule_runner.py  # + "update-all" job, _parse entry, per-job timeout, docstring, _WAIT_BOUND comment
scripts/container-e2e-verify.sh       # + usage line, cmd_update_all, dispatch
tests/ (new)  test_update_all.py  test_update_all_run.py  e2e_update_all_driver.py  test_container_e2e_update_all.py
tests/ (edit) see Validation Architecture
.claude/architecture.md               # + "## Phase 35" subsection; tests/test_docs.py gains _PHASE_35_REQUIRED
```

### Pattern 1: The per-row default (AUTOUPD-01)
**What:** one dataclass field and one branch.
**When to use:** only `update-all` sets `default_on=False`.
**Example:**
```python
# Source: installer/schedules.py:44-52 (the dataclass) and :1571-1572 (the branch to change), read this session
@dataclass(frozen=True)
class Schedule:
    id: str
    label: str
    kind: JobKind
    target: str | None
    default_interval: int
    default_start: str
    daily: bool = False  # Cadence belongs to the row, not its kind.
    default_on: bool = True  # NEW

    if record.decided is None:
        return "turn-on"          # -> return "turn-on" if schedule.default_on else "none"
```
`_reconcile_pass` already runs `_drop_gone_target` only for `JobKind.UPDATE` (`schedules.py:1714`), so a `UPDATE_ALL` row with `target=None` never enters the gone-target branch; `after_target_removed` matches `schedule.target == tool_id` (`:1746`), never true for `None`. Both verified by reading.

### Pattern 2: A pure planner over one pass (AUTOUPD-02, -05)
**What:** `plan(tools, states, outdated, updated_today, platform_os) -> tuple[PlanEntry, ...]`.
**Rules (verified against the code, see Reconciliation for the deviations from CONTEXT):**
1. `MANAGER_IDS = ("brew", "uv", "bun", "pnpm", "sdkman", "volta")`; owner-to-manager map is the identity plus `"cask" -> "brew"`. Owner literals are `"installer", "brew", "cask", "pnpm", "bun", "uv", "sdkman", "volta", "unknown", "dnf", "apt", "pacman", "rpm-ostree", "os-package"` [VERIFIED: `installer/ownership.py:82-97`].
2. A manager is planned when `states[id].present`; its entry is always `update` unless `update_refusal`/no-argv/updated-today says skip. Order: depth over the owner chain (a manager whose `ownership.owner` maps to another manager comes after it), ties by id. Guard a cycle with a visited set (an owner chain only passes through managers).
3. A dependent is any other present tool in `outdated`; its group is `MANAGER_OF.get(owner)` or the final `installer` group; `owner in {"unknown", native, "os-package"}` still plans as a refusal skip when outdated (SPEC R4 requires the refusal text to show).
4. Within a group call `resolve_dependencies(selected=sorted(group, key=id), catalog=tools, available=lambda _t: True, is_installed=lambda _t: True)` and filter `result.closure` back to the group's members. The two callables are **required keyword-only parameters** [VERIFIED: `installer/deps.py:40-47`, `def resolve_dependencies(selected, catalog, *, available, is_installed)`]; pass constants so the planner stays pure. A `DependencyCycleError` cannot occur for a registry the loader accepted; do not catch it.
5. Skip order for one tool: not an `update` candidate -> `cask excluded` (macOS only) -> `update_refusal(tool, ownership)` mapped through `schedules.update_result_line(outcome, None, None)` (the same text the per-tool row logs) -> no unattended path (`ownership.owner == "installer"` and `method.kind == "script"` and `not isinstance(method.params.get("update"), list)`) -> `updated today`.
6. Entries carry `(tool_id, group, action, reason)`; run-dependent skips are NOT produced by the planner.

### Pattern 3: Failure-skip propagation (AUTOUPD-03)
Keep `blocked: dict[str, str]` (tool id -> root failed manager) in the executor only. After each manager outcome with `status == "failed"` set `blocked[id] = id`. Before running an entry: `root = next((blocked[r] for r in transitive_requires(tool) | {owner_manager} if r in blocked), None)`; if found, log `skipped: <root> failed` and, when the skipped tool is itself a manager, set `blocked[tool.id] = root` so manager-on-manager and `pi -> bun -> brew` chains propagate with the root cause named once. A manager that is only **skipped** (refused, updated today, no argv) is not a failure. `transitive_requires` is a ten-line walk over `tool.requires` with a visited set (the registry has `mmdc -> (bun, puppeteer)`, `puppeteer -> (bun, unzip)` [VERIFIED: scan of `load_tools("installer/registry.toml")`, 94 tools]).

### Pattern 4: Reuse `_update` per tool (AUTOUPD-04)
`schedule_run._update(schedule, deps)` finds the tool by `schedule.target` and returns `(line, code)` [VERIFIED: `schedule_run.py:50-68`]. Refactor to `_update_tool(tool, deps)` and keep `_update(schedule, deps)` as a two-line wrapper. For `tool.id == "cursor-agent"` the executor must call `_update_cursor_agent` (shim refresh, `schedule_run.py:113-123`), which needs a `Schedule` only for the id: pass `schedule_by_id("update-cursor-agent")`. Cost note: `_update` resolves ownership twice and `UpdateService.run` once more (`update.py:662`), each a fresh inventory (brew/uv/bun queries); acceptable for a nightly job of tens of tools, and the per-tool rows already pay it.

### Pattern 5: The once-a-day store (AUTOUPD-07)
Path `ctx.state_path.with_name("updated-today.json")`, constant name beside `NOTIFIED_NAME` (`schedules.py:155`), accessor beside `notified_path` (`:1816`), member of `_state_artifacts` (`:1821`). Body `{"version":1,"updated":{"<id>":{"date":"YYYY-MM-DD","by":"<schedule id>"}}}`. Read with `read_capped(path, cap, follow_symlinks=False)`; any parse or type problem reads as empty. **Write with `atomic_replace_entry(path, data, mode=0o600)` after `ensure_dir(path.parent)`, not `atomic_write_text`**: `atomic_write_bytes` "resolves a symlink and replaces its TARGET" while `atomic_replace_entry` "swaps" the link for the file [VERIFIED: `installer/atomic.py:58-66` docstring]. Record per tool immediately after its outcome, not at the end of the run, so a timeout kill keeps what finished. Today comes from an injected `Callable[[], date]` on `RunDeps` (local date; never `date.today()` inside logic). Read rule: `update-all` skips any tool with `date == today`; a per-tool row (`UPDATE` kind) skips only an entry whose `by == "update-all"` and `date == today`. Both runners hold the run lock when they read and write, so there is no race.

### Pattern 6: The summary line within the runner's budget
The runner keeps the child's last result line and cuts it to 300 characters (`_MAX_REASON = 300`, `_sanitize(...)[:_MAX_REASON]`, `schedule_runner.py:103,135`), so only a TAIL can be lost. Phase 34 hit this and wrote `update_check.result_line` to share the budget among reason clauses (`update_check.py:228-240`); that function hard-codes the `ok: N updates available` prefix and is not reusable. Write `update_all.summary_line` with the fixed clauses first (`ok: N updated, M skipped`, optionally `, K unchanged`), then `; notify skipped: <reason>` last with its reason trimmed to the remaining budget; the `failed:` form puts `(<first tool>)` inside the bounded head. Use `notify.reason_line` for the reason (`notify.py:30`).

### Anti-Patterns to Avoid
- **A second update implementation or a hand-built `brew upgrade` argv.** Everything goes through `UpdateService.run`; the plan only chooses.
- **Planning per tool through `resolve_owner`** (about 94 inventory reads). Take one pass; `UpdateService.run` re-resolves per executed tool.
- **Calling `refresh` in plan mode against the real cache path** (it always persists, see O2).
- **`date.today()` or `datetime.now()` in logic or in tests** (midnight flakes); inject the clock.
- **Writing the store or log through `atomic_write_text`/`open(..., "a")`** (symlink write-through).
- **Putting executor or print logic in `setup.py`** (architecture rule 4); `_run_schedule` only forwards `options.plan`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dependency order | a topological sort | `deps.resolve_dependencies` (filter closure to the group) | already cycle-checked, deps-first |
| Refusal texts | new strings | `update_refusal` + `schedules.update_result_line` | plan and run share the text; SPEC R4 compares exact strings |
| Run lock | a new lock | `runlock.try_acquire` (child) / the runner's `_run_lock` | cross-process, holder line already parsed by the view |
| Notification | a subprocess call | injected `Notifier` | argv-only, bounded 10 s, fixed failure reasons (`notify.py:21,71-77`) |
| Outdated set | a second comparison | `outdated_ids(states)` and `oldest_checked_first` | Phase 34 contract; `outdated_ids` docstring says "Phase 35 reuses this contract" |
| Link-safe file IO | `open`/`atomic_write_text` | `read_capped(follow_symlinks=False)` + `atomic_replace_entry` | planted-link safety |
| Log-line sanitizing | regex | `sanitize_log_line` / `notify.reason_line` | already strips ANSI/controls |

**Key insight:** the phase's risk is not new mechanism but composition: every dangerous behavior (root escalation, prompts, stdin, locking, refusal) already has one owner in the repo; the planner must route to them and prove (by test) that nothing else spawns.

## Runtime State Inventory

Not a rename/refactor/migration phase (greenfield row); omitted. One note for the planner: the phase adds two new on-disk state files (`updated-today.json`, `update-all.log`) and one row state record (`schedules.json`), all swept by `_state_artifacts`/`sweep_adapters`; nothing existing is renamed.

## Common Pitfalls

### Pitfall 1: Plan mode cannot be read-only through the shared refresh service
**What goes wrong:** `--plan` calls `VersionRefreshService.refresh`, which queries managers when the snapshot is older than 6 h and always ends in `save_pass()` writing `versions.json` (`version_status.py:2085-2103`; `MANAGER_STALE_AFTER = timedelta(hours=6)`, `version_cache.py:48`). The plan "changes nothing" claim (SPEC R9, D-07, D-18) is then false by one cache write.
**How to avoid:** O2 below. Recommended: build the plan-mode service with a scratch `cache_path` (add an optional `cache_path` to `compose._build_services`, `compose.py:402-410`, seed it by copying the real `versions.json` bytes when present, remove it in a `try/finally` inside a `tempfile.TemporaryDirectory`), and pass a huge `stale_after` so no new network fetch is forced for entries that exist.
**Warning signs:** a test that snapshots `~/.local/state/tools-installer/` before/after `--plan` fails.

### Pitfall 2: brew dependents are decided before `brew update` runs
**What goes wrong:** the outdated set comes from `brew outdated` as of the pass; `brew update` (the brew manager's own update, `registry.toml` brew `update = ["brew", "update"]`) refreshes formula metadata AFTER the pass, so a formula newly outdated by that update is missing from the plan and waits a night. Phase 34's own architecture note says "Brew-owned tools reflect brew's local index because the check never runs `brew update`" [VERIFIED: `.claude/architecture.md` Phase 34 subsection].
**Why it matters:** `UpdateService.run` already calls `invalidate(reason=...)` after every `updated` or `failed` outcome (`update.py:734-746`), and the next `refresh()` re-queries managers (`_managers_invalid`, `version_status.py:1748`), so a second pass after the manager group is cheap and correct.
**How to avoid:** O1. Recommended: two stages in the executor (managers from pass 1, then `refresh` again and `plan_dependents` from pass 2), keeping the planner pure by exposing `plan_managers(...)` and `plan_dependents(...)`; `--plan` prints the managers and the dependents known now with a note line that dependents are re-evaluated after the managers run. If the owner rejects it, document the one-night lag in the architecture subsection.

### Pitfall 3: D-09 as written skips eight tools, not one
A script method without a declared `update` is not rare: `antigravity, codex, fnm, herdr-app, kitty, opencode, volta, xcode-clt` [VERIFIED: scan of `installer/registry.toml` via `load_tools`, 2026-11-22]. `opencode` has a per-tool row (`update-opencode`) whose whole job is re-running the vendor installer (`update.py:512-516`), so under D-09 the unattended nightly `update-all` would skip it while the per-tool row updates it, and every outdated one of the eight would produce a skip line nightly. The registry comment is specific to Volta: "get.volta.sh runs `volta setup` (line 228) ... rewrites ~/.profile, ~/.zshenv or ~/.zshrc, ~/.bashrc and ~/.bash_profile" [VERIFIED: `installer/registry.toml` volta comment, "Verified 2026-11-08"]. Whether the other seven re-runs touch rc files was NOT verified. Recommendation: keep D-09's rule (it is the only rule the planner can compute without new registry data), but state in the plan that the skip text names exactly this set, add a fixture for `opencode`, and raise O4 for the owner (add a registry flag, or accept).

### Pitfall 4: Notification noise from persistent skips
SPEC R10 notifies "after an update-all run that updated or skipped anything". Refusal skips (sdkman's `java`/`gradle`, no-update-argv tools) recur every night while the tool stays outdated, so a skipped-only night would notify nightly. O3 asks the owner; recommended: notify only when `updated + failed > 0` and put the skipped count in the body.

### Pitfall 5: The runner's per-job child options are not parameters yet
`_update(run_id, installer, uv, *, what="update", readonly=False)` hard-codes `timeout=_UPDATE_TIMEOUT` (1800 s) and bundles `--frozen`, `PYTHONDONTWRITEBYTECODE` and `DBUS_SESSION_BUS_ADDRESS` under `readonly` [VERIFIED: `schedule_runner.py:323-358`]. Add a `timeout` parameter (a new constant such as `_UPDATE_ALL_TIMEOUT`, 3 h) and call `_update(run_id, installer, uv, what="update-all", readonly=True, timeout=...)`: `readonly=True` is right for a job that must not write into the checkout (lockfile, bytecode) and it is also the only thing that currently forwards the bus address the notification needs. Do NOT add the bus variable to `_PASSED_ENV`: `tests/test_update_check_contract.py:77` asserts `"DBUS_SESSION_BUS_ADDRESS" not in vars(schedule_runner)["_PASSED_ENV"]` and `:97-104` pins `_PASSED_ENV` to the unit keys plus `LANG`.

### Pitfall 6: `_WAIT_BOUND` and its comment assume a 30-minute holder
The constant and comment (`schedule_runner.py:69-74`) derive the 2 h wait from "a holder lives at most `_UPDATE_TIMEOUT` plus the kill grace (about 30 min)". With a 3 h `update-all` holder, a per-tool row that starts at 06:00 behind a 03:00 run still going will log `skipped: busy` after 2 h. That is acceptable (update-all covers the tool), but the comment is then false and must be re-derived; keep 7200 and say so. The reverse case (update-all waiting for the 00:00 grid's queue, at most six jobs of at most 30 min) fits inside 2 h.

### Pitfall 7: `pnpm self-update` is cwd-sensitive
pnpm's docs: inside a project that pins pnpm (`packageManager`, `devEngines.packageManager`) the command updates the manifest pin; "non-interactive runs fail" if the target is younger than `minimumReleaseAge`; Homebrew/Corepack-managed installs fail outside a pinned project [CITED: https://pnpm.io/cli/self-update, fetched 2026-11-22]. The runner child's cwd is the checkout (`schedule_runner.py:345` `cwd=Path(installer)`), which has no `package.json` or `pnpm-workspace.yaml` [VERIFIED: `ls` this session]. A failing `pnpm self-update` is a manager failure and skips pnpm's dependents (`mmdc`, `puppeteer`) by design.

### Pitfall 8: `uv self update` and shell rc files
`uv self update` reads `modify_path` from the install receipt "defaulting to true if the field is missing" and re-runs the installer with `UV_NO_MODIFY_PATH=1` only when it is false [CITED: https://docs.rs/crate/uv/latest/source/src/commands/self_update.rs, fetched 2026-11-22]. The registry installs uv with `env = { UV_NO_MODIFY_PATH = "1" }` [VERIFIED: `installer/registry.toml` uv method], so installer-owned uv has `modify_path: false`; a uv installed earlier by hand (and the container's `bootstrap_uv`, `curl ... | sh` without that variable, `container-e2e-verify.sh:431-438`) may not. In the disposable container this is harmless and the verdict file should record whether rc files changed; on a real host it is the same "rc edit" class D-09 refuses for Volta. Raise it as O5.

### Pitfall 9: The container's uv has no installer receipt
`bootstrap_uv` installs uv outside the installer, and `landing_bootstrap` needs it to run anything. `engine.install_tool` short-circuits an installed tool, so a driver cannot "install uv through the installer's own code" in that container. Ownership of that uv may resolve as `installer` by elimination or as `unknown` (refused). The e2e must assert the `--plan` line for uv says `would update`; if it says skipped, the run cannot test `uv self update` and the verdict must say so rather than pass.

### Pitfall 10: Test and host leakage
This dev host has real `brew`, `bun`, `pnpm`, `volta`, `uv`, `notify-send` on PATH and CI runners add `aws`, `gh`, `node`. Planner tests use `pass_state` fixtures (no PATH); executor tests inject `runner`, `resolve_owner`, `probe_version`, `notify` and a clock; a test that goes through `schedule_runner.main([...])` must set a scratch `PATH`, `HOME` and clear `DBUS_SESSION_BUS_ADDRESS`/`XDG_RUNTIME_DIR`. Unit tests cannot launch `git` or `gh`; `update-all` needs neither.

## Code Examples

### The runner job entry (what changes in `_parse` and `_locked_run`)
```python
# Source: installer/helper_assets/schedule_runner.py:472-477 and :530-537, read this session
required = {
    "tmp-cleanup": ("--script",),
    "cache-cleanup": (),
    "update": ("--installer", "--uv"),
    "check-updates": ("--installer", "--uv"),
    # NEW: "update-all": ("--installer", "--uv"),
}.get(job)
...
"check-updates": lambda: _update(
    run_id, options["--installer"], options["--uv"], what="update check", readonly=True
),
# NEW: "update-all": lambda: _update(run_id, options["--installer"], options["--uv"],
#          what="update-all", readonly=True, timeout=_UPDATE_ALL_TIMEOUT),
```
`wanted = 2 if job == "update" else 1` and `run_id = job` already give `update-all` the run id `update-all`; the contract test `test_every_schedule_row_has_a_runner_job_with_its_own_id` (`tests/test_update_check_contract.py:36-44`) parses `argv[6:]` of every row, so the new `runner_argv` branch must keep the six-element `uv run --no-cache --no-project --script <runner>` prefix.

### `runner_argv` branch
```python
# Source: installer/schedules.py:873-874 (the CHECK_UPDATES branch to mirror)
elif schedule.kind is JobKind.CHECK_UPDATES:
    job = ["check-updates", "--installer", str(ctx.checkout), "--uv", str(uv)]
# NEW: elif schedule.kind is JobKind.UPDATE_ALL:
#          job = ["update-all", "--installer", str(ctx.checkout), "--uv", str(uv)]
```

### The row and the closed id tuples
```python
# Source: installer/schedules.py:97-106
Schedule("check-updates", "update check", JobKind.CHECK_UPDATES, None, 24, "09:00", daily=True),
...
RUN_SCHEDULE_IDS: Final[tuple[str, ...]] = (
    *UPDATE_SCHEDULE_IDS,
    *(schedule.id for schedule in SCHEDULES if schedule.kind is JobKind.CHECK_UPDATES),
)
# NEW row: Schedule("update-all", "update all", JobKind.UPDATE_ALL, None, 24, "03:00", daily=True, default_on=False)
# NEW: widen the second generator to kind in (CHECK_UPDATES, UPDATE_ALL)
```

### Dispatch gate
```python
# Source: installer/schedule_run.py:134-150
def _run_unlocked(schedule, deps): ...   # add the UPDATE_ALL branch first
if schedule.kind not in (schedules.JobKind.UPDATE, schedules.JobKind.CHECK_UPDATES):
    return f"failed: {schedule_id} is not an update schedule", 2   # add UPDATE_ALL here too
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| CONTEXT: DBUS variable in runner `_PASSED_ENV` (D-21) | per-job `extra_env` only in the `readonly` child; `_PASSED_ENV` pinned to unit keys + `LANG` | Phase 34 | update-all must use `readonly=True` (or its own extra_env), not `_PASSED_ENV` |
| CONTEXT: runner `_run_child` needs `stdin=DEVNULL` (D-16) | already `stdin=subprocess.DEVNULL` with a comment, test `test_every_runner_child_gets_a_closed_stdin` | Phase 34 | D-16 is done; add no work, keep the test |
| CONTEXT: `--run-schedule` choices from `UPDATE_SCHEDULE_IDS` (D-02) | `schedules.RUN_SCHEDULE_IDS` (update ids + check row) | Phase 34 | widen that tuple |
| 34-RESEARCH: nothing is written into the checkout | `uv run --frozen` + `PYTHONDONTWRITEBYTECODE=1` for `readonly` children | Phase 34 | reuse for update-all |

**Deprecated/outdated:** CONTEXT's file:line citations (all shifted; see Reconciliation) and its claim that 34 "currently has only a CONTEXT".

## CONTEXT Reconciliation

What 34 actually exports (all [VERIFIED: files read this session]): `installer/notify.py` (`Notifier = Callable[[str, str], str | None]`, `no_notifier`, `notifier_for(platform_os, which, run, *, environ, uid, is_socket)`, `reason_line`, `NOTIFY_TIMEOUT = 10`, `BUS_VARIABLE`); `installer/update_check.py` (`Refresher` protocol with `cache_path`, `warning`, `refresh(tools, *, stale_after, on_failure)`, `state_of`; `CHECK_STALE_AFTER = timedelta(hours=20)`; `oldest_checked_first`; `run_check`; `result_line`; `RESULT_LIMIT = 300`; `GitRunner`; `git_for_check`); `version_status.outdated_ids(states: Iterable[ToolState | None]) -> frozenset[str]` (docstring: "Phase 35 reuses this contract"); `VersionRefreshService.refresh(..., *, stale_after, on_failure)` returning `(states, cache, snapshot) | None`; `Schedule.daily`; `JobKind.CHECK_UPDATES`; `RUN_SCHEDULE_IDS`; `schedules.NOTIFIED_NAME`/`notified_path`; `RunDeps(tools, updates, resolve_owner, probe_version, context, notify=no_notifier, refresh=None, git=None)`; the runner's `readonly` child; `tests/update_check_doubles.py`; `tests/test_update_check_contract.py`.

| # | CONTEXT says | Code now | Plan should |
|---|--------------|----------|-------------|
| R1 | D-01 `_row_action` at `schedules.py:1548-1562`; `record_for` `:236-241`; `_reconcile_pass` `:1692-1712`; `ensure_schedule_defaults` `:1715-1721`; `_RECORD_KEYS` `:258` | `_row_action` `:1561-1575` (the `decided is None` line is `:1571-1572`); `record_for` `:247-252`; `_reconcile_pass` `:1704-1725`; `ensure_schedule_defaults` `:1728-1734`; `_RECORD_KEYS` `:269` [VERIFIED: Read] | cite the new lines; logic unchanged. `_RECORD_KEYS = frozenset({"decided", "interval", "start", "files"})` still closed, no schema change |
| R2 | D-02 `_require_available` `:710-714`; `row_state` `:1488-1492`; gone-target drop `:1701-1704`; `UPDATE_SCHEDULE_IDS` `:94-96`; kind gate `schedule_run.py:131-133`; `runner_argv` `:853-888`; `cli.py:56-62` builds choices from `UPDATE_SCHEDULE_IDS` | `_require_available` `:721-725`; `row_state` `:1488-1510`; gone-target `:1714-1717`; `UPDATE_SCHEDULE_IDS` `:99-101`; gate `schedule_run.py:149-150`; `runner_argv` `:864-901`; `cli.py:56-62` uses `list(schedules.RUN_SCHEDULE_IDS)` [VERIFIED] | the premise (UPDATE assumes a target) still holds, so a new kind is still right; widen `RUN_SCHEDULE_IDS`, not `UPDATE_SCHEDULE_IDS` |
| R3 | D-03 daily at 03:00, off the update grid | grid is 00:00/06:00/12:00/18:00 for 6 h rows (`_DEFAULT_START = "00:00"`, `_DEFAULT_INTERVAL = 6`); `check-updates` is 09:00 daily [VERIFIED `schedules.py:55-57,97`] | 03:00 still collides with neither. Note `update-all` 03:00 lands 3 h after the 00:00 grid, whose queue can hold the lock ~3 h (6 jobs x up to 30 min): the runner waits up to `_WAIT_BOUND` (2 h) so a 03:00 start is safe |
| R4 | D-04 `schedules.py:1493-1497`, `schedules_screen.py:629`, `what` `:458-466`, `_target` `:430-435`, `sweep_adapters` `:1900-1935`, `compose.py:626-629`, `setup.py:493` | undecided row renders `off` via `row_state` `:1507-1509`; `turn_on` call in `_change_worker` `schedules_screen.py:646-655`; `_detail` `what` chain `:475-485`; `_target` `:445-452`; `sweep_adapters` `:1954-1967`; teardown extras in `setup.py:492-496`; `compose.py` has `_schedule_context` `:516-526`, no `:626-629` teardown block | cite new lines. Also needed: `_extra_lines` `:532-564`, `_detail` CHECK-specific branches `:494-498`. "No Policies row": Policies rows are `tweaks.BUNDLES` (`tweaks.py:148`) [VERIFIED by grep]; assert there |
| R5 | D-05 `ownership.py:82-97`, `resolve.py:15-31` `_RANK`, `registry.toml:63,164,2229,2291` | unchanged lines for `Owner` (`:82-97`) and `_RANK` (`resolve.py:15-31`); the file is `installer/registry.toml` (not repo root); manager ids `uv` (63), `brew` (164), `pnpm` (2230), `volta` (2292) [VERIFIED]. `_RANK` quote: `"brew": 5, "cask": 5, "bun": 6, "node": 7, "script": 10, ... "uv-tool": 20, "sdkman": 20,` and no `volta` | D-05 claim confirmed; ownership-edge order stands |
| R6 | D-06 `resolve_dependencies(selected=..., catalog=...)` `deps.py:40-155` | signature is `resolve_dependencies(selected, catalog, *, available, is_installed)`; both callables required [VERIFIED `deps.py:40-47`] | planner passes `available=lambda _t: True`, `is_installed=lambda _t: True`; add to the plan text |
| R7 | D-07 `download.py:437-465`, `update.py:503-505` | `update_download` `download.py:447`; script-without-update re-run `update.py:512-516` | cite new lines. **Conflict-ish:** "Plan mode ... writes nothing, not even the version cache" cannot hold through `refresh()` (O2) |
| R8 | D-08 `version_status.py:1639-1660`, `update.py:650-660`, `update.py:283`, `update.py:580` | `resolve_owner` `version_status.py:1693-1714`; `UpdateService.run` `update.py:660-749` (fresh re-resolve `:662`); `update_refusal` `:283` unchanged; `UpdateService` class `:590` | the refresh pass already yields `ToolState.ownership` for all tools (`_pass`, `version_status.py:1944-2050`), so the planner needs no `(tool, ownership)` pairs built separately: take `states` as returned by `refresh` |
| R9 | D-09 "today that is Volta" `registry.toml:2310-2320` | eight script tools lack `update` (Pitfall 3); volta comment is in `installer/registry.toml` near `:2300-2320`; a second volta method is `brew` (so brew-installed volta updates through `brew upgrade volta`) [VERIFIED] | **flag O4**; keep the rule, document the set, test `opencode` |
| R10 | D-10 `schedule_runner.py:320-358`, `_parse` `:437-490`, `schedule_run.py:120-123`, `run.py:50,184-191` | `_update` `:323-376`; `_parse` `:450-493`; dispatch `schedule_run.py:134-139`; `CHILD_ENV` `run.py:50`; `run_captured_in_group` `run.py:222-231` [VERIFIED] | reuse as D-10 says, with `readonly=True` + a `timeout` parameter |
| R11 | D-11 `_WAIT_BOUND` `:51,62-69` | `_UPDATE_TIMEOUT = 1800` `:52`; `_WAIT_BOUND = 7200` `:74` with comment `:69-73` | add `_UPDATE_ALL_TIMEOUT`; re-derive the comment (Pitfall 6); tests patch constants with `monkeypatch.setitem(vars(schedule_runner), ...)` (existing pattern, `tests/test_schedule_runner.py:706,735`) |
| R12 | D-12 `_state_artifacts` `schedules.py:1803-1811` | `:1821-1830`, already holds `notified_path(ctx)` | add the two new paths; `update-all.log` lives beside `ctx.log_path` on both OSes |
| R13 | D-13 `atomic_write_text`; `update.py:176-185`; `schedules.py:477-488` | `atomic_write_bytes` resolves a symlink and replaces its TARGET; `atomic_replace_entry` replaces the entry [VERIFIED `atomic.py:36-66`]; `UpdateOutcome` at `update.py:175-185`; `update_result_line` at `schedules.py:488-508` | **flag O6/divergence:** use `atomic_replace_entry`, as `update_check.write_notified` does |
| R14 | D-15 `_locked_run` maps `failed:` to exit 1 `:509-527` | `_locked_run` `:522-545` (`return 1 if result.startswith("failed:") else 0`) | unchanged behavior; budget is 300 chars (Pitfall 6 of the summary pattern) |
| R15 | D-16 add `stdin=DEVNULL` to `_run_child` (`:226-233`) | already present: `stdin=subprocess.DEVNULL,` with the comment `# A scheduled child never reads a terminal.` (`:231-232`), test `test_every_runner_child_gets_a_closed_stdin` (`tests/test_schedule_runner.py:1212`) | **no work**; keep the test green; D-16 is satisfied by Phase 34 |
| R16 | D-17 `notifier_for` in `setup.py:529-544` | `setup.py:531-549`, `notify=notifier_for(platform.os)`, plus `refresh=version_refresh`, `git=git_for_check`; `_build_services` lives in `installer/compose.py:402` | `RunDeps` already carries `notify`, `refresh`; add only a clock and (for plan mode) nothing else |
| R17 | D-18 `cli.py:10-90` | `Options` `:9-19`, `parse_args` `:22-90` | add `plan: bool = False`, `--plan`, and the `parser.error` combinations; add `--plan` to the flag set asserted at `tests/test_cli.py:~100-112` |
| R18 | D-19 `tests/test_schedules.py:105-140` | `:105-107` is `test_exactly_two_rows_are_daily` (asserts `{"tmp-cleanup", "check-updates"}`) and **will break** when `update-all` is `daily=True`; table test `:138-178`; `tests/test_schedules_view.py:240-248` is `:241-250`; `tests/test_cli.py:114-125` is `:115-128` (it asserts `(*UPDATE_SCHEDULE_IDS, "check-updates") == RUN_SCHEDULE_IDS` at `:121`) | add these to the edit list; also `tests/test_update_check_contract.py:47-57` (choices) and `tests/test_layout_80x20.py:326-335`, `tests/test_schedules_view.py:679` (table height) |
| R19 | D-19 "Unchanged: `test_schedules_lifecycle.py:107,152,256,441`, `handover.py:493`" | `test_schedules_lifecycle.py:108` and `:154` assert `turned_on == (...)`, `test_schedules_handover.py:496` asserts `ensure.turned_on == ("tmp-cleanup", "cache-cleanup", "update-claude", "check-updates")` [VERIFIED grep]; an OFF row is not in `turned_on` | confirmed unchanged; `tests/test_schedules_lifecycle.py:556-559` lists `schedule:*` ids for the sweep (an off row has no footprint, so no entry) |
| R20 | D-20 `container-e2e-verify.sh` `:2627-2690`, `:2864`, `:332-336` | `schedules_direct` `:2848-2893`; `cmd_bun_lifecycle` `:3103-3135`; `bootstrap_homebrew_and_uv` `:449-453`; usage line `:121`; dispatch `:3453` | model on `cmd_bun_lifecycle` (landing_* helpers `:2953-3058`, `landing_bootstrap` `:3019`); a usage-text edit shifts the classified PATH lines (see Container section) |
| R21 | D-21 "34 currently has only a CONTEXT"; "DBUS_SESSION_BUS_ADDRESS in the runner's `_PASSED_ENV`" | 34 is executed and merged on this branch (`77af2bc2`); the bus variable is deliberately **not** in `_PASSED_ENV` (per-job in the `readonly` child; asserted by `tests/test_update_check_contract.py:77`) | dependency satisfied; use `readonly=True` for update-all's child |
| R22 | SPEC "eight rows once check-updates exists" | `SCHEDULES` has 8 rows (tmp, cache, 5 updates, check) [VERIFIED]; `update-all` is the ninth; table `max-height: 9` (`schedules_screen.py:256`) holds header + 8 | raise to 10, update `tests/test_layout_80x20.py:331-334` (table rows `range(4, 13)` -> `range(4, 14)`, detail `range(13, 18)` -> `range(14, 18)`) and `tests/test_schedules_view.py:679` (`== 9` -> `== 10`; `detail.region.height == 3` -> `2`). The detail panel loses one row at 80x20: write the `update-all` detail text most-important-line-first |

**Locked-decision conflicts (none overridden; all flagged for the owner/planner):** C1 = O2 (D-07/D-18 "writes nothing" vs `refresh()` persistence); C2 = O4 (D-09 scope: eight tools); C3 = D-13 writer choice (`atomic_write_text` writes through a planted symlink; use `atomic_replace_entry`). Provisional decisions (own reasoning / needs confirmation) D-03, D-05, D-06, D-07, D-08, D-09, D-11, D-12, D-14 were researched, not overridden; D-05's ownership-edge order is **confirmed correct** against `_RANK`.

## Safety facts per manager (the unverified item and what `--plan` must show)

All five managers run through `UpdateService` with children that have `/dev/null` stdin, `HOMEBREW_NO_SUDO=1`, `HOMEBREW_NO_AUTOREMOVE=1` (`run.py:50`) and no `SUDO_ASKPASS` (`apply_child_env`, `run.py:55-58`, called from `setup.py:661` under `__main__`; in-process test imports of `setup.main` do not run it, which is why `tests/test_schedule_runner.py:450-455` pins the runner's own `_CHILD_ENV`).

| Manager | Command the installer runs (verified in registry) | Prompt / root / self-replace risk | Evidence |
|---------|---------------------------------------------------|-----------------------------------|----------|
| brew | `brew update` (script `update`), dependents `brew upgrade <formula>` (`update.py:204`) | `HOMEBREW_NO_SUDO` disables sudo; `brew upgrade` auto-updates first unless `HOMEBREW_NO_AUTO_UPDATE` (throttled by `HOMEBREW_AUTO_UPDATE_SECS`, default 86400) and runs `brew cleanup` on upgraded formulae unless `HOMEBREW_NO_INSTALL_CLEANUP` [CITED: https://docs.brew.sh/Manpage, 2026-11-22]. So `brew upgrade <formula>` right after `brew update` does NOT update again (answers the deferred question, [CITED] not executed) |
| uv | `uv self update` run as the declared leaf `~/.local/bin/uv` (`update.py:541-555` `_declared_leaf`) | Receipt required; package-manager copy errors with "Self-update is only available for uv binaries installed via the standalone installation scripts"; offline refuses; "already up to date" is success; no locking against other uv processes in the file. The installer script replaces with `mv` ("`ensure mv "$_install_temp/$_bin_name" "$_install_dir"`", never `cp`), no prompt, no sudo [CITED: docs.rs uv `self_update.rs` and https://releases.astral.sh/installers/uv/latest/uv-installer.sh via WebFetch summaries, 2026-11-22; installer quotes are the fetch tool's summary, not a byte-for-byte read]. A rename leaves the running binaries' inodes alive on Linux and macOS, so the chain `uv run (runner) -> uv run (setup.py) -> uv self update` is expected safe; **not executed here**: the container run must record it |
| bun | `bun upgrade` (script `update`) | docs page confirms the command exists and Homebrew users should use `brew upgrade bun`; prompts, exit code when current and replace mechanism are NOT stated [CITED: https://bun.com/docs/installation, 2026-11-22]; `[ASSUMED]` non-interactive. A brew-owned bun is updated by `brew upgrade bun` instead |
| pnpm | `pnpm self-update` (script `update`), preceded by `managed_packages()` snapshot and followed by the replay (`update.py:688-722`) | cwd/manifest pin and `minimumReleaseAge` non-interactive failure (Pitfall 7) [CITED] |
| sdkman | `sdk selfupdate` through `executors.sdk_pipeline` = `bash -c '. "$HOME/.sdkman/bin/sdkman-init.sh" && sdk selfupdate'` (`executors.py:680-687`) | the CLI's `__sdk_selfupdate` has no `read`; offline returns 1; "No update available at this time." leaves status 0; the update branch pipes a remote script into `bash` whose prompts could not be read [CITED: https://raw.githubusercontent.com/sdkman/sdkman-cli/master/src/main/bash/sdkman-selfupdate.sh, WebFetch summary 2026-11-22]; the registry notes `sdkman_auto_answer=true` only for installer-bootstrapped SDKMAN (`executors.py:690-701` comment) so a brownfield SDKMAN may prompt; `[ASSUMED]` no prompt on a bootstrapped one. Its dependents (`java`, `gradle`, ...) are refused by `update_refusal` (`_SDKMAN_DETAIL`) so only skip lines appear |
| volta | not updated (D-09): script method has no `update`; a brew-installed volta updates through `brew upgrade volta` | `volta setup` rewrites rc files (registry comment) |

**What `--plan` must show:** one line per entry in run order with the group, the same skip text a real run would log, and the final `ok: plan N to update, M skipped`; for managers also the argv-free fact "would update (self-update)". It must not claim a result for run-dependent outcomes (`<manager> failed`, `busy`).

## Container check (AUTOUPD-08) and what it can prove

**Shape (D-20, adjusted to the code as it is):** a new verb `update-all [--keep-image]` whose function `cmd_update_all` copies `cmd_bun_lifecycle` (`container-e2e-verify.sh:3103-3135`): own container name `tools-installer-e2e-update-all-$$`, `LANDING_DRIVER_MODULE=tests.e2e_update_all_driver`, `PHASE_DIR="$REPO_ROOT/.e2e-artifacts/container-update-all"`, `trap landing_teardown EXIT`, `landing_bootstrap` (start, marker, prereqs, tester, workspace, `bootstrap_homebrew`, `bootstrap_uv`, path, sync), then `landing_step <name> <driver verb>` per phase. The runner copy and the argv come from the existing helpers `schedules_install_assets` (`:2838-2846`) and `schedules_driver argv update-all` (`e2e_schedules_driver.py` prints `runner_argv`; it accepts any id in `SCHEDULES`, so it works for the new row with no edit).

**Steps (each prints a `TRACER_UPDATE_ALL_<STEP>_OK|_FAILED` marker, matching the landing verdict grammar that `landing_step` greps with `_(FAILED|UNPROVEN)( |$)`):**
1. install fixtures with the installer's own code where the engine allows (bun and one brew formula or uv-tool dependent pinned older; sdkman + java for the refusal). uv and brew are bootstrap-installed (Pitfall 9).
2. `--run-schedule update-all --plan` through `uv run --isolated --no-dev setup.py`: assert the order (brew, uv, bun, sdkman before dependents), the uv line says `would update`, the java line says SDKMAN owns it, and the state directory is byte-identical before and after (a `find`/`sha256sum` snapshot): this is the proof for R9 and for O2.
3. record `uv --version`, run the real chain `uv run --no-cache --no-project --script ~/.local/share/tools-installer/schedules/runner.py update-all --installer <ws> --uv <uv> --log ... --lock ... --cap-bytes ...`, record exit code, the shared-log line, `update-all.log`, `updated-today.json`, `uv --version` after, whether `~/.bashrc`/`~/.profile`/`~/.zshrc` changed (compare digests: the uv receipt's `modify_path`), and the uv receipt content.
4. a second real run the same day: assert the tools are `skipped: updated today`.
5. teardown verdict line `TRACER_LANDING_TEARDOWN_OK` is produced by `landing_teardown` (`:2975-2994`).

**What it can prove:** the real `uv run` chain with a real `uv self update` on Linux in a Fedora container, brew and bun update commands against real upstreams, the file contents and the no-write plan, the once-a-day rule. **What it cannot prove:** macOS (`bash 3.2`, launchd, cask exclusion on a real Mac: owner UAT), a real desktop notification, systemd unit behavior (the `--direct` style has no units), a running-binary replace on macOS. Orchestrator-run only; the container and image created are removed by exact name.

**Static pin test** `tests/test_container_e2e_update_all.py`: copy the structure of `tests/test_container_e2e_bun.py` (constants read by regex `^NAME=(\S+)`, `_function(name)` extraction, stubbed `ct`); pin the container-name pattern, the driver module, the verdict markers, the teardown trap, and that the script contains no `sudo`. **Lessons of phases 29 to 34 to apply** (from `34-VALIDATION.md` "Constraints on every new test"): any usage-text change moves the classified PATH line numbers in `tests/test_shell_scripts_path.py` (classified lines today: `container-e2e-verify.sh` 460, 583, 638, 905, `:511-541`), so the same commit that adds the usage line near `:121` must renumber those four; a module added in a plan needs a production import in that plan or the next (`tests/test_reachability.py`); no timing assertions (inject clocks; no `sleep`); xdist-safe fixtures; holds on Python 3.12 and 3.15; macOS bash 3.2 (no apostrophes or unbalanced quotes inside a heredoc inside `$(...)`, no associative arrays); the strict reachability guard; host-state guards and runner-image tools on PATH (isolate PATH).

## Golden files, docs-only, TEST_READ, LEDGER, architecture text

- **Golden files:** none exist for schedules; text assertions are in-test literals (`34-RESEARCH.md` checklist, confirmed: there is no `tests/golden*` directory). The unit-text tests that iterate `SCHEDULES` adapt automatically; the explicit `IDS` tuples listed in Reconciliation R18/R22 do not.
- **docs-only classifier:** `devtools/docs_only.py` treats `.planning/*` and `*.md` as docs-only unless the path matches `TEST_READ` (`AGENTS.md`, `README.md`, `.claude/*`, `.github/*`, `docs/*`, `scripts/*`, `tests/*`, two `.planning` skill-judge globs) [VERIFIED: `devtools/docs_only.py:20-36`]. A `.claude/architecture.md` or `docs/TROUBLESHOOTING.md` edit therefore triggers the full CI run; `.planning/*` edits do not.
- **LEDGER:** `tests/test_docs_only.py` `LEDGER` must classify every string literal ending in `.md` or starting with `.planning` found in any other test (per `34-RESEARCH.md`; the file exists, the `LEDGER` rule was not re-read this session, `[ASSUMED]`: re-check before adding any `.md` literal to a new test).
- **Architecture rules text:** add `## Phase 35: opt-in auto-update` after the Phase 34 subsection (`.claude/architecture.md:1255`), and a `_PHASE_35_REQUIRED` tuple + test in `tests/test_docs.py` next to `_PHASE_34_REQUIRED` (`:243`). Required phrases to pin: `update-all`, `default_on`, `JobKind.UPDATE_ALL`, `installer/update_all.py`, `updated-today.json`, `update-all.log`, `ownership edges`, `no unattended update path`, `skipped: updated today`, `HOMEBREW_NO_SUDO`, the one-night brew lag or the two-stage run (O1), and the container-only verification rule. 24.2 amendment: already recorded at `24.2-SPEC.md` (R3 text "*(amended 2026-11-19, 35 D-01: a row may declare a per-row default; `update-all` seeds off; the recorded-decision rule is unchanged)*") [VERIFIED: Read]; nothing further to amend in 24.x, and no test reads the 24.2 files. README has no Schedules section (`rg -i "schedul|update-all"` finds only unrelated lines at README `:254`, `:351`); an optional README/TROUBLESHOOTING note would be test-read.
- **Uninstall sweep:** `_state_artifacts` (`schedules.py:1821-1830`) is the one list; adding `updated_today_path(ctx)` and `update_all_log_path(ctx)` makes `_state_leftovers` (`:1833`) and `_cleanup_if_last` (`:1856`) delete them; the lock files stay by design. `sweep_adapters` yields `schedule:update-all` only when the row has a unit footprint (`_footprint`, `:1839`); an off row yields none, so `tests/test_schedules_lifecycle.py:556-559` (which lists four `schedule:*` ids) stays valid.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `uv self update` replacing `~/.local/bin/uv` while two uv processes from the same file run is safe on Linux (rename semantics) | Safety facts, Summary | If it fails, the chain breaks nightly; container run decides, the plan must treat the uv result as a recorded finding, not an assumption |
| A2 | `bun upgrade` is non-interactive, exits 0 when current, and replaces the binary safely | Safety facts | A prompt would hang until the per-tool bound; bound + closed stdin make it a failure, not a hang |
| A3 | `sdk selfupdate` has no prompt on an installer-bootstrapped SDKMAN (`sdkman_auto_answer=true`) | Safety facts | prompt -> closed stdin -> failure -> java et al. skipped (they are refused anyway) |
| A4 | The other seven no-`update` script tools (antigravity, codex, fnm, herdr-app, kitty, opencode, xcode-clt) would or would not rewrite rc files when their installers are re-run | Pitfall 3 | affects only whether D-09's blanket rule is too broad; owner decision O4 |
| A5 | Ownership of the container's bootstrap-installed uv resolves to a mutation-grade owner | Pitfall 9 | the e2e could skip uv and prove nothing; step 2's `would update` assertion catches it |
| A6 | `tests/test_docs_only.py` `LEDGER` still requires classification of `.md` string literals in new tests | Golden/docs | an unclassified literal fails a test at the push gate |
| A7 | A brew-installed `volta`/`uv`/`bun`/`pnpm` update through `brew upgrade <formula>` in the manager group is correct (owner branch in `resolve_update_argv`) | Pattern 2 | wrong order if brew-owned managers are not placed after brew (covered by the ownership-edge rule and fixtures) |
| A8 | Notifying when only skips occurred (SPEC R10 wording) is what the owner wants | Pitfall 4 | nightly noise; O3 |
| A9 | `brew upgrade <formula>` after `brew update` in the same run does not auto-update again (24 h throttle) | Safety facts | negligible; doc-cited, not executed |
| A10 | Counting `ok: up to date` outcomes as "updated" in `ok: N updated` is acceptable | Open Questions O7 | misleading nightly counts |

## Open Questions

1. **O1 - Second pass after the manager group (brew-dependent lag).**
   - What we know: the outdated set predates `brew update`; `UpdateService.run` invalidates the epoch and manager snapshot after each outcome, so a second `refresh()` is cheap and fresh.
   - What's unclear: D-08 says one pass and "plan equals run"; a two-stage run makes the real run plan dependents later than `--plan` can show.
   - Recommendation: two stages (`plan_managers`, then re-refresh and `plan_dependents`), `--plan` prints managers plus the dependents known now and one note line. Needs the planner/owner decision; if rejected, document the one-night lag. **Unresolved, owner/planner.**
2. **O2 - Plan mode writes nothing (D-07, D-18, SPEC R9).**
   - What we know: `refresh()` always persists the version cache and may query managers (`version_status.py:2085-2103`, `:1748`).
   - Recommendation: scratch `cache_path` (optional parameter on `compose._build_services`) seeded from the real cache and removed in `finally`; or amend the wording to "no update-all log, store or notification; the version cache is a cache, written as `check-updates` writes it". **Unresolved, owner** (two ways to satisfy the same acceptance; the first keeps the text, the second changes it).
3. **O3 - Notify on skips only?** SPEC R10 wording versus nightly noise (Pitfall 4). Recommendation: notify only when `updated + failed > 0`, skips in the body. **Unresolved, owner.**
4. **O4 - D-09 breadth.** Eight tools hit the rule, `opencode` included. Recommendation: keep the rule, document the set, add an `opencode` fixture; consider a registry flag later. **Unresolved, owner.**
5. **O5 - `uv self update` and rc edits on a uv without `modify_path:false`.** Recommendation: the container records the rc digests; the planner adds no code, but the architecture subsection states the receipt condition. **Unresolved until the container run.**
6. **O6 - Store writer (D-13).** `atomic_write_text` writes through a planted symlink; use `atomic_replace_entry`. **(RESOLVED)** by the evidence (`atomic.py:58-66`, `update_check.write_notified`); no owner input needed, but the planner must carry it so the executor does not follow D-13's literal text.
7. **O7 - What counts as "updated" in the summary.** D-15 gives `ok: N updated, M skipped`; `update_result_line` returns `ok: up to date` for a no-op that still has `status == "updated"`. Recommendation: N counts outcomes whose version moved or is unknown, plus an extra `, K unchanged` clause (allowed by "extra clauses follow 34 D-21"); the store still records unchanged tools. **Unresolved, planner** (wording choice within D-15's discretion).
8. **O8 - `--plan` with `--parent-holds-run-lock`.** D-18 says any other combination is a parser error. Recommendation: reject it too (the flag is meaningless without a real run). **(RESOLVED)** by D-18's own rule.
9. **O9 - Refresh failure in a real run.** `run_check` returns `failed: refresh failed` on `CommandError/OSError` and treats a `None` return (a joined in-flight pass) as empty. Recommendation: fail closed, `failed: refresh failed`, update nothing, exit 1. **(RESOLVED)** by consistency with `update_check.run_check` (`:274-281`).
10. **O10 - The per-tool bound.** Discretion: recommend 1200 s per command (the runner's `_MANAGER_TIMEOUT`) via `functools.partial(run_captured_in_group, timeout=...)` as the `UpdateService` runner for this job only; `run_bounded` still lets short queries pass their own bound (`run.py:229-243`). A killed job at the 3 h bound is `failed: the update-all timed out` and keeps the per-tool lines and store entries written so far. **(RESOLVED)** as a recommendation within Claude's discretion.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| podman | container e2e (orchestrator only) | yes | `/usr/bin/podman` | docker is missing; `scripts/detect-container-runtime.sh` picks a live-proven tool |
| uv | all tests, container bootstrap | yes (host) | 0.11.28 | none needed |
| Python 3.12 local / 3.15.2 CI | tests | yes | 3.12.12 venv; `python3` 3.15.2 | run version-dependent tests under both |
| brew, bun, pnpm, volta, notify-send | host only | present on this dev host | n/a | tests must NOT touch them: inject fakes, isolate PATH |
| sdk (SDKMAN) | e2e sdkman fixture | no (host) | n/a | installed in the container by the driver |
| network (astral.sh, GitHub, Homebrew, npm) | container e2e | not probed (no real update allowed in research) | n/a | an environmental failure ends the run with exit 2 (`landing_environmental`, `:2961`) for the orchestrator to rerun |

**Missing dependencies with no fallback:** none for planning; the real-Mac checks stay owner UAT (out of scope).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-xdist (+ coverage) via `make test`; Textual pilot for the view |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]`; `tests/conftest.py` (xdist worker budget) |
| Quick run command | `uv run pytest tests/test_update_all.py tests/test_update_all_run.py tests/test_schedules.py tests/test_schedule_runner.py tests/test_cli.py tests/test_update_check_contract.py --no-cov -q` |
| Full suite command | `make test` (once per plan, after `make validate`) |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUTOUPD-01 | row seeds OFF; `_row_action` truth table over (default_on, decided); recorded on/off survives re-seed; no Policies row | unit | `uv run pytest tests/test_schedules.py tests/test_schedules_lifecycle.py tests/test_schedules_handover.py --no-cov -q` | partially; new cases in existing files (`test_exactly_two_rows_are_daily` at `test_schedules.py:105` must change) |
| AUTOUPD-02 | managers first (ownership edges), dependents grouped by owner, ties by id, brew-owned manager after brew, empty/managers-only | unit (pure) | `uv run pytest tests/test_update_all.py --no-cov -q` | no, Wave 0 |
| AUTOUPD-03 | failing fake manager: one `skipped: <mgr> failed` per dependent, zero executor calls; manager-on-manager and `requires` chains | unit with executor spy | `uv run pytest tests/test_update_all_run.py -k failed --no-cov -q` | no, Wave 0 |
| AUTOUPD-04 | each refusal text exactly (native, SDKMAN, Volta, pin, os-package); held lock -> `skipped: busy`; AST test no `sudo`/`pkexec`/`doas`; child env `HOMEBREW_NO_SUDO=1` and stdin `/dev/null` | unit | `uv run pytest tests/test_update_all_run.py tests/test_schedule_runner.py tests/test_schedule_update.py --no-cov -q` | stdin test exists (`test_schedule_runner.py:1212`); rest Wave 0 |
| AUTOUPD-05 | macOS fixture: formula planned, cask `skipped: cask excluded` | unit (pure) | `uv run pytest tests/test_update_all.py -k cask --no-cov -q` | no, Wave 0 |
| AUTOUPD-06 | three tools -> three lines in `update-all.log`, exactly one `update-all` line in `schedules.log` via `schedule_runner.main([...])`; summary within 300 chars | unit/hermetic | `uv run pytest tests/test_update_all_run.py -k log --no-cov -q` | no, Wave 0 (model on `tests/test_update_check_job.py`, `tests/update_check_child.py`) |
| AUTOUPD-07 | both directions, next-day, corrupt/symlinked/oversized file, per-tool row skip only for `by == "update-all"` | unit with injected clock | `uv run pytest tests/test_update_all.py tests/test_update_all_run.py -k today --no-cov -q` | no, Wave 0 |
| AUTOUPD-08 | static pin of the target + verdict markers; the real container run is orchestrator-only | unit (static) + manual | `uv run pytest tests/test_container_e2e_update_all.py --no-cov -q` ; `scripts/container-e2e-verify.sh update-all` (orchestrator) | no, Wave 0 |
| R9 (spec) | plan equals run order/skips on one fixture; zero executor calls; no files written in plan mode | unit | `uv run pytest tests/test_update_all_run.py -k plan --no-cov -q` | no, Wave 0 |
| R10 (spec) | one notification with counts; none for an empty run; notifier failure -> `; notify skipped: <reason>`, exit 0 | unit with `FakeNotifier` | `uv run pytest tests/test_update_all_run.py -k notif --no-cov -q` | `FakeNotifier` exists in `tests/update_check_doubles.py:177` |
| CLI | `--plan` valid only with `--run-schedule update-all`; flag set at `tests/test_cli.py` | unit | `uv run pytest tests/test_cli.py --no-cov -q` | edit existing |
| View | ninth row, `never` cell, table height 10, 80x20 layout, detail text | Textual pilot | `uv run pytest tests/test_schedules_view.py tests/test_layout_80x20.py --no-cov -q` | edit existing |
| Docs | Phase 35 phrases pinned | unit | `uv run pytest tests/test_docs.py --no-cov -q` | edit existing |

### Sampling Rate
- **Per task commit:** the targeted pytest of the files edited (the commit hook runs the six static gates; never `make validate` per commit).
- **Per wave merge:** the quick-run command above plus `tests/test_reachability.py` once `installer/update_all.py` gets its production import.
- **Phase gate:** `make validate` once, `make test` once on the final tree, then the orchestrator-run container target before `/gsd-verify-work`; the container verdict (or "not run" with the reason, never a pass) goes into VERIFICATION.

### Wave 0 Gaps
- [ ] `tests/test_update_all.py` - planner (pure) fixtures via `tests/state_doubles.pass_state` with explicit `ownership`
- [ ] `tests/test_update_all_run.py` - executor, log, store, notifier, plan-equals-run, lock, AST no-sudo test
- [ ] `tests/e2e_update_all_driver.py` and `tests/test_container_e2e_update_all.py`
- [ ] extend `tests/update_check_doubles.py` only if a shared helper is needed (a fake `UpdateService` spy with a per-tool outcome map)
- [ ] edits to existing files: `tests/test_schedules.py` (`:105-107`, `:138-178`), `tests/test_schedules_view.py` (`:241-250`, `:679-681`), `tests/test_layout_80x20.py` (`:331-334`), `tests/test_cli.py` (`:96-128`, the flag set at `:101-112`), `tests/test_schedule_runner.py` (job table, per-job timeout, `_parse`), `tests/test_update_check_contract.py` (`:47-57`), `tests/test_docs.py`, `tests/test_shell_scripts_path.py` (renumber `:517-540` if the usage text grows)
- Framework install: none.

## Security Domain

### Applicable ASVS Categories (level 1)

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | no credentials; GitHub token variables never reach a unit or runner child (Phase 34 rule, inherited) |
| V3 Session Management | no | n/a |
| V4 Access Control | yes | zero sudo/pkexec/doas (AST test), `HOMEBREW_NO_SUDO=1`, refusal of native/os-package owners via `update_refusal`, opt-in default OFF |
| V5 Input Validation | yes | tool ids come only from the catalog (`TOOL_ID_RE`), argv lists only (no shell), `sanitize_log_line`/`reason_line` on every logged or notified text, store file parsed strictly |
| V6 Cryptography | no | none hand-rolled; vendor checksums stay in the existing install/update path |
| V12 Files | yes | `read_capped(follow_symlinks=False)`, `atomic_replace_entry` (replaces a planted link), `0o600`, caps on read size, no write through symlinks |
| V14 Configuration | yes | closed schedule table, closed state schema, no new unit environment keys |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Planted symlink at `updated-today.json` / `update-all.log` redirects a write | Tampering | `atomic_replace_entry`; log append with `O_NOFOLLOW` (the runner's `_append_locked` pattern, `schedule_runner.py:170-189`) or replace-the-entry truncation; `read_capped(..., follow_symlinks=False)` |
| Unattended nightly run of vendor installers and updaters (supply-chain trust escalated from interactive `u` to unattended) | Tampering / Elevation | opt-in only (OFF default), refusal predicate shared with `u`, no-update-argv skip, `--plan` preview, closed stdin, per-tool and per-job bounds |
| Privilege escalation inside a child (brew casks need sudo; vendor script `sudo`) | Elevation | casks excluded on macOS, `HOMEBREW_NO_SUDO`, no `SUDO_ASKPASS`; NOPASSWD sudo inside a vendor script remains a documented residual (`run.py:45-49` comment) |
| Log/notification injection from tool output | Spoofing / Tampering | notify only counts and registry ids (`notify.py:1-6` docstring); sanitize every line |
| Stale-lock or overlapping runs corrupting state | Tampering | the run lock (wait <= `_WAIT_BOUND`, then `skipped: busy`), store written only under it |
| Rc-file rewrite by `uv self update` / vendor installers | Tampering | treated as host mutation in e2e (container only), flagged O5; Volta skipped |
| Corrupted state files used to bypass the once-a-day rule or crash the run | DoS | corrupt reads as empty, strict schema, size cap |

## Sources

### Primary (HIGH confidence)
- In-repo files read this session (cited by path:line above): `installer/schedules.py`, `schedule_run.py`, `helper_assets/schedule_runner.py`, `notify.py`, `update_check.py`, `update.py`, `ownership.py` (Owner literal), `resolve.py`, `deps.py`, `run.py`, `runlock.py`, `atomic.py`, `version_status.py` (`outdated_ids`, `refresh`, `_pass`, `resolve_owner`), `cli.py`, `compose.py`, `setup.py`, `schedules_screen.py`, `installer/registry.toml`, `scripts/container-e2e-verify.sh`, `tests/test_update_check_contract.py`, `tests/update_check_doubles.py`, `tests/update_check_child.py`, `tests/test_schedules*.py`, `tests/test_layout_80x20.py`, `tests/test_shell_scripts_path.py`, `.claude/architecture.md` (Phase 34 subsection), `.claude/testing.md`, `devtools/docs_only.py`, `.planning/phases/34-*/34-VALIDATION.md` and `34-RESEARCH.md`, `35-SPEC.md`, `35-CONTEXT.md`.

### Secondary (MEDIUM confidence)
- https://docs.brew.sh/Manpage (`HOMEBREW_AUTO_UPDATE_SECS`, `HOMEBREW_NO_AUTO_UPDATE`, `HOMEBREW_NO_SUDO`, `HOMEBREW_NO_INSTALL_CLEANUP`, `upgrade` cleanup sentence), fetched 2026-11-22.
- https://docs.rs/crate/uv/latest/source/src/commands/self_update.rs (uv `self update` flow, receipt, error text, offline), fetched 2026-11-22 (WebFetch summary).
- https://releases.astral.sh/installers/uv/latest/uv-installer.sh (`mv` into place, no prompt/sudo, `UV_NO_MODIFY_PATH`), fetched 2026-11-22 (WebFetch summary; reached via the 301 from `https://astral.sh/uv/install.sh`).
- https://pnpm.io/cli/self-update (pin/manifest behavior, `minimumReleaseAge` non-interactive failure), fetched 2026-11-22.
- https://raw.githubusercontent.com/sdkman/sdkman-cli/master/src/main/bash/sdkman-selfupdate.sh (no `read`, offline returns 1), fetched 2026-11-22 (WebFetch summary).
- https://bun.com/docs/installation (existence of `bun upgrade`, brew advice only), fetched 2026-11-22.

### Tertiary (LOW confidence)
- None used for a recommendation. The research-plan and research-store seams were not used; sources were fetched directly with WebFetch/WebSearch and nothing was cached.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new dependency; every reused symbol was read.
- Architecture: HIGH - the touch list is derived from reading every enumerating site and the Phase 34 diff (`c2555d78`) as precedent.
- Pitfalls: MEDIUM-HIGH - code-derived pitfalls are HIGH; the manager runtime behaviors are doc-derived and settled only by the container run.

**Research date:** 2026-11-22
**Valid until:** 2026-12-06 (the vendor installers and docs move; the in-repo facts hold until the next schedules or runner edit)
