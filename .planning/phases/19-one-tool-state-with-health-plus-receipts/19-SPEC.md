# Phase 19: One tool state with health plus receipts — Specification

**Created:** 2026-10-13
**Ambiguity score:** 0.18 (gate: ≤ 0.20)
**Requirements:** 10 locked

## Goal

Every catalog view reads one `ToolState` per tool: present, health, owner, version and removability with proof. Every install, update and repair leaves an atomic receipt that is the proof used for removal.

## Background

Scouted 2026-10-13:
- **State is split.** `VersionRefreshService` (`version_status.py:423`) keeps separate status, ownership and skill maps (`statuses` :503, `ownership_of` :510, `skill_status_of` :531). A raced pass merges stale results (`_statuses.update` at :751, :761; `_ownership.update` at :768).
- **One broken mark only.** `catalog_tui.py` has a single `!` mark (`_BROKEN_MARK` :227), used only for the dangling pnpm shim. Each tier keeps its own installed copy (`set_installed` :383).
- **Owner gaps.**
  - The implicit `~/.local/bin` is not checked (B #4).
  - uv tools report the wrong owner dir (F X4).
  - Volta and redirect shims are unattributed (C G5).
  - `host_setup` loses its owner probe (B 15 WR-06).
  - The native probe runs per tool, not memoized (B 15 WR-04).
  - `has_brew` is frozen at launch (A T-07-15).
- **No receipts.** An empty `~/.local/state/tools-installer/receipts/` exists on the host from an earlier version; no current code writes it. Phase 17 leaves the archive layout as the only interim proof.

## Requirements

1. **One state, one swap (STATE-01)**: Each refresh pass builds one `ToolState` per tool and publishes the whole map in one swap. A pass overtaken by a newer refresh publishes nothing.
   - Current: Several maps are updated separately, and the raced merge at :751.
   - Target: One frozen map per generation with `state_of(id)`. When no record exists for the current generation, it returns none and readers show "checking".
   - Acceptance: A deterministic barrier test runs two overlapping passes. Only the newer pass publishes, and an older pass finishing later is discarded.

2. **Closed health set (STATE-02, part 1)**: `tool_health` maps evidence to exactly one `Health`, plus one reason per fact.
   - Current: Only installed, missing and the pnpm `!`.
   - Target: Present tools take, in precedence order: checking > broken > misconfigured > outdated > ok. Absent tools are missing (a method applies here) or unavailable (none applies). Shadowed, off-policy, unknown owner and unreadable version are reasons, not states.
   - Acceptance: A parametrized table covers every evidence combination. Broken plus outdated yields broken, with both reasons listed.

3. **Marks and legend on every tier (STATE-02, part 2; STATE-06)**: Each tier shows one health mark per tool: `✓ ok · ↑ update · ≈ config · ! broken · ○ missing`, a dim row for unavailable, and `…` for checking. The legend fits 78×3, and the focused row shows its reasons and missing configuration steps.
   - Current: A two-state legend; reasons are not shown.
   - Target: One `health_cell` and one legend shared by the system, user and ai tiers.
   - Acceptance: Each mark renders on each tier. The legend fits at 78 columns. An empty tier shows the legend and an empty message. The focused-row detail lists the reasons.

4. **Receipts (STATE-03)**: Install, update and repair write an atomic JSON receipt per tool to `~/.local/state/tools-installer/receipts/<id>.json`.
   - Current: None.
   - Target:
     - The receipt records artifacts (path, type, link target, sha256 for raw files), the package name for manager kinds, and the hooks.
     - Native, skill and `host_setup` tools write no receipt.
     - A reinstall rewrites the receipt, and a failed update keeps the old one.
     - A missing or changed artifact on a present tool marks it broken and not removable.
     - An unreadable or corrupt receipt counts as no proof.
   - Acceptance:
     - Receipts are written for the download, app, script and brew/uv/pnpm kinds.
     - A changed link target makes the tool not removable and broken.
     - A corrupt receipt does not crash anything and is treated as unproven.
     - An injected failure between the method and the receipt write leaves the tool present but unproven.

5. **Adoption by checksum (new, user decision)**: A tool present before receipts existed is adopted automatically when the sha256 of its installed file equals the registry's pinned checksum. Otherwise it is adopted only by reinstalling with `r`.
   - Current: Not possible.
   - Target: Adoption writes a receipt during the refresh pass and states it in the reasons.
   - Acceptance: A matching file is adopted and becomes removable. A non-matching file is not adopted and shows the hint "reinstall with r to adopt".

6. **Proof drives removal (replaces the Phase 17 interim)**: CLI and TUI uninstall remove only artifacts proven by a receipt, by adoption, or by the archive layout.
   - Current: Phase 17's archive-layout-only predicate.
   - Target: The same predicate, now fed by `ToolState.removable`. The Uninstall screen redesign stays in Phase 21.
   - Acceptance: A receipt-proven raw binary is removed by `--yes` and by the TUI. An unproven one is listed as "remove it yourself" in both.

7. **True owners (STATE-04)**: Owner attribution is correct for the cases listed below.
   - Current: The gaps listed in Background.
   - Target:
     - uv tools resolve via `uv tool dir`.
     - Volta, and pnpm reached through Volta, resolve to volta.
     - Redirect shims are looked through to the real owner.
     - The implicit `~/.local/bin/<bin>` counts as presence.
     - `host_setup` keeps its owner probe.
     - The native package probe runs once per pass.
   - Acceptance: graphify installed with uv → owner uv. A Volta fixture → volta. A shim → the real owner. A fixture binary in `~/.local/bin` with no `bin_dir` → present. One `rpm -qf` call per pass for N native tools.

8. **Live manager availability (STATE-05)**: Installing brew during a session makes brew methods available without restarting.
   - Current: `has_brew` is fixed at launch.
   - Target: Re-read on each pass.
   - Acceptance: After a fake brew appears on PATH, colima becomes installable in the same session.

9. **Misconfigured from existing signals (decision)**: `≈` appears in the three cases below.
   - Current: Not shown.
   - Target:
     - A skill pack is missing on a present agent harness.
     - A kitty, WezTerm or Konsole config does not point at zsh (dry run of the existing sync).
     - A pnpm co-install group is incomplete.
     - Hook-based signals arrive in Phase 23.
   - Acceptance: Each signal yields `≈` with its reason. A skill pack for an absent agent gives no `≈`. No terminal installed gives no `≈`.

10. **Skill pack partial and duplicate (STATE-07)**: Skill packs show complete, partial or duplicate per harness.
    - Current: Present or absent only.
    - Target: A per-harness status in the reasons.
    - Acceptance: Fixtures for a partial copy and a duplicate copy each produce their reason.

## Boundaries

**In scope:**
- `Health`, `ToolState`, `tool_health`, one-swap publication, `state_of`, checking
- `health_cell` and the legend on the three tiers; reasons in the focused-row detail
- The receipt writer and reader (`receipts.py`), adoption by checksum, and proof-driven removal in CLI and TUI
- The owner fixes listed in requirement 7; `has_brew` re-read
- Misconfigured from skill packs, terminals and pnpm groups; skill partial/duplicate

**Out of scope:**
- Dispositions and the install plan (`r`, repair, reconfigure) — Phase 20
- The Uninstall screen redesign, Policies and Doctor lifecycle — Phase 21
- Script `paths`/`remove`/`update` and level-3 removal recipes — Phase 22
- Hook registration recorded per host, and hook-based misconfigured — Phase 23
- Deleting the per-screen workers and message plumbing beyond what one swap needs — Phase 21 / 25

## Constraints

- The refresh stays on one worker thread. G measured 4.5–5.7 s for 90 tools; this phase must not add network calls to the pass.
- Receipts are written with the existing atomic writer; no new dependency.
- The legend fits the 78×3 budget the existing tests pin.
- Zero sudo. Tests use a scratch HOME.

## Acceptance Criteria

- [ ] Two overlapping passes: only the newer publishes; an older pass finishing later is discarded
- [ ] Before the first pass completes, every row shows `…`
- [ ] The `tool_health` table covers all combinations; broken plus outdated → broken with both reasons
- [ ] Every mark renders on the system, user and ai tiers; the legend fits 78×3; an empty tier renders without error
- [ ] The focused row shows its reasons and missing configuration steps
- [ ] Receipts are written for the download, app, script, brew, uv and pnpm kinds; none for native, skill or host_setup
- [ ] A reinstall rewrites the receipt; a failed update keeps the old one
- [ ] A changed or missing artifact → broken and not removable; a corrupt receipt → unproven, no crash
- [ ] A crash between the method and the receipt write → present but unproven
- [ ] A sha256-matching pre-receipt file is adopted; a non-matching one shows "reinstall with r to adopt"
- [ ] `--yes` and the TUI remove a receipt-proven raw binary and refuse an unproven one
- [ ] graphify (uv) → owner uv; Volta → volta; a shim → its real owner; an implicit `~/.local/bin` binary → present; one native probe per pass
- [ ] A brew appearing mid-session makes colima installable without a restart
- [ ] `≈` for a missing skill on a present harness, a terminal not on zsh, and an incomplete pnpm group; none for absent agents or terminals
- [ ] Skill pack partial and duplicate fixtures show their reasons

## Edge Coverage

**Coverage:** 21/21 applicable edges resolved · 0 unresolved

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| adjacency | R1 | ✅ covered | Overlapping passes: the newest wins (AC 1) |
| empty | R1 | ✅ covered | Before the first pass, `…` everywhere (AC 2) |
| ordering | R1 | ✅ covered | An older pass finishing later is discarded (AC 1) |
| adjacency | R2 | ✅ covered | Broken plus outdated → broken with both reasons (AC 3) |
| empty | R2 | ✅ covered | No evidence → missing or unavailable by method availability (AC 3) |
| ordering | R2 | ✅ covered | Precedence fixed in the enum; parametrized table (AC 3) |
| adjacency | R3 | ✅ covered | Legend at 78 columns (AC 4) |
| empty | R3 | ✅ covered | An empty tier renders (AC 4) |
| ordering | R3 | ⛔ dismissed | Not applicable to rendering |
| empty | R4 | ✅ covered | No receipt for native, skill or host_setup (AC 6) |
| encoding | R4 | ✅ covered | A corrupt receipt → unproven, no crash (AC 8) |
| idempotency | R4 | ✅ covered | Reinstall rewrites; a failed update keeps the old one (AC 7) |
| concurrency | R4 | 🧪 backstop | Crash between method and receipt → unproven (AC 9; held-out test) |
| concurrency | R5 | ⛔ dismissed | One installer process per host |
| unclassified | R6 | ✅ covered | Same predicate in CLI and TUI (AC 11) |
| unclassified | R7 | ✅ covered | Owner fixtures (AC 12) |
| unclassified | R8 | ✅ covered | brew mid-session (AC 13) |
| adjacency | R9 | ✅ covered | A skill for an absent agent → no `≈` (AC 14) |
| empty | R9 | ✅ covered | No terminals → no `≈` (AC 14) |
| ordering | R9 | ⛔ dismissed | Signals are independent |
| unclassified | R10 | ✅ covered | Partial and duplicate fixtures (AC 15) |

## Prohibitions (must-NOT)

**Coverage:** 3/3 applicable prohibitions resolved · 0 unresolved

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| MUST NOT adopt a file whose sha256 differs from the pinned checksum | R5 | resolved | test: the non-matching fixture writes no receipt |
| MUST NOT show `✓` while a refresh for the current generation is pending | R1, R3 | resolved | test: the row renders `…` until the pass publishes |
| MUST NOT treat a corrupt or unreadable receipt as proof | R4, R6 | resolved | test: a corrupt receipt → not removable |

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes |
|--------------------|-------|------|--------|-------|
| Goal Clarity       | 0.88  | 0.75 | ✓      | One state, receipts as proof |
| Boundary Clarity   | 0.78  | 0.70 | ✓      | Misconfigured signals split between 19 and 23; screens in 21 |
| Constraint Clarity | 0.75  | 0.65 | ✓      | Same worker, no new network, atomic writer |
| Acceptance Criteria| 0.82  | 0.70 | ✓      | 15 pass/fail criteria |
| **Ambiguity**      | 0.18  | ≤0.20| ✓      | |

## Interview Log

| Round | Perspective     | Question summary | Decision locked |
|-------|-----------------|------------------|-----------------|
| 1 | Researcher      | Pre-receipt installs: how do they become ours? | Automatic adoption when the sha256 equals the pinned checksum; otherwise `r` |
| 1 | Boundary Keeper | Which misconfigured signals in Phase 19? | Existing ones (skill packs, terminals, pnpm groups); hooks in Phase 23 |
| 2 | Failure Analyst | Edge table and prohibitions | Accepted as proposed |

---

*Phase: 19-one-tool-state-with-health-plus-receipts*
*Spec created: 2026-10-13*
*Next step: /gsd-discuss-phase 19 — implementation decisions (how to build what's specified above)*
