## Conflict Detection Report

### BLOCKERS (0)

None.

### WARNINGS (1)

[WARNING] Illustrative dependency-chain example may go stale pending an open mmdc decision
  Found: `.planning/ROADMAP.md` Phase 1 Success Criteria #3 and
    `.planning/intel/requirements.md` REQ-dependency-chain-requires (batch 1,
    `docs/prds/2026-09-04-catalog-tiers-and-dependency-chain-v1.0-prd.md`) both
    cite "`mmdc` needing `pnpm`" as the illustrative cross-tier `requires` proof
    case for the tier/dependency-resolver work.
  Found: `docs/prds/2026-09-04-package-manager-policy-v1.0-prd.md` (batch 2)
    leaves `mmdc`'s install method as an explicit open decision (Open
    Question 3) — still unresolved as of batch 4 (see REQ-mmdc-install-decision).
    If `mmdc` moves to brew, it would gain a `requires: ["puppeteer"]`
    edge (an ai/user-tier dependency, not a system-tier one), not `["pnpm"]`.
  Impact: The underlying requirement (`resolve_dependencies` already handles
    cross-tier `requires` with zero new resolver code) is unaffected — `java`→
    `sdkman` remains a valid, unaffected proof case. Only the specific
    `mmdc`→`pnpm` illustrative example in Phase 1's success criteria and in
    REQ-dependency-chain-requires's acceptance bullets may need updating if the
    `mmdc` decision resolves to brew.
  → When routing/planning Phase 1, do not hard-code `mmdc`→`pnpm` as the sole
    proof case; confirm the `mmdc` install-method decision (REQ-mmdc-install-decision)
    first, or use `java`→`sdkman` (already shipped, commit `0e05f50`) as an
    alternative, decision-independent proof case.
  Status: carried forward from batches 1-3; still open after batch 4 (batch 4's
    three PRDs — `agent-cli-ergonomics`, `background-maintenance-daemon`,
    `live-package-management` — do not touch `mmdc`'s install-method decision
    directly; `live-package-management`'s own Open Question 4 asks a related-but-
    distinct question, see Notes below).

### INFO (2)

[INFO] REQ-pnpm-global-reinstall-mitigation's cross-PRD dependency is now unblocked
  Note: batch 2's `REQ-pnpm-global-reinstall-mitigation`
    (`docs/prds/2026-09-04-package-manager-policy-v1.0-prd.md`) was recorded as
    "depends on the not-yet-ingested `live-package-management` PRD's update
    mechanism." That PRD (`docs/prds/2026-09-04-live-package-management-v1.0-prd.md`)
    is ingested this run (batch 4) and defines exactly that mechanism as MVP
    piece #5, `REQ-update-action-manager-delegation`: an "update" action that
    delegates to the correct underlying manager (brew, pnpm, uv tool, or this
    installer's own path) per tool. `REQ-pnpm-global-reinstall-mitigation`'s own
    text — "triggers when `pnpm` itself is the tool being updated, as a natural
    extension of the update mechanism" — matches this piece precisely: when the
    update action's target is `pnpm` itself, the snapshot-and-reinstall-together
    mitigation is a natural extension of it, exactly as originally described.
    `REQ-pnpm-global-reinstall-mitigation`'s `status:` field in
    `.planning/intel/requirements.md` has been updated this run to reflect the
    unblock. No content conflict between the two PRDs — additive, not
    competing.
  → When sequencing/routing (ROADMAP.md Phase 5, currently blocked pending
    batch 5/7's ingest per its own text), the roadmapper can now sequence
    `REQ-pnpm-global-reinstall-mitigation` after `REQ-update-action-manager-delegation`
    is implemented, rather than leaving it flagged as blocked on missing scope.
    The dependency is resolvable/sequenceable, not resolved-in-place — the
    update-action requirement itself still needs implementing first.

[INFO] All 7 PRDs from the 2026-09-04 planning batch are now ingested
  Note: This run (batch 4) ingests the final 3 of 7 PRDs
    (`agent-cli-ergonomics`, `background-maintenance-daemon`,
    `live-package-management`), completing the full set named in
    `.planning/ROADMAP.md`'s Overview ("Three more PRDs from the same
    2026-09-04 batch... will be ingested in subsequent merge-mode passes").
    Cumulative: 7 classified docs across 4 ingest runs, all type `PRD`, no
    ADRs/SPECs/DOCs encountered in any batch.
  → No remaining PRDs pending ingest for this milestone; the roadmapper can
    treat this as the final intel-synthesis pass before producing/updating
    PROJECT.md/REQUIREMENTS.md/ROADMAP.md for the complete 7-PRD scope.

---

Notes:

- `CLASSIFICATIONS_DIR` for this run (batch 4/4, the final 3 of 7 PRDs)
  contained exactly 3 classifications (all type `PRD`, confidence high,
  manifest_override true): `docs/prds/2026-09-04-agent-cli-ergonomics-v1.0-prd.md`,
  `docs/prds/2026-09-04-background-maintenance-daemon-v1.0-prd.md`, and
  `docs/prds/2026-09-04-live-package-management-v1.0-prd.md`.
- Cycle detection: `agent-cli-ergonomics`' `cross_refs` names only
  `installer/tweaks.py` (a source file, not a doc node); `background-maintenance-daemon`'s
  `cross_refs` names only `scripts/prune-user-tmpdir.sh` (a source file);
  `live-package-management`'s `cross_refs` names only source files
  (`installer/versions.py`, `installer/catalog_tui.py`, `installer/wizard_app.py`,
  `installer/status.py`). None of this run's three classified docs reference
  each other or any other doc node. No cycle found among this run's three
  classified nodes, and no cycle across the cumulative 7-doc set either (no doc
  in any prior batch names another doc as a `cross_refs` target that would form
  a cycle — all cross-doc references found across all 4 batches have been
  one-directional, forward or backward prose references to sibling PRDs, not
  graph edges within a single run's node set).
- No PRD-vs-PRD competing acceptance variants were found on identically-scoped
  requirements, either within this batch's three PRDs or against the four
  already-ingested PRDs (batches 1-3). The three batch-4 PRDs are cleanly
  non-overlapping in scope: `agent-cli-ergonomics` (shell aliases/tweaks for
  agent-host CLI ergonomics), `background-maintenance-daemon` (a new
  macOS-only `Policy` type for a scheduled cleanup daemon), and
  `live-package-management` (version-aware status and an update action in the
  TUI) touch different subsystems with no shared requirement scope.
- Cross-batch consistency check (this run's three PRDs against the four
  already-ingested PRDs): `background-maintenance-daemon`'s "Diagnostics view:
  yes, but small and reused, not a new top-level view" design decision
  explicitly cites and respects `.claude/architecture.md`'s "one view registry,
  one nav path" standard, already recorded in `.planning/PROJECT.md`'s
  Constraints section — consistent, no conflict. `background-maintenance-daemon`'s
  `fd`/`rg` dependency-gating requirement explicitly reuses the `requires`/
  `missing_requires` mechanism already established by batch 1's `docker`/`watch`
  precedent — additive, not a new mechanism. `agent-cli-ergonomics`' three new
  tweaks explicitly reuse `TweakBundle`/`tweak_policy` unchanged, matching the
  existing `claude-skip` precedent already in `installer/tweaks.py` — no new
  mechanism introduced. `live-package-management`'s manager-aware update
  requirement (`REQ-update-action-manager-delegation`) explicitly reuses
  `installer/uninstall.py`'s existing `UninstallState` "managed elsewhere"
  concept rather than inventing a parallel one — consistent with existing code.
- `live-package-management`'s Open Question 4 ("should manager-aware update
  also cover moving a tool from a suboptimal method — e.g. still on `pnpm` per
  the package-manager-policy PRD's findings — onto its preferred method as part
  of updating it, or is that migration always a separate, explicit registry
  change?") is related to, but distinct from, the still-open `mmdc` WARNING
  above: it is a general policy question about the update action's own scope,
  not a specific claim about `mmdc`'s install method. Left as an open question
  in `REQ-update-action-manager-delegation`'s source PRD, not bucketed as a
  conflict here — no contradiction, just an unresolved scope question for the
  roadmapper/planner to close.
- `live-package-management`'s deferred item #7 (manager-drift auto-remediation:
  auto-updating the registry and filing a GitHub issue) is explicitly scoped
  out of this PRD's MVP by its own source text ("a real new capability... worth
  a separate, explicit decision and likely its own PRD") — not captured as a
  requirement in `.planning/intel/requirements.md`; recorded only in
  `.planning/intel/SYNTHESIS.md`'s out-of-scope section for roadmapper
  awareness, consistent with how prior batches (e.g. batch 3's out-of-scope
  postinstall items) handled explicitly-deferred, not-a-requirement source
  content.
- Merge-mode checks against `EXISTING_CONTEXT` (`.planning/PROJECT.md`,
  `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`) found no LOCKED-decision
  contradiction (no ADR has been classified in any batch to date, and
  `PROJECT.md`'s "Key Decisions" table has no entries marked locked — all rows
  show outcome "— Pending"). `ROADMAP.md`'s Overview already explicitly
  reserved `live-package-management`, `background-maintenance-daemon`, and
  `agent-cli-ergonomics` as the three remaining PRDs to be ingested "in
  subsequent merge-mode passes" — consistent with this batch's content, no
  contradiction. `REQUIREMENTS.md`'s existing `REQ-pnpm-global-reinstall-mitigation`
  row ("Blocked (depends on batch 5/7 ingest)") is the item unblocked by this
  run's INFO entry above — the roadmapper should update that row when it next
  regenerates `REQUIREMENTS.md`.
- This PRD batch's own text continues to record that SDKMAN exclusivity (batch
  2, `REQ-sdkman-exclusivity`) was already implemented and shipped directly to
  `main` in commit `0e05f50`, outside GSD's research→plan→execute→verify flow.
  Not a cross-document conflict per the seven defined detection passes, so not
  bucketed above; carried forward here for downstream visibility only.
- No remaining PRDs from the 2026-09-04 planning batch are pending ingest —
  all 7 (`catalog-tiers-and-dependency-chain`, `package-manager-policy`,
  `catalog-expansion`, `postinstall-hooks`, `agent-cli-ergonomics`,
  `background-maintenance-daemon`, `live-package-management`) are now
  synthesized across batches 1-4.
