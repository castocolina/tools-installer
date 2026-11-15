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
  - **User-confirmed 2026-10-14:** the label above the log satisfies "the log shows one line".

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

### Amendment 2026-11-15 (pre-plan re-measure at HEAD 572d30fd, orchestrator)

Phases 17 to 24.5 ran after this file was written, so the facts under several locked decisions moved. Each entry below keeps the decision's intent and replaces only its facts. Source: the dated "Pre-phase check 2026-11-15" note under Phase 25 in `.planning/ROADMAP.md`, re-measured at HEAD 572d30fd. Decision rule unchanged: best over easy. Line numbers are the planner's starting point, not a contract; plans re-check them.

- **D-01 (intent kept: a permanent AST reachability test).** Still needed. `vulture` at confidence 80 is silent, and at 60 it prints about 251 lines. That shows a symbol-level scan cannot replace an import-graph check. Re-derive the string-keyed dispatch tables at plan time. Names such as `POSTINSTALL_HOOKS` and `BUNDLES` predate 19 to 24.5, and the probe table is `install_ownership.py`'s keyed dict (`"host-setup": _host_setup`, :378). Use the vulture-60 output as a triage list for D-02, not as proof.
- **D-02 (intent kept: delete what nothing reaches, list kept targets with their caller).** These targets are already gone and need nothing more than a line in the summary: `installer/audit.py`, `agent_policy.py`, `agent_guidance.py`, `guards.py`, `policy.agent_environment_policy`/`compose_agent_environment_policy`, and the `Tool.source`/`owner`/`uninstall` fields. `agent_env.py` stays live: `agent_settings.py` imports it. Phase 25 also takes over two dead subsystems from earlier phases (D-10, D-11 below). The vulture-60 candidates are triaged one by one, each with its caller or its deletion: `AgentAdapter.instruction_path`/`permission_mode`, `diskusage.probe_disk_pressure`, `receipts.scan_retired`, `render.render_troubleshooting`, `deps.requires_integrity_errors`, `schedules.sweep_adapters`. Functions whose only caller is `setup.py` count as live, because vulture scans `installer/` only.
- **D-03 (intent kept: no live chooser deleted by mistake).** The questionary checkbox chooser (`_ask_checkbox`, `select_categories`, `select_tools`) is already gone. `setup.py` keeps `ask_confirm` (:286), `_ask_select` (:295) and `_ask_mismatch` (:309). `app._choose_tools` is the live `--all`/`--categories` filter and stays. No re-trace or deletion is left; the summary records the check.
- **D-04 (intent kept: judge each Message by its post site, epochs stay).** `DaemonDefaultApplied`, `CompetingProbed` and `PolicyToggled` no longer exist. The remaining set in `wizard_app.py` is `GlobalsReinstalled` (:252), `GlobalsAudited` (:265), `DiskPressureProbed` (:291), `ScheduleChanged` (:312), `ScheduleManagerProbed` (:325), `RemovalFinished` (:1162), `CursorModelsRead` (:3446), `ScheduleDefaultsApplied` (:3572), `RefreshPublished` (:3587) and `RefreshFinished` (:3597). A Message that carries a generation or epoch, or that a supersede check reads, stays (AR-04).
- **D-05 (intent kept: narrow move, names kept, compose under the gates, no questionary in compose).** `_build_app` is at `setup.py:743` and `_execute_inputs` at `:1062`. `setup.py` is 1,489 lines. `_build_daemon_policy` and `_which_with_brew` no longer exist. The move set is defined by a rule rather than a stale list: `_build_app`, `_execute_inputs`, and the transitive closure of the `setup.py` private helpers and classes they call that touch neither questionary nor prompt_toolkit. At HEAD that is `_timer_state_cache` (:320), `_CompetitorProbe`/`_competitor_probe` (:348/:373), `_DiskProbe`/`_disk_pressure_probe` (:395/:472), `_cache_redirect_policies` (:502), `_sync_terminals` (:532), `_sync_terminals_and_report` (:562), `_build_services` (:580), `_split_sourced_from`, `_desktop_shell_policies`, `_schedule_context`, `_invalidating`, `_schedule_removed_lines` and `_reconcile_headless`; the plan confirms the closure.
  - A moved helper that a `_run_*` route also calls moves too, and `setup.py` imports it back from `installer.compose`. Best over easy: leaving shared composition outside the gates would defeat LEAN-02.
  - A questionary-backed callback, such as `_ask_mismatch` or `ask_confirm`, reaches compose only as a parameter injected by `setup.py`.
  - `setup.py` keeps `main`, the `_run_*` dispatch, tty/questionary plumbing and argument parsing (architecture rule 4).
- **D-06 (intent kept: one definition of the path and env constants, `installer/` never imports `setup.py`).** The constants block is now `setup.py:112-136`. It adds `_DAEMON_PLIST_PATH`, `_LINUX_DAEMON_UNIT_DIR`, `_ENVIRONMENT_D_DIR` and `_WARN_CONSOLE` to the D-06 list. Every constant the moved code reads gets its one definition in `compose.py`, and `setup.py` imports back what it still uses. `_STYLE` (questionary) stays in `setup.py`.
- **D-07 (intent kept: per-screen modules, every file ≤ 800 lines, verbatim move first and comment cleanup second, no shim, F14 merge excluded).** `wizard_app.py` is 4,438 lines with 28 classes. Five modules cannot meet the cap. The measured blocks at HEAD, imports and header excluded:
  - the shared inputs and messages: :139-355, about 215 lines;
  - `DoctorScreen` with `_BodyStatic`/`_smoke_findings`: :333-1031, about 700;
  - the uninstall block: :1032-2049, about 1,018, of which the `UninstallScreen` class alone is :1180-2049, about 870;
  - `PoliciesScreen` with its helpers: :2050-2581, about 530;
  - `SchedulesScreen` with its constants: :2582-3201, about 620;
  - the modals: :3202-3565, about 364 (`ConfirmGuardFile`, `ConfirmUninstall`, `NavScreen`, `LinkModeScreen`, `ScheduleTimeScreen`, `CursorModelsRead`/`CursorModelScreen`);
  - the app block: :3566-4438, about 873, of which `MutationLock` is :3605-3676 and `UnifiedApp` is :3677-4438, about 762.

  The amended target set is one module per screen, plus modals, plus the app, plus siblings wherever a block alone breaks the cap:
  - `doctor_screen.py`;
  - `uninstall_screen.py`, with a sibling (for example `uninstall_review.py`) that takes `UninstallInputs`, `_UninstallEntry`, `config_split`, the `_review_line`/`_retired_*` helpers and any pure non-widget helpers that `UninstallScreen` needs to get under 800;
  - `policies_screen.py`;
  - `schedules_screen.py`;
  - `modals.py`;
  - `mutation_lock.py`, with `MutationLock`, `MUTATION_REFUSAL` and `SCHEDULED_RUN_REFUSAL`;
  - `wizard_app.py`, with `UnifiedApp` and its app-level messages.

  Each split module carries the inputs, messages and constants that only it uses. Something two or more modules share gets one home that the others import, and the import graph has no cycle: a screen imports `wizard_app` only under `TYPE_CHECKING`. When a class body is still over the cap after the verbatim move and the comment cleanup, pure helpers move into module-level functions in its sibling. A widget method keeps its behaviour and its name on the class. The planner may rename the siblings. Call sites in `setup.py`, `installer/` (`catalog_tui.py`, `execute_screen.py`, `terminal_shell.py`, `ui_common.py`) and tests are updated in the commit that moves the symbol.
  - Tests that cover moved code may move into a per-module test file. They change only their import path, never an assertion.
  - The pilot safety net (`tests/test_layout_80x20.py`, `tests/test_screen_family.py`, `tests/test_wizard_app.py`) stays green at every intermediate commit.
- **D-08 (intent kept: `max_lines=5000`, one write helper, a dropped-lines label above the log, newest line last).** The `RichLog` is at `execute_screen.py:431` with no `max_lines`. The writes are scattered over about :869-953. The plan re-locates every `#execute-log` write.
- **D-09.** Unchanged. The "before" SHA for the net-line report is the last commit before the first Phase 25 code commit, so this amendment and the plans are not counted.

**D-10 (new, inherited from 24.5 D-17): retire the `host_setup` method kind.** pi moved to a bun method plus an executed pnpm `node` fallback, so `rg host_setup installer/registry.toml` finds nothing and the kind has no registry user.
- Delete `installer/host_setup.py` (`HOST_SETUPS`, `HOST_SETUP_IDS`, `pnpm_add_command`) and every branch that exists only for it:
  - `model.py`: the kind in the closed kinds set (:32), its `METHOD_PARAMS` entry (:71) and the `setup_id` validation (:812-814);
  - `engine.py`: `_HANDOFF_KINDS` and the `host_setup` branch (:41, :161);
  - `executors.py`: `host_setup_handoff` and the unused `host_setup_approval_disclosures` (:708-720);
  - `update.py`: `host_setup_update_argv` and its two call sites (:270-276, :391, :445);
  - `ownership.py`: `_HOST_SETUP_OWNERS`, `_host_setup_owner` and its dispatch (:139-140, :945, :1009-1027);
  - `install_ownership.py`: `_host_setup` and its `"host-setup"` probe key (:94, :378);
  - `resolve.py`: the `host_setup` rank and the list entry (:21, :73);
  - `version_status.py:457`, `receipts.py:42` (`RECEIPTLESS_KINDS`), `catalog_audit.py:546`, and the doc comments in `session.py:52`, `post_install.py:15` and `enums.py:62`.
- `InstallStatus.MANUAL_REQUIRED` stays, because native-package handoffs still use it (`engine.py:103`).
- Behaviour after the change: a registry row that declares `kind = "host_setup"` is rejected by the closed-kind loader like any other unknown kind (18-01). No shipped row declares it.
- Compatibility: the plan checks that a receipt, version-cache entry or ownership record written by an earlier host_setup install of pi is still read without a crash. pi installed through pnpm keeps resolving owner pnpm through the pnpm globals evidence (24.5).
- Tests that exist only for the kind are deleted with it. Tests that use it as a sample kind switch to a live kind without weakening their assertion.

**D-11 (new, inherited from 23.2 D-13 and 24.1 D-21): retire the empty sensitive-action machinery.** `SENSITIVE_POST_INSTALL_ACTIONS` is `()` and `SENSITIVE_PROMPTS` is `{}`. The comment at `post_install.py:110` already hands the sweep to Phase 25.
- Delete:
  - `ConfirmSensitiveAction`, `SensitivePrompt`, `SENSITIVE_PROMPTS` and `sensitive_prompt` (`post_install.py`), and the `confirm` parameter that every `PostInstallAction` receives only to `del` it;
  - `SENSITIVE_POST_INSTALL_ACTIONS` and the loader field `default_enabled_sensitive_actions` (`model.py:145-147, :360-406, :837-871`);
  - `SensitiveActionScreen`, `_ask_sensitive_action` and `_DISMISSAL_SENSITIVE` (`execute_screen.py:143`, :850);
  - the `confirm_sensitive_action`/`confirm_sensitive` threading through `engine.py` (:176, :456), `session.py` (:31, :82, :208, :282, :297) and the test doubles.
- The `.claude/architecture.md:779` paragraph on the sensitive-action confirmation is updated in the same plan.
- No registry row declares `default_enabled_sensitive_actions`.
- Behaviour is unchanged, because no action ever asks.

**D-12 (new, 2026-11-15 after 25-RESEARCH): what "the CLI `--all`/`--categories` test files are byte-identical" means.** Read literally, SPEC R3 cannot be met. LEAN-02 moves composition names out of `setup`, so `tests/test_setup.py` must retarget imports and monkeypatches. D-11 also changes `tests/test_app.py`. Best over easy: keep the intent, which is that no assertion about the CLI flags changes.
- `tests/test_cli.py` (the flag parser) stays byte-identical.
- In `tests/test_setup.py`, every test that exercises `--all` or `--categories` keeps every `assert` line and every expected value byte-identical. Only import lines, module-object references and monkeypatch targets may change.
- A guard in the phase-gate plan diffs those tests against the pre-phase SHA and fails on any removed or changed `assert` line.
- D-08 wording: the notice reads "1 earlier line dropped" for one dropped line and "N earlier lines dropped" otherwise.
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
