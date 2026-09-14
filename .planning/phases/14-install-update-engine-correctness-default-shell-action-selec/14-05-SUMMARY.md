---
phase: 14-install-update-engine-correctness-default-shell-action-selec
plan: "05"
subsystem: post-install
tags: [set_login_shell, execute-screen, ask_from_worker, with_sensitive_confirm, architecture, D-05]

requires:
  - phase: 14-install-update-engine-correctness-default-shell-action-selec
    provides: SensitiveInstall, with_sensitive_confirm, render_post_install_handoff, closed POST_INSTALL_HOOKS, UpdateService batch dispatch
provides:
  - In-app SensitiveActionScreen bound through ask_from_worker onto the install seam
  - Reviewed post-install instructions in the in-app post-run log, matching console renderer order
  - Phase 14 architecture section held by tests/test_docs.py, with the stale plural-field clause corrected in place
affects:
  - phase verification (both reported bugs closed on the production path)

actuals:
  tokens: 9647
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Reuse ask_from_worker for a second ModalScreen[str | None]; convert the string answer to bool inside the ask method"
    - "One PromptOpen message for every worker-blocked question"
    - "Architecture facts locked by a required-phrase tuple, never a test-count assertion"

key-files:
  created: []
  modified:
    - installer/execute_screen.py
    - tests/test_execute_screen.py
    - tests/test_wizard_app.py
    - .claude/architecture.md
    - tests/test_docs.py

key-decisions:
  - "The in-app prompt uses the one recorded worker-to-modal mechanism; the helper's signature is unchanged"
  - "The prompt says the installer will show a reviewed command the user runs themselves, matching the console question"
  - "Unattended means no callback, proved by driving the real screen, not by a source-order assertion"
  - "A dismissed prompt is a no, and the log says so"
  - "The stale architecture clause at the singular-versus-plural paragraph is rewritten in place, not contradicted from a distance"

patterns-established:
  - "Parameterise a new modal the way ChecksumMismatchScreen is parameterised; map to the callback's type in the ask method"
  - "Extend the existing wizard-order report test rather than adding a presence-only sibling"
  - "Phase N required-phrase tuples in test_docs.py never assert how many phases the file covers"

requirements-completed: ["D-01", "D-03", "D-04", "D-05", "D-06"]

coverage:
  - id: D1
    description: A sensitive post-install action opens one in-app prompt through ask_from_worker, naming the tool and describing a reviewed command the user runs themselves
    requirement: D-05
    verification:
      - kind: unit
        ref: tests/test_execute_screen.py#test_sensitive_action_screen_names_the_tool_and_the_reviewed_command
        status: pass
      - kind: other
        ref: "python -c WIRE-OK/HELPER-UNCHANGED and awaited-modal count from 14-05 Task 1"
        status: pass
    human_judgment: false
  - id: D2
    description: Selecting the affirmative option returns true to the install seam; selecting no returns false
    requirement: D-05
    verification:
      - kind: unit
        ref: tests/test_execute_screen.py#test_accepting_the_login_shell_prompt_returns_true_to_the_install_seam
        status: pass
      - kind: unit
        ref: tests/test_execute_screen.py#test_refusing_the_login_shell_prompt_returns_false_to_the_install_seam
        status: pass
    human_judgment: false
  - id: D3
    description: Escaping the modal returns false and writes an explanatory attributed line
    requirement: D-05
    verification:
      - kind: unit
        ref: tests/test_execute_screen.py#test_escaping_the_login_shell_prompt_returns_false_and_explains
        status: pass
    human_judgment: false
  - id: D4
    description: With the unattended flag set the modal never opens and the confirmation passed to the binding is absent
    requirement: D-05
    verification:
      - kind: unit
        ref: tests/test_execute_screen.py#test_sensitive_unattended_never_opens_the_modal_and_passes_no_confirmation
        status: pass
    human_judgment: false
  - id: D5
    description: While the modal is open, cancel stays inert and the status line names the waiting prompt
    requirement: D-05
    verification:
      - kind: unit
        ref: tests/test_execute_screen.py#test_cancel_is_inert_while_the_sensitive_prompt_is_open
        status: pass
    human_judgment: false
  - id: D6
    description: Reviewed instructions appear in the in-app post-run log after the manual-required handoff, sanitised, matching the console renderer order
    requirement: D-06
    verification:
      - kind: unit
        ref: tests/test_execute_screen.py#test_post_run_log_carries_every_renderer_in_wizard_order
        status: pass
      - kind: other
        ref: "python -c ORDER-MATCHES from 14-05 Task 2"
        status: pass
    human_judgment: false
  - id: D7
    description: Architecture records both Phase 14 mechanisms, the stale plural-field clause is corrected in place, and a phrase tuple holds the facts with no count assertion
    requirement: D-04
    verification:
      - kind: unit
        ref: tests/test_docs.py#test_architecture_records_phase_14_mechanisms
        status: pass
      - kind: other
        ref: "python -c DOCS-OK and grep -c 'zero production callers as of Phase 12.4' -eq 0 from 14-05 Task 3"
        status: pass
    human_judgment: false

duration: 21 min
completed: 2026-09-14
status: complete
---

# Phase 14 Plan 05: In-App Sensitive Prompt and Architecture Record Summary

**The production `make setup` path now asks inside the app before proposing a login-shell change, prints the reviewed `chsh` command in the post-run log, and records both of this phase's mechanisms in `.claude/architecture.md` behind a test.**

## Performance

- **Duration:** 21 min
- **Started:** 2026-09-14T17:40:49Z
- **Completed:** 2026-09-14T18:01:34Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- `SensitiveActionScreen` asks through the single recorded `ask_from_worker` helper, names the tool, and says the installer will show a reviewed command the user runs themselves — not that the installer changes the login shell.
- Yes, no, escape, and unattended all resolve correctly: yes binds true; no, escape, and `--yes` produce nothing; escape writes an attributed explanation; cancel stays inert while the prompt is open.
- `render_post_install_handoff` is in the in-app `render_report` closure in the same relative position as the console report, inheriting the captured-console sanitiser.
- `.claude/architecture.md` records the install/update split, the disjoint post-install tables, the immutable block behind ublue-os/bazzite#4159, the reviewed-handoff doctrine, and the composition-point adapter; the stale "zero production callers as of Phase 12.4" clause is gone.

## Task Commits

1. **Task 1: the in-app sensitive-action prompt, bound onto the install seam** - `126d596` (feat)
2. **Task 2: the reviewed instructions reach the post-run log** - `254203e` (feat)
3. **Task 3: record both mechanisms in the architecture standard, behind a test** - `4b9c901` (docs)

## Files Created/Modified

- `installer/execute_screen.py` - `SensitiveActionScreen`, `_ask_sensitive_action`, `PromptOpen`, `with_sensitive_confirm` binding, `render_post_install_handoff` in the report
- `tests/test_execute_screen.py` - prompt, unattended, cancel, and wizard-order report pilots; eleven install fakes widened
- `tests/test_wizard_app.py` - two `ExecuteInputs` fake installs widened
- `.claude/architecture.md` - Phase 14 section; singular-versus-plural paragraph and 12.4 audit note corrected in place
- `tests/test_docs.py` - `_PHASE_14_REQUIRED` and `test_architecture_records_phase_14_mechanisms`

## Decisions Made

- **One worker-to-modal mechanism.** The new screen is `ModalScreen[str | None]` like the mismatch prompt; `"yes"`/`"no"`/`None` convert to bool inside `_ask_sensitive_action`. The helper's signature is byte-identical.
- **One prompt-open message.** `PromptOpen` / `on_prompt_open` replaced the mismatch-specific names; both prompts share `_waiting_prompt`.
- **Unattended is behavioural.** `--yes` passes `None` as the confirmation, proved by driving the real screen (`test_sensitive_unattended_...`), not by a source-order comparison that the pre-existing mismatch line already satisfied.
- **Dismissed is a no, and it says so.** Escape resolves false and writes an attributed line naming the tool.
- **Attribution stays outermost.** `attributed_install(runner, with_sensitive_confirm(...), on_outcome)` so every call still carries the tool id.
- **Architecture is edited, not appended-beside.** The paragraph that told readers the plural field had no production caller now says `installer/post_install.py` reads it at the post-success point of the install ladder.

## Deviations from Plan

Task 3 also rewrote the Phase 12.4 audit paragraph that still described the plural field as a dead-code finding, so a reader hitting that historical note would not be told it still has no caller. The plan named only the 337-341 clause; the extra edit stays inside `.claude/architecture.md` and keeps the surrounding warning.

A ruff format wrap on the Task 2 wizard-order constructor call was folded into that task's commit rather than left as a follow-up.

**Total deviations:** 2 auto-fixed (1 stale-clause completeness, 1 format).
**Impact on plan:** Both keep the canonical doc and the committed tree coherent. No scope creep.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Both reported bugs are closed on the path the reports describe: selecting an outdated tool and pressing enter updates it or says why it will not, and installing `oh-my-zsh` on a non-immutable host asks once, in the app, before offering reviewed login-shell instructions.
- Phase 14 is the last plan in this phase; ready for phase verification.
- Catalog Ver-column staleness after `ExecuteScreen` pop remains the documented 14-02 follow-up.

## Verification

- `uv run pytest tests/test_execute_screen.py tests/test_wizard_app.py tests/test_docs.py -q` green.
- `uv run pytest tests/test_execute_screen.py -k 'outdated or confirm or blocked_update or sensitive' -q` selected tests and passed.
- `uv run pytest tests/test_execute_screen.py -k sensitive_unattended -q` selected 1 test and passed.
- `make validate` exits 0.
- `make test` exits 0: 2072 passed, 1 skipped, coverage 95.36%.
- `git diff --stat` of this plan's commits lists only the five declared files.

## Self-Check: PASSED

---
*Phase: 14-install-update-engine-correctness-default-shell-action-selec*
*Completed: 2026-09-14*
