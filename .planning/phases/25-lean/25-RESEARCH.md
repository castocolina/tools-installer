# Phase 25: Lean - Research

**Researched:** 2026-11-15 (HEAD fc479a0a; code unchanged since the 8218c996 pre-phase check)
**Domain:** Python/Textual refactor: dead-code sweep, composition move under pyright strict, module split, bounded RichLog
**Confidence:** HIGH on inventories, line ranges, test impact (all measured live this session); MEDIUM on projected post-split line counts and net-line estimate.

<user_constraints>
## User Constraints (from 25-CONTEXT.md; full text there, binding amendment included)

### Locked Decisions
- Decision rule: best over easy. This phase runs last; every deletion list is computed at execution time against the live tree.
- **D-01** A permanent `tests/test_reachability.py` builds the import graph by AST from the entry points, follows function-level imports and string-keyed dispatch tables, fails if any `installer/` module is unreachable. vulture stays a secondary symbol-level check. (Amended: still needed; vulture-60 output is a triage list, not proof.)
- **D-02** The deletion list is what D-01 reports at execution time; each kept SPEC target is listed in the summary with its caller. Already gone: `audit.py`, `agent_policy.py`, `agent_guidance.py`, `guards.py`, `policy.agent_environment_policy`/`compose_agent_environment_policy`, `Tool.source`/`owner`/`uninstall`. `agent_env.py` stays live (`agent_settings.py` imports it). The vulture-60 candidates are triaged one by one; functions whose only caller is `setup.py` count as live.
- **D-03** The questionary checkbox chooser is already gone. `setup.py` keeps `ask_confirm`, `_ask_select`, `_ask_mismatch`; `app._choose_tools` is the live `--all`/`--categories` filter and stays. Summary records the check.
- **D-04** Judge each Message by its post site; a Message carrying a generation/epoch or read by a supersede check stays (AR-04).
- **D-05** Narrow move to `installer/compose.py`, names kept: `_build_app`, `_execute_inputs`, and the transitive closure of `setup.py` private helpers/classes they call that touch neither questionary nor prompt_toolkit. A moved helper that a `_run_*` route also calls moves too and `setup.py` imports it back. A questionary callback reaches compose only as an injected parameter. `setup.py` keeps `main`, `_run_*` dispatch, tty/questionary plumbing, arg parsing. Tests keep `# pyright: ignore[reportPrivateUsage]`.
- **D-06** One definition of the path/env constants in `compose.py` (adds `_DAEMON_PLIST_PATH`, `_LINUX_DAEMON_UNIT_DIR`, `_ENVIRONMENT_D_DIR`, `_WARN_CONSOLE`); `setup.py` imports back what it still uses; `_STYLE` stays in setup.py; `installer/` never imports `setup.py`.
- **D-07** One module per screen plus modals plus the app plus siblings wherever a block alone breaks the 800-line cap: `doctor_screen.py`, `uninstall_screen.py` (+ a sibling such as `uninstall_review.py`), `policies_screen.py`, `schedules_screen.py`, `modals.py`, `mutation_lock.py`, `wizard_app.py`. Verbatim move first, comment cleanup second; no shim; screens import `wizard_app` only under `TYPE_CHECKING`; a widget method keeps its behaviour and name on the class; F14 modal merge excluded; tests change only import paths.
- **D-08** `RichLog(max_lines=5000)` plus one centralized write helper with its own counters; a one-line "N earlier lines dropped" label directly above the log, inside the log panel, hidden until the first drop; newest line always last; 6,000 writes leave 5,000 lines plus the notice; 5,000 writes show no notice. User-confirmed 2026-10-14.
- **D-09** Full suite + `make validate`, CI green on ubuntu and macOS; summary reports net production lines removed from `git diff --stat` over `installer/` and `setup.py` with both SHAs ("before" = last commit before the first Phase 25 code commit).
- **D-10 (new)** Retire the `host_setup` method kind (`host_setup.py`, `model.py`, `engine.py`, `executors.py`, `update.py`, `ownership.py`, `install_ownership.py`, `resolve.py`, `version_status.py`, `receipts.py`, `catalog_audit.py`, doc comments). `InstallStatus.MANUAL_REQUIRED` stays. Compat: an old record naming host_setup must not crash. Kind-only tests are deleted, sample-kind tests switch to a live kind without weakening assertions.
- **D-11 (new)** Retire the empty sensitive-action machinery (`ConfirmSensitiveAction`, `SensitivePrompt`, `SENSITIVE_PROMPTS`, `sensitive_prompt`, the `confirm` param of every `PostInstallAction`, `SENSITIVE_POST_INSTALL_ACTIONS`, loader field `default_enabled_sensitive_actions`, `SensitiveActionScreen`, `_ask_sensitive_action`, `_DISMISSAL_SENSITIVE`, the `confirm_sensitive_action`/`confirm_sensitive` threading and test doubles) and update `.claude/architecture.md:779`.

### Claude's Discretion
Wave order (suggested: reachability test + deletions, compose.py, wizard_app split, log bound, size report) and the sibling module names.

### Deferred Ideas (OUT OF SCOPE)
F14 modal consolidation (`ChoiceModal`/`ConfirmModal`). Not folded: pnpm shims, GSD per-repo, pi repair, Playwright Chrome.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| LEAN-01 | Dead code removed, race epochs stay | Sections 1.1 (D-10), 1.2 (D-11), 1.3 (D-04), 1.4 (vulture triage), 1.5 (reachability test) |
| LEAN-02 | Composition in an `installer/` module under pyright + coverage | Section 2 (move set, constants, pyright fallout, coverage, test-retarget cost, sandbox hazard) |
| LEAN-03 | `wizard_app.py` split, review-history comments dropped | Section 3 (symbol map, projections, importers, string patch targets, cap breakers) |
| LEAN-04 | Run log bounded | Section 4 (write sites, Textual trim behaviour, label placement, tests) |
</phase_requirements>

## Summary

Phase 25 is a pure-refactor phase with five real work packages. Measured at HEAD: `installer/wizard_app.py` is 4,438 lines, `setup.py` 1,489, `installer/` 41,213 lines. No `installer/` module is unreachable by import today (AST check, below), so the D-01 test is a regression guard that passes on day one; the real deletions are the two inherited subsystems (D-10 host_setup, D-11 sensitive-action) plus a short vulture-60 triage list. All ten remaining `Message` classes in `wizard_app.py` have a live post site and handler: D-04 deletes none.

The expensive parts are not the deletions. They are (a) LEAN-02: moving the composition closure forces about 100 `monkeypatch.setattr(setup, ...)` retargets in tests and, critically, the autouse `sandboxed_setup_paths` fixture plus `test_no_setup_home_constant_points_at_the_real_home` only re-root `setup`'s globals; once the home-derived constants live in `installer/compose.py` those guards would silently stop covering the code that reads them (host-safety hazard); (b) LEAN-03: three of the planned modules exceed 800 lines after a verbatim move (doctor ~829, uninstall_screen ~964, wizard_app ~844), cross-module private names must become public (pyright strict `reportPrivateUsage`), and `monkeypatch.setitem(vars(wizard_app), ...)` patches break silently; (c) the SPEC's "CLI --all/--categories test files byte-identical" clause conflicts with D-11/LEAN-02/LEAN-03 for every file except `tests/test_cli.py`.

**Primary recommendation:** run D-10 then D-11 first (they remove `confirm_sensitive_action`, which also removes 1 of the 5 pyright-strict diagnostics compose would inherit), then LEAN-02 with a dual-module test-patch helper and a generalized sandbox fixture, then the split as verbatim-move commits per screen followed by one comment/helper-extraction commit per over-cap module, and land the size/review-ID guard test last. LEAN-04 is independent and can run in parallel with LEAN-02.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Dead-code reachability guard | Test (tests/) | Makefile validate (vulture) | Import-graph AST check; vulture is symbol-level backup |
| App composition (`_build_app`, services, probes) | `installer/compose.py` (typed, covered) | `setup.py` (parse, prompt, call) | Architecture rule 4: decisions belong in `installer/` |
| Questionary/prompt_toolkit plumbing | `setup.py` | - | Untyped TTY-only boundary stays outside strict |
| Screen modules / modals / app | `installer/*_screen.py`, `modals.py`, `wizard_app.py` | `ui_common.py` shared helpers | One screen per module; shared helpers need one public home |
| Bounded run log | `installer/execute_screen.py` (RichLog subclass + one write helper) | Textual `RichLog.max_lines` | Textual trims silently, notice must be a sibling widget |
| Host-state safety in tests | `tests/conftest.py` + `tests/test_sandbox.py` | `real_home_untouched` session net | Constants resolved at import must be re-rooted per module |

## Standard Stack

No new packages. Everything is already in the project. [VERIFIED: pyproject.toml:1-30]

| Tool | Version | Purpose |
|------|---------|---------|
| Python / uv | 3.12.12 in .venv, `requires-python >=3.11` | runtime |
| textual | 8.2.7 (`.venv`, `textual>=8`) | TUI, `RichLog` |
| pytest + pytest-xdist + pytest-asyncio (`asyncio_mode = "auto"`) | per lock | tests; Textual pilot tests are plain `async def test_*` |
| pyright | 1.1.410 strict, `include = ["installer", "tests"]` | `[tool.pyright]` |
| vulture | `min_confidence = 80`, `paths = ["installer"]` | secondary dead-code check |
| coverage | `source = ["installer"]`, `branch = true`, `fail_under = 90` | gate |

### Package Legitimacy Audit
No external packages are installed or added by this phase. Audit not applicable: **Packages removed (SLOP): none. Packages flagged (SUS): none.**

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `_start_line` read in a `RichLog` subclass for the dropped count | helper-owned write counter | A write counter is wrong whenever a write wraps/multi-lines (RichLog stores rendered strips) or is deferred before the first resize; `_start_line` is exactly the cumulative trimmed-strip count. Private attr, so pin it with the 6,000/5,000 test. |
| Patch both modules in tests | have `setup.py` read constants as `compose.<NAME>` | Single patch target, but D-06 says names are imported back and ~20 setup sites change. Recommend the dual-patch helper. |

## Architecture Patterns

### Data flow (post-phase)
```
setup.py main() --parse--> _run_* routes --inject ask_confirm/_ask_mismatch--> installer/compose.py
   compose._build_app(...) --constructs--> UnifiedApp (wizard_app.py)
        UnifiedApp --imports--> doctor_screen / uninstall_screen(+uninstall_review) / policies_screen
                                / schedules_screen / modals / mutation_lock / catalog_tui / execute_screen
        screens --TYPE_CHECKING only--> wizard_app.UnifiedApp
   shared helpers (fit, sentence, TIMES_LISTED, probe aliases) --> ui_common.py (public names)
ExecuteScreen: InstallLogLine / RunFinished messages --> _write_log() --> RunLog(RichLog, max_lines=5000)
                                                          \--> #execute-log-dropped Static (hidden until dropped > 0)
```

### Anti-Patterns to Avoid
- **Moving constants without re-rooting the test sandbox.** See Pitfall 1.
- **Cross-module `_private` imports.** pyright strict errors (`reportPrivateUsage`, verified: a probe file produced `"_start_line" is protected and used outside of the class in which it is declared`). Rename shared names public; never add `# pyright: ignore` (SPEC prohibition).
- **Changing an assertion to make a refactor pass.** Only import paths, patch targets and deleted-target code may change.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Import graph | a regex/grep over `import` | `ast` walk (precedent: tests/test_registry.py:2606-2615, tests/test_shellrc.py:958, tests/test_executors.py:169) | function-level and `TYPE_CHECKING` imports |
| Log trimming | own ring buffer | `RichLog(max_lines=5000)` | Textual trims at `_rich_log.py:264-267` |
| Dropped-line counter | write counter | `RichLog._start_line` via subclass | exact under wrapping and deferral |
| Test-time sandboxing | per-test ad hoc patches | extend `sandboxed_setup_paths` generically over `("setup", "installer.compose")` | one place, covers future constants |

## Runtime State Inventory (D-10/D-11 retire a kind and a field)

| Category | Items Found | Action |
|----------|-------------|--------|
| Stored data | Receipts: `RECEIPTLESS_KINDS` includes host_setup so none was ever written; `receipts.read` accepts any `method.kind` string (`installer/receipts.py:224-256`, no METHOD_KINDS check). Version cache fingerprints `{"kind": method.kind, "params": ...}` (`installer/version_cache.py:114`); an old entry just mismatches (cache miss). | None; no migration. Compat verified by reading. |
| Live service config | None. | None |
| OS-registered state | None. | None |
| Secrets / env vars | None. | None |
| Build artifacts | `installer/__pycache__/host_setup*.pyc` is untracked build output only. | None |
| pi installed through the old pnpm host_setup | `update.py` `owner == "pnpm"` with `method is None` becomes a plain refusal (`unsupported`, hint `pnpm add --global --ignore-scripts <pkg>`); pi now has bun+node methods (registry.toml:3290-3297) so its live update goes through the method path. `tests/test_update.py:1541 test_update_refuses_host_setup_pnpm_cleanly` already pins this refusal and survives unchanged. | Code edit only |

## 1. LEAN-01 deletion inventory (measured live)

### 1.1 D-10: retire `host_setup`

Production sites (all read this session; quotes verbatim):

| File:line | Content | Action |
|---|---|---|
| `installer/host_setup.py` (56 lines) | `HOST_SETUPS: dict[str, HostSetup]`, `HOST_SETUP_IDS = tuple(HOST_SETUPS)`, `def pnpm_add_command(setup_id: str)`; `HostSetup.requires_project_target` and `approval_disclosures` have no reader | delete file |
| `model.py:12` | `from installer.host_setup import HOST_SETUP_IDS` | delete |
| `model.py:32` | `"host_setup",` in `METHOD_KINDS` | delete |
| `model.py:71` | `"host_setup": frozenset({"setup_id"}),` in `METHOD_PARAMS` | delete |
| `model.py:149` | `"host-setup",` first entry of `OWNER_PROBES` | delete (D-10 list missed this; the drift guard `tests/test_install_ownership.py:673-685` requires `set(_PROBES) <= set(OWNER_PROBES)`, so delete both together) |
| `model.py:812-814` | `if kind == "host_setup": ... unknown host setup` | delete |
| `engine.py:41` | `_HANDOFF_KINDS = frozenset({"host_setup"})` | delete; `_manager_method` (:44-51) returns `True` after the download/app/cargo check |
| `engine.py:161-162` | `if method.kind == "host_setup": return False, None, executors.host_setup_handoff(method), ()` | delete branch |
| `engine.py:296-305` | `verified, unverified_reason, handoff, notes = _perform(...)`; `if handoff: return InstallOutcome(... MANUAL_REQUIRED ... handoff=handoff)` | dead after the branch goes: `_perform`'s handoff slot is always `()`. Shrink `_perform` to a 3-tuple and drop the `if handoff` block. This changes the fake at `tests/test_engine.py:2144-2152` (`fake` returns `(False, None, (), ())`); a return-shape edit of a double, not an assertion. |
| `engine.py:97-98, 153` | comments naming host_setup | reword |
| `executors.py:18` import; `:708-714 host_setup_handoff`; `:717-724 host_setup_approval_disclosures` | | delete (the latter has zero callers anywhere) |
| `update.py:101` import `pnpm_add_command`; `:270-281 host_setup_update_argv`; `:391`; `:443-449`; module doc `:37-39` | `update_refusal`: condition becomes `ownership.owner == "pnpm" and method is None`; `_perform` `elif owner == "pnpm":` branch becomes `executors.execute(method, runner)` and needs a `method is None` guard or an explicit `UpdateError` so pyright narrows `Method | None`. Check whether `real_pnpm` is still imported/used afterwards (ruff F401). | edit |
| `ownership.py:65` import; `:139-140 _HOST_SETUP_OWNERS`; `:945 return _host_setup_owner(...)`; `:1009-1050 _host_setup_owner` | the `owner is None` branch (verified non-native manager) becomes `return None`; reword the comment at :940-944 | edit |
| `install_ownership.py:27` import; `:94-111 _host_setup`; `:378 "host-setup": _host_setup,`; comment `:44`, `:439` | delete | edit |
| `resolve.py:21` `"host_setup": 15,`; `:73 "host_setup",` | delete both (`tests/test_resolve.py:931` pins the same dict: delete that entry) | edit |
| `version_status.py:450-460` | the `or any(method.kind == "host_setup" ...)` arm of `version_argv`; the Volta arm stays | edit |
| `receipts.py:42` | `RECEIPTLESS_KINDS = frozenset({"dnf", "apt", "pacman", "rpm_ostree", "host_setup"})` | drop the member |
| `catalog_audit.py:546` | `if kind in ("sdkman", "host_setup", "rpm_ostree"):` | drop the member |
| comments `session.py:52`, `post_install.py:15` (and the doc at `post_install.py` header naming `installer/host_setup.py`), `enums.py:62` | reword |
| `.claude/architecture.md:328-331` (decision-tree branch naming `host_setup`/`HOST_SETUPS`), `:774-775` (host-setup doctrine), `:1098` ("Native, skill and `host_setup` kinds write none") | reword; `.claude/skills/tool-onboarding/SKILL.md:57,111,172` mention `host_setup`, update. `rg` skips hidden dirs by default: use `rg --hidden` or pass `.claude/` explicitly. |

`registry.toml`: no `host_setup`/`host-setup` row. [VERIFIED: rg over installer/registry.toml returned no match; pi is `bun` + `node`, registry.toml:3290-3297]

**Console-handoff path after D-10:** `InstallOutcome.handoff` and `render_handoff` are NOT dead: native-package handoffs still set `handoff=(manual.command,)` (`engine.py:276`) and the refuses-existing path sets it (`:259`); `render.py:500-513` prints it. Only `_perform`'s handoff slot and the `if handoff:` block at `engine.py:297` die. `_HANDOFF_KINDS` is fully dead.

`pnpm_add_command`: callers are only `update.py:101/278` (and `tests/test_host_setup.py`). No other caller. [VERIFIED: rg over installer/ setup.py]

Tests (delete = exists only for the kind; switch = sample kind):

| File | Tests | Verdict |
|---|---|---|
| `tests/test_host_setup.py` | whole file | delete |
| `tests/test_engine.py:762`, `:778` | `test_host_setup_kind_routes_to_host_setup_handoff`, `test_a_host_setup_method_still_hands_off` | delete |
| `tests/test_engine.py:1712` | `test_handoff_kinds_are_never_smoked` (only host_setup is a handoff kind via `_HANDOFF_KINDS`) | delete |
| `tests/test_engine.py:1150-1165` | a post-install-asks-nothing test using host_setup as the method (also uses `confirm_sensitive_action`) | rewrite with a `dnf` method (still MANUAL_REQUIRED) when D-11 runs; keep `post_install_handoff == ()` assertion |
| `tests/test_ownership.py:3010-3090` (`_pi_tool`, 3 tests) | host_setup owner resolution | delete (check where the block ends before cutting) |
| `tests/test_install_ownership.py:92`, `:895` | host-setup probe tests | delete |
| `tests/test_update.py:50` import, `:1736-1785` (`_pi_target`, 3 pi host-setup update tests, `test_host_setup_without_a_reviewed_command_is_still_refused`) | delete; keep `:1541` |
| `tests/test_session.py:1878` | `test_the_review_offers_pi_an_update_through_its_host_setup` (scenario gone: pnpm + `method is None` is now refused) | delete |
| `tests/test_version_status.py:3778-3830` | `test_host_setup_tool_version_probes_the_unresolved_path`, and the three `host_setup_*` params of `test_resolve_status_forwards_the_unresolved_path_for_volta_and_host_setup` | delete the first; keep the `volta` param only |
| `tests/test_model.py:764` param, `:1307-1321 test_a_host_setup_method_still_loads`, `:1352-1368` (frobnicate row uses `kind = "host_setup"`), `:~1955` | param `("host_setup", 'setup_id = "pi"')` is the only row of `test_smoke_argv_is_rejected_where_nothing_is_installed`: switch it to a live kind that installs nothing (e.g. `dnf`, confirm `METHOD_PARAMS` allows the body) or drop the test if no live kind applies; `1307` delete; `1352` switch the sample kind to `brew` + `formula` | mixed |
| `tests/test_receipts.py:682` | param in `test_receiptless_kinds_write_nothing` | delete the param |
| `tests/test_catalog_audit.py:354-355` | param `Method("host_setup", ...)` | delete the param |
| `tests/test_render.py:422`, `tests/test_execute_screen.py:1331` | `method_kind="host_setup"` in a hand-built `InstallOutcome` | switch to `method_kind="dnf"`, assertions untouched |
| `tests/test_resolve.py:931` | expected `_RANK` dict | delete the entry |
| `tests/test_session.py:1416,1453,1465` | `Method(kind="host", params={"host_setup": True})`: a param key, unrelated kind | no change |
| `tests/test_registry.py:2115` | `assert "host_setup" not in kinds` | keep (passes) |

### 1.2 D-11: retire the sensitive-action machinery

`PostInstallAction` signature today: `Callable[[Tool, Platform, ConfirmSensitiveAction | None], tuple[str, ...] | PostInstallOutput]` (`post_install.py:95-97`). All nine registered actions take the third param and `del` it (`_clone_nvim_starter :243`, `_set_login_shell :304`, `_source_shell_init :342`, `_set_omz_theme :351`, `_set_omz_plugins :396`, `_apply_agent_tuning :429`, `_apply_terminal_tuning :446`, `_show_lean_tips :455`, `_show_nvim_hints :464`). Smallest coherent removal: `PostInstallAction = Callable[[Tool, Platform], tuple[str, ...] | PostInstallOutput]`; drop the parameter and the `del` from each action; `run_post_install(tool, platform)` calls `action(tool, platform)`.

Production sites:

| File:line | Action |
|---|---|
| `post_install.py:82` `ConfirmSensitiveAction = Callable[[str, str], bool]`; `:100-112` `SensitivePrompt` + `SENSITIVE_PROMPTS: dict[str, SensitivePrompt] = {}`; `:115-120 sensitive_prompt`; `:520 run_post_install(... confirm=None)` | delete / shrink; check `replace`, `shell_init_bundle` imports for F401 |
| `model.py:145-147` comment + `SENSITIVE_POST_INSTALL_ACTIONS: tuple[str, ...] = ()`; `:360`, `:383`, `:406` `default_enabled_sensitive_actions` field/ctor; `:837-871` loader (incl. the `undeclared` check `:844` and the kwarg `:871`) | delete; a registry row declaring the key is then rejected as an unknown key (SPEC R1 amendment) |
| `engine.py:25` import, `:176` param `confirm_sensitive_action`, `:202` doc, `:254`, `:370` `_dispatch_post_install(...)`, `:456` signature | delete param and arg |
| `session.py:31` import; `:82` `SensitiveInstall.__call__` param; `:208` `RunContext.confirm_sensitive`; `:282` `_with_force(... confirm ...)`; `:297-301` forced wrapper kwargs; `:530` call | delete; `_with_force` stays (it adds `repair=True`) |
| `app.py:38` import `sensitive_prompt`; `:171-173` `confirm_sensitive` closure; `:184` `confirm_sensitive=None if options.yes else confirm_sensitive` | delete (the CLI route); `prompter` may stay if used elsewhere in the function |
| `execute_screen.py:37` import; `:75 _DISMISSAL_SENSITIVE`; `:143-188 SensitiveActionScreen` (+ `_SENSITIVE_CHOICES`); `:685 confirm_sensitive=self._ask_sensitive_action if attended else None`; `:849-860 _ask_sensitive_action`; `:875-877` the `or message.line == _DISMISSAL_SENSITIVE...` arm of `dismissed`. Keep `PromptOpen`, `ask_from_worker`, `ChecksumMismatchScreen`, `_DISMISSAL_SKIP` (checksum prompt still uses them). `attended` stays (used for `on_mismatch`). |
| `setup.py` | no reference (grep clean); `setup.py:653` strict error disappears with the param |
| `.claude/architecture.md:687` (name list), `:779-784` paragraph | rewrite; `tests/test_docs.py:98` `"binds the sensitive-action confirmation"` in `_PHASE_14_REQUIRED` and the docstring at `:115-116` must drop that phrase in the same commit (docs test pins the paragraph) |

Test fan-out (counts of lines naming the symbols): `test_execute_screen.py` 92, `test_session.py` 16, `test_wizard_app.py` 13, `test_post_install.py` 12, `test_app.py` 9, `test_engine.py` 7, `test_model.py` 4, `state_doubles.py` 4 (`ConfirmSensitiveAction` import `:24`, `self.confirms` `:180`, `confirm_sensitive_action` param `:193`, append `:198`), `test_setup.py` 2.
- delete outright: `tests/test_execute_screen.py:358-390` autouse `legacy_sensitive_prompts` fixture and tests `:1062-1299` (`_recording_sensitive_install` through `test_cancel_is_inert_while_the_sensitive_prompt_is_open`; keep `:1300 test_execute_keys_name_the_idle_actions_before_a_run`); `tests/test_post_install.py:258 test_sensitive_tables_are_empty`, `_record`, the `asked`-based tests; `tests/test_model.py:1950-1982` (`test_sensitive_tables_are_empty` and the `SENSITIVE_POST_INSTALL_ACTIONS == ()` lines at `:1952,1969`); `tests/test_session.py:1236-1335` confirmation-forwarding tests (`test_execute_plan_forwards_the_confirmation_and_unchanged_kwargs`, `test_sensitive_install_protocol_parameters_are_unchanged` and the `run(confirm)` test).
- mechanical (~50 install fakes in test_execute_screen/test_wizard_app/test_app/test_session/test_setup/state_doubles): remove the `confirm_sensitive_action: ConfirmSensitiveAction | None = None` parameter and its name from `del ...` lines; remove the import. `state_doubles.py`: drop `confirms`; check no test reads `.confirms`.
- `test_post_install.py:66-86 _tool/_login_shell_tool(default_enabled_sensitive_actions=...)`: drop the kwarg; `:279 sensitive = set(...)` and its assertion line in `test_post_install_tables_are_disjoint_and_match_their_schema_sets` go with the target.

### 1.3 D-04: the remaining Message classes (all KEEP)

| Message (`wizard_app.py`) | Post site | Handler | Epoch/generation | Verdict |
|---|---|---|---|---|
| `GlobalsReinstalled` :252 | :919 (`_reinstall_globals_worker`) | `on_globals_reinstalled` :1014 | no | keep (live hand-off) |
| `GlobalsAudited` :265 | :950 (`_audit_globals_worker`) | `on_globals_audited` :956 | `generation` | keep (AR-04) |
| `DiskPressureProbed` :291 | :550 (`_probe_disk_pressure_worker` finally) | `on_disk_pressure_probed` :552 (clears `disk_probing`, read by tests) | no | keep |
| `ScheduleChanged` :312 | :3089 | `on_schedule_changed` :3091 | no | keep |
| `ScheduleManagerProbed` :325 | :2752 | `on_schedule_manager_probed` :2754 | no | keep |
| `RemovalFinished` :1162 | :1954 | `on_removal_finished` :1956 | no | keep |
| `CursorModelsRead` :3446 | :3507 | `on_cursor_models_read` :3509 | no | keep |
| `ScheduleDefaultsApplied` :3572 | :4042 (worker `finally`) | `on_schedule_defaults_applied` :4044 | no | keep |
| `RefreshPublished` :3587 | :3926, :3932 | `on_refresh_published` :3936 | no | keep: `request_refresh`/`state_refreshed` (:3897, screens' `state_refreshed`) are the re-render trigger; these two are the worker-to-loop hand-off, not replaced |
| `RefreshFinished` :3597 | :3934 | `on_refresh_finished` :3945 | no (reads `_refresh_pending`) | keep |

Result: D-04 deletes nothing; summary lists all ten with callers. The messages move with their screens in LEAN-03.

### 1.4 D-02 vulture-60 triage

`uv run vulture installer --min-confidence 60` printed 251 lines (output saved at `.../scratchpad/p25-vulture60.txt`). About 200 are Textual framework hooks (`compose`, `on_mount`, `on_*`, `action_*`, `BINDINGS`, `DEFAULT_CSS`, `can_focus`, `cursor_type`, `no_wrap`) and enum members: false positives. Note vulture at the gate's `min_confidence = 80` only reports imports/locals/unreachable code (unused functions score 60), so the gate cannot see dead functions: the reachability test and this triage are the only guards. Production callers measured by AST (Name/Attribute nodes in `installer/`, `setup.py`, `scripts/`):

| Candidate | Prod callers | Tests | Verdict |
|---|---|---|---|
| `AgentAdapter.instruction_path` / `permission_mode` (`agent_env.py:18-19`; `PermissionMode` :8) | none read in production (only set at construction, e.g. :61) | tests/test_agent_env.py (7/3 refs) | DELETE fields, `PermissionMode`, and their assertions (deleted-target) |
| `diskusage.probe_disk_pressure` | `setup.py:463` (`_DiskProbe`) | 16 | KEEP (live via setup.py; moves to compose with it) |
| `receipts.scan_retired` | `setup.py:875,882,1302` | 26 | KEEP |
| `render.render_troubleshooting` | `setup.py:1167,1476` | 1 | KEEP |
| `deps.requires_integrity_errors` (`deps.py:156`) | none | 4 | DELETE with its tests |
| `schedules.sweep_adapters` | `setup.py:810,1319` | 15 | KEEP |
| `run.run_interactive_command` (`run.py:92`) | none, not even tests | 0 | DELETE |
| `version_cache.save_manager_snapshot` (`:378`) | none, not even tests | 0 | DELETE |
| `shellrc.classify_source_line` (`:703`) | none | 12 | DELETE with its tests |
| `omz.disable_plugins` (`:238`) | none | 9 (tests/test_omz.py) | DELETE with its tests (judge against `MANAGED_PLUGINS` use first) |
| `catalog_tui.CatalogScreen.recommends_text` (:506), `status_text` (:502) | none | 13 / 74 | test-only accessors; `status_text` has 74 test uses: KEEP both unless the plan rewrites assertions (not allowed); list as "kept, caller = tests only" and flag to the owner |
| `UnifiedApp.catalog_for` (`wizard_app.py:4077`) | none | 30 | documented "headless-test seam": KEEP, list |
| `wizard_app._BodyStatic.renderable` (:336) | none | 0 real uses | DELETE (verify Textual does not call it: `Static` overrides) |
| `verify_registry.py:183 release_tag` field | no Name/Attribute reader | 0 | check keyword construction before deleting |
| `host_setup_approval_disclosures` (`executors.py:717`) | none | 0 | goes with D-10 |
| everything else listed (`run_wizard`, `configure_path`, `run_doctor`, `clean_rc_duplicates`, `run_uninstall`, `perform_uninstall`, `sync_terminal_shells`, `load_categories`, `detect`, `context_for`, `use_git_runner`, `use_shell_init_sourcing`, `CallbackPrompter`, `SettingsStore`, `ScheduleDefaultWarnings`, ...) | `setup.py` | many | KEEP (setup.py callers count as live) |

`app._choose_tools` is live (the `--all`/`--categories` filter) and `selection.select_tools` is reachable. D-03: `prompt.py` now holds only `AskConfirm`, `Prompter`, `CallbackPrompter` (used at `setup.py:1410`). [VERIFIED: read installer/prompt.py:1-33, installer/selection.py:1-15]

### 1.5 D-01 reachability test

Measured now (script `p25-reach.py`): entry points `setup.py` plus `installer.verify_registry` and `installer.catalog_audit` (Makefile:29, :32 `python -m installer.verify_registry|catalog_audit`; both have `if __name__ == "__main__"` at `verify_registry.py:1648`, `catalog_audit.py:1792`). There is no `installer/__main__.py` and no `importlib`/`import_module` use in `installer/`. Result: **0 unreachable modules**, with or without `TYPE_CHECKING` edges. The test is therefore a regression guard and passes on day one.
- Entry discovery: do not hard-code; parse `setup.py`, every `installer/*.py` containing `if __name__ == "__main__"` (excludes `installer/helper_assets/*.py`, which are installed data files, not imported), and `python -m installer.<x>` lines of the Makefile (regex), assert the Makefile modules are among them.
- Edges: `ast.walk` over the whole file (function-level imports count): `ImportFrom(module="installer.x")`, `ImportFrom(module="installer", names=[x])`, `Import(installer.x)`. Count `TYPE_CHECKING` imports as edges only for a secondary report; the failing assertion is runtime-edge reachability.
- String-keyed dispatch tables that exist today: `post_install.POST_INSTALL_HOOKS` (`post_install.py:478`), `install_ownership._PROBES` (`:377`), `postinstall.POSTINSTALL_HOOKS`, `METHOD_KINDS`/`METHOD_PARAMS`/executor dispatch, `SMOKE_CHECKS`. All their values are Python names imported by the table's own module, so a module-level import graph already reaches them. They only matter for a symbol-level graph (not recommended: that is vulture's job). State this in the test docstring so nobody weakens it.
- Make the guard meaningful: add a seeded-violation case (a tmp tree with an orphan module must be reported), the style of `tests/test_shellrc.py` `test_scan_reports_*`.
- Precedent AST guards: `tests/test_registry.py:2600-2615` (`test_nothing_imports_the_skill_pack_module`, walks installer + tests + setup.py), `tests/test_executors.py:165-172` (elevation-literal scan), `tests/test_screen_family.py:3315-3330 _guarded_files()` (walks `installer/` + `setup.py`), `tests/test_locations.py:469` (`ast.parse(SETUP_PY.read_text())`).
- The same file is the natural home for the LEAN-03 guards (no `installer/*.py` over 800 lines among the split modules; no `CR-0|WR-0|IN-0` in them). Land those last (see wave order).

## 2. LEAN-02: `installer/compose.py`

### 2.1 Exact move set (AST closure over `setup.py`, script `p25-setup-map.py`)

Closure of `_build_app` (:743-1059, 317 lines) and `_execute_inputs` (:1062-1113, 52 lines), none touches questionary/prompt_toolkit (q-names: `questionary`, `create_input`, `create_output`, `Input`, `Output`):
`_timer_state_cache :320-345`, `_CompetitorProbe :348`, `_competitor_probe :373`, `_DiskProbe :395-469`, `_disk_pressure_probe :472`, `_cache_redirect_policies :502`, `_sync_terminals :532`, `_build_services :580-656`, `_split_sourced_from :659`, `_desktop_shell_policies :666`, **`_launch_repairs :677-687`** (not in the CONTEXT list), `_schedule_context :697`, `_invalidating :710`, `_schedule_removed_lines :727`, plus `Install :124` and the constants.

Not in the strict closure but listed by CONTEXT and pure-composition: `_sync_terminals_and_report :562` (called by `_teardown_cli`, `main`; calls only `_sync_terminals`) and `_reconcile_headless :733` (called by `main`; calls `_schedule_context`). Recommend moving both (best over easy: they are shared composition with no questionary), re-imported by setup. `_print_repairs :690` is print-only plumbing: stays. `_schedule_run_deps :1355` calls `_build_services`: stays, imports it back. `_teardown_cli`, `_verify_and_clean` take `ask_confirm` (questionary): stay.

Callers outside the closure that need the name imported back into setup.py: `_REGISTRY` (_run_doctor/_run_fix/_run_uninstall/_teardown_cli/_run_schedule/main), `_DEFAULT_BIN_DIR`, `_MYSHELLRC`, `_SHELLRC`, `_ZSHRC`, `_SHELL`, `_timer_state_cache`, `_competitor_probe`, `_disk_pressure_probe` (`_run_doctor`, `_verify_and_clean`), `_cache_redirect_policies`, `_desktop_shell_policies`, `_schedule_context`, `_schedule_removed_lines` (`_teardown_cli`), `_sync_terminals` (`_sync_terminals_and_report`, main), `_build_services` (`_schedule_run_deps`, main), `_split_sourced_from` (`_run_schedule`, main), `_launch_repairs` (`_run_doctor/_run_fix/_teardown_cli/main`), `_build_app` (`_run_interactive_wizard/_run_doctor/_run_fix/_run_uninstall`).

Constants (setup.py:112-136, read this session): `_REGISTRY`, `_DEFAULT_BIN_DIR = Path.home() / ".local" / "bin"`, `_MYSHELLRC`, `_SHELLRC`, `_ZSHRC = zshrc_path(Path.home(), os.environ)`, `_RC_PATHS = [_ZSHRC, Path.home() / ".bashrc"]`, `_SHELL = os.environ.get("SHELL", "")`, `Install = Callable[..., InstallOutcome]`, `_WARN_CONSOLE = Console(stderr=True)`, `_DAEMON_PLIST_PATH`, `_LINUX_DAEMON_UNIT_DIR`, `_ENVIRONMENT_D_DIR`. Moved code reads: `_DEFAULT_BIN_DIR, _MYSHELLRC, _REGISTRY, _SHELL, _SHELLRC, _ZSHRC, _DAEMON_PLIST_PATH, _LINUX_DAEMON_UNIT_DIR, _ENVIRONMENT_D_DIR, Install`. `_RC_PATHS` and `_WARN_CONSOLE` are read only by setup-side code (`_run_interactive_wizard`, `_verify_and_clean`, `_settings_store`): D-06 still says one definition in compose; `_RC_PATHS` depends on `_ZSHRC`, so move both. `_STYLE` stays.

Size: moved functions about 753 lines + ~25 constants + ~80 import lines: compose.py ≈ 850 lines. The 800 cap applies to the wizard split, not to compose; if the owner wants it applied, split `_build_services`+probes into a sibling.

### 2.2 Questionary callbacks
`_build_app` itself never touches questionary. Callbacks reach it by parameter or not at all: `ask_confirm` is passed into `_verify_and_clean`/`_teardown_cli` (stay in setup) and `_run_interactive_wizard` passes `ask_confirm`/`_ask_mismatch` into `run_wizard`/`_build_app` arguments. No change needed beyond the move; keep them as parameters.

### 2.3 pyright strict on the moved code
`uv run pyright setup.py` (read-only) reports 33 errors. In the compose-bound ranges only two sites:
- `setup.py:653` (inside `_build_services._install`, `**options: object` forwarded to `install_tool`): 3 diagnostics (`checksum_policy`, `confirm_sensitive_action`, `repair` argument types). D-11 deletes the `confirm_sensitive_action` one first; fix the other two by declaring `checksum_policy: ChecksumPolicy = "fail", repair: bool = False` keyword parameters on `_install` instead of `**options` (matches `session.py` `SensitiveInstall.__call__`).
- `setup.py:982` (`schedule_defaults: Callable[[], schedules.ReconcileReport] | None = None` then `def schedule_defaults()`): `reportRedeclaration` + `reportAssignmentType` (2 diagnostics). Fix by naming the closure `_schedule_defaults` and assigning `schedule_defaults = _schedule_defaults` inside the `if`, no suppression.
The other 28 errors stay in setup.py (questionary `Input | Output` at :289/:302, `contextmanager` deprecation at :173/:211/:253, `confirm` lambdas :1163-1352, `on_mismatch` at :1444) and are not gated. Estimate: compose passes strict with 4 fixes after D-11 (5 before). [ASSUMED: no other latent diagnostics appear once imports resolve in a new file; confirm by running pyright on the file as soon as it exists.] bandit and vulture(80) are clean on setup.py today (run read-only), ruff clean.

### 2.4 Coverage
Ran `tests/test_setup.py tests/test_schedules_handover.py tests/test_systemd_daemon.py tests/test_schedule_update.py` with `--cov=setup` (read-only): setup.py 96.3%; the moved line ranges 183 statements, 3 missed (98.4%), all inside `_build_app`. Adding compose.py to `source = ["installer"]` cannot move the 90% floor materially. `Makefile:35-36` comment ("setup.py (composition root) is lint/format-gated but stays out of pyright/coverage: it imports the untyped, TTY-only questionary") must be reworded: composition now lives in `installer/compose.py` under pyright and coverage, setup.py keeps only questionary/tty plumbing.

### 2.5 Test impact: this is NOT only an import-path change
Measured (script `p25-setup-patches.py`, `p25-patched-imports.py`): tests reach moved code through `monkeypatch.setattr(setup, "<name>", ...)`. After the move the moved functions look names up in `installer.compose`'s globals, so a patch on `setup` no longer intercepts them (real code runs, in some cases against home-derived real paths).

| Moved name | patch sites | files |
|---|---|---|
| `_build_app` | 9 | test_setup, test_schedules_handover (these stub the name as seen by `_run_*`: patch target stays `setup`) |
| `_execute_inputs` 1, `_competitor_probe` 1, `_disk_pressure_probe` 6, `_sync_terminals` 2, `_sync_terminals_and_report` 2, `_build_services` 5, `_schedule_context` 3, `_timer_state_cache` 4 | 24 | test_setup, test_schedules_handover, test_schedule_update (`_build_services` :249), test_systemd_daemon (reads) |
| constants `_DEFAULT_BIN_DIR` 4, `_MYSHELLRC` 3, `_SHELLRC` 3, `_ZSHRC` 2, `_RC_PATHS` 2, `_SHELL` 2, `_DAEMON_PLIST_PATH` 5, `_LINUX_DAEMON_UNIT_DIR` 3, `_ENVIRONMENT_D_DIR` 1 | 25 | test_setup `_sandbox` (:566-591) and three more copies (:1286, :2499, :2536) |
| imported names read by moved code and patched on `setup`: `Console` 19, `configure_path` 11, `sync_terminal_shells` 14, `run_doctor` 7, `is_installed` 5, `perform_uninstall` 5, `load_categories` 4, `ScheduleDefaultWarnings` 4, `VersionRefreshService` 2, `install_tool` 2, `UnifiedApp` 1, `resolve_github_tag` 1, `default_cache_path` 1, `run_probe` 1, `which_with_brew` 1 | ~78 (several names are read by both setup-side routes and compose: patch both) | test_setup, test_schedules_handover |

About 125 patch sites. Recommended mitigation (smallest, assertion-neutral): one helper `patch_composition(monkeypatch, name, value)` in `tests/` that does `monkeypatch.setattr(compose_module, name, value)` and also on `setup` when `setup` still has the attribute and a setup-side route reads it; `_sandbox` calls it for the 9 constants. Plan this as the heavy part of LEAN-02.

Other test touchpoints:
- `tests/conftest.py:292-312 sandboxed_setup_paths`: iterates `vars(sys.modules.get("setup"))` and re-roots every `Path`/path-list global. After the move, `installer.compose` holds the home-derived constants; the fixture must loop over both modules, or the real `_build_app` reads real-home constants. `real_home_untouched` (session net, `tests/conftest.py:183`) would fail the whole run late, but only if a test actually writes. **Host-safety item: generalize the fixture and extend `tests/test_sandbox.py:269-282 test_no_setup_home_constant_points_at_the_real_home` to compose.**
- `tests/test_setup.py:1347, 1374, 1385` `importlib.reload(setup)` to re-evaluate `_ZSHRC/_RC_PATHS` under a different `HOME`/`ZDOTDIR`: reload `installer.compose` first (then setup). `:1223` fresh-process `setup._ENVIRONMENT_D_DIR` works unchanged via import-back; `:3562`, `:4484` read `setup._SHELLRC/_MYSHELLRC` (import-back names, patched by `_sandbox`: fine if `_sandbox` patches both).
- `tests/test_versions.py:150-158` parses `setup.py` and asserts `resolve_tag_keywords` is non-empty and all `resolve_github_tag`; both keyword uses (`setup.py:592, 627`) are in `_build_services`, so the list becomes empty and the assert fails. Make the test also parse `installer/compose.py` (a path change, same assertion).
- `tests/test_locations.py:469-500` and `tests/test_run.py:812-826` read `main`/the `__main__` guard in setup.py: unchanged.
- Test imports from setup of moved names: `tests/test_setup.py` (`setup._build_app` 25 reads, `_disk_pressure_probe` 11, `_execute_inputs` 4, `_timer_state_cache` 3, `_build_services` 3, `_sync_terminals` 4, ...), `tests/test_systemd_daemon.py:296-308` (`setup._timer_state_cache`), `tests/test_schedules_handover.py`. Reads can stay via the import-back; patches must follow the table above.

## 3. LEAN-03: split of `installer/wizard_app.py`

### 3.1 Measured symbol map (script `p25-split-map.py`; 28 classes, imports occupy :15-135 = 121 lines)

| Lines | Symbols | Target module |
|---|---|---|
| 138-168 | `UninstallInputs` (31) | `uninstall_review.py` |
| 177, 182 | `DiskPressureProbe`, `CompetingProbe` aliases (used by Doctor, PolicyInputs, ScheduleInputs, `_competing_line`, `_temp_usage_line`, tests) | `ui_common.py` (shared, public) |
| 185-200 | `PolicyInputs` | `policies_screen.py` |
| 203-213 | `ScheduleInputs` | `schedules_screen.py` |
| 216-249 | `_NOTHING_TO_REINSTALL`, `_GLOBALS_*`, `_DISK_PRESSURE_*`, `_POST_APPLY_REWRITES` | `doctor_screen.py` |
| 252-297 | `GlobalsReinstalled`, `GlobalsAudited`, `DiskPressureProbed` | `doctor_screen.py` |
| 300-330 | `ScheduleChange`, `ScheduleChanged`, `ScheduleManagerProbed` | `schedules_screen.py` |
| 333-353 | `_BodyStatic`, `_DOCTOR_READ_ERROR`, `_smoke_findings` | `doctor_screen.py` |
| 356-1028 | `DoctorScreen` (673) | `doctor_screen.py` |
| 1031-1159 | `_UninstallEntry`, `_STATE_TITLES`, `_REMOVES_CELL_MAX`, `_NOTHING_TO_UNINSTALL`, `_BLOCK_KEY/_TWEAK_KEY/_SETTINGS_KEY/_ENV_KEYS`, `_EnvState`, `config_split`, `_REVIEW_COLUMN`, `_review_line`, `_retired_detail`, `_retired_review_lines` | `uninstall_review.py` |
| 1090-1091 | `_REMOVAL_QUIT_WAIT`, `_REMOVAL_QUIT_CUT` (read only by `UnifiedApp`) | `wizard_app.py` |
| 1162-1177 | `RemovalFinished` | `uninstall_screen.py` |
| 1180-2047 | `UninstallScreen` (868) | `uninstall_screen.py` |
| 2050-2122 | `_LINGER_SENTENCE`, `_competing_line`, `_temp_usage_line` (read only by Schedules) | `schedules_screen.py` |
| 2125-2155 | `_POLICY_READ_ERROR`, `_read_failure`, `_DRIFT_DETAIL`, `_read_active_owned` | `policies_screen.py` |
| 2158-2579 | `PoliciesScreen` (422) | `policies_screen.py` |
| 2582-2603 | `_link_mode_status` (read by PoliciesScreen and UnifiedApp) | `policies_screen.py`, imported by wizard_app as a public name |
| 2606-2643 | schedule constants, `_POLICY_FIXED_COLUMNS`, `_POLICY_EFFECT_FLOOR` (used by PoliciesScreen), `_TIMES_LISTED` (used by Schedules and `ScheduleTimeScreen`) | split: policy columns to `policies_screen`; `_TIMES_LISTED` to `ui_common`; rest to `schedules_screen` |
| 2646-2666 | `_fit` (Policies + Schedules), `_sentence` (Schedules + `CursorModelScreen`), `_tilde` (Schedules) | `_fit`, `_sentence` to `ui_common` (public); `_tilde` to schedules |
| 2669-3199 | `SchedulesScreen` (531) | `schedules_screen.py` |
| 3202-3563 | `ConfirmGuardFile`, `ConfirmUninstall`, `NavScreen`, `LinkModeScreen`, `ScheduleTimeScreen`, `CursorModelsRead`, `CursorModelScreen` | `modals.py` |
| 3566-3674 | `MUTATION_REFUSAL`, `SCHEDULED_RUN_REFUSAL`, `MutationLock` | `mutation_lock.py` |
| 3572-3602 | `ScheduleDefaultsApplied`, `RefreshPublished`, `RefreshFinished` | `wizard_app.py` |
| 3677-4438 | `UnifiedApp` (762) | `wizard_app.py` |

### 3.2 Projection after a verbatim move (script `p25-projection.py`; body + estimated imports + header)

| Module | Projected lines | Over 800? |
|---|---|---|
| `uninstall_review.py` | ~182 | no |
| `ui_common.py` additions | +33 | no (file is ~440) |
| `policies_screen.py` | ~527 | no |
| `schedules_screen.py` | ~758 | no (tight) |
| `modals.py` | ~385 | no |
| `mutation_lock.py` | ~86 | no |
| `doctor_screen.py` | ~829 | **yes (~29)** |
| `wizard_app.py` | ~844 | **yes (~44)** |
| `uninstall_screen.py` | ~964 | **yes (~164)** |

Narrative lines (review IDs and phase/decision references, by destination block): uninstall_screen 26 (2 with WR/CR/IN/RR), wizard_app 30 (7), schedules 13 (2), doctor 10 (7), policies 7 (3), uninstall_review 7, modals 1, mutation_lock 1; file-wide 100 narrative lines and 24 matching `WR|CR|IN|RR-\d+`; the SPEC grep `CR-0|WR-0|IN-0` hits 15 lines of wizard_app.py today. Narrative comments are multi-line, so removing them frees roughly 2-3x the matching line count.

Where the cap is still broken and what to do (pure helpers move to module-level functions in the sibling; widget methods keep their name and behaviour; the private helpers below are referenced only inside the class, verified by grep of `tests/` and `installer/`):
- `UninstallScreen` (868): pure or near-pure methods `_config_clause` (9 lines, 0 self refs), `_block_entry` (16, 0), `_retired_entry` (28, 0), `_accept_summary` (12, 0), `_config_lines` (22, 0) = 87 lines; with explicit args instead of `self` also `_tool_entry` (39), `_unknown_entry` (26), `_tweak_entry` (39), `_settings_entry` (22), `_applied_summary` (36), `_with_failure` (27). Moving the first five saves ~72 (leave call sites), the full family ~200, enough with ~50 lines of narrative cleanup to land ~700 lines. They go to `uninstall_review.py` (which grows to ~400).
- `DoctorScreen` (829 with imports): narrative cleanup alone (~20 lines, `__init__` has 52 comment lines) is borderline; extra candidates `_tui_guidance` :709-737 (29 lines, 2 self refs), `_record_pnpm_evidence` :978-1012 (35, 6), or move the three messages (~44 lines) to a `doctor_messages` sibling.
- `UnifiedApp` module (844): narrative cleanup (`UnifiedApp` has 24 ID lines; `_install_closed` has 51 comment lines, `__init__` 58) should land about 790-800; guaranteed fallback: move `ScheduleDefaultsApplied`/`RefreshPublished`/`RefreshFinished` (27 lines) to an `app_messages.py`.

### 3.3 Cross-module dependencies and private-name renames
- Screens use `if TYPE_CHECKING: @property def app(self) -> "UnifiedApp"` already (wizard_app.py:360, 1193, 2168, 2678). Each split screen needs `if TYPE_CHECKING: from installer.wizard_app import UnifiedApp` (precedent `catalog_tui.py:45-46`, `execute_screen.py:69-70`). No runtime cycle.
- `DoctorScreen` -> `ConfirmGuardFile` (modals); `UninstallScreen` -> `ConfirmUninstall` (modals), `RemovalFinished`, review helpers; `PoliciesScreen` -> `LinkModeScreen` (modals), `fit`; `SchedulesScreen` -> `CursorModelScreen`, `ScheduleTimeScreen` (modals), `fit`, `sentence`, `TIMES_LISTED`; `UnifiedApp` -> all screens, `MutationLock`, `link_mode_status`, the three inputs types.
- **Cross-module `_private` names must become public** (pyright strict `reportPrivateUsage`; do not suppress): `_fit`, `_sentence`, `_TIMES_LISTED`, `_link_mode_status`, and every `_`-name `uninstall_screen` imports from `uninstall_review` (`_UninstallEntry, _STATE_TITLES, _REMOVES_CELL_MAX, _NOTHING_TO_UNINSTALL, _BLOCK_KEY, _TWEAK_KEY, _SETTINGS_KEY, _ENV_KEYS, _EnvState, _retired_detail, _retired_review_lines, _review_line`). The planner may pick names; keep the rename a separate mechanical step noted in the plan.
- `wizard_app.py` keeps importing `MutationHolder` (used by `UnifiedApp`? `MutationLock` is the heavy user and moves to `mutation_lock.py`): `tests/test_schedules_view.py:830, 839` reads `wizard_app.MutationHolder` and `test_setup.py` imports `BASE_VIEW, ExecuteScreen`, `tests/test_wizard_app.py` imports `VIEW_ORDER` from `installer.wizard_app` (re-exports of names wizard_app merely imports). If `wizard_app.py` stops using them, ruff F401 removes the import and those tests fail with ImportError/AttributeError: retarget to `installer.enums`, `installer.ui_common`, `installer.execute_screen` (import-path change).

### 3.4 Importers (AST scan, script `p25-importers.py`) and monkeypatch strings

| File:line | Names imported from `installer.wizard_app` | New home |
|---|---|---|
| `setup.py:110` | `PolicyInputs, ScheduleInputs, UnifiedApp, UninstallInputs` | after LEAN-02 this import moves to `compose.py` (if compose goes first); `PolicyInputs`->policies_screen, `ScheduleInputs`->schedules_screen, `UninstallInputs`->uninstall_review, `UnifiedApp` stays |
| `installer/catalog_tui.py:46`, `installer/execute_screen.py:70` | `UnifiedApp` (TYPE_CHECKING) | unchanged |
| `tests/test_catalog_tui.py:65` | `PolicyInputs, RefreshPublished, UnifiedApp, UninstallInputs` | |
| `tests/test_execute_screen.py:66` | `PolicyInputs, UnifiedApp, UninstallInputs` | |
| `tests/test_layout_80x20.py:49` | `ConfirmUninstall, PoliciesScreen, PolicyInputs, SchedulesScreen, UnifiedApp, UninstallInputs, UninstallScreen` | |
| `tests/test_mutation_runlock.py:23` | `SCHEDULED_RUN_REFUSAL, MutationLock` | mutation_lock |
| `tests/test_policies_e2e.py:27` | `LinkModeScreen, PoliciesScreen, PolicyInputs, UnifiedApp, UninstallInputs` | |
| `tests/test_schedules_handover.py:44` | `SchedulesScreen, UnifiedApp` | |
| `tests/test_schedules_view.py:22, 31` | module `wizard_app`; `CursorModelScreen, PolicyInputs, ScheduleInputs, SchedulesScreen, ScheduleTimeScreen, UnifiedApp, UninstallInputs` | |
| `tests/test_screen_family.py:46` | `DiskPressureProbed, DoctorScreen, GlobalsReinstalled, LinkModeScreen, MutationLock, NavScreen, PolicyInputs, RefreshPublished, ScheduleDefaultsApplied, UnifiedApp, UninstallInputs, UninstallScreen` | |
| `tests/test_setup.py:52, 2211` | `BASE_VIEW, DoctorScreen, ExecuteScreen, PolicyInputs, ScheduleInputs, UnifiedApp, UninstallInputs, UninstallScreen`; `LinkModeScreen` | |
| `tests/test_uninstall_e2e.py:25` | `PolicyInputs, UnifiedApp, UninstallInputs, UninstallScreen` | |
| `tests/test_wizard_app.py:75, 489` | `VIEW_ORDER, CompetingProbe, ConfirmUninstall, DiskPressureProbe, DoctorScreen, LinkModeScreen, MutationLock, NavScreen, PoliciesScreen, PolicyInputs, RefreshPublished, SchedulesScreen, UnifiedApp, UninstallInputs, UninstallScreen, config_split`; `ConfirmGuardFile` | |

No importers in `scripts/` or code docs. Prose-only mentions: `installer/terminal_shell.py:64`, `installer/ui_common.py:3`, `tests/test_ownership.py:1950`, `tests/test_catalog_tui.py:4324` (the last reads `tests/test_wizard_app.py`'s own text; unaffected).

String and `vars()` patch targets that break on a move:
- `tests/test_schedules_view.py:596` `monkeypatch.setitem(vars(wizard_app), "_REFRESH_SECONDS", 0.05)`: **silent break** (setitem never checks the key; the screen would read its own module's 30 s value). Retarget to `vars(schedules_screen)`.
- `tests/test_schedules_view.py:673` `vars(wizard_app)["_SCHEDULE_COLUMNS"]`: loud KeyError; retarget to schedules_screen.
- `tests/test_wizard_app.py:409, 888` `monkeypatch.setattr("installer.wizard_app.path_writer_lines_for", ...)`: still valid (used at `wizard_app.py:3821, 3830`, inside `UnifiedApp`, which stays).
- `tests/test_screen_family.py:2951` `monkeypatch.setattr("installer.wizard_app.move_link_mode", spy_move)`: valid for the path it drives (`UnifiedApp._move_first_link_mode`, `wizard_app.py:4209`). `PoliciesScreen` also calls `move_link_mode` (:2551); a test that drives that path would need `installer.policies_screen.move_link_mode`. Check `tests/test_policies_e2e.py` for patches before the move (none found by `rg "installer.wizard_app"`).
- Textual handler dispatch (`on_globals_audited` etc.) depends on class names, not modules: safe.

### 3.5 Which tests are "the CLI --all/--categories files that stay byte-identical" (SPEC R3)
Files mentioning `"--all"`/`--categories`: `tests/test_setup.py` (29), `tests/test_cli.py` (6), `tests/test_schedules_handover.py` (4), `tests/test_container_e2e_receipts.py` (3), `tests/test_install_sh.py` (1). Only `tests/test_cli.py` and `tests/test_install_sh.py` can stay byte-identical: `test_setup.py` must change for LEAN-02 (patch targets, reload, `_sandbox`) and LEAN-03 (imports), `test_schedules_handover.py` for both, and `tests/test_app.py` (the `run_wizard` side of `--all`/`--categories`, 8 fakes with `confirm_sensitive_action`) changes for D-11. **Conflict to resolve with the owner:** read R3's byte-identical clause as "no assertion line changes" in the CLI tests, enforced by a diff check (`git diff -U0 <before>..HEAD -- tests/` shows no removed `assert` line outside deleted-target tests), plus a literal byte-identical check on `tests/test_cli.py` and `tests/test_install_sh.py`.

## 4. LEAN-04: bounded run log

Write sites (`installer/execute_screen.py`, read this session): the widget is created at :431-436 (`RichLog(id="execute-log", markup=False, highlight=False, auto_scroll=True)`, no `max_lines`); `on_install_log_line` :862 writes the tool header `log.write(f"── {message.tool_id} ──")` :871 and the line `log.write(f"{message.tool_id} │ {cleaned}")` :874; `on_install_run_finished` :904 writes at :939 (captured run report), :943-944 (`PATH wiring` + text), :946, :948-949 (`PATH audit` + text), :951, :953 (`message.run_error`). Ten `log.write` statements, two handlers. CSS (:385, :398-400): `#execute-log { display: none; height: 1fr; padding: 0 1; }`, shown by `.-running`/`.-finished`.

Textual 8.2.7 `RichLog` (`.venv/.../textual/widgets/_rich_log.py`):
- `max_lines` param/var at :61/:71/:99.
- `write()` renders the content to strips and `self.lines.extend(strips)` (:262); a wrapped or multi-line write adds several strips. Trim at :264-267: `if self.max_lines is not None and len(self.lines) > self.max_lines: self._start_line += len(self.lines) - self.max_lines; self.refresh(); self.lines = self.lines[-self.max_lines :]`. So `_start_line` is the cumulative number of dropped rendered lines. [VERIFIED: _rich_log.py:262-267]
- Writes before the first non-zero resize are deferred (`_size_known`, :122-139, :207-215) and replayed in `on_resize`. The log is `display: none` until the run starts, so a counter taken from `len(log.lines)` right after `write()` can lag; `_start_line` stays exact after replay.
- `clear()` resets `_start_line` (:294).

Recommended implementation (ponytail-sized):
- `class RunLog(RichLog)` in `execute_screen.py` with `max_lines=5000` fixed in `__init__` and a `dropped` property returning `self._start_line`. Verified with pyright strict that protected access from a subclass is clean while access from outside errors. [VERIFIED: probe file run this session]
- One method `ExecuteScreen._write_log(*lines: str)` that writes through `RunLog` then refreshes the label from `log.dropped`; the 10 call sites switch to it; `_log_text` in the tests reads `log.lines` and keeps working because the notice is a separate widget.
- Label: `Static("", id="execute-log-dropped")` composed immediately before the `RichLog`, CSS `display: none; height: 1; padding: 0 1;`, class `-dropped` flips `display: block`; text `f"{n} earlier lines dropped"`. There is no existing "log panel" container; a sibling directly above the log is the minimal reading of D-08 and avoids retargeting `#execute-log` CSS. The label costs a row only after the first drop, so the 80x20 layout test is unaffected before 5,000 lines.
- Boundary tests: 5,000 writes -> `dropped == 0`, label hidden; 5,001 -> 1 and "1 earlier lines dropped" (decide singular wording or keep the SPEC's plural copy; SPEC edge R4 says "one dropped line and a notice"); 6,000 -> `len(log.lines) == 5000`, label "1000 earlier lines dropped", last line is the newest. Count unit is rendered strips, so use single-line writes in the test and add one wrapped-write case at a narrow size.
- Existing tests that read the log (`tests/test_execute_screen.py:408-418 _log_text` and ~40 callers) stay green: no content change below 5,000 lines. Re-grep `execute-log` after D-11 (the sensitive tests that read it are deleted).

## 5. Wave order (each commit keeps `make validate && make test` green)

Executor sizing: HAIKU = mechanical/deterministic edit; SONNET = needs judgment.

| Wave | Plan | Scope | Executor |
|---|---|---|---|
| 1 | P25-01 | `tests/test_reachability.py` (entry discovery, graph, seeded-violation case). Passes immediately. | sonnet (small) |
| 1 | P25-02 | D-10 retire host_setup, prod + tests + docs/skill text; `_perform` shape; `update.py` pnpm branch; `model.py:149`; test-sample switches | **sonnet** (judgment on update.py narrowing, test classification) |
| 1 | P25-03 | D-11 production removal + `.claude/architecture.md` + `tests/test_docs.py:98` phrase | sonnet |
| 1 | P25-04 | D-11 test fan-out (50 fakes, deletions listed in 1.2) | haiku (mechanical, run per file with `pytest <file>`) |
| 1 | P25-05 | vulture-60 triage deletions (`requires_integrity_errors`, `run_interactive_command`, `save_manager_snapshot`, `classify_source_line`, `disable_plugins`, `AgentAdapter` fields + `PermissionMode`, `_BodyStatic.renderable`) + summary table of kept targets | haiku |
| 2 | P25-06 | `compose.py` move, import-back, pyright fixes (653, 982), dual-module sandbox (conftest + test_sandbox), `patch_composition` helper, retarget ~125 patch sites, `test_versions` scan, reload tests, `Makefile:35-36` + architecture.md:421/439 | **sonnet** (heavy) |
| 2 (parallel with P25-06, disjoint files) | P25-07 | LEAN-04: `RunLog`, `_write_log`, label, CSS, boundary tests | sonnet (small) |
| 3 | P25-08 | split step 1: `mutation_lock.py`, `modals.py` verbatim + importers | haiku |
| 3 | P25-09 | `ui_common` shared public helpers (rename `_fit/_sentence/_TIMES_LISTED/_link_mode_status`), `policies_screen.py`, `schedules_screen.py` verbatim + importers + the two `vars(wizard_app)` patches | sonnet (renames + silent patch) |
| 3 | P25-10 | `doctor_screen.py`, `uninstall_review.py`/`uninstall_screen.py` verbatim + importers | haiku verbatim; commit the over-cap result only if the cap test is not yet active |
| 4 | P25-11 | comment cleanup + pure-helper extraction until every module <= 800; then land the size + review-ID guard in `test_reachability.py` | **sonnet** (uninstall_screen/doctor/wizard_app) |
| 4 | P25-12 | size report (`git diff --shortstat <before> HEAD -- installer setup.py`, both SHAs), D-04/D-03/D-02 kept-target table in the summary, final `make validate && make test`, CI | haiku |

Why this order: D-10/D-11 first so `confirm_sensitive_action` no longer appears in the code compose inherits and so `execute_screen.py` is stable before P25-07 and the split; compose before the split so `PolicyInputs`/`UnifiedApp` import lines change in one place (`compose.py`) rather than twice; the SPEC ordering edge (move before comment cleanup) is honoured because P25-08..10 are verbatim and P25-11 is the cleanup; the cap/ID guard lands last so verbatim-over-cap intermediate commits stay green. Never both D-10 and D-11 in one plan: they overlap in `engine.py`, `model.py`, `test_engine.py`, `test_model.py`.

Net-line expectation (D-09): LOW confidence estimate, well below the 2,000 of the 2026-10 sizing: roughly -250 (D-10: host_setup.py 56 + ~150 elsewhere + tests excluded), -300 (D-11 incl. `SensitiveActionScreen`), -100 (triage), ~0 for compose/split (moves, plus a few hundred import lines, minus narrative comments). The summary reports whatever the command prints.

## Common Pitfalls

### Pitfall 1: Sandbox guards stop covering moved constants (host safety)
**What goes wrong:** `sandboxed_setup_paths` and `test_no_setup_home_constant_points_at_the_real_home` iterate `setup`'s globals; compose's own bindings keep real-home paths, so `_build_app`-driven tests can read/write the developer's `~/.myshellrc`, `~/.shellrc`, LaunchAgents, `environment.d`.
**Avoid:** generalize both over `("setup", "installer.compose")` in the same commit as the move; run `real_home_untouched`-style fingerprint (the session net already exists).
**Warning signs:** `real_home_untouched` fails at session end; `vars(compose)` has a `Path` under the real HOME.

### Pitfall 2: Patch on `setup` no longer reaches moved code
**What goes wrong:** `monkeypatch.setattr(setup, "_build_services"|"UnifiedApp"|"Console"|...)` is silently ineffective for code that now lives in compose (real services/real UnifiedApp run).
**Avoid:** the dual-module helper; grep each moved name; after the move, temporarily assert in a smoke test that the fake was called.

### Pitfall 3: `vars(module)` `setitem` patches fail silently after the split
`tests/test_schedules_view.py:596`; also check any `setitem(vars(...))` in other test files.

### Pitfall 4: Names re-exported only by accident
`wizard_app.MutationHolder`, `BASE_VIEW`, `VIEW_ORDER`, `ExecuteScreen` are importable from `wizard_app` today only because it imports them; the split can drop them and ruff F401 deletes the import.

### Pitfall 5: `update.py` pnpm branch typing after D-10
After deleting `host_setup_update_argv` the `owner == "pnpm"` apply branch must not pass `Method | None` to `executors.execute`; make the invariant explicit (`UpdateError`) rather than silencing pyright.

### Pitfall 6: docs tests pin architecture paragraphs
`tests/test_docs.py:98` pins "binds the sensitive-action confirmation"; `:587` pins the pi/host_setup wording. Edit docs and tests together, run `tests/test_docs.py` after.

### Pitfall 7: `rg` skips hidden directories
`.claude/architecture.md` and `.claude/skills/tool-onboarding/SKILL.md` mention host_setup/sensitive-action; plain `rg` missed them in the first pass.

## Code Examples

### Reachability graph core (AST, function-level imports included)
```python
# Source: pattern of tests/test_registry.py:2600-2615, scratch p25-reach.py
def _edges(path: Path, mods: set[str]) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        names: set[str] = set()
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{a.name}" for a in node.names)
        elif isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        out |= names & mods
    return out
```

### RunLog with exact dropped count
```python
# Source: .venv textual 8.2.7 widgets/_rich_log.py:262-267; probe verified with pyright strict
class RunLog(RichLog):
    @property
    def dropped(self) -> int:
        return self._start_line  # cumulative rendered lines Textual trimmed
```

## State of the Art

| Old | Current | Impact |
|---|---|---|
| vulture 80 as the dead-code gate | module-reachability test + vulture-60 triage | vulture 80 never reports unused functions (score 60) |
| `host_setup` handoff for pi | bun method + node fallback (24.5) | kind has no user |
| `SENSITIVE_PROMPTS` with entries | empty since 23.2 D-13 | whole path inert |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | compose.py has no strict-mode diagnostics beyond the 5 found at `setup.py:653` and `:982` once its imports resolve in a new file | 2.3 | One extra fix per surprise; run pyright first thing in P25-06 |
| A2 | Projected post-split line counts (~829/844/964) are within about 10 lines of a real verbatim move | 3.2 | Wrong helper-extraction budget; re-measure with `wc -l` after each move |
| A3 | `RichLog._start_line` keeps its meaning across future Textual 8.x | 4 | Counter wrong silently; the 6,000/5,000 test is the pin |
| A4 | The owner accepts "no assertion-line change" in place of literal byte-identical CLI test files (SPEC R3) | 3.5 | A literal reading is unsatisfiable together with D-11/LEAN-02/LEAN-03; needs owner confirmation |
| A5 | Net-line estimate (about -600 to -700) | 5 | Only a report; no gate |
| A6 | `catalog_for`, `status_text`, `recommends_text` are intentional test seams to keep | 1.4 | If the owner wants them gone, 100+ test lines change (assertion-adjacent) |
| A7 | `_BodyStatic.renderable` and `verify_registry.release_tag` are dead | 1.4 | Verify with one targeted run before deleting |

## Open Questions

1. **Byte-identical CLI test files (A4).** Recommendation: enforce "no removed assert lines outside deleted-target tests" plus literal byte-identity for `tests/test_cli.py` and `tests/test_install_sh.py`.
2. **Where do shared screen helpers live?** Recommendation: `ui_common.py` with public names; alternative is a new `screen_shared.py`.
3. **Singular wording of the dropped notice** ("1 earlier lines dropped"): SPEC copy is plural; recommend `1 earlier line dropped` for n == 1 only if the owner accepts the extra branch (UI text change is limited to the notice).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv + .venv | all runs | yes | python 3.12.12 | none needed |
| pytest / xdist / asyncio | tests | yes | per lock | - |
| pyright | LEAN-02 gate | yes | 1.1.410 | - |
| vulture, bandit, ruff | validate | yes | per lock | - |
| textual | LEAN-04 | yes | 8.2.7 | - |
| container runtime | e2e (not required by this phase) | not probed | - | none; real install/uninstall tests are out of scope |

Missing with no fallback: none. Host rules: no `make setup/fix/uninstall/doctor/guard/unguard`, no sudo, no installs; tests use a scratch HOME.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8 + pytest-xdist + pytest-asyncio (`asyncio_mode = "auto"`); Textual `App.run_test` pilot |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]`, `[tool.coverage.*]`, `[tool.pyright]`, `[tool.vulture]` |
| Quick run command | `uv run pytest tests/test_reachability.py tests/test_execute_screen.py -x --no-cov -q` (per-plan: the files named in that plan) |
| Full suite command | `make validate && make test` (`uv run pytest -n auto --cov`, ~6,000 tests; CI uses all CPUs) |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LEAN-01 | no unreachable `installer/` module; seeded orphan detected | unit (AST) | `uv run pytest tests/test_reachability.py --no-cov` | Wave 0 (new) |
| LEAN-01 | `host_setup` rejected as unknown kind; `host-setup` rejected as unknown probe | unit | `uv run pytest tests/test_model.py tests/test_install_ownership.py --no-cov` | exists, edit |
| LEAN-01 | `default_enabled_sensitive_actions` rejected; post-install actions take `(tool, platform)` | unit | `uv run pytest tests/test_post_install.py tests/test_model.py tests/test_engine.py tests/test_session.py --no-cov` | exists, edit |
| LEAN-01 | pnpm-owned `method is None` update refused cleanly | unit | `uv run pytest tests/test_update.py -k pnpm --no-cov` | exists (`:1541`) |
| LEAN-01 | race epoch tests still pass | unit | `uv run pytest tests/test_wizard_app.py tests/test_screen_family.py -k "generation or supersede or epoch or refresh" --no-cov` | exists |
| LEAN-02 | compose passes pyright strict and is in coverage | gate | `uv run pyright installer/compose.py` and `uv run pytest -n auto --cov` report lists `installer/compose.py` | Wave 0 (new file) |
| LEAN-02 | `setup.py` has no `_build_app` definition | unit (AST) | add to `tests/test_reachability.py` or `tests/test_setup.py` | Wave 0 |
| LEAN-02 | sandbox covers compose constants | unit | `uv run pytest tests/test_sandbox.py --no-cov` | exists, extend |
| LEAN-03 | each split module <= 800 lines; no `CR-0|WR-0|IN-0` in them | unit (file scan) | `uv run pytest tests/test_reachability.py -k "size or review_id" --no-cov` | Wave 0 (lands last) |
| LEAN-03 | pilot safety net green at every commit | pilot | `uv run pytest tests/test_layout_80x20.py tests/test_screen_family.py tests/test_wizard_app.py -n auto --no-cov` | exists |
| LEAN-04 | 5,000 writes: no notice; 6,000: 5,000 lines + "1000 earlier lines dropped", newest last | pilot | `uv run pytest tests/test_execute_screen.py -k "dropped or max_lines" --no-cov` | Wave 0 (new tests) |
| R5 | full suite + validate; net lines | gate | `make validate && make test`; `git diff --shortstat <before> HEAD -- installer setup.py` | exists |

### Sampling Rate
- Per task commit: the test files the task edits, with `--no-cov`.
- Per wave merge: `make validate` plus `uv run pytest -n auto --no-cov`.
- Phase gate: `make validate && make test` on the exact tree, then CI green on ubuntu and macOS (push per wave per owner memory).

### Wave 0 Gaps
- [ ] `tests/test_reachability.py`: reachability + seeded orphan + (last) size/review-ID guards.
- [ ] `tests/test_execute_screen.py`: boundary tests for the bounded log.
- [ ] `tests/conftest.py` + `tests/test_sandbox.py`: sandbox generalized to `installer.compose`.
- [ ] a `patch_composition` helper in `tests/` used by `tests/test_setup.py::_sandbox`.
- Framework install: none.

## Security Domain

`security_enforcement` is true (`.planning/config.json:42`). This phase adds no input surface. Applicable controls:

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes (loader) | the closed-kind/closed-field loader keeps rejecting removed kinds/fields; never relax it |
| V14 Configuration | yes | zero sudo rule, host never mutated by tests (sandbox + `real_home_untouched`) |
| V2/V3/V4/V6 | no | not touched |

| Threat | STRIDE | Mitigation |
|--------|--------|------------|
| Test run mutates developer's real shell files after constants move | Tampering | Pitfall 1: generalize the sandbox before running `_build_app` tests |
| A registry row smuggling a removed method kind/probe | Tampering | closed loader sets after D-10/D-11 |
| Unbounded log growth (resource exhaustion) | Denial of service | LEAN-04 `max_lines=5000` |
| Moving code under a new module bypassing bandit | - | bandit already scans all of `installer/`, compose included |

## Project Constraints (from CLAUDE.md / AGENTS.md)
- English only; uv owns the environment (never pip/poetry/conda).
- Never bypass a quality gate: no `# noqa`, `# type: ignore`, `# nosec`, no vulture whitelist, no config relaxation (`.claude/python-tooling.md:22-29`); phase SPEC repeats this as a prohibition.
- Coherent commits; `make validate && make test` on the exact tree before each commit; push main and watch CI after each gate-green wave.
- Never mutate the host: do not run `make setup/fix/uninstall/doctor/guard/unguard` or mutating `systemctl --user`; tests use a scratch HOME; real installs only in disposable containers. Zero sudo.
- `.claude/architecture.md` rules: one view registry, one nav path, one apply workflow, setup.py is wiring only (rule 4), no orphan helpers (rule 5).
- Native agents: gsd-executor runs natively (haiku@high per memory), heavy plans on a sonnet executor; no skill packs/GSD in installer scope.

## Sources

### Primary (HIGH confidence, read or run this session)
- `installer/*.py`, `setup.py`, `tests/*.py`, `.claude/architecture.md`, `Makefile`, `pyproject.toml`, `.github/workflows/ci.yml` at HEAD fc479a0a
- `.venv/lib/python3*/site-packages/textual/widgets/_rich_log.py` (Textual 8.2.7)
- Read-only runs: `uv run vulture installer --min-confidence 60`, `uv run pyright setup.py`, `uv run bandit`/`ruff`/`vulture` on setup.py, `pytest --cov=setup` over 4 test files, pyright strict probe of protected access
- Scratch scripts: `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/p25-*.py`

### Secondary / Tertiary
- None; no web sources needed.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH (no new packages)
- Architecture / inventories: HIGH (AST and rg measured)
- Pitfalls: HIGH for sandbox, patch retargeting, private renames (reproduced or read); MEDIUM for projected line counts
- LEAN-04 helper: HIGH for Textual behaviour, MEDIUM for `_start_line` stability

**Research date:** 2026-11-15
**Valid until:** until the first Phase 25 code commit changes line numbers (re-measure with the scripts); otherwise 30 days.
