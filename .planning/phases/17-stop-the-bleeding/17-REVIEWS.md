---
phase: 17
reviewers: [opencode-plan-review]
reviewed_at: 2026-10-14T20:34:24Z
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

### Phase 17 Plan Review — Stop the Bleeding (13 plans)

**Verification method:** I read the referenced code with CodeGraph and targeted reads before judging any plan. Dozens of line-level claims were checked against the tree at `5390577` (on `72c9047`); both flagship RED claims were **reproduced live**: `uv run pyright --pythonplatform Darwin` → 3 errors at `tests/conftest.py:27` (`"sched_getaffinity" is not a known attribute of module "os"`), and the bash 3.2 container check → `line 101: mapfile: command not found`, `prune-tmp-common.sh: line 208: find_type[@]: unbound variable`, `exit=127`, nothing deleted. Every structural claim I traced (linking sites, worker shape, routes, write sites, registry entries, prune bugs, milestone doc arithmetic, threat-ID collision) matched the source, with only trivial line drift (e.g. `_fixture_runner` at `tests/test_download.py:480` vs the claimed `:478`; `binname` at `installer/uninstall.py:83` vs `:90`). What I could not verify: macOS-only behavior (BSD `find` flags, macOS `sh` `time`), CI run history, and the two remote vendor-script claims (codex `install.sh`, graphify forms) — those are marked as such below.

---

## 17-01

**Summary:** CI-repair plan with three genuinely root-caused fixes (prune portability, pyright Darwin, deterministic tests). Every bug it names is real in the source, and I reproduced both RED cases exactly. The wave-1 CI-oracle mechanism (temp branch + draft PR) is correctly designed for a workflow that only triggers on `push: main` / `pull_request` (verified `.github/workflows/ci.yml:3-6`).

**Strengths:**
- The prune diagnosis is complete, not partial: `mapfile` at `scripts/prune-tmp-linux.sh:101`, GNU-only `-regextype` at `scripts/lib/prune-tmp-common.sh:208` and `:233`, and the empty-array-under-`set -u` expansions at `:203-:237` and `prune-tmp-linux.sh:105/:115` — all confirmed on disk, and the container RED shows exactly the two named errors plus exit 127.
- Deleting the dead regex branch of `_prune_common_find_matches0` is safe: I verified every caller (`scripts/prune-user-tmpdir.sh:231-235`) passes `name` mode. The `find | grep -E` replacement is semantically equivalent (GNU `find -regex` and `grep -E "^…$"` both match whole paths with the same ERE).
- The pyright fix (`sys.platform == "linux":` narrowing) is the correct mechanism — `hasattr` cannot narrow an unknown attribute, `sys.platform` can; the worker-cap math is unchanged.
- Ledger Q3 is implemented faithfully (stress-run `test_version_status.py`, edit only if reproduced; the two `second.join(timeout=0.2)` checks at `tests/test_version_status.py:1790` and `:1874` are exactly the candidates claimed).
- No skip/xfail anywhere; each fix names its root cause.

**Concerns:**
- **MEDIUM — owner_cell fix option weakens the test's meaning.** The primary option asserts `expected = owner_label(service.ownership_of("rg"))` — i.e., "the table shows whatever the service committed." After `wait_for_complete()`, that is deterministic but semantically weaker than the original pinned assertion (`'Homebrew'`); it becomes a propagation tautology if both sides read the same resolution. The plan's own alternative (`artifacts_for=lambda _t: []` plus a brew-owning inventory — the seam exists at `tests/test_catalog_tui.py:1171/:1183/:1230`) preserves both determinism *and* the pinned semantic value.
- **LOW — BSD `find` flags are assumed (A1).** `-mmin/-mindepth/-maxdepth` on macOS BSD find is unverified here; the macOS CI job is the only oracle. Mitigated by the wave-1 oracle gate, which catches it before wave 2.
- **LOW — `_prune_common_find_matches0` header comment still lists `MODE`.** The acceptance sed range starts at the function definition, so the `grep -c '\$mode'` check passes either way; trivial.

**Suggestions:**
- In Task 3, prefer the `artifacts_for` alternative (or assert both: the propagated value equals the table cell **and** equals an independently pinned label), keeping the test's original intent.
- Record in the SUMMARY that the near-miss file survival proof comes from the container check, since the pytest prune tests can't run bash 3.2 semantics on this host.

**Risk Assessment:** **LOW-MEDIUM** — all fixes are root-cause and verified-red; the only judgment risk is the owner_cell assertion semantics, and the macOS-only assumptions are fenced by the wave-1 CI oracle before anything builds on them.

---

## 17-02

**Summary:** Correct, minimal hardening of the H1 hazard at exactly the three claimed linking sites, with one shared helper and one shared test runner. The engine contract claim is verified: `installer/engine.py:152` catches `executors.ExecutorError` per method and falls through; a directory member ends as `FAILED` with errors (`engine.py:184`), never `installed`.

**Strengths:**
- The three sites are exactly as claimed: shelled `chmod +x`/`ln -sf` at `installer/download.py:189-190` (`_install_unverified`), `_install_verified` delegating to `_place_verified` (`download.py:225`), and `installer/apps.py:100`. `atomic.replace_symlink` (`installer/atomic.py:117-130`) does sibling-temp + `os.replace` and never writes through an existing link-to-directory.
- `chmod=False` for the app site is a verified behavioral preservation: `install_app` (`apps.py:68-100`) uses `ditto` and never chmods inside a bundle today.
- The reinstall-over-link-to-directory test is the right discriminator for the actual H1 mechanism (`ln -sf` through a symlinked dir creates an entry inside it; `os.replace` on the link path cannot).
- Honest boundary-drawing: the update-path `is_file()` guards are recommended-but-not-built, and the whole-file acceptance greps (`\["ln"` count 0 in `download.py`/`apps.py`) close any fourth site I didn't read (e.g. `_place_verified`'s body).
- The Sublime-shaped test (member `sublime_text/sublime_text`, `bin_name subl`) matches the real archive layout research verified.

**Concerns:**
- **LOW — `fixture_runner` extraction detection is a substring heuristic** ("argv[0] is `sh` and the script contains ` tar `/`unzip `/`ditto `"). Bounded (URLs like `…tar.xz` don't contain a spaced ` tar `), but brittle against future argv shapes.
- **LOW — tar flow extracts the whole archive** (`download.py:182-187` has no member filter), so the byte-identical-reinstall test must seed paths that don't collide with the extracted member; that's test-design care, not a plan defect.

**Suggestions:**
- Consider making `fixture_runner`'s materialization opt-in via an explicit `member=` argument only (it already is) and asserting the *absence* of `ln`/`chmod` argv by recording, which the plan already does — no change needed beyond keeping the heuristic documented in the helper's docstring.

**Risk Assessment:** **LOW** — the mechanism, reuse targets, and engine contract are all verified against source; test churn is bounded and enumerated.

---

## 17-03

**Summary:** Small, correct, and importantly *complete*: it fixes the update-path gap (`run_output`/`run_captured`) that D-10 as written missed, which SPEC R7 ("install and update children") requires. Both runners verified: `popen_with_env` (`installer/run.py:232-241`) already has `stdin=DEVNULL` but no new session; `run_output` (`run.py:70-95`) inherits both.

**Strengths:**
- The discriminating test design is right: under pytest there is no controlling tty, so the `/dev/tty` test can't discriminate — the `getsid` child does, and the plan says so explicitly instead of pretending otherwise.
- `run_command`/`run_interactive_command` (`run.py:50-64`) are left untouched, preserving the console interactive path — verified.
- `_PopenKwargs` (`tests/test_run.py:25`) pins the exact production keyword set, so the two new kwargs can't silently regress.
- The blast radius of `run_output` (daemon/systemd/policy/pnpm/versions callers) is enumerated and its test modules are in the verify list.

**Concerns:**
- **MEDIUM (accepted, documented) — sudo methods regress from "hangs" to "always fails fast".** The `sudo dnf/apt-get/pacman` builders (`installer/executors.py:370-378`, confirmed on the not-shown index) run under StreamingRunner in the TUI; with no controlling terminal they can never prompt, so they now fail until Phase 22 replaces them with a handoff. The plan documents this (T-17-42) and defers correctly, but it is a real user-visible behavior change this phase ships.
- **LOW — the `/dev/tty` acceptance test passes both before and after the fix** under pytest; it only becomes meaningful on a real terminal. The plan knows this; keep the elapsed-time guard.

**Suggestions:**
- Surface the sudo fail-fast change in the phase-level SUMMARY (not just 17-03's) so `/gsd-verify-work` and Phase 22 planning see it as a known limitation, since it changes what a TUI install of native-package tools does.

**Risk Assessment:** **LOW** — two kwargs per runner, precise tests, and the one behavior change is consciously accepted and routed to Phase 22.

---

## 17-04

**Summary:** Clean, registry-independent Doctor scan with correct reuse of the one `DoctorReport → doctor_guidance` path for both renderers. The two pitfalls the plan guards against are verified real: `DoctorReport` equality is tested positionally (appending a defaulted field is the only safe change) and `DoctorScreen._tui_guidance` really rewrites next_steps starting with ``Run `make fix` ``/`` `make setup` `` (`installer/wizard_app.py:603`, `:621`).

**Strengths:**
- The wording split (opt-dir repair vs. remove-the-link for shims whose target lies outside `opt_dir(name)`) is correct — the unconditional opt-dir text would tell users to delete directories the link doesn't point into.
- Zero execution, before/after snapshot test, `shlex.quote` in repair text, no sudo — the zero-mutation rule is enforced by tests, not promises.
- `doctor_data` wiring (`installer/app.py:346-360`, `report = audit_path(...)` at `:358`) is exactly the single place to attach `broken_links`; both consumers inherit it.

**Concerns:**
- **LOW — non-file/non-dir targets (fifo/socket) are skipped silently.** Acceptable for R10's scope; a future `kind` extension is trivial.
- **LOW — the dangling-link `opt_dir` computation via `normpath(join(parent, target))`** handles relative targets correctly, but a target like `/opt/../home/x` normalizes inside `opt_dir` only if it truly is — the `is_relative_to` check keeps it honest. No action needed.

**Suggestions:** None beyond what the plan already specifies; the threat model's injection case (`shlex.quote`) should also cover the *title/meaning* lines, which the plan's `never_escalates` test already scans.

**Risk Assessment:** **LOW** — additive, read-only, well-tested.

---

## 17-05

**Summary:** The registry-hazards plan, and the deepest of the wave. Everything it touches is verified: `postinstall = "graphify-register"` at `installer/registry.toml:1592`, hook code at `installer/postinstall.py:250-281`, names at `installer/model.py:20-22`, Sublime's directory-member bug at `registry.toml:2272` and `:2280` (`member = "sublime_text"` with `bin_name = "subl"` — the H1 source, exactly as claimed), codex's env-less script method at `:1347-1351`, and the homebrew `env = { NONINTERACTIVE = "1" }` pattern at `:166`. It also correctly fixes RESEARCH's error: the update path *does* dispatch postinstall (`run_postinstall` callers include `installer/update.py`), so removing the key is the single lever for both paths.

**Strengths:**
- The probe-first protocol with a stop condition (if every form is cwd-clean, stop and route the decision back) protects against acting on stale evidence, and RUN-LEDGER Q1's removal decision is implemented rather than re-litigated.
- Dead-code deletion follows architecture rule 5 with the parity tests kept aligned (both sets lose `graphify-register` together); the whole-file `git grep` acceptance makes leftovers impossible to miss, and vulture is in `make validate`.
- The Sublime fix (`member = "sublime_text/sublime_text"`, strip 0) is consistent with 17-02's guard and 17-09's `link_name` work; the dated `# Verified` comment convention is the right pre-Phase-18 shape.
- Codex `CODEX_NON_INTERACTIVE=1` rides the existing closed `env` table + `_env_prefix` mechanism — one registry line, no code.

**Concerns:**
- **LOW — network-dependent probe.** If the container can't reach PyPI, the plan records the error and proceeds on the recorded evidence — acceptable, but the SUMMARY must then clearly say the probe is stale.
- **LOW — the probe stop-condition threshold ("every form clean") could mask a partial regression** (e.g. two of four dirty) — no, actually any dirty form keeps removal per D-03; only all-clean halts. Correct as written.

**Suggestions:**
- When deleting the graphify-register tests, also sweep `tests/test_post_install.py`'s parity test list for the name (the plan covers `test_model.py:940` and `test_post_install.py:186` — both lose the name symmetrically, so no edit is needed; verify rather than assume during execution).

**Risk Assessment:** **LOW** — registry-data + dead-code deletion with strong whole-file checks; the only external dependency is the container probe, which has a recorded fallback.

---

## 17-06

**Summary:** Accurate and economical. The 10 write sites are exactly where claimed — `installer/guards.py:388/:392/:425/:448/:472/:554/:564` and `installer/tweaks.py:254/:297/:308`, with the 5+1 `chmod(0o755)` pairs at `:389/:393/:426/:453/:473` and `tweaks.py:255` — I counted them on disk, and there are no other `.write_text(` in either file, so the acceptance greps (count 0) are honest. `clean_rc_duplicates` (`installer/app.py:418-448`) applies stale preview indices at `:447` exactly as diagnosed.

**Strengths:**
- The test-economy argument is sound and verified: the atomic properties (failure-keeps-original, symlink write-through, mode, missing-file) already exist once in `tests/test_atomic.py`, and `atomic_write_bytes` (`installer/atomic.py:34-53`) really does resolve symlinks, honor explicit `mode`, and clean temps on OSError — routing + greps + one concurrency test is the right coverage shape, not per-call-site duplication.
- Byte-level compare (`read_bytes`) for the confirm recheck correctly defeats universal-newline translation — the pitfall is real for `\r\n`/trailing-newline edits.
- Keeping the block computation unchanged (only the write call swaps) minimizes regression surface; existing idempotency/preservation tests stay green.

**Concerns:**
- **LOW — a file deleted between preview and confirm makes the confirm re-read raise `FileNotFoundError`.** Today's code has the same exposure (`:447` re-reads with `read_text`), so it's not a regression, but this rewrite is the natural moment to catch `OSError` on the confirm re-read and treat it as "changed/disappeared; left untouched."

**Suggestions:**
- Add the confirm-time `except OSError` (report + skip that file) to the D-06 rewrite; one more test (`test_clean_rc_duplicates_refuses_a_file_deleted_since_preview`).

**Risk Assessment:** **LOW** — mechanical routing through an already-tested primitive, with a byte-exact recheck that is itself well tested.

---

## 17-07

**Summary:** The most intricate plan, and its diagnosis is verified line-for-line: `_execute_worker` (`installer/execute_screen.py:573-672`) has only `try/finally` — no `except` — with locals at `:581-592`, the `result is None` branch at `:624-625` that leaves `not_attempted` as *all* ordered ids (`:583`) and outcomes empty, `InstallRunFinished` posted positionally at `:657-671`, `_run_updates` (`:674-728`) returning its four collections only at the end, the green `"Done."` at `:953`, and the deliberate no-`event.stop()` comment at `:955-957`. `setup.py:1509` reads exactly the three fields the plan replaces.

**Strengths:**
- The fold-once design (`fold_run` in `session.py`, called by both `ExecuteScreen` and `UnifiedApp.on_install_run_finished` at `wizard_app.py:2924+`) is the right single source of truth, and appending defaulted fields to `Summary` keeps ~22 test constructions valid.
- `update_failed` including `UpdateOutcome.status == "failed"` (not just raised errors) matches how updates actually fail — verified: `UpdateService.run` returns `status="failed"` outcomes rather than raising (`installer/update.py:442+`).
- The per-tool accumulator keyed by id with last-wins (checksum retry re-invokes `on_outcome`) shows the planner actually read the retry path.
- Both stop paths (run_live-caught and uncaught) are handled, and the all-skipped-exits-0 edge is pinned — the SPEC's exact acceptance.

**Concerns:**
- **LOW — `error = error or f"run stopped: {exc}"` can mask the original error text** when a path/verify error was already recorded and a later step then raises; the status then names the later exception only. Cosmetic, both still exit 1.
- **LOW — the `_run_updates` accumulator refactor changes an early-return-on-cancel into break-plus-not-attempted extension**; the plan describes it, but the cancel-path skip messages must survive — its `test_completed_updates_survive_a_later_crash` covers the crash half, not the cancel half.

**Suggestions:**
- Add one cancel-path assertion (cancel mid-updates → completed updates kept, unrun update ids in `not_attempted`, `has_failure` False) since Task 2 rewrites that flow.

**Risk Assessment:** **MEDIUM** — not because the design is wrong (it's verified against the code in detail) but because it touches the most state (worker, message, two handlers, two exit sites) and the tests are the only safety net for the message-field plumbing. The task split and acceptance greps are strong.

---

## 17-08

**Summary:** Faithful implementation of D-09 *with* the two RESEARCH corrections and ledger Q2 binding (link-mode-aware-only). Verified: `Policy` is frozen with the append-only comment at `installer/policy.py:148-149` and `owned` as the last field (`:158`); the factories exist at `:267/:357/:485/:583/:680/:885`; `installer/uninstall.py:19` imports policy, so `PolicyMove` living in `policy.py` (not importing from uninstall) is the correct cycle avoidance; the pickers are at `wizard_app.py:2179` and `:2759` as claimed.

**Strengths:**
- The restore semantics are specified to a level rare in plans: apply-failure → mode back, old block restored, mode forward, per-policy report; set-mode-failure → re-apply in old mode (mode was never saved, so old mode is still current — correct) and re-raise so `run_live` reports it.
- Because the closures read the live mode, even the messy recovery edges converge on consistent states — the plan exploits this rather than fighting it.
- Not moving daemon/omz policies (RUN-LEDGER Q2, TypeSafe 0.94) avoids pointless service re-bootstrap; the `link_mode_aware` flag is appended per the dataclass's own rule.
- Both pickers share one `link_mode_aware_active()` helper instead of duplicating the filter.

**Concerns:**
- **LOW — a policy whose `remove()` fails is still left behind while the mode flips** (`failed` in the report, block stays in the old mode's file). That's identical to today's state for that policy, so not a regression — but the user sees "mode saved: split" while one block is stranded in the old file until they re-toggle. The report says failed; consider making the status name it too.
- **LOW — if the recovery's `set_link_mode(new_mode)` itself fails**, subsequent applies correctly land in the *old* mode (closures read live mode — self-consistent), but their report entries read `moved`, which is now misleading about where the block ended up.

**Suggestions:**
- On a failed re-set of the new mode, stop the loop and re-raise (mirror the set-mode-failure contract) instead of continuing with mislabeled `moved` entries; or record the final mode in each `PolicyMove`.

**Risk Assessment:** **MEDIUM** — rollback logic with several interacting failure modes, but the algorithm is fully specified, the closures' live-mode reads make states converge, and both pickers are tested end-to-end.

---

## 17-09

**Summary:** The strict-removal plan, correctly built *beside* `plan_uninstall` instead of inside it. Verified: `plan_uninstall` derives `binname = PurePosixPath(member).name` (`installer/uninstall.py:83`) while install names the link `bin_name or member-basename` (`installer/download.py:144`) — so Sublime's `subl` link is invisible to the lenient plan today, exactly the companion fix the plan makes; `classify_tools` calls `plan_uninstall([tool])` per tool at `:299` (the single swap point); `run_uninstall` plans at `installer/app.py:548`; the app-bundle tests and `test_classify_removable_when_artifacts_on_disk` at `tests/test_uninstall.py:188-276`/`:338` are the right rewrites.

**Strengths:**
- One predicate for TUI and CLI with a same-deletion-set test (`test_tui_and_cli_delete_the_same_set`) directly discharges the `--yes`-vs-TUI divergence threat (T-17-26).
- The proof shape (`link.is_symlink() and resolved.is_file() and resolved.is_relative_to(opt_dir(name).resolve())`) with the adjacency test (link into another tool's opt dir) covers the spoofing cases that matter; `remove_paths` (`uninstall.py:342-351`) already unlinks links without following.
- The shared `_download_link` lookup means the lenient evidence list and strict predicate cannot drift — and `plan_uninstall`'s three other callers (ownership evidence) keep their behavior, with the Sublime link-name fix making their evidence *more* truthful.
- The regression (app bundles, raw binaries unremovable until Phase 19 receipts) is SPEC-sanctioned, stated up front, and consistent with the e2e ledger observation (only ~46/74 removable today).

**Concerns:**
- **MEDIUM (deliberate, accepted) — the functional regression is broad.** The run-ledger e2e numbers imply roughly a third of installed tools become "remove it yourself" until Phase 19. I verified this does **not** break the phase gate: `scripts/container-e2e-verify.sh` pass2 step 2 asserts only the `--uninstall --yes` exit code (`:449-454`) and step 3 tolerates a higher `already=` count (`:469-475` only requires failed/dep/mismatched == 0). But the *evidence value* of `UNINSTALL_OK` silently shrinks.
- **LOW — the uv/pip/shared fixtures encode today's host shapes** (uv ruff symlink into `~/.local/share/uv/...`) — correct, but they must be planted as plain paths under the scratch home so they don't depend on a real uv layout; the plan's fixture builder already does this.

**Suggestions:**
- Have 17-13's SUMMARY record the pass2 shift explicitly (uninstall now removes only the proven set; reinstall `already=` rises) so a future reader of the e2e transcripts doesn't misread it as a regression, and so Phase 19 has a before/after baseline.

**Risk Assessment:** **MEDIUM** — a deliberate, well-bounded safety regression with a single predicate, shared fixtures, and idempotency pinned; the risk is user-visible behavior change, not correctness.

---

## 17-10

**Summary:** The D-12 surgery, and every wiring claim checks out: `_build_app` takes `execute: ExecuteInputs | None` today; `_run_interactive_wizard` builds `cache`/`probe` precisely to share them with `execute=` (`setup.py:1224-1250`, comment at `:1224-1226` — exactly as the plan describes); the four bare routes return 0 without execute (`setup.py:1296`, `:1332`, `:1357`, guard branch `:1435-1448` — and the plan's correction that `_run_guard` is the console-only path is right); `_execute_inputs`' signature (`setup.py:1166-1211`) is exactly what `_build_app` will call; the empty-selection message at `installer/catalog_tui.py:1040` is verbatim what the plan says needs only a test; and `test_accepting_the_catalog_without_execute_still_exits_with_ids` exists at `tests/test_wizard_app.py:7185` for deletion.

**Strengths:**
- Removing the parameter (the D-12 "best over easiest" choice) closes the bug *class*; the rejected smaller diff is documented as rejected, matching the user's standing decision rule.
- `_hermetic_route` as one shared helper (scratch PATH, `systemd_available` False, TTY patches, install replaced at the `_execute_inputs` seam) is the strongest part of the plan — five route pilots can't each forget a patch, and 17-11 reuses it.
- `_session_exit_code` gives every route the same honesty rule (SAFE-05's exit code on all routes, not just setup), with one grep-verifiable call-count contract (4 routes + wizard = 5 calls + def = 6).
- The shared-cache invariant (`one _timer_state_cache call`) is protected by an existing test the plan explicitly keeps green.

**Concerns:**
- **LOW — `UnifiedApp.execute` stays optional** while `_build_app` can no longer produce `None` — a residual seam inconsistency, but justified (tests construct `UnifiedApp` directly with `execute=None`) and documented.
- **LOW — five real-app pilots in one parametrized test** is the plan's heaviest test addition; xdist-safe by construction (each pilot builds its own scratch home via `_hermetic_route`).

**Suggestions:** None material; consider asserting in `test_build_app_has_no_execute_parameter` that `UnifiedApp.__init__` still *accepts* execute (pins the deliberate asymmetry so a later refactor doesn't widen scope by accident).

**Risk Assessment:** **MEDIUM** — composition-root surgery across every route, but the seam is verified, the old behavior's replacement is tested per route, and the helper design makes hermeticity structural rather than per-test discipline.

---

## 17-11

**Summary:** Verified hazard and correct fix: `load_settings` (`installer/settings.py:44-65`) catches only `(OSError, json.JSONDecodeError)` — `UnicodeDecodeError` is a `ValueError` but not a `JSONDecodeError`, so non-UTF-8 bytes crash every route today; the single `load_settings` caller in `setup.py` is `:1283` (confirmed by grep — the "17 callers" in CONTEXT is the transitive count, and the plan resolved it correctly); `SettingsStore` (`:97-116`) writes only in `set_link_mode`; the warning queue (`_pending_warnings` `wizard_app.py:2471`, `_flush_pending_warnings` `:2714`) exists as described.

**Strengths:**
- Single read + typed result (`LoadedSettings`) implements D-11's chosen option and keeps the rejected double-read probe rejected; the byte-equality-after-launch test (with the picker dismissed) pins "never overwrite a damaged file."
- Scope is narrowed exactly per RUN-LEDGER (warn only for invalid UTF-8/JSON; wrong-shape and unknown `link_mode` keep today's silent `Settings()` — the two existing tests keep their assertions), which avoids changing two tests' meaning.
- The dismissed-picker message composition (`w · Link mode unchanged…`) means answering the one first-run question can't erase the only notice the file was ignored — a subtle UX trap the plan closes.
- The store's warning flag clears only after `save_settings` returns — the "invalid on disk" contract holds by construction.

**Concerns:**
- **LOW — `on_mount` base-view flush timing is genuinely uncertain** (is the catalog's status widget mounted when `on_mount` runs?). The plan flags it and gives the tracer test the decision (`call_after_refresh` fallback) — acceptable, but it's the one place the plan bets on an unverified Textual lifecycle detail.

**Suggestions:** None beyond the tracer-decided fallback.

**Risk Assessment:** **LOW** — small surface, verified mechanism, one acknowledged lifecycle uncertainty with a decision protocol.

---

## 17-12

**Summary:** Docs-only, and its factual base is fully verified: `16-SECURITY.md` has the exact 7-column register and the convention "Total register rows: 60 (T-16-01..T-16-44 = 44, plus one T-16-SC per plan = 16)" (`:80`) — so the plan's 65 (48 numbered + 17 SC) and 75 (56 + 19) arithmetic is correct under the file's own convention; the T-16-49/50/51 collision is real and *between different threats* (`16-18-PLAN.md:317-319` vs `16-19-PLAN.md:192-194`); 16-17's threats T-16-45..48 (incl. accept T-16-47) are as described (`16-17-PLAN.md:268-271`); `16-VALIDATION.md` carries `audited: "2026-10-10"` and the map structure the plan appends to.

**Strengths:**
- Read-only discipline enforced by `git show --stat` per commit; a failing check is reported open, not fixed in place — the correct posture for an audit.
- Qualified threat IDs (`T-16-49 (16-18)` / `(16-19)`) plus an explanatory note is the least-bad handling of a closed milestone's numbering collision; renumbering was correctly rejected as out of scope.
- Evidence cited as `file::symbol` + pytest node id (not line numbers) is the right call given Phase 17's later plans edit the same files.
- Every recorded command is re-run by the verify step before the row is believed.

**Concerns:**
- **LOW — the objective's claim that "plan 17-13 re-runs every command on the final tree" overstates 17-13.** 17-13's gates run the full suite (`make test`) plus e2e — a row whose node id a later Phase 17 plan *deletes* would silently stop being re-proved rather than fail. I checked the specific new rows (16-17..19 → rcclean/`_judge_line`/handoff/owner-label tests): Phase 17 rewrites but does not delete those, so the actual exposure is nil for 17-12's own rows.
- **LOW — the verify's `eval` of command strings extracted from a markdown table** is brittle quoting (nested backticks in the `grep -o`), though the orchestrator already fixed similar command defects in 17-13 during plan checking.

**Suggestions:**
- Reword the cross-reference to "the full suite re-runs every test the rows cite" or add a `git grep` guard that no node id cited by the new rows is deleted by Phase 17's diff.

**Risk Assessment:** **LOW** — documentation with run-backed evidence and honest collision handling; no code touched.

---

## 17-13

**Summary:** The phase gate, disciplined correctly around the one irreversible thing it touches (main). Verified: `ci.yml` triggers only on `push: main` and `pull_request` (unfiltered, so a draft PR does trigger the workflow) with job name `validate & test on ${{ matrix.os }}` (`:14-21`) producing exactly the two context strings the protection body requires; `Makefile` has `validate` (`:34`), `test` (`:50`), `e2e` (`:53`); HEAD is the docs-only plan commit `5390577` on `72c9047` with a clean tree, so the `git diff --exit-code 72c9047 HEAD -- pyproject.toml uv.lock` base is sound; and the no-main-push discipline is real — the only `git push origin main` occurrences in the plan are the verification grep and the post-verification orchestrator step.

**Strengths:**
- The temporary-branch + draft-PR oracle is the correct mechanism to get macOS evidence before main is published, and the branch is deleted after each use so no re-run ever needs force.
- Two consecutive full-suite runs (flake detection), `pre-commit run --all-files`, `make e2e`, and the dependency freeze check make the local gate genuinely strong.
- CI-02 is handled with exactly the right amount of ceremony: blocking-human checkpoint, exact `gh api` body, undo command, "skip" path fully specified and *verified* (the Task 3 check branches on the recorded answer, and the autonomous run's orchestrator-recorded skip is attributed, not passed off as the user's choice).
- The `oracle sha:` + "HEAD differs only under `.planning/`" check keeps later docs-only commits from invalidating the recorded run — the subtle failure the plan-checker iteration already fixed.

**Concerns:**
- **LOW — Ubuntu 26 migration (2026-10-19) is an external assumption (A3)**; the plan handles it (triage runner image before blaming the phase), but the final oracle timing relative to that date is luck.
- **LOW — `make e2e`'s UNINSTALL_OK evidence shrinks under 17-09** (verified: the e2e uninstall gate is exit-code-only, so it stays green, but the transcript's meaning changes) — see 17-09's suggestion to record it.
- **LOW — the Task 3 "apply" path can only run post-verification** (correct per D-17), meaning this run's skip path is the one that executes — consistent with the ledger and the amendment note.

**Suggestions:**
- Record the pass2 semantic shift (17-09) and the sudo fail-fast note (17-03) in the phase-level SUMMARY so verification reads the e2e transcripts with the right expectations.

**Risk Assessment:** **LOW-MEDIUM** — nothing here can corrupt the repo or the host; the residual risks are external (runner migration, CI queue) and all have specified triage paths.

---

## Cross-Plan Assessment

**Requirement coverage (complete):** SAFE-01 → 17-02+17-05(Sublime)+17-04(Doctor) · SAFE-02 → 17-05 · SAFE-03 → 17-09 · SAFE-04 → 17-06 · SAFE-05 → 17-07 (+17-10's route exit codes) · SAFE-06 → 17-08 · SAFE-07 → 17-03+17-05(codex env) · SAFE-08 → 17-11 · SAFE-09 → 17-10 · R10 → 17-04 · CI-01 → 17-01+17-13 · CI-02 → 17-13 · CI-03 → 17-12. Every SPEC requirement R1–R13 maps to at least one plan with an acceptance test.

**Wave/dependency soundness:** I cross-checked `files_modified` for same-wave conflicts — there are none (e.g. wave 3's 17-08/17-09/17-10 touch disjoint files; `setup.py` is only edited by 17-10 within its wave; `tests/test_app.py` sequences 17-01 → 17-06 → 17-09 across waves). The wave-1 CI-oracle gate before wave 2 is the right dependency: everything later is judged against a green baseline. Cross-plan seams are explicit where they matter: 17-10's `_hermetic_route` reused by 17-11; 17-09's `plant_removal_fixtures` imported by `test_app.py`; 17-02's `fixture_runner` shared by three test modules; 17-06's `has_failure` consumed by 17-07/17-10.

**Ledger compliance (no contradictions found):** Q1 removal + dead-code deletion (17-05), Q2 link-mode-aware-only (17-08's flag), Q3 stress-run-then-fix-only-if-reproduced (17-01), CI-02 skip/hand-off (17-13's amendment + verified skip path), 17-11's dropped extension (only UTF-8/JSON warn), TDD-red-in-SUMMARY (every executor-rules block), and the temp-branch wave-1 oracle (17-01's orchestrator step) are all *implemented*, not merely cited. 17-04's flagged assumption (the executor sudo scan can't pass in Phase 17) is honest and correctly scoped to Phase 22 per the SPEC's own deferral.

**The honest gaps:** macOS-only claims (BSD `find` flags, macOS `sh` `time`, the macOS CI verdicts), the remote vendor-script facts (codex `install.sh`, graphify forms), and CI run history are taken from research/ledger records, not independently re-verified here — each has a specified oracle (the macOS job, the container probe re-run, `gh run` evidence) inside the plans themselves.

## Overall Risk Assessment

**LOW-MEDIUM.** This is an unusually well-researched, source-faithful plan set: of the dozens of line-level claims I checked across 13 plans, I found zero factual errors about the code and only trivial line-number drift; both flagship RED claims reproduce exactly. The genuinely risky work (17-07's worker/exit plumbing, 17-08's rollback matrix, 17-09's deliberate removal regression, 17-10's composition-root surgery) is MEDIUM individually and is uniformly backed by end-to-end pilot tests, shared fixtures, and acceptance greps that would catch a miss. No HIGH findings. The suggestions above are quality refinements (owner_cell assertion semantics, clean_rc confirm-time OSError, 17-08 recovery labeling, e2e/sudo notes in the phase summary), none blocking.

**Verdict: approved for execution** — proceed with the wave order as planned, folding in the four LOW-severity suggestions if convenient.

---

## Consensus Summary

Single reviewer this cycle (opencode-plan-review, source-grounded: it cited `file:line` evidence throughout and reproduced both RED claims of 17-01 live), so there is no cross-reviewer consensus to compute. Verdict: **approved for execution, no HIGH findings.** Overall risk LOW-MEDIUM.

### Agreed Strengths
- (single reviewer) Plans are source-faithful: dozens of line-level claims checked, zero factual errors, only trivial line drift.
- (single reviewer) RUN-LEDGER decisions (Q1 graphify removal, Q2 link-mode-aware-only, Q3 stress-run, CI-02 skip/hand-off, 17-11 warning scope, TDD red in SUMMARY, wave-1 CI oracle) are implemented, not re-litigated.
- (single reviewer) No same-wave `files_modified` conflicts; requirement coverage SAFE-01..09, CI-01..03 complete.

### Agreed Concerns
None (one reviewer). Actionable non-HIGH items not yet in the PLAN.md files:
- 17-01 (MEDIUM): owner_cell fix's primary option (`expected = owner_label(service.ownership_of("rg"))`) weakens the test to a propagation tautology; prefer the `artifacts_for=lambda _t: []` + brew-owning inventory alternative, or also assert an independently pinned label.
- 17-06 (LOW): a file deleted between preview and confirm makes the confirm `read_bytes()` raise; catch `OSError`, report "changed/disappeared; left untouched", add a test.
- 17-07 (LOW): add a cancel-path assertion for the rewritten `_run_updates` flow (completed updates kept, unrun ids in `not_attempted`, `has_failure` False).
- 17-08 (LOW): specify what happens when the recovery `set_link_mode(new_mode)` fails (stop and re-raise, or record the final mode in `PolicyMove`); and make the picker status name `failed` entries, not only `Moved: <ids>`.
- 17-09/17-13 (LOW): record in the 17-13 SUMMARY that e2e pass2 `UNINSTALL_OK` now proves only the proven-owned set (reinstall `already=` rises), as a Phase 19 baseline.
- 17-12 (LOW): the objective's "plan 17-13 re-runs every command on the final tree" overstates 17-13; reword to "the full suite re-runs every cited test" or add a guard that no cited node id is deleted by Phase 17.

### Divergent Views
None (one reviewer).
