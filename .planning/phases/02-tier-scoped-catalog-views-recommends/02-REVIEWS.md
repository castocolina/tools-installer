---
phase: 2
reviewers: [opencode-plan-review]
reviewed_at: 2026-09-05T02:35:53Z
plans_reviewed: [02-01-PLAN.md, 02-02-PLAN.md]
models:
  opencode-plan-review: "xai/grok-4.6 (reasoning=high)"
model_sources:
  opencode-plan-review: "pinned"
---

# Cross-AI Plan Review — Phase 2

## Consensus Summary

Only one reviewer lane ran this cycle (`opencode-plan-review`, the configured
`review.default_reviewers` instance backed by `xai/grok-4.6` via the OpenCode adapter — `gemini`,
`codex`, `coderabbit`, `qwen`, `cursor` were not configured as defaults and other local-server
lanes were not reachable). The review is source-grounded: every strength and concern cites
`path:line` evidence traced against the actual repo (view registry, `tool_browser.py`,
`catalog_tui.py`, `deps.py`, `registry.toml`, and the existing test suites), not just the plan
text. No consensus synthesis across multiple reviewers is possible with a single lane; the
findings below stand on that one reviewer's verified evidence.

### Agreed Strengths
Not applicable — only one reviewer ran.

### Agreed Concerns
Not applicable — only one reviewer ran.

### Divergent Views
Not applicable — only one reviewer ran.

## OpenCode Review (opencode-plan-review)

I'll verify both plans against the real code, starting with the files and mechanisms they claim to reuse.
The skill is for invoking other CLIs; I’ll review the plans against the repo myself. Next I’ll read the view registry, catalog screens, and the tests they claim to extend.
I need the truncated view-registry, browser selection, tests, and registry entries next.
Verified against the current tree. Findings below cite real `path:line` mechanisms, not the plans’ restatements.

---

# Plan 02-01 — Three tier-scoped catalog views

## Summary

The design matches the code: one `VIEWS` table, number keys from `enumerate(VIEW_ORDER)`, `CatalogScreen` already taking a tool list, and `resolve_dependencies` already walking only `requires` over the full catalog. Shared `_staged` plus in-place `|=` / `^=` is the right fix for today’s rebind in `action_select_all` / `action_invert`. The load-bearing accept path is also correctly identified: `Accepted.ids` is adapter-filtered, so enter from AI would drop other-tier marks unless `Decided` reads the shared set via `select_tools`. Main residual risk is execution: Task 1 is huge, and the test-migration recipe under-specifies `"catalog"` string replacements in `tests/test_wizard_app.py`.

## Strengths

- **Nav is actually data-driven.** `VIEWS` is the single table (`installer/ui_common.py:101-142`); `VIEW_ORDER` is derived (`:144`); number keys are `enumerate(VIEW_ORDER)` (`installer/wizard_app.py:668-671`). Replacing the `catalog` row and deriving `GLOBAL_NAV` from `len(VIEWS)` (`:160` is a hand-maintained `"1-4 views"`) is the architecture-legal move.
- **Shared selection is necessary, not clever.** `action_select_all` / `action_invert` rebind `self.selected` (`installer/tool_browser.py:222-236`). That would wipe other-tier marks. For an owned set, `selected ⊆ selectable`, so `|=` equals assign and `^=` equals `{selectable} - selected`. Uninstall keeps the same object identity (`:225` constructs `ToolBrowser(self._adapter())` with no injected set).
- **Enter must not use `event.ids`.** `selected_ids()` filters to adapter items (`:240-246`); `on_tool_browser_accepted` currently posts `Decided(event.ids)` (`installer/catalog_tui.py:245-251`). With a shared set, enter from AI would commit only AI ids. Switching to `select_tools(self._catalog, list(self._staged))` (`installer/selection.py:81-84`) is the correct full-catalog order.
- **Cross-tier resolve already works post-TUI.** `run_wizard` calls `resolve_dependencies(..., tools, ...)` on the full catalog (`installer/app.py:119-125`). The only real cross-view `requires` edge is `mmdc` (user) → `pnpm` (system) (`installer/registry.toml:1641-1649`, `:1442-1448`). `claude` has no `requires` (`:1182-1197`). Substituting `mmdc→pnpm` plus a synthetic ai→system fixture is honest.
- **`missing_requires` is not a second resolver.** `resolve_dependencies` still owns ordering, availability, cycles (`installer/deps.py:31-137`). A mark-time preview with no `Platform` matches `CatalogScreen` having none (`installer/catalog_tui.py:150-161`).
- **Empty-view install pitfall is named.** `on_mount` requires non-base screens in `_views` (`installer/wizard_app.py:708-718`). Routing User/AI through that dict is the right fix.
- **`_tool` default must become `system`.** `Tool.__init__` defaults `tier=Tier.USER` (`installer/model.py:76`). `tests/test_catalog_tui.py:39-56` does not pass `tier`, so today’s fixtures are all **user**. After the split, base is System — without `tier="system"` the System view is empty and every existing `space`/`a`/`i` test dies. The plan’s `fails_when` catches this.

## Concerns

- **HIGH — `tests/test_wizard_app.py` `"catalog"` sentinels are under-specified.** The action lists number-key +2 and `VIEW_ORDER`, but `_app(..., initial_view: str = "catalog")` at `tests/test_wizard_app.py:94` and `test_esc_on_catalog_is_inert` (`:885`, `initial_view="catalog"`) are unnamed. After `VIEWS` drops `catalog`, that default calls `show_view("catalog")` → `KeyError` on `_views`. Same for ~10 `current_view == "catalog"` asserts (`:124`, `:138`, `:256`, `:283`, `:305`, `:879`, `:888`, `:925`). Uninstall tests that `press("3")` from the default view (`:336`, `:352`, `:376`, `:393`, `:414`) do need `press("5")` — that part is covered; the string sentinels are not.
- **MEDIUM — ROADMAP SC#2 as written stays false.** SC#2 names `claude` → `pnpm`. `claude` installs via script/cask and declares no `requires` (`installer/registry.toml:1182-1197`). After this plan, marking `claude` in AI still will not mention `pnpm`. Mechanism is proved; the named criterion is not. Documented, but the phase goal text will not be true.
- **MEDIUM — SC#3’s unavailable-dependency notice is not in-view.** `missing_requires` makes no availability judgement (correct — no `Platform` on the screen). The “not available on this platform — skipped” line lives only in `resolve_dependencies` (`installer/deps.py:102-106`) + `render_dependency_notice` (`installer/render.py:20-32`), after the TUI. Drag-in is obvious at mark time; unavailable is not.
- **MEDIUM — Task 1 is one tracer covering nav, shared selection, three screens, setup.py, and four test modules.** `confidence: low` is accurate. A missed `install_screen` or leftover `"catalog"` sentinel is a Textual stack bug, not a red test in isolation.
- **MEDIUM — ONESHOT Rule 8 vs optional manual sanity.** Phase has `UI hint: yes`. Rule 8 (`.planning/ONESHOT-RULES.md:103-112`) requires a real terminal session; headless `Pilot.press` is not a substitute. The plan marks `make setup` as “optional, not gating.”
- **LOW — `missing_requires` indexing `installed`.** Spec says “reported installed” without `.get`. `unstaged_recommends` in 02-02 correctly uses `.get` to avoid `KeyError` in a Textual handler. A partial map here would wedge the message loop the same way.
- **LOW — `SelectionChanged.__init__` must call `super().__init__()`.** `Accepted` does (`installer/tool_browser.py:76-78`). Plan says “storing both on the message” but does not mention `super()`. Omitting it breaks Textual message delivery.
- **LOW — `test_tool_browser.py` not in Task 1’s targeted pytest.** Widget API changes (`selected=`, in-place mutate, `refresh_marks`, payload). Isolation tests (`tests/test_tool_browser.py:58`) should still pass; they only show up in the later full suite.

## Suggestions

- In Task 1’s test migration, add an explicit replace: every `"catalog"` view name in `tests/test_wizard_app.py` and `tests/test_ui_common.py` → `"system"` / `BASE_VIEW`, including `_app`’s default and `initial_view="catalog"`.
- Pin `installed.get(dep_id, False)` in `missing_requires` the same way 02-02 pins `unstaged_recommends`.
- Require `SelectionChanged.__init__` to copy `Accepted` (`super().__init__()` then attributes).
- Add `uv run pytest tests/test_tool_browser.py` to Task 1 verify.
- Either rewrite ROADMAP SC#2 to `mmdc`/`agent→pnpm`, or add a real ai-tier `requires` edge that is actually true — do not invent `claude.requires = ["pnpm"]`.
- Make the Rule 8 terminal pass gating for this TUI phase, or record a waiver.

## Risk Assessment

**MEDIUM.** Design is sound and grounded in real call paths. Risk is concentrated in the `"catalog"` → `"system"` test/app sentinel sweep and the size of Task 1, not in the architecture.

---

# Plan 02-02 — `Tool.recommends` and the selection-time prompt

## Summary

This is the cleaner half. Mirroring `requires` on `Tool` / `load_tools` (`installer/model.py:63-93`, `:137-152`) is the right parse shape. Putting `unstaged_recommends` in `selection.py` rather than `deps.py` preserves the hard/soft split `resolve_dependencies` already encodes (`installer/deps.py:63` walks only `tool.requires`). A second `StatusLine` is justified: 02-01 writes the requires notice to `self.status` on the same `SelectionChanged` (`installer/catalog_tui.py:240-243`). Illustrative `claude`/`opencode` → `rg`/`fd`/`jq` matches real catalog data and the D-02/D-03 split. Main gap: the `on_screen_resume` test sequence likely does not fail without `on_screen_resume`.

## Strengths

- **Field + parse copy the proven `requires` path.** Frozen `init=False` `Tool` needs a last `__init__` param and `object.__setattr__` (`installer/model.py:67-93`). The string guard at `:137-140` is the exact bug (`tuple("rg")` → characters). Placing `recommends` after `desc` and before `[[tool.method]]` is required TOML (`claude` `desc` at `installer/registry.toml:1189`, first method `:1190`; `opencode` `:1207-1208`).
- **Demo pair is real and cross-tier.** `rg`/`fd` are `tier = "ai"`, `audience = "ai"` (`:78-84`, `:164-170`); `jq` is `tier = "user"`, `audience = "ai"` (`:116-122`). Accepting from AI stages a row that view cannot draw — that is the whole point of `self._catalog` vs `self.tools`.
- **Consent boundary is enforceable in code.** `resolve_dependencies` never reads a field named `recommends` (`installer/deps.py:63`). Staging only in `action_accept_recommends` via `_staged.update` matches D-05. Task 1’s `selected == {"claude"}` **before** `r` is the right SC#4 assertion.
- **Two lines, no modal.** `AppScreen.compose` yields `compose_body()` then `self.status` (`installer/ui_common.py:290-296`). A second `StatusLine` in `compose_body` sits above the requires notice. `tests/test_ui_common.py:134` asserts one `StatusLine` on synthetic `_Demo`, not `CatalogScreen`.
- **`r`/`d` bubbling has a precedent.** ToolBrowser binds `a`/`i` **without** `priority=True` (`installer/tool_browser.py:95-96`); those keys already reach the widget from a focused `DataTable` (`tests/test_catalog_tui.py:203-211`). Screen-level `r`/`d` without priority should bubble the same way. Fallback `priority=True` in verify is correct.
- **Unknown-id skip is a handler guard, not a product feature.** Matches D-03. Task 3’s `test_shipped_registry_recommends_all_resolve` beside `test_shipped_registry_requires_all_resolve` (`tests/test_registry.py:683-685`) is the right CI net, without a production `recommends_integrity_errors` (architecture rule 5, `.claude/architecture.md:23-25`).
- **Does not touch `deps.py` / `wizard_app.py` / `ui_common.py`.** Wave-2 isolation is real if 02-01 lands as specified.

## Concerns

- **MEDIUM — `on_screen_resume` test likely passes without the handler.** Sequence is: `3`, `space`, `r`, `2` — User is never shown first. First `push_screen` of User mounts `ToolBrowser`, `_rebuild` paints from `row_cells` using `tool.id in self._browser.selected` (`installer/catalog_tui.py:184`) plus `call_after_refresh(_refresh_marks)` (`installer/tool_browser.py:149`). Shared set already contains `jq`, so the checkbox is `[x]` on first mount. Resume only matters after: visit User (stamped empty) → AI accept `jq` → return to User. As written, T-02-08 is not pinned.
- **MEDIUM — no test that `resolve_dependencies` ignores `recommends`.** SC#4’s “never auto-install” is pinned at the TUI (`selected == {"claude"}` before `r`). A one-liner `resolve_dependencies([claude], catalog, ...)` asserting `rg`/`fd`/`jq` not in `dragged_in` would lock the engine boundary. Today that is true only because `:63` walks `tool.requires`; a mistaken `for dep_id in tool.requires + tool.recommends` would still pass the TUI tests if the implementer also skips auto-stage.
- **MEDIUM — Rule 8 again.** Recommends prompt is the new TUI surface. Manual `make setup` is optional.
- **LOW — `test_agent_hosts_recommend_existing_catalog_tools` asserts both lists equal.** Phase 8 CONTEXT D-01 says per-host membership, not a uniform list. This test becomes mandatory churn in Phase 8.
- **LOW — stray `r` while DataTable is focused.** Mitigated by a/i precedent; verify already says flip to `priority=True` if needed.
- **LOW — empty second `StatusLine` may still consume a row.** `height: auto; padding: 0 1` (`installer/ui_common.py:64`). Minor layout risk, not behavioral.

## Suggestions

- Change the cross-tier test to: open User, leave, accept `jq` from AI, return to User. Assert both `selected` and `get_cell("jq", "sel")`.
- Add `test_resolve_dependencies_does_not_drag_in_recommends` in `tests/test_deps.py` (or `test_selection.py`) using a tool that recommends an uninstalled catalog id.
- Relax Task 3’s “lists are equal” to “both non-empty and subset of catalog ids” so Phase 8 can diverge.
- Keep `recommends` as the last `Tool.__init__` parameter (positional callers today end at `requires`).

## Risk Assessment

**LOW–MEDIUM.** Shape is right, data is real, consent path is narrow. Highest defect risk is a stale checkbox after a true resume, which the specified test may not catch.

---

# Cross-cutting

## Rule 7 (`.planning/ONESHOT-RULES.md:98-102`)

**Does not apply as HIGH.** Neither plan adds a registry method `kind`, executor, or resolver rank.

| Addition | Kind? | Tests |
|---|---|---|
| `Tool.recommends` | Field, not a kind | `test_model.py`, `test_registry.py`, `test_catalog_tui.py`, `test_selection.py` — appropriate |
| `missing_requires` | Preview, not a resolver rank; `resolve_dependencies` stays byte-identical | `test_deps.py`, `test_catalog_tui.py` — appropriate |

`tests/test_session.py`, `tests/test_policy_tweaks.py`, `tests/test_policies_e2e.py`, `tests/test_executors.py`, `tests/test_status.py` are correctly untouched. 02-01 does migrate `test_wizard_app.py` for nav, which is required by D-01, not by Rule 7.

## Phase goals

| SC | Verdict |
|---|---|
| SC#1 three views + groupings | Achieved by 02-01 if the sentinel sweep is complete |
| SC#2 `claude` surfaces `pnpm` | **Not met literally**; mechanism met via `mmdc`/`synthetic agent` |
| SC#3 no required visit order | Drag-in yes at mark time; unavailable only post-TUI |
| SC#4 recommends prompt, never auto-install | Achieved by 02-02 if accept is the only writer |

**Overall phase risk: MEDIUM** — 02-01 test/sentinel migration and the SC#2 wording gap, not the shared-set or recommends designs.
