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
    Question 3) — still unresolved as of batch 3 (see REQ-mmdc-install-decision).
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
  Status: carried forward from batches 1-2; still open after batch 3 (batch 3's
    two PRDs — `catalog-expansion`, `postinstall-hooks` — do not touch `mmdc`).

### INFO (1)

[INFO] catalog-expansion's Open Question 3 (Oh-My-Zsh plugin catalog entries) is already answered
  Note: `docs/prds/2026-09-04-catalog-expansion-v1.0-prd.md` (batch 3) lists as
    Open Question 3: "Do Oh-My-Zsh plugins need their own catalog entries, per
    the open question in the tier PRD?" — but that same document's own Risks
    section already marks this resolved ("~~Oh-My-Zsh plugin representation~~
    resolved in the tier PRD (config-array edit, not a Tool entry) - no longer
    a risk here"), and batch 1's synthesized `REQ-oh-my-zsh-plugin-config`
    (`.planning/intel/requirements.md`) records the same resolution with no
    open `status:` field. Treated as an internal staleness in the source
    document's Open Questions list (Core Features vs. Risks/Open Questions
    sections disagree on whether this is still open), not a cross-document
    conflict — auto-resolved by preferring the more specific/later resolution
    (Risks section + batch 1's already-synthesized requirement) over the
    stale Open Question wording. No action needed; `REQ-system-tier-shell-container-entries`
    (batch 3) does not model oh-my-zsh plugins as separate catalog entries.

---

Notes:

- `CLASSIFICATIONS_DIR` for this run (batch 3/7) contained exactly 2
  classifications (both type `PRD`, confidence high, manifest_override true):
  `docs/prds/2026-09-04-catalog-expansion-v1.0-prd.md` and
  `docs/prds/2026-09-04-postinstall-hooks-v1.0-prd.md`.
- Cycle detection: `catalog-expansion`'s classification `cross_refs` names
  `2026-09-04-catalog-tiers-and-dependency-chain-v1.0-prd.md` and
  `2026-09-04-package-manager-policy-v1.0-prd.md` — both already ingested in
  prior batches (1 and 2) and therefore not nodes in *this run's* classified
  set (their classification JSONs live in `.planning/intel/classifications-archive/`,
  not `.planning/intel/classifications/` for this run) — these are prose
  references to already-synthesized sibling docs, not graph edges within this
  run's node set, consistent with how batch 2's forward reference to the
  not-yet-ingested `live-package-management` PRD was treated. `postinstall-hooks`'s
  `cross_refs` is empty (`[]`). No cycle found among this run's two classified
  nodes.
- Cross-batch consistency check (this run's two PRDs against the two
  already-ingested PRDs, batches 1-2): `catalog-expansion`'s `codegraph` entry
  (`kind="github_release"`) matches, and explicitly cites, batch 2's
  `REQ-codegraph-github-release` finding — reinforcing, not contradicting.
  `catalog-expansion`'s system-tier tools (`zsh`, `oh-my-zsh`) fill in the
  concrete registry entries that batch 1's `REQ-dependency-chain-requires`
  illustrated generically (`oh-my-zsh.requires = ["zsh"]`) — additive, not
  conflicting. `catalog-expansion`'s `recommends` wiring
  (`REQ-recommends-wiring-agent-hosts`) instantiates batch 1's
  `REQ-recommends-soft-dependency` mechanism with concrete tool data —
  additive, not a competing variant. `postinstall-hooks`'s postinstall
  mechanism explicitly builds on the existing `run_live` single-apply-path
  architecture constraint already recorded in `.planning/PROJECT.md`'s
  Constraints section — consistent, no conflict.
- No PRD-vs-PRD competing acceptance variants were found on identically-scoped
  requirements across batches 1-3. `catalog-expansion` explicitly scopes
  `codegraph`'s postinstall MCP registration as out-of-scope, covered by
  `postinstall-hooks` — the two PRDs in this batch are cleanly complementary,
  not overlapping.
- Merge-mode checks against `EXISTING_CONTEXT` (`.planning/PROJECT.md`,
  `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`) found no LOCKED-decision
  contradiction (no ADR has been classified in any batch to date, and
  `PROJECT.md`'s "Key Decisions" table has no entries marked locked — all rows
  show outcome "— Pending"). `ROADMAP.md`'s Context and Out-of-Scope sections
  already explicitly reserved `catalog-expansion` and `postinstall-hooks` as
  "not yet ingested" companion PRDs, consistent with this batch's content.
- This PRD batch's own text continues to record that SDKMAN exclusivity (batch
  2, `REQ-sdkman-exclusivity`) was already implemented and shipped directly to
  `main` in commit `0e05f50`, outside GSD's research→plan→execute→verify flow.
  Not a cross-document conflict per the seven defined detection passes, so not
  bucketed above; carried forward here for downstream visibility only. See the
  `status:` field on `REQ-sdkman-exclusivity` in `.planning/intel/requirements.md`.
- Two remaining PRDs from the 2026-09-04 planning batch are not yet ingested:
  `live-package-management`, `background-maintenance-daemon`, `agent-cli-ergonomics`
  (3 of 7 remain after this batch).
