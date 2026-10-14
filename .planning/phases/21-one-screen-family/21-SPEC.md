# Phase 21: One screen family — Specification

**Created:** 2026-10-13
**Ambiguity score:** 0.17 (gate: ≤ 0.20)
**Requirements:** 9 locked

## Goal

Every screen shows the current truth after any mutation. Uninstall, Policies and Doctor become projections of the shared `ToolState` and follow the same lifecycle as the catalog tiers.

## Background

Scouted 2026-10-13 (`installer/wizard_app.py` unless noted):
- **Forked lifecycle.**
  - Views mount on their own: `on_mount` at :411, :1164 and :1659.
  - `show_view` (:2676) and `_navigable` (:2720) treat some screens differently from others (G R2 forks 1–10).
  - `AppScreen` (`ui_common.py:321`) already has `enter_view` (:337).
- **Patched status.** Uninstall keeps a `_pending_status` (:952, :1165–1186) to survive its own first entry. It also runs a `_resync` (:1238) with precedence rules.
- **Messages instead of state.** `OwnershipRefreshed` (`catalog_tui.py`, handled at :2978, posted at :1550) is how screens learn about changes. Each screen has its own worker.
- **Stale views.**
  - Policies does not re-read `is_active()` on entry (F3, F8, AR-08).
  - Doctor has a hidden `a` binding (:292, F17).
  - A dangling pnpm global shim is a Doctor finding, not a tool state (todo 2026-09-16).
  - The first-run link pick leaves Doctor stale (B 13 WR-04).
  - On macOS, the prune policy reads as ON even without its plist (A #7).
- **Phases 19 and 20 provide the input.** Phase 19 delivers `ToolState`, `state_of`, the one-swap refresh and `health_cell`. Phase 20 delivers the install plan and its summary.

## Requirements

1. **Neutral root and one show path (UI-01, UI-02)**: All six views are installed once, on top of an empty, non-navigable root `Screen`.
   - Current: Some views are pushed and some are the default screen; `_navigable` has special cases.
   - Target:
     - `show_view` calls `leaving.clear_transient()` for any `AppScreen`, pops the view on top, pushes the target, and then calls `enter_view()`.
     - `_navigable` is `self.screen in self._views.values()`.
   - Acceptance: A test records the call order for each of the six views: clear → push → enter. Pressing the key of the current view changes nothing.

2. **One refresh owner, full catalog (UI-01)**: Every mutation (install close, `u` on any tier, an Uninstall removal, a Policies toggle, Doctor `r`) ends by asking the app-level worker for one full-catalog pass.
   - Current: Per-screen refreshes and messages.
   - Target:
     - Rows show `…` until the pass publishes (O9).
     - A visible view re-renders when the pass publishes, and a hidden view renders the published state on its next `enter_view`.
     - Entering a view starts no new pass.
   - Acceptance: A matrix test crosses each source mutation with each target view (system, user, ai, Uninstall, Policies, Doctor). The new state appears on the target's next entry, and immediately when the target is visible.

3. **Status lifecycle (UI-02)**: A status written during a view's first entry stays visible. Every view clears its transient status on leave.
   - Current: `_pending_status` in Uninstall only.
   - Target: `clear_transient()` defaults to `self.status.clear()`, and `enter_view` never clears a status written during that entry.
   - Acceptance: Each view's first entry keeps a status written during entry. Leaving and re-entering shows no stale status.

4. **Uninstall is a projection (UI-03)**: Uninstall reads `ToolState` and groups the tools.
   - Current: `classify_tools` and its closures, plus `_resync` precedence.
   - Target:
     - **Removable:** `removable.level` is set. The proof (receipt, adoption or archive layout) and the environment levers are shown.
     - **Managed elsewhere:** present with no proof, shown with `removable.hint`. A broken row says "reinstall it from the catalog to repair; nothing to remove here".
     - **Nothing to do:** missing or unavailable.
     - A Health column uses `health_cell`.
     - An unknown owner is never attributed to a manager.
   - Acceptance:
     - Fixtures cover each group.
     - A tool with an unknown owner shows no manager name or command.
     - A broken row shows the repair text.
     - With nothing installed, the screen shows only the third group and its message.

5. **Removal on a worker (UI-05, F16)**: A removal runs on a worker and shows "Removing…".
   - Current: The removal runs on the UI thread.
   - Target:
     - The user may navigate away while it runs.
     - The tools being removed show `…` on every tier.
     - A second removal is refused with a status until the first one finishes.
     - Quitting waits for the worker to finish.
     - Afterwards the tool moves to "nothing to do" and every tier shows `○`.
     - A removed policy ban reads OFF in Policies on its next entry.
   - Acceptance: With a held fake remover, the UI stays responsive, navigation works, and a second removal is refused. When the remover is released, the tool sits under "nothing to do", `○` shows on every tier, and the ban is OFF in Policies.

6. **Prune stale selections (UI-08, F4)**: `ToolBrowser.reload` drops selected ids that are no longer selectable, and `selected_ids` returns only selectable ids.
   - Current: Stale ids survive a reload (999.1(a)).
   - Acceptance: A tool that is selected, then removed or made unavailable, is no longer selected after reload, and its id is never passed to execute.

7. **Policies read live truth (UI-06)**: `PoliciesScreen.enter_view` re-reads `is_active()`.
   - Current: Values are cached from mount.
   - Target:
     - Missing prerequisites are computed from `state_of`.
     - DRIFT means owned and not active.
     - On macOS, the prune policy is ON only when its plist exists (A #7).
   - Acceptance:
     - Installing `watch` unblocks the docker tweak on the next entry.
     - A policy owned but deactivated outside the app shows DRIFT.
     - A macOS fixture without the plist reads OFF.

8. **Doctor on the same lifecycle (UI-07)**: Doctor renders from `enter_view`. The hidden `a` binding is deleted.
   - Current: Doctor computes its own state.
   - Target:
     - pnpm findings (missing, unhealthy, incomplete global shims) become `ToolState.reasons`, so a dangling shim shows `!` on its tier.
     - The first-run link-mode pick re-renders Doctor (B 13 WR-04).
   - Acceptance:
     - Pressing `a` in Doctor does nothing.
     - A dangling pnpm shim fixture shows `!` with its reason on the tier and in Doctor.
     - After the first-run link pick, Doctor shows the chosen mode without a restart.

9. **Forks deleted**: The parallel refresh paths are removed.
   - Current: `OwnershipRefreshed`, `_pending_status`, the `_resync` precedence machinery, `classify_tools` closures, `_own_script_install` and the per-screen workers.
   - Target: Views read only `state_of` and the published generation.
   - Acceptance: A grep test finds none of `OwnershipRefreshed`, `_pending_status` or `_own_script_install` in `installer/`. The full suite stays green.

## Boundaries

**In scope:**
- Neutral root, `show_view`/`_navigable`, the default `enter_view`/`state_refreshed`/`clear_transient` in `AppScreen`
- One app-level refresh request after every mutation; re-render on publish
- Uninstall projection with the Health column; the removal worker; pruning
- Policies `enter_view`, live prerequisites, DRIFT, macOS prune truth
- Doctor lifecycle, deleting `a`, pnpm findings → reasons, re-render after the link pick
- Deleting the forks listed in requirement 9

**Out of scope:**
- "Delete config too" (UI-04) — Phase 22, because it needs `config_paths` (LIFE-04)
- Script `remove`/`update` recipes and level-1 manager removal — Phase 22
- Hook-based reconfigure and receipt hooks — Phase 23
- Replacing the three tier instances or the six number keys (kept per TA §7)
- A `RowsScreen` base class (cut; `AppScreen` defaults cover it)
- Cancelling a removal mid-way

## Constraints

- One refresh worker for the whole app. No view starts its own pass, and the pass adds no network calls (Phase 19: 4.5–5.7 s for 90 tools).
- Keep three tier instances and the six number keys.
- Legend and review widths stay within the existing 78-column tests.
- Zero sudo. Tests use a scratch HOME and fake removers. Nothing is removed on the host.

## Acceptance Criteria

- [ ] For each of the six views, `show_view` calls clear → push → enter in that order; pressing the current view's key does nothing
- [ ] Matrix: each source mutation × each target view shows the new state on the next entry, and immediately when visible
- [ ] Entering a view starts no new refresh pass
- [ ] Each view's first entry keeps a status written during entry; leaving clears it
- [ ] Uninstall fixtures show the three groups; an unknown owner names no manager; a broken row shows the repair text; with nothing installed, only "nothing to do" and its message show
- [ ] With a held remover, the UI stays responsive, navigation works and a second removal is refused; after release, "nothing to do", `○` on every tier, and the ban OFF in Policies
- [ ] Quitting during a removal waits for the worker
- [ ] A selected tool that becomes unselectable is pruned and never reaches execute
- [ ] Installing `watch` unblocks the docker tweak; an owned but inactive policy shows DRIFT; a macOS fixture without the plist reads OFF
- [ ] Doctor `a` does nothing; a dangling pnpm shim shows `!` with its reason; the first-run link pick re-renders Doctor
- [ ] No `OwnershipRefreshed`, `_pending_status` or `_own_script_install` in `installer/`; the suite is green

## Edge Coverage

**Coverage:** 19/19 applicable edges resolved · 0 unresolved

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| adjacency | R1 | ✅ covered | Pressing the current view's key changes nothing (AC 1) |
| empty | R1 | ✅ covered | At launch the root is empty; the system tier is shown through the same `show_view` path (AC 1) |
| ordering | R1 | ✅ covered | clear → push → enter, recorded per view (AC 1) |
| adjacency | R2 | ✅ covered | Two mutations back to back: the newest pass publishes (Phase 19 one-swap; AC 2) |
| empty | R2 | ✅ covered | A refused mutation still ends with one pass; rows are unchanged (AC 2) |
| ordering | R2 | ✅ covered | The pass is requested after the mutation completes, never before (AC 2) |
| idempotency | R2 | ✅ covered | Re-entering a view starts no pass (AC 3) |
| concurrency | R2 | 🧪 backstop | A mutation during a running pass supersedes it; the older result is discarded (Phase 19 barrier; held-out test) |
| adjacency | R3 | ✅ covered | A status written during entry, then an immediate leave: cleared (AC 4) |
| empty | R3 | ✅ covered | A view with no status: clear is a no-op (AC 4) |
| ordering | R3 | ✅ covered | The entry-written status survives the entry render (AC 4) |
| empty | R4 | ✅ covered | Nothing installed → only "nothing to do" and its message (AC 5) |
| encoding | R4 | ✅ covered | An unknown owner label → no manager name or command (AC 5) |
| unclassified | R5 | ✅ covered | Held remover, navigation, second removal refused (AC 6) |
| unclassified | R5 | 🧪 backstop | Quit during a removal waits for the worker (AC 7; held-out test) |
| unclassified | R6 | ✅ covered | Removed or unavailable → pruned, never executed (AC 8) |
| unclassified | R7 | ✅ covered | `watch` prerequisite, DRIFT, macOS plist fixture (AC 9) |
| unclassified | R8 | ✅ covered | `a` inert, pnpm shim `!`, link pick re-render (AC 10) |
| empty | R9 | ✅ covered | The grep finds zero matches (AC 11) |

## Prohibitions (must-NOT)

**Coverage:** 4/4 applicable prohibitions resolved · 0 unresolved

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| MUST NOT attribute an unknown owner to a manager or print a removal command for it | R4 | resolved | test: the unknown-owner fixture has no manager name or argv |
| MUST NOT start a refresh pass from a view's entry | R2 | resolved | test: a spy on the worker counts zero passes per entry |
| MUST NOT run a second removal while one is in progress | R5 | resolved | test: the held remover; the second request is refused |
| MUST NOT pass an unselectable id to execute | R6 | resolved | test: the pruned id is absent from the execute inputs |

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes |
|--------------------|-------|------|--------|-------|
| Goal Clarity       | 0.90  | 0.75 | ✓      | One lifecycle, one refresh owner |
| Boundary Clarity   | 0.82  | 0.70 | ✓      | UI-04 → 22, hooks → 23; RowsScreen cut |
| Constraint Clarity | 0.72  | 0.65 | ✓      | One worker, no network, keep tiers and keys |
| Acceptance Criteria| 0.84  | 0.70 | ✓      | 11 pass/fail criteria including the matrix |
| **Ambiguity**      | 0.17  | ≤0.20| ✓      | |

## Interview Log

`--auto`: the initial ambiguity of 0.17 was under the gate, so the interview was skipped. Open decisions were screened with jev-fast-decision. Each one first went to local Laya (`system-one` on 127.0.0.1:8010, one call per question). Questions where Laya's confidence was low were then re-asked through TypeSafe direct (`jev-latest`, which answers as `jev-1.13.0`). Zen was unavailable: 401 with the old keys, and 429 "Policy budget exceeded" with the new key, including on `jev-1.13-free`. Every answer is advisory, and the final decision is recorded below.

| Round | Perspective     | Question summary | Laya (advisory) | TypeSafe (advisory) | Decision locked |
|-------|-----------------|------------------|-----------------|---------------------|-----------------|
| auto | Researcher      | What does a refresh after a mutation cover? | full_catalog p=0.47 (needs fallback) | mutated_first_then_full p=0.63 (needs fallback) | Full catalog. A partial pass would bring back the merged-map race that Phase 19 removes with its one swap |
| auto | Failure Analyst | Can the user navigate during a removal? | allow_navigation p=0.56 (needs fallback) | allow_navigation p=0.84 | Allowed; affected rows show `…`; a second removal is refused; quit waits |
| auto | Boundary Keeper | Include the link-pick re-render (WR-04) and macOS prune truth (A #7)? | defer p=0.72 | include p=1.00 | **Include.** TA §8.1 maps both only to this phase, so deferring them would orphan them |
| auto | Failure Analyst | Edge table and prohibitions | – | – | All resolved as covered or backstop; none dismissed |

---

*Phase: 21-one-screen-family*
*Spec created: 2026-10-13*
*Next step: /gsd-discuss-phase 21 — implementation decisions (how to build what's specified above)*
