---
phase: 03-install-uninstall-tweak-lifecycle-hardening
plan: 02
subsystem: shell-tweaks
tags: [oh-my-zsh, zshrc, policies, plugins]

requires:
  - phase: 03-install-uninstall-tweak-lifecycle-hardening
    provides: PoliciesScreen run_live Policy factory pattern
provides:
  - installer/omz.py single-line plugins=(...) editor
  - omz_plugins_policy presence-gated Policy
  - Policies row for bundled git/docker plugins
affects:
  - 03-03 symmetric uninstall teardown (consumes omz_plugins_policy)

actuals:
  tokens: 7800
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - third Policy factory parallel to ban_policy/tweak_policy
    - in-place single-line array edit of a user-owned rc file
    - OmzPluginsError(OSError) so run_live surfaces refusals

key-files:
  created:
    - installer/omz.py
    - tests/test_omz.py
    - tests/test_policy_omz.py
  modified:
    - installer/policy.py
    - installer/wizard_app.py
    - setup.py
    - tests/test_policies_e2e.py
    - tests/test_setup.py

key-decisions:
  - "D-02: in-place line edit, not apply_block/strip_block; .zshrc is user-owned"
  - "Third Policy factory, not a TweakBundle and not a new TweakBundle field"
  - "OmzPluginsError subclasses OSError so run_live surfaces it with no new except"
  - "Enable raises on a missing array; disable never does"
  - "plugins_enabled requires ALL managed names; partial state is disclosed, not designed away"
  - "Policies detail panel height 7 so the four-line omz-plugins disclosure is visible"

patterns-established:
  - "Policy factory for a non-block, non-catalog mutation (omz_plugins_policy)"
  - "User-owned file edits stay in a standalone import-free module"

requirements-completed:
  - REQ-oh-my-zsh-plugin-config

coverage:
  - id: D1
    description: "Toggling Oh-My-Zsh plugins in Policies edits plugins=(...) in .zshrc in place, no catalog entry"
    requirement: REQ-oh-my-zsh-plugin-config
    verification:
      - kind: e2e
        ref: tests/test_policies_e2e.py#test_policies_screen_toggles_omz_plugins_live
        status: pass
      - kind: unit
        ref: tests/test_omz.py#test_enable_adds_only_the_missing_names_and_preserves_the_rest
        status: pass
      - kind: other
        ref: "uv run python3 -c load_tools; assert oh-my-zsh not in registry"
        status: pass
    human_judgment: false
  - id: D2
    description: "Editor preserves every other plugin and every other line; refuses multi-line/missing/commented arrays"
    requirement: REQ-oh-my-zsh-plugin-config
    verification:
      - kind: unit
        ref: tests/test_omz.py#test_multi_line_array_is_refused_not_parsed
        status: pass
      - kind: unit
        ref: tests/test_omz.py#test_last_matching_line_wins
        status: pass
      - kind: unit
        ref: tests/test_omz.py#test_indentation_and_trailing_comment_are_preserved
        status: pass
    human_judgment: false
  - id: D3
    description: "Policy gates on omz_present via existing requires/missing_requires UX; unusable .zshrc stays OFF"
    requirement: REQ-oh-my-zsh-plugin-config
    verification:
      - kind: e2e
        ref: tests/test_policies_e2e.py#test_policies_screen_refuses_omz_toggle_without_oh_my_zsh
        status: pass
      - kind: e2e
        ref: tests/test_policies_e2e.py#test_policies_screen_surfaces_an_unusable_zshrc_as_an_error
        status: pass
      - kind: unit
        ref: tests/test_policy_omz.py#test_apply_on_a_zshrc_without_an_array_raises_os_error
        status: pass
    human_judgment: false
  - id: D4
    description: "Detail panel discloses toggle-off and partial-state reading (Reads ON only when)"
    requirement: REQ-oh-my-zsh-plugin-config
    verification:
      - kind: e2e
        ref: tests/test_policies_e2e.py#test_policy_detail_discloses_the_partial_state_reading
        status: pass
      - kind: automated_ui
        ref: "tmux capture-pane Policies row + Disabling removes + Reads ON only when"
        status: pass
    human_judgment: false
  - id: D5
    description: "Proved against a real upstream Oh-My-Zsh install in a disposable container"
    requirement: REQ-oh-my-zsh-plugin-config
    verification:
      - kind: other
        ref: "docker run alpine + official oh-my-zsh installer; added=('docker',); plugins=(git docker); zsh -i alias gst"
        status: pass
    human_judgment: false

duration: 18min
completed: 2026-09-05
status: complete
---

# Phase 3 Plan 02: Oh-My-Zsh Plugins Policy Summary

**In-place single-line `plugins=(...)` editor plus a presence-gated Policies toggle for Oh-My-Zsh's bundled git and docker plugins, with no catalog entry and no marker block in `.zshrc`.**

Toggling the Oh-My-Zsh plugins policy ON in the Policies view edits the existing `plugins=(...)` line in the user's `.zshrc`, adding `git` and `docker` only when absent and preserving every other plugin and every other line. Toggling OFF removes only those two names. There is no `Tool` row; `installer/omz.py` is a standalone editor, not `apply_block`/`strip_block`. A missing or multi-line array raises `OmzPluginsError` (an `OSError`) so the row stays OFF. The policy declares `requires=('oh-my-zsh',)` and reuses the existing unmet-requires UX.

## Performance

- **Duration:** 18 min
- **Started:** 2026-09-05T07:22:19Z
- **Completed:** 2026-09-05T07:40:07Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- `installer/omz.py` edits one single-line `plugins=(...)` array in place (last match wins; nested parentheses and newline-spanning arrays are refused)
- `omz_plugins_policy` is a third Policy factory appended after the tweak bundles in `setup.py`
- Policies detail panel discloses both toggle-off (D-01) and partial-state (`Reads ON only when`) consequences
- Real-terminal tmux check and a disposable alpine container with the official Oh-My-Zsh installer both passed

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end Policies toggle adds git and docker** - `56bc37e131864d848adabebc5856888717148ab1` (feat)
2. **Task 2: Editor contract for every .zshrc shape** - `3a6d872a365be570da3c0d6a4e91e6dccc8e11a2` (test)
3. **Task 3: Presence gate, wiring, tmux + container verification** - `1adcfe4fda8b122e70610d0af1ae9432922a1dfb` (feat)

## Files Created/Modified

- `installer/omz.py` - pure editor, file wrappers, `omz_present`, `OmzPluginsError`
- `installer/policy.py` - `omz_plugins_policy` and `_ZSH_RELOAD_HINT`
- `installer/wizard_app.py` - `omz-plugins` detail copy; detail panel height 7
- `setup.py` - appends the policy after tweak bundles
- `tests/test_omz.py` - editor + presence tests
- `tests/test_policy_omz.py` - factory, layers, OSError property
- `tests/test_policies_e2e.py` - live toggle, refusal, disclosure
- `tests/test_setup.py` - composition-root wiring (source inspection)

## Decisions Made

Followed the plan. For plan 03-03's consolidated architecture note:

- The marker-block mechanism applies only to files this installer owns (`~/.myshellrc`)
- Oh-My-Zsh's `plugins=(...)` array is the one in-place exception, in `installer/omz.py`
- Only the single-line form is supported; the multi-line form raises `OmzPluginsError`
- `OmzPluginsError` subclasses `OSError` so `run_live` surfaces it under architecture rule 3
- The feature is a `Policy` (`omz_plugins_policy`), not a `Tool` and not a `TweakBundle`

## Deviations from Plan

**1. [Rule 2 - Missing Critical] Policies detail panel height 5 clipped the fourth disclosure line**
- **Found during:** Task 3 (tmux structural check)
- **Issue:** `omz-plugins` has four detail lines plus label plus requires, so `height: 5` hid `Reads ON only when` in a real terminal — the cycle-1 MEDIUM disclosure the user is supposed to read before toggling
- **Fix:** `PoliciesScreen #policy-detail { height: 7 }`
- **Files modified:** `installer/wizard_app.py`
- **Verification:** re-ran tmux; capture contains `Reads ON only when`
- **Committed in:** `1adcfe4` (Task 3)

**2. [Rule 1 - Bug] `test_build_app` uses source inspection, not a live `_build_app` call**
- **Found during:** Task 3
- **Issue:** calling private `_build_app` trips pyright (`reportPrivateUsage`) and closes over import-time `Path.home()` constants
- **Fix:** read `setup.py` source and assert `ban_policy` < `tweak_policy` < `omz_plugins_policy` call order, as the plan's allowed fallback
- **Files modified:** `tests/test_setup.py`
- **Verification:** `make validate` pyright 0 errors
- **Committed in:** `1adcfe4` (Task 3)

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 blocking/types).
**Impact on plan:** Height change is required for the pinned disclosure to be visible; source-inspection fallback is what the plan already allowed. No scope creep.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 03-03 (symmetric uninstall teardown). `omz_plugins_policy` is the disable path 03-03 should reuse. `.claude/architecture.md` is still untouched; 03-03 owns the consolidated Phase 3 architecture section.

## Real-environment evidence (ONESHOT Rule 14)

**Tier 2 tmux:** Policies table shows `Oh-My-Zsh plugins` with Requires `oh-my-zsh`. Detail panel after Down includes `Disabling removes` and `Reads ON only when`. Keys used: `6`, `Down`, `q` only — never `space`.

**Tier 3 container:** official Oh-My-Zsh installer in `alpine:latest` via colima/docker.

```
--- upstream .zshrc plugins line ---
73:plugins=(git)
added: ('docker',)
--- after enable ---
73:plugins=(git docker)
git plugin loaded in a real zsh
```

## Self-Check: PASSED

- Key files exist on disk: `installer/omz.py`, `tests/test_omz.py`, `tests/test_policy_omz.py`
- `git log --grep=03-02` returns 3 production commits
- `make validate` passed (ruff, ruff format, pyright, bandit, vulture, shellcheck)
- `make test` passed at the 90% coverage floor
- `git status --porcelain .claude/architecture.md` is empty
- Registry has no `oh-my-zsh` / `omz` tool id
- tmux and container gating checks passed

---
*Phase: 03-install-uninstall-tweak-lifecycle-hardening*
*Completed: 2026-09-05*
