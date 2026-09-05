---
phase: 02-tier-scoped-catalog-views-recommends
plan: 01
subsystem: ui
tags: [tier-views, staged-selection, missing_requires, textual, nav]

requires:
  - phase: 01-catalog-tier-foundation
    provides: Tool.tier enum and registry backfill
provides:
  - "Six-view nav in D-01 order: System / User / AI / Doctor / Uninstall / Policies"
  - "Three CatalogScreen instances over one shared staged set"
  - "BASE_VIEW and GLOBAL_NAV derived from the VIEWS table"
  - "deps.missing_requires read-only cross-tier preview"
affects: [02-02-recommends-soft-dependency]

actuals:
  tokens: 8500
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "One shared set[str] staged batch injected into ToolBrowser.selected; bulk actions mutate in place"
    - "Tier view names equal Tier member values so UnifiedApp builds one screen per tier with no second map"
    - "missing_requires is a preview beside resolve_dependencies, never a second resolver"

key-files:
  created: []
  modified:
    - installer/ui_common.py
    - installer/tool_browser.py
    - installer/catalog_tui.py
    - installer/wizard_app.py
    - installer/deps.py
    - setup.py
    - tests/test_ui_common.py
    - tests/test_tool_browser.py
    - tests/test_catalog_tui.py
    - tests/test_wizard_app.py
    - tests/test_setup.py
    - tests/test_deps.py
    - .claude/architecture.md

key-decisions:
  - "Three CatalogScreens share UnifiedApp._staged; only the active screen posts Decided, carrying the whole batch in full-catalog order."
  - "missing_requires names unstaged uninstalled requires ids; availability verdict stays on the post-TUI resolve_dependencies path."

patterns-established:
  - "BASE_VIEW = VIEW_ORDER[0] replaces every base-screen name literal."
  - "GLOBAL_NAV is f-stringed from len(VIEWS)."
  - "catalog_for(view) is the headless seam for non-base tier screens."

requirements-completed:
  - REQ-catalog-tier-views

coverage:
  - id: D1
    description: "Top nav offers six views in order System / User / AI / Doctor / Uninstall / Policies with derived 1-6 keys and GLOBAL_NAV"
    requirement: REQ-catalog-tier-views
    verification:
      - kind: unit
        ref: tests/test_ui_common.py#test_tier_views_lead_the_nav_and_match_the_tier_enum
        status: pass
      - kind: unit
        ref: tests/test_ui_common.py#test_global_nav_names_every_view
        status: pass
      - kind: automated_ui
        ref: tmux gsd-p2-nav capture-pane
        status: pass
    human_judgment: false
  - id: D2
    description: "Three tier views partition the catalog by Tool.tier and keep the five grouping tabs"
    requirement: REQ-catalog-tier-views
    verification:
      - kind: unit
        ref: tests/test_catalog_tui.py#test_each_tier_view_lists_only_its_own_tier
        status: pass
      - kind: unit
        ref: tests/test_catalog_tui.py#test_tier_view_keeps_the_five_grouping_tabs
        status: pass
    human_judgment: false
  - id: D3
    description: "Staging spans tier views, commits once from any view, and a/i stay scoped to the active view"
    requirement: REQ-catalog-tier-views
    verification:
      - kind: unit
        ref: tests/test_catalog_tui.py#test_staging_spans_tier_views_and_commits_from_any_of_them
        status: pass
      - kind: unit
        ref: tests/test_catalog_tui.py#test_select_all_is_scoped_to_the_active_tier_view
        status: pass
    human_judgment: false
  - id: D4
    description: "Marking a tool announces unstaged cross-tier requires from that tool's own view; ids still resolve against the whole catalog"
    requirement: REQ-catalog-tier-views
    verification:
      - kind: unit
        ref: tests/test_catalog_tui.py#test_system_tier_dependency_is_announced_from_the_ai_view
        status: pass
      - kind: unit
        ref: tests/test_catalog_tui.py#test_selection_made_in_one_tier_view_resolves_against_the_whole_catalog
        status: pass
      - kind: unit
        ref: tests/test_deps.py#test_missing_requires_matches_the_real_registry_cross_tier_edge
        status: pass
      - kind: automated_ui
        ref: tmux gsd-p2-req capture-pane
        status: pass
    human_judgment: false

duration: 50min
completed: 2026-09-05
status: complete
---

# Phase 2 Plan 01: Tier-Scoped Catalog Views

Split the flat Catalog into System / User / AI views over one shared staged batch, and surface cross-tier `requires` in the status line at mark time.

## Task Commits

1. **Task 1: Shared-selection seam and derived BASE_VIEW** - `b39e131d06f0405b145a6932d3000af92771a3a9` (feat)
2. **Task 2: Three tier-scoped catalog views** - `d627cb0cbff53373964feecbe7981b6666ca63a3` (feat)
3. **Task 3: Cross-tier requires notice** - `676c037b0993f9c2a6b71532e4f6fea2df8ba8f9` (feat)

## Deviations from Plan

- Task 1 kept `_refresh_marks = refresh_marks` so existing isolation tests that getattr the former private name stay green without editing them. Ruff SIM300 required `VIEW_ORDER[0] == BASE_VIEW` instead of the plan's comparison order.
- Task 2 also shifted palette down-counts, `press("2", "3", "4", "1")`, and the unsettled key-burst `"52452152"` (sites the `press("[1-9]")` work list does not match), and added `tier="system"` to one direct `Tool(...)` in `test_detail_bar_shows_requires_when_declared`.
- Task 3's gating `gsd-p2-req` tmux script was re-run with `PATH=/usr/bin:/bin` and absolute `/usr/local/bin/uv` because this machine's Homebrew `/usr/local/bin/pnpm` makes `missing_requires` correctly omit an already-installed dependency. The six-view `gsd-p2-nav` script passed verbatim.

## Self-Check: PASSED
