# Phase 3: Install/Uninstall & Tweak Lifecycle Hardening - Context

**Gathered:** 2026-09-04
**Status:** Ready for planning

<domain>
## Phase Boundary

A run that hits a failed prerequisite skips its dependents with a clear
"dependency failed" reason instead of attempting them or silently dropping
them from the summary. A full uninstall removes tweak-managed artifacts
(both the helper executables and their `~/.myshellrc` blocks), not only
`Tool`-shaped artifacts. Oh-My-Zsh's bundled `git`/`docker` plugins turn on
the same way every other Policies tweak does.

</domain>

<decisions>
## Implementation Decisions

### Oh-My-Zsh plugin editing mechanism
- **D-01:** Edit the existing `plugins=(...)` line in the user's `.zshrc` via targeted regex: locate the line, parse its space-separated contents, insert `git`/`docker` only if absent (toggle-on), remove only those two if present (toggle-off) — preserving every other plugin already in the array and every other line in the file untouched.
- **D-02:** This is a genuinely new capability, not a reuse of `installer/shellrc.py`'s `apply_block`/`strip_block` — that mechanism owns and rewrites an entire marker-delimited block in a file `tools-installer` controls (`~/.myshellrc`); Oh-My-Zsh's `plugins=(...)` line lives in a file the user's own setup already populated, and must be edited in place, not replaced wholesale. — **Reversibility:** costly — a shell-config edit mechanism, once shipped and relied on for toggling real `.zshrc` files, is not something to casually redesign; regressing its regex would risk corrupting a user's real shell config.
- **D-03:** Single-line `plugins=(...)` syntax is the target for this phase — multi-line array syntax (`plugins=(\n  git\n  docker\n)`) is a known valid Oh-My-Zsh form but is explicitly out of scope here; not adding a full multi-line-aware parser.

### Uninstall sweep scope
- **D-04:** A full uninstall run performs a symmetric teardown of every currently-enabled tweak: it reuses the exact same `tweak_policy`/`strip_block` + `remove_tweak_executables` pair that Policies already uses to disable a tweak, for every tweak that is still enabled at uninstall time — not just a narrow sweep of orphaned executable files.
- **Rationale:** deleting only the executable (the REQ's literal wording) while leaving its shellrc block in place would leave a dangling shell function/alias pointing at a file that no longer exists — a strictly worse state than before the uninstall. Reusing the existing disable path avoids inventing a second, narrower cleanup mechanism.

### Oh-My-Zsh presence precondition
- **D-05:** The Policies toggle detects Oh-My-Zsh's presence (`~/.oh-my-zsh` directory or `$ZSH` env var) before offering/enabling it, mirroring the existing `requires` pattern other `TweakBundle` entries already use (e.g. the docker bundle's `requires=("watch",)`) — extended from a PATH-binary check to a directory-existence check, since Oh-My-Zsh is not a PATH binary.
- **D-06:** When toggled on but Oh-My-Zsh isn't actually present, the same unmet-`requires` UX other bundles already show applies here (blocked/flagged with a clear reason) — no new UX pattern needed, just a new detection predicate feeding the existing mechanism.

### Claude's Discretion
- The exact new `InstallStatus`-family value (or equivalent) used to represent "dependency failed" in `run_installs`'/`summarize`'s output, and its color/label in the wizard summary — implementation detail, not a user decision.
- Whether the presence-check predicate for Oh-My-Zsh becomes a new field on `TweakBundle` (parallel to `requires`) or a bundle-specific special case — planner's call, informed by how `requires`' existing PATH-binary check is implemented.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements source
- `.planning/PROJECT.md` — REQ-install-failure-propagation and REQ-uninstall-sweep-tweak-executables both surfaced by code review of commit `431a0a9`; "soft-warn + skip dependents on failure" was the original (never-implemented) spec
- `.planning/REQUIREMENTS.md` — REQ-install-failure-propagation, REQ-uninstall-sweep-tweak-executables, REQ-oh-my-zsh-plugin-config full text
- `.planning/ROADMAP.md` — Phase 3 goal, 3 success criteria, "Depends on: Nothing — independent of the tier work in Phases 1-2"

### Existing pattern to mirror
- `installer/session.py::run_installs` (lines ~50-75) — current per-tool install loop with zero failure-tracking; needs to accumulate failed tool ids and check each subsequent tool's `requires` against that set
- `installer/uninstall.py::plan_uninstall` (lines ~47+) — currently walks only download/app-method artifacts; needs to also enumerate active tweaks' `ManagedExecutable`s and shellrc blocks
- `installer/tweaks.py::TweakBundle`/`ManagedExecutable`/`install_tweak_executables`/`remove_tweak_executables` (lines ~23-180) — the exact pair `plan_uninstall`'s sweep must call symmetrically with the existing toggle-off path
- `installer/policy.py::tweak_policy` (lines ~128-175) — the reference implementation of "toggle a tweak off" that the uninstall sweep must reuse rather than reinvent
- `installer/shellrc.py::apply_block`/`strip_block` (lines ~1-80) — the block-based mechanism `NOT` being reused for Oh-My-Zsh (D-02); still the reference for every other tweak's `~/.myshellrc` editing

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `installer/tweaks.py::install_tweak_executables`/`remove_tweak_executables` — directly reusable by the uninstall sweep (D-04) for every enabled tweak, no new removal logic needed
- `installer/policy.py::tweak_policy`'s enable/disable branches — the template for what "full uninstall disables every enabled tweak" actually calls

### Established Patterns
- Every existing `TweakBundle` writes into a file `tools-installer` fully owns (`~/.myshellrc`) via idempotent marker-delimited blocks — Oh-My-Zsh's `plugins=(...)` line breaks this pattern by requiring in-place editing of a user-owned file, which is why D-01/D-02 treat it as new capability rather than reuse
- `requires=("watch",)`-style preconditions already gate other bundles on a PATH binary being present; D-05 extends this concept (not its exact code path) to a directory-existence check

### Integration Points
- `installer/session.py::run_installs` — needs failed-id tracking threaded through the per-tool loop
- `installer/uninstall.py::plan_uninstall` — needs a new code path enumerating active tweaks alongside the existing `Tool`-shaped artifact walk
- `installer/tweaks.py` — needs a new `TweakBundle` entry (or equivalent) for Oh-My-Zsh plugins, plus the new regex-based `plugins=(...)` editor function
- `installer/policy.py` — the Oh-My-Zsh tweak's enable/disable wiring, including the new presence-check gate

</code_context>

<specifics>
## Specific Ideas

- Motivating context from the user: nobody realistically uninstalls zsh/oh-my-zsh itself day-to-day — the actual value of this phase's hardening is making a **full machine restore/re-bootstrap** (which the user plans to do soon) clean and predictable, not supporting a routine "remove oh-my-zsh" workflow. This reinforces D-04 (symmetric teardown) as the right default: a full uninstall should leave the machine in a genuinely clean state for a fresh re-provision, not a partially-cleaned one.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within Phase 3 scope.

</deferred>

---

*Phase: 3-install-uninstall-tweak-lifecycle-hardening*
*Context gathered: 2026-09-04*
