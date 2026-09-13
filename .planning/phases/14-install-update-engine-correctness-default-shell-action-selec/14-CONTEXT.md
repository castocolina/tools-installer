# Phase 14: Install/Update Engine Correctness & Default-Shell Action - Context

**Gathered:** 2026-09-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Two independent bugs bundled by "found running the shipped v0.49.0 installer on a real machine" (ROADMAP.md, urgent insertion after Phase 12):

1. **Silent update no-op:** confirming install on a tool that is already installed but has an available update does nothing, because `resolve_dependencies` (`installer/deps.py`) excludes any already-installed tool from the install order regardless of outdated status, and `installer/engine.py::install_tool`'s `ALREADY_INSTALLED` short-circuit (`is_installed(tool)` check) never distinguishes "installed and current" from "installed and outdated." The only real update path today is the separate, per-row `u` keybind (`action_update_tool` in `installer/catalog_tui.py`). This phase unifies the two paths.
2. **Unimplemented `set_login_shell`:** the action is declared in `installer/model.py`'s `POST_INSTALL_ACTIONS`/`SENSITIVE_POST_INSTALL_ACTIONS` schema but has no dispatcher and no tool references it. This phase implements it, guarded against a documented Bazzite/KDE-SDDM login-failure bug (ublue-os/bazzite#4159) that is the reason `oh-my-zsh`'s registry entry currently forces `CHSH=no`.

</domain>

<decisions>
## Implementation Decisions

### Update-path unification
- **D-01:** Selecting an outdated, already-installed tool in the main select+enter flow (`on_tool_browser_accepted` in `installer/catalog_tui.py`) triggers the same `UpdateTarget`/`service.run` mechanism `action_update_tool` (the `u` keybind) already uses — same ownership/mutation-grade gate (`MUTATION_GRADE`), same `UpdateService`. No new update-execution code. — **Reversibility:** reversible — this only changes which code path decides to call the existing update service, not the service itself.
- **D-02:** The main flow's existing pre-run confirmation (the batch confirm before `run_installs`) is treated as the user's consent for D-01's auto-update — no separate "also update outdated tools?" prompt is added, consistent with `action_update_tool`'s own doc comment ("Immediate, no confirmation (D-01 in that screen's own code)"). — **Reversibility:** reversible.

### Blocked-update messaging
- **D-03:** When the ownership/mutation-grade gate blocks an auto-update during the batch (owner unknown or `ownership.confidence` outside `MUTATION_GRADE`) — the same gate `action_update_tool` already applies — the reason is accumulated per-tool and surfaces in the existing post-run summary (`render_summary`/`render_failure_details` in `installer/app.py::run_wizard`), not as an inline message during the run. Reuse the exact reason text `action_update_tool` already produces (`"cannot update {tool_id}: {reason}"`), not new wording. — **Reversibility:** reversible.

### `set_login_shell` guard and confirmation
- **D-04:** `Platform.immutable` (already computed and used at `installer/resolve.py:75-76` to skip the `rpm_ostree` method) is a hard guard: on an immutable host, `set_login_shell` is never offered or executed, no exception — this covers Bazzite. — **Reversibility:** one-way — relaxing this later for a specific atomic variant would require re-verifying ublue-os/bazzite#4159 doesn't reproduce there; loosening a safety guard silently is the wrong default.
- **D-05:** On a non-immutable host, `set_login_shell` still requires an explicit confirmation step before running (a confirm prompt, following the existing `SENSITIVE_POST_INSTALL_ACTIONS` classification already in `model.py`) — never fires automatically even off atomic distros. — **Reversibility:** reversible.

### `set_login_shell` scope and dispatch site
- **D-06:** `set_login_shell` is dispatched as a `post_install` action inside the existing `oh-my-zsh` install ladder — the same mechanism already declared in `installer/model.py`'s `POST_INSTALL_ACTIONS` and referenced by the `oh-my-zsh` registry entry's intended use. No new install-time action-invocation surface is created. — **Reversibility:** reversible.
- **D-07:** Scope stays zsh-only for this phase — no generalization to an arbitrary "future shell" parameter. The registry today has exactly one shell-configuration entry (`oh-my-zsh`); generalizing now would be speculative design for a second case that doesn't exist yet. — **Reversibility:** reversible — a future generalization would add a parameter, not restructure this phase's implementation.

### Claude's Discretion
- Exact wording of the batch-summary line for D-03 (as long as it reuses `action_update_tool`'s reason string as the substantive content).
- Exact UI shape of the D-05 confirmation prompt (modal vs inline `_ask_select`-style prompt) — follow whatever pattern `installer/app.py::run_wizard`'s existing `prompter.confirm(...)` step already uses for consistency.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Update engine
- `installer/deps.py::resolve_dependencies` — the exclusion-of-already-installed logic that causes the silent no-op (see its own docstring: "Already-installed tools are satisfied as-is... excluded from the returned order").
- `installer/engine.py::install_tool` lines ~90-118 — `ALREADY_INSTALLED` short-circuit via `is_installed(tool)`.
- `installer/catalog_tui.py::action_update_tool` (line ~556) and `_update_tool_worker` — the existing, tested `UpdateTarget`/`service.run` mechanism to reuse, including its ownership/mutation-grade gate.
- `installer/catalog_tui.py::on_tool_browser_accepted` (line ~649) — the main select+enter confirm flow this phase must wire the update path into.
- `tests/test_catalog_tui.py` lines 1379-1487, 1665, 1741 — existing coverage of `action_update_tool`'s gate behavior; new tests for the unified path should follow the same fixtures/patterns.

### Default-shell action
- `installer/model.py` lines 46-54 — `POST_INSTALL_ACTIONS` (includes `set_login_shell`) and `SENSITIVE_POST_INSTALL_ACTIONS` (already classifies it as sensitive).
- `installer/registry.toml` lines 526-542 — the `oh-my-zsh` tool entry, currently `env = { RUNZSH = "no", CHSH = "no", KEEP_ZSHRC = "yes" }` — the `CHSH=no` is the existing workaround this phase's guarded implementation replaces with a real, gated action.
- `installer/resolve.py` lines 70-76 — `Platform.immutable` check pattern (used today to skip `rpm_ostree`), the exact primitive D-04 reuses.
- ublue-os/bazzite#4159 — the documented Bazzite/KDE-SDDM login-failure bug that motivates the guard (external GitHub issue, referenced by ROADMAP.md's Phase 14 description; not a local file).

### Roadmap source
- `.planning/ROADMAP.md` lines 464-473 — Phase 14's full urgent-insertion description (the source of both bug reports).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `UpdateTarget` / `UpdateService.run` (used by `action_update_tool`) — the entire update-execution mechanism (ownership resolution, mutation-grade gate, global replay, cleanup warnings, postinstall re-run) is production-ready and tested; this phase only needs a second call site, not new logic.
- `Platform.immutable` — already computed platform state; reused as-is for the `set_login_shell` guard.
- `SENSITIVE_POST_INSTALL_ACTIONS` classification in `model.py` — already exists; this phase implements the dispatcher that respects it, not the classification itself.

### Established Patterns
- One-view-registry / one-apply-workflow constraint (`.claude/architecture.md`) — any new confirmation UI (D-05) must fit within `run_wizard`'s existing `prompter.confirm(...)` pattern rather than inventing a parallel prompt mechanism.
- `resolve.py`'s `if platform.immutable: return False` pattern — the established idiom for "skip on atomic distros," now reused for the shell-change guard.

### Integration Points
- `installer/catalog_tui.py::on_tool_browser_accepted` → needs a check for outdated-and-selected tools before/alongside dispatching the batch, routing those to the `UpdateTarget` mechanism.
- The `oh-my-zsh` install ladder (wherever `post_install` actions are dispatched after a successful install method — the actual dispatcher for `POST_INSTALL_ACTIONS` names, which does not yet exist for `set_login_shell` specifically) is the integration point for D-06.

</code_context>

<specifics>
## Specific Ideas

No specific UI mockups or exact wording were dictated — the discussion focused on *which mechanism* to reuse (existing `UpdateTarget` service, existing `Platform.immutable` guard, existing `POST_INSTALL_ACTIONS` schema) rather than new design. The consistent theme across all four decisions: reuse what Phase 12's update-action work and the existing schema already built, rather than adding parallel mechanisms.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. No scope-creep suggestions arose during this discussion.

</deferred>

---

*Phase: 14-install-update-engine-correctness-default-shell-action-selec*
*Context gathered: 2026-09-13*
