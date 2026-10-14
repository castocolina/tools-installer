# Phase 25: Lean - Context

**Gathered:** 2026-10-14 (assumptions mode, `--analyze --all --batch`, jev ladder, best-over-easy)
**Status:** Ready for planning

<domain>
## Phase Boundary

Code that still has no production caller after Phases 17–24.1 is deleted, with behaviour unchanged. App composition moves under pyright strict and the coverage gate (`installer/compose.py`). `wizard_app.py` is split into per-screen modules of at most 800 lines. The run log is bounded.

The WHAT is locked in `25-SPEC.md` (R1–R5). This file locks the HOW.

**This phase runs last.** Every deletion list is computed **at execution time** against the post-24.1 tree, never hardcoded from today's pre-17 code.
- Many targets are already deleted by earlier phases: 19 D-04, 20 D-08/D-12 (`audit.py`, `render_audit`, `Summary`), 21 D-16, 22 D-08.
- Others become live: 23's `agent_settings.py` and its reuse of `agent_env.AgentAdapter` (23 D-06, corrected 2026-10-14).

Out of scope:
- Anything a later phase wired.
- The race epochs (AR-04).
- Behaviour or UI text changes beyond the dropped-lines notice.
- Replacing questionary; the confirms stay.
- F14's modal class consolidation, because it would need assertion changes (see D-07).
</domain>

<decisions>
## Implementation Decisions

**Decision rule:** best over easy, with the jev ladder.

### Reachability and deletion (R1)
- **D-01 (best, not easy):** A **permanent** `tests/test_reachability.py` builds the import graph by AST from the entry points.
  - Entry points: `setup.py`, `installer/__main__` if present, and the modules the Makefile/`install.sh` invoke.
  - It follows **function-level** imports too (`policy.py:192, 251` import lazily) and string-keyed dispatch tables (`POSTINSTALL_HOOKS`, `POST_INSTALL_HOOKS`, `BUNDLES`, the `METHOD_KINDS` dispatch).
  - It fails if any `installer/` module is unreachable.
  - vulture stays a secondary symbol-level check (`pyproject.toml:60`). vulture alone misses self-referencing dead subgraphs such as the agent-policy trio.
  - A one-shot script was rejected: F11's root cause was a helper that was never wired and that nothing checked.
  - jev: Laya 0.52 (needs fallback); TypeSafe permanent_ast_test 1.00.
- **D-02:** The deletion list is what D-01 reports at execution time.
  - Each kept SPEC target is listed in the summary **with its caller**, which is the LEAN-01 acceptance.
  - Expected but not assumed: `agent_policy.py` and `agent_guidance.py` are dead, because 23 wires neither. `agent_env.py` is live, because 23 D-06 reuses `AgentAdapter`. Also expected dead: `policy.agent_environment_policy`/`compose_agent_environment_policy` (`policy.py:181-264`).
- **D-03:** The questionary chooser (`setup.py:300-349` `_ask_checkbox`, `prompt.py:15-33` `select_categories`/`select_tools`, `selection.py` choices, the `app.py:101-124` `_choose_tools` fallback) is reachable by import but infeasible by control flow (G#9).
  - D-01 cannot prove that, so the plan **re-traces** `main` → `run_wizard` against the landed 20 D-12 code before deleting, and cites the line numbers.
  - The confirms (`_ask_confirm`, `_ask_select`) stay.
- **D-04:** Message classes (F15) are not pre-decided.
  - At execution, each remaining `Message` (for example `GlobalsReinstalled`, `GlobalsAudited`, `DiskPressureProbed`, `CompetingProbed`, `PolicyToggled`, `DaemonDefaultApplied`) is deleted only if its post site is unreachable, **or** it is fully replaced by 21's `request_refresh`/`state_refreshed`.
  - Never where an epoch or generation check depends on it (AR-04).

### Composition under the gates (R2)
- **D-05 (best, not easy):** **Narrow move** to `installer/compose.py`, keeping the names. Tests change only their import path, and they keep `# pyright: ignore[reportPrivateUsage]`.
  - What moves:
    - `_build_app` (`setup.py:755-1163`), which per 17 D-12 builds `ExecuteInputs`.
    - `_execute_inputs` (`:1166-1211`).
    - Their private helpers with no other caller: `_timer_state_cache :362`, `_competitor_probe :417`, `_disk_pressure_probe :516`, `_build_daemon_policy :546`, `_cache_redirect_policies :653`, `_which_with_brew :683`, `_sync_terminals :710`, `_sync_terminals_and_report :741`.
  - What stays in `setup.py` (allowed by architecture rule 4: parse, prompt, construct): `main`, the `_run_*` dispatch, and every questionary/prompt_toolkit piece.
  - `compose.py` imports no questionary.
  - jev: Laya move_everything 0.62 (needs fallback); TypeSafe narrow_move 0.99.
- **D-06:** The path and environment constants (`_DEFAULT_BIN_DIR`, `_MYSHELLRC`, `_ZSHRC`, `_RC_PATHS`, `_SHELL`, `_REGISTRY`, `_SHELLRC`; `setup.py:99-110`) get one definition in `compose.py`, and `setup.py` imports them back. `installer/` never imports `setup.py`.
  - `compose.py` falls under pyright strict, coverage and vulture just by living in `installer/` (`pyproject.toml:41-43, 52, 60`). No gate is suppressed, and strict-mode fixes are local.

### Split `wizard_app.py` (R3)
- **D-07:** Five modules, using the boundaries the audit named (`2026-10-11-ponytail-audit.md:313`):
  - `doctor_screen.py`: `DoctorScreen` plus its messages and `_BodyStatic`, about 650 lines.
  - `uninstall_screen.py`: `UninstallScreen`, `UninstallInputs`, `_UninstallEntry`, about 816–840 lines. That is over the cap, so a small `uninstall_inputs.py` sibling takes the inputs and entry types.
  - `policies_screen.py`: `PoliciesScreen`, `PolicyInputs` and its messages, about 600 lines.
  - `modals.py`: `ConfirmGuardFile`, `ConfirmUninstall`, `NavScreen`, `TimePickerScreen`, `LinkModeScreen`, moved **verbatim**, about 185 lines.
  - `wizard_app.py`: `UnifiedApp` plus `DaemonDefaultApplied`, about 611 lines.
  - Line counts are re-measured on the post-21 file, because 21 deletes a lot from these screens.
  - Call sites are updated (`setup.py:97` becomes separate imports). There is no compatibility shim.
  - Review-ID comments (`CR-0`, `WR-0`, `IN-0`, phase narratives) are dropped. "Why" comments stay.
  - F14's `ChoiceModal`/`ConfirmModal` merge is **excluded**: it would change test assertions (a SPEC constraint), so it is deferred.

### Bounded run log (R4)
- **D-08 (full model; both jev models had low confidence):** `RichLog(max_lines=5000)` plus **one centralized write helper** with its own counters.
  - Every `#execute-log` write goes through it; today they are scattered at `execute_screen.py:850-952`.
  - The dropped-count notice is a one-line label **directly above the log, inside the log panel**, hidden until the first drop. It reads "N earlier lines dropped".
  - The newest log line always stays last. 6,000 writes leave exactly 5,000 log lines plus the notice; 5,000 writes show no notice.
  - Why: Textual trims silently, with no eviction hook (`_rich_log.py:264-267`), and only appends. Keeping a notice *inside* the log would mean rewriting the whole buffer on every write, or making the notice the last line, which breaks "newest line last".
  - jev: Laya header_label 0.64 (needs fallback); TypeSafe in_log_rewrite 0.61 (needs fallback). In-log rewrite can't keep the newest line last without an O(n) rewrite on every write.
  - **Deferred confirm:** the SPEC says "the log shows one line". I read the label above the log, inside the panel, as satisfying that.

### Gate (R5)
- **D-09:** The full suite plus `make validate` run, with CI green on ubuntu and macOS.
  - The summary reports the net production lines removed, from `git diff --stat` over `installer/` and `setup.py` against the commit before the phase, with both SHAs.

### Claude's Discretion
- Wave order. Suggested:
  1. The reachability test and the deletions.
  2. `compose.py`.
  3. The `wizard_app` split.
  4. The log bound.
  5. The size report.
- The sibling module's name.

### Folded Todos
None.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `.planning/phases/25-lean/25-SPEC.md`: locked R1–R5
- `.planning/research/2026-10-13-target-architecture.md`: §8 P9 (:368), §9.1 cut list, AR-04 (:36)
- `.planning/research/2026-10-11-ponytail-audit.md`: F11–F17 (:278-362)
- `.planning/research/audit-2026-10-13/G-ui-health-states-and-reuse.md`: #9 (:406-409)
- Prior contexts: 17 D-12; 19 D-04; 20 D-08, D-12; 21 D-05, D-06, D-16; 22 D-08; 23 D-06 (corrected)
- `Makefile` (validate), `pyproject.toml` (pyright/coverage/vulture scope)
- `.claude/architecture.md` (rules 4 and 5), `AGENTS.md`
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Precedents for AST-level guard tests (`.claude/architecture.md:853-863`) and grep tests (21 D-16)
- Textual `RichLog.max_lines` (trims silently)

### Established Patterns
- Compute cleanup targets from the live tree, never from a stale list.
- Keep names when moving code, so tests change only their import path.
- `installer/` never imports `setup.py`.

### Integration Points
- `setup.py` → `installer.compose`; the split modules ← `setup.py:97` and tests
- `execute_screen` log writes → one helper
</code_context>

<specifics>
## Specific Ideas

- The "≈ −2,000 lines" estimate predates 19–24.1. The count is measured, not targeted.
</specifics>

<deferred>
## Deferred Ideas

- F14 modal consolidation (`ChoiceModal`/`ConfirmModal`): a separate scope, because it needs assertion changes.

### Reviewed Todos (not folded)
- pnpm shims (0.6, Phase 21), GSD per-repo (0.6), pi repair (0.6), Playwright Chrome (0.2).
</deferred>
