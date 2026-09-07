---
phase: 02-tier-scoped-catalog-views-recommends
plan: 02
subsystem: ui
tags: [recommends, soft-dependency, unstaged_recommends, catalog-prompt, textual]

requires:
  - phase: 02-tier-scoped-catalog-views-recommends
    provides: shared staged set, three tier CatalogScreens, SelectionChanged.item_id
provides:
  - "Tool.recommends tuple field with load_tools parse matching requires"
  - "selection.unstaged_recommends flat one-hop lookup outside deps.py"
  - "Non-blocking CatalogScreen prompt (r accept / d dismiss) into the shared staged batch"
  - "Shipped illustrative recommends on claude and opencode; CI id-resolution"
affects: [08-recommends-wiring-agent-hosts]

actuals:
  tokens: 5311
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "recommends is a second StatusLine, never a modal and never self.status"
    - "unstaged_recommends lives in selection.py so it cannot drift into a second resolver"
    - "Accept mutates the shared staged set the same way a space-mark does"

key-files:
  created: []
  modified:
    - installer/model.py
    - installer/selection.py
    - installer/catalog_tui.py
    - installer/registry.toml
    - tests/test_model.py
    - tests/test_selection.py
    - tests/test_catalog_tui.py
    - tests/test_registry.py
    - tests/test_deps.py
    - .claude/architecture.md

key-decisions:
  - "Prompt is a second StatusLine so the 02-01 requires notice and the recommends offer can both stay visible."
  - "Dismissal is not remembered; suppression comes from ids already being staged."
  - "jq is in the illustrative list on purpose so accept stages a user-tier id from the AI view."

patterns-established:
  - "Hard requires vs soft recommends: same parse shape, no shared semantics."
  - "on_screen_resume re-stamps marks because accept is the only writer for a non-active screen."
  - "Registry recommends integrity is a test, not a production twin of requires_integrity_errors."

requirements-completed:
  - REQ-recommends-soft-dependency

coverage:
  - id: D1
    description: "Tool.recommends parses like requires; a bare string is rejected; unstaged_recommends is flat one-hop"
    requirement: REQ-recommends-soft-dependency
    verification:
      - kind: unit
        ref: tests/test_model.py#test_tool_recommends_defaults_empty_and_parses
        status: pass
      - kind: unit
        ref: tests/test_model.py#test_load_tools_rejects_recommends_as_a_string
        status: pass
      - kind: unit
        ref: tests/test_selection.py#test_unstaged_recommends_is_flat_one_hop
        status: pass
    human_judgment: false
  - id: D2
    description: "Marking claude in the AI view offers rg, fd, jq without auto-staging; r folds them into the shared batch"
    requirement: REQ-recommends-soft-dependency
    verification:
      - kind: e2e
        ref: tests/test_catalog_tui.py#test_marking_claude_in_the_ai_view_offers_its_recommends_and_r_stages_them
        status: pass
      - kind: automated_ui
        ref: tmux gsd-p2-rec capture-pane
        status: pass
    human_judgment: false
  - id: D3
    description: "Dismiss, unmark, bulk select, and already-staged ids leave the batch untouched; cross-tier accept is visible on resume"
    requirement: REQ-recommends-soft-dependency
    verification:
      - kind: unit
        ref: tests/test_catalog_tui.py#test_dismissing_the_prompt_leaves_the_selection_untouched
        status: pass
      - kind: unit
        ref: tests/test_catalog_tui.py#test_accepted_cross_tier_recommendation_shows_marked_on_returning_to_its_tier_view
        status: pass
      - kind: unit
        ref: tests/test_deps.py#test_resolve_dependencies_does_not_drag_in_recommends
        status: pass
    human_judgment: false
  - id: D4
    description: "Shipped registry recommends on claude and opencode all resolve to catalog ids"
    requirement: REQ-recommends-soft-dependency
    verification:
      - kind: unit
        ref: tests/test_registry.py#test_shipped_registry_recommends_all_resolve
        status: pass
      - kind: unit
        ref: tests/test_registry.py#test_agent_hosts_recommend_existing_catalog_tools
        status: pass
    human_judgment: false

duration: 55min
completed: 2026-09-05
status: complete
---

# Phase 2 Plan 02: Recommends Soft-Dependency Prompt

Selecting `claude` or `opencode` surfaces a one-action, non-blocking prompt naming its `recommends`; `r` folds those ids into the shared staged batch and `d` dismisses. Nothing in that list is staged or installed without the keypress.

## Task Commits

1. **Task 1: End-to-end mark-claude-offers-recommends-and-r-stages-them** - `22c506ed6a53226c7808ef91328e046686c1a5e5` (feat)
2. **Task 2: Dismiss, transience, suppression, and cross-tier visibility** - `b2ac04040a4c5d0c17dab8cd15ff24de9e7e7b83` (feat)
3. **Task 3: Both agent hosts shipped, dangling ids fail CI, split written down** - `35e9e5ba0b4489bc103a142fd6c17750ed0083ae` (feat)

## Deviations from Plan

- Task 1's `test_unstaged_recommends_names_uninstalled_unstaged_ids` used `staged=set[str]()` instead of `staged=set()` so pyright-strict does not report `set[Unknown]`.
- Task 3's gating `gsd-p2-rec` tmux script was re-run with `PATH=/bin` and absolute `/usr/local/bin/uv` because this machine's Homebrew `/usr/local/bin/{rg,fd}` and Apple `/usr/bin/jq` make `unstaged_recommends` correctly omit already-installed recommendations. The verbatim script with the default PATH marked `claude` but raised no prompt. With `PATH=/bin` the three captures matched `press r` absent → `rg, fd, jq - press r` present → `press r` absent.

## Self-Check: PASSED
