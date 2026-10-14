# Phase 20: Install plan with dispositions — Specification

**Created:** 2026-10-13
**Ambiguity score:** 0.17 (gate: ≤ 0.20)
**Requirements:** 9 locked

## Goal

Before anything runs, the user sees what will happen to each selected and dragged tool. The TUI and headless runs then execute that same plan and report honest outcomes in the same words.

## Background

Scouted 2026-10-13:
- **Two orderings, no plan.** The order comes from `order_for_install` (`installer/session.py:116`). The review in `execute_screen.py` classifies the selection on the fly (`_classify_selection` :499, `_update_targets` :531, `_preflight_prompt` :1008), and headless has its own path (`app.py:127` `run_wizard`, `render_audit` :163, `render.py:48`). No single object says what each row will do.
- **Current tools re-run or vanish.** There is no `r` reinstall. Present dependencies that get dragged in are not shown under their dependent (999.1, G R4).
- **Selection is lost.** After a run the selection clears whatever the outcome (B 13 WR-03).
- **Headless exit code.** It does not come from row outcomes (B 13, B 14 IN-01).
- **False promise.** Two strings promise a migration that does not exist: "moving it there is not available yet" (`catalog_tui.py:923`, `update.py:296`; O8, B 16 D-04).
- **Phase 19 provides the input.** `ToolState`, `Health` and receipts arrive in Phase 19 and feed the dispositions.

## Requirements

1. **Plan with dispositions (PLAN-01)**: One `InstallPlan` is built from the selection and the `ToolState` map. It has one row per selected or dragged tool, and each row carries one disposition plus a reason.
   - Current: Classification happens inside the review screen. Dragged tools are not listed.
   - Target:
     - The dispositions are: will install, will update, will repair, will reconfigure, will be reinstalled, skipped, blocked.
     - Dragged dependencies are indented under their first dependent and listed once. A dragged present dependency reads "already present".
     - Row order follows `order_for_install`.
   - Acceptance: The G probe cases A–I are parametrized tests over `build_plan`, and the review renders the same rows on the system, user and ai tiers.

2. **Reinstall only on `r` (PLAN-02, O7)**: A current, installer-owned tool is planned as "skipped — already current (r: reinstall)". Pressing `r` on that row toggles it to "will be reinstalled".
   - Current: No `r`.
   - Target: `r` acts only on rows the installer owns (by receipt or adoption). On a tool owned by another manager, it keeps the row as "skipped — managed by <owner>" and shows that reason.
   - Acceptance: `r` toggles the row both ways. `r` on a dnf-owned row does not change the disposition.

3. **Repair and reconfigure (PLAN-03)**: Health maps to a disposition. A present tool that is broken becomes "will repair". One that is misconfigured becomes "will reconfigure". One that is outdated becomes "will update" when the installer or a user-level manager (brew, uv, pnpm) owns it, and "skipped — managed by <owner>" otherwise.
   - Current: Broken and misconfigured tools are not planned.
   - Target: For dragged dependencies, missing becomes "will install" and broken becomes "will repair". A dragged dependency that is outdated or misconfigured still satisfies its dependent, so it is "skipped — already present" with its health reason shown; only a direct selection updates or reconfigures it (amended 2026-10-14, user decision). A broken tool that the installer cannot act on (for example, it is owned by dnf and that would need sudo) becomes "blocked" with the reason.
   - Acceptance: There is a test for each health and owner pair. A broken dragged dependency appears under its dependent as "will repair".

4. **Summary in the review's words (PLAN-04, 999.1)**: The summary counts outcomes per disposition using the same words as the review, for example "2 installed, 1 updated, 3 skipped, 1 failed".
   - Current: The words and counts differ from the review.
   - Target: A single vocabulary table is shared by review, summary and headless output.
   - Acceptance: Every disposition and outcome word comes from that one table. A test checks that every review word has a matching summary word.

5. **Selection after a run (PLAN-05)**: After a run, rows that ended failed, blocked or not attempted stay selected. Rows that ended done or skipped are cleared. Pressing `esc` before the run starts keeps the whole selection.
   - Current: The selection is cleared on every run.
   - Target: Each row's outcome decides whether it stays selected. A worker crash marks the unfinished rows as not attempted.
   - Acceptance: After a mixed run, exactly the failed, blocked and not-attempted rows are still selected. `esc` from the review restores the previous selection unchanged.

6. **Headless shares the plan (PLAN-06)**: `--all` and `--categories` call the same `build_plan` and the same engine.
   - Current: A separate path with an unrelated exit code.
   - Target:
     - `--yes` runs every runnable row. It never turns a skipped row into a reinstall.
     - Without `--yes`, the plan is printed and the run asks for confirmation.
     - The exit code is 1 when any row ends failed or not attempted, and 0 otherwise.
     - Blocked and skipped rows are printed with their reasons and do not change the exit code.
   - Acceptance:
     - On a fixture host with one outdated brew tool, `--all --yes` updates it and exits 0.
     - An injected failing row exits 1.
     - An all-current host runs nothing and exits 0.

7. **Wait for state, never act stale (PLAN-07, O9)**: While a tool's state for the current generation is pending, its row shows "checking…". Pressing Enter on the review waits for the refresh, and `esc` cancels the wait with the selection kept.
   - Current: Enter acts on whatever state is cached.
   - Target: The plan is rebuilt from the published state before the engine starts. There is no timeout, because the refresh measured 4.5–5.7 s and `esc` is the user's way out. Headless waits for one synchronous pass.
   - Acceptance: With a held refresh, Enter shows the wait and starts nothing. Once the refresh is released, the plan is rebuilt and the run starts. `esc` during the wait returns to the review with the selection intact.

8. **No false migration promise (PLAN-08)**: No screen or CLI text promises moving a tool to its declared manager.
   - Current: The two strings above.
   - Target: Off-policy rows state the fact ("<real> owns this copy; the catalog installs it via <declared>") with no promise.
   - Acceptance: A grep test finds no "moving it there" in `installer/`. The off-policy reason still names both owners.

9. **`a` on a tier (new, auto decision)**: `a` selects every available tool on the tier. The plan then gives each tool its disposition, and nothing is ever planned as a reinstall.
   - Current: `a` re-runs current tools.
   - Target: Unavailable rows (dim) are not selected.
   - Acceptance: `a` on an all-current tier gives only skipped rows, starts nothing, and the summary reads "N skipped".

## Boundaries

**In scope:**
- `InstallPlan`, `build_plan`, the disposition enum and the shared vocabulary table
- Review rendering with dragged tools indented; the `r` toggle
- Health and owner → disposition mapping, including dragged dependencies
- Summary counts, keeping the selection after a run, `esc` before start
- Headless `--all`/`--categories`/`--yes` on the same plan and engine, with the exit code taken from outcomes
- Waiting with "checking…" before execution; removing the migration promise

**Out of scope:**
- `ToolState`, `Health`, receipts and adoption — Phase 19 (consumed here)
- Uninstall plans, Policies and the Doctor lifecycle screens — Phase 21
- Script `update`/`remove` recipes and level-3 removal — Phase 22
- Actually migrating an off-policy tool to its declared manager — not planned this milestone
- Hook-driven reconfigure steps — Phase 23

## Constraints

- One engine for TUI and headless, with no second ordering. `order_for_install` stays the only source of row order.
- No new network calls when building the plan; it reads only the published `ToolState`.
- Zero sudo. Rows that would need sudo are blocked, never escalated.
- The review stays within the existing 78-column test budget. Indented dragged rows must not wrap at 78 columns.
- Tests use fixture states and a scratch HOME. Nothing installs on the host.

## Acceptance Criteria

- [ ] G probe cases A–I pass as `build_plan` tests on the system, user and ai tiers
- [ ] missing → "will install"; current → "skipped — already current (r: reinstall)"; after `r` → "will be reinstalled"
- [ ] broken → "will repair"; misconfigured → "will reconfigure"; outdated brew → "will update"; outdated dnf → "skipped — managed by dnf"
- [ ] A dragged present dependency shows "already present", indented under its dependent and listed once
- [ ] `r` on a row owned by another manager does not change it
- [ ] A broken tool that would need sudo is "blocked" with the reason
- [ ] Every review word has a matching summary word from the one vocabulary table
- [ ] After a mixed run, only the failed, blocked and not-attempted rows stay selected; `esc` before start keeps the selection
- [ ] `--all --yes` on a fixture with one outdated brew tool updates it and exits 0; an injected failure exits 1; an all-current host exits 0 and runs nothing
- [ ] With a held refresh, rows show "checking…", Enter waits and starts nothing, and `esc` cancels the wait with the selection kept
- [ ] No "moving it there" string anywhere in `installer/`
- [ ] `a` on an all-current tier starts nothing and the summary reads "N skipped"

## Edge Coverage

**Coverage:** 18/18 applicable edges resolved · 0 unresolved

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| adjacency | R1 | ✅ covered | A dependency dragged by two selected tools is listed once, under its first dependent (AC 4) |
| empty | R1 | ✅ covered | An empty selection: Enter does nothing and the review shows "nothing selected" (case A of AC 1) |
| ordering | R1 | ✅ covered | Row order is `order_for_install`; ties keep catalog order (AC 1) |
| idempotency | R1 | ✅ covered | Re-running the same selection on an all-current host plans only skipped rows (AC 12) |
| concurrency | R1 | ✅ covered | The plan is rebuilt from the published state after the wait (AC 10) |
| unclassified | R2 | ✅ covered | `r` toggles both ways; foreign-owned rows refuse it (AC 2, AC 5) |
| unclassified | R3 | ✅ covered | One test per health and owner pair, including dragged dependencies and sudo → blocked (AC 3, AC 6) |
| unclassified | R4 | ✅ covered | Vocabulary parity test (AC 7) |
| unclassified | R5 | 🧪 backstop | A worker crash mid-run → unfinished rows not attempted and still selected (AC 8; held-out test) |
| adjacency | R6 | ✅ covered | A blocked row plus a done row → exit 0; a failed or not-attempted row → exit 1 (AC 9) |
| empty | R6 | ✅ covered | An all-current host → runs nothing, exit 0 (AC 9) |
| ordering | R6 | ✅ covered | Headless uses the same `build_plan` order as the TUI (AC 1, AC 9) |
| unclassified | R7 | ✅ covered | A held refresh: wait, release, `esc` (AC 10) |
| empty | R8 | ✅ covered | An off-policy row with an unknown declared manager shows only the real owner (AC 11) |
| encoding | R8 | ✅ covered | A literal ASCII grep over `installer/` (AC 11) |
| adjacency | R9 | ✅ covered | A tier mixing current and missing tools: only the missing ones are "will install" (AC 1) |
| empty | R9 | ✅ covered | `a` on an all-current tier → nothing runs (AC 12) |
| ordering | R9 | ✅ covered | `a` uses the same plan order (AC 1) |

## Prohibitions (must-NOT)

**Coverage:** 4/4 applicable prohibitions resolved · 0 unresolved

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| MUST NOT reinstall a current tool unless the user pressed `r` on that row (`a` and `--yes` never do) | R2, R6, R9 | resolved | test: `a` and `--all --yes` on an all-current host start nothing |
| MUST NOT start the engine on state from an older generation | R7 | resolved | test: with a held refresh, the engine is not called until release |
| MUST NOT escalate privileges for a repair or update | R3 | resolved | test: a sudo-needing row is blocked; there are no sudo, pkexec or doas calls in the plan path |
| MUST NOT show a migration promise | R8 | resolved | test: grep for "moving it there" finds nothing |

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes |
|--------------------|-------|------|--------|-------|
| Goal Clarity       | 0.90  | 0.75 | ✓      | One plan, same words, same engine |
| Boundary Clarity   | 0.80  | 0.70 | ✓      | State in 19, uninstall in 21, migration not planned |
| Constraint Clarity | 0.72  | 0.65 | ✓      | One ordering, no network, zero sudo, 78 columns |
| Acceptance Criteria| 0.86  | 0.70 | ✓      | 12 pass/fail criteria, G cases A–I |
| **Ambiguity**      | 0.17  | ≤0.20| ✓      | |

## Interview Log

`--auto`: the initial ambiguity of 0.17 was already under the gate, so the interview was skipped. The jev-fast-decision helper was enabled for this run but was unavailable (Zen returned `http_401`, and local Laya was not running), so I picked the recommended defaults without any jev input.

| Round | Perspective     | Question summary | Decision locked |
|-------|-----------------|------------------|-----------------|
| auto | Failure Analyst | What does Enter do while state is checking? | Wait, cancelable with `esc`, no timeout; never act on stale state (O9) |
| auto | Boundary Keeper | Which dispositions can `a` produce? | Every disposition except reinstall (TA §3.1) |
| auto | Researcher      | What does `--yes` repair, and what sets the exit code? | Every runnable row; rows needing sudo are blocked; exit 1 only on failed or not attempted |
| auto | Failure Analyst | Edge table and prohibitions | All resolved as covered or backstop; none dismissed |

---

*Phase: 20-install-plan-with-dispositions*
*Spec created: 2026-10-13*
*Next step: /gsd-discuss-phase 20 — implementation decisions (how to build what's specified above)*
