---
phase: 13
reviewers: [opencode-fallback]
reviewed_at: 2026-09-14T03:36:02Z
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
  opencode-plan-review: "configured default reviewer instance (opencode, model router-env/my-plan-review) — retried twice this cycle after cycle 1's router-unavailability was confirmed fixed (direct `opencode run --model router-env/my-plan-review` smoke test returned 'OK'). Attempt 1 hit the lane's outer wall-clock timeout (660s default; raised to 1500s via review.timeouts.opencode and retried) with 'spawn error: ETIMEDOUT'. Attempt 2 at the raised timeout ran for ~25 min and exited status 1 with 'OpenCode review returned no assistant text (#1936: agent ended its turn with no final message)' after 870 output tokens of tool-calls only — the agent never emitted a final assistant message for this prompt size/effort combination on this host."
  gemini: "gemini CLI binary is still broken on this host — MODULE_NOT_FOUND for @google/gemini-cli/bundle/gemini.js under the pnpm global install; reproduced directly with `gemini --version` this cycle, unchanged from cycle 1"
  codex: "codex CLI auth token still expired/reused (401 refresh_token_reused via wss://chatgpt.com/backend-api/codex/responses); reproduced directly with `codex exec --json`, requires `codex login` on this host, out of scope for this review run"
  cursor: "cursor-agent is now logged in (castocolina.dev@gmail.com, previously blocked at the login step) but still hits its account usage limit (ActionRequiredError: 'You've hit your usage limit'); reproduced directly with `cursor-agent -p`"
  antigravity: "not re-probed this cycle (binary responds to --version but was not otherwise exercised); cycle 1 reported account ineligibility (Google account verification required) and no fix was reported"
---

# Cross-AI Plan Review — Phase 13

<!-- gsd:plan-revision-conflicts:begin -->
## Plan-Revision Conflicts
(none recorded)
<!-- gsd:plan-revision-conflicts:end -->

> **Reviewer-availability note (cycle 2):** the project's configured `review.default_reviewers`
> (`opencode-plan-review`, pinned to `router-env/my-plan-review`) was retried synchronously this
> cycle after confirming the cycle-1 router-unavailability was resolved (the model now answers a
> direct smoke-test prompt). It still could not produce a usable review: a first attempt hit the
> lane's outer timeout on this large, source-grounded, high-effort prompt; a second attempt, run
> after raising `review.timeouts.opencode` from its 660s default to 1500s, ran for roughly 25
> minutes and then exited with the CLI's own `#1936` failure mode (the agent ended its turn after
> tool calls with no final assistant message) rather than a router or auth error. `gemini` remains
> broken by a broken pnpm install (`MODULE_NOT_FOUND`, unchanged from cycle 1). `codex` remains
> blocked by an expired/reused OAuth refresh token. `cursor` is now logged in (previously blocked
> earlier in the login flow) but still hits its account's monthly Agent usage limit. `agy`/
> Antigravity was not re-probed for account eligibility this cycle. As in cycle 1, one fallback
> pass was run through the already-available `opencode` adapter using the alternate configured
> router model (`router-env/my-coding`, confirmed reachable and confirmed to complete this
> cycle's prompt end-to-end) instead of the still-unusable `my-plan-review` lane. This is again a
> single-reviewer, source-grounded review — treat it as directional, not as a substitute for
> restoring the intended multi-CLI review roster once the router/auth/billing/CLI issues above are
> fixed.

## OpenCode Review (opencode-fallback)

I'll load the plan-review skills, then verify each disposition against the referenced source instead of taking the ledger at its word.
The first glob missed the phase dir — I'll locate the plans and load the remaining review references.
The phase directory is there; glob missed it. I'll list the plans and ground the review against the source they cite.
This is a cycle-2 disposition audit, not a fresh first-pass review. I'll read the ledgers and ground each claimed fix in the source.
I've got the first three plans and cycle 1's report. Next I'll read 13-04–13-07 and check each ledger claim against the live source.
I'll ground each ledger claim against the live source—signatures, vulture config, and the line numbers the plans cite.
I need the live signatures and the cited line ranges before I can judge whether each ledger row actually closes the concern.
Several ledger claims need a second look in the live files—especially `run_live`, `AppScreen` status, `_run_fix`, and the vulture scoring story.
A few ledger claims look shaky—I'll verify vulture scoring, the `self.screen` callback timing, and the `finally: wait()` deadlock.
I'll verify vulture's confidence scoring and a few remaining cited line ranges before writing the report.
I'll confirm vulture's scoring and a couple of remaining cited ranges before writing the report.
There's a leftover `2 passed` gate in 13-07. I'll confirm vulture scoring and a few remaining cited ranges.
Vulture's constructor doesn't take `min_confidence` that way — I'll inspect the 2.16 API so the Wave-1 dead-code claim is actually measured.
Cycle 2 audit of all 7 ledgers against live source (`session.py`, `run.py`, `ui_common.py`, `wizard_app.py`, `setup.py`, `pyproject.toml`, vulture 2.16). Cycle-1 HIGHs are closed; one new MEDIUM from the `finally: wait()` revision.

## 13-01

**Summary.** Wave 0 still de-risks the unexercised worker-to-modal combo before any production helper exists. Both cycle-1 LOWs are in Task 3's action, acceptance, and grep gates, and 13-07 is named as the architecture.md follow-through.

**Strengths**
- Spike stays throwaway; characterisation tests import nothing from `installer.execute_screen`.
- Rule-2 ruling is now a required sentence (`MECHANISM=A` exception vs `MECHANISM=B` is the rule-2 shape), matching `.claude/architecture.md:16-17`.
- Three test names are pinned so 13-04/13-05 cannot silently drop them.

**Concerns**
- None new. Both ledger rows check out.

**Suggestions**
- None.

**Risk Assessment:** LOW.

**Dispositions Ledger Audit**
| Concern | Disposition | Verdict |
|---|---|---|
| Rule 2 vs mechanism A | incorporated | **RESOLVED** — Task 3 requires a `rule 2` sentence and a 13-07 write-down (`.planning/phases/13-live-in-tui-install-execution-persistent-wizard-settings-ins/13-01-PLAN.md:240-248`, `:289-291`). |
| Characterisation tests must survive file growth | incorporated | **RESOLVED** — same section plus 13-05 Task 2 `grep -q` of the three `def test_a_*` names (`13-05-PLAN.md:174-181`, `:288-294`). |

## 13-02

**Summary.** Seam choice is still right: Popen `StreamingRunner` on `MethodAwareRunner` (`installer/run.py:15-21`, `installer/engine.py:126-127`) and a keyword-only `should_continue` appended after `catalog` (`installer/session.py:69-76`). Cycle-1 HIGH/MEDIUMs are substantively closed. The new `finally: wait()` text creates a pipe-deadlock on the path it was meant to fix.

**Strengths**
- Vulture half of the HIGH is measured, not argued: vulture 2.16 `DEFAULT_CONFIDENCE` is 60, imports are 90 (`.../vulture/core.py:15`, `:420`); `[tool.vulture] min_confidence = 80` (`pyproject.toml:59-61`). A probe unused class/const/method/attr is silent at 80 and reported at 60. Task 1 now asserts `uv run vulture` with `pyproject.toml` unmodified.
- Incremental child is now `python -u` + `flush=True`, and the docstring records that vendor tools on a pipe may still burst.
- `should_continue` tail is `catalog=..., *, should_continue=...` with an `inspect.signature` gate (`13-02-PLAN.md:272-282`, `:307`). Live signature has `catalog` last and positional (`session.py:69-76`).
- Rule 5 is named and enforced at 13-07, not waived.

**Concerns**
- **MEDIUM — `finally: proc.wait()` can deadlock if `emit` raises.** Cycle-1 asked to reap the child. The revision waits without draining or closing stdout (`13-02-PLAN.md:215-221`, `:243`). If `emit` raises mid-stream, unread pipe data can fill the OS buffer, the child blocks on write, `wait()` never returns, and 13-04's worker `try/finally` never posts `InstallRunFinished` — the stuck-"Installing..." mode T-13-07 exists to prevent (`13-04-PLAN.md:218-220`). `wait()`-only also cannot terminate (DD-1 forbids that); the missing step is drain-then-wait.

**Suggestions**
- In `__call__`'s `finally`, drain `proc.stdout` (or close-and-then-wait after a bounded drain) before `wait()`. Keep the `terminate`/`kill` grep at 0.

**Risk Assessment:** MEDIUM (new hang path on the emit-raises case).

**Dispositions Ledger Audit**
| Concern | Disposition | Verdict |
|---|---|---|
| Wave-1 vulture / rule 5 HIGH | incorporated (vulture measured; rule 5 → 13-07) | **RESOLVED** — `pyproject.toml:59-61`, vulture 2.16 scores, 13-07 Task 2 greps (`13-07-PLAN.md:236-245`, `:289`). |
| Live lines vs pipe buffering | incorporated | **RESOLVED** — `-u` + `flush=True` plus honest burst docstring (`13-02-PLAN.md:174-175`, `:223-229`). |
| `should_continue` placement | incorporated | **RESOLVED** — append after `catalog`; signature gate (`session.py:69-76`, `13-02-PLAN.md:272-282`). |
| Popen without `finally: wait()` | incorporated | **PARTIALLY-RESOLVED** — `finally: wait()` is specified; drain is not, so the emit-raises path can hang instead of orphan. |
| Drop `make validate` from Wave 1 | rejected | **RESOLVED** — rejection is correct given the vulture measurement; keeping the gate is the `CLAUDE.md` rule. |

## 13-03

**Summary.** Persistence still mirrors `version_cache.py` (`installer/version_cache.py:137-175`, `:196-197`) with a closed set matching `installer/cli.py:54-59`. The HIGH is the same measured vulture story as 13-02; JSON `null` round-trip is now a required test.

**Strengths**
- `Settings.link_mode=None` vs `"centralized"` stays the first-run discriminator.
- Two-way `LINK_MODES` vs CLI `choices=` (parse_args + `ast`) is still the drift check.
- `set_link_mode` does not catch `OSError`; `run_live` (`installer/ui_common.py:41-50`) remains the one apply workflow.
- Every export is mapped to a 13-06 adopter; 13-07 greps `SettingsStore` / `link_mode_needs_choice` in `setup.py`.

**Concerns**
- **LOW — load-contract wording fights itself.** Task 1 action says require `link_mode` to be a `str` (`13-03-PLAN.md:188-190`) and also that JSON `null` must take the missing-key path (`:192-198`). Both return `Settings()`. An executor who implements only the `str` check still passes the new test; the "missing-key vs type-rejection" distinction is documentation-only.

**Suggestions**
- Write the load steps as: missing/null key → `Settings()`; present but not a `LINK_MODES` member → `Settings()`. Drop "must be a str" as a prior gate.

**Risk Assessment:** LOW.

**Dispositions Ledger Audit**
| Concern | Disposition | Verdict |
|---|---|---|
| Wave-1 vulture / rule 5 HIGH | incorporated | **RESOLVED** — same measurement as 13-02; 13-07 adoption greps (`13-03-PLAN.md:89-119`, `13-07-PLAN.md:289`). |
| `save_settings(Settings())` / JSON `null` | incorporated | **RESOLVED** — own behavior bullet and test (`13-03-PLAN.md:162-163`). Observable contract holds even if null is classed as type-rejection. |
| Land settings.py in 13-06 / skip vulture | rejected | **RESOLVED** — context-budget reason is explicit; orphan property moves to 13-07. |

## 13-04

**Summary.** Tracer architecture is unchanged and still right: `ModalScreen` not `AppScreen` (`installer/ui_common.py:308-339`, `installer/wizard_app.py:1630-1636`), interactive path never calls `run_wizard` (`installer/app.py:94-97`). All five cycle-1 items are in the task text with tests. Construction-site count now matches the tree.

**Strengths**
- `run_live` `(None, message)` path now posts `InstallRunFinished` with `summarize([])`, never `None` (`installer/ui_common.py:41-50`, `installer/engine.py:136`).
- `install_summary` accumulates; `setup.py:791-793` would otherwise report only the last batch.
- `catalog_tui.py` is in `files_modified`; `Decided` docstring currently claims unconditional `App.exit` (`installer/catalog_tui.py:193-195`) and the plan rewrites both branches.
- Live count: 16 `UnifiedApp(` sites (1 in `setup.py`, 15 in tests) plus the class statement; comment at `wizard_app.py:1476` still says nine; plan now requires that comment gone.

**Concerns**
- None that reopen cycle 1. Ctrl+c disclosure + 13-07 residual is the right branch: `action_hard_abort` is unguarded and priority (`wizard_app.py:1417-1420`, `:1679-1681`).

**Suggestions**
- None beyond 13-02's drain-then-wait, which this worker will sit behind.

**Risk Assessment:** LOW.

**Dispositions Ledger Audit**
| Concern | Disposition | Verdict |
|---|---|---|
| `run_live` empty-outcomes | incorporated | **RESOLVED** — explicit failure paragraph + Pilot (`13-04-PLAN.md:235-247`, `:332`). |
| ctrl+c orphans child | incorporated (disclose, don't guard) | **RESOLVED** — status line + T-13-24 + 13-07 residual (`13-04-PLAN.md:267-279`; `wizard_app.py:1679-1681`). |
| last `install_summary` wins | incorporated | **RESOLVED** — merge, not overwrite (`13-04-PLAN.md:298-307`, `:331`). |
| Stale `Decided` docstring | incorporated | **RESOLVED** — `catalog_tui.py` in `files_modified`; `grep -q ExecuteScreen` (`13-04-PLAN.md:8-11`, `:308-314`). |
| Seventeen vs nine | incorporated | **RESOLVED** — 16 constructions counted; `grep -c "Nine UnifiedApp"` gate (`13-04-PLAN.md:287-296`). |
| Bind hard abort to status line | partially adopted | **RESOLVED** — disclosure taken; rebinding rejected with a recorded reason. |

## 13-05

**Summary.** Capability gap after the tracer is still the right scope. Cycle-1 items (rule-2 production use, `c` under the mismatch modal, three stop keys, characterisation-test preservation) are in Task 1–2 with Pilot gates.

**Strengths**
- `ask_from_worker` is "whatever 13-VALIDATION.md recorded," not a second spike.
- Labels stay verbatim from `_ask_mismatch` (`setup.py:310-317`); `on_mismatch=None if unattended` matches `run_wizard` (`installer/app.py:157`).
- Dismissal → `skip` is the only `MismatchChoice` that does not install an unverified artifact (`installer/session.py:16-17`, `:109-121`).
- Not-attempted stays a set difference; `summarize`'s closed map is untouched (`session.py:135-143`).

**Concerns**
- None new. Nested-modal `c` is chosen and tested (`13-05-PLAN.md:264-272`, `:285`).

**Suggestions**
- None.

**Risk Assessment:** LOW.

**Dispositions Ledger Audit**
| Concern | Disposition | Verdict |
|---|---|---|
| Mechanism A vs rule 2 in production | incorporated | **RESOLVED** — two-branch ruling in design decisions + Task 1 (`13-05-PLAN.md:93-108`, `:165-172`). |
| `c` while mismatch modal is up | incorporated | **RESOLVED** — pick-and-test: event stays unset; status names the waiting prompt (`13-05-PLAN.md:231`, `:264-272`). |
| Escape vs `c` vs ctrl+c | incorporated | **RESOLVED** — `execute-keys` names three distinct effects (`13-05-PLAN.md:232`, `:256-262`). |
| Keep 13-01 characterisation tests | incorporated | **RESOLVED** — names kept; throwaway App stays; Task 2 `grep -q` of all three defs (`13-05-PLAN.md:174-181`, `:288-294`). |

## 13-06

**Summary.** Persistence half still treats live re-read as the real bug (`setup.py:392` snapshots `rc_paths` today). The cycle-1 HIGH is closed: first-run status goes to the visible `AppScreen.status` (`installer/ui_common.py:315-319`), with a dedicated `initial_view="doctor"` Pilot matching `_run_fix` (`setup.py:640-645`, `wizard_app.py:1541-1542`).

**Strengths**
- `ban_policy` / `tweak_policy` value-or-callable keeps existing list/tuple call sites (`installer/policy.py:218-225`).
- `_link_mode_picked` copies `_time_picked` except the `None` branch sets a warn (`wizard_app.py:1256-1258`).
- `m` is unbound in `installer/` today; Policies already has `l`/`t` (`wizard_app.py:932-935`); Catalog has `r`/`d`/`u` (`catalog_tui.py:201-205`). Footer comes from `View.actions` (`ui_common.py:170`, `:208-210`).
- `prompt_link_mode` allowlist matches `apply_daemon_default` (`setup.py:519-528`).
- Picker is last in `on_mount` and asserted with daemon default also wired.

**Concerns**
- **LOW — callback fallback reintroduces the HIGH if timing is wrong.** `_first_link_mode_picked` uses `self.screen` when it is an `AppScreen`, else `self.catalog.status` (`13-06-PLAN.md:366-376`). Textual invokes the callback after dismiss, so `self.screen` should be Doctor on `make fix`. If a future Textual change fires the callback while `LinkModeScreen` is still current, the fallback writes the catalog again. The new Doctor Pilot is the tripwire; keep it.

**Suggestions**
- Prefer `self.screen` if `AppScreen`, else `self._views.get(self.current_view) or self.catalog`, not a hard catalog fallback.

**Risk Assessment:** LOW.

**Dispositions Ledger Audit**
| Concern | Disposition | Verdict |
|---|---|---|
| First-run status on hidden catalog (HIGH) | incorporated | **RESOLVED** — visible `AppScreen.status`; Doctor Pilot (`setup.py:640-645`, `ui_common.py:319`, `13-06-PLAN.md:366-376`, `:398`). |
| Picker vs daemon worker | incorporated | **RESOLVED** — last in `on_mount`; `app.screen is LinkModeScreen` with daemon wired (`wizard_app.py:1543-1544`, `13-06-PLAN.md:358-364`, `:396`). |
| "Once per machine" vs dismiss | incorporated | **RESOLVED** — "once per ANSWER"; file stays null (`13-06-PLAN.md:29`, `:348`). |
| Confirm `m` is free | incorporated | **RESOLVED** — live grep empty; re-grep before bind; one-file gate (`13-06-PLAN.md:276-281`). |
| Keep `_ask_mismatch` / `_ask_select` | no action (endorsement) | **RESOLVED** — `questionary.select` count stays 1 (`setup.py:299`). |

## 13-07

**Summary.** Close-out is in the right place (architecture.md after Phase 12.4 at `.claude/architecture.md:582`, PRD deferred-fork at `docs/prds/unified-ui-redesign-v1.0-prd.md:134-138`, `tests/test_docs.py:5-26`). Cycle-1 items are in Task 1–2, including the rule-5 adoption greps that close 13-02/13-03.

**Strengths**
- Engine-untouched `fails_when` now says a pre-Phase-13 diff is a wrong baseline, never a reason to edit `engine.py` (`13-07-PLAN.md:294`).
- Worker-to-modal name joins the Phase 13 phrase tuple when A shipped.
- Residual scope names `clean_rc_duplicates`, weak cancel, `link_mode`-only, ctrl+c orphan (`action_hard_abort` grep), and dismissed-picker reprompt.
- `pyproject.toml` must be byte-identical across the phase (`fail_under = 90`, `min_confidence = 80`).

**Concerns**
- **LOW — leftover `2 passed` in plan-level `<verification>`.** Task 1 correctly dropped the function-count assertion (`13-07-PLAN.md:190-197`, `:203`). `<verification>` still says `uv run pytest tests/test_docs.py -q` reports 2 passed (`13-07-PLAN.md:323`). An executor treating that block as a gate reintroduces the fragility Task 1 removed.
- **LOW — `sanitize_log_line` in the rule-5 grep is tautological.** It is defined in `installer/execute_screen.py` (13-04), so `grep -q sanitize_log_line installer/execute_screen.py` cannot prove a caller. `StreamingRunner` / `should_continue` / `SettingsStore` greps are cross-module and real.

**Suggestions**
- Delete the `2 passed` line from `<verification>`.
- Drop `sanitize_log_line` from the adoption list, or grep a use that is not the `def`.

**Risk Assessment:** LOW.

**Dispositions Ledger Audit**
| Concern | Disposition | Verdict |
|---|---|---|
| Engine-untouched `fails_when` | incorporated | **RESOLVED** — guidance sits in `fails_when`, where a red gate is tempting to "fix" (`13-07-PLAN.md:294`). Automated command still cannot auto-narrow `BASE`; that is documented, not silent. |
| Record `push_screen_wait` if A | incorporated | **RESOLVED** — Task 1 two-branch + phrase tuple (`13-07-PLAN.md:180-188`). |
| `test_docs.py` exactly-two count | incorporated | **PARTIALLY-RESOLVED** — Task 1/acceptance/automated fixed; plan-level `<verification>` still says `2 passed` (`13-07-PLAN.md:323`). |
| 13-02/13-03 rule-5 HIGH | incorporated here | **RESOLVED** — production greps + T-13-25 (`13-07-PLAN.md:236-245`, `:289`, `:316`). |
| ctrl+c in residual scope | incorporated | **RESOLVED** — named entry + `grep -q action_hard_abort` (`13-07-PLAN.md:270-276`, `:294`). |

---

## Cross-plan

DD-1 / DD-2 / DD-3 stay consistent across all seven files. Interactive vs headless split (13-04 option b) still isolates `--all`/`--yes` (`app.py:94-97`). No new view row (`ui_common.py:162-171`).

**New in this revision (not cycle 1):**
1. **MEDIUM** — 13-02 `finally: wait()` without drain can hang the 13-04 worker if `emit` raises.
2. **LOW** — 13-07 `<verification>` still requires `2 passed`.
3. **LOW** — 13-03 load steps say both "must be a str" and "null is missing-key".

## Overall risk: LOW

Cycle-1's three HIGHs are closed in source, not just in ledger rows: vulture 2.16 at `min_confidence = 80` does not flag unused classes (`pyproject.toml:59-61`); first-run status targets the visible `AppScreen` (`ui_common.py:319`, `setup.py:640-645`); rule 5 is checked at phase end (`13-07-PLAN.md:289`). Remaining work is the drain-before-wait hole and two leftover inconsistencies. Not a replan of the architecture.

---

## Consensus Summary

Single-reviewer cycle (see the reviewer-availability note above) — no cross-reviewer consensus
computation applies. Treat the findings below as one grounded, source-verified pass, not a
multi-model consensus.

### Agreed Strengths
Not applicable — only one reviewer produced a result this cycle.

### Agreed Concerns
Not applicable — only one reviewer produced a result this cycle. See "Cross-plan" above for the
full concern list from the single reviewer that ran.

### Divergent Views
Not applicable — only one reviewer produced a result this cycle.
