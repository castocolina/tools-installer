# Phase 21: One screen family - Discussion Log (Assumptions Mode)

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the analysis.

**Date:** 2026-10-14
**Phase:** 21-one-screen-family
**Mode:** assumptions (`--analyze --all --batch`), jev screening, best-over-easy
**Areas analyzed:** Screen stack and lifecycle; Refresh owner; Uninstall and removal; Policies and Doctor; Pruning and deletions

## Assumptions Presented

The analyzer was `gsd-assumptions-analyzer` (sonnet) with jev-fast-decision injected. It made 56 tool calls (codegraph, reads, and Textual source) and no network calls. The CodeGraph index was synced during the session (2 files, 40 nodes).

| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| Delete `get_default_screen`; six views installed; one `show_view` path | Confident | wizard_app.py:2670-2674, 2509-2511, 2589-2592, 2676-2712; textual/app.py:1380-1391 |
| `AppScreen` defaults: `state_refreshed`, `clear_transient` | Confident | ui_common.py:321-355; catalog_tui.py:825-837 |
| First-entry status: mount timing vs a base-class stash | Unclear | wizard_app.py:1172-1186 |
| One coalescing `request_refresh`; direct `state_refreshed` call on publish | Likely → best | catalog_tui.py:404-469; wizard_app.py:1531-1550, 2978-3000 |
| `…` during removal: global invalidate vs in-flight set | Unclear | 19 D-02/D-03; wizard_app.py:1485-1508 |
| Removal worker plus in-flight guard plus `finally` message | Confident | wizard_app.py:1442-1529 (UI thread today, F16); idiom at :2062-2071, :2613-2650 |
| Quit waits for the removal worker | Unclear → best | textual/app.py:3737-3752 (no wait at shutdown) |
| Removal words in 20's `WORDS` | Likely → best | wizard_app.py:1552-1597 |
| Policies `enter_view` re-reads `is_active`; DRIFT = owned ∧ ¬active | Confident | wizard_app.py:1600-1652; policy.py:132-164, 716-717, 1250 |
| pnpm findings → `reasons`; smoke via Doctor | Unclear → best | wizard_app.py:495-500; TA §7 |
| Link pick → Doctor `enter_view()` | Likely → best | wizard_app.py:2759-2788, 417-433 |
| `reload`/`selected_ids` prune non-selectable ids | Confident | tool_browser.py:204-220, 325-331 |
| Forks deleted in the same wave | Confident | ownership.py:1465,1511; setup.py:860 |

## jev screening

One Laya call per item, then TypeSafe direct (`jev-latest` → `jev-1.13.0`). Summaries only.

| Item | Laya | TypeSafe | Outcome |
|---|---|---|---|
| `…` during removal | bump_generation p=0.65 (needs fallback) | bump_generation p=0.56 (needs fallback) | Asked the user: per-tool, via `mark_pending` (D-09) |
| Doctor smoke result | doctor_renders_own p=0.58 (needs fallback) | evidence_cache p=0.92 | D-13 |
| Quit during removal | await_worker p=0.77 | await_worker p=0.99 | D-10 |
| First-entry status | render_only_in_enter_view p=0.54 (needs fallback) | render_only_in_enter_view p=0.97 | D-04 |

## Corrections Made

### Removal `…` signal
- **Recommended:** bump the generation when the removal starts (whole catalog `…`).
- **User choice:** the per-tool option ("Yo no me preocuparia por los otros tiers … tomaria la segunda opción").
- **How it is built without a second renderer signal:** `mark_pending(ids)` drops only those ids from the published map in the same generation, so `state_of` stays the only input (D-09).
- **Deferred:** the user would expect the screen to stay put during a removal (block navigation), "aunque no es un requisito por ahora".

## Side decision in this session (not Phase 21 scope)
- The cross-AI executor was changed to `pi -p --model router-env/my-coding --no-session` (`workflow.cross_ai_command`). User: "Deberia ser pi usando el modelo router-env/my-coding". A stdin probe returned `PI_OK`.

## Folded Todos
- Dangling pnpm global shims in Doctor (0.9) → D-13.
