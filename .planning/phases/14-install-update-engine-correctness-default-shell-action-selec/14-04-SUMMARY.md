---
phase: 14-install-update-engine-correctness-default-shell-action-selec
plan: "04"
subsystem: post-install
tags: [set_login_shell, confirm, render_post_install_handoff, with_sensitive_confirm, run_wizard, D-05]

requires:
  - phase: 14-install-update-engine-correctness-default-shell-action-selec
    provides: InstallOutcome.post_install_handoff, install_tool confirm_sensitive_action, closed POST_INSTALL_HOOKS
provides:
  - render_post_install_handoff for reviewed successful-install instructions
  - SensitiveInstall protocol and with_sensitive_confirm adapter
  - run_wizard confirmation binding, unattended skip, and report rendering
affects:
  - 14-05 (in-TUI confirm binding through with_sensitive_confirm)

actuals:
  tokens: 4666
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Bind a keyword-only confirmation at a composition point rather than widening the shared Install protocol"
    - "A successful-install instruction renderer is a sibling of render_handoff, not an extension of it"
    - "Instruction lines print with markup=False so reviewed shell syntax survives"

key-files:
  created: []
  modified:
    - installer/render.py
    - installer/session.py
    - installer/app.py
    - tests/test_render.py
    - tests/test_session.py
    - tests/test_app.py

key-decisions:
  - "The shared Install protocol does not change; SensitiveInstall plus with_sensitive_confirm bind at a composition point"
  - "run_wizard builds its confirmation from the prompter it already holds; setup.py is untouched"
  - "--yes means no callback, which means skip, mirroring the checksum-mismatch unattended rule"
  - "The sensitive question names the tool and says the user runs a reviewed command themselves"
  - "render_post_install_handoff is a new renderer; it copies render_handoff's structure and disables markup on instruction lines"

patterns-established:
  - "Wider protocol + adapter returns the original Install so existing fakes and attributed_install stay valid"
  - "FakePrompter is extended additively: new answers are keyword-with-default, confirmed still counts every question"
  - "Unattended skip is a behavioural test (sensitive_unattended), never a source-order assertion"

requirements-completed: ["D-05", "D-06"]

coverage:
  - id: D1
    description: Reviewed post-install instructions print for a successful install, stay silent otherwise, and square brackets survive as literal text
    requirement: D-06
    verification:
      - kind: unit
        ref: tests/test_render.py#test_render_post_install_handoff_prints_heading_and_instruction_lines
        status: pass
      - kind: unit
        ref: tests/test_render.py#test_render_post_install_handoff_is_silent_for_empty_instruction_tuple
        status: pass
      - kind: unit
        ref: tests/test_render.py#test_render_post_install_handoff_preserves_bracketed_instruction_text
        status: pass
      - kind: other
        ref: "python -c RENDER-OK from 14-04 Task 1"
        status: pass
    human_judgment: false
  - id: D2
    description: A confirmation binds onto install_tool through with_sensitive_confirm without widening the shared Install protocol
    requirement: D-05
    verification:
      - kind: unit
        ref: tests/test_session.py#test_with_sensitive_confirm_reaches_post_install_gate
        status: pass
      - kind: unit
        ref: tests/test_session.py#test_install_protocol_parameters_are_unchanged
        status: pass
      - kind: other
        ref: "python -c PROTOCOL-UNCHANGED/BIND-OK from 14-04 Task 2"
        status: pass
    human_judgment: false
  - id: D3
    description: Console run_wizard asks a distinct tool-naming question, skips it under --yes, and prints the resulting reviewed instructions
    requirement: D-05
    verification:
      - kind: unit
        ref: tests/test_app.py#test_run_wizard_prints_login_shell_instructions_when_sensitive_confirmed
        status: pass
      - kind: unit
        ref: tests/test_app.py#test_run_wizard_skips_login_shell_instructions_when_sensitive_refused
        status: pass
      - kind: unit
        ref: tests/test_app.py#test_run_wizard_sensitive_unattended_never_asks_and_prints_no_instructions
        status: pass
      - kind: other
        ref: "pytest -k 'login_shell or sensitive' and -k sensitive_unattended from 14-04 Task 3"
        status: pass
    human_judgment: false

duration: 20 min
completed: 2026-09-14
status: complete
---

# Phase 14 Plan 04: Console Confirm Binding and Post-Install Renderer Summary

**Console install path asks a distinct, truthful login-shell question, skips it when unattended, binds the answer without widening `Install`, and prints the reviewed `chsh` instructions a successful install produced.**

## Performance

- **Duration:** 20 min
- **Started:** 2026-09-14T16:31:37Z
- **Completed:** 2026-09-14T16:51:29Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- `render_post_install_handoff` prints reviewed follow-up steps for a tool that installed, stays silent otherwise, and disables rich markup on instruction lines so bracketed shell text survives.
- `SensitiveInstall` plus `with_sensitive_confirm` bind `confirm_sensitive_action` at a composition point; the shared `Install` protocol and `run_installs` are unchanged.
- `run_wizard` asks a tool-naming question that says the user runs the command themselves, binds `None` under `--yes`, and joins the new renderer after `render_handoff`.
- `setup.py` is untouched.

## Task Commits

1. **Task 1: render the reviewed post-install instructions** - `077e1e5` (feat)
2. **Task 2: bind a sensitive-action confirmation without widening the shared Install protocol** - `ac30c95` (feat)
3. **Task 3: the console entry point asks, binds, and prints (D-05)** - `5bf5e88` (feat)

## Files Created/Modified

- `installer/render.py` - `render_post_install_handoff` with markup disabled on instruction lines
- `installer/session.py` - `SensitiveInstall` protocol and `with_sensitive_confirm` adapter
- `installer/app.py` - `run_wizard` confirmation closure, adapter binding, and report renderer
- `tests/test_render.py` - renderer silence, order, installed-outcome, and bracket-survival cases
- `tests/test_session.py` - adapter gate, kwargs-forwarding, `None` binding, protocol-unchanged
- `tests/test_app.py` - additive `FakePrompter`, six fakes widened, confirming/refusing/unattended/no-action cases

## Decisions Made

- **Protocol stays byte-identical.** Binding happens above `run_installs` so 29 existing fake installs and `attributed_install` need no edit.
- **Confirmation lives in `installer/`.** `run_wizard` builds it from the prompter it already holds; the composition root gains nothing.
- **`--yes` is skip.** The confirmation closure is `None` when unattended, the same rule the checksum-mismatch prompt already uses.
- **The question tells the truth.** Yes shows a reviewed command the user runs after exit; it does not claim the installer changes the login shell.
- **New renderer, not a widened sibling.** `render_handoff` is for tools that did not install; this one is for tools that did, and it is the only body print in the file that turns markup off.

## Deviations from Plan

Task 3's commit also includes typed `is_installed`/`resolve_tag` stubs in `tests/test_session.py` so pyright stays green on the Task 2 tests. No production-code change beyond the plan.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Ready for 14-05: the in-TUI execute path is the second `with_sensitive_confirm` caller.
- `setup.py` and `installer/execute_screen.py` are untouched, as required.

## Verification

- `uv run pytest tests/test_app.py tests/test_session.py tests/test_render.py tests/test_engine.py tests/test_post_install.py -q` green.
- `make validate` exits 0; vulture reports no unused code for the new protocol, adapter, or renderer.
- `make test` / `uv run pytest --cov -q`: 2065 passed, 1 skipped, coverage 95.38%.
- `git diff --stat 077e1e5^..HEAD` lists only the six declared files.

## Self-Check: PASSED

---
*Phase: 14-install-update-engine-correctness-default-shell-action-selec*
*Completed: 2026-09-14*
