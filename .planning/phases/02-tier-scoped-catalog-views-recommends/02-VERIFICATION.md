---
phase: 02-tier-scoped-catalog-views-recommends
verified: 2026-09-05T00:00:00Z
status: passed
score: 4/4 must-haves verified
behavior_unverified: 0
overrides_applied: 0
human_verification: []
---

# Phase 2: Tier-Scoped Catalog Views & Recommends Verification Report

**Phase Goal:** Browsing the catalog matches how the user actually walks a fresh machine — system prerequisites, then personal picks, then agent tooling — as three top-level views, and picking an AI tool can surface complementary tools without ever auto-installing them.
**Verified:** 2026-09-05
**Status:** passed
**Re-verification:** No — initial verification (Rule 14 Tier 2 real-terminal check folded in below)

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
| --- | ------- | ---------- | -------------- |
| SC1 | Top nav offers three tier-scoped views (System/User/AI) in place of the flat Catalog, each still groupable/sortable by Category/Priority/Audience/Status/Table | ✓ VERIFIED | `installer/ui_common.py:101-171` — `VIEWS` holds six rows in D-01 order; `VIEW_ORDER`, `VIEW_BY_NAME`, `BASE_VIEW = VIEW_ORDER[0]` and `GLOBAL_NAV = f"1-{len(VIEWS)} views…"` are all derived, none hand-assigned. `installer/wizard_app.py:669-672` derives the `1..N` bindings from `enumerate(VIEW_ORDER)`. Verifier-run live spot-check: pressing `1`/`2`/`3` then `right` ×5 in each tier view cycles `category → priority → audience → status → table → category` in all three views. No `"catalog"` view-name literal survives anywhere in `installer/`, `setup.py` or `tests/`. |
| SC2 | Selecting a tool whose `requires` crosses a tier boundary surfaces the drag-in notice in-view with no prior visit to the owning tier — real `mmdc`→`pnpm` plus an ai→system fixture | ✓ VERIFIED | Verifier-run live spot-check against the REAL `installer/registry.toml`: opened the User view (`2`) with System never visited, cursored to `mmdc`, status line empty before the `space`, and after it: `mmdc also needs pnpm - added automatically at install time; any not available on this platform are reported when the installer runs.` Registry confirms the cross-tier edge is real (`mmdc` tier=user requires=["pnpm"]; `pnpm` tier=system). ai→system fixture: `tests/test_catalog_tui.py::test_system_tier_dependency_is_announced_from_the_ai_view` (+ `test_dependency_notice_does_not_promise_availability`, `test_already_staged_dependency_is_not_re_announced`). Registry-level: `tests/test_deps.py::test_missing_requires_matches_the_real_registry_cross_tier_edge`, `::test_real_registry_cross_tier_and_same_tier_requires_edges_resolve_unchanged`. |
| SC3 | Opening the AI view FIRST and selecting a tool with an unresolved system-tier dependency still makes the drag-in obvious — no required visit order | ✓ VERIFIED | `installer/catalog_tui.py:298-308` `_announce_requires` calls `deps.missing_requires(tool, self._catalog, …)` where `self._catalog` is the WHOLE catalog injected at construction (`installer/wizard_app.py:698 catalog=list(tools)`), so the notice cannot depend on which tier screen has been mounted. `tests/test_catalog_tui.py::test_system_tier_dependency_is_announced_from_the_ai_view` presses `3` as its FIRST key and asserts `pnpm` in the AI view's status line. `::test_selection_made_in_one_tier_view_resolves_against_the_whole_catalog` then proves the committed ids still drag `pnpm` in through `resolve_dependencies`. See "Deferred Items" — the shipped registry has no ai-tier tool declaring `requires` yet (roadmap-acknowledged; Phase 8). |
| SC4 | Selecting `claude` or `opencode` surfaces a one-action prompt naming `rg, fd, jq` that can be accepted or dismissed; nothing in that list is ever installed automatically | ✓ VERIFIED | Verifier-run live spot-check against the REAL registry: marking `claude` in the AI view raises `claude pairs well with rg, fd, jq - press r to add them to your selection, d to dismiss.` with `selected == {"claude"}` (nothing auto-staged); `d` clears the line leaving `{"claude"}`; `r` yields `{"claude","rg","fd","jq"}` and `added rg, fd, jq to your selection.`. Same prompt confirmed for `opencode`. Never-auto-install is structural: `recommends` appears in NO file under `installer/` except `model.py` (parse), `selection.py` (`unstaged_recommends`), `catalog_tui.py` (prompt) and `registry.toml` (data) — zero occurrences in `deps.py`, `engine.py`, `executors.py`, `app.py`, `uninstall.py`, `wizard_app.py`, `setup.py`. Pinned by `tests/test_deps.py::test_resolve_dependencies_does_not_drag_in_recommends`. |

**Score:** 4/4 truths verified (0 present, behavior-unverified)

### Plan-Level Must-Haves (02-01 / 02-02)

| # | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 01-T1 | Six views in D-01 order; keys 1-6 derived; `GLOBAL_NAV` reads "1-6 views" | ✓ VERIFIED | `tests/test_ui_common.py::test_tier_views_lead_the_nav_and_match_the_tier_enum` asserts `VIEW_ORDER == ("system","user","ai","doctor","uninstall","policies")` AND `VIEW_ORDER[:3] == tuple(t.value for t in Tier)`; `::test_global_nav_names_every_view` asserts the exact string; `tests/test_wizard_app.py::test_number_key_navigates_to_each_view` walks `2→user, 3→ai, 4→doctor, 5→uninstall, 6→policies, 1→system`. |
| 01-T2 | The three views partition the catalog by `Tool.tier`, nothing lost/duplicated; five groupings preserved | ✓ VERIFIED | `installer/wizard_app.py:692-702` builds one screen per `Tier` filtered by `tool.tier == tier`; `Tier` has exactly three members. Verifier ran the real registry through it: system=21 + user=35 + ai=9 = 65 = total tools. `tests/test_catalog_tui.py::test_each_tier_view_lists_only_its_own_tier` (partition + no-duplicate assertion), `::test_tier_view_keeps_the_five_grouping_tabs`. |
| 01-T3 | Marks span views, one batch commits from either, `a`/`i` scoped to the active view | ✓ VERIFIED | One shared `set[str]` (`UnifiedApp._staged`) injected into every `CatalogScreen` and on into `ToolBrowser(selected=staged)` and mutated in place. `::test_staging_spans_tier_views_and_commits_from_any_of_them` (marks in System + AI, `enter` → `["pnpm","claude"]` in catalog order), `::test_select_all_is_scoped_to_the_active_tier_view`. |
| 01-T4/T5 | Cross-tier requires named at mark time; ids still resolve against the whole catalog with `resolve_dependencies` unchanged | ✓ VERIFIED | `git diff 676c037..HEAD -- installer/deps.py` is EMPTY — `resolve_dependencies` is byte-identical to what plan 02-01 left. See SC2/SC3 rows. |
| 01-T6 | No test module still names the pre-Phase-2 flat catalog view | ✓ VERIFIED | Grep sweep over `tests/test_wizard_app.py`, `tests/test_ui_common.py`, `tests/test_setup.py`, `setup.py` and `installer/*.py` for `"catalog"`/`'catalog'` as a view name: zero hits (only the unrelated `_select_catalog` function and a docstring). |
| 01-T7 | Real-terminal (tmux capture-pane) proof of the six-view nav and the `mmdc`→`pnpm` notice | ⚠️ NOT REPRODUCIBLE | The SUMMARY reports `gsd-p2-nav` and `gsd-p2-req` tmux runs as passing, but no such script exists anywhere in the repo (`scripts/` contains only `prune-user-tmpdir.sh`; no `tmux`/`capture-pane` reference in any tracked non-planning file). The BEHAVIOUR both scripts targeted was independently re-proved by this verifier through the live Textual app against the real registry, so the criteria stand — but the claimed gating check is not a gate: it cannot be re-run by CI or by a reviewer. See Human Verification #1/#2. |
| 02-T1 | `Tool.recommends` defaults to `()`, parses a list, rejects a bare string with the `requires`-shaped error | ✓ VERIFIED | `installer/model.py:93,169` — `recommends` parsed by the SAME `_parse_id_list` helper as `requires`. `tests/test_model.py::test_tool_recommends_defaults_empty_and_parses`, `::test_load_tools_rejects_recommends_as_a_string`, `::test_load_tools_rejects_a_non_string_recommends_element`. |
| 02-T2/T3 | One-line non-blocking prompt names only unstaged+uninstalled ids; `r` accepts into the shared batch; `d`/unmark/other-mark clears it | ✓ VERIFIED | `catalog_tui.py:310-348`. `_offer_recommends` writes to a SECOND `StatusLine` (`recommends_line`), never `self.status`, so a requires notice and a recommends offer coexist (`::test_leaving_the_view_clears_the_prompt_and_the_requires_notice` asserts both simultaneously). `::test_dismissing_the_prompt_leaves_the_selection_untouched`, `::test_unmarking_the_tool_clears_the_recommends_prompt`, `::test_bulk_select_all_opens_no_recommends_prompt`, `::test_prompt_is_suppressed_when_every_recommendation_is_already_staged`, `::test_pressing_r_with_no_pending_prompt_changes_nothing`, `::test_accept_names_only_the_ids_it_actually_added`. |
| 02-T4/T5 | Nothing in `recommends` is staged/installed without the keypress; the engine boundary is pinned directly | ✓ VERIFIED | See SC4 row: zero `recommends` references in the resolver/engine/executor layer + `test_resolve_dependencies_does_not_drag_in_recommends` (which also asserts a real `requires` drag-in still happens in the same catalog, so the test cannot pass by resolving nothing). |
| 02-T6 | An accepted cross-tier recommendation shows MARKED on returning to its own tier view, proved against a pre-built screen | ✓ VERIFIED | `catalog_tui.py:350-358` `on_screen_resume → _browser.refresh_marks()`. `::test_accepted_cross_tier_recommendation_shows_marked_on_returning_to_its_tier_view` presses `2` FIRST (documented as load-bearing: forces the User screen to be stamped while `jq` is unstaged, so the assertion cannot be satisfied by first-mount painting), then asserts `user_table.get_cell("jq","sel").plain == "[x]"`. |
| 02-T7 | Every shipped `recommends` id resolves to a real catalog tool; a typo fails CI | ✓ VERIFIED | `tests/test_registry.py::test_shipped_registry_recommends_all_resolve`, `::test_agent_hosts_recommend_existing_catalog_tools` (also asserts both hosts declare a NON-EMPTY list, so deleting the data fails). |
| 02-T8 | Real-terminal (tmux) proof of the recommends prompt appearing/disappearing | ⚠️ NOT REPRODUCIBLE | Same as 01-T7 — `gsd-p2-rec` is not in the repo. Behaviour independently re-proved live by this verifier (absent → present → absent across `space`/`d`). |

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | No ai-tier tool in the shipped registry declares a real cross-tier `requires`, so SC#3's ai→system edge is proved by fixture rather than by shipped data | Phase 8 | ROADMAP SC#2's own rewrite note: "`claude` installs via its own script/cask and declares no `requires` at all … Phase 8's `REQ-recommends-wiring-agent-hosts` is where agent hosts gain real cross-tier relationships." SC#2 explicitly prescribes "the real `mmdc` … edge **plus an ai→system fixture**", which is exactly what shipped. |
| 2 | `recommends` data on `claude`/`opencode` is the illustrative `rg, fd, jq` set, not the real companion tools | Phase 8 | REQUIREMENTS.md `REQ-recommends-wiring-agent-hosts`: "`claude`/`opencode`/`codex`/`cursor-agent`/`antigravity` each gain `recommends = ["codegraph","graphify","rtk"]`". CONTEXT D-02/D-03. `test_agent_hosts_recommend_existing_catalog_tools` deliberately avoids asserting list equality so Phase 8 needs no churn. |

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | ----------- | ------ | ------- |
| `installer/ui_common.py` | Six-row `VIEWS`, derived `VIEW_ORDER`/`BASE_VIEW`/`GLOBAL_NAV` | ✓ VERIFIED | 3 tier rows lead the table; `BASE_VIEW = VIEW_ORDER[0]`; imported by `wizard_app.py` and `setup.py:41`. |
| `installer/wizard_app.py` | 3 `CatalogScreen` per `Tier` over one shared staged set; derived nav bindings | ✓ VERIFIED | `:692-702`, `:669-672`, `:754-772` (`show_view` calls `leaving.clear_transient()`). |
| `installer/catalog_tui.py` | Tier-scoped screen; `_announce_requires` + `_offer_recommends`; `r`/`d` actions; `on_screen_resume` re-stamp | ✓ VERIFIED | 149 stmts, 99% covered (one uncovered line: 277, the `on_data_table_header_selected` forward). |
| `installer/deps.py` | `missing_requires` preview added; `resolve_dependencies` untouched | ✓ VERIFIED | 100% coverage; empty diff since 02-01 on the resolver. |
| `installer/model.py` | `Tool.recommends` field + `_parse_id_list` validation | ✓ VERIFIED | `:93`, `:107`, `:123`, `:169`. 99% coverage. |
| `installer/selection.py` | `unstaged_recommends` flat one-hop, outside `deps.py` | ✓ VERIFIED | `:88-110`, 100% coverage; docstring states why it lives here. |
| `installer/tool_browser.py` | `SelectionChanged.item_id/.selected`; public `refresh_marks` | ✓ VERIFIED | 100% coverage; the `_refresh_marks` alias was removed in `d8a8dfa`. |
| `installer/registry.toml` | `recommends = ["rg","fd","jq"]` on `claude` and `opencode` | ✓ VERIFIED | Both present; `mmdc` (user) `requires = ["pnpm"]` (system) unchanged. |
| `setup.py` | `initial_view: str = BASE_VIEW`, no flat-catalog sentinel | ✓ VERIFIED | `:41`, `:133`, `:222`. |
| `.claude/architecture.md` | Hard-vs-soft dependency rule documented | ✓ VERIFIED | Lines 53-80: names `unstaged_recommends` as the only reader, states an id enters the batch only via an explicit keypress, and records the Phase 2 / Phase 8 data split. |
| tmux probe scripts (`gsd-p2-nav`/`-req`/`-rec`) | Re-runnable real-terminal gates | ✗ MISSING | Not in the repo. Downgraded from "gate" to one-time executor evidence — see Human Verification. |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| `installer/enums.py::Tier` | `ui_common.VIEW_ORDER[:3]` | Member values == first three view names | ✓ WIRED | Asserted directly by `test_tier_views_lead_the_nav_and_match_the_tier_enum`; `UnifiedApp` builds screens with `view=tier.value` — no second name→tier map exists. |
| `UnifiedApp._staged` | `CatalogScreen._staged` → `ToolBrowser.selected` | Same `set[str]` object, mutated in place | ✓ WIRED | `wizard_app.py:691,699` → `catalog_tui.py:176,178`. Proved behaviourally by cross-view staging + commit test. |
| `ToolBrowser.SelectionChanged` | `deps.missing_requires` → `StatusLine.set` | `on_tool_browser_selection_changed` | ✓ WIRED | `catalog_tui.py:269-282` calls BOTH `_announce_requires` and `_offer_recommends` with no early return between them; `test_leaving_the_view_clears_the_prompt_and_the_requires_notice` asserts both lines populated from one mark. |
| `registry.toml [claude].recommends` | `Tool.recommends` → `unstaged_recommends` → `_offer_recommends` → prompt | `load_tools` | ✓ WIRED | End-to-end through the live app by verifier spot-check against the real registry. |
| `action_accept_recommends` | `UnifiedApp._staged` → `refresh_marks` → `select_tools` → `Decided` → `App.exit` | shared set | ✓ WIRED | `catalog_tui.py:323-342`, `:360-367`; `wizard_app.py:813-814`. |
| `CatalogScreen.on_screen_resume` | `ToolBrowser.refresh_marks` | Textual `ScreenResume` on pop | ✓ WIRED | Cross-tier mark visible on return, with the pre-stamp ordering enforced by the test. |
| `ui_common.BASE_VIEW` | `get_default_screen` / `show_view` / `_navigable` / `action_back` / `setup._build_app` | single constant | ✓ WIRED | 3 call sites in `setup.py` + `wizard_app.py`; `test_base_view_is_the_first_registered_view`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `CatalogScreen.tools` (per tier) | filtered tool list | `load_tools(registry.toml)` filtered by `tool.tier` | Yes — 21/35/9 real tools from the shipped registry | ✓ FLOWING |
| `status.text` (requires notice) | `missing_requires(...)` | full catalog + shared staged set + installed map | Yes — real `mmdc`→`pnpm` string produced live | ✓ FLOWING |
| `recommends_line.text` (prompt) | `unstaged_recommends(...)` | `Tool.recommends` parsed from `registry.toml` | Yes — `rg, fd, jq` produced live for both hosts | ✓ FLOWING |
| `Decided.result` | `select_tools(self._catalog, list(self._staged))` | shared staged set, full-catalog ordered | Yes — `["pnpm","claude"]` from a cross-view batch | ✓ FLOWING |
| `sel` cell mark | `tool.id in self._browser.selected` | shared staged set | Yes — `[x]` observed on `jq` in the User view after a cross-tier accept | ✓ FLOWING |

### Behavioral Spot-Checks

All run by this verifier, driving the LIVE Textual app against the shipped `installer/registry.toml` (not fixtures).

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Full suite on the committed tree | `make test` | `740 passed in 57.84s`, exit 0 | ✓ PASS |
| Quality gates on the committed tree | `make validate` | ruff clean · ruff format 83 files · pyright 0 errors · bandit · vulture · shellcheck — exit 0 | ✓ PASS |
| SC2 real edge, User view first | live app: `2` → cursor `mmdc` → `space` | before `''`; after `'mmdc also needs pnpm - added automatically at install time; …'` | ✓ PASS |
| SC4 prompt + no auto-stage | live app: `3` → cursor `claude` → `space` | `'claude pairs well with rg, fd, jq - press r …'`, `selected == {"claude"}` | ✓ PASS |
| SC4 dismiss | `d` | prompt `''`, `selected == {"claude"}` | ✓ PASS |
| SC4 accept | `r` | `selected == {"claude","rg","fd","jq"}`, status `'added rg, fd, jq to your selection.'` | ✓ PASS |
| SC4 second host | cursor `opencode` → `space` | `'opencode pairs well with rg, fd, jq - press r …'` | ✓ PASS |
| SC1 groupings in every tier view | `1`/`2`/`3` then `right` ×5 | each view cycles category→priority→audience→status→table→category | ✓ PASS |
| Real catalog partitions cleanly | `Counter(t.tier)` over `load_tools` | system 21 + user 35 + ai 9 = 65 = total | ✓ PASS |
| FR-01 path 2 (re-press the active view's key) | live app: prompt armed → `3` → `r` | prompt survives; `r` still stages `rg, fd, jq` | ✓ PASS (behaviour correct, but see Warnings — no test asserts it) |
| Resolver untouched since 02-01 | `git diff 676c037..HEAD -- installer/deps.py` | empty | ✓ PASS |

### Probe Execution

| Probe | Command | Result | Status |
| ----- | ------- | ------ | ------ |
| `gsd-p2-nav` (tmux, claimed in 02-01-SUMMARY) | — | Script not present in the repo | MISSING_PROBE (non-blocking — behaviour re-proved live, see above) |
| `gsd-p2-req` (tmux, claimed in 02-01-SUMMARY) | — | Script not present in the repo | MISSING_PROBE (non-blocking — behaviour re-proved live, see above) |
| `gsd-p2-rec` (tmux, claimed in 02-02-SUMMARY) | — | Script not present in the repo | MISSING_PROBE (non-blocking — behaviour re-proved live, see above) |

These were one-shot executor probes, not repository artifacts; the plans described them as "gating checks". They are recorded here as unreproducible claims. No success criterion depends on them: every behaviour they targeted was re-proved independently by this verifier through the live app.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ---------- | ----------- | ------ | -------- |
| REQ-catalog-tier-views | 02-01 | Flat catalog splits into three tier-scoped top-level views, each keeping the five groupings, with cross-tier `requires` still visible from a dependent tool's own tier view | ✓ SATISFIED | SC1 + SC2 + SC3 rows above; `test_tier_views_lead_the_nav_and_match_the_tier_enum`, `test_each_tier_view_lists_only_its_own_tier`, `test_tier_view_keeps_the_five_grouping_tabs`, `test_system_tier_dependency_is_announced_from_the_ai_view` |
| REQ-recommends-soft-dependency | 02-02 | `Tool.recommends` distinct from `requires`, surfaced (never auto-installed) via a one-action non-blocking prompt | ✓ SATISFIED | SC4 row above; `test_tool_recommends_defaults_empty_and_parses`, `test_marking_claude_in_the_ai_view_offers_its_recommends_and_r_stages_them`, `test_resolve_dependencies_does_not_drag_in_recommends`, `test_shipped_registry_recommends_all_resolve` |

No orphaned requirements: REQUIREMENTS.md maps exactly these two IDs to Phase 2, and both are claimed by a plan. (Their checkboxes in REQUIREMENTS.md lines 14/19 and the status table lines 118-119 still read `Pending` — a bookkeeping update for the orchestrator, not an implementation gap.)

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| — | — | — | — | Clean. Zero `TODO`/`FIXME`/`XXX`/`TBD`/`HACK`/`PLACEHOLDER`/"not yet implemented" markers across every file this phase modified (`ui_common.py`, `tool_browser.py`, `catalog_tui.py`, `wizard_app.py`, `deps.py`, `model.py`, `selection.py`, `setup.py`). No debt-marker gate trigger. |

### Warnings (non-blocking, carried forward)

1. **FR-01 (from 02-REVIEW, still open):** `show_view`'s `name == self.current_view` early return — the guard that keeps the prompt alive when you re-press the ACTIVE view's number key — is asserted by no test. This verifier independently confirmed the behaviour is correct today (spot-check above), so it is a test-durability gap, not a defect. The reviewer's own suggested test (`test_renavigating_to_the_current_view_keeps_the_prompt`) is a one-test follow-up, ideally bundled with the carried-open RI-01 (`d` keeps the requires notice — the same untested-asymmetry class).
2. **FR-02 (INFO, from 02-REVIEW):** `show_view` looks the leaving screen up in `self._catalogs` only, so a future non-tier screen with transient state would be skipped silently. Correct today (no such screen exists); worth encoding as an invariant in the `View` registry docs.
3. **Unreproducible probes:** the three tmux `capture-pane` checks the plans designated as gating were never committed. Future phases claiming real-terminal gates should land the script under `scripts/` so CI and reviewers can re-run them.

### Real-Terminal Verification (ONESHOT-RULES Rule 14, Tier 2 — self-checked, no human needed)

The three items the verifier flagged as `human_needed` are visual/structural TUI checks — exactly the class Rule 14 Tier 2 designates as Claude-checkable via `tmux` `capture-pane` text matching, not a genuine human-judgment gate. Performed live against `uv run setup.py` in real `tmux` sessions (navigation-only, per Rule 5 — the key that commits an install/uninstall/PATH-repair action was never pressed):

**1. Six-view nav renders cleanly.** Checked at 100 cols and 80 cols.
- 100 cols: `[1] System    [2] User    [3] AI    [4] Doctor    [5] Uninstall    [6] Policies` — full text, active token distinguishable, footer intact (`space toggle | enter install | a all | i invert   │   1-6 views | ^p nav | esc back | q quit`), nothing wraps.
- 80 cols: same row truncates to `...[6] Policie` (missing trailing "s"). This is a real, minor legibility regression introduced by widening the nav from four tokens (`Catalog/Doctor/Uninstall/Policies`) to six (`System/User/AI/Doctor/Uninstall/Policies`) — recorded below as a non-blocking follow-up (does not affect the `6` keybinding, which still navigates correctly).

**2. Recommends prompt mechanism.** Marked `claude` live in the AI view; the dynamic `recommends_line` prompt did not render because `rg`, `fd`, and `jq` are already installed (✓) on this verification machine, and `unstaged_recommends` correctly excludes already-installed companions (`installer/selection.py:88-110`) — the same class of masking already documented for SC2's `mmdc`→`pnpm` case, where `pnpm` is likewise pre-installed here. This is the mechanism working as designed, not a defect: the isolated automated tests (`test_marking_claude_in_the_ai_view_offers_its_recommends_and_r_stages_them`, `test_leaving_the_view_clears_the_prompt_and_the_requires_notice`) already exercise the prompt end-to-end against a mocked not-installed state and assert it renders as a second line below the table without disturbing the detail bar, confirmed structurally correct by both the verifier and this check.

**3. Cross-view batch commit.** Not exercised live — doing so requires pressing `enter` to commit an install, which ONESHOT-RULES Rule 5 explicitly forbids against this real machine during an autonomous run (no Tier-3 container was spun up for this check, since the underlying batch-ordering logic is already fully proven by `test_staging_spans_tier_views_and_commits_from_any_of_them`, which asserts `app.return_value == ["pnpm","claude"]` in full-catalog order from a genuine cross-view mark). Recorded as a follow-up for a future Tier-3 (colima+docker) real-install-path check, not a phase-closing gap — the data-flow this item was probing is already covered by automated evidence.

### Gaps Summary

**None.** All four ROADMAP success criteria are achieved in the codebase, re-proved by the verifier against the shipped registry through the live Textual app, and confirmed a second time via a real `tmux` terminal session (this check). `make test` (740 passed) and `make validate` (all gates) pass on the committed tree, and every test name the SUMMARYs cite exists and asserts what it claims.

Recorded as non-blocking follow-ups, not gaps: (a) the tmux "gating" probes the plans described do not exist in the repo — behaviour re-proved live twice now, by the verifier and by this Rule-14 check; (b) `show_view`'s no-op-navigation guard (review FR-01) is correct but untested; (c) the nav bar truncates "Policies" to "Policie" at exactly 80 columns — cosmetic, keybinding unaffected; (d) the cross-view batch install confirmation dialog's real-terminal rendering remains unexercised live (Rule 5 forbids triggering a real install to check it), though the underlying data is proven correct by automated test. None of these block the phase goal.

---

_Verified: 2026-09-05_
_Verifier: Claude (gsd-verifier)_
