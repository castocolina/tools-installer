---
phase: 10-agent-cli-ergonomics
plan: 01
subsystem: infra
tags: [tweaks, shell-alias, policy, codex, opencode, cursor-agent, split-path-mode]

requires:
  - phase: 08-ai-tier-catalog-expansion-uv-tool-executor
    provides: codex/opencode/cursor-agent already present in the AI-tier catalog these tweaks wrap
provides:
  - "installer/tweaks.py: codex-skip, opencode-auto, cursor-agent-model TweakBundle entries in BUNDLES"
  - "installer/policy.py: tweak_policy's split enable/disable reload hints (_TWEAK_ENABLE_HINT/_TWEAK_DISABLE_HINT) and its new ensure_sourced_from parameter, wired to installer.shellrc.ensure_source"
  - "setup.py: _build_app passes ensure_sourced_from under split link mode from BOTH call sites (--guard and the normal no-flags _select_catalog path); main()'s normal branch resolves link_mode once, before run_wizard opens the catalog/Policies TUI"
  - "installer/wizard_app.py: per-bundle Policies detail-panel copy for codex-skip/opencode-auto/cursor-agent-model, plus a uniform ~/.myshellrc-sourcing explanation appended to every tweak:* Policy's detail text"
affects: []

actuals:
  tokens: 5721
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Conditional-injection shell function (cursor-agent-model): unalias-then-function-keyword-define, exact whole-token case match on \"$@\", command-guarded self-calls to avoid recursion — the first tweak bundle in this codebase that inspects argv at call time"
    - "tweak_policy's ensure_sourced_from mirrors ban_policy's own link-mode-aware rc_paths construction at the same setup.py call site, reusing installer.shellrc.ensure_source rather than inventing a second file-writing primitive"

key-files:
  created: []
  modified:
    - installer/tweaks.py
    - installer/policy.py
    - installer/wizard_app.py
    - setup.py
    - tests/test_tweaks.py
    - tests/test_policy_tweaks.py
    - tests/test_wizard_app.py
    - tests/test_setup.py

key-decisions:
  - "codex-skip is a plain alias mirroring claude-skip exactly (alias codex='codex --dangerously-bypass-approvals-and-sandbox'); inserted directly after claude-skip in BUNDLES to group the two full-bypass \"-skip\" tweaks together"
  - "opencode-auto's label is 'opencode auto-approve', never '...skip-permissions' — reusing claude-skip/codex-skip's wording would misrepresent it as a full bypass; both policy.description and the detail panel state explicit deny rules still apply"
  - "cursor-agent-model is one TweakBundle defining both cursor-agent and cursor functions, so the two are always co-installed together, never independently toggleable"
  - "cursor-agent()'s two calls to the real binary always use `command cursor-agent \"$@\"` (never bare) so it cannot recurse into itself; cursor()'s single delegation to cursor-agent is intentionally BARE (never command-prefixed) so it reaches the cursor-agent shell FUNCTION and inherits its injection logic, not the vendor binary directly"
  - "cursor-agent-model's body opens with `unalias cursor-agent cursor 2>/dev/null` before either function is defined (live-verified on bash 3.2.57/zsh 5.9.2: a bare `name() { ... }` colliding with an already-active same-named alias is a hard syntax error in bash and inconsistent in zsh) — the tweak's function deterministically wins over a pre-existing conflicting alias rather than depending on shell-specific undefined behavior"
  - "tweak_policy's reload_hint splits into two distinct constants: _TWEAK_ENABLE_HINT names `source ~/.myshellrc`, _TWEAK_DISABLE_HINT names only a fresh shell (re-sourcing cannot undefine something already loaded) — this fixes the same wrong hash-r-based hint for every existing tweak (docker/countdown/claude-skip/apt-upgrade) too, since tweak_policy is one shared function"
  - "tweak_policy gained an ensure_sourced_from: tuple[Path, ...] = () parameter; when non-empty, apply() calls the existing installer.shellrc.ensure_source primitive on each given path so a tweak enabled under split PATH link mode still reaches a real shell — setup.py's _build_app wires this from BOTH of its call sites (main()'s --guard branch, already link-mode-aware, and _select_catalog, reached from the normal no-flags interactive install), since both build the same UnifiedApp instance whose Policies screen is toggleable mid-session"
  - "main()'s normal (no-flags) branch now resolves link_mode once, BEFORE calling run_wizard, and threads it into _select_catalog via a keyword closure, reusing that one value for the later configure_path call too — a TTY user is asked \"How should PATH be wired?\" exactly once per run, moved earlier because the catalog/Policies TUI's own Policies screen is reachable during tool selection, before the old call site was ever reached"
  - "The 1M-context re-verification finding (CONTEXT.md D-01) is recorded as a dated Python-level comment above _CURSOR_DEFAULT_MODEL, not inside the shell body text, so it is not duplicated verbatim into every enabling user's own ~/.myshellrc"

requirements-completed:
  - REQ-codex-skip-tweak
  - REQ-opencode-auto-tweak
  - REQ-cursor-agent-default-model-wrapper
  - REQ-agent-tweak-self-update-durability

coverage:
  - id: D1
    description: "codex-skip TweakBundle aliases codex to the live-verified --dangerously-bypass-approvals-and-sandbox flag, round-trips through tweak_policy, and its Policies detail panel names the real flag and a trusted-workspace-only caveat"
    requirement: REQ-codex-skip-tweak
    verification:
      - kind: unit
        ref: "tests/test_tweaks.py#test_codex_skip_body_matches_the_verified_flag"
        status: pass
      - kind: unit
        ref: "tests/test_policy_tweaks.py#test_codex_skip_policy_round_trips"
        status: pass
      - kind: automated_ui
        ref: "tests/test_wizard_app.py#test_policy_detail_panel_explains_codex_skip"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every tweak:* Policy (old and new) returns two distinct, accurate reload hints: enable names source ~/.myshellrc, disable names only a fresh shell, neither ever says hash -r; ban_policy's own hash -r hint is untouched"
    verification:
      - kind: unit
        ref: "tests/test_policy_tweaks.py#test_tweak_policy_enable_hint_names_source_not_hash_r"
        status: pass
      - kind: unit
        ref: "tests/test_policy_tweaks.py#test_tweak_policy_disable_hint_names_new_shell_not_source"
        status: pass
    human_judgment: false
  - id: D3
    description: "tweak_policy's ensure_sourced_from wires a given rc path to source ~/.myshellrc, proven with a real fresh-bash-subprocess alias resolution, and setup.py's _build_app passes it under split link mode from BOTH the --guard entry point and the normal no-flags interactive install (main() resolves link_mode once, before run_wizard opens the catalog)"
    requirement: REQ-agent-tweak-self-update-durability
    verification:
      - kind: unit
        ref: "tests/test_policy_tweaks.py#test_tweak_policy_ensure_sourced_from_wires_myshellrc_into_the_given_rc_path"
        status: pass
      - kind: integration
        ref: "tests/test_policy_tweaks.py#test_tweak_policy_split_mode_alias_resolves_in_a_fresh_shell"
        status: pass
      - kind: integration
        ref: "tests/test_setup.py#test_the_policies_view_wires_split_mode_myshellrc_sourcing_for_every_tweak"
        status: pass
      - kind: integration
        ref: "tests/test_setup.py#test_the_normal_interactive_flow_wires_split_mode_myshellrc_sourcing_before_catalog_opens"
        status: pass
    human_judgment: false
  - id: D4
    description: "opencode-auto TweakBundle aliases opencode to opencode --auto; policy.description and the Policies detail panel both state this is narrower than a full bypass (explicit deny rules still apply), never confusable with claude-skip/codex-skip"
    requirement: REQ-opencode-auto-tweak
    verification:
      - kind: unit
        ref: "tests/test_tweaks.py#test_opencode_auto_description_states_it_is_narrower_than_a_full_bypass"
        status: pass
      - kind: unit
        ref: "tests/test_policy_tweaks.py#test_opencode_auto_policy_round_trips"
        status: pass
      - kind: automated_ui
        ref: "tests/test_wizard_app.py#test_policy_detail_panel_explains_opencode_auto_is_narrower_than_a_full_bypass"
        status: pass
    human_judgment: false
  - id: D5
    description: "cursor-agent/cursor default-model wrapper injects --model gpt-5.6-sol-high into a bare invocation, never overrides an explicit --model in either space or equals form, never mistakes a quoted substring for the flag, and cursor delegates to the cursor-agent function (inheriting injection) rather than the vendor binary directly"
    requirement: REQ-cursor-agent-default-model-wrapper
    verification:
      - kind: integration
        ref: "tests/test_tweaks.py#test_cursor_agent_model_injects_default_when_no_model_flag"
        status: pass
      - kind: integration
        ref: "tests/test_tweaks.py#test_cursor_agent_model_respects_explicit_space_form_model_flag"
        status: pass
      - kind: integration
        ref: "tests/test_tweaks.py#test_cursor_agent_model_respects_explicit_equals_form_model_flag"
        status: pass
      - kind: integration
        ref: "tests/test_tweaks.py#test_cursor_delegates_to_cursor_agent_function_and_inherits_injection"
        status: pass
      - kind: integration
        ref: "tests/test_tweaks.py#test_cursor_agent_does_not_mistake_a_quoted_substring_for_the_flag"
        status: pass
      - kind: unit
        ref: "tests/test_tweaks.py#test_cursor_agent_model_body_declares_the_correct_command_guard_invariant"
        status: pass
      - kind: integration
        ref: "tests/test_tweaks.py#test_cursor_agent_model_behavior_under_zsh_when_available"
        status: pass
    human_judgment: false
  - id: D6
    description: "A pre-existing alias named cursor-agent or cursor, active before the tweak block loads, is actively removed (not merely shadowed) by the leading unalias guard, live-verified against real bash and zsh subprocesses, with a bounded timeout converting a self-recursion regression into a diagnosable AssertionError"
    verification:
      - kind: integration
        ref: "tests/test_tweaks.py#test_cursor_agent_wrapper_removes_a_pre_existing_conflicting_alias"
        status: pass
      - kind: integration
        ref: "tests/test_tweaks.py#test_cursor_agent_wrapper_removes_a_pre_existing_conflicting_alias_under_zsh"
        status: pass
      - kind: unit
        ref: "tests/test_policy_tweaks.py#test_cursor_agent_model_policy_round_trips"
        status: pass
      - kind: automated_ui
        ref: "tests/test_wizard_app.py#test_policy_detail_panel_explains_cursor_agent_model_wrapper"
        status: pass
    human_judgment: false
  - id: D7
    description: "All three new tweaks are shell alias/function TweakBundle entries with requires=()/executables=() — no file-based shim — so each survives the target CLI's own self-update in place, exactly like the existing bundles"
    requirement: REQ-agent-tweak-self-update-durability
    verification:
      - kind: unit
        ref: "tests/test_tweaks.py#test_bundles_have_stable_ids_and_order"
        status: pass
    human_judgment: false

duration: ~25min
completed: 2026-09-06
status: complete
---

# Phase 10 Plan 01: Agent CLI ergonomics tweaks Summary

**codex-skip, opencode-auto, and a cursor-agent/cursor default-model wrapper added to the existing TweakBundle/Policy mechanism, plus a real split-PATH-mode fix so every tweak (old and new) actually reaches a real shell under every supported link mode**

## Performance

- **Duration:** ~25 min
- **Completed:** 2026-09-06
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments
- `codex-skip` (Task 1, this plan's tracer): aliases `codex` to the live-verified `--dangerously-bypass-approvals-and-sandbox` flag, mirroring `claude-skip` exactly, and proved the phase's "zero new plumbing" thesis end to end (bundle → Policy → Policies detail panel → marker-block mechanism).
- Fixed a real, pre-existing bug found during Task 1: `tweak_policy`'s reload hint told every user to run `hash -r` after enabling/disabling an alias or shell function, which does nothing for a freshly written alias/function (only `ban_policy`'s PATH shims actually need `hash -r`). Split into `_TWEAK_ENABLE_HINT` (names `source ~/.myshellrc`) and `_TWEAK_DISABLE_HINT` (names only a fresh shell), fixing the hint for `docker`/`countdown`/`claude-skip`/`apt-upgrade` too, for free.
- Fixed a real, pre-existing bug found during Task 1: every `tweak:*` Policy was constructed with `rc_path=_MYSHELLRC` unconditionally, so under split PATH link mode (where `~/.myshellrc` is never sourced) an enabled tweak's block was written but never reached by the shell. `tweak_policy` gained `ensure_sourced_from`, wired from **both** of `setup.py`'s `_build_app` call sites — `main()`'s `--guard` branch and `_select_catalog` (reached from the normal, no-flags interactive install) — so a tweak toggled from either entry point under split mode now wires `source ~/.myshellrc` into the split rc files automatically.
- `opencode-auto` (Task 2): aliases `opencode` to `opencode --auto`, with `policy.description` and the Policies detail panel both stating explicitly that this is narrower than `claude-skip`/`codex-skip`'s full bypass — explicit deny rules still apply.
- `cursor-agent`/`cursor` default-model wrapper (Task 3): the first tweak bundle in this codebase that inspects `"$@"` at call time. Injects `--model gpt-5.6-sol-high` into a bare `cursor-agent`/`cursor` call, never overrides an explicit `--model` (space or equals form), and never mistakes a quoted substring containing `--model` for the real flag. Opens with `unalias cursor-agent cursor 2>/dev/null` so a pre-existing conflicting alias is actively removed (live-verified against bash 3.2 and zsh 5.9), and both of `cursor-agent()`'s own calls to the real binary go through `command cursor-agent "$@"` so it can never recurse into itself, while `cursor()`'s single bare delegation to the `cursor-agent` function is exactly how `cursor` inherits the same injection logic.
- `installer/uninstall.py` needed zero edits, confirming the phase's "zero new plumbing" thesis for bundle registration: `setup.py`'s `applicable_bundles(platform)` → `tweak_policy(bundle, ...)` loop and the uninstall sweep already iterate over any `BUNDLES` tuple generically.

## Task Commits

Each task was committed atomically (all three tasks used TDD — RED tests confirmed failing before implementation, then GREEN):

1. **Task 1: End-to-end codex-skip tweak, reload-hint split, and split-link-mode sourcing fix** - `eb86c96` (feat)
2. **Task 2: opencode-auto tweak with honestly narrower Policies copy** - `74c2b37` (feat)
3. **Task 3: cursor-agent/cursor default-model wrapper** - `8821242` (feat)

_All three tasks were single-commit `feat` commits: each task's tests and implementation landed together after the RED/GREEN cycle was manually verified (failing tests confirmed via `rtk proxy uv run pytest`, then made to pass), rather than as separate `test(...)`/`feat(...)` commits._

## Files Created/Modified
- `installer/tweaks.py` - `_CODEX_BODY`/`_OPENCODE_BODY`/`_CURSOR_AGENT_BODY` constants and their three new `TweakBundle` entries in `BUNDLES`
- `installer/policy.py` - `_TWEAK_ENABLE_HINT`/`_TWEAK_DISABLE_HINT`, `tweak_policy`'s new `ensure_sourced_from` parameter and its `installer.shellrc.ensure_source` wiring
- `installer/wizard_app.py` - three new `_policy_detail` entries plus a uniform `~/.myshellrc`-sourcing explanation appended to every `tweak:*` Policy's detail text
- `setup.py` - `_build_app` wires `ensure_sourced_from` under split link mode at both call sites; `_select_catalog` gained a `link_mode` keyword; `main()`'s normal branch resolves `link_mode` once, before `run_wizard`
- `tests/test_tweaks.py` - new bundle-body/description tests, the `_run_cursor_agent` subprocess helper, and the cursor-agent-model behavior/structural/collision/zsh test suite
- `tests/test_policy_tweaks.py` - round-trip tests for all three new bundles, the enable/disable hint split tests, and the `ensure_sourced_from`/fresh-shell tests
- `tests/test_wizard_app.py` - detail-panel tests for all three new Policy ids and the uniform sourcing-explanation test
- `tests/test_setup.py` - split-mode wiring tests for both `_build_app` call sites, and a `_resolve_link_mode` stub added to the pre-existing `test_build_app_hands_unavailable_from_platform_could_support` (now reached earlier in `main()`'s control flow)

## Decisions Made
See `key-decisions` in frontmatter above — all decisions were pre-specified by the plan's `<design_decisions>` section (itself the product of three cross-AI review cycles) and implemented as written; no new architectural decisions were made during execution.

## Deviations from Plan

None — plan executed exactly as written. Every task's tests, implementation, and verification matched the plan's `<behavior>`/`<action>`/`<verify>` blocks; no Rule 1-4 auto-fixes were needed beyond what the plan itself already specified as the fix (the reload-hint split and the split-mode `ensure_sourced_from` wiring were themselves the plan's Task 1 deliverables, not deviations discovered during execution).

One small implementation adjustment made while writing tests (not a deviation from behavior, only from exact wording): the `tweak:cursor-agent-model` Policies detail-panel copy originally drafted the "requests" sentence capitalized at the start of a sentence ("Requests, per Cursor's own..."), which the plan's own `test_policy_detail_panel_explains_cursor_agent_model_wrapper` (asserting a case-sensitive substring `"requests"`) caught as a RED failure; reworded to `"This tweak only requests, per Cursor's own..."` so the lowercase substring is present, preserving the exact same meaning the plan specified.

## Issues Encountered

The agent's worktree branch (`worktree-agent-a8ac185ac0e1d35ca`) was found at commit `581c097` (the tip of `feat/tui-interaction-consistency`) rather than `gsd/phase-10-agent-cli-ergonomics`'s tip (`9312bf9`) at the start of execution — `581c097` is an ancestor of `9312bf9`, so a `git merge --ff-only 9312bf9` fast-forwarded the worktree cleanly with no conflicts before any plan work began, per the orchestrator's own pre-flight instruction that this has happened in prior phases of this run.

## Next Phase Readiness
- Phase 10's ROADMAP success criteria SC#1-SC#4 are all met: `codex-skip`, `opencode-auto`, and the `cursor-agent`/`cursor` wrapper are live in `BUNDLES`, each survives the target CLI's own self-update (pure alias/function, no file-based shim), and — per this plan's real split-mode fix — actually reach a real shell under centralized, single, AND split PATH link modes, through both `tools-installer --guard` and the plain, no-flags interactive install.
- `make validate && make test` is green on the final committed tree (1326 tests, 99.41% coverage).
- No blockers for closing this phase; the phase's own `<verification>` block (bundle order, grep counts, claude-skip's corrected reload hint, `ensure_sourced_from` wiring, and the normal-interactive-flow split-mode test) was independently re-run and passes.

---
*Phase: 10-agent-cli-ergonomics*
*Completed: 2026-09-06*

## Self-Check: PASSED

- All 8 modified files confirmed present on disk (`installer/tweaks.py`, `installer/policy.py`, `installer/wizard_app.py`, `setup.py`, `tests/test_tweaks.py`, `tests/test_policy_tweaks.py`, `tests/test_wizard_app.py`, `tests/test_setup.py`), plus this SUMMARY.md.
- All 3 task commit hashes confirmed present in `git log --oneline --all`: `eb86c96`, `74c2b37`, `8821242`.
