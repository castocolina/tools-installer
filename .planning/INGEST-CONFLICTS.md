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
  Found: `docs/prds/2026-09-04-package-manager-policy-v1.0-prd.md` (batch 2, this
    ingest) leaves `mmdc`'s install method as an explicit open decision (Open
    Question 3) — "leaning brew now" because the pnpm-vs-brew freshness gap that
    previously favored pnpm is currently closed, but still deferred to the user
    to confirm. If `mmdc` moves to brew, it would gain a `requires: ["puppeteer"]`
    edge (an ai/user-tier dependency, not a system-tier one), not `["pnpm"]`.
  Impact: The underlying requirement (`resolve_dependencies` already handles
    cross-tier `requires` with zero new resolver code) is unaffected — `java`→
    `sdkman` remains a valid, unaffected proof case. Only the specific
    `mmdc`→`pnpm` illustrative example in Phase 1's success criteria and in
    REQ-dependency-chain-requires's acceptance bullets may need updating if the
    `mmdc` decision resolves to brew.
  → When routing/planning Phase 1, do not hard-code `mmdc`→`pnpm` as the sole
    proof case; confirm the `mmdc` install-method decision (REQ-mmdc-install-decision,
    this batch) first, or use `java`→`sdkman` (already shipped, commit `0e05f50`)
    as an alternative, decision-independent proof case.

### INFO (0)

None.

---

Notes:

- `CLASSIFICATIONS_DIR` for this run contained exactly 1 classification (type
  `PRD`, confidence high, manifest_override true):
  `docs/prds/2026-09-04-package-manager-policy-v1.0-prd.md`
  (`.planning/.ingest-manifests/02-package-manager-policy.yaml` scoped this run
  to that single doc, batch 2/7 of the 2026-09-04 planning batch). This doc's
  own `cross_refs` field in the classification JSON is empty (`[]`), so cycle
  detection over the classified set trivially found no cycle.
- The source PRD references several sibling docs in prose that were **not**
  part of this classification batch: `docs/prds/2026-09-04-live-package-management-v1.0-prd.md`
  (REQ-pnpm-global-reinstall-mitigation depends on its update mechanism) and
  the already-ingested `docs/prds/2026-09-04-catalog-tiers-and-dependency-chain-v1.0-prd.md`
  (batch 1). Since the live-package-management PRD was not classified in this
  batch, it contributes no node to this run's cross-ref graph — no cycle
  possible. It will be ingested in a future pass per the project's stated
  7-PRD batch order.
- Merge-mode checks against `EXISTING_CONTEXT`
  (`.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`)
  found no LOCKED-decision contradiction: `PROJECT.md`'s "Key Decisions" table
  has no entries marked locked (all rows show outcome "— Pending"), and no
  ADR was classified in either batch 1 or batch 2, so the
  ADR-vs-existing-locked-CONTEXT.md pass (rule 2) has nothing to check against.
  The single WARNING above is the only cross-check finding between this
  batch's PRD and the existing planning artifacts.
- No PRD-vs-PRD competing acceptance variants were found on identically-scoped
  requirements between batch 1 and batch 2 — their requirement scopes are
  disjoint (catalog tiers/dependency-resolver UI vs. package-manager
  ban/redirect/registry-method policy) apart from the illustrative-example
  overlap captured as the WARNING above.
- This PRD's own text records that SDKMAN exclusivity (five `kind="sdkman"`
  method entries, `installer/status.py` `detect_path` fallback) was already
  implemented and shipped directly to `main` in commit `0e05f50`, outside
  GSD's research→plan→execute→verify flow, per the user's own standing
  instruction for this PRD batch ("no vamos a implementar nada"). This is not
  a cross-document conflict per the seven defined detection passes, so it is
  not bucketed above, but it is surfaced here for downstream visibility: GSD's
  planning of REQ-sdkman-exclusivity should treat commit `0e05f50` as prior
  art requiring verification and hardening (broader test coverage, e2e
  verification, review), not as already-sufficient shipped work. See the
  `status:` field on REQ-sdkman-exclusivity in `.planning/intel/requirements.md`.
