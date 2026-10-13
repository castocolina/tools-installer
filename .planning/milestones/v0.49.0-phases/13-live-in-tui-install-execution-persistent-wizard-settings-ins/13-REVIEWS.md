---
phase: 13
reviewers: [opencode-fallback]
reviewed_at: 2026-09-14T04:09:02Z
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
  opencode-plan-review: "configured default reviewer instance (opencode, model router-env/my-plan-review) — retried synchronously this cycle (respecting the review.timeouts.opencode=1500s raised in cycle 2). Unlike cycle 2's ~25-minute wall-clock timeout, this cycle's attempt failed fast (within seconds): opencode's own log shows the agent loop exiting after step 1 with no final assistant message (#1936 'agent ended its turn with no final message'), same failure signature as cycle 2 but a different failure mode (quick loop-exit vs outer timeout). Per instructions, only one real attempt was spent on this lane before falling back."
  opencode-fallback-first-attempt: "the proven fallback (opencode, model router-env/my-coding) was tried immediately after the default lane failed, and ALSO hit the same #1936 'no final assistant message' failure on the first attempt — a regression from cycles 1-2 where this lane succeeded on the first try. A second, identical retry of the same lane/model succeeded (see reviewers: [opencode-fallback] above), confirming the first failure was transient flakiness in the opencode agent loop on this large source-grounded prompt, not a durable block. gemini remains broken (MODULE_NOT_FOUND, unchanged since cycle 1). codex remains blocked by an expired/reused OAuth refresh token (401 token_expired, reproduced directly this cycle). cursor-agent is logged in but still hits its account's monthly Agent usage limit (reproduced directly this cycle). agy/Antigravity still reports account ineligibility (Google account verification required, reproduced directly this cycle, unchanged since cycle 1 — cycle 2 had not re-probed it)."
---

# Cross-AI Plan Review — Phase 13

<!-- gsd:plan-revision-conflicts:begin -->
## Plan-Revision Conflicts
(none recorded)
<!-- gsd:plan-revision-conflicts:end -->

> **Reviewer-availability note (cycle 3, FINAL — max_cycles=3):** the project's configured
> `review.default_reviewers` (`opencode-plan-review`, pinned to `router-env/my-plan-review`) was
> retried synchronously this cycle, respecting the `review.timeouts.opencode=1500s` raised in
> cycle 2. Rather than the ~25-minute outer-timeout failure seen in cycle 2, this cycle's attempt
> failed fast (within seconds of starting) with the same underlying CLI defect (`#1936`: the
> opencode agent loop exits after its first step with no final assistant message) confirmed
> directly against `~/.local/share/opencode/log/opencode.log`. Per the cycle-3 instructions, only
> one real attempt was spent on the default lane before falling back to the proven alternate
> (`opencode` with `router-env/my-coding`). That fallback's *first* attempt also hit the identical
> `#1936` failure — a new development, since it succeeded on the first try in both cycle 1 and
> cycle 2 — but an immediate, otherwise-identical retry of the same lane and model succeeded end
> to end and produced a full 7-plan source-grounded review. This confirms the failure is transient
> flakiness in the opencode agent loop under this prompt's size/effort combination, not a durable
> regression. `gemini` remains broken by the same `MODULE_NOT_FOUND` pnpm install defect reported
> in cycles 1-2. `codex` remains blocked by an expired/reused OAuth refresh token (reproduced
> directly this cycle: `401 token_expired` against `wss://chatgpt.com/backend-api/codex/responses`).
> `cursor-agent` is logged in (as in cycle 2) but still hits its account's monthly Agent usage
> limit (reproduced directly this cycle). `agy`/Antigravity was re-probed this cycle (cycle 2 did
> not re-probe it) and still reports account ineligibility requiring Google account verification,
> unchanged since cycle 1. As in cycles 1 and 2, this is a single-reviewer, source-grounded review
> — treat it as directional pending the router/auth/billing/CLI-stability issues above being fixed,
> though its content is a thorough, fully-cited 7-plan audit that explicitly re-verified every one
> of cycle 2's five incorporated fixes against live source rather than trusting the plan ledgers.

## OpenCode Review (opencode-fallback)

Cycle 3 plan review — I'll load the review skill, then verify the five cycle-2 items against live source before scoring each plan.
The phase glob missed; locating the real plan files and grounding cycle-2 claims against source.
Plans are on disk; next I'll ground the five cycle-2 claims and the live signatures they depend on.
Glob missed the long phase dir; listing it directly and grounding the cycle-2 claims in source.
Cycle-2 items look incorporated in plan text; next I'll check the live seams they depend on so any leftover gap is real, not ledger-only.
Cycle-2 plan text checks out; I'll verify the live seams those five items depend on, then look for anything new.
Cycle-2 plan text looks incorporated; I'll count the live seams and hunt for anything the ledger still missed.
Need one more pass on worker try/finally, `_views` construction, and a few remaining seams before I write the cycle-3 verdict.
Need to confirm `_views` actually includes Doctor/Policies — the 13-06 fallback depends on that.
Checking whether the merge-base branch the gates depend on actually exists, and scanning for leftover contradictions.

Cycle-3 source audit of all 7 plans against live `run.py`, `session.py`, `wizard_app.py`, `setup.py`, `engine.py`, `ui_common.py`, `policy.py`, `cli.py`, `catalog_tui.py`, `pyproject.toml`. Cycle-2's five items are closed in plan text, not just ledger rows. No new HIGH/MEDIUM.

## Cycle-2 disposition audit

| # | Item | Verdict | Evidence |
|---|---|---|---|
| 1 | MEDIUM: `finally: wait()` without drain | **RESOLVED** | Drain-to-EOF then close then `wait()` (`13-02-PLAN.md:220-242`); named test `test_streaming_runner_reaps_child_when_emit_raises`; T-13-26; comment-filtered `terminate`/`kill` grep stays 0 |
| 2 | LOW: load-contract `str` vs `null` | **RESOLVED** | Four ordered steps; standalone `str` gate forbidden ahead of `raw is None` (`13-03-PLAN.md:189-205`); literal-null fixture + `never chosen` grep |
| 3 | LOW: hard `self.catalog` fallback | **RESOLVED** | `self._views.get(self.current_view) or self.catalog` (`13-06-PLAN.md:372-389`); live `_views` holds doctor/uninstall/policies (`wizard_app.py:1473-1474`, `:1495-1509`); Doctor Pilot + grep gate |
| 4 | LOW: leftover `2 passed` | **RESOLVED** | Plan-level `<verification>` is "green, with NO assertion on how many tests" (`13-07-PLAN.md:333`); no remaining count gate |
| 5 | LOW: tautological `sanitize_log_line` grep | **RESOLVED** | Dropped; scope rule is cross-module only (`13-07-PLAN.md:247-255`, `:299`); automated still greps the four real callers |

---

## 13-01

**Summary.** Wave 0 still de-risks the unexercised `call_from_thread` + modal combo before any production helper exists. Both cycle-1 LOWs remain in Task 3's action, acceptance, and grep gates. Nothing new.

**Strengths**
- Spike is throwaway; characterisation tests import nothing from `installer.execute_screen` (architecture rule 5).
- Rule-2 ruling is a required sentence keyed off `MECHANISM=A|B` (`.claude/architecture.md:16-17`).
- Three test names are pinned so 13-04/13-05 cannot drop them silently.

**Concerns**
- None new. Both ledger rows check out.

**Suggestions**
- None.

**Risk Assessment:** LOW.

---

## 13-02

**Summary.** Seam choice is still right: Popen `StreamingRunner` on `MethodAwareRunner` (`installer/run.py:15-21`, `installer/engine.py:126-127`) and keyword-only `should_continue` appended after `catalog` (`installer/session.py:69-76`). Cycle-2's drain-then-wait is now in Task 1 with a hang-failing test, not just a comment.

**Strengths**
- Vulture half of the HIGH is measured: `[tool.vulture] min_confidence = 80` (`pyproject.toml:59-61`); unused class/const score 60%. Gate asserts `uv run vulture` with `pyproject.toml` unmodified.
- Incremental child is `python -u` + `flush=True`; docstring records vendor tools on a pipe may still burst.
- `should_continue` tail is `catalog=..., *, should_continue=...` with an `inspect.signature` gate. Live signature has `catalog` last and positional (`session.py:69-76`).
- Drain-then-wait is arithmetic, not assertion: ~64 KiB pipe, raising `emit` stops the reader, bare `wait()` hangs 13-04's worker (T-13-07). Close-under-live-child declined as terminate-by-EPIPE (DD-1).
- Rule 5 named and enforced at 13-07, not waived.

**Concerns**
- None new. Cycle-2 MEDIUM is in the task text, the named test, T-13-26, and the grep gates.

**Suggestions**
- None.

**Risk Assessment:** LOW.

---

## 13-03

**Summary.** Persistence still mirrors `version_cache.py` (`installer/version_cache.py:137-175`, `:196-197`) with a closed set matching `installer/cli.py:54-59`. The load contract is now two outcomes with ordered steps; the cycle-2 wording fight is gone.

**Strengths**
- `Settings.link_mode=None` vs `"centralized"` stays the first-run discriminator.
- Two-way `LINK_MODES` vs CLI `choices=` (parse_args + `ast`) is still the drift check.
- `set_link_mode` does not catch `OSError`; `run_live` (`installer/ui_common.py:41-50`) remains the one apply workflow.
- Null path asserted against an on-disk fixture, not only through `save_settings` round-trip.
- Every export mapped to a 13-06 adopter; 13-07 greps `SettingsStore` / `link_mode_needs_choice` in `setup.py`.

**Concerns**
- None new. Cycle-2 LOW is incorporated (`13-03-PLAN.md:189-205`).

**Suggestions**
- None.

**Risk Assessment:** LOW.

---

## 13-04

**Summary.** Tracer architecture is unchanged and still right: `ModalScreen` not `AppScreen` (`installer/ui_common.py:308-339`, `installer/wizard_app.py:1630-1636`), interactive path never calls `run_wizard` (`installer/app.py:94-97`). All cycle-1 items stay in the task text with tests. Construction-site count matches the tree.

**Strengths**
- `run_live` `(None, message)` path posts `InstallRunFinished` with `summarize([])`, never `None` (`installer/ui_common.py:41-50`, `installer/engine.py:136`).
- `install_summary` accumulates; `setup.py:791-793` would otherwise report only the last batch.
- `catalog_tui.py` is in `files_modified`; `Decided` currently claims unconditional `App.exit` (`installer/catalog_tui.py:193-195`) and the plan rewrites both branches.
- Live count: 16 `UnifiedApp(` constructions (1 in `setup.py:574`, 15 in tests: wizard_app 5, policies_e2e 6, uninstall_e2e 3, catalog_tui 1). Comment at `wizard_app.py:1476` still says nine; plan requires that comment gone.
- Ctrl+c disclosure + 13-07 residual is the right branch: `action_hard_abort` is unguarded and priority (`wizard_app.py:1417-1420`, `:1679-1681`).
- Sits behind 13-02's drain-then-wait; emit may raise and the runner must survive it.

**Concerns**
- None new.

**Suggestions**
- None.

**Risk Assessment:** LOW.

---

## 13-05

**Summary.** Capability gap after the tracer is still the right scope. Cycle-1 items (rule-2 production use, `c` under the mismatch modal, three stop keys, characterisation-test preservation) are in Task 1-2 with Pilot gates.

**Strengths**
- `ask_from_worker` is "whatever 13-VALIDATION.md recorded," not a second spike (`13-05-PLAN.md:93-108`).
- Labels stay verbatim from `_ask_mismatch` (`setup.py:310-317`); `on_mismatch=None if unattended` matches `run_wizard` (`installer/app.py:157`).
- Dismissal -> `skip` is the only `MismatchChoice` that does not install an unverified artifact (`installer/session.py:16-17`, `:109-121`).
- Not-attempted stays a set difference; `summarize`'s closed map is untouched (`session.py:135-143`).
- Nested-modal `c` is chosen and tested (`13-05-PLAN.md:264-272`).

**Concerns**
- None new.

**Suggestions**
- None.

**Risk Assessment:** LOW.

---

## 13-06

**Summary.** Persistence half still treats live re-read as the real bug (`setup.py` snapshots `rc_paths` today). Cycle-1 HIGH stays closed (visible `AppScreen.status`, Doctor Pilot). Cycle-2's hard-catalog residual is replaced by a registry lookup that cannot land on a hidden screen.

**Strengths**
- `ban_policy` / `tweak_policy` value-or-callable keeps existing list/tuple call sites (`installer/policy.py:218-225`).
- `_link_mode_picked` copies `_time_picked` except the `None` branch sets a warn (`wizard_app.py:1256-1258`).
- `m` is unbound in `installer/` today; Policies already has `l`/`t` (`wizard_app.py:932-935`); Catalog has `r`/`d`/`u` (`catalog_tui.py:201-205`). Footer comes from `View.actions` (`ui_common.py:170`, `:208-210`).
- Fallback `self._views.get(self.current_view) or self.catalog` is correct on the live tree: `_views` starts as non-base catalogs (`wizard_app.py:1473-1474`) then gains doctor/uninstall/policies (`:1495-1509`); `current_view` updates in `show_view` (`:1628`); `catalog` is `_catalogs[BASE_VIEW]` (`:1591-1593`). When `current_view` is the base catalog, `_views.get` is None and `or self.catalog` is the only arm that should fire.
- `prompt_link_mode` allowlist matches `apply_daemon_default`. Picker is last in `on_mount` (`wizard_app.py:1543-1544`).
- "Once per ANSWER," not once per machine; dismissed picker leaves `link_mode: null`.

**Concerns**
- None new. Cycle-2 LOW is in the action, the Doctor Pilot tripwire, T-13-17, and the `grep -c 'self._views.get(self.current_view)'` gate (`13-06-PLAN.md:412`, `:420`).

**Suggestions**
- None.

**Risk Assessment:** LOW.

---

## 13-07

**Summary.** Close-out is in the right place (architecture.md after Phase 12.4 at `.claude/architecture.md:582`, PRD deferred-fork at `docs/prds/unified-ui-redesign-v1.0-prd.md:134-138`, `tests/test_docs.py:5-26`). Cycle-1 and cycle-2 items are in Task 1-2, including the four cross-module rule-5 greps that close 13-02/13-03.

**Strengths**
- Engine-untouched `fails_when` says a pre-Phase-13 diff is a wrong baseline, never a reason to edit `engine.py`. `feat/tui-interaction-consistency` exists locally; merge-base resolves.
- Worker-to-modal name joins the Phase 13 phrase tuple when A shipped.
- Residual scope names `clean_rc_duplicates`, weak cancel, `link_mode`-only, ctrl+c orphan (`action_hard_abort` grep), and dismissed-picker reprompt.
- `pyproject.toml` must be byte-identical across the phase (`fail_under = 90`, `min_confidence = 80`).
- `test_docs.py` count assertion is gone from Task 1, acceptance, `<automated>`, and `<verification>`.
- Rule-5 list is the four greps that can actually prove a caller: `StreamingRunner` / `should_continue` in `execute_screen.py`, `SettingsStore` / `link_mode_needs_choice` in `setup.py`.

**Concerns**
- None new. Both cycle-2 LOWs are incorporated (`13-07-PLAN.md:247-255`, `:333`, `:367-368`).

**Suggestions**
- None.

**Risk Assessment:** LOW.

---

## Cross-plan

DD-1 / DD-2 / DD-3 stay consistent across all seven files. Interactive vs headless split (13-04 option b) still isolates `--all`/`--yes` (`app.py:94-97`). No new view row (`ui_common.py:162-171`). `m` still unbound. Sixteen `UnifiedApp(` constructions match the compatibility claim.

**Cycle-2 follow-through:** all five items are in the owning task's `<action>`, acceptance criteria, and `<automated>` gates -- not only in the ledger.

**New this cycle:** none. Not a replan; the plans are ready to execute.

## Overall risk: LOW

Cycle-1's three HIGHs remain closed in source, not just ledger rows: vulture 2.16 at `min_confidence = 80` does not flag unused classes (`pyproject.toml:59-61`); first-run status targets the visible `AppScreen` (`ui_common.py:319`, `setup.py:640-645`) with a registry fallback that cannot hide on catalog (`wizard_app.py:1473-1509`, `:1591-1593`); rule 5 is checked at phase end with four cross-module greps (`13-07-PLAN.md:247-255`). Cycle-2's drain-before-wait hole is a specified `finally` order plus a hang-failing test. No new HIGH or actionable MEDIUM/LOW.

---

## Consensus Summary

Single-reviewer cycle (as in cycles 1 and 2). The `opencode-fallback` lane ran a full source-grounded audit of all 7 plans and explicitly re-verified each of cycle 2's five previously-incorporated fixes against the live source tree, not just against plan-ledger checkboxes. Every one of the five was confirmed RESOLVED with `file:line` evidence tying the fix to both the plan text and the live code it depends on. No new HIGH or actionable MEDIUM/LOW concerns were raised anywhere across the 7 plans. Given this is a single reviewer, treat the LOW overall-risk verdict as directional rather than as multi-source consensus -- but the review's methodology (independent re-verification against source, not re-statement of the ledger) gives it more weight than a first-pass opinion would carry.

### Agreed Strengths
Not applicable -- single reviewer this cycle.

### Agreed Concerns
Not applicable -- single reviewer this cycle; the sole reviewer raised none.

### Divergent Views
Not applicable -- single reviewer this cycle.
