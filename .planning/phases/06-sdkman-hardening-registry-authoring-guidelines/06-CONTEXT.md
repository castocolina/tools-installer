# Phase 6: SDKMAN Hardening & Registry-Authoring Guidelines - Context

**Gathered:** 2026-09-04
**Status:** Ready for planning

<domain>
## Phase Boundary

The already-shipped SDKMAN-exclusivity work (commit `0e05f50`, landed outside
GSD's normal flow) gets the verification/hardening pass it skipped — broader
test coverage, an end-to-end non-interactive check, resolving whether `java`
needs a pinned SDKMAN candidate version. Separately, two registry-authoring
guidelines get written down: a mandatory per-tool per-OS verification step
for future registry additions, and a brew-preference convention (with
SDKMAN's Java carve-out as the named exception). Both guidelines are
documentation/process additions, not new code mechanisms.

</domain>

<decisions>
## Implementation Decisions

### Verification checklist recording mechanism
- **D-01:** A comment citing what was checked (e.g. "verified via brew.sh formula page, 2026-09-04") is the recording mechanism for the new per-tool, per-OS registry-authoring verification checklist — not a stronger checked-in excerpt/snapshot of the verified source. Lower friction, matches this project's existing convention of citing sources in comments; avoids adding real file weight or staleness risk from snapshotting external content that can change upstream.

### Brew-preference guideline enforcement
- **D-02:** "Prefer brew over other userspace package managers" (with SDKMAN's Java carve-out) is documented-only, pure convention — no lint/test enforcement. Matches how this project already handles the analogous SDKMAN carve-out (explained in prose, not lint-enforced); brew availability differs per OS/tool, so an automated check would risk noisy false positives.

### Claude's Discretion
- Exact placement of the verification-checklist and brew-preference documentation (a new section in `.claude/architecture.md`, a dedicated `CONTRIBUTING`-style doc, or inline in `installer/registry.toml`'s own header comment) — planner's call, informed by where this project already documents similar authoring conventions.
- Whether `java`'s SDKMAN candidate needs a pinned `version` to avoid an interactive prompt (ROADMAP SC#2) — a technical/research question to resolve via testing `sdk install java` non-interactively, not a user-preference gray area.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements source
- `.planning/REQUIREMENTS.md` — REQ-sdkman-exclusivity (status: "Already implemented and shipped in commit `0e05f50`, outside GSD's normal flow — treat as prior art requiring verification/hardening, not as sufficient as-is"), REQ-registry-authoring-verification-checklist, REQ-brew-preference-guideline full text
- `.planning/ROADMAP.md` Phase 6 section — goal, 4 numbered success criteria
- Commit `0e05f50` — the existing SDKMAN-exclusivity implementation to verify/harden, not reimplement

### Existing pattern to mirror
- Wherever `java`/`gradle`/`maven`/`groovy`/`springbootcli` currently route through SDKMAN (find via `installer/registry.toml` and whatever install-method dispatch handles `kind="sdkman"` or similar) — the code this phase verifies/hardens, not rewrites
- `.claude/architecture.md` — existing convention for where project-wide authoring rules get documented (the "five rules" plus Phase 1's tier-is-a-label addition)

</canonical_refs>

<specifics>
## Specific Ideas

None beyond the two locked decisions above — this phase's gray areas were narrowly about documentation mechanism/enforcement, both resolved to the lighter-weight, convention-based option.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within Phase 6 scope.

</deferred>

---

*Phase: 6-sdkman-hardening-registry-authoring-guidelines*
*Context gathered: 2026-09-04*
