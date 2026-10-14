# Phase 17: Stop the bleeding - Context

**Gathered:** 2026-10-13 (assumptions mode, with `--analyze --batch --all`)
**Status:** Ready for planning

<domain>
## Phase Boundary

No known host hazard (H1–H7, TA §10) can fire on the user's machine. Every failed or crashed run reports failure and exits 1. CI is green on ubuntu-latest and macos-latest, and main requires that check.

The WHAT is locked in `17-SPEC.md` (R1–R13). This file locks the HOW.

Out of scope: receipts and removal plans (19/22), registry data fixes other than Sublime's `member` (18), exit codes taken from plan outcomes (20), native handoff instead of sudo (22), and real-host UAT (24).
</domain>

<decisions>
## Implementation Decisions

**Decision rule for this phase and the ones after it (user, 2026-10-13):** when options compete, choose the best design (correct, one source of truth, no duplicated reads or parsing). Do not choose the smallest diff. Test churn is not a reason to choose the weaker option.

### Link safety and removal proof (R1–R3)
- **D-01:** Each of the three linking sites (`installer/download.py:189-190` `_install_unverified`, `:403-404` `_place_verified`, and `installer/apps.py:100`) checks `is_file()` on the member before linking. A non-file member raises `ExecutorError` and links nothing.
  - The shelled `chmod +x` and `ln -sf` are replaced with `os.chmod` and `installer/atomic.py:117` `replace_symlink`, which is the atomic sibling-temp + `os.replace` helper the update paths already use.
- **D-02:** Sublime's registry `member` (`installer/registry.toml:2270,2278`) is corrected to the binary inside the archive dir (`sublime_text/sublime_text`), and gets a `# Verified` line.
- **D-03:** graphify (R2) is decided empirically during execution.
  - An isolated-HOME probe runs in a disposable podman container (scratch HOME and scratch cwd).
  - If the cwd stays empty, the hook uses the global per-host form and also pins `cwd=` to a scratch dir as a second safeguard.
  - If anything lands in the cwd, the `postinstall` key is removed from graphify's `[[tool]]` entry. Dispatch is registry-driven, so no runtime code changes in that case.
  - The probe result is recorded in the plan summary.
- **D-04:** The removal proof (R3) is one predicate in `installer/uninstall.py`, used by both `classify_tools` (TUI) and the `setup.py` `--yes` path.
  - A tool is removable only when `bin_dir/<bin>` is a symlink that resolves to a regular file inside that same tool's `opt_dir(<bin>)`.
  - Every other match is listed as "remove it yourself" with its path: raw single-file binaries, uv/pip files, shared files, and **app-kind bundles**. The SPEC lists "app files" explicitly; the analyzer marked this point Unclear, and the SPEC settles it.
  - `tests/test_uninstall.py` fixtures that relied on the name match (`test_classify_removable_when_artifacts_on_disk` at :338-350, and the app-bundle tests at :184-276) are rewritten to the strict shape.
  - Phase 19 receipts later restore app-kind removability.

### Atomic writes and honest failure (R4–R5)
- **D-05:** Every direct `write_text` on rc files and shims becomes `installer/atomic.py` `atomic_write_text`, which writes through a symlink to its target.
  - The call sites are `installer/guards.py:388,392,425,448,472,554,564` and `installer/tweaks.py:254,297,308`.
  - Shim scripts pass `mode=0o755`, because there is no target to copy the mode from.
- **D-06:** `installer/app.py` `clean_rc_duplicates` (:418-448) keeps the previewed bytes. At confirm it re-reads the file and refuses, unchanged, if the bytes differ (a trailing newline counts). If they match, it applies the indices computed from the previewed bytes and writes atomically.
- **D-07:** The worker in `installer/execute_screen.py` `_execute_worker` (:593-656) gets an `except Exception` ahead of its `finally`.
  - Rows already done stay done, the rest become "not attempted", and the run is marked crashed.
- **D-08 (user):** Failure reaches the exit code through new fields on `installer/session.py` `Summary` (:105-113): `crashed: bool` and `update_errors`.
  - `wizard_app.py` `on_install_run_finished` (:2924-2974) folds `error`, `not_attempted` and `update_errors` into them.
  - `setup.py:1275` and `:1509` both check them. The headless path gets the same check for symmetry.
  - An all-skipped run exits 0. Phase 20 later replaces this with plan outcomes.

### Runtime safety (R6–R9)
- **D-09 (user):** A new `move_link_mode(policies, new_mode, set_link_mode)` lives in `installer/policy.py`.
  - It filters to active policies using `installer/uninstall.py` `active_policies` (:401-444), removes them in the old mode, sets the mode, then applies them in the new mode.
  - If an apply fails, it restores that policy's old block. It returns a per-policy report.
  - `wizard_app.py` `_link_mode_picked` (:2179-2194) calls it through `run_live`, with the screen's own policy list.
  - With no active policies, it only saves the mode.
- **D-10:** `installer/run.py` `StreamingRunner.popen_with_env` (:232-240) adds `start_new_session=True`. `stdin=DEVNULL` is already there.
  - codex's registry method gets `env = { CODEX_NON_INTERACTIVE = "1" }`, using the existing `_env_prefix` mechanism.
  - Acceptance: a fake `/dev/tty` reader exits non-zero within 5 s.
- **D-11 (user, "best over easiest"):** `load_settings` reads and parses once and returns the settings plus an optional warning, as a typed result (for example `LoadedSettings(settings, warning)`).
  - It catches `UnicodeDecodeError` and `json.JSONDecodeError`.
  - The store keeps an "invalid on disk" flag, so it never writes defaults over the bad file until the user changes a setting.
  - All 7 callers in `setup.py` (:1283,1292,1321,1349,1439,1450,1469) and the tests in `tests/test_settings.py` are updated.
  - The first screen shows the warning in its status.
  - Rejected option: a separate `settings_warning(path)` probe, which would re-read and re-parse the file and duplicate the decode logic.
- **D-12:** Every route passes `execute=_execute_inputs(...)` (`setup.py:1166-1211`) to `_build_app`, exactly like `_run_interactive_wizard` (:1234-1239).
  - The routes are `_run_doctor` (:1289), `_run_fix` (:1315), `_run_uninstall` (:1346) and `_run_guard` (:1386).
  - `test_accepting_the_catalog_without_execute_still_exits_with_ids` is deleted.
  - Enter with nothing selected shows a message and runs nothing.

### Doctor, CI and governance (R10–R13)
- **D-13 (user):** Doctor (`installer/doctor.py`) gets a generic scan of every symlink in `bin_dir()`.
  - A dangling link or a link to a directory is one finding.
  - The repair text is derived from `opt_dir(name)`: remove the opt dir, then reinstall `<name>` from the catalog. Nothing is executed, and the scan does not depend on the registry.
- **D-14:** In `scripts/prune-tmp-linux.sh:101`, `mapfile -t files < <(...)` becomes a `while IFS= read -r` loop, which works on bash 3.2.
- **D-15 (verified 2026-10-13 in a throwaway ubuntu container):** On ubuntu, `/usr/bin/sh` is dash, and dash has no `time` keyword or binary (`sh: time: not found`), so `time . file` never sources. bash does source it.
  - The `time-shells0` test keeps `sh`, and asserts what each shell really does: bash and zsh source it, dash does not.
  - The classifier still refuses `time .` in all three, which is the conservative outcome.
  - The analyzer's "dash forks a subshell" explanation was wrong. The original idea of dropping `sh` is rejected because it loses coverage.
- **D-16:** Console-width tests in `tests/test_app.py` force an explicit console width.
  - The `test_version_status` race test uses a `threading.Barrier` / `Event` instead of timing.
  - `test_setup::test_interactive_wizard_shares_one_cache…` and `test_catalog_tui::test_owner_cell_semantic_value…` get their macOS root cause fixed. Neither is skipped.
- **D-17:** Branch protection (R12) is applied with `gh api` only after the final commit's CI is green **and** the user confirms in the moment. Both jobs are required, with `enforce_admins=false`.
- **D-18:** The R13 re-audit appends entries for plans 16-17..16-19 to `16-SECURITY.md` and `16-VALIDATION.md` under `.planning/milestones/v0.49.0-phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/`.

### Claude's Discretion
- Plan and wave split. A sensible order: CI repairs first, so later commits are judged by a green baseline; then H1/H3/H4 file-safety; then failure, tty, settings and routes; then Doctor; governance last.
- The exact shape and name of the typed settings result, and of the `Summary` fields.
- How to word the "remove it yourself" and Doctor repair text, within the zero-sudo rule.

### Folded Todos
None.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `.planning/phases/17-stop-the-bleeding/17-SPEC.md` — locked requirements R1–R13 and acceptance criteria
- `.planning/research/2026-10-13-target-architecture.md` §10 (hazards H1–H7), §9.2 (O2, O14)
- `.planning/research/audit-2026-10-13/SYNTHESIS-AND-PLAN.md` — source findings
- `.planning/REQUIREMENTS.md` — SAFE-01..09, CI-01..03
- `.claude/architecture.md` — rules (setup.py is wiring only; decisions live in `installer/`; `run_live` for screen mutations)
- `AGENTS.md` — non-negotiables (never mutate the host, zero sudo, validate before commit)
- `.planning/milestones/v0.49.0-phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-SECURITY.md`, `16-VALIDATION.md` — R13 targets
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `installer/atomic.py`: `atomic_write_bytes`/`atomic_write_text` (symlink-through), `replace_symlink`, `capture_symlink_target`, `staged_sibling`, `recover_update_remnants`
- `installer/ui_common.py` `run_live`: the one screen-mutation wrapper
- `installer/uninstall.py` `active_policies`/`policy_owned` (:387-444)
- `setup.py` `_execute_inputs` (:1166-1211)
- `installer/executors.py` `_env_prefix` and the registry `env = {...}` pattern (`registry.toml:166,173,554`)
- `installer/locations.py` `opt_dir`/`bin_dir`
- `scripts/detect-container-runtime.sh` for the graphify probe container

### Established Patterns
- `install_tool` (`engine.py:95-196`) already catches per-tool exceptions; the crash gap is in the worker's non-install steps (`_ask_*`, `_run_updates`).
- `run_live` catches only `OSError`, `CommandError` and `ShellrcRefusal`.
- `Policy` has `apply`/`remove`/`is_active`/`owned`; its closures read `_current_link_mode()` live, so remove-before-flip and apply-after-flip target the correct files.
- Registry-driven postinstall dispatch: removing a key disables the hook.

### Integration Points
- `download.py`/`apps.py` → `atomic.replace_symlink`
- `uninstall.py` predicate ↔ `setup.py --yes` (one predicate)
- `guards.py`/`tweaks.py`/`app.clean_rc_duplicates` → `atomic_write_text`
- `execute_screen._execute_worker` → `wizard_app.on_install_run_finished` → `session.Summary` → `setup.py:1275,1509`
- `wizard_app._link_mode_picked` → `policy.move_link_mode`
- `run.StreamingRunner.popen_with_env` (install and update children)
- `setup._run_doctor/_run_fix/_run_uninstall/_run_guard` → `_execute_inputs`
- `settings.load_settings` → 7 setup.py callers + store invalid flag
- `doctor.py` scan ← `locations`; consumed by `_build_app`'s `doctor_data` (:782-787)
</code_context>

<specifics>
## Specific Ideas

- The live reproduction on this host: `~/.local/bin/subl` points to a directory (Sublime `member` typo). Doctor's finding for it must read: remove `~/.local/opt/subl`, then reinstall from the catalog. The user runs those steps.
- The graphify probe and any shell or CI check run only in disposable podman containers, which are removed afterwards.
</specifics>

<deferred>
## Deferred Ideas

### Reviewed Todos (not folded)
- `2026-09-16-detect-dangling-pnpm-global-bin-shims-in-doctor` (score 0.9) is not folded, because Phase 21 owns it (UI-07: "dangling pnpm global shims appear as broken"). D-13's generic scan may surface a dangling pnpm shim as a broken link, but the pnpm-specific reasons belong to 21.
</deferred>
