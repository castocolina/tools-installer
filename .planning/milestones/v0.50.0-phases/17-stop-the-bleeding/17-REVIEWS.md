---
phase: 17
cycle: 3
reviewers: [opencode-plan-review]
reviewed_at: 2026-10-14T21:33:59Z
plans_reviewed: [17-01-PLAN.md, 17-02-PLAN.md, 17-03-PLAN.md, 17-04-PLAN.md, 17-05-PLAN.md, 17-06-PLAN.md, 17-07-PLAN.md, 17-08-PLAN.md, 17-09-PLAN.md, 17-10-PLAN.md, 17-11-PLAN.md, 17-12-PLAN.md, 17-13-PLAN.md]
models:
  opencode-plan-review: "router-env/my-plan-review"
model_sources:
  opencode-plan-review: "pinned"
---

# Cross-AI Plan Review — Phase 17

<!-- gsd:plan-revision-conflicts:begin -->
## Plan-Revision Conflicts
<!-- gsd:plan-revision-conflicts:end -->

## OpenCode Review (opencode-plan-review)

### Cross-AI Plan Review — Phase 17, Convergence Cycle 3 (final)

**Verification method.** I read the cycle-2 review (`git show 5b7bc37:.planning/phases/17-stop-the-bleeding/17-REVIEWS.md`), the RUN-LEDGER decisions, and the e72ce68 revision diff, then traced every revision-load-bearing claim plus a fresh sample of the underlying claims to live source with CodeGraph and targeted reads. Key verifications: `installer/settings.py:112-116` (assign-then-save today), `setup.py:755-769/800-801/1000/1214-1281/1289-1458` (routes, `execute` param, exit lines, def adjacency), `installer/wizard_app.py:2676-2680/2790-2794/2924-2976` (`show_view` early return, exit-with-ids, summary merge), `installer/uninstall.py:56-97/259-330`, `installer/download.py:144/189-190/403-404`, `installer/apps.py:100`, `installer/run.py:88/232-241`, `installer/executors.py:41/335/371-379`, `installer/doctor.py` (whole), `installer/guidance.py:104-139`, `installer/app.py:346-360/418-448/515-556`, `installer/atomic.py:117-130`, guards/tweaks write-site greps, `installer/session.py:105-113`, `installer/update.py:151-160/308`, `installer/execute_screen.py:573-656/897-956`, `installer/policy.py:120-158`, `installer/registry.toml:166/1592/2266-2281/1345-1352`, `model.py:20-22`, `postinstall.py:250-280`, `.github/workflows/ci.yml`, both 16-milestone records, the 16-17/18/19 plans (threat IDs, task counts 6/8/4, waves 8/9/10, collision confirmed), `scripts/container-e2e-verify.sh:423-487`, and the named test seams (`tests/conftest.py:26-28`, prune scripts :101/:196-239, `test_catalog_tui.py:1162-1184/2013-2035`, `test_settings.py:173-178`, `test_atomic.py:23/40/46/59`, `test_run.py`, `test_engine.py:197-198`, `test_apps.py:50-60`, `test_download.py:479-489`, `test_wizard_app.py:7185`, `catalog_tui.py:1040-1042`). What I could not independently verify (macOS/CI-runner behavior, remote vendor scripts, network probe outcomes) carries its in-plan oracle and is marked below.

---

## 17-01

**Summary:** CI-repair plan whose owner_cell fix (the one cycle-1 MEDIUM) is now fully source-grounded: I re-confirmed `_offline_service` already accepts `which`/`artifacts_for` and hard-codes `read_inventory_fn=_empty_inventory` at tests/test_catalog_tui.py:1184, so the added optional keyword drops in as specified; the current test seeds `service._ownership` and derives the expected label from `owner_label(ownership)` (tests/test_catalog_tui.py:2013-2035) — exactly the tautology the revision removes. The bash-3.2 failures (`mapfile` at scripts/prune-tmp-linux.sh:101; `-regextype posix-extended` and the empty `"${find_type[@]}"`/`"${fd_type[@]}"` expansions under `set -u` at scripts/lib/prune-tmp-common.sh:203-236) and the `os.sched_getaffinity`/hasattr pyright-Darwin gap (tests/conftest.py:26-28) are all real and line-accurate.

**Round-2 status:** No round-2 finding was upheld for this plan (the "sibling test :2827" citation was refuted by the orchestrator; 17-REVIEWS.md:365). Nothing to rule on.

**Strengths:**
- Every shell fix named is in the code at the cited lines; the `find | grep -E "^${pattern}$"` rewrite preserves the anchored full-path match set (pattern already anchored by the escaped root, scripts/prune-tmp-linux.sh:95-101), and the near-miss/too-young survivors are asserted in the container run (T-17-01).
- The time-shells0 change matches the existing parametrization and loop exactly; `_run_updates`-style `Path(shell).resolve().name == "dash"` derivation is sound.
- The wave-1 CI oracle (temporary branch + draft PR, ci.yml triggers verified: push-to-main/pull_request only) gates all macOS assumptions before wave 2 starts.

**Concerns:**
- LOW (residual, non-actionable): the bash:3.2 image's `find` provenance (busybox vs GNU) is asserted, not proven — but the fixed script's `find | grep -E` form works on either, and the container verify is self-proving.
- LOW (carried from cycle 1, dispositioned): the `fixture_runner` extraction-call heuristic and whole-archive extraction notes belong to 17-02.

**Suggestions:** None.

**Risk Assessment:** **LOW-MEDIUM** — macOS-only assumptions remain, but they are fenced by the wave-1 CI oracle before anything builds on them.

## 17-02

**Summary:** Unchanged since cycle 2 and still verified end to end: shelled `chmod +x`/`ln -sf` at download.py:189-190 and :403-404 and apps.py:100; the exact inline expression `bin_name or PurePosixPath(target.member).name` at download.py:144 (and its update-path twin) that `link_name` extracts; `replace_symlink` at atomic.py:117-130; the engine ladder already catching `ExecutorError` (engine.py:151) so no engine change is needed.

**Round-2 status:** No findings; nothing to rule on.

**Strengths:**
- One helper (`link_executable`) + one shared test runner (`fixture_runner`), with `chmod=False` at the app site a verified behavioral preservation (install_app never chmods inside a bundle).
- Whole-file acceptance greps (`\["ln"` = 0 in download.py/apps.py) close any fourth linking site.
- The reinstall-over-link-to-directory test pins the actual H1 damage mode (write-through), not just the guard.

**Concerns:** None new.

**Suggestions:** None beyond the carried cycle-1 note (document the extraction heuristic in `fixture_runner`'s docstring).

**Risk Assessment:** **LOW.**

## 17-03

**Summary:** Unchanged and verified: `popen_with_env` (run.py:232-241) has `stdin=DEVNULL` but no `start_new_session`; `run_output`'s `subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=...)` at run.py:88 inherits both — the update-path gap SPEC R7 names. The sudo builders that will fail fast under a new session exist at executors.py:371-379, matching T-17-42.

**Round-2 status:** No findings; nothing to rule on.

**Strengths:**
- The `getsid` discriminating test plus the alarm-guarded `/dev/tty` reader is the right pair (under pytest there is no controlling tty either way — the plan says so).
- `_PopenKwargs` keyword pinning keeps every Popen double honest; `run_command`/`run_interactive_command` untouched.
- The known-until-Phase-22 sudo regression is recorded in-plan (T-17-42), in the SUMMARY instruction, and surfaced at phase level in 17-13's baseline section.

**Concerns:** None new.

**Suggestions:** None.

**Risk Assessment:** **LOW.**

## 17-04

**Summary:** Additive read-only Doctor scan; all interface claims verified: `DoctorReport(missing, broken, duplicated)` frozen (doctor.py:8-12) so an appended defaulted field keeps the equality test valid; `has_problems` at :30; `doctor_guidance`'s `[_HEALTHY]` early return (guidance.py:119-120); `_tui_guidance` rewriting next_steps starting ``Run `make fix` ``/``Run `make setup` `` (wizard_app.py:599-630, confirmed by grep); the single wiring point `doctor_data` (app.py:346-360) consumed by both `run_doctor` and `_build_app`.

**Round-2 status:** **RESOLVED.** Cycle-2 LOW (relative fixture targets would resolve under `bin/`): Task 1's behavior now plants `bin/subl` with "the ABSOLUTE target `str(opt_dir("subl") / "sublime_text")`" and creates the directory first; Task 2's ghost fixture uses the absolute `str(opt_dir("ghost") / "ghost")`, each with the rationale spelled out. The mechanism (`normpath` of the target joined to `entry.parent`) makes the absolute form the only one that satisfies the expected `kind`/`opt_dir` — the revision is correct.

**Strengths:**
- Two-branch wording (opt-dir repair only when the normalized target lies inside `opt_dir(name)`; remove-the-link otherwise) is correct for uv/pnpm shims and never tells the user to delete an opt dir the link does not point into.
- Zero-execution enforced by a before/after tree snapshot test; `shlex.quote` covers copy-paste injection; no sudo/pkexec/doas with a dedicated never-escalates test.
- The flagged assumption about the SPEC's executor argv scan (belongs to Phase 22) is surfaced explicitly rather than silently dropped.

**Concerns:** None new (fifo/socket skip and dangling-normpath notes were cycle-1 accepted dispositions).

**Suggestions:** None.

**Risk Assessment:** **LOW.**

## 17-05

**Summary:** Still fully verified against the registry and hook code: `postinstall = "graphify-register"` at registry.toml:1592; Sublime's two Linux tarballs with `member = "sublime_text"` + `bin_name = "subl"` + `archive = "xz"` (~:2266-2281); codex's script method with no `env` yet (~:1345-1352); homebrew's `env = { NONINTERACTIVE = "1" }` pattern at :166; `POSTINSTALL_HOOK_NAMES` with all three names (model.py:20-22) and the hook code at postinstall.py:250/258/280. The update-path dispatch claim is correct — `warning = _run_postinstall(target, method, runner, tools, postinstall)` runs after an update (update.py:~308), so removing the registry key disables both paths.

**Round-2 status:** No findings; nothing to rule on.

**Strengths:**
- Probe-first with a stop condition that defers to the orchestrator if the evidence contradicts RESEARCH; network-failure fallback already decided by RUN-LEDGER Q1.
- Dead-code deletion (hook, name, tests, architecture.md row) follows architecture rule 5; the dictated replacement comment deliberately avoids the strings the acceptance `git grep` bans.
- Parity sets shrink together, so the test_model/test_post_install comparisons stay aligned without edits.

**Concerns:**
- LOW (residual, in-plan): the container probe's `pip install graphifyy==0.9.54` is network-dependent; the fallback (record error, proceed per Q1) is specified. Non-actionable.

**Suggestions:** None.

**Risk Assessment:** **LOW-MEDIUM** (network-dependent probe; everything else is deterministic).

## 17-06

**Summary:** Verified: all ten write sites exist as listed (guards.py `write_text` at 388, 392, 425, 448, 472, 554, 564 with `chmod(0o755)` pairs; tweaks.py 254-255, 297, 308); `clean_rc_duplicates` today previews with `read_text()`, applies stale indices, and writes with `write_text` (app.py:418-448); the atomic property tests cited for reuse exist at tests/test_atomic.py:23/40/46/59. The mode counts in the acceptance greps match the real site counts (5 shim sites in guards.py, 1 in tweaks.py).

**Round-2 status:** No findings; nothing to rule on.

**Strengths:**
- Ponytail test economy is real: atomic properties proven once on `atomic_write_text`, routing enforced by `.write_text(` = 0 greps — no per-call-site duplication.
- The D-06 byte-exact recheck (including the trailing-newline edge) plus the cycle-1-added deleted-file-at-confirm refusal (`except OSError` → same "changed" branch, never recreate) close both stale-index failure modes.
- No-op branches and ownership checks (`is_our_shim`, `_is_our_executable`) explicitly untouched.

**Concerns:** None new.

**Suggestions:** None.

**Risk Assessment:** **LOW.**

## 17-07

**Summary:** Verified against the worker's real shape: `_execute_worker` (execute_screen.py:573+) initializes `summary = summarize([])`, `outcomes = []`, `not_attempted = [all ids]`, and its `if result is None: error = message` branch leaves exactly that empty state — the bug the plan describes; `on_install_run_finished` then marks those rows "skipped" at :914-915 and always writes green "Done." at :953; `InstallRunFinished` carries the fields the fold needs (:335-372); `Summary` ends at `manual_required` (session.py:105-113) so three appended defaulted fields keep ~22 constructions valid; `UpdateOutcome.status` is the closed Literal claimed (update.py:151-160); the wizard merge is field-wise (wizard_app.py:2924-2976); the exit conditions at setup.py:1275 read exactly `summary.failed or summary.mismatched or summary.dependency_failed`. `_run_updates` returns its four collections only at the end with the cancel check at loop top — the accumulator rewrite's target is real.

**Round-2 status:** No findings for this plan (the cycle-2 17-07 note was ruled "Already in plan", 17-REVIEWS.md:366).

**Strengths:**
- Both stop paths (run_live-caught and escaping exception) rebuild from one accumulator; `_partial_run` is pure and reused by both.
- The cancel test pins the D-08-locked semantics precisely (completed updates kept, unrun ids in `not_attempted`, `crash_error` None, `update_failed` empty, `has_failure` True) — the ledger correctly rejected the reviewer's `has_failure False` suggestion.
- `has_failure`/`fold_run` live in installer/ per architecture rule 4; setup.py only reads it.

**Concerns:** None new.

**Suggestions:** None.

**Risk Assessment:** **LOW-MEDIUM** (threaded worker surgery, but every path has a named test including the parametrized RuntimeError/OSError pair).

## 17-08

**Summary:** The cycle-2 MEDIUM lives here now, correctly. I verified the premise (settings.py:112-116 assigns `self._link_mode = value` before `save_settings(...)`, and `setup.py:800-801`/`:1000` wire `_current_link_mode`/`set_link_mode` onto that store), the fix (Task 2 swaps the two lines; `files_modified` now includes installer/settings.py with an artifact and key_link), the wave safety (17-08 is wave 3; the only other wave-3 plans — 17-09, 17-10 — touch neither settings.py nor its tests), and that no existing test pins the old order: `test_set_link_mode_propagates_oserror` (tests/test_settings.py:173-178) asserts only the raise, and `test_set_link_mode_is_live_and_persisted` asserts only the post-success state, so 17-08 needs no test_settings.py edit. Both raise-path tests now drive a real `SettingsStore` with `save_settings` patched to fail — the reorder is RED under today's setter, exactly as the plan states.

**Round-2 status:** **RESOLVED.**
- MEDIUM `set_link_mode` save-order — **RESOLVED**, with evidence: premise confirmed at installer/settings.py:112-116 (current order: validate → assign → save); 17-08-PLAN Task 2 (e72ce68) performs the swap, adds the `save-first` awk acceptance gate, real-store rollback tests, and the corrected rollback premise text ("the setter raises before it assigns the live mode"); 17-11 Task 2 keeps the order and adds only the warning-clear last, with its own sequencing gate (`save_settings(|self._link_mode = value|self._warning = None`). The orchestrator's placement decision (17-08, not 17-11) is sound: 17-11 is wave 4 and depends on 17-08.
- Cycle-1 items (recovery re-set rollback, `_link_mode_status` naming failures) were already in the plan and are unchanged.

**Strengths:**
- `link_mode_aware` appended after `owned` honors the frozen-dataclass append-only comment (policy.py:146-158, verified); the flag set (ban, tweak, macOS cache redirect only) matches RUN-LEDGER Q2, and `active_policies` genuinely cannot serve as the filter (it rebuilds from bundles, uninstall.py:401+).
- The two raise paths share one private rollback helper; the re-set-failure path stops the loop instead of emitting false `moved` entries (T-17-44).
- `_link_mode_status` used by both pickers prevents console/TUI wording drift; severity warn on partial failure is the honest middle.
- macOS `cache_redirect_policy` remove-mode-independence is flagged for the executor to verify rather than assumed.

**Concerns:**
- LOW (observation, not actionable): between `set_link_mode(old_mode)` and the final `set_link_mode(new_mode)` in the apply-failure restore, the store briefly advertises the old mode; every reader in that window is this same synchronous function on the UI thread, so there is no observable inconsistency.

**Suggestions:** None.

**Risk Assessment:** **LOW-MEDIUM** — the failure matrix is now fully specified and pinned to the production setter; residual risk is implementation slip in the rollback helper, which the two real-store tests would catch.

## 17-09

**Summary:** Verified: `plan_uninstall`'s member-basename + traversal-guard + declared-`bin_dir` logic (uninstall.py:84-96) is exactly what `_download_link` extracts; `classify_tools` currently calls `plan_uninstall([tool], ...)` per tool; `run_uninstall` starts from `paths = plan_uninstall(tools, default_bin_dir)`; the lenient callers that must keep working are real (version_status.py:594, setup.py:1108); `UninstallState` rows and the REMOVABLE-only selectable gate (wizard_app.py:993) match; the current tests asserting the `ln`/`chmod` argv (test_apps.py:50-60, test_engine.py:197-198) and the name-match fixtures are correctly targeted for rewriting.

**Round-2 status:** No findings for this plan; nothing to rule on.

**Strengths:**
- One predicate shared by TUI and `--yes` with a same-set test (T-17-26) — the strongest possible closure of the H3 trust boundary.
- `link_name` dedupes the naming rule across install/update/uninstall, which is what makes Sublime's `subl` ever removable; `plan_uninstall` stays lenient for its three evidence-only callers.
- The accepted regression (app bundles and raw files not removable until Phase 19 receipts) is explicit, and its e2e evidence shift is recorded in 17-13's baseline section.

**Concerns:** None new.

**Suggestions:** None.

**Risk Assessment:** **LOW-MEDIUM** (temporary removability regression is user-visible but documented and test-pinned).

## 17-10

**Summary:** Verified: `_build_app` still has `execute: ExecuteInputs | None = None` (setup.py:755-769) and the four routes call it bare with `initial_view` "doctor"/"doctor"/"uninstall"/"policies" and return literal 0 (setup.py:1289-1296, 1322-1332, 1348-1357, 1436-1448); `on_catalog_screen_decided` exits with ids when `self._execute is None` (wizard_app.py:2790-2794); the test to delete exists (tests/test_wizard_app.py:7185); `_execute_inputs` has the exact signature the plan reuses (setup.py:1166-1211); the `^def` adjacency the acceptance sed ranges rely on holds (`_run_interactive_wizard` 1214 → `_settings_store` 1281, no other top-level def between); `catalog_tui.py:1040-1042` already has the empty-selection message.

**Round-2 status:** **RESOLVED.** Cycle-2 LOW (route pilots must navigate to the catalog): Task 1's doctor pilot and Task 2's parametrized route test now both call `await app.show_view(BASE_VIEW)` and assert `current_view == BASE_VIEW` before selecting. `show_view`'s early return when `name == self.current_view` (wizard_app.py:2676-2680) makes the setup-route call a genuine no-op, so one code path serves all five ids. Correct.

**Strengths:**
- Removing the parameter (not passing `execute=` at four routes) closes the bug class; `inspect.signature` test enforces it structurally.
- One `_hermetic_route` helper (scratch PATH, `systemd_available` False, Linux platform, TTY patches, seam-injected install recorder) makes the route pilots safe by construction and is reused by 17-11.
- One exit rule (`_session_exit_code`) for all five routes; the wizard keeps its abort and `clean_rc_duplicates` steps.
- The shared-cache invariant survives: `_build_app` already resolves `timer_cache` once when both are omitted (setup.py:770-778), and the wizard stops building its own.

**Concerns:** None new.

**Suggestions:** None.

**Risk Assessment:** **LOW-MEDIUM** (widest `setup.py` surgery of the phase, but every route has a pilot test and the exit rule is centralized).

## 17-11

**Summary:** Verified: `load_settings` calls `path.read_text()` and catches only `(OSError, json.JSONDecodeError)` (settings.py:54-55), so `UnicodeDecodeError` escapes today — the crash premise holds; `_settings_store` is the single caller; `UnifiedApp.__init__` ends with `prompt_link_mode`/`terminal_sync` (wizard_app.py:2445-2446) so appending `startup_warning` is append-safe; `_pending_warnings`/`_flush_pending_warnings` exist (wizard_app.py:2471, 2714-2717) for the reuse the plan mandates; the launch test correctly reuses 17-10's `_hermetic_route` (17-11 is wave 4 and depends on 17-10).

**Round-2 status:** **RESOLVED.** The cycle-2 MEDIUM (this plan edits `set_link_mode` without fixing the order) is split correctly: the reorder itself lands in 17-08 (wave 3, whose rollback contract needs it — 17-REVIEWS.md:375's wave-2 assumption corrected per RUN-LEDGER), and this plan now *keeps and asserts* the order: Task 2's action says "keep plan 17-08's order and add the clear last", the failed-save test also asserts `link_mode` stays `"centralized"`, and the acceptance awk demands exactly `save_settings(|self._link_mode = value|self._warning = None`. Scope also matches RUN-LEDGER (warn only on invalid UTF-8/invalid JSON; the two dropped-extension tests carry no warning assertion, enforced by grep).

**Strengths:**
- One read, one parse, typed result — D-11's rejected duplicate-probe option stays rejected (single-`read_text` grep enforced).
- The invalid-on-disk flag clears only on a successful user change, and the launch byte-equality test covers the "never rewrite a damaged file" invariant including the dismissed-picker path.
- The dismissed-picker message keeps the warning via the same " · " join `_flush_pending_warnings` uses, so erasing the only notice is impossible.

**Concerns:** None new.

**Suggestions:** None.

**Risk Assessment:** **LOW.**

## 17-12

**Summary:** All planning facts verified against the milestone directory: 16-SECURITY.md has `T-16-SC (x16)`, footer "Total register rows: 60", AR-16-08 for plans 16-01..16-16, `threats_open: 0`; 16-VALIDATION.md is `audited: "2026-10-10"` with no 16-17-0x/16-18-0x/16-19-0x rows; all six 16-1x PLAN/SUMMARY files exist; the threat sets are exactly as claimed (16-17: T-16-45..48, 6 tasks; 16-18: T-16-49..53, 8 tasks; 16-19: T-16-49..51 — a different three, 4 tasks; waves 8/9/10), so the collision handling (qualified IDs + note) is necessary and correctly designed. The footer arithmetic checks out (65 after Task 1; 75 = 56 + 19 after Task 2).

**Round-2 status:** No findings; nothing to rule on.

**Strengths:**
- Evidence cited as `file::symbol` + pytest node id (not line numbers), so rows survive later Phase 17 edits to the same files — and 17-13 Task 1 re-runs every recorded command on the final tree, closing the deleted-cited-test hole.
- Read-only discipline enforced by `git show --stat` per commit; open-`high` stop rule prevents paper closures.

**Concerns:**
- LOW (residual, non-actionable): the verify's `grep -o "uv run pytest[^\`]*" | eval` loop trusts that each recorded command sits on one table-cell line; 17-12 writes those rows itself in the same format its own extraction reads, so it is self-consistent by construction.

**Suggestions:** None.

**Risk Assessment:** **LOW.**

## 17-13

**Summary:** Verified: ci.yml triggers on push-to-main and pull_request only, with job name `validate & test on ${{ matrix.os }}` producing the two required contexts; `concurrency.cancel-in-progress` is per-ref so the temporary-branch oracle is unaffected; `scripts/container-e2e-verify.sh` exists and writes `TRACER_REINSTALL_OK` into `pass2-transcript.log` (:423, :474, :487), matching the baseline-extraction command; the Step-0 numbers match RUN-LEDGER (installed=45 already=1 on 72c9047); the D-17 checkpoint is `blocking-human` with the autonomous-run skip answer pre-recorded exactly as the Task 3 check parses it.

**Round-2 status:** **RESOLVED.** Cycle-2 LOW (cwd-relative pathspec): Task 1's oracle-sha check now uses `":(top)" ":(top,exclude).planning"` — magic pathspecs anchored at the repo root regardless of cwd, and the exclude subtracts from the union of the two pathspecs, giving exactly "HEAD differs from the oracle commit only under `.planning/`". Correct.

**Strengths:**
- The full publication ordering is enforced structurally: no task pushes main (region-scoped prohibition grep), pre-verify CI rides a deleted-after-use temporary branch, and the post-verification main push is an orchestrator step with its own recorded check.
- Both behaviour shifts the reviews asked to surface (17-09's already= rise, 17-03's sudo fail-fast) live in one SUMMARY section with an automated check.
- The skip path is verified against GitHub's live state (404 "Branch not protected"), not just against the SUMMARY text.

**Concerns:**
- LOW (external, dispositioned twice already): the 2026-10-19 Ubuntu-26 runner migration could redden the ubuntu job for environment reasons; Task 1's triage rule (compare runner image first) is the right containment and cannot be planned further.

**Suggestions:** None.

**Risk Assessment:** **MEDIUM** — inherent to a plan whose subject is external CI and a user-action gate, but every step has a re-runnable check and a stop rule; no design weakness remains.

---

## Overall

**Unresolved HIGH: 0.**

All four cycle-2 findings are **RESOLVED** with verified evidence: 17-08/17-11 `set_link_mode` save-order (premise confirmed at installer/settings.py:112-116; reorder lands in 17-08 Task 2 with real-store RED tests and a `save-first` gate; 17-11 keeps and asserts the order; wave placement safe); 17-04 absolute fixture link targets (both fixtures now state the absolute target with the normpath rationale); 17-10 route pilots navigate to the catalog first (`show_view(BASE_VIEW)` + `current_view` assert; early-return verified at wizard_app.py:2676-2680); 17-13 root-anchored pathspec (`:(top)`/`:(top,exclude).planning)`). The e72ce68 revisions introduced no new inconsistencies: `files_modified` sets remain conflict-free within every wave (17-08's added installer/settings.py has no same-wave competitor), every verify-count and acceptance grep I recomputed matches the behavior lists, and the cited line references in the revised text match source.

**Unresolved actionable MEDIUM/LOW concerns:** None. The residual notes above (17-01 macOS/bash-image assumptions gated by the wave-1 CI oracle, 17-02's carried fixture_runner heuristic, 17-05's network-dependent probe with a decided fallback, 17-08's transient in-function mode flip, 17-12's self-consistent command extraction, 17-13's external runner migration) are all either already dispositioned in a Review Dispositions Ledger or carry an in-plan oracle; none requires a PLAN.md change.

**Verdict: approved for execution.** The phase goal coverage is complete (SAFE-01..09, CI-01..03 all owned by named plans with tests), the wave DAG is sound (17-06←17-01/17-04, 17-07←17-01, 17-08←17-06/17-07, 17-09←17-02/17-06, 17-10←17-07, 17-11←17-08/17-10, 17-13←all), and RUN-LEDGER decisions are implemented rather than re-litigated. Overall phase risk: **LOW-MEDIUM**, concentrated where it belongs — external CI and the two worker/rollback rewrites, each fenced by the tests named above.

---

## Consensus Summary

Convergence cycle 3 (final): plans revised in e72ce68 against cycle 2 (5b7bc37). Single reviewer (opencode-plan-review, source-grounded: `file:line` evidence throughout, every plan id 17-01..17-13 has its own section), so there is no cross-reviewer consensus to compute and the consensus gate does not engage. Verdict: **approved for execution, 0 HIGH, 0 unresolved actionable concerns.** All four cycle-2 findings are ruled RESOLVED.

Orchestrator verification of the round-2 rulings (checked against the tree before recording):
- **Confirmed RESOLVED** — 17-08/17-11 MEDIUM `set_link_mode` save order: `installer/settings.py:112-116` still assigns before `save_settings` today; 17-08-PLAN.md now lists `installer/settings.py` in `files_modified`, swaps the lines in Task 2 and gates it with the `save-first` awk check (17-08-PLAN.md:191); 17-11 keeps the order and asserts `save_settings(|self._link_mode = value|self._warning = None`. Wave 3 peers 17-09/17-10 do not touch `installer/settings.py`; 17-11 (wave 4) depends on 17-08, matching the RUN-LEDGER cycle-2 row.
- **Confirmed RESOLVED** — 17-04 LOW: both fixtures state absolute targets (17-04-PLAN.md:108, :146).
- **Confirmed RESOLVED** — 17-10 LOW: both pilots call `await app.show_view(BASE_VIEW)` and assert `current_view` (17-10-PLAN.md:114, :149); `show_view` returns early when already on the view (`installer/wizard_app.py:2676-2680`).
- **Confirmed RESOLVED** — 17-13 LOW: 17-13-PLAN.md:119 uses `":(top)" ":(top,exclude).planning"`; tested from `installer/` and `tests/`: a `.planning`-only range exits 0, a code-changing range exits 1 and lists root-level paths.

New findings: none actionable. The reviewer's residual LOW notes (17-01 bash:3.2 `find` provenance, 17-05 network-dependent probe, 17-08 transient in-function mode flip, 17-12 single-line command extraction, 17-13 Ubuntu-26 runner migration) are each marked non-actionable by the reviewer and are already covered by an in-plan oracle, fallback or Review Dispositions Ledger entry. No new finding needed refuting.

### Agreed Strengths
- (single reviewer) Round-2 revisions are source-faithful: the reorder premise, wave placement, absolute fixture targets, `show_view` no-op path and root-anchored pathspec all match the code.
- (single reviewer) `files_modified` stays conflict-free within every wave after 17-08 gained `installer/settings.py`; SAFE-01..09 and CI-01..03 coverage complete.
- (single reviewer) RUN-LEDGER decisions are implemented, not re-litigated.

### Agreed Concerns
None (one reviewer; no unresolved actionable concerns).

### Divergent Views
None (one reviewer).
