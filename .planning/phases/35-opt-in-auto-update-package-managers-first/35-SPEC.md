# Phase 35: Opt-in auto-update, package managers first — Specification

**Created:** 2026-11-19
**Ambiguity score:** 0.18 (gate: ≤ 0.20)
**Requirements:** 10 locked

## Goal

A user who opts in gets their tools updated on a schedule in a safe order — package managers first, then the tools that depend on them — with nothing updated twice a day, nothing run as root, and no tool updated after its manager failed.

## Background

- Schedules (`installer/schedules.py`) hold a closed tuple of `Schedule(id, label, kind, target, default_interval, default_start)` rows; every row is on by default when its target is installed, and a recorded user decision is never changed by the installer (24.2 SPEC SCHED-01, `.planning/milestones/v0.50.0-phases/24.2-schedules-view/24.2-SPEC.md:61`). There is no per-row default today; the owner approved a per-row `default_on = False` at the 2026-11-19 ingest gate (amended below).
- `installer/resolve.py:15` `_RANK` ranks install **method kinds** (brew and cask 5, bun 6, node 7, script 10, github_release, uv-tool, sdkman, tarball and app 20, cargo_distrobox 25, dnf, apt, pacman 30, rpm_ostree 35); it has no `volta` key and ranks `sdkman` after `script`. The owner named brew, sdkman, bun and volta as the managers to update first. Which ordering source implements "managers first" (`_RANK` as the roadmap says, or an explicit manager order) is a discuss decision; the observable order is specified here.
- Reusable pieces: `UpdateService` (`installer/update.py:580`), `update_refusal(tool, ownership)` (`:283`), `CHILD_ENV` with `HOMEBREW_NO_SUDO` (`installer/run.py:50`), the run lock (`installer/runlock.py`, used by `schedule_run.run_schedule`), `deps.resolve_dependencies` (`installer/deps.py:40`), and the `check-updates` runner and notifier from phase 34.
- Five per-tool agent-CLI update rows exist (`update-claude`, `-opencode`, `-pi`, `-cursor-agent`, `-copilot`), each default interval 6 h.
- Research: `.planning/research/2026-11-17-update-automation.md` (feature 2); an unverified item is whether `uv self update` is safe while the runner runs under `uv run`.
- The owner's request (2026-11-17): a policy the user can activate that updates package managers first (brew, sdkman, bun, volta, ...) and then the other tools that depend on them. Doctrine: a Schedules row, never a Policies row.

## Requirements

1. **Opt-in `update-all` row (AUTOUPD-01)**: Schedules has an `update-all` row that is off by default and is never a Policies row; once the user sets it, the installer never changes it on its own.
   - Current: every schedule seeds on; no per-row default.
   - Target: a per-row default (`default_on=False` for `update-all`) honored by seeding, with recorded decisions untouched.
   - Acceptance: a fresh scratch HOME seeds `update-all` off and every other row as before (existing seeding tests unedited); no Policies row exists for it; after the user turns it on, a re-seed or reconfigure leaves it on, and after the user turns it off, leaves it off.

2. **Managers first (AUTOUPD-02)**: `update-all` updates package managers first, then their dependents grouped by owner and ordered by `deps.resolve_dependencies`; the ordering source for managers is chosen in discuss and covers brew, bun, uv, sdkman and Volta where installed.
   - Current: no such runner; `_RANK` ranks method kinds, not manager update order.
   - Target: a pure planner that turns the installed tools into an ordered list of managers and dependent groups.
   - Acceptance: a unit test with brew, uv and two dependents asserts the order (managers first, dependents grouped by owner, ordered by dependency); a second test with bun and sdkman asserts the same rule; the planner is a pure function over fixtures.

3. **Skip dependents of a failed manager (AUTOUPD-03)**: When a manager's update fails, each of its dependents is skipped and logged as skipped.
   - Current: n/a.
   - Target: the runner records the failure and skips by owner.
   - Acceptance: a fake manager that fails produces one `skipped: <manager> failed` line per dependent and zero update calls for them; dependents of a manager that succeeded still run.

4. **Reuse the safe update path (AUTOUPD-04)**: `update-all` reuses `UpdateService`, `update_refusal`, closed-stdin children, `HOMEBREW_NO_SUDO` and the run lock; refused tools are skipped with their reason, a held lock makes the run refuse instead of overlapping, and no path runs sudo, pkexec or doas.
   - Current: the pieces exist for the per-tool rows.
   - Target: the runner composes them without a second update implementation.
   - Acceptance: a test with refused tools (native owner, SDKMAN, Volta, pins, os-package) shows each skipped with its refusal text; a held-lock test returns `skipped: busy`; a grep test finds no `sudo`, `pkexec` or `doas` spawn in the new code; the children's environment contains `HOMEBREW_NO_SUDO=1` and a closed stdin.

5. **Casks excluded by default on macOS (AUTOUPD-05)**: Brew casks are excluded from `update-all` on macOS by default.
   - Current: n/a.
   - Target: casks are filtered out of the plan unless the owner later allows them (a future requirement).
   - Acceptance: a macOS fixture with a cask and a formula plans only the formula; the cask appears in the plan output as `skipped: cask excluded`.

6. **Run log and summary line (AUTOUPD-06)**: An `update-all` run writes one run-log line per tool while the shared schedule log keeps one summary line per schedule id.
   - Current: the shared log has one line per schedule.
   - Target: a per-run log of tool lines plus the summary line.
   - Acceptance: a run over three tools leaves three tool lines in the run log and exactly one `update-all` line in the shared schedule log.

7. **Updated at most once a day (AUTOUPD-07)**: A tool also covered by a per-tool agent-CLI schedule row is updated at most once per day across both rows.
   - Current: the per-tool rows run every 6 h independently.
   - Target: a per-tool last-updated record both runners consult.
   - Acceptance: with `update-claude` having updated a tool today, `update-all` skips it as `skipped: updated today`; the reverse holds; the next calendar day both may run.

8. **Container end-to-end (AUTOUPD-08)**: `update-all` is exercised end to end in a disposable container (never on the developer host), and whether `uv self update` is safe under `uv run` is verified there.
   - Current: unverified.
   - Target: a recorded container run of the plan and a real run on tools installed in the container.
   - Acceptance: a container log shows the plan, the order and the per-tool results; the `uv self update` finding is recorded in the phase verification with the command output; the container is removed afterwards.

9. **Plan-only mode (added by the interview)**: `--run-schedule update-all --plan` prints what would be updated, in what order and what would be skipped with reasons, and changes nothing.
   - Current: n/a.
   - Target: a plan output from the same planner the real run uses.
   - Acceptance: the plan output equals the order and skip reasons of a real run on the same fixture; a spy on the update executor shows zero calls in plan mode.

10. **Notification after a run (added by the interview)**: After an `update-all` run that updated or skipped anything, one desktop notification summarizes the result through the phase 34 notifier.
    - Current: n/a.
    - Target: the notifier is called once with counts.
    - Acceptance: a run that updated two tools and skipped one sends one notification with those counts (fake notifier); a run with nothing to do sends none; a notifier failure logs `notify skipped` and the run still exits ok.

## Boundaries

**In scope:**
- The `update-all` row with a per-row default, the planner, the runner with skip rules, the plan-only mode, the run log, the once-a-day rule, the post-run notification, unit templates for both OSes, and a container end-to-end run.
- Recording the 24.2 SCHED-01 amendment (below).

**Out of scope:**
- Updating macOS casks by default — excluded; allowing them is a future requirement.
- Removing or merging the five per-tool agent-CLI rows — both stay and duplicates are skipped.
- Running anything with sudo, pkexec or doas, or `softwareupdate` — zero-sudo rule.
- A Policies row or a TUI question for this feature — doctrine: a Schedules row.
- Real-Mac checks — UAT lines deferred to the owner's Mac.

## Constraints

- Opt-in only: a fresh install never runs `update-all`.
- Container runs only in disposable containers (`scripts/detect-container-runtime.sh`), removed afterwards; tests use a scratch HOME and fakes; never the developer host.
- The runner changes the host's tools only when the user opted in; plan-only mode and tests change nothing.
- `make validate && make test` pass on the commit.

## Amendment of Phase 24.2

*(amended 2026-11-19, 35 D-01: SCHED-01 "a schedule is on by default" gains a per-row default; `update-all` seeds off; the rule that the installer never changes a recorded user decision is unchanged. Owner-approved at the 2026-11-19 ingest gate.)* The statement amended is `24.2-SPEC.md:61`.

## Acceptance Criteria

- [ ] A fresh scratch HOME seeds `update-all` off, with no Policies row, and a user's choice is never changed.
- [ ] The planner test asserts managers first, dependents grouped by owner and ordered by dependency (brew, uv, bun, sdkman fixtures).
- [ ] A failed manager yields one skip line per dependent and no update call for them.
- [ ] Refused tools are skipped with their reason; a held lock refuses; no sudo, pkexec or doas appears in the new code.
- [ ] macOS casks are excluded by default and shown as skipped in the plan.
- [ ] One run-log line per tool and one shared-log summary line.
- [ ] A tool covered by both runners is updated at most once a day.
- [ ] The container log shows the plan, the order and the results, with the `uv self update` finding recorded.
- [ ] Plan-only mode matches a real run's order and changes nothing.
- [ ] One summary notification per non-empty run; none for an empty run; a notifier failure never fails the run.

## Edge Coverage

**Coverage:** 51/51 applicable edges resolved · 0 unresolved

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| adjacency | R1 | ✅ covered | Acceptance 1: the per-row default affects only update-all; the seven existing rows seed exactly as before (existing seeding tests unedited) |
| empty | R1 | ✅ covered | Acceptance 1: a host with no tools installed still seeds update-all off and runs nothing |
| ordering | R1 | ✅ covered | Acceptance 2: the order is deterministic (managers, then dependents grouped by owner, ties by tool id) and asserted by the planner test |
| idempotency | R1 | ✅ covered | Acceptance 1: re-seeding twice leaves a user's on or off decision unchanged |
| concurrency | R1 | 🧪 backstop | held-out test: a second run while the run lock is held returns `skipped: busy` and changes nothing |
| adjacency | R2 | ✅ covered | Acceptance 2: two managers of equal standing are ordered by tool id, so the plan is deterministic |
| empty | R2 | ✅ covered | Acceptance 2: no managers or no dependents installed gives an empty or managers-only plan, never an error |
| ordering | R2 | ✅ covered | Acceptance 2: the order is deterministic (managers, then dependents grouped by owner, ties by tool id) and asserted by the planner test |
| idempotency | R2 | ✅ covered | Acceptance 7: a second run the same day skips tools already updated; plan mode never changes state |
| concurrency | R2 | 🧪 backstop | held-out test: a second run while the run lock is held returns `skipped: busy` and changes nothing |
| adjacency | R3 | ✅ covered | Acceptance 3: a dependent owned by two managers is skipped when either failed and the line names the failed one |
| empty | R3 | ✅ covered | Acceptance: nothing to update gives an empty plan, `ok: 0 updated`, an empty run log and no notification |
| ordering | R3 | ✅ covered | Acceptance 2: the order is deterministic (managers, then dependents grouped by owner, ties by tool id) and asserted by the planner test |
| idempotency | R3 | ✅ covered | Acceptance 7: a second run the same day skips tools already updated; plan mode never changes state |
| concurrency | R3 | 🧪 backstop | held-out test: a second run while the run lock is held returns `skipped: busy` and changes nothing |
| adjacency | R4 | ✅ covered | Acceptance: planner fixtures include tools of equal rank, ties broken by tool id (asserted in the planner test) |
| empty | R4 | ✅ covered | Acceptance: nothing to update gives an empty plan, `ok: 0 updated`, an empty run log and no notification |
| encoding | R4 | ✅ covered | Acceptance 4: refusal text and the child environment value `HOMEBREW_NO_SUDO=1` are compared as exact strings |
| ordering | R4 | ✅ covered | Acceptance 2: the order is deterministic (managers, then dependents grouped by owner, ties by tool id) and asserted by the planner test |
| idempotency | R4 | ✅ covered | Acceptance 7: a second run the same day skips tools already updated; plan mode never changes state |
| concurrency | R4 | 🧪 backstop | held-out test: a second run while the run lock is held returns `skipped: busy` and changes nothing |
| adjacency | R5 | ✅ covered | Acceptance: planner fixtures include tools of equal rank, ties broken by tool id (asserted in the planner test) |
| empty | R5 | ✅ covered | Acceptance: nothing to update gives an empty plan, `ok: 0 updated`, an empty run log and no notification |
| ordering | R5 | ✅ covered | Acceptance 2: the order is deterministic (managers, then dependents grouped by owner, ties by tool id) and asserted by the planner test |
| idempotency | R5 | ✅ covered | Acceptance 7: a second run the same day skips tools already updated; plan mode never changes state |
| concurrency | R5 | 🧪 backstop | held-out test: a second run while the run lock is held returns `skipped: busy` and changes nothing |
| adjacency | R6 | ✅ covered | Acceptance: planner fixtures include tools of equal rank, ties broken by tool id (asserted in the planner test) |
| empty | R6 | ✅ covered | Acceptance: nothing to update gives an empty plan, `ok: 0 updated`, an empty run log and no notification |
| ordering | R6 | ✅ covered | Acceptance 2: the order is deterministic (managers, then dependents grouped by owner, ties by tool id) and asserted by the planner test |
| idempotency | R6 | ✅ covered | Acceptance 7: a second run the same day skips tools already updated; plan mode never changes state |
| concurrency | R6 | 🧪 backstop | held-out test: a second run while the run lock is held returns `skipped: busy` and changes nothing |
| adjacency | R7 | ✅ covered | Acceptance 7: a tool covered by both an agent-CLI row and update-all is updated once; a tool covered by only one runs normally |
| empty | R7 | ✅ covered | Acceptance: nothing to update gives an empty plan, `ok: 0 updated`, an empty run log and no notification |
| ordering | R7 | ✅ covered | Acceptance 2: the order is deterministic (managers, then dependents grouped by owner, ties by tool id) and asserted by the planner test |
| idempotency | R7 | ✅ covered | Acceptance 7: a second run the same day skips as `updated today`; the next calendar day both may run |
| concurrency | R7 | 🧪 backstop | held-out test: a second run while the run lock is held returns `skipped: busy` and changes nothing |
| adjacency | R8 | ✅ covered | Acceptance: planner fixtures include tools of equal rank, ties broken by tool id (asserted in the planner test) |
| empty | R8 | ✅ covered | Acceptance 8: a container with no installed tools runs the plan and logs an empty plan, not a failure |
| ordering | R8 | ✅ covered | Acceptance 2: the order is deterministic (managers, then dependents grouped by owner, ties by tool id) and asserted by the planner test |
| idempotency | R8 | ✅ covered | Acceptance 7: a second run the same day skips tools already updated; plan mode never changes state |
| concurrency | R8 | 🧪 backstop | held-out test: a second run while the run lock is held returns `skipped: busy` and changes nothing |
| adjacency | R9 | ✅ covered | Acceptance: planner fixtures include tools of equal rank, ties broken by tool id (asserted in the planner test) |
| empty | R9 | ✅ covered | Acceptance: nothing to update gives an empty plan, `ok: 0 updated`, an empty run log and no notification |
| ordering | R9 | ✅ covered | Acceptance 2: the order is deterministic (managers, then dependents grouped by owner, ties by tool id) and asserted by the planner test |
| idempotency | R9 | ✅ covered | Acceptance 9: plan mode is read-only, so repeating it prints the same plan and changes nothing |
| concurrency | R9 | 🧪 backstop | held-out test: a second run while the run lock is held returns `skipped: busy` and changes nothing |
| adjacency | R10 | ✅ covered | Acceptance: planner fixtures include tools of equal rank, ties broken by tool id (asserted in the planner test) |
| empty | R10 | ✅ covered | Acceptance: nothing to update gives an empty plan, `ok: 0 updated`, an empty run log and no notification |
| ordering | R10 | ✅ covered | Acceptance 2: the order is deterministic (managers, then dependents grouped by owner, ties by tool id) and asserted by the planner test |
| idempotency | R10 | ✅ covered | Acceptance 7: a second run the same day skips tools already updated; plan mode never changes state |
| concurrency | R10 | 🧪 backstop | held-out test: a second run while the run lock is held returns `skipped: busy` and changes nothing |

## Prohibitions (must-NOT)

**Coverage:** 3/3 applicable prohibitions resolved · 0 unresolved

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| `update-all` MUST NOT run on a fresh install or be re-enabled by the installer after the user turned it off | 1 | resolved | test: seeding and reconfigure fixtures |
| No code path of `update-all` MUST run sudo, pkexec or doas or update a tool whose refusal says it cannot be updated | 4 | resolved | test: grep over the new code and a refused-tool fixture |
| `update-all` MUST NOT update a dependent after its manager's update failed | 3 | resolved | test: failing-manager fixture with a spy on the executor |

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes |
|--------------------|-------|------|--------|-------|
| Goal Clarity       | 0.90  | 0.75 | ✓      | Owner request, roadmap and research agree |
| Boundary Clarity   | 0.85  | 0.70 | ✓      | Both stages in one phase; casks excluded; both runners stay |
| Constraint Clarity | 0.70  | 0.65 | ✓      | Manager ordering source and per-tool last-updated store left to discuss |
| Acceptance Criteria| 0.80  | 0.70 | ✓      | Pure planner plus a container end-to-end run |
| **Ambiguity**      | 0.18  | ≤0.20| ✓      | |

## Interview Log

Auto path, one round. The open items went through jev: one advisory answer per item, and `needs_fallback` items are decided by own reasoning. Summaries only, advisory. Rule: mvp-mode inactive, the best design wins over the smallest diff.

| Round | Perspective | Question summary | jev (advisory) | Decision locked |
|-------|-------------|------------------|----------------|-----------------|
| 1 | Simplifier | OQ-AUTOUPD-2: managers only now or both stages in this phase? | low 0.47 (both_stages_one_phase); second rung choice both_stages_one_phase 0.97 | Both stages in this phase (R2, R3) |
| 1 | Boundary Keeper | OQ-AUTOUPD-5: notify after an auto-update run? | noul yes 0.74 | Yes, through the phase 34 notifier (R10) |
| 1 | Researcher | OQ-AUTOUPD-6: plan-only mode? | noul yes 0.87 | Yes (R9) |
| 1 | Boundary Keeper | OQ-AUTOUPD-1, -3, -4 (opt-in, keep both runners, casks excluded) | none | Locked by AUTOUPD-01, -07 and -05 as written (R1, R7, R5) |

---

*Phase: 35-opt-in-auto-update-package-managers-first*
*Spec created: 2026-11-19*
*Next step: /gsd-discuss-phase 35 — implementation decisions (how to build what's specified above)*
