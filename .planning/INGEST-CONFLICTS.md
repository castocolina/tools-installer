## Conflict Detection Report

### BLOCKERS (0)

None.

### WARNINGS (0)

None.

### INFO (0)

None.

---

Notes:
- `CLASSIFICATIONS_DIR` contained exactly 1 classification (type `PRD`,
  confidence high): `docs/prds/2026-09-04-catalog-tiers-and-dependency-chain-v1.0-prd.md`.
  With a single classified doc and no existing `.planning/` context to
  check against (mode: new), none of the seven conflict-detection passes
  (LOCKED-vs-LOCKED, ADR-vs-existing-locked, PRD-overlap, SPEC-vs-ADR,
  lower-vs-higher precedence, UNKNOWN-low-confidence, cycle) found a
  match. No BLOCKER/WARNING/INFO entries to report.
- The classified PRD's `cross_refs` list 6 paths, all of which exist on
  disk but were **not** part of this classification batch (the ingest
  manifest `.planning/.ingest-manifests/01-catalog-tiers.yaml` scoped
  this run to a single doc): `docs/prds/2026-09-04-catalog-expansion-v1.0-prd.md`,
  `docs/prds/2026-09-04-postinstall-hooks-v1.0-prd.md`,
  `docs/prds/dependencies-and-shell-tweaks-v1.0-prd.md`,
  `docs/superpowers/plans/2026-06-21-dependencies-and-shell-tweaks.md`,
  `docs/prds/2026-09-04-package-manager-policy-v1.0-prd.md`,
  `.claude/architecture.md`. Since none of these were classified in
  this batch, they contribute no nodes to the cross-ref graph for this
  run — no cycle exists among the classified set. This is not a
  conflict per the defined checks, but is noted here for traceability:
  a future ingest batch including those docs may surface conflicts not
  visible from this single-doc run (e.g. the two "identified by review,
  not implemented" gaps in `requirements.md` reference the
  `dependencies-and-shell-tweaks` PRD/plan directly).
