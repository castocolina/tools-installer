# Phase 17: Stop the bleeding - Research

**Researched:** 2026-10-14
**Domain:** Python/Textual installer hardening (file safety, atomic writes, honest failure, runtime safety), POSIX shell portability (bash 3.2), GitHub Actions + branch protection
**Confidence:** HIGH for code facts and reuse (read this session), MEDIUM for the macOS-only CI items (no macOS host; verified through CI logs and a bash 3.2.57 container)

## User Constraints (from CONTEXT.md)

<user_constraints>
### Locked Decisions
Decision rule (user, 2026-10-13): when options compete, choose the best design (correct, one source of truth, no duplicated reads or parsing). Do not choose the smallest diff. Test churn is not a reason to choose the weaker option.

- **D-01:** Each of the three linking sites (`installer/download.py:189-190` `_install_unverified`, `:403-404` `_place_verified`, and `installer/apps.py:100`) checks `is_file()` on the member before linking. A non-file member raises `ExecutorError` and links nothing. The shelled `chmod +x` and `ln -sf` are replaced with `os.chmod` and `installer/atomic.py:117` `replace_symlink`.
- **D-02:** Sublime's registry `member` (`installer/registry.toml:2270,2278`) is corrected to the binary inside the archive dir (`sublime_text/sublime_text`), and gets a `verified` date (as a `# Verified` comment until Phase 18 introduces the `verified` key).
- **D-03:** graphify (R2) is decided empirically during execution. An isolated-HOME probe runs in a disposable podman container (scratch HOME and scratch cwd). If the cwd stays empty, the hook uses the global per-host form and also pins `cwd=` to a scratch dir as a second safeguard. If anything lands in the cwd, the `postinstall` key is removed from graphify's `[[tool]]` entry. The probe result is recorded in the plan summary.
- **D-04:** The removal proof (R3) is one predicate in `installer/uninstall.py`, used by both `classify_tools` (TUI) and the `setup.py` `--yes` path. A tool is removable only when `bin_dir/<bin>` is a symlink that resolves to a regular file inside that same tool's `opt_dir(<bin>)`. Every other match is listed as "remove it yourself" with its path: raw single-file binaries, uv/pip files, shared files, and app-kind bundles. `tests/test_uninstall.py` fixtures that relied on the name match (`test_classify_removable_when_artifacts_on_disk` at :338-350, and the app-bundle tests at :184-276) are rewritten to the strict shape. Phase 19 receipts later restore app-kind removability.
- **D-05:** Every direct `write_text` on rc files and shims becomes `installer/atomic.py` `atomic_write_text` (writes through a symlink to its target). Call sites: `installer/guards.py:388,392,425,448,472,554,564` and `installer/tweaks.py:254,297,308`. Shim scripts pass `mode=0o755`.
- **D-06:** `installer/app.py` `clean_rc_duplicates` (:418-448) keeps the previewed bytes. At confirm it re-reads the file and refuses, unchanged, if the bytes differ (a trailing newline counts). If they match, it applies the indices computed from the previewed bytes and writes atomically.
- **D-07:** The worker in `installer/execute_screen.py` `_execute_worker` (:593-656) gets an `except Exception` ahead of its `finally`. Rows already done stay done, the rest become "not attempted", and the run is marked crashed.
- **D-08:** New fields on `installer/session.py` `Summary` (:106-113), same shape as the existing outcome fields: `not_attempted: tuple[str, ...]`, `update_failed: tuple[str, ...]`, `crash_error: str | None`. `wizard_app.py` `on_install_run_finished` (:2924-2974) folds the worker's `error`, `not_attempted` and `update_errors` into them. `setup.py:1275` and `:1509` exit 1 when `failed`, `mismatched`, `dependency_failed`, `not_attempted` or `update_failed` is non-empty, or when `crash_error` is set. The headless path uses the same check. An all-skipped run exits 0. Rejected: `crashed: bool` with opaque `update_errors`.
- **D-09:** New `move_link_mode(policies, new_mode, set_link_mode)` in `installer/policy.py`. It filters to active policies using `installer/uninstall.py` `active_policies` (:401-444), removes them in the old mode, sets the mode, then applies them in the new mode. If an apply fails, it restores that policy's old block. It returns a per-policy report. `wizard_app.py` `_link_mode_picked` (:2179-2194) calls it through `run_live`, with the screen's own policy list. With no active policies, it only saves the mode.
- **D-10:** `installer/run.py` `StreamingRunner.popen_with_env` (:232-240) adds `start_new_session=True` (`stdin=DEVNULL` is already there). codex's registry method gets `env = { CODEX_NON_INTERACTIVE = "1" }` via the existing `_env_prefix`. Acceptance: a fake `/dev/tty` reader exits non-zero within 5 s.
- **D-11:** `load_settings` reads and parses once and returns a typed result (for example `LoadedSettings(settings, warning)`). It catches `UnicodeDecodeError` and `json.JSONDecodeError`. The store keeps an "invalid on disk" flag so it never writes defaults over the bad file until the user changes a setting. All callers and `tests/test_settings.py` are updated. The first screen shows the warning in its status. Rejected: a separate `settings_warning(path)` probe.
- **D-12:** `_build_app` (`setup.py:755`) builds `ExecuteInputs` itself through `_execute_inputs` (:1166-1211) from its own `tools`, `platform`, `link_mode` and disk-pressure probe, plus a new `unattended: bool` keyword. The optional `execute: ExecuteInputs | None = None` parameter is removed. `_run_interactive_wizard` (:1234-1239) stops building it. The ~20 tests that call `_build_app([], platform)` keep working. Tests that injected a fake `execute` now inject at the `_execute_inputs` seam. `test_accepting_the_catalog_without_execute_still_exits_with_ids` is deleted. Enter with nothing selected shows a message and runs nothing.
- **D-13:** Doctor (`installer/doctor.py`) gets a generic scan of every symlink in `bin_dir()`. A dangling link or a link to a directory is one finding. Repair text derived from `opt_dir(name)`: remove the opt dir, then reinstall `<name>` from the catalog. Nothing is executed; the scan does not depend on the registry.
- **D-14:** In `scripts/prune-tmp-linux.sh:101`, `mapfile -t files < <(...)` becomes a `while IFS= read -r` loop (bash 3.2).
- **D-15:** On ubuntu `/usr/bin/sh` is dash and `time . file` never sources. The `time-shells0` test keeps `sh` and asserts what each shell really does: bash and zsh source it, dash does not. The classifier still refuses `time .` in all three. Dropping `sh` is rejected.
- **D-16:** Console-width tests in `tests/test_app.py` force an explicit console width. The `test_version_status` race test uses a `threading.Barrier` / `Event` instead of timing. `test_setup::test_interactive_wizard_shares_one_cache…` and `test_catalog_tui::test_owner_cell_semantic_value…` get their root cause fixed. Neither is skipped.
- **D-17:** Branch protection (R12) is applied with `gh api` only after the final commit's CI is green and the user confirms in the moment. Both jobs required, `enforce_admins=false`.
- **D-18:** The R13 re-audit appends entries for plans 16-17..16-19 to `16-SECURITY.md` and `16-VALIDATION.md` under `.planning/milestones/v0.49.0-phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/`.

### Claude's Discretion
- Plan and wave split. Sensible order: CI repairs first (later commits judged by a green baseline), then H1/H3/H4 file-safety, then failure, tty, settings and routes, then Doctor, governance last.
- Exact shape and name of the typed settings result, and of the `Summary` fields.
- Wording of the "remove it yourself" and Doctor repair text, within the zero-sudo rule.

### Deferred Ideas (OUT OF SCOPE)
- `2026-09-16-detect-dangling-pnpm-global-bin-shims-in-doctor` is Phase 21 (UI-07). D-13's generic scan may surface a dangling pnpm shim, but pnpm-specific reasons belong to 21.
- Out of phase: receipts and removal plans (19/22), registry data fixes other than Sublime's `member` (18), exit codes from plan outcomes (20), native handoff instead of sudo (22), real-host UAT (24).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SAFE-01 | Link targets are files | Sites, test churn and the Sublime layout in "Link safety" below |
| SAFE-02 | graphify never writes into CWD | Probe result: the global form is NOT cwd-clean for opencode/cursor (Open Question 1) |
| SAFE-03 | Only proven artifacts removed | One predicate; `plan_uninstall` has 4 callers, 2 must stay lenient |
| SAFE-04 | Atomic rc and shim writes | `atomic_write_text` reuse; byte-compare pitfall (`read_text` translates newlines) |
| SAFE-05 | Failure is reported | Worker accumulators, `UpdateOutcome.status == "failed"` gap, fold helper |
| SAFE-06 | Link-mode change carries active policies | Which policies are mode-dependent; `active_policies` cannot filter a list |
| SAFE-07 | No terminal prompt hangs the TUI | Updates run through `run_output`, not `StreamingRunner` (gap in D-10) |
| SAFE-08 | Bad settings never crash launch | Only ONE `load_settings` call site; `_settings_store` has the 6 callers |
| SAFE-09 | Execute on every route | Four `_build_app` routes (the 4th is inline in `main`, not `_run_guard`) |
| CI-01 | CI green on both OSes | Real failure list differs from SPEC (owner_cell fails on ubuntu; bash 3.2 has TWO prune bugs plus GNU-only `find`) |
| CI-02 | main requires CI check | Exact `gh api` body and the required context names |
| CI-03 | Phase 16 gap plans re-audited | Doc-only; plans 16-17..19 each carry a `<threat_model>` |
</phase_requirements>

## Summary

Every Phase 17 change is a hardening of code that already exists; no new package is needed. The reusable parts are all in place: `installer/atomic.py` (`atomic_write_text` :56, `replace_symlink` :117), `installer/ui_common.py::run_live` (:42), `installer/uninstall.py` (`policy_owned` :387, `active_policies` :401, `sweep_policies` :496), the registry `env = {…}` + `executors._env_prefix` (:335) mechanism, `guidance.py`/`render.py` Doctor plumbing, and the catalog's existing empty-selection message (`catalog_tui.py:1040-1042`, already "Select at least one tool, or press q to quit."). The plan can be mostly edits plus test rewrites; the largest new code is `move_link_mode`, the strict removal predicate, the `Summary` fold, and the Doctor link scan.

Research found **eight facts that differ from, or are missing in, the CONTEXT/SPEC text**. The planner must account for them (each is detailed below, with evidence): (1) the graphify global form still writes into the cwd for opencode and cursor; (2) the update path runs through `run_output`/`run_captured`, which has NO `stdin=DEVNULL` and NO new session, so D-10 as written does not cover updates; (3) the macOS prune failure is two bash-3.2 bugs plus a GNU-only `find -regextype`, not just `mapfile`; (4) `test_owner_cell…` fails on **ubuntu** too and is the intermittent race (a race with the mount-time refresh worker); (5) `test_interactive_wizard_shares_one_cache…` fails on macOS because the daemon policy is gated on the real host's `systemctl`; (6) `_link_mode_picked`'s policy list is `Policy.active` snapshots and `active_policies` cannot filter an existing list, and moving the daemon/omz policies on a mode change is hazardous and pointless; (7) `Summary.update_failed` must also fold `UpdateOutcome.status == "failed"`, not only raised errors; (8) `plan_uninstall` ignores `bin_name`, so Sublime (`subl`) can never be matched by a strict predicate unless that is fixed.

**Primary recommendation:** Work in the CONTEXT order (CI first). Put the new strict predicate beside, not inside, `plan_uninstall` (ownership code needs the lenient evidence list). Fold `Summary` once in a pure `session.py` function that both `ExecuteScreen` and `wizard_app` call. Put the tty hardening in `run_output` as well as `StreamingRunner`. Ask the user to confirm the mixed graphify probe outcome before removing the hook.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Link/member checks, atomic link replace | `installer/download.py`, `installer/apps.py` (core) | `installer/atomic.py` | Decision logic lives in core (`.claude/architecture.md` rule 4) |
| Removal proof predicate | `installer/uninstall.py` | `setup.py` (wiring only) | One predicate for `classify_tools` and `run_uninstall` |
| rc/shim atomic writes, cleanup recheck | `installer/guards.py`, `installer/tweaks.py`, `installer/app.py` | `installer/atomic.py` | Writers already share `atomic_write_text` elsewhere |
| Failure fold and exit code | `installer/session.py` (pure) | `execute_screen.py`, `wizard_app.py`, `setup.py` | Single pure function; `setup.py` only reads it |
| Link-mode move | `installer/policy.py` | `wizard_app.py` via `run_live` | Rule 3: screens supply closures, core mutates |
| Child process isolation | `installer/run.py` | registry `env` for codex | One module owns subprocess |
| Settings load/warn | `installer/settings.py` | `wizard_app.py` (status), `setup.py` (store build) | Parse once, in core |
| Route wiring | `setup.py` `_build_app` | — | Rule 4 wiring-only; closes the F2 bug class |
| Doctor link scan + text | `installer/doctor.py`, `installer/guidance.py` | `render.py`, `wizard_app.py` DoctorScreen | Pure guidance shared by console and TUI |
| CI/portability | `scripts/`, `tests/`, `.github/workflows/ci.yml` | GitHub branch protection (user action) | — |

## Standard Stack

No new libraries. Stack in use (read from the repo this session): Python >=3.11 (`pyproject.toml:5`; local 3.12.12), uv 0.11.28, pytest + pytest-xdist + coverage (`fail_under = 90`, `pyproject.toml:58`), ruff, pyright (excludes `setup.py`), bandit, vulture, shellcheck (through `uv run`), Textual, Rich. [VERIFIED: Makefile:42-63, pyproject.toml]

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Stdlib `os.chmod` + `atomic.replace_symlink` | Keep shelled `chmod`/`ln` | Shelled `ln -sf` onto an existing link-to-dir writes through it (the H1 hazard); rejected by D-01 |
| `find ... \| grep -E` for the prune regex | `find -regextype` (GNU) / `find -E` (BSD) switch | Name pre-filter + `grep -E` is identical on GNU, BSD and busybox; no flavour detection |

**Installation:** none (no `pyproject.toml` or lock change).

## Package Legitimacy Audit

Not applicable: this phase installs no external package. `uv.lock` and `pyproject.toml` must show no diff at phase end. The graphify probe installs `graphifyy==0.9.54` **inside a disposable podman container only** (pip, throwaway image); nothing is added to the project. **Packages removed due to SLOP:** none. **Packages flagged SUS:** none.

## Architecture Patterns

### System Architecture Diagram

```
 install/update request
   |
   +-- TUI: ExecuteScreen._execute_worker (thread)
   |      |-- run_installs -> install_tool -> executors/download/apps -> Runner
   |      |       Runner = StreamingRunner (install)  [popen_with_env: +start_new_session]
   |      |       Runner = run_captured -> run_output (update)  [GAP: add stdin/session here]
   |      |-- _run_updates -> UpdateService.run -> run_captured
   |      |-- wire_path / verify
   |      +-- finally: post InstallRunFinished(summary, outcomes, not_attempted, error, update_*)
   |             |
   |             +-> ExecuteScreen.on_install_run_finished -> fold(...) -> status "Failed"(error)|"Done."(ok)
   |             +-> UnifiedApp.on_install_run_finished  -> fold(...) -> install_summary (accumulates)
   |                        |
   |                        +-> setup.py: exit 1 if Summary.has_failure else 0   [also headless run_wizard]
   |
 download member -> extract -> member.is_file()? --no--> ExecutorError (ladder falls through, nothing linked)
                                        |yes
                                        +-> os.chmod -> atomic.replace_symlink(link, binary)

 uninstall (TUI classify_tools | CLI run_uninstall --yes)
   plan_uninstall(tools)  [lenient: evidence, still used by ownership/version_status/setup]
        +-> strict predicate: bin/<bin> is symlink -> regular file inside opt_dir(<bin>)?
              yes -> removable [link, opt dir]      no -> "remove it yourself" list (never deleted)

 Policies screen link-mode picker
   -> run_live(move_link_mode(active link-mode-dependent policies, new_mode, settings.set_link_mode))
        remove(old) -> set mode -> apply(new) ; per-policy failure -> restore old block, report

 Doctor: doctor_data -> DoctorReport(+broken_links from scan of bin_dir()) -> doctor_guidance -> render / DoctorScreen
```

### Recommended Project Structure
No new modules. Additions: `session.py` (fold + `Summary` fields), `uninstall.py` (strict plan function), `policy.py` (`move_link_mode`), `settings.py` (`LoadedSettings`), `doctor.py` (link scan), `guidance.py` (finding text), `render.py` (one "remove it yourself" printer). Optional: a tiny test-support helper in `tests/` that builds a runner which materializes the member file (see Pitfall 1).

### Pattern 1: Link only a verified regular file
**What:** after extraction, `binary = opt / member`; `if not binary.is_file(): raise ExecutorError(...)`; `binary.chmod(0o755)` (same mode the update path already uses, `download.py:288,307`); `replace_symlink(link, str(binary))`.
**Reuse:** `atomic.replace_symlink` (`atomic.py:117`, already imported at `download.py:16` and `apps.py:24`). `engine.install_tool` already catches `ExecutorError` and falls through the ladder (`engine.py:137-150`), so no engine change.
**When:** all three sites in D-01. **Also recommended (not required by SPEC):** the same `is_file()` guard on `new / member` in `download._replace_archive` (:292-310) and on the app CLI in `apps.update_app`: today a directory member passes `live_binary.exists()` and `os.access(X_OK)` (both true for a directory) and the update would link to a directory. One shared tiny helper `_require_file(path, label)` serves all five sites. Flag as optional hardening.

### Pattern 2: Strict removal proof beside the lenient plan
**What:** keep `plan_uninstall` (returns every name match). Four callers: `app.py:548` (CLI), `uninstall.py:299` (`classify_tools`), `version_status.py:594` and `setup.py:1108` (ownership evidence, via `resolve_ownership(artifacts=…)`). Only the first two delete. Add one function, e.g. `plan_removal(tools, default_bin_dir) -> RemovalPlan(removable: list[Path], yourself: list[Path])`, used by `classify_tools` and `run_uninstall`. Do not change `plan_uninstall`'s result for the ownership callers (it would silently change Owner column attribution, `ownership.py:964` "installer artifact").
**Predicate (D-04):** `link = base / binname; link.is_symlink() and (resolved := link.resolve()).is_file() and resolved.is_relative_to(opt_dir(binname).resolve())`. Removable paths = `[link, opt_dir(binname)]`; everything else that `plan_uninstall` found for the tool goes to `yourself`.
**Required companion fix:** `plan_uninstall` derives `binname = PurePosixPath(member).name` (`uninstall.py:90`) but install names the link `bin_name or basename(member)` (`download.py:144,242`). With `bin_name = "subl"` the plan looks for `bin/sublime_text` and never sees `subl`. Use the same `bin_name`-first expression in the plan (one line; share it with the executor if cheap).
**TUI shape:** no new `UninstallState`. A tool with matches but no proof becomes `MANAGED` (inert, `wizard_app.py:993` makes only `REMOVABLE` selectable) with hint "remove it yourself: <paths>" (new text only). Adding an enum member would need the four dicts at `wizard_app.py:877-880,1019-1030` updated for no gain.
**CLI shape:** `run_uninstall` prints the `yourself` list (new small `render` function next to `render_uninstall`, `render.py:171`) and deletes only `removable`; the "nothing to uninstall" early-return at `app.py:~556` must still print the manual list; a second `--yes` run then has `removable == []` and exits 0.

### Pattern 3: Fold once, read everywhere (SAFE-05)
**What:** `Summary` gains `not_attempted`, `update_failed` (tuples of ids, default `()`), `crash_error: str | None = None`; add `Summary.has_failure` (property) and one pure `session.fold_run(summary, *, not_attempted, update_outcomes, update_errors, error) -> Summary`. Both `ExecuteScreen.on_install_run_finished` (status colour) and `UnifiedApp.on_install_run_finished` (accumulation, D-08) call the same function; `setup.py:1275,1509` read `summary.has_failure`. Only two production `Summary(` constructors exist (`session.py:209`, `wizard_app.py:2968`); defaults keep the 24 test constructions valid.
**`update_failed` must include** `outcome.status == "failed"` from `update_outcomes` (a failing update returns `UpdateOutcome(status="failed")`, `update.py:153`; it does NOT raise) as well as the ids in `update_errors` (exceptions). `unknown-owner` and `unsupported` are "cannot update" notices, not failures (recommend: not counted; Phase 20 owns the mapping).
**Status line:** `ExecuteScreen` `self.status.set("Done. enter or esc returns to the catalog.", "ok")` (`execute_screen.py:953`) becomes `"Failed. …"` with severity `"error"` when `has_failure`. Severity strings in use: `"ok"`, `"warn"`, `"error"`.
**Worker (D-07):** `_execute_worker` currently assigns `outcomes`/`summary` only after `run_installs` returns (`execute_screen.py:~632-640`), so an exception mid-run loses every finished row. Accumulate in the existing `on_outcome` callback (`attributed_install(runner, install, on_outcome)`) into a local list, and on `except Exception as exc` use that list as `outcomes`, derive `not_attempted` from it, set `error`/`crash_error`. Same for `_run_updates`: it returns its four collections only at the end; have it append to caller-owned lists (or catch per tool) so completed updates survive a later exception. `run_live` only catches `OSError`, `CommandError`, `ShellrcRefusal` (`ui_common.py:42`).

### Pattern 4: `move_link_mode` (SAFE-06)
**Facts (read):** only three policy kinds depend on the link mode: `ban_policy` (apply writes aliases to `apply_rc_paths()` read live; remove strips the union `all_ban_rc_paths`, `policy.py:267-349`), `tweak_policy` (block always in `~/.myshellrc`; split mode adds `ensure_source` lines via `ensure_sourced_from()`, `policy.py:357-455`) and the macOS `cache_redirect_policy` (same `ensure_sourced_from`, `policy.py:485-580`). The Linux cache redirect, the daemon (launchd/systemd) and the omz-plugins policy do not read the link mode.
**Two corrections to D-09:**
1. `active_policies` (`uninstall.py:401`) builds its own policy objects from `bundles`, and never includes the ban. It cannot filter the screen's existing list. For the screen's list the live truth is `PoliciesScreen.active_state[policy.id]` (`wizard_app.py:1638,2012`); `Policy.active` is a construction-time snapshot. `policy_owned` (`uninstall.py:387`) is only right for policies with `is_active`/`owned`.
2. Removing and re-applying "every active policy" would also bootout/bootstrap the daemon and rewrite `.zshrc` plugins on every mode change. Recommend an appended `Policy` field, e.g. `link_mode_aware: bool = False`, set `True` by `ban_policy`, `tweak_policy` and `cache_redirect_policy` (Policy is frozen; new fields are APPENDED per the dataclass comment at `policy.py:148`). See Open Question 2.
**Algorithm:** `move_link_mode(policies, new_mode, set_link_mode, *, old_mode)`: (a) `remove()` each policy in old mode; (b) `set_link_mode(new)` (if it raises, re-`apply()` every removed policy in the old mode, report, stop); (c) `apply()` each; on a failure, `set_link_mode(old)` -> `apply()` that policy -> `set_link_mode(new)`, record "failed, old block restored"; return `tuple[(policy_id, ok|failed, message)]`. Closures read the mode live (`setup.py:_current_link_mode`, `_ban_apply_rc_paths`, `_tweak_ensure_sourced_from`, `setup.py:~899-905`), which is what makes remove-before-flip/apply-after-flip correct.
**Call sites:** `PoliciesScreen._link_mode_picked` (`wizard_app.py:2179`) with `[p for p in self._policies if p.link_mode_aware and self.active_state[p.id]]`, and `UnifiedApp._first_link_mode_picked` (`wizard_app.py:~2770-2790`), which today also just saves the mode. The first-run picker runs at mount, before any toggle, so `policy.active` is exact there. Both go through `run_live` (rule 3).

### Pattern 5: Settings load once (SAFE-08)
`load_settings` is called from exactly one place, `setup.py:1283` inside `_settings_store`; the "7 callers" in CONTEXT are the callers of `_settings_store` (`setup.py:1292,1321,1349,1439,1450,1469`). Put the warning on `SettingsStore` (constructed in `_settings_store`) so those six callers stay unchanged. `except (OSError, ValueError)` covers `UnicodeDecodeError` and `JSONDecodeError` (both `ValueError` subclasses); `FileNotFoundError` is "never chosen", not a warning. The store never writes at launch (only `set_link_mode` -> `save_settings`), so "does not overwrite the bad file until the user changes a setting" holds by construction; a single `warning: str | None` field replaces the separate flag. Surface it with the existing `UnifiedApp._pending_warnings` queue, flushed at the end of `on_mount` (`wizard_app.py:2594-2606`, `_flush_pending_warnings` :2714), because the base catalog never goes through `show_view`.

### Pattern 6: One execute path (SAFE-09)
`_build_app` (`setup.py:755`) already holds `tools`, `platform`, a `_current_link_mode` closure, and resolves `disk_pressure`/`timer_cache` when omitted (`setup.py:~770-785`). Build `_execute_inputs(tools, platform, link_mode=_current_link_mode, unattended=unattended, disk_pressure=disk_pressure)` inside it, then the existing `replace(execute, version_refresh=…, updates=…)` (`setup.py:1134`) applies unconditionally. `_run_interactive_wizard` can then drop its own `cache`/`probe` construction (`_build_app` builds identical ones when both are `None`) and pass `unattended=options.yes`. **Routes with a bare `_build_app(...).run()`:** `_run_doctor` (`setup.py:1295`), `_run_fix` (:1324), `_run_uninstall` (:1351), and the guard/unguard branch **inline in `main`** (:1441); CONTEXT names `_run_guard :1386`, but that function is the console-only path with no app. All four ignore the app's `install_summary` and `return 0`; once Enter executes, they should return the same exit code (`summary.has_failure`).
**Empty Enter** already shows "Select at least one tool, or press q to quit." and posts nothing (`catalog_tui.py:1040-1042`); it needs a test, not code. `UnifiedApp.execute: ExecuteInputs | None` stays (its `None` branch, `wizard_app.py:2791`, only runs for tests constructing `UnifiedApp` directly; `test_wizard_app.py` builds it with `execute=None` in many tests); do not widen scope to make it required.

### Pattern 7: Doctor finding (R10)
Add `broken_links: tuple[BrokenLink, …] = ()` (appended, defaulted) to `DoctorReport` (`doctor.py:9`), fill it in `doctor_data` (`app.py:346`) with a pure scan of `default_bin_dir`: for each entry, `is_symlink()` and (`not exists()` -> dangling, or `is_dir()` -> link-to-directory). Emit one `Guidance` per link from `doctor_guidance` (`guidance.py:104`), include them in `has_problems`. **Pitfall:** `DoctorScreen._tui_guidance` (`wizard_app.py:599`) rewrites any `next_step` that starts with "Run `make fix`" or "Run `make setup`", so the new next_step must not start with either prefix. Repair text: if `opt_dir(link.name)` exists, "Remove ~/.local/opt/<name>, then reinstall <name> from the catalog (make setup)"; otherwise (dangling link with no opt dir, e.g. a uv/pnpm shim) "Remove the dangling link <path>, or reinstall its owner". The unconditional opt-dir wording in D-13 would be wrong for those. Live check on this host (read-only): `~/.local/bin/subl -> /home/bazzite/.local/opt/subl/sublime_text`, and `find -xtype d` lists `subl`, i.e. the live link-to-directory exists. [VERIFIED: ls -l, find]

### Anti-Patterns to Avoid
- **Changing `plan_uninstall` itself:** breaks ownership evidence (3 other callers).
- **Reading rc text with `read_text()` for the confirm compare:** universal-newline translation hides `\r\n` and trailing-newline changes. Compare `read_bytes()`.
- **A new `UninstallState` member:** touches four dicts for no benefit.
- **Moving every active policy on a mode change:** re-bootstraps the daemon and rewrites `.zshrc` for nothing.
- **Skipping or `xfail`-ing the CI tests:** forbidden by `.claude/testing.md`; every one has a root cause below.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic file/link writes | temp+rename code | `atomic.atomic_write_text(…, mode=0o755)`, `atomic.replace_symlink` | Already symlink-through, unique temp, cleans up on error; tested in `tests/test_atomic.py` |
| Live-mutation error handling | `try/except OSError` in a screen | `ui_common.run_live` | Architecture rule 3 |
| Env for a vendor script | new env plumbing | registry `env = {…}` + `_env_prefix` (`executors.py:335`, registry `:166,173,554`) | Closed, tested path; codex needs one line |
| Empty selection message | new guard | existing `on_tool_browser_accepted` (`catalog_tui.py:1040`) | Already there |
| Worker-warning delivery | new status channel | `UnifiedApp._pending_warnings` / `_flush_pending_warnings` | Existing queue |
| Doctor wording split console/TUI | two texts | one `Guidance` list (`guidance.py`) | Both renderers consume it |
| bash 3.2 empty-array safety | custom wrappers | `${arr[@]+"${arr[@]}"}` | Standard idiom; passes shellcheck |

**Key insight:** each hazard here has a sibling that already solved it (update paths use `replace_symlink`; `omz.py`/`shellrc.py` use `atomic_write_text`; `env_redirect` uses `atomic_write_bytes`). The phase makes the remaining call sites match.

## Runtime State Inventory

This is a hardening phase, not a rename; two items are runtime-state relevant.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None - verified: no datastore keys change | None |
| Live service config | None | None |
| OS-registered state | None | None |
| Secrets/env vars | None | None |
| Build artifacts | Host damage already done: `~/.local/bin/subl` -> directory; `~/.local/opt/subl/sublime_text/` tree | Doctor prints repair; **user** runs it (zero host mutation). Do not repair from code or tests |

## Common Pitfalls

### Pitfall 1: Fake-runner tests cannot satisfy `is_file()`
**What goes wrong:** ~29 assertions across `tests/test_download.py` (23 `"ln"/"chmod"` lines), `tests/test_apps.py` (3), `tests/test_engine.py` (2) check the shelled argv `["ln","-sf",binary,link]` produced against a recording runner that creates nothing. After D-01 there is no `ln` argv and the file check fails.
**Avoid:** one shared test helper whose runner, on the extract call (`sh -c … tar`/`unzip`), creates the member under the opt dir; assert on `link.is_symlink()` / `readlink`. `test_download.py:175` (`test_tarball_bin_name_overrides_the_symlink_name`) encodes the Sublime bug (`member: "sublime_text"`) and must change to `sublime_text/sublime_text`.

### Pitfall 2: Sublime member is a layout fact, verified
The x64 and arm64 archives both have a single top-level dir `sublime_text/` containing the executable `sublime_text/sublime_text` (`-rwxrwxr-x`). So `member = "sublime_text/sublime_text"`, `strip` stays 0, binary = `~/.local/opt/subl/sublime_text/sublime_text`. [VERIFIED: `tar -tvJf` of both archives in a disposable python:3.12-slim container, 2026-10-14]

### Pitfall 3: graphify global form is not cwd-clean (D-03 evidence)
Probe (disposable `python:3.12-slim`, `pip install graphifyy==0.9.54`, fresh HOME and fresh cwd per run). Output verbatim, `cwd entries` / what landed:

| Command | cwd after | HOME after |
|---|---|---|
| `graphify claude install` (current hook form) | `.claude CLAUDE.md` | nothing |
| `graphify install --platform claude` | empty | `.claude/skills/graphify/…` |
| `graphify install --platform codex` | empty | `.codex/skills/graphify/…` |
| `graphify install --platform opencode` | `.opencode` (`plugins/graphify.js`, `opencode.json`) | `.config/opencode/skills/graphify/…` |
| `graphify install --platform cursor` | `.cursor` (`rules/graphify.mdc`) | nothing |
| `graphify install` (default) | empty | `.claude`, `.config` |

[VERIFIED: container run this session] So the literal D-03 rule ("if anything lands in the cwd, remove `postinstall`") yields **remove**, but the outcome is mixed per host (claude/codex clean, opencode/cursor dirty). The current hook form (`graphify <host> install`, `postinstall.py:269`) is the dirty per-project form for all four. Also: the update path never runs the hook (only `engine.py:166` calls `run_postinstall`, on install), so "update leaves cwd empty" holds by construction; keep a test. The runner seam is `Callable[[list[str]], None]` (`run.py:16`) and has no `cwd` parameter, so D-03's "pin `cwd=`" would need an argv-level `sh -c 'cd "$(mktemp -d)" && exec …'` wrapper; this is another reason to prefer removing the hook. If the hook is removed, per architecture rule 5 also delete `_graphify_register`, `_GRAPHIFY_HOST_SUBCOMMANDS`, the `POSTINSTALL_HOOKS` entry and the `"graphify-register"` name in `model.py:21` plus their tests (`tests/test_postinstall.py` has 20 graphify lines; `test_registry.py` 27; `test_model.py` 4), or vulture/dead-code review will flag them. See Open Question 1.

### Pitfall 4: D-10 misses the update path
`UpdateService` and the Doctor reinstall use `runner=run_captured` (`setup.py:1121`, `update.py:406`), and `run_captured` calls `run_output` -> `subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=…)` (`run.py:~60`) with **inherited stdin and no new session**. A vendor update script reading `/dev/tty` or stdin can still hang the TUI. Add `stdin=subprocess.DEVNULL, start_new_session=True` there too (other `run_output` callers are `executors.py:206,264`, `pnpm_globals.py:413`, `versions.py:277,298`, all queries or browser launches that read no stdin; also verify `daemon.py`, `policy.py`, `systemd_daemon.py`, which use `run_captured` for launchctl/systemctl). Do **not** touch `run_command` (console runner; must keep the terminal for interactive prompts). Test updates required: `tests/test_run.py::test_run_output_unbounded_by_default` uses a fake `subprocess.run` with a fixed keyword list and must accept the two new kwargs.
**Test design:** under pytest there is usually no controlling tty, so `open("/dev/tty")` fails with ENXIO whether or not the session is new (checked: errno 6 both ways). A tty-open test alone cannot discriminate. The discriminating assertion is a child that exits non-zero unless `os.getsid(0) == os.getpid()`; keep a `/dev/tty` reader test for the 5 s acceptance. [VERIFIED: local experiment]
**Side effect to note:** a child in its own session no longer receives the terminal's SIGINT/SIGHUP with the parent; acceptable under Textual raw mode, but mention in the summary.

### Pitfall 5: macOS prune failure is three bugs, not one
Reproduced under bash 3.2.57 (`docker.io/library/bash:3.2`): `mapfile: command not found` (`prune-tmp-linux.sh:101`) **and** `find_type[@]: unbound variable` (`scripts/lib/prune-tmp-common.sh:208`, empty array under `set -u`), exactly the two CI errors. Fixing only `mapfile` (D-14) still leaves exit 127. The same empty-array pattern is at `:203,209,211,228,234,236`, and at `prune-tmp-linux.sh:105,115` (`"${files[@]}"`). Third: `find -regextype posix-extended -regex` (`prune-tmp-common.sh:208,233`) is GNU-only; macOS BSD find has no `-regextype`, and the `2>/dev/null || true` swallows the error so matches silently vanish after the other two fixes.
**Verified fix (prototype in a scratch copy, run in bash 3.2.57):** `files=(); while IFS= read -r line; do files+=("$line"); done < <(…)`; `${arr[@]+"${arr[@]}"}` everywhere; replace the `-regex` predicate with `find … -mmin +N … | grep -E "^${pattern}$" || true` (and the NUL variant is only used by name-mode, unaffected). Result in the container: dry-run lists exactly the two matching files, near-miss and too-young files survive, apply deletes 2, empty dir exits 0. [VERIFIED: bash 3.2.57 + busybox find]. BSD `find -mmin/-mindepth/-maxdepth` support is [ASSUMED] (standard BSD options); only the macOS CI job proves it. Keep `shellcheck -x` green (it runs in `make validate` over these scripts).

### Pitfall 6: `test_owner_cell…` is the intermittent race, and it fails on ubuntu
CI history (5 recent runs on ubuntu-latest) shows it failing with `'installer artifact' == 'Homebrew'`; it passes locally. Root cause reproduced: the test seeds `service._ownership` by hand, but mounting the app starts the catalog's refresh worker, which re-resolves ownership with `artifacts_for=lambda tool: [_MANAGED / tool.cmd]` (`test_catalog_tui.py:1183`) and overwrites it with "installer". Adding `await app.workers.wait_for_complete()` before the assert reproduces the CI failure locally. [VERIFIED: temporary test copy, deleted]. Fix: make the refresh produce the same answer (`artifacts_for=lambda _t: []` plus a brew inventory), or wait for workers and assert the refreshed value. The SPEC's attribution of this test to macOS is wrong, and the SPEC's separate "`test_version_status` race" could not be reproduced (6 consecutive runs of `tests/test_version_status.py` passed; no CI run in the last 12 shows it failing). The planner should first run `gh run list`/`--log-failed` for it and, if it cannot be found, treat `test_owner_cell…` as the race and note the finding in the summary; the two negative `second.join(timeout=0.2); assert second.is_alive()` checks (`test_version_status.py:1790,1874`) are the only wall-clock-dependent assertions in that file if a candidate is needed.

### Pitfall 7: `time-shells0` depends on a coreutils package
CI failure text: `MARKER=` plus GNU `time` rusage output. On the runner `/usr/bin/time` exists, so dash runs the external `time` binary with `.` as a command (fails); in the CONTEXT container it did not exist (`time: not found`). Both mean dash does not source. D-15's per-shell expectation is right; derive the expectation from `Path(shutil.which("sh")).resolve().name == "dash"` rather than assuming. macOS `sh` is bash-in-posix-mode and has the keyword [ASSUMED].

### Pitfall 8: The two macOS `test_app.py` failures are Rich wrapping
A long `/private/var/folders/…` pytest path wraps at the default console width (output shows `test_configure_pa\nth_reports…`). Force a wide `Console(width=…)` in the test fixture that builds the buffer console. [VERIFIED: CI log]

### Pitfall 9: `test_interactive_wizard_shares_one_cache…` is host-dependent
It patches `setup.detect` to Linux but `_build_daemon_policy` gates on the real host's `systemd_daemon.systemd_available(which=…)` (`setup.py:~627`), so on macOS there is no `daemon:` policy and `next(...)` raises `StopIteration` (CI log). Make the test supply systemd availability (patch `setup.systemd_daemon.systemd_available` or `setup.shutil.which` to find `systemctl`), as the sibling test at `test_setup.py:2827` does for the shared-cache case.

### Pitfall 10: Rewrites of the removal tests
`test_uninstall.py` has 63 tests; those at :31-100, :184-276 and :338-350 assert name-match planning and the app-bundle plan. Keep tests for the lenient `plan_uninstall` (still used for ownership) and add a strict-shape family; only the `classify_*` removable tests and the app-bundle removable assertions change. Fixtures need a real `opt/<bin>/<member>` file and a symlink to it.

### Pitfall 11: Branch-protection required context names
The jobs are `validate & test on ubuntu-latest` and `validate & test on macos-latest` (the job `name:` expands the matrix; confirmed from run 38607235232). Required contexts must match those strings exactly. `ubuntu-latest` migrates to Ubuntu 26 starting 2026-10-19 (runner annotation), five days from today; the final-commit CI run should land and be recorded promptly, and a red run after the migration needs triage before blaming the phase.

## Code Examples

### Strict-compatible link (SAFE-01)
```python
# Source: pattern from installer/download.py:288-325 (update path) + atomic.py:117
binary = opt / target.member
if not binary.is_file():
    raise ExecutorError(f"archive member '{target.member}' is not a regular file")
binary.chmod(0o755)
replace_symlink(link, str(binary))
```

### Byte-exact confirm recheck (SAFE-04)
```python
# installer/app.py clean_rc_duplicates: preview
before = rc_path.read_bytes(); text = before.decode(); indices = find_duplicate_path_lines(text, managed_dirs, env)
# confirm
if rc_path.read_bytes() != before:
    console.print(f"{rc_path} changed since the preview; left untouched."); continue
atomic_write_text(rc_path, strip_lines(text, indices))   # atomic_write_text follows a symlinked rc
```

### Shims through the atomic writer (SAFE-04)
```python
atomic_write_text(target, shim_script(name), mode=0o755)   # replaces write_text + chmod pair
```

### Branch protection body (CI-02, run only after green CI + user confirmation)
```bash
# Source: docs.github.com/en/rest/branches/branch-protection (update-branch-protection)
gh api -X PUT repos/castocolina/tools-installer/branches/main/protection --input - <<'JSON'
{"required_status_checks":{"strict":false,"checks":[
   {"context":"validate & test on ubuntu-latest","app_id":-1},
   {"context":"validate & test on macos-latest","app_id":-1}]},
 "enforce_admins":false,"required_pull_request_reviews":null,"restrictions":null}
JSON
gh api repos/castocolina/tools-installer/branches/main/protection --jq '.required_status_checks.checks,.enforce_admins.enabled'
```
All four top-level keys are required (null allowed); `checks` is preferred over `contexts`. [CITED: docs.github.com branch-protection page]. Current state: `gh api …/protection` returns 404 "Branch not protected"; repo is public and the user has `admin: true`; no rulesets exist. [VERIFIED: gh api]

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| `required_status_checks.contexts` | `checks` with `app_id` | `contexts` is documented as closing down |
| Shelled `ln -sf` | `os.symlink` + `os.replace` | atomic, no write-through |
| `mapfile` / `-regextype` | `while read` / `grep -E` | works on bash 3.2 and BSD find |

**Deprecated:** Node 20 GitHub actions (`actions/checkout@v4`, `astral-sh/setup-uv@v5` warn on the runner). Not in scope; note only.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | BSD `find` supports `-mmin`, `-mindepth`, `-maxdepth` as used | Pitfall 5 | prune tests still fail on macOS after the fix; CI shows it |
| A2 | macOS `/bin/sh` (bash posix mode) sources `time . file` | Pitfall 7 | the per-shell expectation is wrong on macOS; derive by probing instead |
| A3 | `ubuntu-latest` = Ubuntu 26 keeps `sh` -> dash and the current Python/uv behaviour | Pitfall 11 | a green run before 2026-10-19 may go red after; unrelated to the phase |
| A4 | Treating `unknown-owner`/`unsupported` update outcomes as non-failures matches the user's intent | Pattern 3 | `make`/TUI exit codes differ from expectations; Phase 20 re-maps anyway |
| A5 | The `second.join(timeout=0.2)` checks are the only timing-based candidates for the SPEC's `test_version_status` race | Pitfall 6 | a different flaky test stays unfixed |
| A6 | `Policy.link_mode_aware` (appended field) is acceptable as the "active policy" filter | Pattern 4 | user may want literally every active policy moved (Open Question 2) |

## Open Questions

1. **graphify: remove the hook, or keep it for the clean hosts?**
   - Known: the probe above; literal D-03 says remove; per-project form is never allowed (SPEC R2).
   - Unclear: D-03 is binary, the result is mixed (claude/codex clean via `graphify install --platform <host>`, opencode/cursor drop `.opencode`/`.cursor` into the cwd; cursor's form installs nothing globally).
   - Recommendation: follow D-03 literally (remove `postinstall`, delete the dead hook code); confirm with the user, because the user loses automatic claude/codex skill registration. The re-run of the probe in the plan must still be recorded in the summary.
2. **Which policies does a link-mode change move?**
   - Known: only ban, tweaks and the macOS cache redirect are mode-dependent; moving the daemon/omz policies has side effects.
   - Recommendation: appended `Policy.link_mode_aware` flag (Pattern 4). Confirm with the user as a refinement of D-09's "every active policy".
3. **Identity of the SPEC's "timing-dependent race test"** (Pitfall 6): not reproduced; plan a first task that checks CI history before editing.
4. **Doctor repair text for a dangling link with no opt dir** (wording is Claude's discretion; the Pattern 7 split is a recommendation).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv | all test runs | yes | 0.11.28 | — |
| Python | tests | yes | 3.12.12 (project >=3.11) | — |
| podman | graphify probe, bash 3.2 checks, `make e2e` | yes | 5.8.7 | docker (none installed) |
| bash 3.2 image | prune verification | yes (pulled) | `docker.io/library/bash:3.2` = 3.2.57 | — |
| python:3.12-slim image | graphify/sublime probes | yes | local | — |
| gh (authenticated) | CI-01 evidence, CI-02 | yes | 2.101.0, user `castocolina`, repo admin | — |
| macOS host | CI-01 macOS | no | — | GitHub macos-latest job only (known constraint) |
| BSD `find` | prune on macOS | no | — | CI only; `find\|grep -E` form avoids flavour differences |
| network | probes | yes | — | — |

**Missing with no fallback:** none. A container probe needs `--security-opt label=disable` for read-only host mounts on this SELinux host (otherwise "Permission denied").

## Validation Architecture

> `workflow.nyquist_validation` is true in `.planning/config.json`.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-xdist + coverage (`fail_under = 90`) |
| Config file | `pyproject.toml` (`addopts = "-q"`), `tests/conftest.py` (40% worker cap, real-home guard) |
| Quick run command | `uv run pytest <files> -x -q --no-cov` (targeted; do not pass a fixed `-n`) |
| Full suite command | `make validate && make test` (validate then `pytest -n auto --cov`); `make e2e` for container installs |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SAFE-01 | dir member raises `ExecutorError`, no link; reinstall over link-to-dir leaves inner file byte-identical; apps same; Sublime member | unit (scratch HOME) | `uv run pytest tests/test_download.py tests/test_apps.py tests/test_engine.py tests/test_registry.py -x -q --no-cov` | exists; ~29 assertions rewritten + new tests Wave 0 |
| SAFE-02 | graphify has no `postinstall` (or clean global form); install via `install_tool` runs no hook; update runs none; scratch cwd stays empty | unit | `uv run pytest tests/test_postinstall.py tests/test_registry.py tests/test_model.py -x -q --no-cov` | exists, edits; probe result recorded in summary |
| SAFE-03 | uv `ruff` symlink, pip `yq` file, shared `drawio` -> 0 deletions in TUI and `--yes`; archive tool removed; link into other opt dir not removed; same deletion set both paths; second `--yes` deletes nothing | unit + e2e | `uv run pytest tests/test_uninstall.py tests/test_uninstall_e2e.py tests/test_setup.py tests/test_wizard_app.py -k "uninstall or removal" -x -q --no-cov` | exists; rewrites + new Wave 0 |
| SAFE-04 | injected write failure leaves bytes; changed-between-preview-and-confirm refused (trailing newline counts); symlinked rc stays symlink; foreign bytes untouched; empty/missing rc | unit | `uv run pytest tests/test_guards.py tests/test_tweaks.py tests/test_app.py tests/test_atomic.py -x -q --no-cov` | exists; new tests Wave 0 (reuse `os.replace` monkeypatch from `test_atomic.py`) |
| SAFE-05 | worker raise -> red "Failed", earlier rows done, rest not attempted, exit 1; failed update (status `failed` and raised) exit 1; all-skipped exit 0 | pilot + unit | `uv run pytest tests/test_execute_screen.py tests/test_session.py tests/test_setup.py tests/test_wizard_app.py -k "summary or crash or failed or exit" -x -q --no-cov` | exists; new tests Wave 0 |
| SAFE-06 | ban + tweak active, centralized->split moves blocks (absent in old, present where new mode sources); injected apply failure keeps old block and reports; no active -> only save | unit + pilot | `uv run pytest tests/test_policy.py tests/test_policies_e2e.py tests/test_wizard_app.py -k "link_mode" -x -q --no-cov` | exists; new tests Wave 0 |
| SAFE-07 | child in a new session (`getsid` check) and a fake `/dev/tty` reader exits non-zero < 5 s, for both `StreamingRunner` and `run_output`; codex method has `env` | unit | `uv run pytest tests/test_run.py tests/test_registry.py tests/test_executors.py -x -q --no-cov` | exists; fake-kwargs test updated |
| SAFE-08 | invalid-UTF-8 and invalid-JSON `settings.json` reach first screen, bytes unchanged, warning shown | unit + pilot | `uv run pytest tests/test_settings.py tests/test_setup.py tests/test_wizard_app.py -k "settings" -x -q --no-cov` | exists; rewrites (18 settings tests) |
| SAFE-09 | one test per route (setup, doctor, fix, uninstall, guard) asserts Enter runs the selection; empty Enter shows message and runs nothing; old test deleted | pilot | `uv run pytest tests/test_setup.py tests/test_wizard_app.py -k "route or execute or accept" -x -q --no-cov` | exists; new tests Wave 0 |
| R10 (Doctor) | link-to-dir and dangling link each one finding with repair text; filesystem unchanged | unit | `uv run pytest tests/test_doctor.py tests/test_guidance.py tests/test_render.py -x -q --no-cov` | exists; new tests Wave 0 |
| CI-01 | the 11 named failures pass on both OSes; prune under bash 3.2 | unit + container | `uv run pytest tests/test_prune_tmp_linux_sh.py tests/test_prune_user_tmpdir_sh.py tests/test_shellrc.py tests/test_app.py tests/test_setup.py tests/test_catalog_tui.py -x -q --no-cov`; bash 3.2: `podman run --rm --security-opt label=disable -v "$PWD/scripts:/s:ro" docker.io/library/bash:3.2 bash /s/prune-tmp-linux.sh --tmpdir <dir>`; final: CI run `success` on both jobs | exists |
| CI-02 | protection shows both checks required, `enforce_admins` false | manual (needs user confirmation) | `gh api repos/castocolina/tools-installer/branches/main/protection --jq '…'` | n/a; optionally extend `tests/test_ci_workflow.py` to pin the job `name:` the protection depends on |
| CI-03 | SECURITY/VALIDATION entries for 16-17..19 exist and are committed | doc check | `grep -c "16-1[789]" <16-SECURITY.md> <16-VALIDATION.md>`; `git log -1 -- <files>` | files exist; entries Wave 0 |

### Sampling Rate
- **Per task commit:** the quick command of the touched row (< 30 s each).
- **Per wave merge:** `make validate && make test`.
- **Phase gate:** `make validate && make test` green on the exact tree, then `make e2e` once for SAFE-01/03 integration, then the CI run on the final commit green on both jobs, before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] shared test helper for a runner that materializes the extracted member (Pitfall 1), used by `test_download.py`, `test_apps.py`, `test_engine.py`
- [ ] strict-shape uninstall fixtures (real `opt/<bin>/<member>` + symlink; adjacency case: link into another tool's opt dir)
- [ ] per-route Enter tests (5) and the empty-Enter test
- [ ] `getsid`-based session test and a `/dev/tty` reader test for `run_output` and `StreamingRunner`
- [ ] link-mode move tests with injected apply failure (reuse the `os.replace` failure injection pattern from `test_atomic.py`)
- [ ] all tests: scratch HOME via `tmp_path` + `monkeypatch`, no fixed paths, xdist-safe; the session-scope guard in `conftest.py` only fingerprints five dotfiles, so every new test must patch home-derived constants like `tests/test_setup.py::_sandbox`

## Security Domain

`security_enforcement` is enabled (absent = enabled; `security_asvs_level: 1`, block on `high`).

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | `is_file()`/`resolve()` + `is_relative_to` containment for archive members and removal proof; registry stays the only source of argv |
| V12 Files and Resources | yes | atomic temp+replace writes; symlink-aware writes; never delete unproven paths |
| V7 Error Handling and Logging | yes | no silent green on crash; surfaced `crash_error` |
| V14 Configuration | yes | settings fallback without overwriting; closed `LINK_MODES` set unchanged |
| V2/V3/V4/V6 | no | no auth, session, access control or crypto change |

### Known Threat Patterns
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Archive member symlinked to a path outside the opt dir (chmod follows it) | Tampering | optional: require `resolved.is_relative_to(opt.resolve())` in the same `_require_file` helper (not required by SPEC; mentioned once) |
| Write-through of a symlinked shim target | Tampering | `atomic_write_text` resolves the symlink first, same as today's `write_text` follow; no regression, but a dangling symlink at a shim path would create its target; unchanged behavior |
| Deleting a user-owned file by name match | Tampering/Repudiation | strict predicate (D-04) |
| Vendor script blocking on `/dev/tty` | DoS | new session + `stdin=DEVNULL` + `CODEX_NON_INTERACTIVE=1` |
| sudo in repair text | Elevation | repair text lists only `rm`/reinstall; the SPEC's argv scan over executors must remain green |
| Branch protection applied without consent | — | procedural: user confirms in the moment; no `--force` |

## Reuse Map (ponytail)

| Change | Reuse (file:line) | New code actually needed |
|---|---|---|
| Atomic link | `atomic.replace_symlink` atomic.py:117 | `is_file` guard + `os.chmod` |
| Atomic rc/shim | `atomic.atomic_write_text` atomic.py:56 (24 callers) | swap 10 call sites; delete 4 `chmod` lines |
| Confirm recheck | `rcclean`/`strip_lines` already used in `app.py:447` | keep bytes, one compare |
| Worker catch | `attributed_install`'s `on_outcome` callback (`execute_screen.py:~609`) | local accumulator + `except Exception` |
| Exit code | `Summary` in `session.py:106`; `setup.py:1275,1509` | 3 fields, `has_failure`, `fold_run` |
| Link-mode move | `Policy.apply/remove` closures live-read mode; `run_live` | `move_link_mode` + 1 flag |
| tty | `StreamingRunner.popen_with_env` run.py:232; `run_output` run.py:~60 | 2 kwargs each |
| codex env | `_env_prefix` executors.py:335 | one registry line |
| Settings | `SettingsStore` (settings.py:90), `_pending_warnings` (wizard_app.py:2471) | `LoadedSettings`, one except, store field |
| Routes | `_execute_inputs` setup.py:1166 | move one call inside `_build_app`; delete the param and 2 tests |
| Doctor | `Guidance`, `doctor_guidance`, `DoctorReport` | scan + one guidance branch |
| Empty Enter | `catalog_tui.py:1040` | tests only |
| Prune | existing library | idiom fixes in 6 spots |
| Branch protection | `gh` authenticated | one command, run once |

**Not required by SPEC/CONTEXT (flag, do not build unless asked):** `is_file()` guard on the *update* paths (recommended, tiny), raw `cp`-onto-link-dir variant, symlink-containment check on members, `agent_policy.py` `write_text` sites (not rc/shims), making `UnifiedApp.execute` required, `move_link_mode` for the daemon/omz policies, a `settings` backup/repair UI, any pnpm-specific Doctor reasons.

## Project Constraints (from CLAUDE.md / AGENTS.md)

- `uv` only (no pip/poetry/venv); `make validate && make test` must pass on the exact tree before commit; never lower the coverage floor or add skip/xfail to go green.
- English only (code, comments, logs, commits).
- Never mutate the host: no `make setup/fix/uninstall`, no mutating `systemctl --user`, no real rc or agent settings edits. Real installs/removals/probes only in disposable containers (`scripts/detect-container-runtime.sh`), removed afterwards. Tests use a scratch HOME.
- Zero sudo/pkexec/doas, including repair text.
- Coherent commits: amend/squash, no "fix review comment" pile. Do not sweep in the unrelated working-tree changes present at start (`scripts/container-e2e-verify.sh`, `tests/test_shell_scripts_path.py`, `.planning/RUN-LEDGER.md`).
- Architecture: `setup.py` wiring only; decisions in `installer/`; screen mutations via `run_live`; no orphan helpers (delete dead graphify hook code if the hook is removed).
- Tests: `pytest -n auto` capped at ~40% threads, xdist-safe (no fixed shared paths, ports, order dependence).

## Sources

### Primary (HIGH confidence)
- Repo files read this session with line ranges cited inline: `installer/download.py`, `apps.py`, `atomic.py`, `uninstall.py`, `app.py`, `guards.py`, `tweaks.py`, `execute_screen.py`, `wizard_app.py`, `session.py`, `settings.py`, `run.py`, `policy.py`, `doctor.py`, `guidance.py`, `engine.py`, `postinstall.py`, `registry.toml`, `setup.py`, `scripts/*.sh`, `tests/conftest.py`, `.github/workflows/ci.yml`, Makefile.
- CI run 38437178670 and runs 38607235232, 38603690103, 38601827665, 38586893968, 38560070151 (`gh run view --log-failed`).
- Container experiments this session: graphify 0.9.54 probe (python:3.12-slim), Sublime archive listings (x64, arm64), bash 3.2.57 reproduction and prototype fix, `getsid`/`/dev/tty` behaviour, `https://chatgpt.com/codex/install.sh` lines 6/100/851-853 re-confirmed.
- Local temp-file experiment reproducing the `owner_cell` race (file removed afterwards).

### Secondary (MEDIUM confidence)
- https://docs.github.com/en/rest/branches/branch-protection (update-branch-protection body shape, `checks` vs `contexts`)

### Tertiary (LOW confidence)
- BSD find option support and macOS `sh` `time` behaviour (assumed; A1, A2).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH (no change)
- Architecture/reuse: HIGH (all call sites read this session)
- Pitfalls: HIGH for Linux-verifiable items, MEDIUM for macOS-only items (CI is the only macOS oracle)

**Research date:** 2026-10-14
**Valid until:** 2026-10-21 (the ubuntu-latest to Ubuntu 26 migration on 2026-10-19 can change CI baselines); code facts valid until the next commit touching the cited files
