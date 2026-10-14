---
phase: 17
cycle: 2
reviewers: [opencode-plan-review]
reviewed_at: 2026-10-14T21:14:13Z
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

### Cross-AI Plan Review — Phase 17, Convergence Cycle 2

**Verification method:** I read the cycle-1 review (`17-REVIEWS.md`, commit d702a38) and `RUN-LEDGER.md`, then verified the revised plans against the live tree with CodeGraph and targeted reads. Every revision load-bearing claim was traced to source: the `_offline_service` seams (`which`/`artifacts_for`/`read_inventory_fn` all already exist, tests/test_catalog_tui.py:1169-1184), `_tool("rg")`'s brew method (:115), `resolve_ownership`'s candidate→`attribute_path`→single-candidate-direct path (ownership.py:561-632, 983-992), the `_execute_worker`/`_run_updates`/`on_install_run_finished` shapes (execute_screen.py:573-728, 897-957), the cancel-sweep in the handler (:914-918), `Policy`'s append-only rule and both pickers (policy.py:120-158, wizard_app.py:1630-1634, 2179-2194, 2759-2788), `_current_link_mode` and the ban/tweak closures (setup.py:800-801, 916-923), `SettingsStore.set_link_mode` (settings.py:112-116), `clean_rc_duplicates` (app.py:418-448), `plan_uninstall`/`classify_tools`/`_plan_app`/`remove_paths` (uninstall.py:33-97, 259-348), `_build_app`/`_execute_inputs`/all routes (setup.py:755-769, 1134-1135, 1166-1211, 1289-1458), the prune scripts line-by-line (prune-tmp-linux.sh:101-115, prune-tmp-common.sh:196-239), conftest.py:26-28, test_shellrc.py:2650-2679, doctor.py:8-32, guidance.py:104-139, `_tui_guidance` (wizard_app.py:599-629), `POSTINSTALL_HOOK_NAMES` (model.py:20-22), registry.toml entries (:166, :1329, :1592, :2272-2281), ci.yml:3-21, container-e2e-verify.sh:423-474, and the 16-SECURITY/16-VALIDATION structure and totals. What I could not independently verify (macOS-only behavior, CI run history, remote vendor scripts) is marked as such and carries its in-plan oracle.

---

## 17-01

**Summary:** CI-repair plan, unchanged in structure from cycle 1 except Task 3's owner_cell fix, which now implements the reviewer-preferred alternative (brew-owning inventory + `artifacts_for=lambda _t: []` + brew-prefix `which`, pinned literal `"Homebrew"`). I verified the whole revised mechanism end to end against source: it resolves brew/direct and is deterministic with or without the mount-time refresh worker.

**Round-1 status:**
- owner_cell propagation tautology (MEDIUM) — **RESOLVED.** Task 3 now builds the record through the refresh itself: `_offline_service` already accepts `which` and `artifacts_for` (tests/test_catalog_tui.py:1169, 1171) and already passes `read_inventory_fn=_empty_inventory` to `VersionRefreshService` (:1184), so the added optional keyword drops in exactly as specified. `_tool("rg")` carries `Method(kind="brew", params={"formula": "rg"})` (:115), so `_collect_candidates`' brew branch fires on `brew_formulae={"rg": "1.0"}` (ownership.py:983-992); `attribute_path` attributes `tmp_path/brew/bin/rg` under `brew_prefix` (owner_dirs, ownership.py:446-448); the single-candidate branch returns owner `brew`, confidence `"direct"` (ownership.py:615-632); `owner_label` → `OWNER_LABELS["brew"] = "Homebrew"` (:1153, :1194-1206). `dangling_shim` needs a node method (status.py:108-113) — none on this tool, so `broken=False`. The acceptance greps (pinned `"Homebrew"`, 0 `owner_label(` calls) now enforce the semantic value, not propagation.
- BSD `find` flags assumed (LOW) — **RESOLVED** as a documented assumption (A1) fenced by the wave-1 CI-oracle gate before wave 2 (17-01 `<verification>`).
- `_prune_common_find_matches0` header comment (LOW) — **RESOLVED:** Task 1's action now says to update the header comment to "-name only."

**Strengths:**
- Both RED reproductions are real (cycle-1 reproduced pyright-Darwin at conftest.py:26-28 and the bash-3.2 double failure; I re-confirmed `mapfile` at prune-tmp-linux.sh:101, the empty-array expansions and GNU-only `-regextype` at prune-tmp-common.sh:203/:209/:211/:228/:234/:236 — every line claim in Task 1 is accurate).
- The `sys.platform == "linux"` narrowing is the correct pyright mechanism, and the worker-cap math is untouched.
- The time-shells0 change fits the existing loop exactly (test_shellrc.py:2653 parametrization, `shutil.which(name)` at :2665, assertion message style at :2676-2679); the `Path(shell).resolve().name == "dash"` derivation is sound.
- The wave-1 CI-oracle orchestrator step is correctly gated before wave 2.

**Concerns:**
- **LOW — the "sibling test" citation is inaccurate.** Task 3 says to supply systemd availability "as the sibling test at `test_setup.py:2827` does" — that test (`test_build_app_omitted_arguments_still_share_one_cache`, :2827-2851) achieves availability by patching `setup.shutil.which` to find `systemctl` (:2842-2845) plus a fake unit dir, not by patching `systemd_available`. The *prescribed* mechanism is nonetheless sound: all three call sites invoke it keyword-only (`which=` — setup.py:385, :429, :624), so `lambda **_kwargs: True` works. Citation nit only.
- **LOW — Task 3's route-pilot `--guard`/`--fix`/`--uninstall`/`--doctor` routes open on non-catalog initial views** (see 17-10's concern NEW-C; it applies to this plan's doctor-route pilot too).

**Suggestions:**
- Fix the sibling-test parenthetical to name the actual seam (`setup.systemd_daemon.systemd_available`, verified keyword-only at setup.py:624) so the executor doesn't hunt for a patch form that doesn't exist in :2827.

**Risk Assessment:** **LOW-MEDIUM** — the MEDIUM revision is verified correct in detail against source; residual risk is the macOS-only assumptions, which the wave-1 oracle gates before anything builds on them.

---

## 17-02

**Summary:** Unchanged from cycle 1 (no actionable findings then; none now). The three linking sites, the shared-helper design, and the engine contract are all verified: shelled `chmod +x`/`ln -sf` at download.py:189-190, `install_download`'s `bin_name or PurePosixPath(target.member).name` at :144 (the exact inline expression `link_name` extracts), `replace_symlink` (atomic.py:117-130, temp suffix `.tools-installer.tmp` at :31 — the failure test's "no temp sibling" assertion matches the real suffix).

**Round-1 status:**
- fixture_runner substring heuristic (LOW) — **NOT ADDRESSED** (cycle-1 deemed it acceptable and bounded; unchanged).
- tar-flow extracts whole archive (LOW) — **NOT ADDRESSED** (test-design care for the executor; unchanged).

**Strengths:**
- One helper + one shared test runner, with `chmod=False` at the app site a verified behavioral preservation.
- The Sublime-shaped test (member `sublime_text/sublime_text`, `bin_name="subl"`) matches the verified archive layout and 17-05's registry fix.
- The whole-file acceptance greps (`\["ln"` = 0 in download.py/apps.py) close any fourth site.

**Concerns:** None new — my spot-checks confirmed the cycle-1 verification.

**Suggestions:** None beyond keeping the extraction heuristic documented in `fixture_runner`'s docstring (cycle-1 note, still open, non-blocking).

**Risk Assessment:** **LOW.**

---

## 17-03

**Summary:** Unchanged; correct and complete. `popen_with_env` (run.py:232-241) has `stdin=DEVNULL` but no new session; `run_output` (run.py:70-95, subprocess.run at :88) inherits both — exactly the update-path gap the plan closes, as SPEC R7 requires.

**Round-1 status:**
- sudo fail-fast regression not surfaced at phase level (MEDIUM, accepted/documented) — **RESOLVED** via 17-13: Task 1's `## e2e pass2 baseline (Phase 19)` section now carries the 17-03 sudo note ("install and update children run in a new session with no controlling terminal, so the `sudo dnf/apt-get/pacman` methods fail fast in the TUI… until Phase 22"), with a must_haves truth. 17-03's own T-17-42 already documents the limitation; the phase-level surfacing the reviewer asked for now exists.
- `/dev/tty` acceptance test non-discriminating under pytest (LOW) — **RESOLVED** (documented; the `getsid` discriminator and alarm guard are retained in the behavior spec).

**Strengths:** The discriminating test design (`getsid` child vs. `/dev/tty` reader), `_PopenKwargs` keyword pinning, and the untouched `run_command`/`run_interactive_command` are all verified.

**Concerns:** None new.

**Suggestions:** None.

**Risk Assessment:** **LOW.**

---

## 17-04

**Summary:** Unchanged; additive, read-only, well-tested. Verified: `DoctorReport(missing, broken, duplicated)` frozen (doctor.py:8-12) — appending a defaulted `broken_links` keeps the equality test valid; `has_problems` (:30-32); `doctor_guidance` returns `[_HEALTHY]` when no problems (guidance.py:119-120) so including `broken_links` in `has_problems` is required and specified; `_tui_guidance` rewrites next_steps starting ``Run `make fix` ``/:603 and ``Run `make setup` ``/:621 — the plan's prefix guard is correctly motivated; `doctor_data` is consumed from `_build_app` (setup.py:785-791), so the single wiring point claim holds.

**Round-1 status:**
- fifo/socket targets skipped silently (LOW) — **NOT ADDRESSED** (accepted for R10 scope; trivial future extension).
- dangling-link `opt_dir` normpath (LOW) — **NOT ADDRESSED** (cycle-1: no action needed; the `is_relative_to` check keeps it honest).

**Strengths:** The two-branch wording (opt-dir repair only when the normalized target is inside `opt_dir(name)`; otherwise remove-the-link) is correct for uv/pnpm shims; zero-execution enforced by the before/after snapshot test; `shlex.quote` covers copy-paste injection.

**Concerns:**
- **LOW — the dangling-link fixture's expected `opt_dir` requires an absolute (or `../opt/…`) link target.** `scan_bin_links` computes the normalized target as `normpath(target joined to entry.parent)`; a planted *relative* target string like `opt/ghost/ghost` resolves to `~/.local/bin/opt/ghost/ghost`, which is not inside `~/.local/opt/ghost`, so the test's expected `opt_dir=opt/ghost` would fail. The fixture must plant an absolute target (e.g. `str(opt_dir("ghost") / "ghost")`). Mechanism is fine; the behavior spec is ambiguous on this one detail.

**Suggestions:** State in Task 2's fixture that the ghost link's `os.readlink` value is the absolute `~/.local/opt/ghost/ghost` so the normpath-join yields the opt dir.

**Risk Assessment:** **LOW.**

---

## 17-05

**Summary:** Unchanged; the deepest wave-1 plan and still fully verified: `postinstall = "graphify-register"` at registry.toml:1592, Sublime's directory member at :2272/:2280 with `bin_name = "subl"` at :2273/:2281 (both Linux tarballs), codex at :1329, the homebrew `env = { NONINTERACTIVE = "1" }` pattern at :166, and `POSTINSTALL_HOOK_NAMES = {"codegraph-mcp-register", "rtk-register", "graphify-register"}` at model.py:20-22 (both sets lose the name together, so the parity tests stay aligned without edits — as the plan claims).

**Round-1 status:**
- Network-dependent probe (LOW) — **RESOLVED** (Task 1 records the error-and-proceed fallback with the stale-evidence caveat).
- Probe stop-condition threshold (LOW) — **RESOLVED** (cycle-1 re-checked: correct as written; any dirty form keeps removal).
- Parity-test-list sweep suggestion — covered by the plan's context notes and the whole-file `git grep` acceptance.

**Strengths:** Probe-first with a stop condition; dead-code deletion follows architecture rule 5; the update-path dispatch correction (`update.py` runs the hook too) makes the registry key the single lever for both paths; the codex env rides the existing closed `env` table + `_env_prefix`.

**Concerns:** None new.

**Suggestions:** None.

**Risk Assessment:** **LOW.**

---

## 17-06

**Summary:** The revision adds exactly what cycle 1 asked for: the confirm-time `OSError` catch ("treat as changed"), a fifth test (`test_clean_rc_duplicates_refuses_a_file_deleted_since_preview`), the must_haves truth, the acceptance grep (`except OSError` ≥ 1), and the raised verify floor (9 = 4 existing + 5 new, consistent with the RUN-LEDGER's "floors 9 and 9" fix).

**Round-1 status:**
- File deleted between preview and confirm makes the confirm re-read raise (LOW) — **RESOLVED.** Task 3 wraps only the confirm-time `read_bytes()` in `try/except OSError`, treats it via the same "changed since the preview; left untouched" branch (never recreates, continues with the other files), and pins it with the new test. Verified against today's code: preview skips missing files via `if not rc_path.exists(): continue` (app.py:433-434) and confirm re-reads/re-writes at :446-447 — the rewrite's shape fits.

**Strengths:**
- Test economy argument re-verified: `atomic_write_text` (atomic.py:56-58) really is symlink-through, mode-capable, temp-cleaning, and the temp suffix matches the test's no-sibling assertion (atomic.py:31).
- Byte-level compare defeats universal-newline translation; the block computation is untouched, so the existing idempotency/preservation tests stay green.

**Concerns:** None new.

**Suggestions:** None.

**Risk Assessment:** **LOW.**

---

## 17-07

**Summary:** The revision adds the cancel-path test and the `_partial_run` accumulator, and I verified the one thing that could have contradicted it: the existing `test_cancel_mid_update_tail_sweeps_unreached_outdated_row_to_skipped` still passes unchanged, because the "sweep to skipped" happens in `on_install_run_finished` (:912-918: not-attempted → skipped, pending update rows → skipped + appended to `self.not_attempted`), not in `_run_updates` — the plan's "keep ExecuteScreen's existing display loop" is exactly right, and the current test already asserts `"fd" in screen.not_attempted` (:2061). The new test's `install_summary.not_attempted` assertion is what the message-level extension provides.

**Round-1 status:**
- Cancel-path not tested (LOW) — **RESOLVED.** Task 2 adds `test_cancel_mid_updates_keeps_completed_updates_and_reports_the_rest_not_attempted` (completed rg update kept in posted outcomes, fd in `not_attempted`, `update_failed == ()`, `crash_error is None`, `has_failure` True), the action names the cancel-flow change, and the ledger records it.
- The reviewer's suggested `has_failure` False assertion — **RESOLVED as an explicit, reasoned rejection:** D-08 (locked) makes `has_failure` true whenever `not_attempted` is non-empty; the test instead pins that a cancel is neither a crash nor an update failure. RUN-LEDGER's cycle-1 row confirms this was the deliberate resolution. The rationale is consistent with the locked decision, not wrong.

**Strengths:**
- The worker/message/handler plumbing claims are verified line-for-line (execute_screen.py:581-672, wizard_app.py:2924-2976, setup.py:1509-1512 — the exact three-field condition replaced by `has_failure`).
- `update_failed` counting `UpdateOutcome.status == "failed"` matches how updates actually fail (update.py:442-471 returns status outcomes rather than raising).
- The pre-try `result` initialization makes the new `except Exception` branch sound for exceptions raised before the `run_live` call too.

**Concerns:**
- **LOW — placement of the not-attempted extension on the escaped-exception path.** "Before posting, extend the posted `not_attempted` with the `_to_update` ids not in `attempted`" is clear in intent ("e.g. after a crash or cancel"), but an exception escaping `_run_updates` itself (outside the inner `run_live`/`finally`) bypasses any end-of-`_run_updates` extension, and no planned test pins that shape (the crash tests cover the installs phase and `wire_path`). The extension should be computed at the `finally` posting site from `attempted`, and the plan should say so.

**Suggestions:**
- Name the extension's home explicitly (the `finally` post site) and, if cheap, extend the crash test's parametrization with one exception escaping `_run_updates` mid-loop asserting the unrun update ids land in `not_attempted`.

**Risk Assessment:** **MEDIUM** (unchanged from cycle 1) — it touches the most state, but the message plumbing, both stop paths, the cancel flow, and both exit sites are now all pinned by tests.

---

## 17-08

**Summary:** The revision adds the recovery re-set failure handling (stop the loop, shared private rollback helper, re-raise) and the shared `_link_mode_status` formatter naming failed policies — both specified with tests. The rollback algorithm's per-policy math checks out against the verified closure semantics (ban strips the union, tweak strips its fixed `rc_path`, both read the live mode via `_current_link_mode`, setup.py:916-923). However, I found a real-path contract mismatch that undercuts the rollback's core assumption (NEW-8 below).

**Round-1 status:**
- Recovery `set_link_mode(new_mode)` failure unspecified; later entries would read `moved` while blocks land in the old mode (LOW) — **RESOLVED as specified:** Task 2 stops the loop, rolls every removed policy back to the live mode via the shared helper, and re-raises; `test_move_link_mode_rolls_back_when_re_saving_the_new_mode_fails` pins it; must_haves truth and T-17-44 added. *But see the new MEDIUM concern — the specified rollback rests on an assumption the real setter violates.*
- Picker status names only `Moved:` (LOW) — **RESOLVED.** `_link_mode_status` appends `Failed: <id> (<detail>).` with severity warn, used by both pickers (acceptance: definition + 2 calls = 3 matches).
- Remove-failed policy not named in the status (LOW) — **RESOLVED** implicitly by the same `Failed:` entries.
- "Record the final mode in each `PolicyMove`" alternative — **RESOLVED as an explicit, reasoned rejection** (continuing would leave moved blocks in the new mode's files while the saved mode is old; stop-and-rollback keeps one consistent state). The rationale is sound.

**Strengths:**
- `Policy` append-only verified (policy.py:148-149, `owned` last at :158); `PoliciesScreen._link_mode` is a callable (`self._link_mode()` at wizard_app.py:1704) so `old = self._link_mode()` works; `_first_link_mode_picked` exists at :2759 with `_read_link_mode` (:2773); `active_state` is the live truth as claimed.
- The daemon/omz exclusion (RUN-LEDGER Q2) is implemented via the flag, with a test that a non-aware active policy is never touched.
- `PolicyMove` living in policy.py is the correct cycle avoidance (uninstall.py imports policy).

**Concerns:**
- **MEDIUM (NEW) — the real `SettingsStore.set_link_mode` violates the rollback's "mode was never saved, so the old mode is still current" contract.** settings.py:112-116 sets `self._link_mode = value` *before* `save_settings`; `_current_link_mode` returns `settings.link_mode` (setup.py:800-801), and the composition binds `set_link_mode=settings.set_link_mode` directly (setup.py:1000). So when the real setter raises (an `OSError` from `save_settings` — the exact injected-write-failure class this phase hardens), the store's *live* mode is already NEW while the disk still records OLD. Both raise paths' rollbacks then re-`apply()` policies through closures that read the live mode → blocks land in the NEW mode's rc files while the persisted mode is OLD → the stranded-policy state SAFE-06 exists to prevent, materializing on the next session (disk wins). The plan's own tests pin the *correct* contract but with fakes that "raise without changing its stored mode," so the suite cannot catch the mismatch. Cycle-1's review note ("subsequent applies correctly land in the *old* mode — closures read live mode") assumed the opposite of what the code does.
- **LOW — rollback scope for a policy whose `remove()` failed** is "left as it was" (consistent with its `failed` report), but a partially-stripped multi-file remove leaves per-file inconsistency; acceptable, worth one SUMMARY note if encountered.

**Suggestions:**
- Fix the contract where it's already being edited: in 17-11 Task 2 (or 17-08 Task 1), reorder `SettingsStore.set_link_mode` to `save_settings(...)` *then* `self._link_mode = value` (and clear the warning after), so a failed save leaves the live mode old — making the tested rollback contract true on the production path. One line; no test changes needed beyond optionally asserting the live mode is unchanged after a failed save.

**Risk Assessment:** **MEDIUM** — the rollback matrix is now fully specified and tested, but the new MEDIUM finding means one production-path edge (failed save mid-move) currently defeats it; the fix is one line in an already-touched method.

---

## 17-09

**Summary:** Unchanged except the ledger routing the e2e-baseline concern to 17-13 (where it landed). The predicate-beside-lenient-plan design is verified: `plan_uninstall` derives `binname = PurePosixPath(member).name` (uninstall.py:83) with the traversal guard (:84-88) and declared-bin_dir handling (:89-94) exactly as the plan's `_download_link` extraction describes; `install_download` names the link `bin_name or member-basename` (download.py:144) — so the shared `link_name` is the correct one-rule fix; `classify_tools`'s single swap point is `plan_uninstall([tool])` at :299; `remove_paths` unlinks symlinks without following (:345-347); `_plan_app` (:33-53) is why app bundles always land in `yourself`.

**Round-1 status:**
- e2e `UNINSTALL_OK` evidence value shrinks; record a Phase 19 baseline (LOW) — **RESOLVED via 17-13 Task 1** (`## e2e pass2 baseline (Phase 19)` with the Step-0 line, the final-tree line, and the explanation; I verified `pass2-transcript.log` is the real transcript name, container-e2e-verify.sh:423/:485-487, the UNINSTALL_OK gate is exit-code-only (:449-454), and the TRACER_REINSTALL_OK format (:474) matches the section's grep pattern).
- Broad functional regression (MEDIUM, deliberate/accepted) — **RESOLVED** (SPEC-sanctioned, stated up front; baseline now recorded).

**Strengths:**
- One predicate for TUI and CLI with `test_tui_and_cli_delete_the_same_set`; the adjacency spoof case (`is_relative_to(opt_dir(name).resolve())`) and the shared `_download_link` (no drift between lenient evidence and strict proof).
- The TUI shape (MANAGED with "remove it yourself" hint, no new `UninstallState` member) avoids the four-dict churn; `run_uninstall`'s nothing-to-uninstall early-return keeps the manual list (the branch exists at app.py:566-576 exactly as the plan says).

**Concerns:** None new (the `plant_removal_fixtures` scratch-path point from cycle 1 stands as handled).

**Suggestions:** None.

**Risk Assessment:** **MEDIUM** (unchanged) — deliberate, well-bounded user-visible regression, not a correctness risk.

---

## 17-10

**Summary:** Unchanged; the D-12 surgery verified again where it matters: `_build_app` takes `execute: ExecuteInputs | None = None` today (setup.py:762), `if execute is not None:` at :1134-1135, `_run_interactive_wizard` builds `cache`/`probe` only to share them (:1224-1250, comment at :1224-1226), `_execute_inputs` already has the exact `unattended` signature (:1166-1173), the four bare routes return 0 (:1296, :1332, :1357, guard branch :1441-1448), `_current_link_mode` is nested inside `_build_app` (:800, after the call site — the plan's "define or move whatever the call needs" note is accurate), and the shared-cache test's `calls == [cache]` invariant (test_setup.py:2786) is protected by dropping the wizard's own construction (:773-778 resolves one shared cache when both are omitted).

**Round-1 status:**
- `UnifiedApp.execute` stays optional (LOW) — **NOT ADDRESSED** (documented justification: tests construct UnifiedApp directly with `execute=None`; verified — `on_catalog_screen_decided` still needs the None branch, wizard_app.py:2791).
- Five real-app pilots heavy (LOW) — **NOT ADDRESSED** (xdist-safe by construction; each pilot builds its own scratch home).

**Strengths:**
- `_hermetic_route` as one helper is the strongest part — five pilots can't each forget a patch, and 17-11 reuses it; the `_execute_inputs` seam (D-12) is where the install recorder goes.
- `_session_exit_code` gives every route one honesty rule with a grep-verifiable call-count contract (def + 4 routes + wizard = 6).

**Concerns:**
- **LOW (NEW) — the route pilots must navigate home before selecting.** `--doctor`/`--fix` open `initial_view="doctor"` (setup.py:1295, :1327), `--uninstall` opens `"uninstall"` (:1354), `--guard` opens `"policies"` (:1444). The parametrized test's "show the base catalog view, select the fake tool, press enter" needs an explicit navigate-to-catalog step first (esc via `action_back`, wizard_app.py:2738-2743, or the nav palette) — the plan's pilot steps gloss this, and it applies to 17-01's doctor pilot and 17-11's launch test expectations too. Executor discovers it at RED; naming it saves a cycle.

**Suggestions:**
- Add one line to the route-test behavior: "navigate to the base catalog first (escape/`action_back`) for every non-setup route, whose initial view is doctor/uninstall/policies."

**Risk Assessment:** **MEDIUM** (unchanged) — composition-root surgery, but the seam, the per-route replacement tests, and the helper design are all verified.

---

## 17-11

**Summary:** Unchanged from cycle 1 (no actionable findings then). Verified: `load_settings` catches only `(OSError, json.JSONDecodeError)` at settings.py:55 so non-UTF-8 crashes every route today; there is exactly one read call in the module (the acceptance grep is honest); `_settings_store` (setup.py:1281-1286) is the only `load_settings` caller with six route callers (:1292, :1321, :1349, :1439, :1450, :1469 — confirmed); `_pending_warnings`/`_flush_pending_warnings` (wizard_app.py:2714-2718, " · " join) exist as described; `on_mount` pushes the picker last (:2598-2604) and the base-view flush is genuinely absent today; the dismissed picker branch writes no file (verified :2772-2780 — the byte-equality-after-dismissal test's premise holds).

**Round-1 status:**
- `on_mount` base-view flush timing uncertain (LOW) — **RESOLVED** (tracer-decided `call_after_refresh` fallback retained; the uncertainty is acknowledged, not hidden).

**Strengths:**
- The scope narrowing (warn only invalid UTF-8/JSON) matches RUN-LEDGER's locked row, and the two existing wrong-shape/tampered tests keep their assertions.
- `except ValueError` covers exactly the two errors D-11 names; the store's warning flag clears only after `save_settings` returns.

**Concerns:**
- Shares the **NEW MEDIUM from 17-08**: this plan edits `SettingsStore.set_link_mode` (warning clear) without fixing the in-memory-before-save ordering — the natural one-line fix belongs here (see 17-08's concern/suggestion).

**Suggestions:**
- Fold the `save_settings`-then-`self._link_mode` reorder into Task 2 and assert the live mode is unchanged after a failed save (one line, one assertion; makes 17-08's rollback contract real).

**Risk Assessment:** **LOW-MEDIUM** — small verified surface plus the shared setter-ordering edge.

---

## 17-12

**Summary:** Docs-only, and the revision is exactly the rewording cycle 1 asked for: the objective now describes 17-13's actual check ("re-runs every `uv run pytest` command this plan records in the 16-17..16-19 map rows… so a later Phase 17 commit that deletes or renames a cited test fails there"), and 17-13 Task 1 really carries that automated check (I verified the extraction grep, the `[^\`]` escaping inside the double-quoted bash -c payload, and that a `-k` expression selecting nothing exits non-zero per the must_haves truth). The arithmetic is correct under the file's own convention: footer at 16-SECURITY.md:80 reads "Total register rows: 60 (T-16-01..T-16-44 = 44, plus one T-16-SC per plan = 16)" → 65 (48 + 17 SC) → 75 (56 + 19 SC). Frontmatter (`status: verified`, `threats_open: 0`, `audited: "2026-10-10"`) matches the plan's claims.

**Round-1 status:**
- "17-13 re-runs every command" overstatement (LOW) — **RESOLVED** (objective reworded + the 17-13 check exists and is mechanically sound).
- `eval`-quoting brittleness (LOW) — **RESOLVED** (the specific truncation/`[^\r]` defects were fixed inline per RUN-LEDGER; I re-checked the quoting of both plans' extraction greps).

**Strengths:** Read-only discipline with per-commit `git show --stat`; qualified collision IDs plus the explanatory note; evidence as `file::symbol` + node ids so later Phase 17 edits don't rot the citations; every recorded command re-run before its row is believed.

**Concerns:** None new.

**Suggestions:** None.

**Risk Assessment:** **LOW.**

---

## 17-13

**Summary:** The phase gate, now carrying the two cycle-1 asks plus the orchestrator's command fixes. Verified: ci.yml triggers only on `push: [main]` + `pull_request` (:3-6) with job name `validate & test on ${{ matrix.os }}` (:15) producing exactly the two required contexts; the temp-branch + draft-PR oracle is the correct mechanism and the branch is deleted after each use (`ls-remote` exit-2 check); `pass2-transcript.log` is the real transcript path (container-e2e-verify.sh:423) and `TRACER_REINSTALL_OK` prints `installed= already= failed= dependency_failed=` (:474), matching the baseline section's grep; the `oracle sha:` + "HEAD differs only under `.planning/`" check correctly tolerates the post-oracle SUMMARY commits; the Task 3 check branches on the recorded `CI-02 answer:` line, and the autonomous-run skip is attributed to the orchestrator, not the user.

**Round-1 status:**
- Ubuntu 26 migration (A3) (LOW) — **RESOLVED** (triage runner image before attributing; recorded in Task 1).
- `UNINSTALL_OK` evidence shrinks under 17-09 (LOW) — **RESOLVED** (the `## e2e pass2 baseline (Phase 19)` section with before/after lines, the expected-`already=`-rise sentence, an automated check on the section, and the 17-03 sudo fail-fast line the review asked to surface at phase level).
- Task 3 apply path only post-verification (LOW) — **RESOLVED** (by design per D-17; skip path fully specified and verified).

**Strengths:**
- Two consecutive full-suite runs, `pre-commit run --all-files`, `make e2e`, the dependency-freeze diff, and the 16-VALIDATION command re-run make the local gate genuinely strong.
- No-main-push discipline is enforced by a scoped grep over the tasks plus the post-verification orchestrator step; CI-02's blocking-human checkpoint with exact body and undo is the right ceremony.

**Concerns:**
- **LOW — `git diff --quiet "$sha" HEAD -- . ":(exclude).planning"` is cwd-relative.** The `:(exclude).planning` pathspec resolves from the working directory; the check must run from the repo root (all other commands in the plan do, but this one silently passes/fails differently if run elsewhere). One `cd`/workdir note or a `:(exclude,top).planning` magic prefix would pin it.
- The macOS oracle timing vs. the 2026-10-19 runner migration remains external luck with a specified triage path (unchanged from cycle 1).

**Suggestions:** Note the repo-root requirement (or use `:(exclude,top)`) on the oracle-sha diff check.

**Risk Assessment:** **LOW-MEDIUM** (unchanged) — nothing here can corrupt the repo or host; residual risks are external with specified triage.

---

## Cross-Plan Assessment (cycle-2 additions)

- **Requirement coverage:** unchanged and complete (SAFE-01→17-02/17-05/17-04, SAFE-02→17-05, SAFE-03→17-09, SAFE-04→17-06, SAFE-05→17-07+17-10, SAFE-06→17-08, SAFE-07→17-03+17-05, SAFE-08→17-11, SAFE-09→17-10, R10→17-04, CI-01→17-01+17-13, CI-02→17-13, CI-03→17-12).
- **Wave/dependency soundness re-checked:** no same-wave `files_modified` conflicts (wave 1: 17-01/02/03/04/05/12 disjoint; wave 3: 17-08/09/10 disjoint; `tests/test_app.py` sequenced 17-01→17-06→17-09 across waves). 17-11's reuse of 17-10's `_hermetic_route` and 17-09's `plant_removal_fixtures` import by `tests/test_app.py` are correctly ordered.
- **Ledger compliance:** Q1 (remove hook), Q2 (link-mode-aware only), Q3 (stress-run owner_cell, version_status only if reproduced), CI-02 skip/handoff, 17-11 scope drop, TDD red-in-SUMMARY, wave-1 oracle — all *implemented* in the revised plans, not re-litigated.
- **Revision defects found:** one cross-plan MEDIUM (the real `SettingsStore.set_link_mode` ordering breaks 17-08's rollback contract — the only finding that changes behavior), plus three LOWs (17-01 sibling citation, 17-10 route-pilot navigation, 17-04 dangling-fixture target form) and one LOW placement note in 17-07.

## Round-1 Resolution Table

| Plan | Cycle-1 concern | Severity | Status |
|------|----------------|----------|--------|
| 17-01 | owner_cell fix weakened to a propagation tautology | MEDIUM | RESOLVED — Task 3's brew-owning inventory + `artifacts_for=lambda _t: []` + pinned `"Homebrew"`; verified against the real seams and resolution path |
| 17-01 | BSD `find` flags assumed (A1) | LOW | RESOLVED — documented assumption, fenced by the wave-1 CI oracle gate |
| 17-01 | `_prune_common_find_matches0` header comment | LOW | RESOLVED — Task 1 updates the header comment |
| 17-02 | fixture_runner substring heuristic | LOW | NOT ADDRESSED — accepted as bounded (non-blocking) |
| 17-02 | tar flow extracts whole archive | LOW | NOT ADDRESSED — test-design care (non-blocking) |
| 17-03 | sudo fail-fast regression not surfaced at phase level | MEDIUM | RESOLVED — via 17-13 Task 1's baseline section note |
| 17-03 | `/dev/tty` test non-discriminating under pytest | LOW | RESOLVED — documented; getsid discriminator + alarm guard retained |
| 17-04 | non-file/non-dir targets skipped | LOW | NOT ADDRESSED — accepted for R10 scope |
| 17-04 | dangling-link opt_dir normpath edge | LOW | NOT ADDRESSED — cycle-1: no action needed |
| 17-05 | network-dependent probe | LOW | RESOLVED — recorded fallback with stale-evidence caveat |
| 17-05 | probe stop-condition threshold | LOW | RESOLVED — re-checked correct as written |
| 17-06 | deleted-between-preview-and-confirm raises | LOW | RESOLVED — confirm-time OSError catch + new test (verified) |
| 17-07 | cancel-path assertion missing | LOW | RESOLVED — new cancel test; `has_failure` False rejected with a sound D-08 rationale |
| 17-07 | `error = error or …` masks original error | LOW | NOT ADDRESSED — cosmetic (non-blocking) |
| 17-08 | recovery re-set failure unspecified / mislabeled `moved` | LOW | RESOLVED as specified — stop + shared rollback + re-raise + test (but see new MEDIUM) |
| 17-08 | picker status names only `Moved:` | LOW | RESOLVED — `_link_mode_status` with `Failed:` entries, warn severity |
| 17-08 | "record final mode in PolicyMove" alternative | LOW | RESOLVED — explicit reasoned rejection (sound) |
| 17-09 | e2e `UNINSTALL_OK` evidence shrink / Phase 19 baseline | LOW | RESOLVED — via 17-13 Task 1 (transcript path and format verified) |
| 17-09 | broad deliberate regression | MEDIUM | RESOLVED — SPEC-sanctioned, stated, baseline recorded |
| 17-09 | fixtures encode host shapes | LOW | NOT ADDRESSED — scratch-path planting already handled |
| 17-10 | `UnifiedApp.execute` stays optional | LOW | NOT ADDRESSED — documented justification (verified) |
| 17-10 | five real-app pilots heavy | LOW | NOT ADDRESSED — xdist-safe by construction |
| 17-11 | on_mount flush timing uncertain | LOW | RESOLVED — tracer-decided fallback retained |
| 17-12 | "17-13 re-runs every command" overstates | LOW | RESOLVED — objective reworded + 17-13's automated check (verified) |
| 17-12 | eval-quoting brittleness | LOW | RESOLVED — specific defects fixed per RUN-LEDGER; quoting re-checked |
| 17-13 | Ubuntu 26 migration (A3) | LOW | RESOLVED — triage path specified |
| 17-13 | apply path only post-verification | LOW | RESOLVED — by design per D-17; skip path verified |

## Overall

**Cycle-1 actionable concerns: 7 of 7 RESOLVED** (17-01 MEDIUM, 17-06 LOW, 17-07 LOW, 17-08 LOW ×2, 17-09/17-13 LOW, 17-12 LOW), plus the accepted/documented items unchanged as intended. **Unresolved HIGH: 0. Unresolved actionable NEW concerns: 1 MEDIUM, 4 LOW.**

- **MEDIUM (17-08/17-11, the one behavioral finding):** `SettingsStore.set_link_mode` sets in-memory mode before `save_settings` (settings.py:112-116) while the ban/tweak closures read the live mode (`_current_link_mode`, setup.py:800-801/916-923) — so a real failed save mid-`move_link_mode` makes both rollback paths re-apply blocks into the *new* mode's files while the persisted mode stays old, the exact stranded-policy state SAFE-06 exists to prevent. The plan's tests can't catch it (their fake setter models the right contract). Fix: reorder save-then-flip in 17-11 Task 2 (already editing that method), one line.
- **LOWs:** 17-01's inaccurate sibling-test citation (the prescribed `systemd_available` seam itself is verified sound, keyword-only at setup.py:385/:429/:624); 17-10's route pilots need an explicit navigate-to-catalog step (initial views are doctor/uninstall/policies); 17-04's dangling-link fixture must plant an absolute link target for the expected `opt_dir`; 17-07's not-attempted extension should be pinned to the `finally` posting site; 17-13's `:(exclude).planning` pathspec is cwd-relative.

**Verdict: approved for execution** — proceed with the wave order as planned, folding in the one-line `set_link_mode` reorder (17-08/17-11) and the four LOW notes if convenient. This cycle's verification again found zero factual errors in the plans' line-level claims about the code (every claim I traced — including all the revision-specific ones — matched the source), and the one MEDIUM is a cross-component contract mismatch the plan set inherited, not a planning error.

---

Not checked: macOS-only behavior (BSD `find` flags, macOS `sh` `time`), CI run history, and the remote vendor-script facts (codex `install.sh`, graphify forms) — taken from research/ledger records; each has an in-plan oracle (the macOS CI job, the container probe re-run). Risk to know: if the 17-08/17-11 setter reorder is not folded in, a failed settings save during a link-mode move can strand active policy blocks in the wrong mode's rc files on the next session.

---

## Consensus Summary

Convergence cycle 2 (plans revised in 0e6a9c7 against cycle 1, d702a38). Single reviewer (opencode-plan-review, source-grounded: `file:line` evidence throughout, every plan id covered), so there is no cross-reviewer consensus to compute and the consensus gate does not engage. Verdict: **approved for execution, no HIGH findings.** All 7 cycle-1 actionable concerns are RESOLVED in the PLAN.md files (ledger entries verified against plan text and source). The cycle-1 items the reviewer marks "NOT ADDRESSED" are the ones cycle 1 already classed as accepted/non-actionable.

Orchestrator verification of the new findings (checked against the tree before recording):
- **Confirmed** — 17-08/17-11 MEDIUM: `installer/settings.py:112-116` assigns `self._link_mode = value` before `save_settings(...)`; `setup.py:800-801` `_current_link_mode` reads the store live and `setup.py:1000` binds `set_link_mode=settings.set_link_mode`. 17-08 Task 2's rollback text ("the mode was never saved, so the old mode is still current") therefore does not hold on the production setter, and 17-11 Task 2 (`installer/settings.py`) edits the same method without reordering it.
- **Confirmed** — 17-04 LOW: the behavior fixture `bin/subl -> opt/subl/sublime_text/` does not say the link target is absolute; the action resolves `normpath(target joined to entry.parent)`, so a relative `opt/...` string resolves under `bin/` and the test's expected `kind="directory"` / `opt_dir=opt/subl` would not hold.
- **Confirmed** — 17-10 LOW: `--doctor`/`--fix` open `initial_view="doctor"` (setup.py:1295, :1327), `--uninstall` `"uninstall"` (:1354), guard `"policies"` (:1444); the route-pilot behavior says "show the base catalog view" but does not name the navigation step.
- **Confirmed** — 17-13 LOW: `git diff --quiet "$sha" HEAD -- . ":(exclude).planning"` is cwd-relative (17-13-PLAN.md:119).
- **Refuted** — 17-01 LOW "sibling test at test_setup.py:2827" citation: 17-01-PLAN.md:221 cites the seam `setup.systemd_daemon.systemd_available` at `setup.py:624`, not a sibling test; there is no `:2827` reference in the plan. Not actionable.
- **Already in plan** — 17-07 LOW placement: 17-07-PLAN.md:179 makes `attempted` and the accumulators caller-owned (created in `_execute_worker` before the try) and extends `not_attempted` "before posting"; the post happens only in the `finally`. An optional extra crash-in-`_run_updates` test case is a nicety, not a gap.

### Agreed Strengths
- (single reviewer) Revisions are source-faithful: every revision-specific claim traced (17-01 owner_cell seam path through `resolve_ownership`, 17-06 confirm-time `OSError`, 17-07 cancel flow vs `on_install_run_finished` sweep, 17-08 `_link_mode_status`, 17-12/17-13 extraction greps) matched the code.
- (single reviewer) RUN-LEDGER decisions (Q1-Q3, CI-02 hand-off, 17-11 scope drop, D-08 `has_failure` lock, TDD red-in-SUMMARY, wave-1 CI oracle) implemented, not re-litigated.
- (single reviewer) No same-wave `files_modified` conflicts; SAFE-01..09 and CI-01..03 coverage complete.

### Agreed Concerns
None (one reviewer). Actionable non-HIGH items not yet in the PLAN.md files:
- 17-08 + 17-11 (MEDIUM): reorder `SettingsStore.set_link_mode` to `save_settings(...)` first, then `self._link_mode = value` (then clear the warning), in 17-11 Task 2 which already edits that method; add an assertion that the live mode is unchanged after a failed save; adjust 17-08 Task 2's rollback premise to cite that ordering (17-11 is wave 2, 17-08 wave 3, so the order is safe).
- 17-04 (LOW): state in Task 2's behavior that the fixture links use absolute targets (e.g. `str(opt_dir("subl") / "sublime_text")`).
- 17-10 (LOW): add to the route-pilot behavior "navigate to the base catalog view first (`show_view(BASE_VIEW)` / back) on doctor, fix, uninstall and guard, whose initial views are doctor/uninstall/policies".
- 17-13 (LOW): run the oracle-sha diff from the repo root or use `":(top,exclude).planning"`.

### Divergent Views
None (one reviewer).
