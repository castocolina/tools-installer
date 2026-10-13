# Phase 7: System & User Tier Catalog Expansion - Context

**Gathered:** 2026-09-04
**Status:** Ready for planning

<domain>
## Phase Boundary

New system-tier prerequisites (`zsh`, `oh-my-zsh`, `gnu-bash` on macOS, Apple
Containers on macOS) and user-tier terminal emulators (`kitty`, `wezterm`)
join the catalog with verified, per-platform install methods, including a
real Linux/Bazzite path for the system-tier entries (reusing the existing
`podman` entry for the container-runtime story there, not adding a new one).

</domain>

<decisions>
## Implementation Decisions

### Apple Containers availability gating
- **D-01:** Apple Containers always appears as a catalog entry (never omitted), regardless of whether research finds a real install action or confirms it's a doc/version-gate case (native `container` CLI already present, nothing to install). If it's unavailable on the current machine (wrong macOS version, non-Apple-Silicon, etc.), it shows in the catalog **disabled** — reusing this project's existing unmet-requires/unavailable-dependency display pattern rather than inventing a new one or hiding the entry entirely. This keeps the System-tier bootstrap checklist visually complete even when one entry is a no-op or unavailable on this particular machine.

### Claude's Discretion
- Exact disabled-state rendering for Apple Containers when unavailable — reuse whatever `catalog_tui.py`/`ui_common.py` mechanism already renders an unmet-`requires` or platform-unavailable tool (per D-01's instruction to reuse, not invent).
- Whether `oh-my-zsh`'s `.zshrc`-rewriting behavior, once read, is safe enough to treat as a plain `kind="script"` candidate, or needs a narrower/gated install method — a research finding, not a locked decision.
- Exact Linux path per tool (distro package manager vs. the existing GitHub-release download path) for `kitty`/`wezterm` — per-tool research call, verified live before shipping (this project's registry-authoring convention).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements source
- `.planning/REQUIREMENTS.md` — REQ-system-tier-shell-container-entries, REQ-terminal-emulator-entries, REQ-linux-bazzite-shell-parity full text (including Open Question 4 on Apple Containers, now resolved by D-01)
- `.planning/ROADMAP.md` Phase 7 section — goal, "Depends on: Phase 1 ... and Phase 4-6's registry-authoring verification checklist", 3 numbered success criteria
- `.planning/phases/06-sdkman-hardening-registry-authoring-guidelines/06-CONTEXT.md` — D-01's verification-checklist recording mechanism (a comment citing what was checked) that every new entry this phase adds must follow

### Existing pattern to mirror
- `installer/registry.toml`'s existing `podman` entry — the container-runtime story for Linux/Bazzite (REQ-linux-bazzite-shell-parity), reused as-is, not duplicated
- Whatever mechanism already renders an unmet-`requires`/unavailable-dependency tool in `catalog_tui.py`/`ui_common.py` — the template for D-01's disabled-when-unavailable Apple Containers state
- Existing platform-conditional registry entries (macOS vs Linux methods on one entry) as the template for `zsh`/`oh-my-zsh`'s dual-platform install paths

</canonical_refs>

<specifics>
## Specific Ideas

- User's own framing on Apple Containers (2026-09-04): "If not available show it but disabled" — always visible, gate on availability via the disabled state rather than an omit/include decision made at research time.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within Phase 7 scope.

</deferred>

---

*Phase: 7-system-user-tier-catalog-expansion*
*Context gathered: 2026-09-04*
