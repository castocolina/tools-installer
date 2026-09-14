---
phase: 13
reviewers: [opencode-fallback]
reviewed_at: 2026-09-14T01:32:23Z
plans_reviewed:
  - .planning/phases/13-live-in-tui-install-execution-persistent-wizard-settings-ins/13-01-PLAN.md
  - .planning/phases/13-live-in-tui-install-execution-persistent-wizard-settings-ins/13-02-PLAN.md
  - .planning/phases/13-live-in-tui-install-execution-persistent-wizard-settings-ins/13-03-PLAN.md
  - .planning/phases/13-live-in-tui-install-execution-persistent-wizard-settings-ins/13-04-PLAN.md
  - .planning/phases/13-live-in-tui-install-execution-persistent-wizard-settings-ins/13-05-PLAN.md
  - .planning/phases/13-live-in-tui-install-execution-persistent-wizard-settings-ins/13-06-PLAN.md
  - .planning/phases/13-live-in-tui-install-execution-persistent-wizard-settings-ins/13-07-PLAN.md
models:
  opencode-fallback: "router-env/my-coding (reasoning=high)"
model_sources:
  opencode-fallback: "pinned"
failed_lanes:
  opencode-plan-review: "configured default reviewer instance (opencode, model router-env/my-plan-review) — router backend reports the mapped model 'claude/claude-opus-5' unavailable; reproduced 3x directly with `opencode run --model router-env/my-plan-review`"
  gemini: "gemini CLI binary is broken on this host — MODULE_NOT_FOUND for @google/gemini-cli/bundle/gemini.js under the pnpm global install; reproduced directly with `gemini --version`"
  codex: "codex CLI auth token expired/reused (401 refresh_token_reused) — requires `codex login` on this host, out of scope for this review run"
  cursor: "cursor-agent hit its account usage limit (ActionRequiredError: monthly Agent usage limit)"
  antigravity: "agy account not eligible for Antigravity (Google account verification required)"
---

# Cross-AI Plan Review — Phase 13

<!-- gsd:plan-revision-conflicts:begin -->
## Plan-Revision Conflicts
(none recorded)
<!-- gsd:plan-revision-conflicts:end -->

> **Reviewer-availability note:** the project's configured `review.default_reviewers` (`opencode-plan-review`, pinned to `router-env/my-plan-review`) could not run — the router backend reports the model it maps to (`claude/claude-opus-5`) as unavailable, reproduced 3 times outside this workflow. Every other detected reviewer CLI on this host also failed for host-local reasons unrelated to phase 13's plans: `gemini` (broken pnpm install, `MODULE_NOT_FOUND`), `codex` (expired/reused OAuth refresh token), `cursor` (monthly Agent usage limit reached), and `agy`/Antigravity (account not eligible). To avoid a zero-reviewer outcome, one fallback pass was run through the already-available `opencode` adapter using an alternate configured router model (`router-env/my-coding`, confirmed reachable) instead of the broken `my-plan-review` alias. This is a single-reviewer, source-grounded review — treat it as directional, not as a substitute for restoring the intended multi-CLI review roster once the router/auth/billing issues above are fixed.

## OpenCode Review (opencode-fallback)

# Phase 13 Plan Review

Grounded against the live tree (`installer/run.py`, `session.py`, `engine.py`, `wizard_app.py`, `ui_common.py`, `setup.py`, `app.py`, `policy.py`, `catalog_tui.py`, `cli.py`, `locations.py`, `version_cache.py`, `render.py`, `tests/test_docs.py`, `pyproject.toml`, `.claude/architecture.md`, the PRD deferred-fork note).

## 13-01

### Summary
Wave 0 does the right thing: prove the one unexercised Textual combination (`call_from_thread` + `push_screen_wait`) before any production helper exists, pin it with three green characterisation tests, and write the choice into `13-VALIDATION.md` so 13-05 cannot re-decide. That matches architecture rule 5 and RESEARCH Pitfall 1.

### Strengths
- Spike is throwaway; `git status --porcelain -- installer tests setup.py` must stay clean.
- Tests live in `tests/test_execute_screen.py` and import nothing from `installer.execute_screen` — rule 5 is explicit, not a slogan.
- Test 2 (`None` on escape) is the property D-05.3 needs; Test 3 is T-13-07 (loop stays live).
- DD-1 / DD-2 / DD-3 are recorded here and copied into the validation artifact, which CONTEXT.md required.
- Wave 0 boxes that this plan does not itself create are ticked only with a destination plan/task — that is how a validation contract stays honest.

### Concerns
- **LOW — architecture.md rule 2 vs mechanism A.** Rule 2 says modals return only via `push_screen(modal, callback)` (`.claude/architecture.md` lines 16–17). Mechanism A is `push_screen_wait`. If the spike picks A, 13-07 must record the exception or 13-05 will look like a rule break.
- **LOW — file reuse.** The same `tests/test_execute_screen.py` is the 13-04/13-05 dump. The three characterisation tests must keep passing when that file grows; the plan does not say so out loud.

### Suggestions
- In Task 3's `## Worker-to-modal mechanism` section, add one sentence: if A, this is a documented exception to architecture rule 2; if B, it is the rule-2 shape.
- State that 13-04/13-05 must not rename or skip the three characterisation tests.

### Risk Assessment
**LOW.** Correct de-risking order. Failure mode is a hung spike (timeout 120), which the verify block already treats as a fail.

## 13-02

### Summary
The right seam: a Popen `StreamingRunner` on the existing `Runner` / `MethodAwareRunner` protocols (`installer/run.py:15-21`, `installer/engine.py:126-127`) plus a between-tools `should_continue` on `run_installs` (`installer/session.py:69-125`). No engine/executor edits. DD-1's weak cancel is expressed as "not attempted = input ids minus outcomes," which avoids a new `InstallStatus` and a `summarize`/`render` cascade.

### Strengths
- `emit` is a required constructor argument; `_current()` raises if `set_tool` was not called — that is D-05.2 as structure, not a comment. The abandoned branch's `captured_runner=None` path cannot recur.
- `stdin=DEVNULL`, `stderr=STDOUT`, same-thread read loop match RESEARCH Pitfall 3. `OSError` → `CommandError(..., 127)` matches `run_command` (`installer/run.py:48-49`) and `run_output` (`:85-86`).
- No timeout, with the same rationale already in `run_output` (`:74-76`).
- `should_continue` default `None` keeps `run_wizard` (`installer/app.py:151-158`) and existing `tests/test_session.py` positional calls working — *if* it is appended as keyword-only after `catalog`, not inserted between `on_mismatch` and `catalog`.
- Engine-untouched gate plus the "wrong merge-base" precondition is the right kind of paranoia on this branch.

### Concerns
- **HIGH — Wave 1 `make validate` / vulture vs rule 5.** `[tool.vulture] paths = ["installer"]` (`pyproject.toml:59-61`). After this plan, `StreamingRunner` and `STREAM_DETAIL_LINES` have no production caller until 13-04 (Wave 2). Plan-level verification still requires `make validate`. Vulture does not look at tests. 13-01 avoided this on purpose; this plan does not. Silencing vulture is forbidden.
- **MEDIUM — "live" lines vs pipe buffering.** `text=True, bufsize=1` line-buffers the *parent*. A child writing to a pipe is typically fully buffered. `print()` without `flush=True` will not deliver the first line before `sleep`. Vendor tools (`pnpm`, SDKMAN) often detect a non-TTY and burst. D-03 can look green in tests and still be burst-at-exit in production unless the test child uses `flush=True` / `-u`, and the plan should say the production runner cannot force vendor scripts to line-buffer.
- **MEDIUM — `should_continue` placement.** "Keyword-only, after `on_mismatch` and before `catalog`" cannot both be true without a `*` that also makes `catalog` keyword-only. Today `catalog` is the last positional (`session.py:69-76`). Inserting a new positional between them would steal a 7th positional argument. Put `*, should_continue=None` *after* `catalog`.
- **LOW — Popen without `finally: wait()`.** If `emit` raises, the child can be orphaned. Wrap the read/`wait` in `try/finally`.

### Suggestions
- Drop `make validate` from this plan's verification; keep `pyright`/`ruff` on the two files. Re-run full `make validate` in 13-04 (first caller) and 13-07.
- Specify the incremental test child as `python -u -c "print('a', flush=True); ..."` so the timestamp gap actually measures streaming.
- Write the new parameter as `catalog=..., *, should_continue: Callable[[], bool] | None = None`.

### Risk Assessment
**MEDIUM.** Seam choice is sound; Wave 1 cannot pass its own vulture gate, and streaming tests can pass without proving live delivery.

## 13-03

### Summary
Pure-core settings module mirroring `installer/version_cache.py:154-197` (`{"version": 1, ...}`, `ensure_dir` + `atomic_write_text`, degrade on `OSError`/`JSONDecodeError`). Closed-set check against `LINK_MODES` matches `installer/cli.py:54-59` and protects `rc_paths_for_mode` / `ban_rc_paths` (`installer/locations.py:45-65`). DD-3 as two tested functions is the right place for the rule (architecture rule 4).

### Strengths
- `Settings.link_mode=None` vs `"centralized"` is the whole first-run prompt. Collapsing them would re-prompt forever or never prompt.
- Two-way `LINK_MODES` vs CLI `choices=` (`parse_args` round-trip + `ast` of the literal) is the assertion that actually prevents drift; skipping argparse's "invalid choice" text is correct for 3.11 vs 3.12.
- `SettingsStore.set_link_mode` does not catch `OSError` — `run_live` (`installer/ui_common.py:41-50`) is the one apply workflow.
- Flag override never calls `set_link_mode`. That is DD-3 as code, not as a `setup.py` if-chain.
- `grep -c "open("` gate forces `Path.read_text()` / `atomic_write_text`, matching `version_cache.py`.

### Concerns
- **HIGH — same Wave 1 vulture / rule 5 hole, worse.** The entire module is unused by production until 13-06 (Wave 4). Task 2's "every symbol is either exported for 13-06 or covered by a test" does not satisfy vulture (`paths = ["installer"]`). `make validate` in this plan's acceptance will fail, and architecture rule 5 is the rule 13-01 was written to obey.
- **LOW — `save_settings` of `Settings()`.** Envelope becomes `{"version": 1, "link_mode": null}`. `load_settings` must treat JSON `null` as "never chosen," not as a type error that also returns `Settings()`. Say so in the load contract.

### Suggestions
- Do not run vulture until 13-06 lands the composition-root caller, or land `settings.py` in 13-06 Task 1 instead of Wave 1. Do not whitelist symbols.
- One test: `save_settings(path, Settings())` then `load_settings(path).link_mode is None`.

### Risk Assessment
**MEDIUM.** Design is the one this repo already uses for `versions.json`. Sequencing fights rule 5 and the Wave 1 quality gate.

## 13-04

### Summary
The tracer is the phase. `CatalogScreen.Decided` currently does `self.exit(message.result)` (`installer/wizard_app.py:1669-1670`). Pushing a `ModalScreen` instead of an `AppScreen` is the correct reading of D-01: `AppScreen` indexes `VIEW_BY_NAME` (`installer/ui_common.py:339`) and would add a seventh nav target, breaking `_navigable` (`wizard_app.py:1630-1636`). Splitting the interactive path so it never calls `run_wizard` is RESEARCH Pitfall 2 option (b) and matches `_choose_tools` (`installer/app.py:94-97`): `--all` / `--categories` never touch `select_catalog`.

### Strengths
- Confirm text is rendered in `on_mount` and the worker starts only on `action_start` (or after that render when `unattended=True`). That is D-05.1 / audit finding A, and it is testable ("fake install not invoked before enter").
- `attributed_install` sets the tool through the existing `Install` seam (`session.py:38-50`) before `install(...)`. Attribution cannot vanish behind an optional runner.
- Same-worker `wire_path` + `verify` via `Console(file=io.StringIO())` is the `_apply_fix` pattern (`setup.py:473-486`).
- `exit_on_error=False` + try/finally posting `InstallRunFinished` copies `_apply_daemon_default_worker` (`wizard_app.py:1546-1578`).
- `execute=None` keeps today's exit-with-ids for every existing `UnifiedApp(...)` site (comment at `wizard_app.py:1476-1480`).
- `grep -c "_select_catalog" setup.py` is 0 is the right gate: the name is in comments at `setup.py:523` and `:761` today, not only in the def.
- A1 (`clean_rc_duplicates` stays console after `.run()`) is an explicit scope cut, not a miss. `_verify_and_clean` (`setup.py:705-718`) is the current pair; dropping the second `run_doctor` on the interactive path is correct if the screen already rendered it.

### Concerns
- **MEDIUM — `run_live(run_installs)` error path.** `run_live` only catches `OSError` and `CommandError` (`ui_common.py:41-50`). `install_tool` already swallows `CommandError` (`engine.py:136`). If something still raises, `run_live` returns `(None, message)`. The worker must still post `InstallRunFinished` with a usable `summary`/`error`. The plan names the `error` field and does not specify the empty-outcomes case.
- **MEDIUM — `ctrl+c` during a run.** `action_hard_abort` always `exit(None)` (`wizard_app.py:1679-1681`). That tears down the app on top of a live `Popen`. DD-1 refuses `terminate()`; hard abort is a worse kill. At least document that ctrl+c is process abort, not weak cancel, and that the child may be orphaned.
- **MEDIUM — last `install_summary` wins.** After D-02's keypress the screen pops to the catalog; the app keeps running. A second batch overwrites `install_summary`. `main`'s exit code (`setup.py:791-793`) then reflects only the last run. Say that, or exit the app after the first completed run.
- **LOW — stale `Decided` docstring.** `catalog_tui.py:193-195` still says the host forwards the message to `App.exit`. `files_modified` omits that file.
- **LOW — "seventeen" vs "nine".** Plan says seventeen `UnifiedApp(...)` sites; the class comment says nine outside `setup.py` (`wizard_app.py:1476`). Count before writing the compatibility sentence.

### Suggestions
- If `run_live` returns `None` for the install step, post `InstallRunFinished` with `outcomes=[]`, `error=the message`, `finished=True`.
- Bind hard abort during a run to the same status line as mid-run escape, or document the orphan-child risk in 13-07 residual scope.
- One-line update to `CatalogScreen.Decided`'s docstring: host pushes `ExecuteScreen` when `execute=` is set.

### Risk Assessment
**MEDIUM.** Architecture is right (ModalScreen, option b, one worker). The underspecified `run_live` failure path and post-run app lifetime are the ways a tracer can look green and still mis-exit.

## 13-05

### Summary
This plan closes the capability gap the tracer left: in-app `_ask_mismatch` (`setup.py:310-317`), DD-1's status list and weak cancel, and the post-run `render_*` sequence (`installer/app.py:160-169`). Dismissal → `skip` plus an attributed log line is the conservative security default (T-13-13) and D-05.3 made concrete.

### Strengths
- `ask_from_worker` is "whatever 13-VALIDATION.md recorded," not a second spike. 13-01 exists so this task cannot waffle.
- Labels are verbatim from `_ask_mismatch`. Nested `ModalScreen` on `ExecuteScreen` matches `TimePickerScreen` on Policies (`wizard_app.py:1353-1386`), including letter-prefixed ids.
- `on_mismatch=None if inputs.unattended else self._ask_mismatch` is `run_wizard` line 157.
- `on_outcome` default `None` keeps 13-04's `attributed_install` callers working.
- Not-attempted stays a set difference, not `InstallStatus.CANCELLED` — `summarize`'s closed bucket map (`session.py:135-143`) does not need a new key.
- Post-run order asserted by `index()` on the log text, using the same `render_*` helpers, so the in-app words cannot drift from the console words.
- `c` is added to `execute-keys`, not only `BINDINGS` — same reason the `u` key had to land in `VIEWS`.

### Concerns
- **MEDIUM — mechanism A vs rule 2, now in production.** If 13-01 picked A, `ask_from_worker` is the first production `push_screen_wait`. 13-07 must write that down. If B, the worker `event.wait()` plus a main-thread callback is the proven shape; do not also keep a `push_screen_wait` branch.
- **LOW — cancel vs mismatch modal.** While `ChecksumMismatchScreen` is on top, ExecuteScreen's `c` does not fire. Worst case is one in-flight tool plus one unanswered prompt — acceptable, but the status line should say the modal is waiting, not that cancel is available.
- **LOW — escape vs `c`.** 13-04: escape mid-run does not pop. 13-05: `c` cancels the batch. Two "stop" keys with different meanings. `execute-keys` must name both.

### Suggestions
- One Pilot case: mismatch modal visible ⇒ `c` does not set the cancel event until the modal dismisses (or it does — pick one and test it).
- Keep the three 13-01 characterisation tests; lift shape, don't delete the throwaway app until `ask_from_worker` is what they call.

### Risk Assessment
**MEDIUM.** Behavior is specified well. Residual risk is the worker-to-modal combination and nested-modal key routing, which 13-01 is supposed to have already paid for.

## 13-06

### Summary
This is the persistence half, and it correctly treats "persist `link_mode`" as insufficient: `_build_app` snapshots `link_mode` into `rc_paths` (`setup.py:392`), `ban_policy(apply_rc_paths=...)` (`:447-449`), `tweak_policy(ensure_sourced_from=...)` (`:460`), `_apply_fix` (`:484-485`), and the preview string (`:488-492`). A mid-session change that does not re-read those is a silent no-op (aliases in a `~/.myshellrc` split mode never sources). Folding the picker into Policies with no new `VIEWS` row is DD-2 and rules 1–2.

### Strengths
- `ban_policy` / `tweak_policy` accept value-or-callable and normalize to a reader called at apply time. Existing list/tuple call sites in `tests/test_policy.py` stay valid — same optional-kwargs convention as `UnifiedApp` (`wizard_app.py:1476-1480`).
- `_time_picked`'s `if value is None: return` (`wizard_app.py:1257-1258`) is the silent-cancel anti-pattern. `_link_mode_picked` is specified as the same structure *except* that branch sets a warn status. That is D-05.3 with a cited counterpart.
- `m` in the `policies` `View.actions` string (`ui_common.py:170` is currently `"space toggle"`) is mandatory: `FooterBar.render_text` (`:208-210`) is the only footer the user sees.
- `DoctorScreen._fix_preview` is a `str` appended in `_refresh_body` (`wizard_app.py:300`); `enter_view` already calls `_refresh_body` (`:247-262`). Widening to `str | Callable[[], str]` is the same "predicate, not its result" comment already on `guard_state` (`:189-192`).
- Flag does not persist; only the picker calls `set_link_mode`. Test reads the file back. DD-3.
- `prompt_link_mode` allowlist matches `apply_daemon_default` (`setup.py:519-528`): wizard + interactive `make fix` only.
- Rewording `_questionary_tty_io` / `_ask_checkbox` instead of deleting them is load-bearing: those blocks are why questionary gets `/dev/tty` (`setup.py:169-187`, `:259-265`). The grep gate ("each library owns fd 0", "Every ask_* helper needs this") is the right way to keep the rationale.

### Concerns
- **HIGH — first-run status is posted on the catalog while `make fix` is on Doctor.** `_run_fix` opens `_build_app(..., initial_view="doctor")` (`setup.py:640-645`). Task 3 always writes OK/warn/error onto the catalog `StatusLine`. After dismiss, the user is looking at Doctor (`show_view("doctor")` in `on_mount`, `wizard_app.py:1541-1542`). The explanation D-05.3 requires is on a hidden screen. Post to `self.screen`'s status (the visible `AppScreen`), not `self.catalog.status`.
- **MEDIUM — first-run picker vs daemon worker.** `on_mount` starts `_apply_daemon_default_worker` then (as planned) pushes `LinkModeScreen`. Two overlapping first-run surfaces. Probably harmless (daemon is macOS, independent of link mode) but the picker should be last and the only modal.
- **LOW — "asked at most once" vs dismiss.** Dismiss does not persist, so the next launch prompts again. That matches `link_mode_needs_choice`. Don't claim "once per machine" in success criteria without "once answered."
- **LOW — `PoliciesScreen.BINDINGS` already has `l` and `t`.** `m` is free. Confirm no catalog-level `m`.

### Suggestions
- `_first_link_mode_picked`: `screen = self.screen; if isinstance(screen, AppScreen): screen.status.set(...)`. Catalog is the fallback, not the only target.
- One `tests/test_setup.py` Pilot (or unit on the callback) with `initial_view="doctor"` + `prompt_link_mode=True` + escape, asserting Doctor's `StatusLine.text` is non-empty.
- Keep `_ask_mismatch` / `_ask_select` for the headless path; the `questionary.select` count gate of 1 is correct.

### Risk Assessment
**MEDIUM.** Live re-read of ban/tweak/fix/preview is the important correctness fix. The first-run message on the wrong screen is a D-05.3 miss on the `make fix` entry point.

## 13-07

### Summary
Close-out is in the right place: `.claude/architecture.md` after Phase 12.4 (`:582`), PRD deferred-fork bullet (`docs/prds/unified-ui-redesign-v1.0-prd.md:134-138`) corrected in place, `tests/test_docs.py` gains a second phrase-pin test matching the Phase 12 pattern (`tests/test_docs.py:5-26`). Residual scope (A1, weak cancel, `link_mode`-only) is written as decisions. The engine-untouched diff is only meaningful here, where it sees every plan's commits.

### Strengths
- Six architecture paragraphs match what a later contributor cannot infer: IO adapter not a second engine, ModalScreen not a view, structural attribution, weak cancel, DD-2/DD-3, live-read of link mode.
- PRD keeps the original trade-off and appends the outcome — it does not rewrite history.
- Phase-diff assertion against new skip/xfail/noqa/`type: ignore` is the anti-bypass gate `CLAUDE.md` wants. Pre-existing `BLE001` in `engine.py` is correctly excluded.
- Residual scope names `clean_rc_duplicates`, child-kill, and extra settings keys with decision ids.

### Concerns
- **MEDIUM — engine-untouched merge-base.** Both 13-02 and 13-07 measure from `git merge-base HEAD feat/tui-interaction-consistency`. The 13-02 precondition already warns this range can include pre-Phase-13 churn. If 13-07 sees a non-empty diff, the plan says "narrow BASE, don't edit the engine." Repeat that in Task 2's verify `fails_when` so an executor does not "fix" the gate by touching `engine.py`.
- **LOW — record the worker-to-modal exception.** If 13-01 picked A, architecture.md must mention `push_screen_wait` as the checksum-mismatch seam, or rule 2 will be used to rip it out later.
- **LOW — `test_docs.py` "exactly two test functions."** Fragile if another phase adds a third. Prefer "a Phase 13 test exists and the Phase 12 test is unchanged."

### Suggestions
- Add `call_from_thread` / recorded mechanism name to the required-phrase tuple if A shipped.
- Put ctrl+c-orphans-child in residual scope if 13-04 does not bind hard abort.

### Risk Assessment
**LOW.** This plan cannot save a wrong 13-04/13-06, but it records the design in the place this repo actually reads.

---

## Overall risk assessment

**MEDIUM.**

The phase is an IO-adapter job and the plans treat it that way: existing `run_installs` / `install_tool` / `configure_path` stay owners; `StreamingRunner` is the one new I/O primitive; `feat/install-experience` is reference-only; D-05.1–3 are tested, not hoped for. DD-1/2/3 are consistent across all seven files.

What keeps this from LOW:

1. **Wave 1 cannot pass `make validate` as written.** `StreamingRunner` (13-02) and `installer/settings.py` (13-03) have no production caller until Waves 2 and 4. Vulture scans `installer/` only (`pyproject.toml:59-61`). 13-01 already solved this for `ask_from_worker`; 13-02/13-03 reintroduce it. Fix: drop vulture from Wave 1 plan gates, or don't land those modules until their first caller.
2. **13-06 first-run status on catalog while `make fix` shows Doctor** (`setup.py:640-645`, `wizard_app.py:1541-1542`) — a D-05.3 hole on a real entry point.
3. **Streaming "liveness" is easy to test-cheat** without `flush=True` / `python -u`, and vendor children on a pipe may still burst.
4. **`should_continue`'s "keyword-only between `on_mismatch` and `catalog`" fights the current positional signature** (`session.py:69-76`).

Do those four and the rest is executable: tracer in 13-04, mismatch/cancel/report in 13-05, live settings in 13-06, record in 13-07. Headless `--all` / `--yes` stays the console `run_wizard` path (`app.py:94-97`, `setup.py:764-786`) and is structurally isolated.

---

## Consensus Summary

Only one reviewer lane produced a usable, source-grounded review this cycle (`opencode-fallback`); every other detected reviewer CLI failed on this host for infrastructure/auth/billing reasons unrelated to the plans (see the frontmatter `failed_lanes` and the reviewer-availability note above). There is no cross-reviewer agreement to synthesize — treat every finding below as single-reviewer, source-grounded, and not yet corroborated.

### Agreed Strengths
Not applicable — only one reviewer ran.

### Agreed Concerns
Not applicable — only one reviewer ran. The reviewer's own three HIGH findings are:
- 13-02: `StreamingRunner`/`STREAM_DETAIL_LINES` have no production caller until Wave 2, so Wave 1's `make validate` (vulture, `installer/` only) fails as currently scoped.
- 13-03: `installer/settings.py` has no production caller until Wave 4 (13-06), same vulture failure mode, worse because the whole module is unused.
- 13-06: first-run link-mode status is posted to the catalog `StatusLine`, but `make fix` opens the app on the Doctor view — the status lands on a screen the user isn't looking at.

### Divergent Views
Not applicable — only one reviewer ran.
