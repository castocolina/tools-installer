# Phase 14: Install/Update Engine Correctness & Default-Shell Action - Research

**Researched:** 2026-09-14
**Domain:** Python/Textual TUI install-engine control flow (dependency resolution, update dispatch) + a new sensitive system-mutation action (`chsh`-equivalent shell change)
**Confidence:** HIGH for the current-implementation analysis (everything below is read from the live tree this session); MEDIUM for the `set_login_shell` execution-mechanism recommendation (grounded in verified primitives, but the final wiring choice is a genuine open design decision for the planner)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Update-path unification**
- **D-01:** Selecting an outdated, already-installed tool in the main select+enter flow (`on_tool_browser_accepted` in `installer/catalog_tui.py`) triggers the same `UpdateTarget`/`service.run` mechanism `action_update_tool` (the `u` keybind) already uses — same ownership/mutation-grade gate (`MUTATION_GRADE`), same `UpdateService`. No new update-execution code. — **Reversibility:** reversible.
- **D-02:** The main flow's existing pre-run confirmation (the batch confirm before `run_installs`) is treated as the user's consent for D-01's auto-update — no separate "also update outdated tools?" prompt is added, consistent with `action_update_tool`'s own doc comment ("Immediate, no confirmation (D-01 in that screen's own code)"). — **Reversibility:** reversible.

**Blocked-update messaging**
- **D-03:** When the ownership/mutation-grade gate blocks an auto-update during the batch (owner unknown or `ownership.confidence` outside `MUTATION_GRADE`) — the same gate `action_update_tool` already applies — the reason is accumulated per-tool and surfaces in the existing post-run summary (`render_summary`/`render_failure_details` in `installer/app.py::run_wizard`), not as an inline message during the run. Reuse the exact reason text `action_update_tool` already produces (`"cannot update {tool_id}: {reason}"`), not new wording. — **Reversibility:** reversible.

**`set_login_shell` guard and confirmation**
- **D-04:** `Platform.immutable` (already computed and used at `installer/resolve.py:75-76` to skip the `rpm_ostree` method) is a hard guard: on an immutable host, `set_login_shell` is never offered or executed, no exception — this covers Bazzite. — **Reversibility:** one-way.
- **D-05:** On a non-immutable host, `set_login_shell` still requires an explicit confirmation step before running (a confirm prompt, following the existing `SENSITIVE_POST_INSTALL_ACTIONS` classification already in `model.py`) — never fires automatically even off atomic distros. — **Reversibility:** reversible.

**`set_login_shell` scope and dispatch site**
- **D-06:** `set_login_shell` is dispatched as a `post_install` action inside the existing `oh-my-zsh` install ladder — the same mechanism already declared in `installer/model.py`'s `POST_INSTALL_ACTIONS` and referenced by the `oh-my-zsh` registry entry's intended use. No new install-time action-invocation surface is created. — **Reversibility:** reversible.
- **D-07:** Scope stays zsh-only for this phase — no generalization to an arbitrary "future shell" parameter. — **Reversibility:** reversible.

### Claude's Discretion
- Exact wording of the batch-summary line for D-03 (as long as it reuses `action_update_tool`'s reason string as the substantive content).
- Exact UI shape of the D-05 confirmation prompt (modal vs inline `_ask_select`-style prompt) — follow whatever pattern `installer/app.py::run_wizard`'s existing `prompter.confirm(...)` step already uses for consistency.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope. No scope-creep suggestions arose during CONTEXT.md's discussion.

**IMPORTANT CORRECTION surfaced by this research (see "Current Implementation Analysis" below):** D-02's and the Claude's-Discretion note's references to `run_wizard`'s `prompter.confirm(...)` describe the **CLI-flags path** (`--all`/`--categories`), which never touches `CatalogScreen`/`on_tool_browser_accepted` at all. The actual production `make setup` interactive flow — the one `on_tool_browser_accepted` belongs to — was rewired by Phase 13 to push `ExecuteScreen` instead, whose own `enter start · esc cancel` gate (`installer/execute_screen.py:342,348-356`) is the real "existing pre-run confirmation" D-02 refers to. This does not change the *decisions* (D-01 through D-07 stand as written and are still satisfiable), but it changes *where in the live code* they must be implemented. See below.
</user_constraints>

## Summary

Phase 14 bundles two independent, already-diagnosed bugs. Both root causes are confirmed by reading the live tree this session, and both bugs live one layer deeper than CONTEXT.md's (pre-Phase-13) canonical refs describe, because Phase 13 rewired the production install-execution path from a synchronous console flow (`installer/app.py::run_wizard`) to a pushed Textual `ExecuteScreen` (`installer/execute_screen.py`) fed by `installer/wizard_app.py::UnifiedApp.on_catalog_screen_decided`. `run_wizard` is now reachable ONLY via the `--all`/`--categories` CLI-flag paths in `setup.py::main` (`setup.py:891`); it is **not** the code the phase's actual bug lives in.

**Bug 1 (silent update no-op):** `installer/deps.py::resolve_dependencies` treats "installed" as "satisfied," full stop (`is_installed(t) and t.id not in blocked` at `deps.py:111` excludes the tool from `order` regardless of version). `ExecuteScreen.on_mount` (`execute_screen.py:326-334`) calls this exact function on the ids `CatalogScreen.Decided` posts, so an outdated, already-installed, user-selected tool is silently dropped from the batch before `install_tool` is ever called — `install_tool`'s own `ALREADY_INSTALLED` short-circuit (`engine.py:116-117`) is not even reached for this case; the drop happens one layer earlier, inside dependency resolution.

**Bug 2 (`set_login_shell` unimplemented):** `installer/model.py` fully validates `Tool.post_install`/`POST_INSTALL_ACTIONS`/`SENSITIVE_POST_INSTALL_ACTIONS`/`Tool.default_enabled_sensitive_actions` at load time (`model.py:46-54`, `268-269`, `635-653`) but **zero production code reads `Tool.post_install`** — confirmed by an exhaustive grep across `installer/` and `setup.py` finding only `model.py`'s own parsing/validation lines. No registry entry declares `post_install = [...]` either. This is a from-scratch dispatcher, not a rewiring job. The genuinely hard part is not the dispatch table (mirror the existing `postinstall.py::POSTINSTALL_HOOKS` shape) — it is that `chsh`/shell-change is a **PAM-password-prompting, TTY-requiring system mutation**, and the codebase's *existing, load-bearing* doctrine for exactly this class of action (`installer/host_setup.py`'s module docstring, `host_setup.py:1-7`) is "the installer therefore displays reviewed commands to run after leaving Textual and never launches them from its worker thread." This research surfaces a genuine, unresolved design choice — reviewed-handoff-only vs. an in-process `Textual App.suspend()` handoff (verified present in the installed `textual==8.2.7`) — and recommends the former as lower-risk and consistent with existing precedent.

**Primary recommendation:** (1) Thread the update-vs-install split and the `UpdateService`/`VersionRefreshService` objects into the `ExecuteScreen`/`ExecuteInputs` seam (they are already constructed once in `setup.py::_build_app` and already shared with `CatalogScreen`, `setup.py:572-601,620-622`) rather than trying to execute updates from `CatalogScreen` before the `Decided` message is posted. (2) Implement `set_login_shell` as a new `POST_INSTALL_HOOKS`-shaped closed dispatch table dispatched from `install_tool` immediately after a successful `oh-my-zsh` method (mirroring the existing `tool.postinstall` call site at `engine.py:150-154`), gated by `Platform.immutable` (hard) and a new optional confirm callback threaded through `install_tool`/`run_installs` the same way `on_mismatch`/`OnMismatch` already is (`session.py:75`, `17`) — and have that confirm's "yes" branch produce **reviewed handoff instructions** (`chsh -s $(which zsh)`) rather than actually invoking `chsh` from a worker thread, consistent with `host_setup.py`'s documented precedent.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Dependency/update-eligibility resolution (`resolve_dependencies`) | Backend/core (`installer/deps.py`) | — | Pure, terminal-free decision function; both the TUI (`ExecuteScreen`) and CLI (`run_wizard`) call it, per `.claude/architecture.md`'s "ExecuteScreen is a thin IO adapter, not a second decision layer." |
| Update mutation (ownership re-resolution, argv dispatch, replay, cache invalidation) | Backend/core (`installer/update.py::UpdateService`) | — | Already built, tested, and shared across all three `CatalogScreen` tier instances (`update.py:307-326`); this phase's job is a *second call site*, never new mutation logic (D-01). |
| Install-run orchestration + confirm gate | Textual TUI (`installer/execute_screen.py::ExecuteScreen`) | Backend/core (`installer/session.py::run_installs`) | `ExecuteScreen` owns the "enter start" confirm and progress display; `run_installs`/`install_tool` own the actual decision-and-execute logic it streams. |
| `set_login_shell` dispatch (new) | Backend/core (`installer/engine.py::install_tool`, new `installer/post_install.py`-shaped module) | Textual TUI (confirm modal) + main-thread terminal handoff | The mutation itself (deciding *whether* to run, and what to hand off) is core logic mirroring `postinstall.py`; the *confirm* and any terminal-owning step must cross into the TUI/main-thread layer because a worker thread cannot safely own the real terminal (`host_setup.py:1-7`). |
| Platform-immutability gate | Backend/core (`installer/platform.py::Platform.immutable`, `installer/resolve.py`) | — | Already computed once per run (`platform.py:52-54`); reused as-is (D-04). |

## Standard Stack

No new third-party libraries are introduced by this phase. Both bugs are fixed entirely with existing stdlib (`subprocess`) and existing in-repo primitives (`installer.deps`, `installer.update`, `installer.postinstall`-shaped dispatch, `installer.run`, Textual's own `App.suspend()`). `textual` itself is already a pinned dependency (`pyproject.toml:9`, `textual>=8`; the installed version this session is `8.2.7`, confirmed via `uv run python3 -c "import textual; print(textual.__version__)"` [VERIFIED: live `uv run` this session]).

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Reviewed handoff instructions for `set_login_shell` (never run `chsh` from the app) | `App.suspend()` + inline `chsh` invocation | Suspend is real and available (verified below) but is a genuinely new interaction pattern nowhere else in this codebase uses; the existing `host_setup.py` precedent for "needs a real terminal" is explicitly handoff-only. Higher engineering/testing cost for one action. |
| `chsh -s <path>` (POSIX standard, PAM-password-prompting) | `usermod -s <path> $USER` | `usermod` typically requires root/sudo unconditionally, which is a *worse* UX/security posture for a per-user preference change than `chsh`'s "only your own password, only your own shell" model. Not recommended. |

**Installation:** No new packages. No `npm install`/`pip install`/`uv add` needed for this phase.

**Version verification:** N/A — no new dependencies.

## Package Legitimacy Audit

**Not applicable.** This phase installs no new external packages (npm, PyPI, crates, or otherwise). All work is in-repo Python plus a system-provided `chsh` binary the OS already ships. The Package Legitimacy Gate protocol was not run because there is nothing to check against a registry.

## Architecture Patterns

### Current Implementation Analysis (live tree, grounded this session)

**The two production entry points, and which one this phase's bug actually lives in:**

`setup.py::main` (`setup.py:838-911`) branches on CLI flags:
- No `--all`/`--categories` (the default, genuine interactive `make setup`): `_run_interactive_wizard` (`setup.py:672-711`) → `_build_app(..., execute=_execute_inputs(...))` (`setup.py:684-694`) → `app.run()`. This is `UnifiedApp` (`installer/wizard_app.py`), and `_build_app` constructs `version_refresh`/`updates` (`setup.py:572-601`) and passes them **alongside** `execute` into the same `UnifiedApp(...)` call (`setup.py:603-624`, specifically lines 620-622: `version_refresh=version_refresh, updates=updates, execute=execute,`). `CatalogScreen.on_tool_browser_accepted` (`catalog_tui.py:650-661`) posts `Decided(ids)`; `UnifiedApp.on_catalog_screen_decided` (`wizard_app.py:1812-1816`) does:
  ```python
  def on_catalog_screen_decided(self, message: CatalogScreen.Decided) -> None:
      if self._execute is None or message.result is None:
          self.exit(message.result)
          return
      self.push_screen(ExecuteScreen(message.result, self._execute), self._install_closed)
  ```
  [VERIFIED: installer/wizard_app.py:1812-1816] — when `execute` is given (which it always is on the real `make setup` path), `run_wizard` is **never called**. `ExecuteScreen.on_mount` (`execute_screen.py:325-346`) does its own `resolve_dependencies` + `render_head` (the "Install N tools? enter start · esc cancel" line at `execute_screen.py:342`) and only starts the real work on `action_start` (bound to `enter`, `execute_screen.py:282,348-356`).
- `--all` or `--categories A,B`: `run_wizard(tools, platform, prompter, console, options, on_mismatch=_ask_mismatch, category_blurbs=...)` (`setup.py:891-899`) is called **with no `select_catalog` argument**, so `_choose_tools` (`app.py:85-108`) takes the `options.all`/`options.categories` branch and never touches `CatalogScreen`/`ToolBrowser`/`on_tool_browser_accepted` at all. This is confirmed by `tests/test_wizard_app.py:4123-4128`'s `test_accepting_the_catalog_without_execute_still_exits_with_ids`, which shows the ONLY way `UnifiedApp` skips `ExecuteScreen` is when `execute=None` — a configuration the real `make setup` interactive path never uses.

**Conclusion (HIGH confidence, directly read this session):** CONTEXT.md's reference to `run_wizard`'s `prompter.confirm("Install the selected tools?")` (`app.py:148`) as "the main flow's existing pre-run confirmation" is **stale** — it describes a different, CLI-flags-only code path that the phase's actual bug (selecting an outdated tool via the TUI catalog and pressing enter) never reaches. The real pre-run confirmation for the main select+enter flow is `ExecuteScreen`'s own `enter start` gate. D-02 is still satisfiable (there genuinely is exactly one confirm step before mutation in the real flow) — the planner must just implement against `ExecuteScreen`, not `run_wizard`.

**Where Bug 1 actually happens, traced end to end:**

1. `on_tool_browser_accepted` (`catalog_tui.py:650-661`) computes `ids` from `select_tools(self._catalog, list(self._staged))`, filtering only `self._unavailable` — **it does not consult `self._version_statuses` or `self._installed` at all**. An outdated, already-installed, selected tool's id is included here.
2. `Decided(ids)` propagates unchanged through `UnifiedApp` to `ExecuteScreen(message.result, self._execute)`.
3. `ExecuteScreen.on_mount` (`execute_screen.py:326-334`):
   ```python
   selected = select_tools(self._inputs.catalog, self._ids)
   resolved = resolve_dependencies(
       order_for_install(selected),
       self._inputs.catalog,
       available=lambda tool: bool(resolve_methods(tool, platform)),
       is_installed=self._inputs.installed,
   )
   self._ordered = list(resolved.order)
   ```
   [VERIFIED: installer/execute_screen.py:326-334]. Inside `resolve_dependencies` (`deps.py:32-138`), `is_blocked` (`deps.py:81-100`) treats any `is_installed(tool) == True` tool as `not blocked` (line 85-86: `if is_installed(tool): return False`), and then line 111 excludes it from `runnable`/`order` regardless: `satisfied_by_install = {t.id for t in wanted if is_installed(t) and t.id not in blocked}` then `runnable = [t for t in wanted if t.id not in blocked and t.id not in satisfied_by_install]` (`deps.py:111,113`) [VERIFIED: installer/deps.py:81-113, quoted above]. **The tool never reaches `self._ordered`, so it never reaches `run_installs`/`install_tool` at all** — this is a strictly earlier drop than `install_tool`'s own `ALREADY_INSTALLED` short-circuit (`engine.py:116-117`), confirming CONTEXT.md's second-listed mechanism (`install_tool`'s short-circuit) is not actually where the silent no-op happens for the TUI path; it is `resolve_dependencies` alone.
4. The existing `test_already_installed_dependency_is_not_dragged_in` (`tests/test_deps.py:64-69`) only tests the "not dragged in as someone else's *dependency*" case, not "explicitly *selected*, installed, and outdated" — there is currently no test asserting behavior for a selected-but-outdated tool anywhere in `tests/test_deps.py`, `tests/test_execute_screen.py`, or `tests/test_catalog_tui.py` (confirmed by grep across all three files for `outdated` combined with `resolve_dependencies`/`on_tool_browser_accepted`/`on_mount`). This is a genuine Wave-0 test gap, not merely an existing-test update.

**The existing, reusable update mechanism (`u` keybind), read in full — this is what D-01 says to reuse:**

`CatalogScreen.action_update_tool` (`catalog_tui.py:558-583`) and `_update_tool_worker` (`catalog_tui.py:585-610`):
```python
def action_update_tool(self) -> None:
    """Press `u` on the highlighted row. Immediate, no confirmation (D-01)."""
    if self._updates is None or self._version_refresh is None:
        return
    tool_id = self._browser.highlighted_id()
    ...
    status = self._version_statuses.get(tool_id)
    if status is not None and status.outdated is False:
        return
    ownership = self._version_refresh.ownership_of(tool_id)
    if ownership is None:
        return
    if ownership.owner == "unknown" or ownership.confidence not in MUTATION_GRADE:
        reason = ownership.unknown_reason or "no manager claimed this tool"
        self.status.set(f"cannot update {tool_id}: {reason}", "warn")
        return
    if not self._updates.begin(tool_id):
        ...
    self._update_tool_worker(tool_id)
```
[VERIFIED: installer/catalog_tui.py:558-583, quoted]. Two things worth calling out precisely for the planner:
- The eligibility gate is `status is not None and status.outdated is False` → skip. **Both `status is None` (unknown — version refresh hasn't completed) and `status.outdated is True` fall through and attempt the update.** This exact predicate is asserted by `tests/test_catalog_tui.py:1440-1488` (`test_action_update_tool_starts_worker_when_outdated_is_none`, quoted: `screen._version_statuses = {"pnpm": VersionStatus(..., outdated=None, ...)}` then `assert started == ["pnpm"]`) [VERIFIED: tests/test_catalog_tui.py:1440-1488]. Reusing this exact predicate (not "only when `outdated is True`") matters: `CatalogScreen`'s version refresh is asynchronous (`_refresh_versions_worker`, `catalog_tui.py:275-287`) and may not have completed by the time the user presses enter, so treating "unknown" as "attempt update" avoids a race where a genuinely-outdated tool is silently skipped just because the version probe was slow.
- `UpdateService.run` (`installer/update.py:366-422`) does its own **fresh** ownership re-resolution (`fresh = self._reresolve_ownership(target.tool)`, line 368) and its own `MUTATION_GRADE` check (line 369) — it never trusts the caller's cached `ownership`. This means D-01's "same ownership/mutation-grade gate" is satisfied automatically by calling `UpdateService.run`; a caller does not need to re-implement the gate, only construct an `UpdateTarget` from *some* ownership snapshot (even a stale one) and call `run`.

### System Architecture Diagram

```
User presses Enter on the main catalog screen (some selected ids are
outdated-but-installed)
        │
        ▼
CatalogScreen.on_tool_browser_accepted            [catalog_tui.py:650]
   ids = select_tools(catalog, staged) - unavailable
        │  posts CatalogScreen.Decided(ids)
        ▼
UnifiedApp.on_catalog_screen_decided              [wizard_app.py:1812]
   push_screen(ExecuteScreen(ids, self._execute))
        │
        ▼
ExecuteScreen.on_mount                            [execute_screen.py:325]
   resolve_dependencies(ids, catalog, is_installed=...)
        │
        ├──► not-installed ids ─────────────► self._ordered (install path,
        │                                       unchanged today)
        │
        └──► installed-but-outdated ids ────► TODAY: silently dropped here.
                                                THIS PHASE: must also reach
                                                a decision, per D-01/D-02/D-03.
        │
        ▼  [enter] action_start           [execute_screen.py:348]
_execute_worker (thread)                          [execute_screen.py:371]
   run_live(lambda: run_installs(self._ordered, ..., should_continue=...))
        │
        ▼
run_installs → install_tool (per tool)            [session.py:69, engine.py:89]
   is_installed(tool) → ALREADY_INSTALLED short-circuit (unaffected by this
   phase for a tool NOT selected for update; still correct for truly-current
   tools)
        │  on success, dispatches tool.postinstall (unchanged, singular hook)
        ▼
   IF method == oh-my-zsh's script method AND "set_login_shell" in
   tool.post_install:
        │
        ▼
   NEW: post_install action dispatcher            [to be built, mirrors
        (Platform.immutable hard-gate, then           postinstall.py's shape]
         confirm callback, then handoff/execute)
```

The dashed "THIS PHASE" branch is the crux of the Open Question below: does the update call happen *inside* `ExecuteScreen`'s existing worker (same `run_live`-wrapped thread, alongside `run_installs`), or does `CatalogScreen` intercept and run updates *before* ever posting `Decided`? See "Open Questions."

### Pattern 1: Extend `ExecuteInputs`/`ExecuteScreen` to also carry update capability (RECOMMENDED for D-01/D-02/D-03)

**What:** Add `version_refresh: VersionRefreshService | None` and `updates: UpdateService | None` fields to `ExecuteInputs` (mirroring how `CatalogScreen.__init__` already accepts them, `catalog_tui.py:219-220`), wired from the same `setup.py::_build_app` call site that already constructs both objects once and shares them (`setup.py:572-601,620-622`). Inside `ExecuteScreen.on_mount`, after computing `resolved = resolve_dependencies(...)`, additionally compute `needs_update = {tool.id for tool in selected if self._inputs.installed(tool) and <not confidently current>}` using the exact `status is not None and status.outdated is False → skip` predicate quoted above. Inside `_execute_worker` (the existing `@work(thread=True)` method, `execute_screen.py:371`), after (or interleaved with) the `run_installs` call, loop `needs_update` and call `UpdateService.run(UpdateTarget(tool=tool, ownership=<any snapshot, it re-resolves fresh anyway>))` via `run_live`, exactly mirroring `_update_tool_worker`'s existing single-tool body (`catalog_tui.py:585-610`) but looped sequentially (an `UpdateService` instance only permits one in-flight update at a time via its `begin`/`end` lock, `update.py:355-364`, so this is inherently sequential, not parallel, matching a single install ladder run's own sequential nature). Accumulate blocked-update reasons (`status == "unknown-owner"`) into a list and render them in the same `render_report` closure `on_install_run_finished` already builds (`execute_screen.py:500-506`) — this is the concrete implementation of D-03's "surfaces in the existing post-run summary" once translated from the pre-Phase-13 console screen onto the Phase-13-era `ExecuteScreen` log.

**When to use:** This is the only design that (a) reuses `UpdateService`/`UpdateTarget` verbatim (D-01's "no new update-execution code"), (b) puts the update dispatch behind the exact same `enter start` confirm gate as the install batch (satisfying D-02 without inventing a second prompt), and (c) keeps `resolve_dependencies` pure and untouched (it is not the right place to also decide "should I update this" — that is a `VersionStatus`/`ManagerOwnership` question `deps.py` has no access to and, per `.claude/architecture.md`'s "a screen with no `Platform` must not make a judgement it cannot make correctly," should not be given).

**Example (the piece already proven correct and reusable, single-tool form):**
```python
# Source: installer/catalog_tui.py:585-610 (existing, tested _update_tool_worker —
# the per-tool body Pattern 1 loops for the batch case)
def _update_tool_worker(self, tool_id: str) -> None:
    outcome: UpdateOutcome | None = None
    ...
    tool = self._by_id.get(tool_id)
    service = self._updates
    refresh = self._version_refresh
    if tool is None or service is None or refresh is None:
        return
    cached = refresh.ownership_of(tool_id)
    if cached is None:
        return
    target = UpdateTarget(tool=tool, ownership=cached)
    result, error = run_live(lambda: service.run(target))
    outcome = result
```

### Pattern 2: `set_login_shell` as a new closed dispatch table, mirroring `postinstall.py` but for the plural `post_install` field

**What:** `Tool.postinstall: str | None` (singular) already has a full, tested dispatch mechanism (`installer/postinstall.py::POSTINSTALL_HOOKS`, dispatched from `install_tool` at `engine.py:150-154`). `Tool.post_install: tuple[str, ...]` (plural, `model.py:268`) is architecturally distinct — architecture.md is explicit about this: *"Do not confuse this NAMED, singular `Tool.postinstall` mechanism with `installer/model.py`'s similarly-named but semantically distinct `Tool.post_install` (plural) field... the latter has zero production callers as of Phase 12.4"* [VERIFIED: .claude/architecture.md, "Phase 9: postinstall hooks" section, quoted]. Building a new, small `POST_INSTALL_HOOKS`-shaped table (even with a single `"set_login_shell"` entry, since D-07 keeps scope zsh-only) keeps this consistent with the codebase's established "registry selects a NAME from a closed, code-owned set, never a literal command" doctrine (`model.py:260-264`'s comment on the sibling singular field says the same thing) and leaves room for the other five `POST_INSTALL_ACTIONS` names to be wired in later phases without restructuring.

**When to use:** Dispatch this new table from `install_tool`, immediately after a successful method, exactly where `tool.postinstall` is already dispatched (`engine.py:150-154`) — this is the literal meaning of D-06's "inside the existing oh-my-zsh install ladder."

**The hard part — `chsh` needs a real, uncaptured terminal, and every runner this codebase has either discards or captures a child's stdin:**
- `run_command` (`run.py:45-52`, the default for `install_tool` on the plain-console `run_wizard` path) inherits the parent's stdio unmodified — fine on a genuine console, but `run_wizard` is not the path this phase's tools go through (see above).
- `StreamingRunner.__call__` (`run.py:136-181`, used by `ExecuteScreen`'s worker via `attributed_install`) explicitly sets `stdin=subprocess.DEVNULL` (`run.py:146`) — a `chsh` password prompt reading from a devnull'd stdin fails immediately or hangs, depending on the PAM stack.
- `run_captured`/`run_output` (`run.py:65-100`, used by `UpdateService`'s default runner) uses `subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=timeout)` — `capture_output=True` redirects stdout/stderr but leaves stdin inherited from the parent; inside a running Textual app, the parent's stdin is a real terminal fd but Textual has already put it in raw/alt-screen mode for its own rendering, so handing it to a child expecting a normal cooked-mode password prompt is unreliable at best and corrupts the TUI's rendered frame at worst.
- `run_interactive_command` (`run.py:55-59`) and `InteractiveTerminalUnavailable` (`run.py:41-42`) already exist and look purpose-built for exactly this ("Run approved argv with the active terminal available for system prompts," checking `sys.stdin.isatty()`/`sys.stdout.isatty()` first) — but a repo-wide grep for `run_interactive_command`/`InteractiveTerminalUnavailable` outside `installer/run.py` itself returns **zero matches** [VERIFIED: grep across `installer/`, `setup.py`, `tests/` this session]. It is unused scaffolding, not a proven pattern — and critically, `isatty()` alone does not detect "Textual currently owns and has reconfigured this terminal," so this check alone is insufficient protection against corrupting the TUI mid-run.
- The codebase's own **existing, load-bearing, already-shipped** doctrine for "this genuinely needs a live terminal, cannot be safely scripted from a Textual worker thread" is `installer/host_setup.py`'s module docstring: *"These setup flows need a terminal or a user-selected project. The installer therefore displays reviewed commands to run after leaving Textual and never launches them from its worker thread."* [VERIFIED: installer/host_setup.py:1-7, quoted verbatim]. `host_setup_handoff` (`installer/executors.py:501-507`) returns `setup.handoff` — a tuple of strings shown to the user, never executed — and `install_tool`'s own `_perform` routes `kind == "host_setup"` to exactly this (`engine.py:83-84`), producing `InstallStatus.MANUAL_REQUIRED` (`engine.py:139-145`).
- Separately and worth surfacing even though it is **not** the existing-precedent recommendation: Textual (the actual installed version, `8.2.7`) does ship `App.suspend()`, verified this session by reading its live source:
  ```python
  # Source: textual/app.py (installed textual==8.2.7), read via
  # `uv run python3 -c "import inspect; from textual.app import App; print(inspect.getsource(App.suspend))"`
  @contextmanager
  def suspend(self) -> Iterator[None]:
      """... the app will stop reading input and emitting output. Other
      applications will have full control of the terminal ... When the
      `with` block ends, the application will start reading input and
      emitting output again."""
  ```
  [VERIFIED: live `textual==8.2.7` source, read this session via `uv run`]. This is a real, textual-safe way to hand the terminal to a child `chsh` process and get it back — but it is a *sync* context manager that must be entered from the app/main thread (not from `ExecuteScreen`'s `@work(thread=True)` worker directly; it would need the same `call_from_thread` hand-off `ask_from_worker` already uses, `execute_screen.py:124-137`), and nothing else in this codebase uses it today.

**Recommendation:** Follow the existing `host_setup.py` precedent — never invoke `chsh` from inside the running Textual process at all. On confirm-accept (D-05), produce reviewed handoff text ("run `chsh -s $(which zsh)` in a terminal after this session ends") shaped like `InstallOutcome.handoff`/`InstallStatus.MANUAL_REQUIRED` rather than attempting execution. This is lower-risk, matches an established and tested pattern, and sidesteps the PAM-password-prompt-inside-raw-terminal problem entirely. `App.suspend()` is documented here as a real, viable alternative for the planner to weigh, not a recommendation to build a new interaction pattern for one action — see Open Questions.

### Anti-Patterns to Avoid
- **Re-implementing the `MUTATION_GRADE`/ownership gate inline in `catalog_tui.py` or `execute_screen.py`:** `UpdateService.run` already does this correctly with a **fresh** re-resolution (`update.py:368-369`); a second, inline gate check risks drifting from it and violates D-01's "no new update-execution code."
- **Calling `chsh` through `StreamingRunner` or `run_captured`:** both discard or fail to properly hand over stdin for a PAM password prompt (see above) — this would produce a hang or a cryptic, unrecoverable failure with the TUI's raw-mode terminal still held.
- **Making `resolve_dependencies` version-aware:** it is a pure, terminal-free, platform/is_installed-only function by design (module docstring, `deps.py:1-9`); teaching it about `VersionStatus`/ownership would couple a core resolver to TUI-only state and contradicts `.claude/architecture.md`'s "one apply workflow" / thin-adapter framing for `ExecuteScreen`.
- **Silently defaulting `set_login_shell` to "run without asking" when `default_enabled_sensitive_actions` lists it:** `SENSITIVE_POST_INSTALL_ACTIONS`/`default_enabled_sensitive_actions` (`model.py:54,269`) is validated schema, but D-05 is explicit that a confirmation is required "even off atomic distros" regardless of any default-enabled flag — the confirm gate must not be bypassable by a registry declaration.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Ownership/mutation-grade gate for an update | A new `owner in MUTATION_GRADE` check | `UpdateService.run` (`update.py:366-422`) — re-resolves ownership fresh and gates internally | Already tested (`tests/test_update.py`, `tests/test_catalog_tui.py:1379-1488`); D-01 explicitly forbids new update-execution code. |
| A second "please confirm this batch" prompt for auto-updates | A new modal/prompt | `ExecuteScreen`'s existing `enter start` gate (`execute_screen.py:342,348-356`) | D-02: the existing pre-run confirm already IS the consent; a second prompt would contradict the decision. |
| TTY/terminal-ownership detection for a system-prompting command | A bespoke `sys.stdin.fileno()`/`os.isatty` check | Either the existing (unused) `run_interactive_command`/`InteractiveTerminalUnavailable` seam (`run.py:41-59`) or, if execution-in-process is chosen, Textual's own `App.suspend()` | Both already exist; a hand-rolled check would not know about Textual's raw/alt-screen terminal ownership the way `App.suspend()` does. |
| A new "reviewed console instructions" screen for a sensitive action | A bespoke instructions renderer | The existing `MANUAL_REQUIRED`/`handoff` shape (`engine.py:139-145`, `render_handoff` already called in `ExecuteScreen.on_install_run_finished`, `execute_screen.py:504`) | The rendering pipeline for "here are commands to run yourself" already exists end-to-end and is already streamed into `ExecuteScreen`'s log. |
| A new confirm-modal widget for D-05 | A bespoke `ModalScreen` | `ChecksumMismatchScreen` (`execute_screen.py:79-121`) as the direct template — same `ask_from_worker`/`push_screen_wait` mechanism (`execute_screen.py:124-137`) | This codebase already has exactly one documented, spike-validated worker-to-modal mechanism (MECHANISM=A, `.planning/phases/13-.../13-VALIDATION.md`); a second ad hoc mechanism would violate the "one navigation path" architecture rule's documented exception scope. |

**Key insight:** every primitive this phase needs — the update mechanism, the mutation-gate, the worker-to-modal confirm pattern, and the "reviewed handoff, never auto-executed" pattern for terminal-owning commands — already exists in this codebase, built and tested in Phases 9, 12, and 13. The work is wiring a second call site for each, not inventing new mechanisms. The one genuinely new production code surface is the `post_install`/`set_login_shell` dispatch table itself (currently zero callers) and the `chsh` handoff text.

## Common Pitfalls

### Pitfall 1: Treating `run_wizard`'s `prompter.confirm` as the integration point
**What goes wrong:** Implementing D-01/D-02/D-03 inside `installer/app.py::run_wizard` (following CONTEXT.md's literal canonical refs) fixes a code path the real `make setup` interactive flow never executes.
**Why it happens:** CONTEXT.md predates Phase 13's `ExecuteScreen` rewiring; its refs were accurate when written.
**How to avoid:** Implement against `ExecuteScreen`/`ExecuteInputs` (see Pattern 1). If `run_wizard`'s own `--all`/`--categories` path should also get the fix for consistency, that is an *additional*, separately-scoped change — `run_wizard` currently calls `resolve_dependencies` directly too (`app.py:138-143`) and has the identical bug, just reachable only via CLI flags, not via `on_tool_browser_accepted`.
**Warning signs:** A plan or PLAN.md task that references `run_wizard`, `prompter.confirm`, or `render_summary`/`render_failure_details` in `app.py` as the place to add the update split, without also touching `execute_screen.py`.

### Pitfall 2: Assuming `VersionStatus` is always populated at accept-time
**What goes wrong:** `CatalogScreen._version_statuses` is filled asynchronously by a `@work(thread=True)` version-refresh worker (`catalog_tui.py:275-287`) that may not have completed by the time the user presses enter. A naive `if status.outdated: update` check that requires `status is not None` would silently skip genuinely-outdated tools whose probe simply hadn't finished.
**Why it happens:** Version refresh and user interaction are decoupled by design (so the UI never blocks on a slow network probe).
**How to avoid:** Reuse the exact `action_update_tool` gate predicate: skip **only** when `status is not None and status.outdated is False` (a confirmed-current tool); attempt the update for both `status is None` (unknown) and `status.outdated is True`.
**Warning signs:** A test that asserts "unknown version status → no update attempted" — that is the *opposite* of the behavior `test_action_update_tool_starts_worker_when_outdated_is_none` (`tests/test_catalog_tui.py:1440-1488`) already establishes and locks in.

### Pitfall 3: Running `chsh` (or any password-prompting command) through `StreamingRunner`/`run_captured` from a Textual worker thread
**What goes wrong:** `StreamingRunner` sets `stdin=subprocess.DEVNULL` (`run.py:146`); a `chsh` invocation expecting to read a password from stdin gets an immediate EOF or hang, depending on the local PAM stack, with no way for the user to respond because Textual's worker thread cannot forward keystrokes to the child.
**Why it happens:** Every existing runner in this codebase was built for non-interactive package-manager/downloader children, never for a command that itself needs to prompt the human.
**How to avoid:** Do not execute `chsh` in-process at all (see Pattern 2's recommendation) — produce reviewed handoff instructions instead. If the planner chooses the `App.suspend()` alternative, `chsh` must run through a bespoke path that hands off via `call_from_thread` to the main thread, never through `StreamingRunner`/`run_captured`/`run_command` as currently constructed.
**Warning signs:** A test that mocks `chsh`'s subprocess call with a `Runner` fake and asserts success without ever addressing stdin — such a test would pass while the real behavior hangs or fails silently on a real machine.

### Pitfall 4: Confusing `Tool.postinstall` (singular) with `Tool.post_install` (plural) during implementation
**What goes wrong:** Wiring `set_login_shell` into `installer/postinstall.py::POSTINSTALL_HOOKS` (the singular mechanism) instead of building the new plural-field dispatcher. `POSTINSTALL_HOOKS`' keys are validated against `POSTINSTALL_HOOK_NAMES` (`model.py:19-21`), a **different, disjoint** closed set from `POST_INSTALL_ACTIONS` (`model.py:46-53`) — `"set_login_shell"` is not and must not become a member of `POSTINSTALL_HOOK_NAMES`.
**Why it happens:** The two names are one character apart and both dispatch "after a successful method" per their respective docstrings.
**How to avoid:** `.claude/architecture.md`'s "Phase 9: postinstall hooks" section already documents this confusion explicitly by name; keep the new dispatcher in a distinctly-named module/table (e.g. mirroring `postinstall.py`'s shape but named for `post_install`/`POST_INSTALL_HOOKS` or similar, clearly distinguished in naming from the existing `postinstall.py`).
**Warning signs:** A single dispatch dict in `installer/postinstall.py` growing a `"set_login_shell"` key, or `model.py::POSTINSTALL_HOOK_NAMES` growing to include it.

## Code Examples

### The exact predicate to reuse for "is this selected tool eligible for auto-update"
```python
# Source: installer/catalog_tui.py:568-570 (existing, live-verified this session)
status = self._version_statuses.get(tool_id)
if status is not None and status.outdated is False:
    return  # confirmed current -- skip
# Both status is None (unknown, probe still in flight) and
# status.outdated is True fall through and are attempted.
```

### The exact ownership-fresh-resolution contract a batch-update loop must not bypass
```python
# Source: installer/update.py:366-376 (existing, live-verified this session)
def run(self, target: UpdateTarget) -> UpdateOutcome:
    """Re-resolve, pre-capture, mutate, replay, invalidate — in that order."""
    fresh = self._reresolve_ownership(target.tool)
    if fresh.owner == "unknown" or fresh.confidence not in ownership_mod.MUTATION_GRADE:
        return UpdateOutcome(
            tool_id=target.tool.id,
            status="unknown-owner",
            owner=fresh.owner,
            detail=fresh.unknown_reason or _FALLBACK_UNKNOWN,
        )
```
A batch-update loop needs no additional gate logic — construct `UpdateTarget` from any ownership snapshot (even a stale one from `VersionRefreshService.ownership_of`) and let `run` re-resolve and refuse on its own.

### The existing, tested "on_mismatch" optional-callback pattern to mirror for a new sensitive-action confirm
```python
# Source: installer/session.py:16-17, 69-79 (existing, live-verified this session)
MismatchChoice = Literal["retry", "skip", "fallback"]
OnMismatch = Callable[[str], MismatchChoice]

def run_installs(
    tools: list[Tool],
    platform: Platform,
    runner: Runner = run_command,
    resolve_tag: TagResolver = resolve_github_tag,
    install: Install = install_tool,
    on_mismatch: OnMismatch | None = None,
    catalog: Mapping[str, Tool] | None = None,
    *,
    should_continue: Callable[[], bool] | None = None,
) -> list[InstallOutcome]:
```
A new `confirm_sensitive_action: Callable[[str], bool] | None = None`-shaped parameter, threaded the same way through `install_tool`/`run_installs`/`ExecuteScreen`'s worker/`run_wizard`, is the established idiom for "an optional, seam-injected human decision mid-install"; "no callback given" should default to the safe choice (skip the sensitive action, never run it silently), mirroring `on_mismatch`'s own "No callback = unattended mode: the hard-fail outcome stands" contract (`session.py:85`).

### The reviewed-handoff shape to reuse for `set_login_shell`'s actual effect
```python
# Source: installer/host_setup.py:27-41 (existing HOST_SETUPS worked example, "pi")
HOST_SETUPS: dict[str, HostSetup] = {
    "pi": HostSetup(
        handoff=(
            "After leaving the installer, run these Pi setup commands in a console:",
            "pnpm add -g --ignore-scripts @earendil-works/pi-coding-agent",
            "pi",
        ),
        probes=(...,),
        owner="pnpm",
    ),
}
```
`set_login_shell`'s dispatcher should produce a comparably-shaped `handoff` tuple (e.g. `("Run this in a terminal to make zsh your login shell:", "chsh -s $(which zsh)")`) rather than executing `chsh` in-process, per Pattern 2's recommendation.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Install execution via console `run_wizard` (`prompter.confirm` → `run_installs`, synchronous, blocking) | Install execution via Textual `ExecuteScreen` (`enter start` → threaded `run_installs` with `StreamingRunner`, live log, per-tool progress) | Phase 13 (this milestone, completed immediately before Phase 14) | `run_wizard` is now reachable only via `--all`/`--categories` CLI flags; any bug-fix or feature aimed at the interactive `make setup` flow must target `ExecuteScreen`, not `app.py`. |
| `oh-my-zsh` registry entry hard-codes `CHSH=no` as its only shell-safety mechanism | This phase replaces the blanket workaround with a guarded, confirmed, real action | This phase | `env = { RUNZSH = "no", CHSH = "no", KEEP_ZSHRC = "yes" }` (`registry.toml:541`) stays unchanged — `CHSH=no` remains the *install-script*-level guard (oh-my-zsh's own installer never silently runs chsh); `set_login_shell` becomes a **separate, explicit, user-opted-in** step layered on top, never a relaxation of the install-script default. |

**Deprecated/outdated:** None — this phase does not remove or replace any shipped mechanism, only adds a second call site for updates and a net-new dispatcher.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `chsh -s <path>` on the target distros (Fedora/Bazzite, Debian, Arch, macOS) generally prompts for the invoking user's own password via PAM when changing their own shell, rather than succeeding silently — based on general PAM/`chsh` documentation (`pam_rootok.so` bypasses only for root), not a live test against a real Bazzite/Fedora/macOS machine in this session. | Architecture Patterns, Pattern 2; Pitfall 3 | If some target distro's PAM config for `chsh` does *not* prompt a normal user for a password when changing their own shell, the "needs a real TTY" risk is smaller than assessed, and an in-process, non-interactive `subprocess.run(["chsh", "-s", path])` might actually work through `run_captured` without any terminal-handoff machinery. The planner should verify this live on Bazzite (and any other target OS) before committing to the reviewed-handoff-only design — a `checkpoint:human-verify` task is warranted here specifically. |
| A2 | The exact root cause behind ublue-os/bazzite#4159 (why `chsh`-to-zsh specifically breaks KDE/SDDM login) was not established — the GitHub issue itself contains no maintainer root-cause analysis or fix (the reporter explicitly declined to share diagnostic logs, and the issue was closed "not planned"). This research treats the *symptom* (login failure after `chsh` to zsh on Bazzite) as established fact per the issue's title/description, but the *mechanism* is unknown. | Summary; D-04's rationale; Security Domain | If the actual mechanism is narrower than "any chsh-to-zsh on any immutable/Bazzite host" (e.g. specific to a particular SDDM/KDE Plasma version combination, or to a particular `.zshrc`/PAM config interaction), `Platform.immutable`'s blanket hard-block (D-04, already user-decided and out of scope to relitigate) may be broader than strictly necessary — but D-04 is a locked decision, not something this research recommends changing. |

## Open Questions

1. **Does the update dispatch belong inside `ExecuteScreen`'s worker, or does `CatalogScreen` intercept before ever posting `Decided`?**
   - What we know: `CatalogScreen` already owns `_updates`/`_version_refresh` and has a proven single-tool update worker (`_update_tool_worker`). `ExecuteScreen` already owns the one confirm gate the real flow uses and already receives the full `Tool` catalog + `Platform`. `setup.py::_build_app` constructs `version_refresh`/`updates` once and could pass them to either (or both) screens.
   - What's unclear: Whether splitting "which ids need install vs. update" should happen in `CatalogScreen.on_tool_browser_accepted` (before `Decided` is posted, keeping `ExecuteScreen` purely install-shaped) or inside `ExecuteScreen.on_mount`/`_execute_worker` (keeping `CatalogScreen` purely a picker, as it is today for every other case).
   - Recommendation: Do the split inside `ExecuteScreen` (Pattern 1 above) — `CatalogScreen.on_tool_browser_accepted` currently does no execution-adjacent work at all (it only filters by availability and posts ids), and giving it update-execution responsibility would blur the "one screen, one job" shape Phase 13 was built to establish (`execute_screen.py`'s own docstring: "Thin IO adapter over unchanged pure core... three modules independently deciding control flow in the abandoned `feat/install-experience` branch [was] a real defect"). Splitting inside `ExecuteScreen` keeps exactly one screen owning "what happens after the user confirms."

2. **Should `set_login_shell` ever actually execute `chsh` in-process (via `App.suspend()`), or should this phase ship handoff-only?**
   - What we know: `App.suspend()` exists and is a real, textual-safe terminal-release mechanism (verified against the installed `textual==8.2.7`). The codebase's only existing precedent for "needs a real terminal" (`host_setup.py`) is handoff-only and explicitly documents "never launches them from its worker thread" as a deliberate choice, not an oversight.
   - What's unclear: Whether a handoff-only `set_login_shell` (the user must manually run `chsh -s $(which zsh)` themselves after the installer exits) satisfies the spirit of "implement it" from ROADMAP.md/STATE.md, or whether an in-process, suspend-based execution is expected. CONTEXT.md's decisions (D-04/D-05/D-06/D-07) are agnostic to this — they constrain *when* it may run (never on immutable, always confirmed) and *where it is dispatched from* (the oh-my-zsh ladder), not *how* the mutation itself is technically carried out.
   - Recommendation: Ship handoff-only for this phase (lower risk, reuses a proven pattern, avoids the A1 assumption above becoming load-bearing for actual execution correctness) and record the `App.suspend()` alternative as a follow-up idea if live testing later shows the PAM password prompt is not actually a blocker on the target distros.

3. **Does `run_wizard`'s own `--all`/`--categories` CLI-flags path need the same D-01 fix?**
   - What we know: `run_wizard` (`app.py:111-170`) calls `resolve_dependencies` directly (`app.py:138-143`) and has the identical "outdated tool silently excluded" bug, but it is reached only via `--all`/`--categories`, not via the interactive TUI catalog this phase's bug report describes.
   - What's unclear: Whether fixing only the TUI path (per D-01's literal text, which names `on_tool_browser_accepted`) leaves an inconsistency between `--all`/`--categories` and interactive `make setup` that a future bug report would surface.
   - Recommendation: Out of this phase's stated scope (CONTEXT.md names `on_tool_browser_accepted` specifically); flag as a fast-follow candidate for STATE.md's pending-todos, not a blocker for Phase 14.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `chsh` (util-linux on Linux / `dscl`-backed on macOS) | `set_login_shell`'s eventual real effect | Not verified live in this research session (no target-OS shell-change test run) | — | See Assumption A1 — a `checkpoint:human-verify` task on a real Bazzite (or other target) machine is recommended before shipping any in-process `chsh` invocation. |
| `textual` | Both bugs' UI surfaces | ✓ | 8.2.7 (verified via `uv run python3 -c "import textual; print(textual.__version__)"` this session) | — |
| `pytest`/coverage tooling | Wave 0 tests | ✓ (existing project tooling, `pyproject.toml:46-57`) | — | — |

**Missing dependencies with no fallback:** None — everything needed is stdlib or already-installed.

**Missing dependencies with fallback:** `chsh`'s live behavior on Bazzite specifically was not verified this session; recommend the planner insert a `checkpoint:human-verify` task rather than blocking on it.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (`pyproject.toml:46-49`), `asyncio_mode = "auto"` |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.run]`/`[tool.coverage.report]`) |
| Quick run command | `uv run pytest tests/test_deps.py tests/test_engine.py tests/test_execute_screen.py tests/test_catalog_tui.py -x -q` |
| Full suite command | `make test` (pytest + coverage, `fail_under = 90`, `pyproject.toml:57`) |

### Phase Requirements → Test Map
No REQ-IDs were supplied for this phase invocation (CONTEXT.md/ROADMAP.md describe it narratively rather than with a REQUIREMENTS.md id list); the map below is keyed to CONTEXT.md's D-01 through D-07 instead.

| Decision | Behavior | Test Type | Automated Command | File Exists? |
|----------|----------|-----------|-------------------|-------------|
| D-01 | Selecting an outdated, installed, selected tool via the main flow triggers `UpdateService.run` | unit (Textual pilot) | `uv run pytest tests/test_execute_screen.py -k outdated -x` | ❌ Wave 0 — no such test/fixture exists yet; model on `tests/test_wizard_app.py:4112-4128`'s existing `execute=` pilot pattern and `tests/test_catalog_tui.py:1440-1488`'s `outdated=None` fixture shape. |
| D-01 (resolver layer) | `resolve_dependencies` alone does not need to change (it is correctly "installed = satisfied"); the new split logic lives one layer up | unit | `uv run pytest tests/test_deps.py -x` | ✅ existing suite, must stay green — confirms this phase should NOT touch `deps.py`'s own contract. |
| D-02 | No second confirm prompt is added; `enter start` remains the only gate | unit (Textual pilot) | `uv run pytest tests/test_execute_screen.py -k confirm -x` | ❌ Wave 0 — assert the update dispatch does not fire before `action_start`/`enter`. |
| D-03 | A blocked update (unknown owner / non-`MUTATION_GRADE`) surfaces in the post-run summary log with the reused `"cannot update {tool_id}: {reason}"` text, not inline mid-run | unit (Textual pilot) | `uv run pytest tests/test_execute_screen.py -k blocked_update -x` | ❌ Wave 0 — model on `tests/test_catalog_tui.py:1407-1437`'s `test_action_update_tool_refuses_non_mutation_grade` reason-text assertion. |
| D-04 | `set_login_shell` is never offered/executed when `Platform.immutable` is `True` | unit | `uv run pytest tests/test_engine.py -k login_shell -x` or a new `tests/test_post_install.py` | ❌ Wave 0 — new dispatcher, new test file needed (mirror `tests/test_postinstall.py`'s existing shape for the sibling singular-hook mechanism). |
| D-05 | On a non-immutable host, `set_login_shell` never fires without an explicit confirm returning True | unit | same new test file | ❌ Wave 0. |
| D-06 | `set_login_shell` dispatches only from the `oh-my-zsh` tool's ladder, only after a successful method | unit | same new test file, plus `tests/test_registry.py` assertion that only `oh-my-zsh` declares `post_install = ["set_login_shell"]` | ❌ Wave 0. |
| D-07 | No generalized "future shell" parameter is introduced | code-review / registry-integrity | `uv run pytest tests/test_registry.py -x` (ensure no second `post_install`-declaring tool sneaks in unreviewed) | ✅ existing suite; the *absence* of new generalization is enforced by review, not a new automated test. |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_deps.py tests/test_engine.py tests/test_execute_screen.py tests/test_catalog_tui.py -x -q` (touches every module this phase modifies)
- **Per wave merge:** `make test` (full suite + coverage floor)
- **Phase gate:** Full suite green (`make validate && make test`, per `.claude/testing.md`'s "Definition of done") before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] A test asserting `resolve_dependencies` output for a *selected, installed, outdated* tool (currently no such test exists in `tests/test_deps.py`) — establishes the documented, unchanged baseline before `ExecuteScreen`'s new split logic is layered on top.
- [ ] `tests/test_execute_screen.py` fixtures for an `ExecuteInputs` that also carries `version_refresh`/`updates` (today's `_execute_inputs` helper at `tests/test_wizard_app.py:4070-4100` has no such fields).
- [ ] A new `tests/test_post_install.py` (or equivalent) mirroring `tests/test_postinstall.py`'s structure, for the new `post_install`/`set_login_shell` dispatch table.
- [ ] A `Platform.immutable=True` fixture case proving `set_login_shell` is never offered (D-04) — reuse the existing `Platform(os=..., arch=..., immutable=True, has_brew=...)` construction pattern already used throughout `tests/test_resolve.py`/`tests/test_engine.py`.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Indirectly | `set_login_shell`'s underlying `chsh` mutation is itself gated by the OS's own PAM authentication (the user's own password) — this project must never attempt to bypass, cache, or forward that credential; it only ever invokes the OS binary and lets PAM handle authentication itself (see Assumption A1). |
| V4 Access Control | Yes | D-04's `Platform.immutable` hard block and D-05's mandatory confirm are both access-control gates on a sensitive local mutation; `SENSITIVE_POST_INSTALL_ACTIONS` (`model.py:54`) is the existing closed-set mechanism this project already uses to mark an action as requiring elevated consent. |
| V5 Input Validation | Yes | The dispatch table for `post_install` (mirroring `POSTINSTALL_HOOKS`) selects a NAME from a closed, code-owned set — never a literal registry-supplied command string — the same invariant `.claude/architecture.md`'s "Phase 9: postinstall hooks" section documents for the sibling singular mechanism: *"a registry edit alone can never introduce arbitrary post-install execution."* [VERIFIED: .claude/architecture.md, quoted]. This must hold identically for the new plural-field dispatcher. |
| V6 Cryptography | No | Not applicable — no cryptographic material is involved in either bug fix. |
| V12 File and Resources | N/A | No file-upload or resource-handling surface is touched. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Command injection via an untrusted shell path passed to `chsh -s <path>` | Tampering | The shell path must come from this project's own trusted resolution (e.g. `shutil.which("zsh")` or the tool's own known install location), never from unsanitized user input or registry-declared free text; pass as a `list[str]` argv element, never through `shell=True` string interpolation (matches `.claude/python-tooling.md`'s existing bandit-enforced convention: *"bandit findings are real until proven otherwise (e.g. subprocess calls — validate inputs, avoid shell=True with interpolated user data)"*). |
| Elevation of privilege / unintended system-wide effect from a sensitive action silently firing during an unattended (`--yes`/`--all`) run | Elevation of Privilege | D-05's confirm requirement must have a safe "no callback given" default (skip, never auto-run) mirroring `on_mismatch`'s existing "No callback = unattended mode: the hard-fail outcome stands" contract (`session.py:85`) — an unattended CI/scripted run must never silently change the invoking user's login shell. |
| Denial of service / account lockout from a shell change that breaks login (the exact bazzite#4159 failure mode) | Denial of Service | D-04's hard `Platform.immutable` block is the primary mitigation, already user-decided and locked; this research found no evidence (Assumption A2) that the mechanism is narrower than "any chsh-to-zsh on Bazzite," so the blanket block is the conservative, correct-by-construction choice given the available (silent, root-cause-free) evidence. |
| Terminal/PTY hijacking or corrupted rendering from mixing a raw-mode Textual session with a child process expecting a cooked-mode TTY | Tampering (of the user's own session display) | Either avoid in-process execution entirely (Pattern 2's recommendation) or use `App.suspend()`'s documented terminal-release/restore contract rather than any ad hoc stdin/stdout manipulation. |

## Sources

### Primary (HIGH confidence — read directly this session)
- `installer/deps.py`, `installer/engine.py`, `installer/catalog_tui.py`, `installer/wizard_app.py` (lines 1700-1850), `installer/execute_screen.py`, `installer/app.py`, `installer/session.py`, `installer/update.py`, `installer/model.py`, `installer/resolve.py`, `installer/platform.py`, `installer/status.py`, `installer/postinstall.py`, `installer/host_setup.py`, `installer/run.py`, `installer/ownership.py` (lines 85-135), `installer/version_status.py` (lines 115-160), `installer/enums.py`, `installer/registry.toml` (lines 480-550), `setup.py` (lines 375-920) — all read via the `Read` tool this session.
- `tests/test_deps.py`, `tests/test_engine.py`, `tests/test_catalog_tui.py` (lines 1379-1520), `tests/test_wizard_app.py` (lines 4070-4140) — read this session.
- `.claude/architecture.md`, `.claude/testing.md`, `.claude/python-tooling.md`, `.planning/STATE.md`, `.planning/phases/14-.../14-CONTEXT.md`, `.planning/phases/14-.../14-DISCUSSION-LOG.md` — read this session.
- `textual==8.2.7`'s installed `App.suspend` source — read live via `uv run python3 -c "import inspect; ..."` this session.
- `pyproject.toml` — read this session (pytest/coverage config).

### Secondary (MEDIUM confidence)
- [Using ZSH causes major issues · Issue #4159 · ublue-os/bazzite](https://github.com/ublue-os/bazzite/issues/4159) — fetched this session; confirms the symptom (chsh-to-zsh breaks KDE/SDDM login on Bazzite, closed "not planned") but contains no maintainer root-cause analysis (see Assumption A2).
- General `chsh`/PAM non-interactive-password-prompt behavior — WebSearch this session, cross-referencing [Wikipedia: Chsh](https://en.wikipedia.org/wiki/Chsh) and general PAM documentation; not verified against a live Bazzite/Fedora/macOS machine (Assumption A1).

### Tertiary (LOW confidence)
None used as load-bearing for any recommendation above LOW-confidence assumptions A1/A2 (both explicitly logged).

## Metadata

**Confidence breakdown:**
- Current-implementation analysis (Bug 1 root cause, the `run_wizard`-vs-`ExecuteScreen` correction, the existing `UpdateService`/`action_update_tool` mechanism): HIGH — every claim is a direct `Read` of the live tree this session, with line numbers and verbatim quotes.
- `set_login_shell` dispatch mechanism recommendation (Pattern 2): MEDIUM — the *primitives* (`host_setup.py`'s doctrine, `run.py`'s runner shapes, `App.suspend()`'s existence) are HIGH-confidence verified facts; the *recommendation* to use reviewed-handoff-only rather than in-process execution is a judgment call the planner/user should confirm, flagged explicitly in Open Question 2.
- `chsh`/PAM interactive-password-prompt behavior on the actual target distros (Assumption A1): LOW — WebSearch-sourced general knowledge, not live-verified on Bazzite; recommend a `checkpoint:human-verify` task.
- Security Domain / ASVS mapping: MEDIUM — derived from direct reads of this project's own existing conventions (bandit rules, `SENSITIVE_POST_INSTALL_ACTIONS`) plus standard ASVS category definitions from training knowledge.

**Research date:** 2026-09-14
**Valid until:** 2026-10-14 (30 days — this is fast-moving, actively-developed in-repo code, not a third-party API; re-verify against the live tree if Phase 14 planning is delayed past that window, especially the exact line numbers cited throughout).
