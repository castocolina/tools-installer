---
phase: 22
reviewers: [opencode-referee-one]
reviewed_at: 2026-11-04T01:34:56Z
cycle: 1
plans_reviewed: [22-01-PLAN.md, 22-02-PLAN.md, 22-03-PLAN.md, 22-04-PLAN.md, 22-05-PLAN.md, 22-06-PLAN.md, 22-07-PLAN.md, 22-08-PLAN.md, 22-09-PLAN.md, 22-10-PLAN.md, 22-11-PLAN.md, 22-12-PLAN.md, 22-13-PLAN.md]
models:
  opencode-referee-one: "router-env/my-referee-one"
model_sources:
  opencode-referee-one: "pinned"
---

# Cross-AI Plan Review — Phase 22

<!-- gsd:plan-revision-conflicts:begin -->
## Plan-Revision Conflicts
<!-- gsd:plan-revision-conflicts:end -->

## Cycle 1 (current) — reviewed at HEAD 8639fda

Reviewer: opencode-referee-one (`opencode run --model router-env/my-referee-one`). It was the only reviewer, so there is no consensus gate. It read all 13 plans and the locked inputs (22-SPEC, 22-CONTEXT, 22-UI-SPEC, 22-RESEARCH, 22-REUSE, 22-VALIDATION and the `| 22 |` RUN-LEDGER rows). It grounded its claims with `codegraph explore` against HEAD `8639fda`, modified no file, and ran no tests, containers or UAT. The raw output is `.review-diagnostics/20261104T013456Z-plan-review-cycle1/opencode-referee-one/lane.out` (gitignored).

Two things it confirmed mechanically and that need no change: the 13 `files_modified` sets do not intersect within any of the 7 waves, and the dependencies are acyclic. It also confirmed 18 script stanzas across 14 tool ids.

## opencode-referee-one Review

This section is condensed. It keeps every concern with its severity and evidence. Paths are relative to the phase directory unless they name a repo file.

### 22-01 — Risk: Medium
The schema changes fit the model. The shared harness denylist is the right approach.
- **HIGH: RED commits violate the commit gate.** `22-01-PLAN.md:98` has the executor commit failing tests (`test(22-01): …`) before the implementation, and requires `make validate && make test` only on `feat` commits. `AGENTS.md:29-30` and `.claude/git-workflow.md:10-12` require both to pass on every committed tree. The same protocol appears in every plan. Passing pre-commit is not enough.
- **LOW: an acceptance grep contradicts the constructor change.** `:128` adds both the dataclass field and the `__init__` keyword (the `requires` pattern, `installer/model.py:389` and `:424`). Both would match the `grep -c "config_paths: tuple\[str, ...\] = ()"` in `:149`, which expects exactly 1.
- Suggestions: run RED and paste its output, but do not commit it; commit tests and code together. Anchor the grep to the field's indentation.

### 22-02 — Risk: Medium
- **MEDIUM: the run report is not fully copy-safe.** `:221` adds `markup=False` to `render_handoff` but not `soft_wrap=True`, and does not sanitize the handoff line. `installer/render.py:346` has neither. `22-UI-SPEC.md:230` requires that the app never wraps the line (the headless console prints with `soft_wrap=True`), and `:319` requires every displayed command to be sanitized. The test at `:215` uses a short command with brackets, so it misses both gaps.
- Suggestions: add a long-command assertion that includes an escape sequence. Name the executor-table test (`tests/test_executors.py:96-107`) and the direct native executor tests (`:38-53`) as tests to rewrite.

### 22-03 — Risk: High
- **HIGH: the new reader rejects what the unchanged writer writes.** `:130` rejects `tree`/`leaf` artifacts that have `sha256`, `size`, `mtime_ns` or `key` "present", and says `_write_unlocked` needs no change. `installer/receipts.py:126-135` always writes all of those keys, with null values for these types.
- **HIGH: existence after install can adopt an untouched foreign path.** `:128-130` records every declared path found after the install (`installer/receipts.py:270-286`, `artifact_paths` plus `fingerprint`), with no evidence from before the install. The foreign-file test (`:123`) plants the file only after the receipt is written. A helper that existed before the install, at a declared path, becomes receipt-proven even when the vendor script never touched it.
- Suggestions: define one serialized shape and test it. Add a fixture where the helper exists before the install.

### 22-04 — Risk: Medium
- **LOW: the security-relevant nearest-parent branches are untested.** `:131` requires the owner comparison and fail-closed handling of `OSError`, but the tests at `:125` cover only writable and non-writable directories owned by the current user.
- Suggestions: add mocked cases for an ownership mismatch and for `OSError`. Note that `tests/state_doubles.py:426-441` `plan_state` has no `unwritable` keyword. Make `HOMEBREW_NO_SUDO` (22-08) mandatory where it is supported.

### 22-05 — Risk: Medium
- **MEDIUM: the unresolved-root error needs an input the function lacks.** `:95` raises `UpdateError(f"cannot resolve {token} for the {tool} update")`, but `_update_installer_owned` (`installer/update.py:379-385`) gets only method, platform, runner and resolver. Task 1 (`:129`) adds no tool id.

### 22-06 — Risk: High ("do not execute unchanged")
- **HIGH: an empty legacy script receipt can authorize the vendor `remove`.** The L3 rule (`:105`) asks only for a readable receipt with no drifted artifact. `receipts.drifted()` (`installer/receipts.py:587-589`) reports no drift for an empty tuple. The legacy test (`:189`) covers only a method without `remove`.
- **HIGH: managers can be removed before the packages that depend on them.** `:232` removes tools in the order given. The CLI passes the whole registry (`setup.py:1306-1324`), where `uv` (`installer/registry.toml:63`) comes before `ruff` (`requires = ["uv"]`, `:707`). The TUI keeps the selection order (`installer/tool_browser.py:365-374`, `installer/wizard_app.py:1495-1503`).
- **HIGH: the CLI skips the fresh command-proof check the TUI gets.** `perform_uninstall` plans again and compares paths and argv (`:151`). The CLI runs the plans it collected before the confirm prompt (`:232`). `remove_tool` runs the argv before any further proof (`:108`). Today the CLI proves everything again after the confirm (`installer/app.py:589-593`).
- Suggestion: extend the every-kind test (`:226`) to cover the published Uninstall projection.

### 22-07 — Risk: High
- **HIGH: the refresh pass defeats the crash backstop.** `22-06-PLAN.md:188` expects that a crash after the vendor `remove` leaves the receipt and a broken tool that cannot be removed. The pass wired at `:130` calls `_receipt_evidence` first, which retires a receipt whose artifacts are all gone (`installer/version_status.py:1448-1457`). When only some are gone, `tool_health` drops the broken facts of an absent tool (`:240-252`). The test calls `broken_drift` and `removal_plan` directly, so it sees neither behavior.
- **MEDIUM: the existing native-command expectations are not reconciled.** `:169` removes the native command templates, but `tests/test_ownership.py:1844-1860` and `:2662-2677` still expect native commands such as `dnf remove ripgrep` and `dnf remove glab`.

### 22-08 — Risk: High
- **HIGH: whole manager roots contain user packages and toolchains.** `:154` proposes recursive trees for `PNPM_HOME`, `~/.volta/`, `~/.local/share/fnm/` and `~/.bun/`. Under the type-only tree rule (`22-03-PLAN.md:130-132`), removal deletes everything in them, including content added after the receipt. pnpm keeps global packages under `$PNPM_HOME/global` and Bun under `~/.bun/install/global`, according to the vendors' docs.
- **MEDIUM: the safe omissions give no manual-removal guidance.** OMZ, SDKMAN and Homebrew get no paths and no `remove` (`:22-24`). The research says these stay "remove it yourself" (`22-RESEARCH.md:235-242`), but they declare no paths for that clause to list, and an installer-owned record has no `removal_hint` (`tests/test_ownership.py:1778-1789`).

### 22-09 — Risk: High
- **HIGH: the core cannot enforce the full shared-owner rule.** The check in `:95` runs over the decision, but `UninstallDecision.tools` holds only the selected tools (`installer/app.py:645-649`). The binding rule (`.planning/RUN-LEDGER.md:247`) needs every declaring tool. The test (`:158`) has no unselected owner.
- **HIGH: exact path equality misses overlapping config.** The validator (`22-01-PLAN.md:130`) accepts `~/.config/shared` for one tool and `~/.config/shared/plugin` for another. The rules in `:95` and `22-10-PLAN.md:99` compare only equal strings.
- **HIGH: checking only the final symlink does not keep deletes out of harness dirs.** `config_targets` only expands `~` (`22-06-PLAN.md:107`), and `delete_config_path` checks only the last path component (`:94`). An intermediate directory symlinked into `~/.claude` would let the delete reach a harness dir. The test (`:162`) covers only a symlink at the target itself.

### 22-10 — Risk: High
- **HIGH: `config_split` cannot reach the published state it must read.** Its signature, `config_split(flagged: Sequence[Tool], catalog: Sequence[Tool])` (`:99`), takes only tools, but the function must read `state.removable.config`. That field is on `ToolState` (`installer/version_status.py:763-780`), not on `Tool` (`installer/model.py:377-411`). The call sites (`:131`) and the 22-11 handoff repeat the two-argument form.
- **HIGH: the destructive flags are not reset on each visit.** `22-UI-SPEC.md:79` and `:371-372` (A3) require every flag to start off on each visit. The plan clears flags only on selection changes, after a removal and on reload (`:100`, `:208`). `show_view` calls `clear_transient` and `enter_view` (`installer/wizard_app.py:3188-3198`), and the base `clear_transient` only clears the status (`installer/ui_common.py:376-378`).

### 22-11 — Risk: High
- **HIGH: computing the decision again after the confirm can delete config the modal never listed.** The review uses `config_split` (`:121`), and `_apply_removal` calls it again after the confirm. The callback captures only ids (`installer/wizard_app.py:1485-1507`), and a refresh can publish while the modal is open (`installer/ui_common.py:363-371`). The test (`:114`) never changes state while the modal is open.
- **MEDIUM: the action omits warning severity.** `:194` raises the severity only for `config_not_deleted`. The severity expression (`installer/wizard_app.py:1661`) does not look at `swept.warnings`, yet the test at `:188` expects `warn`.

### 22-12 — Risk: High
- **HIGH: neither the tracked cask tokens nor the "current snapshot" has a defined path.** `_load_or_query_snapshot` gets only `now` and `platform` (`installer/version_status.py:1609-1611`), while the catalog is in its caller (`:1734-1747`). The snapshot is local to `_pass` (`:1746-1750`), and `VersionRefreshService` stores none (`:932-1018`), yet the accessor in `:163` reads a "current snapshot".
- **MEDIUM: a failed greedy query reads the same as "nothing outdated".** `:36` and `:92-93` turn a failed or malformed greedy read into an empty set. An empty cask map means current (`installer/version_status.py:529-540`), and `_partial_manager_failure` sees only `None` fields (`:1686-1692`), so the result is cached as a successful 6-hour check.

### 22-13 — Risk: High
- **HIGH: a failed manager removal can still pass the e2e gate.** The CLI prints removal failures (`22-06-PLAN.md:232`), and `_run_uninstall` returns 0 anyway (`setup.py:1311-1330`). The harness checks only the exit code and the yq receipt (`scripts/container-e2e-verify.sh:584-591`). Manager receipts have no artifacts (`22-06-PLAN.md:97`), and the receipt dir `.local/state/tools-installer` is on the allowlist (`:86`). A failed `brew uninstall` therefore passes both checks.
- **MEDIUM: must-clear paths are checked only after the baseline is subtracted.** `:84` and `:123` compute after minus before first. A receipt-proven path that is already in the baseline is never checked; bootstrap installs files before the baseline (`scripts/container-e2e-verify.sh:190-208`).

### Cross-plan priorities (reviewer)
1. Do not execute the plans unchanged.
2. Close the proof boundaries: receipt serialization, pre-existing files, empty legacy receipts, manager-root package stores, and a fresh command check in the shared remover.
3. Make config consent hold end to end: the full declaring catalog, overlapping paths, symlinked ancestors, a frozen modal decision, and flags cleared on each visit.
4. Test the real state lifecycle: a crash seen through a full refresh, manager removal ordered against its dependents, a refresh while the modal is open, and a failed manager removal reaching the CLI exit code and the e2e gate.
5. Repair the missing handoffs: `config_split` state, the tool id for the update error, and the storage for greedy tokens.
6. Replace committed RED checkpoints with uncommitted RED evidence and coherent GREEN commits, without relaxing the gates.
7. Keep the reuse and deletion bias: no second removal service, no shell templating, no persistent journal.

### Not checked (reviewer)
Nothing was executed (implementation, tests, validation, containers, UAT). Incidental fixture bodies were not checked exhaustively. Vendor layouts were not fully audited again. Real macOS behavior is not verified.

## Source-grounding adjudication

The orchestrator re-checked every HIGH, MEDIUM and LOW concern against the plan text and the source at HEAD `8639fda`.

**Fact-drift pass.** Every cited `file:line` exists and says what the reviewer claims. That covers, among others, `installer/receipts.py:126-135` (the writer emits null `sha256`/`size`/`mtime_ns`/`key`) and `:587-589`; `installer/app.py:589-593` and `:645-649`; `installer/version_status.py:240-252`, `:763-780`, `:932-1018`, `:1448-1457`, `:1609-1611`, `:1686-1692` and `:1734-1750`; `installer/wizard_app.py:1485-1507`, `:1661` and `:3188-3198`; `installer/ui_common.py:376-378`; `installer/update.py:379-385`; `installer/executors.py:449/453/457`; `installer/registry.toml:63` and `:707`; `setup.py:1306-1330` (`return 0` unconditionally); `scripts/container-e2e-verify.sh:584-591`; `tests/test_ownership.py:1778-1789`, `:1844-1860` and `:2662-2677`; and `.planning/RUN-LEDGER.md:247`. The only internal inconsistency found is in the plan, not the review: `22-05-PLAN.md:95` says the error is raised "inside `_perform`", while Task 1 (`:129`) puts it in `_update_installer_owned`. That supports R1-07.

**R1-01 (RED commits): is it a real plan defect or settled precedent?** It is a real defect, and the settled precedent sides with the reviewer.
- The rules: `AGENTS.md` ("`make validate && make test` must pass on the exact tree you are about to commit"), `.claude/git-workflow.md` ("One commit = … passes `make validate && make test`. Never commit a knowingly broken tree.") and `.claude/testing.md:42` (done means green "on the committed tree").
- The binding precedent: `.planning/RUN-LEDGER.md:31` (Phase 17) records "TDD red commits vs AGENTS.md coherent-commit rule → `tdd="true"` tasks; RED output recorded in SUMMARY, test + code in one commit", because "AGENTS.md forbids invalid intermediate commits".
- Phases 17-20 followed it: 30 `test(17..20…)` commits, none tagged RED (they are standalone passing test changes).
- Phase 21 drifted. It has 77 `test(21…)` commits, and 62 of them are tagged `(RED)` (for example `cfafbb0`, a test-only commit). Its plans did not ask for this; they said "paste the RED output into the SUMMARY, implement, paste the GREEN output" (for example `21-10-PLAN.md:80`). The commits came from the executors and from the review fix loop (`21-REVIEW-FIX.md:20`). Ledger rows 186, 189 and 191 recorded "RED/GREEN separate" as an observation, and no row overrides row 31. The pre-commit config has no pytest hook, so those RED trees passed the hooks while failing `make test`.
- Phase 22 makes the drift explicit. All 13 plans instruct a `test(22-NN): …` RED commit, and `22-01-PLAN.md:98` limits the test gate to `feat` commits.
- The GSD `tdd-review-checkpoint` gate, which looks for `test(`/`feat(` commit pairs in `type: tdd` plans, is advisory: `passed` is always true (`.claude/gsd-core/bin/lib/gate-tdd-review-checkpoint.cjs` header). Dropping the RED commits therefore blocks nothing.
- Verdict: **CONFIRMED**. The required change, in every plan: write the RED tests, run them and paste the output into the SUMMARY, but do not commit them; commit tests and implementation together in one `feat(22-NN)` (or `test(22-NN)` for test-only) commit, with `make validate && make test` exit 0 on every commit (ledger row 31). Executors should expect the advisory TDD checkpoint to list these plans and should not treat that as a failure.

**Verdict notes on the other concerns**
- R1-04 (PARTIAL): the ambiguity is real ("present" can mean the key exists or that its value is non-null). But the tracer `test_a_script_install_is_removed_by_its_receipt` round-trips `record` into `plan_removal`, so a wrong reading fails GREEN instead of shipping. The plan needs one sentence: absent or null.
- R1-05 (PARTIAL): the gap is real (no evidence from before the install), but `record` has always fingerprinted after the install, for every receipt kind (`installer/receipts.py:258-286`). The SPEC (lines 38 and 145) only requires that a foreign file *not in the receipt* survives. A naive pre-install snapshot would also drop legitimate paths on repair or reinstall. The plan needs an explicit rule and a fixture, or an accepted-limit note.
- R1-10 (PARTIAL): L2 paths are still proven again after the confirm, through `remove_proven` in `remove_tool` step 2, and with argv through `remove_paths` and `matches`. Only the argv itself runs on proof from before the confirm in the CLI.
- R1-11 (CONFIRMED): `22-SPEC.md:165` makes this backstop a SPEC row ("the next pass shows the tool broken and not removable"), so the gap is against the SPEC, not just the test. The outcome is safe (MISSING, no argv), but the plan claims a property the production pass does not deliver.
- R1-13 (PARTIAL): the data-loss risk is real. Deleting a manager root also removes catalog-tracked pnpm tools (`mmdc` and `puppeteer` at `registry.toml:2525/2649`) and toolchains managed by Volta or fnm. Two points are overstated: the vendors document deleting the directory as the uninstall, and ledger row 247 ("other packages stay") is about removing one pnpm package, not about removing pnpm itself. The data is still in research and verification (22-08 Task 3 says "Verify first").
- R1-14 (PARTIAL): no locked input requires a manual-removal hint for OMZ, SDKMAN or Homebrew; only the research suggests one (Pitfalls 5 and 7). The plan must either add the hints or record that these rows deliberately stay without one.
- R1-15 (PARTIAL): the catalog-wide rule is enforced in the TUI's `config_split` (22-10), which is the only producer of `decision.config`; the CLI never deletes config. 22-09 claims only "shared by two selected tools" (`:29`). The gap is in defense in depth, and it gets worse with R1-20.
- R1-16 (PARTIAL): nothing in the planned registry data overlaps today (gh, uv, kitty and pnpm config dirs). The gap is latent, and a load-time overlap refusal in the 22-01 validator closes it cheaply.
- R1-17 (PARTIAL): `22-SPEC.md:69` defines the denylist as a load-time string check (`load_tools`). Deleting through a symlinked ancestor is a real hardening gap beyond the SPEC, and an unusual layout is needed to hit it.
- R1-22 (PARTIAL): passing the tracked tokens is genuinely unspecified (`_load_or_query_snapshot` needs a new input). The accessor can read the persisted snapshot through `load_manager_snapshot(self._cache_path)` (`installer/version_status.py:1619`), so it is underspecified rather than impossible. The epoch guard and the invalidation on mutation (`:1254-1258`) must still be stated.
- R1-03 (22-02), R1-12 (22-07) and R1-21 (22-11) are CONFIRMED but low-risk: each plan's own verify command runs the whole affected test file, so GREEN would expose them. The plans should still name the change.

## Consensus Summary

There was a single reviewer, so this table is the orchestrator's adjudication of that reviewer's concerns. The severities are the reviewer's.

| ID | Plan | Severity | Verdict | Required plan change |
|---|---|---|---|---|
| R1-01 | all (22-01:98) | HIGH | CONFIRMED | Run RED and paste it into the SUMMARY, but never commit it; one tests-plus-code commit per task with `make validate && make test` green (ledger row 31) |
| R1-02 | 22-01 | LOW | CONFIRMED | Anchor the `config_paths` grep to the dataclass field (or expect 2) |
| R1-03 | 22-02 | MEDIUM | CONFIRMED | `render_handoff` prints `markup=False, soft_wrap=True` and sanitizes each line; add a long-command plus escape-byte test |
| R1-04 | 22-03 | HIGH | PARTIAL | State that tree/leaf readers reject only non-null hash/key fields (or the writer omits them); pin the serialized shape in a test |
| R1-05 | 22-03 | HIGH | PARTIAL | Define which declared paths an install may newly claim (paths that existed before the install versus repair or reinstall); add a fixture with the helper present before the install, or record the accepted limit |
| R1-06 | 22-04 | LOW | CONFIRMED | Add mocked tests for a foreign-owned writable parent and for an `OSError` probe (fail closed) |
| R1-07 | 22-05 | MEDIUM | CONFIRMED | Give `_update_installer_owned` the tool id, or raise from `_perform`; fix the `_perform`-versus-helper wording |
| R1-08 | 22-06 | HIGH | CONFIRMED | The L3 argv requires at least one receipt-proven artifact (D-06 "plus receipt-proven paths"); test an empty legacy receipt with `remove` |
| R1-09 | 22-06 | HIGH | CONFIRMED | Order the removal set so dependents (via `requires` and manager kind) go before their managers, in both CLI and TUI; add a test |
| R1-10 | 22-06 | HIGH | PARTIAL | Move the post-confirm `removal_plan(verify=True)` comparison of argv and paths into the shared remover path, so the CLI gets it too |
| R1-11 | 22-07 | HIGH | CONFIRMED | Specify the retirement and health behavior for an interrupted recipe removal, and test it through `VersionRefreshService.refresh` (all gone and partly gone), or amend SPEC:165 |
| R1-12 | 22-07 | MEDIUM | CONFIRMED | Rewrite the native cases in `tests/test_ownership.py:1844-1860` and `:2662-2677`, keeping their package-name coverage |
| R1-13 | 22-08 | HIGH | PARTIAL | Limit the trees that receipts can delete to manager binaries and trees only the installer owns; keep package and toolchain stores (pnpm global, `~/.bun/install/global`, Volta and fnm runtimes), or name them in the review; add a test with an unrelated global package |
| R1-14 | 22-08 | MEDIUM | PARTIAL | Add honest manual-removal hints for OMZ, SDKMAN and Homebrew, or record the decision to leave them hint-less |
| R1-15 | 22-09 | HIGH | PARTIAL | Give `perform_uninstall` the declaring owners from the catalog for each config path, and check them again at delete time; test an unselected owner and an owner with the flag off |
| R1-16 | 22-09 | HIGH | PARTIAL | Treat overlap between an ancestor and a descendant as shared, or refuse such overlaps across tools at load in the 22-01 validator |
| R1-17 | 22-09 | HIGH | PARTIAL | Before deleting, resolve the parent chain and refuse when it leaves HOME or enters a harness marker dir; keep unlink-only for a final symlink; add a test |
| R1-18 | 22-10 | HIGH | CONFIRMED | Give `config_split` an explicit state/snapshot argument, and update 22-10 and 22-11 together |
| R1-19 | 22-10 | HIGH | CONFIRMED | Clear `_config_on` on each visit (leave or enter, not on modal cover); add a test that navigates away and back |
| R1-20 | 22-11 | HIGH | CONFIRMED | Build the removal decision once when the modal opens, render it, and pass exactly that to the confirm; fresh checks may only narrow it; add a test that publishes while the modal is open |
| R1-21 | 22-11 | MEDIUM | CONFIRMED | Make the `on_removal_finished` severity `warn` when `swept.warnings` is non-empty and nothing failed |
| R1-22 | 22-12 | HIGH | PARTIAL | Pass the tracked cask tokens into the snapshot query explicitly; define where `greedy_casks()` reads from, with its epoch guard and invalidation on mutation |
| R1-23 | 22-12 | MEDIUM | CONFIRMED | Keep a failed greedy read distinct (None), feed it to `_partial_manager_failure`, and test a transient failure after an outdated result |
| R1-24 | 22-13 | HIGH | CONFIRMED | Make a CLI removal failure exit non-zero; the harness asserts manager receipts are gone; add a self-test with a failed manager uninstall |
| R1-25 | 22-13 | MEDIUM | CONFIRMED | Check receipt-proven must-clear paths for absence whatever the baseline holds; list bootstrap exceptions explicitly |

### Rejected

None. Every concern held up under source grounding: 16 CONFIRMED, 9 PARTIAL, 0 REFUTED (16 HIGH, 7 MEDIUM, 2 LOW).

Unscored reviewer suggestions (not concerns, so no plan change is required): make `HOMEBREW_NO_SUDO` mandatory in 22-08, name the `tests/state_doubles.py` `plan_state` change in 22-04, add the registry-verification tests to 22-05's targeted verify, and extend the 22-06 every-kind test to the Uninstall projection.

CYCLE_SUMMARY: current_high=16 current_actionable=25

## Cycle 1 resolution

Replanned in reviews mode against this file at `b8dad84`. Plan count (13), task count (39), wave count (7) and every plan ID are unchanged; same-wave `files_modified` sets stay disjoint and every cross-wave file overlap has a dependency path (checked mechanically). New `files_modified` entries: 22-04 `tests/state_doubles.py`; 22-06 `installer/engine.py`, `tests/test_setup.py`; 22-07 `tests/test_setup.py`; 22-09 `setup.py`, `tests/test_uninstall_e2e.py`. New `depends_on` edges (no wave moved): 22-06 on 22-04 (both edit `engine.install_tool`), 22-08 on 22-06 (its store test removes through `remove_tool`). Each affected plan carries a `## Review Dispositions Ledger` round for `b8dad84`.

| ID | Plan(s) changed | How resolved |
|---|---|---|
| R1-01 | all 13, 22-VALIDATION | Every "commit the RED tests" step is gone: RED output goes to the SUMMARY only, each task lands as one `feat(22-NN)` commit holding tests and code, `make validate && make test` exit 0 on every commit (ledger row 31); the advisory TDD checkpoint is noted as expected. VALIDATION "File Exists" and sign-off wording follow |
| R1-02 | 22-01 | The `config_paths` acceptance greps are anchored: the 4-space dataclass field and the 8-space `__init__` keyword, each expected once |
| R1-03 | 22-02 | `render_handoff` prints `sanitize_log_line(line)` with `markup=False, soft_wrap=True`; new long-command plus escape-byte test; Task 2 names the executor tests to rewrite (`tests/test_executors.py:38-53`, `:83-87`, `:96-107`) |
| R1-04 | 22-03 | Readers reject only non-null `sha256`/`size`/`mtime_ns`/`key` (absent or null is no value) and a non-null tree `target`; the writer is unchanged; the round-trip test pins the raw JSON shape |
| R1-05 | 22-03, 22-05, 22-06, 22-13 | `record(..., preexisting=)` plus `preexisting_paths(method)`: a declared path that existed before the install or update is recorded only when the previous receipt proved it (repair and reinstall keep their proof); `None` fails closed. Wired in `engine.install_tool` (22-06) and `update._perform` (22-05); fixtures with the helper present before the install at the receipt, engine and update levels. Pre-phase receipts stay unproven until a remove-and-reinstall (truth updated) |
| R1-06 | 22-04 | Mocked tests for a foreign-owned writable parent and an `lstat` `OSError` (both not writable); `pass_state`/`plan_state` gain `unwritable` |
| R1-07 | 22-05 | `_update_installer_owned` gains a required `tool_id` keyword passed by its one caller `_perform`; the error is raised there and the "inside `_perform`" wording is fixed |
| R1-08 | 22-06 | The L3 argv needs at least one receipt-proven artifact (`plan.by_tool` non-empty); `test_an_empty_legacy_script_receipt_never_runs_remove` |
| R1-09 | 22-06 | `removal_order` (reuses `deps.resolve_dependencies`, dependents first, independents keep their order) in both `perform_uninstall` and `run_uninstall`; TUI and CLI tests run `uv tool uninstall ruff` while `uv` exists. Manager kind is covered by `requires` (registry tests force it for uv-tool and node; brew is never removable here) |
| R1-10 | 22-06 | The post-confirm `removal_plan(verify=True)` comparison of paths and argv moves into `remove_tool`, shared by CLI and TUI; `test_the_cli_re_proves_after_the_confirm` |
| R1-11 | 22-06, 22-07 | `_pass` counts a receipt's broken drift as presence for health, so a partly removed tool reads BROKEN and level `none`; an all-gone receipt is retired (G10) and reads MISSING, level `none`; both tested through `VersionRefreshService.refresh`. Planner reading recorded in 22-07's ledger: SPEC:165 "broken" applies when anything recorded is left (see open item below) |
| R1-12 | 22-07 | `tests/test_ownership.py:1844-1860` and `:2662-2677` rewritten to the package-naming hint and `None` with `ripgrep`/`glab` coverage kept; the same change's other breakages are named too (`_FROZEN_REMOVAL` at `:2924-2958`, `tests/test_setup.py:2294`/`:2321`) |
| R1-13 | 22-08, 22-13 | pnpm, bun, Volta and fnm declare only their executables as leaves, never a store root; two registry tests (no store tree; a global package or toolchain survives the manager's removal); 22-08's SUMMARY lists the kept stores and 22-13's allowlist names them, their executables still must-clear |
| R1-14 | 22-08 | Recorded decision: OMZ, SDKMAN and Homebrew stay hint-less this phase (no locked input requires a hint; one would need a new registry key or a per-tool `removal_hint` branch) |
| R1-15 | 22-09 | `perform_uninstall` requires `catalog`; step 4 deletes a path only when every catalog declarer was removed with it listed; `setup._do_uninstall` passes the registry; unselected-owner and flag-off test |
| R1-16 | 22-01, 22-09 | `_refuse_config_overlap` refuses cross-tool ancestor/descendant `config_paths` at load, so 22-09's exact-equality shared-path rule is complete |
| R1-17 | 22-09 | `delete_config_path` resolves the parent with `realpath` and refuses outside the real HOME or under a harness marker; final symlinks stay unlink-only; in-HOME dotfiles links allowed; test |
| R1-18 | 22-10, 22-11 | `config_split(flagged, catalog, state_of)`; the screen passes `self._state_of`; both plans use the three-argument form |
| R1-19 | 22-10 | `UninstallScreen.clear_transient` clears every flag on leave (the one `show_view` path); a modal cover keeps them; `test_flags_start_off_on_every_visit` |
| R1-20 | 22-10, 22-11 | `_decision(ids)` builds the decision (and the kept map) once before `ConfirmUninstall` opens; the confirm hands that object to `_apply_removal`; the review renders from it; `test_a_refresh_while_the_modal_is_open_keeps_the_decision` |
| R1-21 | 22-11 | Severity: `error` on `remove_failed` or `config_not_deleted`, else `warn` on a terminal warning or `swept.warnings`, else `ok`; tested |
| R1-22 | 22-12 | `_pass` computes the tracked cask tokens and passes them through `_load_or_query_snapshot(..., casks=)` to `read_outdated`; `greedy_casks()` reads `_greedy`, written in the publish block under the epoch guard; `invalidate` deliberately leaves it (it names casks that auto-update, which no mutation changes); test |
| R1-23 | 22-12 | A failed greedy read returns `greedy=None` and `cask=None`, `_partial_manager_failure` reports it, the previous facts are kept with the 30-minute retry; two tests |
| R1-24 | 22-06, 22-13 | `run_uninstall` returns the failed ids and `_run_uninstall` exits 1; the harness writes `removable-receipts.txt` before the uninstall and `assert_removed_receipts_gone` fails on a left one (self-test with a left manager receipt); Task 3's verify requires `TRACER_RECEIPTS_GONE_OK` |
| R1-25 | 22-13 | Recorded receipt paths are checked against the whole after listing, baseline or not; declared paths stay new-only; the bootstrap exception list is explicit and empty, with the reason (a receipt never records a pre-existing path, R1-05); test |

Open items for the orchestrator:
- R1-11: with nothing recorded left (the opencode anchor's single path, deleted by its own `remove`), the pass retires the receipt and the tool reads MISSING, not BROKEN. Not removable and nothing re-run hold in both cases. SPEC:165 may be amended to "broken when anything recorded is left; retired when nothing is", or the reading accepted as is.
- R1-14 and R1-22's "invalidation on mutation" were resolved by recorded decisions rather than new code; each plan's ledger gives the reason.
