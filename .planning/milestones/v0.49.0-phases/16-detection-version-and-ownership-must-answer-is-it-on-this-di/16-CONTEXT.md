# Phase 16: Catalog Truth — Detection, Version and Ownership from the Filesystem - Context

**Gathered:** 2026-09-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Five live defects found running the shipped v1 installer on a real Bazzite host, all sharing one root cause: detection, version and ownership answer "can I run a binary right now" instead of "is it on this disk and who put it there" (ROADMAP.md Phase 16).

1. **skill_pack tools read as not installed while present on disk** — superpowers, opengsd, matt-pocock-skills, ponytail, softaworks-agent-toolkit. `installer/skill_lifecycle.py::inspect_status()` already returns present/absent/unknown and has zero callers; it shells out per harness.
2. **Version detection only tries `[tool.cmd, "--version"]`** — sdkman's cmd is a sourced non-executable script, so it reads "no version" while `~/.sdkman/var/version` and each candidate's `current` symlink hold the real answer.
3. **Ownership only considers a tool's DECLARED methods** — groovy/java/gradle/maven read "(source unknown)" and refuse to update, even though `brew list --formula` plainly lists them. No sdkman branch exists anywhere in `ownership.py`.
4. **An unselectable row goes silent** — kitty was assumed OS-image-owned and dimmed with no explanation; investigation during discussion found it is actually installed via its own official userspace installer (`~/.local/kitty.app`), which the registry simply never declared as a method. wezterm gives "Install 0 tools" with no notice when selected while already current.
5. **A broken shim looks installed** — mmdc's pnpm-managed bin shim survives after its package is removed; it reads "installed, no version" instead of "broken, needs repair." This folds in pending todo `2026-09-16-detect-dangling-pnpm-global-bin-shims-in-doctor.md` (score 0.9 match), which is CLOSED by this phase's broken-state design.

</domain>

<decisions>
## Implementation Decisions

### Owner vs. registry conflict
- **D-01:** Owner reports the tool's REAL source — the path/inventory that actually proves it, not the registry's declared method. groovy owned by Homebrew reads "Homebrew," not "unknown." — **Reversibility:** reversible.
- **D-02:** When the real owner differs from the registry's declared policy for that tool (e.g. Homebrew owns a tool the registry declares SDKMAN-exclusive), the row carries a **visible marker**, not just a detail-pane note — e.g. a dim "≠ policy" tag. — **Reversibility:** reversible.
- **D-03:** Pressing `u` on an off-policy tool **offers to migrate** it to the catalog's declared manager (e.g. brew groovy → SDKMAN groovy). — **Reversibility:** reversible (the offer itself; the migration's own mutations are scoped by D-04).
- **D-04:** The migration flow itself (uninstall from the old manager, install via the declared one, handle dependents — e.g. brew's `openjdk` vs SDKMAN's `java`) is **deferred to its own phase**. It mutates installed toolchains and needs its own design (dependency handling, rollback). — **Reversibility:** reversible (deferral, not the migration's own danger — that's costly and belongs in that phase's own threat model).
- **D-05:** Until migration exists, `u` on an off-policy tool **updates through its real, provable owner** (e.g. `brew upgrade groovy`), with a note that migration is coming. Never silently refuses. — **Reversibility:** reversible.
- **D-06:** A tool owned by **two managers at once** (e.g. brew's `openjdk` and a later SDKMAN `java`) shows the ACTIVE owner (whichever PATH resolves) plus a "also installed via X" note for the shadowed one. — **Reversibility:** reversible.
- **D-07:** A tool that installs itself into its own directory via its own script (bun → `~/.bun`, fnm → `~/.local/share/fnm`, volta → `~/.volta`) reports Owner = **"own installer"**, proven by the active path matching the tool's declared location (feeds D-13's per-method location mechanism). — **Reversibility:** reversible.
- **D-08:** Owner stays **"unknown" only when no manager's path or inventory proves anything**, and even then the detail pane shows the active binary's resolved path so the user can see where it actually came from. "Unknown" becomes rare and always explained. — **Reversibility:** reversible.

### skill_pack detection
- **D-09:** The registry's `supported_harnesses` lists are **factually wrong** for at least `superpowers` (declared Pi-only; verified upstream it supports Claude Code, Antigravity, Codex App/CLI, Cursor, Factory Droid, Gemini CLI, Copilot CLI, Kimi Code, OpenCode, and Pi). Every `skill_pack` entry's `supported_harnesses` must be re-audited against its own upstream docs before the detection mechanism is built on top of it — garbage host lists make correct detection answer the wrong question. — **Reversibility:** reversible.
- **D-10:** A skill pack's install state is read through **each harness's own CLI** (`pi list`, `codex plugin list`, `claude plugin list`, etc.), run in a background worker and **cached** — the same pattern `installer/version_cache.py` already uses for versions, not a new mechanism. — **Reversibility:** reversible.
- **D-11:** For a supported harness that has **no list/status command at all**, fall back to reading its on-disk state for that harness only (never as the general mechanism — CLI stays primary wherever one exists). — **Reversibility:** reversible.
- **D-12:** While the background probe is running, the Inst column shows the **last cached answer with the existing stale `~` marker** (reused from the version column's convention), not a blank/"checking…" state. Replaced in place when the probe lands. — **Reversibility:** reversible.
- **D-13:** A pack installed in several hosts at once lists **every host** in the Owner column (e.g. "Claude Code, Pi"), truncating to "Claude Code +2" when narrow, with the full list in the detail pane. — **Reversibility:** reversible.
- **D-14:** Harness CLIs are re-run **on every catalog launch**, in the background (one list call per installed harness, not per pack) — not on the version cache's longer TTL and not manual-only. — **Reversibility:** reversible.
- **D-15:** When a skill pack is selected for install, instructions are shown only for harnesses **present on this machine** — Cursor included, since it was missed in the first pass (installed as `cursor`/`cursor-agent` shell functions, not resolvable binaries). Host presence detection must work from disk as well as PATH, not PATH alone. — **Reversibility:** reversible.

### What a row says when it can't act
- **D-16:** A tool that has genuinely **no install method on this platform** stays dimmed and unselectable, but the row shows a short reason and the detail pane explains fully (e.g. "no install method for immutable Linux"). Never silent. — **Reversibility:** reversible.
- **D-17:** Pressing enter on a **selected, already-installed** tool: if outdated, it updates through its real owner (same path as `u`); if current, the confirm screen lists it as "already current — nothing to do." Never "Install 0 tools" with no explanation. **Regardless of install/update state, the tool's post-install policies are applied on this explicit selection** (D-20 governs the re-propose rule). — **Reversibility:** reversible.
- **D-18:** A tool whose shim/binary exists but whose backing package is gone (mmdc's dangling pnpm shim) gets a **distinct "broken" state** — a separate Inst marker, a detail-pane explanation ("shim present, package missing — reinstall to repair"), and selecting it reinstalls/repairs. Never reads as plainly installed, never reads as plainly absent. This closes pending todo `2026-09-16-detect-dangling-pnpm-global-bin-shims-in-doctor.md`. — **Reversibility:** reversible.
- **D-19:** The registry gains **per-method, per-OS install-location declarations** — each OS-filtered method states where it puts the tool (a `bin_dir` for a plain binary, an `app`/bundle path for macOS, an install root like `~/.local/kitty.app` for a Linux app bundle). A hit at that location is also the ownership proof feeding D-01/D-07. This generalizes beyond kitty: kitty itself was found DURING this discussion to already be installed via its own official userspace installer, which the registry never declared — the fix is adding kitty's real method (and auditing other tools for the same gap), not inventing a new per-tool-per-OS table alongside methods. — **Reversibility:** costly for the mechanism shape (a second ownership-proof source once chosen is awkward to unwind across every method kind) but the kitty fix itself is reversible.
- **D-20:** An installed tool's post-install policies are (re)applied **only on explicit user selection** (sensitive actions still ask to confirm, per `installer/post_install.py`'s existing doctrine). A dependency drag-in or a plain re-run of the installer never re-proposes a policy the user already declined — this preserves `post_install.py`'s documented one-shot-trigger protection. — **Reversibility:** reversible.

### Foreign PATH lines
- **D-21:** Doctor can **offer to guard a foreign unguarded PATH line in place** — rewrite it into the self-deduping case-guard form at the same position, never delete it. Safe even for a line inside an `if`/`case` block (nothing is removed, so no empty then-clause). — **Reversibility:** reversible.
- **D-22:** A line that sits inside **another tool's own marked block** (e.g. kitty-setup's `# >>> my-kitty PATH >>>`) is **never touched** — Doctor names the owning tool and tells the user to fix it there, because that tool may regenerate its block on its own next run and collide with or undo our edit. — **Reversibility:** reversible.
- **D-23:** Guarding a foreign line is preceded by a **backup**, using the exact same `.tools-installer.old` convention Phase 15.8 already established for `~/.shellrc` consolidation — one guardrail, one mental model across the codebase. — **Reversibility:** reversible.
- **D-24:** Guarding runs from **Doctor's apply step, with per-file opt-in** — each offending file is listed and confirmed individually before it is edited, consistent with Doctor already being the audit-then-apply screen. — **Reversibility:** reversible.

### Claude's Discretion
- Exact wording of the "≠ policy" row marker (D-02) and the "broken" state's marker/color (D-18) — visual detail, not locked by the user.
- Whether the per-harness background probe (D-10/D-14) shares a worker/thread pool with the existing version-refresh worker or runs its own — implementation detail.
- Exact registry schema shape for per-method install-location declarations (D-19) — a field name/structure decision for the planner, not a user-facing choice.
- Full audit list of other tools needing per-OS location fixes beyond kitty (D-19) — to be discovered during research/planning, not pre-enumerated here.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Ownership and version
- `installer/ownership.py` — full module; D-05/D-01 adapter pattern from Phase 15 (`_native_owner`), `NATIVE_OWNERS`/`OS_PACKAGE_OWNER`/`UNMANAGEABLE_OWNERS`, the "claim only on proof" doctrine (lines 22-26) that D-01/D-08 must preserve.
- `installer/install_ownership.py` — `detect_owner`, `_PROBES` table (already contains `brew` and `sdkman` probes that no tool declares — `owner_probes`), `path_owner_package` (the INVERSE "whatever owns this path, name it" query — same shape D-02's groovy case needs), `_sdkman` probe at line 364 (reads a `sdk_candidate` param the registry never writes under `[[tool.method]] kind = "sdkman"` — reads `candidate` instead, so it can never match).
- `installer/model.py:271-272` — `owner_probes` field, per-tool opt-in probe list (D-10's background-CLI pattern is the skill_pack analog of this).
- `installer/status.py` — `is_installed`, just fixed (commit `3544e52`) to consult a method's declared `bin_dir`; D-19's per-method location declarations extend this same field for ownership proof too.
- `installer/version_cache.py` — the caching pattern D-10/D-14 must reuse for skill_pack harness-CLI results.
- `.planning/phases/15-catalog-accuracy-doctor-refresh-version-parsing-ownership-at/15-CONTEXT.md` — D-05/D-06 adapter precedent this phase extends rather than re-derives.

### skill_pack detection
- `installer/skill_lifecycle.py` — `inspect_status()` (zero callers today), `SkillLifecycle`/`SkillTarget` model, `_status_probe` (only `codex_plugin_status` and `pi_package_status` operation_ids reviewed so far — D-09's audit must check every declared harness has a working status operation).
- `installer/registry.toml` — every `[[tool.method]] kind = "skill_pack"` entry's `supported_harnesses` and `targets` (placeholder tokens like `<pi-package-dir>`, `<selected-skill>`, not resolvable paths — D-19's per-method location mechanism should likely absorb these too).
- https://github.com/obra/superpowers/blob/main/README.md — verified upstream host-support list, source of D-09's correction.
- https://code.claude.com/docs/en/plugins-reference — `installed_plugins.json` / Claude Code plugin manifest shape, relevant if a disk-fallback (D-11) is needed for Claude Code specifically.

### Row states and post-install
- `installer/wizard_app.py` (`DoctorScreen`) — `action_apply`/`_refresh_guidance` (Phase 15's D-01/D-02 precedent for conditional guidance text — D-16's "short reason" follows the same shape).
- `installer/deps.py:111` — `satisfied_by_install` drops any installed tool regardless of outdated status with no notice; this is the root cause D-17 fixes.
- `installer/post_install.py` — full module docstring; the one-shot-trigger doctrine ("a tool the installer detects as already present never reaches this table at all... not an oversight to be widened") that D-20 must preserve exactly, extending it only for explicit re-selection.
- `installer/resolve.py:75` — skips native package managers on immutable hosts; the reason kitty (pre-fix) and alacritty (unrelated, already in the registry) have no method on Bazzite.
- `.planning/todos/pending/2026-09-16-detect-dangling-pnpm-global-bin-shims-in-doctor.md` — the dangling-shim investigation D-18 closes; already has root cause confirmed (pnpm shim survives a comma-group removal that deletes the module it points at).
- `docs/catalog-unsupported-tools.md` — the doc already recording per-tool "no method on this platform" explanations (kitty, alacritty); D-16's reasons should likely cite the same doc rather than duplicate its prose.

### Foreign PATH lines
- `installer/rcclean.py` — `unguarded_path_writers` (just added, commit `2eaae39`) already names which foreign files add a duplicate; D-21-D-24 build the guard-in-place action on top of this existing detection, not a new scan.
- `.claude/architecture.md` — Phase 15.8 section: the consolidation guardrails (backup-then-write, byte-exact refusal, never touch an indented line inside an `if`/`case` block) D-21/D-22/D-23 must follow for consistency, not reinvent.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `installer/install_ownership.py::path_owner_package` — the inverse-ownership-query pattern (resolve from the path backward, no declared candidate needed) is structurally the same question D-01/D-02 ask of brew for an SDKMAN-declared tool; extend this pattern rather than writing a new one.
- `installer/version_cache.py` — caching mechanism D-10/D-14 reuse directly for skill_pack harness-CLI results.
- `installer/rcclean.py::unguarded_path_writers` — already does the detection half of D-21; only the guard-in-place write action is new.
- Phase 15.8's `.tools-installer.old` backup convention — D-23 reuses it verbatim rather than inventing a second backup scheme.

### Established Patterns
- `.claude/architecture.md` rule 5 (no duplicate production helpers with the same behavior) — governs how D-01's owner-proof mechanism and D-19's per-method location mechanism should connect (one proof source, not two).
- `installer/ownership.py`'s "evidence rule" (claim only on active-path match or complete negative evidence) — D-01, D-06, D-08 are all refinements within this existing rule, not a loosening of it.
- `installer/post_install.py`'s one-shot-trigger doctrine — D-20 is a narrow, explicit exception (re-trigger ONLY on fresh explicit selection) stated to avoid accidentally widening the general rule.

### Integration Points
- `installer/deps.py` and `installer/engine.py`'s `ALREADY_INSTALLED` short-circuit — where D-17's "outdated → update, current → say so, policies always apply on selection" logic is inserted.
- `installer/wizard_app.py` `DoctorScreen` — where D-16's reason text and D-21-D-24's per-file guard-in-place confirmation UI are added.
- `installer/registry.toml` — every `skill_pack` method's `supported_harnesses` (D-09 audit) and every method's new location declaration (D-19).

</code_context>

<specifics>
## Specific Ideas

**kitty was investigated live during this discussion, not assumed.** The user corrected an initial wrong assumption (that kitty was OS-image-owned); checking the real machine showed `~/.local/bin/kitty -> ~/.local/kitty.app/bin/kitty`, kitty's own official userspace installer layout, with no `/usr/bin/kitty` at all. This became D-19's generalization: the registry needs real per-OS, per-package-nature install locations (plain binary vs. macOS `.app` vs. Linux app-bundle-in-home), not an assumption that native package managers are the only path. The user explicitly asked this be audited across other tools too, not special-cased for kitty alone.

**The groovy/SDKMAN ownership conflict is real, not hypothetical** — the user has it installed via Homebrew right now, confirmed by `brew list --formula` showing `groovy`, `gradle`, `maven`, `openjdk`. D-01 through D-05 were worked out against this exact live case.

**Area 2 (skill_pack) started from a wrong premise the user corrected**, not from a gray area the user needed to choose between: the registry's `supported_harnesses: ["pi"]` for superpowers is simply wrong, verified against upstream. D-09 states this as a data-correctness requirement, not a design decision with options.

</specifics>

<deferred>
## Deferred Ideas

- **brew→SDKMAN migration flow** (D-04) — remove the brew formula, install the SDKMAN candidate, handle dependents (brew's `openjdk` vs SDKMAN's `java` is the concrete case). Needs its own design: dependency handling, rollback, confirmation flow. Deferred to its own future phase, explicitly not folded into Phase 16.
- **kitty-setup project's own `.bashrc` block** (`# >>> my-kitty PATH >>>`) emits an unguarded `~/.local/bin` prepend. This is upstream of this repo (`../kitty-setup`), not something `tools-installer` can or should fix — noted so it isn't mistaken for an in-scope foreign-PATH-line case; D-22 explicitly says such blocks are named, never edited.

### Folded Todos
- `2026-09-16-detect-dangling-pnpm-global-bin-shims-in-doctor.md` — folded into D-18 (the "broken" row state). The todo's own investigation (pnpm shim surviving a comma-group removal that deleted `@mermaid-js/mermaid-cli`'s module) is the concrete reproduction case for D-18's design.

### Reviewed Todos (not folded)
None — only one todo matched this phase's scope (score 0.9), and it was folded.

</deferred>

---

*Phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di*
*Context gathered: 2026-09-24*
