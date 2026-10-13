# Phase 4: Package Manager Redirect Policy - Context

**Gathered:** 2026-09-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Every banned command that has a safe, argv-compatible managed-toolchain
equivalent transparently redirects to it instead of hard-blocking, without
losing the underlying command's real exit code/stdout/stderr and without
silently losing pnpm's gated-postinstall security where that matters. This
phase was originally scoped as npx-only; it expanded during this
discuss-phase session (see `<specifics>` below) to also cover pip/pip3 and a
npm-global-to-Volta split, since both were already open questions recorded
against `installer/guards.py`'s existing ban mechanism and the Volta split
directly resolves a previously-deferred requirement.

</domain>

<decisions>
## Implementation Decisions

### Shim architecture
- **D-01:** `npx` (and any other tool this phase redirects) gets a NEW `REDIRECTED` shim mechanism, implemented parallel to the existing `BANNED` hard-block dict in `installer/guards.py` — never a generalization of `BANNED` itself. The existing hard-block shim (`shim_script`, 4-line POSIX-sh, exit 127) stays untouched and simple; a redirect shim execs into its target command, preserving the real exit code and stdout/stderr (e.g. `exec pnpm dlx "$@"`).
- **D-02:** `guard_status()`'s return shape stays an unchanged `{name: bool}` ("shim installed") — ROADMAP SC#6's literal ask. The doctor UI's per-tool label text is what distinguishes them: e.g. "redirected to pnpm dlx" for npx vs. "blocked" for npm. No new status enum, no ripple into `doctor.py`/`render.py` call sites that assume a plain bool today.

### npx redirect target
- **D-03:** `npx <pkg>` execs into `pnpm dlx "$@"` — not `pnpx` (pnpm's own shortcut for the same thing). Explicit and always available wherever pnpm is, no dependency on a separate `pnpx` binary/alias existing.

### Scope expansion (2026-09-04, mid-discussion)
- **D-04:** The user asked whether pip/pip3 should also become redirects instead of staying hard-blocked, given `installer/guards.py` already carries an open, unresolved note about this (raised 2026-09-04 at the batch-2 merge gate — see REQUIREMENTS.md's REQ-npm-npx-redirect-policy history). Decision: **yes, research it now, implement in this same phase if research confirms it's safe.** Research question: is `uv pip <subcommand>` (`install`/`uninstall`/`list`/`show`/`freeze`/`compile`) a safe, argv-compatible drop-in for the pip invocations this project's shim needs to cover? If yes, pip/pip3 redirect the same way npx does (D-01/D-02 mechanism, reused). If research finds a real gap, pip/pip3 stay hard-blocked and the gap gets documented in the plan/summary — never force a redirect past what research actually confirms.
- **D-05:** `npm` itself (non-global invocations — `install`/`add`/`run`/`exec`/`ci`/`publish` without `-g`/`--global`) stays hard-blocked either way. Its own subcommand-allowlist decision (which npm subcommands have clean pnpm equivalents vs. which don't) remains a separate, later concern — explicitly NOT part of this phase, regardless of the pip/pip3 and Volta expansion.
- **D-06:** A `-g`/`--global` flag on `npm install`/`npm add` (and on `pnpm add -g` itself) is detected and redirected specifically to `volta install <pkg>` instead of `pnpm`. A non-global `npm install`/`npx` invocation still redirects to plain `pnpm`/`pnpm dlx` per D-03. Rationale (user, 2026-09-04): Volta is a toolchain-version-manager-plus-global-tool-shim layer with no local/per-project dependency-installation mechanism of its own — "global installs → volta, local project installs → pnpm" is the natural boundary between the two tools, not an approximation.
- **D-07:** D-06 is gated on research first: does `volta install` shell out to npm internally for the actual install step? If so, it inherits npm's unrestricted-postinstall-script behavior, losing pnpm's gated-postinstall security advantage for anything moved to Volta. This is the deciding factor for whether the Volta redirect ships as a clean win or a documented security-for-stability tradeoff the user explicitly accepts. Record the finding either way — do not implement the redirect while treating this as assumed-safe.
- **D-08:** The Volta redirect (D-06/D-07) is included in *this* phase specifically because it resolves `REQ-pnpm-global-reinstall-mitigation`'s root cause (pnpm loses its globally-installed package set on self-update) for anything moved to Volta — that requirement is re-pointed here from its prior "Phase 5, sequences after Phase 12" placeholder assignment. Concretely: after implementing D-06, determine whether any catalog tool still needs `pnpm add -g` at all. If the residual set is empty, `REQ-pnpm-global-reinstall-mitigation` is satisfied by elimination — record that explicitly. If any tool remains on `pnpm add -g`, implement the requirement's original mechanism (snapshot the pnpm-managed global set, reinstall it together in one invocation after `pnpm` itself updates) for that residual set, in this same phase.

### Claude's Discretion
- Exact wording of the doctor UI's per-tool status label text (D-02) — implementation detail.
- Whether the `REDIRECTED` mechanism's dict/data structure lives in `installer/guards.py` alongside `BANNED` or in a small sibling module — planner's call, informed by 01/02/03's precedent of keeping related mechanisms in the same file when small.
- Exact shape of the pip/pip3 argv-translation (e.g. does `pip install X` become `uv pip install X` via a straight passthrough, or does some flag need remapping) — this is what the D-04 research must actually determine, not something to guess ahead of it.

### Post-research resolutions (2026-09-05, autonomous run — no user available to ask; resolved from D-06/D-08's own text and existing precedent, recorded here so the planner and any reviewer can see the reasoning)
- **R-01 (scope of D-06's "and on `pnpm add -g` itself"):** D-06's text already answers this literally — yes, `pnpm add -g <pkg>` must also be detected and redirected to `volta install <pkg>`, not just guidance. This requires a conditional wrapper on the real `pnpm` binary (04-RESEARCH.md's "Pattern 3"): when invoked with `-g`/`--global`, exec into `volta install`; every other `pnpm` invocation execs into the real `pnpm` unmodified, so pnpm's normal function is never at risk. This is genuinely new territory for `installer/guards.py` (existing redirects/bans never had to stay a full pass-through for the non-triggering case) — the planner should treat this as its own task with its own argv-parsing tests, not an extension of the flat `REDIRECTED` dict shape D-01 defines for npx/pip.
- **R-02 (volta as a registry.toml entry):** Yes — D-06's redirect is non-functional if `volta` isn't installed, so this phase adds `volta` to `registry.toml` as a `tier="system"` tool (mirroring `uv`/`pnpm`/`brew`'s existing tier per Phase 1's tier field), installed via `brew` (research found no unusual install story). The D-06/D-07 redirect must gate on volta's presence the same way Phase 3's `omz_plugins_policy` gated enabling on `omz_present` — redirecting to a binary that may not exist would trade one broken command for another. If volta is absent, the existing hard-block behavior for that invocation stays in place (fails safe, not silently).
- **R-03 (what triggers the pnpm-global snapshot-reinstall mechanism for the `mmdc` residual set):** D-08 requires the *mechanism* to exist in this phase, not an automatic trigger — the natural automatic trigger (a version-aware update action noticing pnpm just updated) is Phase 12's not-yet-built infrastructure, and this phase must not take a dependency on it. Resolution: implement the snapshot-and-reinstall as a manually-invokable Doctor remediation (parallel to the existing PATH-repair fix flow) that a user runs after noticing pnpm lost its global set — audit-only until invoked, matching this project's existing "read-only audit, explicit apply" Doctor convention. Do not attempt to auto-detect "pnpm just updated" in this phase; that wiring is Phase 12's job once its update-action mechanism exists.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements source
- `.planning/REQUIREMENTS.md` — REQ-npx-ban, REQ-npm-npx-redirect-policy (expanded text, 2026-09-04), REQ-npm-global-volta-redirect (new, 2026-09-04), REQ-pnpm-global-reinstall-mitigation (re-pointed text, 2026-09-04) — full text and history
- `.planning/ROADMAP.md` Phase 4 section — goal, 6 numbered success criteria, scope-expansion note; also see the edited cross-references in Phase 5's and Phase 12's sections noting the requirement move

### Existing pattern to mirror
- `installer/guards.py::BANNED`/`shim_script`/`is_our_shim`/`install_shims`/`remove_shims`/`guard_status`/`ban_alias_block`/`write_ban_aliases`/`remove_ban_aliases`/`guard_path_warning` (whole file, 142 lines) — the complete existing hard-block mechanism; D-01's new `REDIRECTED` mechanism sits parallel to this, following its same idempotent-shim-plus-alias shape but with an exec-through body instead of a print-and-exit-127 body
- `tests/test_guards.py` (if it exists — check) or wherever `installer/guards.py` is currently tested — existing ban tests extend to cover npx, not duplicated into a parallel file (REQ-npx-ban's explicit instruction)

</canonical_refs>

<code_context>
## Existing Code Insights

### Established Patterns
- Every banned command shim carries a sentinel comment (`SHIM_SENTINEL = "# tools-installer-ban-shim"`) so `is_our_shim` can tell a managed shim from a real binary someone else put there — a redirect shim needs the identical sentinel-based ownership check so `install_shims`/`remove_shims`-equivalents stay safe to run idempotently.
- The alias layer (`ban_alias_block`) is a faster interactive-shell message on top of the PATH-shim layer — a redirect's interactive alias should actually invoke the redirect target (not just print a message), since redirects are meant to work transparently, not just warn.

### Integration Points
- `installer/guards.py` — the new `REDIRECTED` dict/mechanism, plus wherever `install_shims`/`guard_status`/`ban_alias_block` iterate `BANNED` today needs a parallel or merged iteration over `REDIRECTED`
- `installer/doctor.py`/`installer/render.py` — wherever `guard_status()`'s per-tool bool currently renders to the doctor/status UI needs the label-text differentiation from D-02

</code_context>

<specifics>
## Specific Ideas

- User's own words on why Volta belongs here (2026-09-04): "la idea segun lo que me dijiste en ese entonces es que volta era como una pnpm -g pero sin los problemas de seguridad de npm, y esa para mi esta bien ya que el problema de pnpm ahora mismo es que al actualizarlo los paquetes instalados globales se pierden" — Volta as a `pnpm -g` replacement without npm's security problems, directly motivated by pnpm's real, currently-experienced bug of losing globally-installed packages on update.
- The scope expansion happened because the user pushed back on an initially npx-only framing, asking "¿Acaso todos los redirects son iguales? ¿Acaso se va a hacer hard block en lugar de redirect? Se deberían cambiar los bans por redirect y considerar que quizás cada uno merece atención particular... se debe hacer research para cada caso" — each banned command may deserve its own redirect-target research rather than assuming a uniform mechanism. D-01/D-02's parallel-mechanism design (rather than generalizing BANNED) is a direct response to this: it keeps room for per-tool differences (a redirect target, an exec shape) without forcing every future ban into one rigid shape.

</specifics>

<deferred>
## Deferred Ideas

- npm's own subcommand-allowlist decision (non-global invocations) — explicitly out of this phase per D-05, a separate future decision.
- Applying the same "does a safe redirect exist" research question to any *future* banned command beyond npm/npx/pip/pip3 — noted as a general principle in the user's original question, but not itself an action item for this phase; the four tools already in scope (npx, pip, pip3, npm-global) are this phase's complete list.

</deferred>

---

*Phase: 4-package-manager-redirect-policy*
*Context gathered: 2026-09-04*
