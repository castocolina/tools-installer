# Phase 13: Live in-TUI Install Execution & Persistent Wizard Settings - Research

**Researched:** 2026-09-13
**Domain:** Textual TUI worker-thread execution, streaming subprocess output, persisted local JSON state
**Confidence:** MEDIUM-HIGH (the codebase's own established patterns cover ~80% of this phase; the remaining risk is a specific Textual thread/modal interaction that has not been exercised anywhere in this repo yet)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Confirming install PUSHES a new Textual screen (same
  `push_screen`/`pop_screen` pattern `DoctorScreen` already uses,
  `installer/wizard_app.py:154`) rather than an overlay/modal over the
  catalog — no overlay pattern exists in the codebase today; reusing the
  existing push/pop convention is zero new mechanism. — **Reversibility:**
  reversible.
- **D-02:** On completion (success, failure, or partial), the screen STAYS
  showing the full log until the user presses a key — it does not
  auto-return to the catalog after a timer. `render_failure_details`/
  `render_handoff`/`render_postinstall_warnings` (`installer/app.py:163-168`)
  already assume the user reads this output attentively; auto-closing
  risks losing exactly that information. — **Reversibility:** reversible.
- **D-03 (locked earlier in this conversation, restated for downstream
  agents):** Execution runs live inside a log/text-area widget in the TUI
  (not summarized after the fact) — this was the user's original,
  standing request from a prior session, restated when this phase was
  scoped. — **Reversibility:** reversible.
- **D-04:** A prior, never-merged branch (`feat/install-experience`,
  diverged from `main` July 2026, still present as a worktree at
  `.worktrees/install-experience`) already implements almost this exact
  feature. A read-only audit (`13-AUDIT-install-experience.md`) found real
  UX/architecture problems in it AND a high (15-23h) cost to reconcile 10
  concrete type/signature collisions with how far `main` has since evolved.
  **Decision: research and planning must treat this branch as a design
  reference and a named anti-pattern list — never cherry-pick or port its
  code directly.** — **Reversibility:** one-way.
- **D-05:** The new implementation MUST avoid three confirmed defects from
  the old branch, as hard constraints on the design (not suggestions):
  1. **No blocking modal loop before execution visibly starts.**
  2. **Output must be attributed per tool, unconditionally** — never
     dependent on an optional injected parameter.
  3. **No silently-swallowed prompt cancellation.**
  — **Reversibility:** reversible — these are design constraints on new
  code, not a claim about legacy code being kept.

### Claude's Discretion

- Exact Textual widget choice for the streaming log (`RichLog` vs a plain
  `TextArea` writable buffer) — implementation detail, as long as D-01/D-02/
  D-05.2 hold.
- Whether the worker-thread execution model is built from scratch or
  informed by (never copy-pasted from) `installer/install_plan.py`'s
  `ExecutionEvent`/`ExecutionState` shape as naming/structure inspiration
  only — the audit's collision list applies to REUSING the code, not to
  learning from its shape.

### Open Design Questions (from CONTEXT.md, NOT YET DECIDED — carried into this research's Open Questions section)

- Failure handling mid-run: fail-fast vs continue-with-running-status-list,
  and whether the user can cancel mid-run.
- Settings wizard scope and location: `link_mode` only, or folded with other
  one-time preferences (default-shell, headless-flag defaults)? Where does
  the user adjust it afterward — a new Settings view, or folded into
  `PoliciesScreen`?
- CLI flag vs. persisted setting precedence: does `--link-mode` on a later
  run override the persisted value for that run only, or also update the
  persisted value going forward?

### Deferred Ideas (OUT OF SCOPE)

None — the discussion stayed within this phase's scope; the "Open Design
Questions" above are unresolved parts of THIS phase's domain, not deferred
to another phase.
</user_constraints>

<phase_requirements>
## Phase Requirements

No requirement IDs are registered in `.planning/REQUIREMENTS.md` for this
inserted phase (confirmed during discuss-phase — this is a v0.49.0
real-machine-audit-driven phase, not part of the original v1 requirements
batch). `13-CONTEXT.md`'s D-01 through D-05 decisions, plus its three "Open
Design Questions," are the authoritative scope instead. This research maps
each decision to the concrete mechanism that satisfies it (see
`## Architecture Patterns` and `## Code Examples`).
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **uv owns the environment.** Never `pip`/`poetry`/`conda`/hand-rolled venv;
  `make install`/`make setup`/`make test`/`make validate` are the only entry
  points a plan should reference.
- **English only** in all code, comments, commits.
- **Never bypass a quality gate** — fix root causes, never silence lint/type
  errors to make CI green.
- **Coherent commits** — no "fix review comment" pile-ups.
- **`make validate && make test` must pass** before any commit.
- From `.claude/architecture.md` (checked into the repo, same authority as a
  locked CONTEXT.md decision):
  1. **One view registry** (`installer/ui_common.py::VIEWS`) — a new screen
     is a one-row addition there; nothing else may enumerate views.
  2. **One navigation path** (`UnifiedApp.show_view`) — every screen
     transition goes through it; installed screens are suspended, not
     destroyed, on pop.
  3. **One apply workflow** (`ui_common.run_live`) — any live core mutation
     triggered from a screen goes through this closure-based wrapper, never
     a screen's own `try/except OSError`.
  4. **`setup.py` is wiring only** — no decision logic; every pure function
     lives in `installer/` where pyright/coverage/tests apply.
  5. **No orphan helpers** — a shared helper with zero production callers is
     deleted or adopted, never kept "for later."

## Summary

This phase closes a gap the project's own PRD explicitly parked
(`docs/prds/unified-ui-redesign-v1.0-prd.md:134-138`, "Deferred fork —
operador en vivo"): today, `setup.py::_select_catalog` runs a Textual app
whose *only* job is picking tool ids; the moment `UnifiedApp.exit(ids)`
returns control to `setup.py`, everything else — `installer/app.py::run_wizard`'s
dependency resolution, pre-flight audit, confirm, `run_installs`, summary
rendering, `configure_path` (PATH wiring), and the post-run doctor/dedup
verification — happens on a plain `rich.Console`, completely outside Textual.
The codebase already has every primitive this phase needs, just never
wired end-to-end for this flow: a `push_screen`/`pop_screen` convention
(`DoctorScreen`), a proven `@work(thread=True, exclusive=True, group=...)`
+ `post_message` pattern for off-loop work (four independent workers already
do this — globals audit/reinstall, version refresh, tool update, daemon
default-apply), a single `Runner` seam every install side effect funnels
through (`installer/run.py::Runner`, `installer/engine.py`'s
`MethodAwareRunner` protocol), a "redirect console output into a StringIO so
the TUI renders its own success text" precedent (`setup.py::_apply_fix`),
and an atomic-JSON-state-file precedent for anything this project needs to
remember between runs (`installer/version_cache.py` +
`installer/atomic.py::atomic_write_text`).

The one genuinely new mechanism is a **line-streaming Runner** — every
existing `Runner` implementation (`run_command`, `run_captured`, `run_output`)
blocks on `subprocess.run(...)` and returns only after the child exits, so
none of them can feed a live log widget while the child is still running.
This phase needs a `subprocess.Popen`-based runner that reads stdout
line-by-line as it arrives and hands each line to a callback — implemented
once, and used unconditionally (never behind an optional injected
parameter) to satisfy D-05.2's per-tool attribution requirement. The
second genuinely new interaction is confirmed technically viable by reading
the installed Textual 8.2.7 source directly (not assumed): a thread worker
that hits a checksum-mismatch mid-run can synchronously block itself (not
the event loop) by calling `self.app.call_from_thread(async_modal_fn)`,
where `async_modal_fn` does `await self.push_screen_wait(modal)` — this
exact combination is not documented together anywhere in this codebase or
its dependency's docs, so it needs a small throwaway spike before the real
plan commits to it (see Common Pitfalls).

Persisting `link_mode` follows the version-cache precedent exactly: a new
small JSON file under `~/.local/state/tools-installer/`, written through
the same `atomic_write_text` this project already uses for `versions.json`,
never a new hand-rolled write mechanism.

**Primary recommendation:** Build one new screen (a fresh module, not named
`install_screen.py` to avoid any resemblance to the abandoned branch — e.g.
`installer/execute_screen.py`) that `CatalogScreen.Decided` pushes onto the
stack (via a new `UnifiedApp` handler, replacing today's `self.exit(...)`
for the *interactive* path only); that screen renders the dependency
notice + pre-flight audit immediately and visibly (D-05.1), then on an
explicit keypress starts a single `@work(thread=True, exclusive=True)`
worker that calls the *existing* `run_installs` with a new streaming
`Runner`, posts one `Message` per output line (or small batch) back to the
main thread for the log widget to render, and finally — inside the same
worker, no state left inconsistent — calls the existing `configure_path`
(console redirected to `io.StringIO()`, exactly like `_apply_fix` already
does) and a read-only doctor audit, before posting a terminal "done"
message the screen renders and then waits on any key (D-02) before popping
back to the catalog.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Catalog selection (existing) | TUI screen (`CatalogScreen`) | — | Unchanged this phase |
| Dependency resolution + pre-flight audit | Pure core (`installer/deps.py`, `installer/audit.py`) | TUI screen renders it | Already pure/tested; screen only formats, never re-derives |
| Install confirm | TUI screen (new execute screen) | — | Replaces `questionary.confirm`; must render visibly before any subprocess starts (D-05.1) |
| Command execution (subprocess) | Worker thread (new streaming `Runner`) | Pure core (`installer/engine.py::install_tool`, unchanged) | Blocking I/O must never touch the event loop; the install engine itself needs zero changes — only the `Runner` implementation passed into it changes |
| Live output rendering | TUI screen (main thread, via `post_message`) | — | Widgets are only touched from the app's own thread — established convention (`GlobalsAudited`, `ToolUpdated`, etc.) |
| Checksum-mismatch decision | TUI modal, invoked synchronously from the worker thread | — | New: `call_from_thread` + `push_screen_wait` (verified against installed Textual source, not yet used anywhere in this codebase) |
| PATH wiring (`configure_path`) | Pure core (`installer/app.py::configure_path`), called from the same worker | TUI screen renders the captured console text | Reuses the exact `Console(file=io.StringIO())` redirect `DoctorScreen._apply_fix` already does |
| Post-install verification (doctor audit) | Pure core (`installer/app.py::doctor_data`/`run_doctor` machinery, or the existing `DoctorScreen`) | TUI screen | See Open Questions — recommend calling the read-only audit inline, but routing the destructive rc-dedup confirm to the existing Doctor/Policies screens rather than duplicating a confirm UI |
| `link_mode` persistence | Pure core (new `installer/settings.py`, following `version_cache.py`'s pattern) | `setup.py` composition root reads it once at startup | New JSON state file, atomic write, mirrors existing precedent exactly |
| `link_mode` adjustment UI | TUI screen (see Open Questions: new Settings view vs. folded into `PoliciesScreen`) | — | Must fit the "one view registry" constraint — a new view is a one-row `VIEWS` addition, not a parallel mechanism |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `textual` | 8.2.7 (installed; `pyproject.toml` pins `>=8`) [VERIFIED: .venv/lib/python3.12/site-packages/textual/__init__.py] | TUI framework already used for the entire wizard | Already the project's sole TUI dependency; no new dependency for this phase |
| Python stdlib `subprocess.Popen` | stdlib | Line-streaming child process execution | The only way to read a child's stdout incrementally in Python without a third-party dependency; every other `Runner` in this codebase already uses stdlib `subprocess` exclusively (`installer/run.py`) |
| Python stdlib `json` | stdlib | `link_mode` settings persistence | Matches `installer/version_cache.py`'s exact approach — no new serialization library |

No new third-party package is introduced by this phase. **Package Legitimacy
Audit is not applicable** — see that section below for the explicit
disposition.

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `rich.text.Text` | already a transitive dep via `textual`/`rich` | Styled log lines (color per outcome: installed/failed/skipped) | Already used everywhere else in this codebase's rendering (`installer/render.py`, `installer/ui_common.py`) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `subprocess.Popen` line-streaming | `asyncio.create_subprocess_exec` + `async for line in proc.stdout` | Would require the execution worker to be an **async** Textual worker (`@work` without `thread=True`) rather than a thread worker. Rejected: `run_installs`/`install_tool`/every executor in `installer/executors.py`, `installer/download.py`, `installer/apps.py` are synchronous functions built around a synchronous `Runner: Callable[[list[str]], None]`. Converting that whole call chain to async to gain streaming would touch every executor module (`installer/executors.py`, `installer/apps.py`, `installer/download.py`, `installer/postinstall.py`) for a phase whose CONTEXT.md scope is the TUI wiring, not an async rewrite of the install engine. `subprocess.Popen` inside a `thread=True` worker keeps every existing pure-core function's signature unchanged. |
| A single JSON `settings.json` | A comment-marker block in `~/.myshellrc` (the pattern `installer/daemon.py`/`installer/omz.py` use for boolean "decided" flags) | Rejected: `link_mode` is a **string enum value**, not a boolean flag; encoding it as a marker comment would need a bespoke mini-parser this project does not otherwise need. `installer/version_cache.py` already establishes the JSON-envelope-under-`~/.local/state/tools-installer/`-via-`atomic_write_text` pattern for exactly this shape of data (a small typed value keyed by name), so reusing it needs zero new mechanism. |

**Installation:** None — no new packages.

**Version verification:** `textual==8.2.7` confirmed installed in this
project's own `.venv` [VERIFIED: `.venv/lib/python3.12/site-packages/textual/__init__.py`, read this session]. `pyproject.toml:9` pins `textual>=8` [VERIFIED: pyproject.toml:9, read this session] — no version bump needed.

## Package Legitimacy Audit

**Not applicable this phase.** No new external package is introduced;
`textual` is an existing, already-audited dependency and `subprocess`/`json`
are stdlib. Skipping the Package Legitimacy Gate protocol is correct here
per its own trigger condition ("whenever this phase installs external
packages").

## Architecture Patterns

### System Architecture Diagram

```
 CatalogScreen (existing)
   │  user presses enter with a non-empty staged batch
   │  posts CatalogScreen.Decided(ids)
   ▼
 UnifiedApp.on_catalog_screen_decided(message)
   │  INTERACTIVE PATH CHANGE: instead of self.exit(message.result),
   │  build the new execute screen and push it (D-01)
   ▼
 ExecuteScreen (new, pushed via push_screen — same convention as DoctorScreen)
   │
   │  on_mount / enter_view:
   │    - resolve_dependencies(...)              [pure, existing]
   │    - render dependency notice + pre-flight   [screen renders it in the
   │      audit as WIDGET TEXT, visible immediately (D-05.1) --   log/body widget, never a blocking dialog]
   │    - show "press enter to install N tools, esc to cancel"
   │
   │  user presses enter (a visible, non-modal confirm --
   │  satisfies D-05.1: no blocking modal loop before visible start)
   ▼
 @work(thread=True, exclusive=True, group="install-execute") worker starts
   │
   │  for each tool in resolved order:
   │    - StreamingRunner.set_current_tool(tool.id)  (attribution, D-05.2,
   │      UNCONDITIONAL -- never an optional injected parameter)
   │    - install_tool(tool, platform, runner=streaming_runner, ...)
   │        [pure core, UNCHANGED -- only the Runner implementation differs]
   │        → every line the child process writes is captured by
   │          subprocess.Popen and handed to a callback that does
   │          self.post_message(InstallLogLine(tool_id, line))
   │    - on CHECKSUM_MISMATCH: self.app.call_from_thread(async_modal_fn)
   │        blocks THIS THREAD (not the event loop) until the user answers
   │        a real Textual modal (never silently falls back -- D-05.3)
   │  after the loop:
   │    - configure_path(tools, Console(file=io.StringIO()), ...)
   │        [pure core, UNCHANGED -- console redirected exactly like
   │        DoctorScreen._apply_fix already does]
   │    - run a read-only doctor audit (doctor_data/audit_path)
   │    - post_message(InstallRunFinished(summary, captured_text))
   ▼
 ExecuteScreen.on_install_run_finished(message)
   │  renders the full log + summary; STAYS ON SCREEN (D-02) until
   │  the user presses any key
   ▼
 user presses a key → app.pop_screen() → back to CatalogScreen
   (the staged batch is cleared the same way clear_transient() already
   clears other transient per-selection state)
```

### Recommended Project Structure

```
installer/
├── run.py                # ADD: StreamingRunner (Popen-based, line callback)
├── engine.py              # UNCHANGED -- MethodAwareRunner protocol already
│                          #   supports method_started(); StreamingRunner
│                          #   implements it for per-method log headers
├── session.py             # UNCHANGED -- run_installs already takes any Runner
├── app.py                 # UNCHANGED -- configure_path, doctor_data reused as-is
├── settings.py            # NEW: link_mode persistence (mirrors version_cache.py)
├── execute_screen.py      # NEW: the pushed execution screen (D-01)
│                          #   (deliberately NOT named install_screen.py --
│                          #   avoids any filename echo of the abandoned
│                          #   feat/install-experience branch's install_screen.py)
├── wizard_app.py          # MODIFIED: UnifiedApp.on_catalog_screen_decided
│                          #   pushes ExecuteScreen instead of calling exit();
│                          #   VIEWS-style registration if the settings UI
│                          #   becomes its own view (see Open Questions)
├── ui_common.py           # POSSIBLY MODIFIED: VIEWS gains a "settings" row
│                          #   ONLY IF the settings UI becomes a new view
│                          #   (see Open Questions) -- otherwise unchanged
└── catalog_tui.py         # MODIFIED: CatalogScreen.Decided's *meaning*
                           #   changes for the interactive path (still posts
                           #   the same message shape; the app-level handler
                           #   changes what it does with it)
```

### Pattern 1: Worker-thread execution with `post_message` hand-off (established in this codebase)

**What:** A `@work(thread=True, exclusive=True, group="...")` method runs
blocking I/O off the event loop; it never touches a widget directly; it
posts a `Message` subclass back to the screen, which handles it on the main
thread.
**When to use:** Any subprocess/blocking call started from a screen — this
project already does this four times.
**Example (existing, verbatim read from the repo this session):**
```python
# Source: installer/wizard_app.py:434-443 (DoctorScreen._reinstall_globals_worker)
@work(thread=True, exclusive=True, group="globals-reinstall")
def _reinstall_globals_worker(self, packages: tuple[str, ...]) -> None:
    """Run the reinstall off the event loop, then hand the outcome back to it.

    A synchronous subprocess here would freeze every frame for the length of
    a `pnpm add -g`. Widgets may only be touched from the app's own thread,
    hence a posted message rather than a direct refresh.
    """
    _, error = run_live(lambda: self._reinstall_globals(packages))
    self.post_message(GlobalsReinstalled(error))
```
The new install-execution worker follows this exact shape: `thread=True`,
its own `group=` (so it cannot be cancelled by, or cancel, an unrelated
worker like the version-refresh one), and a dedicated `Message` subclass
per event it needs to report (at minimum: one for each streamed output
line/batch, one for the terminal summary).

### Pattern 2: Redirecting a pure-core `Console` into a widget (established in this codebase)

**What:** Every pure-core function that renders to a `rich.console.Console`
(e.g. `configure_path`) can be called unmodified from a TUI screen by
passing `Console(file=io.StringIO())` and reading `.getvalue()` after.
**When to use:** Reusing `configure_path`/`run_doctor` inside the new
execute screen, exactly as `DoctorScreen` already does for its own "apply
fix" action.
**Example (existing, verbatim read from the repo this session):**
```python
# Source: setup.py:473-486 (_build_app's _apply_fix closure)
def _apply_fix() -> None:
    # Runs live inside the DoctorScreen. A quiet console keeps configure_path's
    # own prints from corrupting the running TUI; the screen renders its own
    # result. Link mode is resolved before the app opens (never prompted while
    # the TUI is live).
    configure_path(
        tools,
        Console(file=io.StringIO()),
        platform=platform,
        default_bin_dir=_DEFAULT_BIN_DIR,
        myshellrc_path=_MYSHELLRC,
        rc_paths=rc_paths,
        link_mode=link_mode,
    )
```
The new execute screen's post-install step calls `configure_path` the same
way, inside the SAME worker that just ran `run_installs` (not a second,
separate worker) — this keeps "confirm, run commands, wire PATH, verify" one
continuous, uninterrupted flow, matching the phase description's framing.

### Pattern 3: A thread worker blocking itself (not the event loop) to await a modal answer

**What:** `App.call_from_thread(callback, *args)` runs `callback` — which
may be a coroutine function — on the main event loop and blocks the
*calling thread* until it completes, via
`asyncio.run_coroutine_threadsafe(...).result()`. Combined with
`App.push_screen_wait(screen)` (an `async` method that pushes a screen and
awaits its `dismiss()` result), a worker thread can synchronously ask the
user a question mid-install without freezing the UI: the event loop keeps
rendering and responding to input; only the worker thread (which has
nothing else to do until it gets an answer) blocks.
**When to use:** The checksum-mismatch decision (`OnMismatch` in
`installer/session.py`) when it fires during in-TUI execution — today this
is a `questionary.select` prompt (`setup.py::_ask_mismatch`), which cannot
run while Textual owns the terminal.
**Verification:** Read directly from this project's installed Textual
source this session (not assumed from training data or docs):
```python
# Source: .venv/lib/python3.12/site-packages/textual/app.py
# (App.call_from_thread, read this session)
def call_from_thread(
    self,
    callback: Callable[..., CallThreadReturnType | Awaitable[CallThreadReturnType]],
    *args: Any,
    **kwargs: Any,
) -> CallThreadReturnType:
    ...
    if self._thread_id == threading.get_ident():
        raise RuntimeError(
            "The `call_from_thread` method must run in a different thread from the app"
        )
    callback_with_args = partial(callback, *args, **kwargs)
    async def run_callback() -> CallThreadReturnType:
        with self._context():
            return await invoke(callback_with_args)
    future: Future[CallThreadReturnType] = asyncio.run_coroutine_threadsafe(
        run_callback(), loop=self._loop
    )
    result = future.result()
    return result
```
```python
# Source: .venv/lib/python3.12/site-packages/textual/app.py:2981-2999
# (App.push_screen_wait, read this session)
async def push_screen_wait(
    self, screen: Screen[ScreenResultType] | str, *, mode: str | None = None
) -> ScreenResultType | Any:
    """Push a screen and wait for the result ...
    Note that this method may only be called when running in a worker.
    """
    await self._flush_next_callbacks()
    return await asyncio.shield(
        self.push_screen(screen, wait_for_dismiss=True, mode=mode)
    )
```
`[VERIFIED: .venv/lib/python3.12/site-packages/textual/app.py, read this session — call_from_thread and push_screen_wait definitions quoted verbatim above]`. **This exact combination (a `thread=True` worker calling `call_from_thread` with a callback that itself calls `push_screen_wait`) is not exercised anywhere in this codebase today** — every existing thread worker (`_reinstall_globals_worker`, `_audit_globals_worker`, `_refresh_versions_worker`, `_update_tool_worker`, `_apply_daemon_default_worker`) is fire-and-forget with no mid-run user decision. Treat this as the phase's one real spike risk (see Common Pitfalls) — worth a 30-minute throwaway prototype (a worker that shows a modal and returns its answer) before the real plan is written around it.

### Pattern 4: Atomic small-JSON persisted state (established in this codebase)

**What:** A `~/.local/state/tools-installer/<name>.json` file, written via
`installer/atomic.py::atomic_write_text` (sibling-temp + `os.replace`),
read defensively (malformed/missing degrades to a safe default, never
crashes).
**When to use:** Persisting `link_mode` across runs.
**Example (existing, verbatim read from the repo this session):**
```python
# Source: installer/version_cache.py:154-197 (save_version_cache, default_cache_path)
def save_version_cache(
    path: Path,
    cache: Mapping[str, VersionCacheEntry],
    *,
    managers: Mapping[str, object] | None = None,
) -> None:
    """Write the versioned envelope. managers=None preserves the existing key."""
    managers_out = dict(managers) if managers is not None else _existing_managers(path)
    payload = {
        "version": 1,
        "tools": {...},
        "managers": managers_out,
    }
    ensure_dir(path.parent)
    atomic_write_text(path, json.dumps(payload, indent=2) + "\n")

def default_cache_path() -> Path:
    return Path.home() / ".local" / "state" / "tools-installer" / "versions.json"
```
`[VERIFIED: installer/version_cache.py:154-176, 196-197, read this session — quoted verbatim]`. A new `installer/settings.py` should follow this exact shape: `{"version": 1, "link_mode": "centralized"}`, `default_settings_path() -> Path.home() / ".local" / "state" / "tools-installer" / "settings.json"`, `load_settings(path) -> Settings` degrading to a default `Settings()` on any `OSError`/`json.JSONDecodeError`/malformed-content, `save_settings(path, settings)` via `ensure_dir` + `atomic_write_text`.

### Anti-Patterns to Avoid (drawn directly from the phase's own audit — D-04/D-05)

- **Setting `started = True` before any approval UI, then queuing modal
  after modal with nothing visible in between** —
  `.worktrees/install-experience`'s `install_screen.py:378-397`. The new
  execute screen must render its confirm/audit text the INSTANT it is
  pushed (in `compose_body`/`on_mount`), before any worker starts.
- **Attribution that vanishes when an optional parameter is `None`** —
  the old branch's `session.py:182`, where `captured_runner=None` silently
  dropped all per-tool prefixing. The new `StreamingRunner` must be the ONLY
  runner passed to `install_tool` on the interactive TUI path — there is no
  fallback "plain runner" branch to accidentally take.
- **One shared, unsectioned log for every tool** —
  `install_screen.py:463-478`. Each streamed line must carry (and the
  widget must render) which tool it belongs to, not just concatenate raw
  child output.
- **A cancelled/dismissed prompt that silently does nothing next** —
  `wizard_app.py:946-968` in the old branch (a `None` from
  `PathLinkModePrompt` fell through a guard with no message). Any new modal
  this phase adds (checksum-mismatch, settings-wizard) must render an
  explicit "cancelled — nothing changed" status line, never a silent
  no-op.
- **Three modules sharing execution responsibility with no owning seam**
  (Severity MEDIUM in the audit: `install_screen.py` / `session.py::run_plan`
  / `install_plan.py` each independently decided part of the control flow).
  This phase's design keeps the *existing* `run_installs`/`install_tool`
  pure-core functions as the SOLE owners of install control flow — the new
  screen and worker are a thin IO adapter around them, not a second
  decision-making layer.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic file writes | A custom write-then-rename | `installer/atomic.py::atomic_write_text` | Already handles symlink targets, concurrent-writer temp-name collisions, and cleanup-on-failure — exactly the settings-file use case |
| Dependency resolution / install ordering | Any new pre-check inside the execute screen | `installer/deps.py::resolve_dependencies` (unchanged) | This is the sole ordering mechanism per `.claude/architecture.md`; a second one would drift out of sync |
| Per-tool failure propagation | A new "skip if a dependency failed" check in the screen | `installer/session.py::run_installs` (unchanged) — already tracks `DEPENDENCY_FAILED` across a single forward pass | Re-implementing this in the screen would duplicate `_UNRESOLVED`/blocked_by logic that is already tested |
| Console-output capture for a screen | A bespoke print-interceptor | `rich.console.Console(file=io.StringIO())` | Already the established pattern (`_apply_fix`); zero new mechanism |
| Confirmation UX | A new generic "Are you sure?" modal component | `ConfirmUninstall` (`installer/wizard_app.py:1291`) as the shape to mirror for any NEW destructive confirm this phase needs (if any) | Matches existing visual language and BINDINGS convention (`enter`/`y` confirm, `escape`/`n` cancel) |

**Key insight:** Nothing about install *decision logic* is new in this
phase — every pure function (`resolve_dependencies`, `audit`, `run_installs`,
`install_tool`, `configure_path`, `run_doctor`) is reused unchanged. The
entire phase is an IO-adapter problem: replace a plain-`Console`
presentation layer with a Textual-widget one, and replace a blocking
`Runner` with a streaming one. Treating it as "build a new install engine"
(as the abandoned branch effectively did, per the audit's Severity MEDIUM
finding C) is the anti-pattern to avoid.

## Common Pitfalls

### Pitfall 1: `call_from_thread` + `push_screen_wait` is unverified IN COMBINATION for this codebase

**What goes wrong:** The plan assumes a worker thread can pop a modal and
get an answer back synchronously, based on reading each primitive's source
independently. No test or existing code path in this repo exercises the
combination.
**Why it happens:** Every existing thread worker in this codebase is
fire-and-forget (no worker-initiated user decision mid-run).
**How to avoid:** Before writing the full execute-screen plan around this,
spike a 20-line throwaway: a `@work(thread=True)` method that calls
`self.app.call_from_thread(self._ask)` where `_ask` is `async def
_ask(self) -> bool: return await self.push_screen_wait(ConfirmUninstall("test"))`,
run under `app.run_test()` with a `Pilot` pressing a key, and confirm the
thread actually receives the boolean. If it does not work as expected,
fall back to a simpler design: queue the mismatch as a `post_message` and
have the worker `time.sleep`-poll a `threading.Event` that the main-thread
modal-dismiss callback sets (more code, but only uses primitives already
proven in this codebase — `post_message` + a plain `threading.Event`).
**Warning signs:** `RuntimeError: The 'call_from_thread' method must run
in a different thread from the app` (calling it from the wrong thread) or
the modal never actually appearing (a coroutine scheduled but never
awaited by the outer `invoke()`).

### Pitfall 2: `UnifiedApp.run()`'s return type currently gates on `list[str] | None`

**What goes wrong:** `setup.py::main()` calls
`run_wizard(..., select_catalog=lambda tools: _select_catalog(tools, ...))`,
and `run_wizard` (`installer/app.py:111-170`) itself performs
resolve/confirm/`run_installs`/render AFTER `select_catalog` returns. If the
interactive TUI path now performs ALL of that internally, `run_wizard`'s
console-based sequence must not run a SECOND time for the same tools.
**Why it happens:** `run_wizard` was written when the TUI's only job was
selection; its own body still assumes it owns everything after selection.
**How to avoid:** The plan must explicitly decide (and RESEARCH flags this
as needing a plan-time decision, not a silent default) one of:
(a) `select_catalog`'s contract changes for the TUI path so it returns the
finished `Summary` directly (e.g. via a new return-shape or a sentinel), and
`run_wizard`/`main()` skip their own resolve/confirm/install/render
sequence whenever `select_catalog` was used and already produced a summary; or
(b) keep `run_wizard`'s shape for the headless (`--all`/`--categories`)
path unchanged, and give the interactive TUI its OWN, parallel top-level
function in `setup.py`/`installer/app.py` that never calls `run_wizard` at
all. **Recommendation: (b)** — it keeps the headless path (which this phase
explicitly must not regress, per the "genuinely headless-capable" framing)
byte-for-byte unchanged, and avoids adding a conditional branch inside
`run_wizard` that only the TUI path takes.
**Warning signs:** A tool getting installed twice, or `configure_path`
running twice (once inside the TUI worker, once again from `setup.py::main()`
after the TUI's `.run()` returns).

### Pitfall 3: Streaming a subprocess's stdout can deadlock on a full pipe buffer

**What goes wrong:** `subprocess.Popen(cmd, stdout=PIPE, stderr=STDOUT)`
followed by `for line in proc.stdout: ...` without ALSO managing the write
side correctly is a well-known deadlock source if stdin is also piped and
not closed, or if the reading loop is slower than the child's output rate
against a small OS pipe buffer.
**Why it happens:** None of this project's existing commands are
interactive or write unbounded output today (curl/tar/unzip/pnpm/brew are
all short, bounded), so this failure mode has never been hit, but a
line-by-line streaming reader is new here.
**How to avoid:** Close `stdin=subprocess.DEVNULL` explicitly (no existing
install command reads stdin), merge `stderr=subprocess.STDOUT` (single
stream — this is also what makes single-source line-ordering simple), and
read in the SAME thread that owns the `Popen` object (the worker thread
already does this — never hand the `Popen` object across threads).
**Warning signs:** The worker "hangs" for a specific tool (e.g. one whose
install script produces a very large amount of output, such as a verbose
`sdk install java`).

### Pitfall 4: Doctor/dedup "verify" step has no existing TUI equivalent for the destructive half

**What goes wrong:** `setup.py::_verify_and_clean` (today, console-only)
does two things: a read-only `run_doctor` call, AND a `clean_rc_duplicates`
call that CONFIRMS before deleting duplicate PATH lines from rc files. The
phase description's "verify" step maps to the first half cleanly (reuse
`doctor_data`/the existing read-only audit), but the second half is a
genuinely separate destructive action with no existing screen.
**Why it happens:** `clean_rc_duplicates` was written for the console-only
"just ran the whole wizard" moment and was never wired into any Textual
screen (not even the existing `DoctorScreen`).
**How to avoid:** This research recommends treating `clean_rc_duplicates`
as OUT OF THIS PHASE's execute-screen scope (`[ASSUMED]` — this is an
interpretive scope call, not something CONTEXT.md settled explicitly): the
execute screen calls `configure_path` (PATH wiring) and a read-only doctor
audit inline, but leaves rc-duplicate cleanup as a separate, already-console-only
concern reachable the way it is today (or, if desired, a future addition to
the existing `DoctorScreen`, not a new mechanism invented inside the
execute screen). Flag this explicitly to the user during
`/gsd-discuss-phase` or the plan-review step if not already confirmed.
**Warning signs:** Scope creep — building a THIRD confirm surface (catalog
confirm, install-execute confirm, rc-dedup confirm) inside one phase whose
CONTEXT.md decisions only explicitly cover two.

## Code Examples

### The existing `MethodAwareRunner` protocol already anticipates a smarter runner

```python
# Source: installer/run.py:15-19 (read this session, verbatim)
@runtime_checkable
class MethodAwareRunner(Protocol):
    """Optional runner capability used to attribute method-ladder transitions."""

    def __call__(self, cmd: list[str]) -> None: ...

    def method_started(self, method: str) -> None: ...
```
```python
# Source: installer/engine.py:124-127 (read this session, verbatim)
for method in methods:
    if isinstance(runner, MethodAwareRunner):
        runner.method_started(method.kind)
```
`[VERIFIED: installer/run.py:15-19 and installer/engine.py:124-127, read this session]`. The new `StreamingRunner` should implement `method_started(method: str)` to emit a header line (`"-- trying <method.kind> --"`) into the log stream — this is a zero-change integration point already present in `install_tool`, not something this phase needs to add to the engine.

### Every install side effect funnels through one `Runner` call site

```python
# Source: installer/download.py (grep, read this session) -- every
# side-effecting line in the download executor calls ctx.runner(argv):
ctx.runner(["sh", "-c", f"curl -fsSL -o {quoted_link} -- {quoted_url}"])
ctx.runner(["chmod", "+x", str(link)])
ctx.runner(["curl", "-fsSL", "-o", str(asset_path), "--", target.url])
ctx.runner(["unzip", "-q", "-o", str(asset_path), target.member, "-d", str(dest)])
```
`[VERIFIED: installer/download.py, grepped and confirmed via Read this session — every subprocess-shaped side effect in the download path is a `ctx.runner(...)` call, no direct `subprocess` import in that module]`. This confirms the `Runner` seam is the single, total interception point — a new `StreamingRunner` needs no changes anywhere in `installer/executors.py`, `installer/download.py`, `installer/apps.py`, or `installer/postinstall.py` to get streaming for free across every install method kind.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Catalog TUI exits, everything else drops to console (`questionary`/`rich`) | This phase: the whole confirm→run→wire-PATH→verify sequence stays inside the same Textual app instance | This phase (v0.49.0 hardening cycle) | The PRD's own "deferred fork" (`unified-ui-redesign-v1.0-prd.md:134-138`) becomes real; headless (`--all`/`--categories`/`--yes`) mode is UNCHANGED and must stay console-only by design (no TTY, no Textual app at all) |

**Deprecated/outdated:** Nothing in this phase deprecates an existing
public interface — `run_wizard`'s console path, `configure_path`, `run_doctor`,
and every `Runner` implementation in `installer/run.py` remain valid and in
use for the headless/non-TTY path.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `clean_rc_duplicates` (the rc-dedup destructive confirm) is out of this phase's execute-screen scope and stays console-only for now | Common Pitfalls #4, Architectural Responsibility Map | If wrong, the plan under-scopes "verify" and a reviewer flags a missing confirm surface for rc-dedup; low risk to fix later since `clean_rc_duplicates` is currently unreachable from any TUI screen already, so nothing regresses either way |
| A2 | The new execute screen module should be named something other than `install_screen.py` (e.g. `execute_screen.py`) to avoid any filename echo of the abandoned branch | Recommended Project Structure | Purely cosmetic; wrong naming has zero functional risk, easy to rename in review |
| A3 | `--link-mode` on a later run should override the persisted value for THAT RUN ONLY, without overwriting the stored preference | Open Design Questions (carried from CONTEXT.md, still unresolved) | CONTEXT.md explicitly lists this as "NOT YET DECIDED" — the plan/discuss-phase step MUST confirm this with the user rather than silently building either behavior |
| A4 | The settings adjustment UI should fold into the existing `PoliciesScreen` rather than create a new "Settings" view | Architectural Responsibility Map, Open Questions | CONTEXT.md explicitly lists this as open; a new view requires justification against the "one view registry" constraint per CONTEXT.md's own framing — the plan must make and record this call, not default silently |
| A5 | Failure handling mid-run should continue with a per-tool running status list (not fail-fast), reusing `Summary`'s existing partial-outcome shape | Architectural Responsibility Map (implicit), Common Pitfalls | CONTEXT.md explicitly lists this as open; `run_installs` (unchanged, pure) already naturally supports "continue" semantics (its only stop condition is a blocked dependency chain, not a hard abort) — a fail-fast requirement would need NEW logic in the worker loop, not just reuse |

**If this table is empty:** N/A — see entries above; every one needs
explicit confirmation because CONTEXT.md itself marked the underlying
question unresolved.

## Open Questions

1. **Does the interactive TUI path fully replace `run_wizard`'s console
   sequence, or run alongside a restructured version of it?**
   - What we know: `run_wizard`'s headless path (`--all`/`--categories`)
     must stay unchanged — it never touches Textual at all.
   - What's unclear: The exact seam change in `setup.py`/`installer/app.py`
     for the interactive path (see Pitfall 2's two options).
   - Recommendation: Give the interactive TUI path its own top-level
     function that never calls `run_wizard`, so the headless path's tests
     and behavior are provably untouched by this phase's diff.

2. **Failure handling mid-run: fail-fast or continuous with a running
   status list, and is mid-run cancel supported?** (CONTEXT.md open
   question, restated.)
   - What we know: `Summary`/`InstallOutcome` already carry partial-outcome
     information across a whole run; `run_installs` is a single forward
     pass with no built-in early-abort.
   - What's unclear: Whether the user should be able to press a key to
     cancel a running install worker mid-tool (Textual workers ARE
     cancellable via `Worker.cancel()`, but a cancelled thread worker
     cannot interrupt a `subprocess.Popen.wait()` already in flight cleanly
     without also killing the child process — `proc.terminate()`/`proc.kill()`
     would need to be wired to the cancellation).
   - Recommendation: Ship continue-with-running-status-list (matches
     existing `Summary` shape, zero new logic); explicitly defer true
     mid-run cancellation as a follow-up unless the user confirms it's
     in-scope during discuss-phase, since it touches subprocess lifecycle
     management this phase's other primitives do not otherwise need.

3. **Settings wizard scope: `link_mode` only, or bundled with other
   one-time preferences?** (CONTEXT.md open question, restated.)
   - What we know: `link_mode` is the only concretely-specified persisted
     setting in this phase's CONTEXT.md; "default-shell preference,
     headless-flag defaults" are named as adjacent ideas from the same
     real-machine audit but not committed to this phase.
   - What's unclear: Whether bundling them now is in-scope or scope creep.
   - Recommendation: Ship `link_mode` only this phase (matches CONTEXT.md's
     concrete decisions); design `installer/settings.py`'s JSON envelope
     with a `"version": 1` field (mirroring `version_cache.py`) so adding
     more keys later is additive, not a migration.

## Environment Availability

Skipped — this phase has no external tool/service dependency beyond the
project's own already-verified `textual`/Python stdlib; no new CLI,
runtime, or network service is introduced.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest` + `pytest-asyncio` (`asyncio_mode = "auto"`) [VERIFIED: pyproject.toml, read this session] |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest tests/test_wizard_app.py -x -q` |
| Full suite command | `make test` (pytest with coverage) |

### Phase Requirements → Test Map

No `REQ-*` IDs are registered for this phase (see `<phase_requirements>`).
Mapping instead to CONTEXT.md's decisions/open questions:

| Decision | Behavior | Test Type | Automated Command | File Exists? |
|----------|----------|-----------|-------------------|-------------|
| D-01 | Confirming install pushes a new screen (not exit) | integration (Textual `Pilot`) | `uv run pytest tests/test_wizard_app.py -k execute_screen -x` | ❌ Wave 0 — new test file/section needed |
| D-02 | Screen stays visible after completion until keypress | integration (Textual `Pilot`) | same file | ❌ Wave 0 |
| D-05.2 | Every output line is attributed to a tool, unconditionally | unit (`StreamingRunner`, no Textual needed) | `uv run pytest tests/test_run.py -k streaming -x` | ❌ Wave 0 |
| D-05.3 | A cancelled prompt shows an explicit message, never a silent no-op | integration (`Pilot`) | `tests/test_wizard_app.py` | ❌ Wave 0 |
| `link_mode` persistence | Round-trip save/load, malformed file degrades safely | unit | `uv run pytest tests/test_settings.py -x` | ❌ Wave 0 — mirror `tests/test_...` pattern used for `version_cache.py`; check for an existing `tests/test_version_cache.py` as the template |

### Sampling Rate

- **Per task commit:** the narrowest test file touched (e.g.
  `uv run pytest tests/test_run.py -k streaming -x -q`)
- **Per wave merge:** `uv run pytest tests/test_wizard_app.py tests/test_run.py tests/test_settings.py -q`
- **Phase gate:** `make test` (full suite + coverage) green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_run.py` — add streaming-runner unit tests (a fake
      `Popen`-shaped subprocess via `monkeypatch`, matching this project's
      existing convention of injecting fakes rather than mocking
      `subprocess` directly — check `tests/test_run.py`'s current fakes
      first)
- [ ] `tests/test_settings.py` — new file for `installer/settings.py`
      (load/save round-trip, malformed-file degrade, matches
      `tests/test_...` for `version_cache.py` if one exists — verify at
      plan time)
- [ ] `tests/test_wizard_app.py` — extend with the new execute-screen
      Pilot-driven tests (this file already has 3787 lines and an
      established `_settle(app, pilot)` helper — reuse it)
- [ ] A throwaway (non-committed) spike script proving the
      `call_from_thread` + `push_screen_wait` combination works as expected
      (see Common Pitfalls #1) — do this BEFORE the real plan's tasks are
      written, since it may change the design

*(Framework install: none needed — `pytest`/`pytest-asyncio`/`textual` are
already project dependencies.)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | No | No auth surface in this phase |
| V3 Session Management | No | N/A |
| V4 Access Control | No | Single-user local CLI tool, unchanged |
| V5 Input Validation | Marginal | `link_mode` persisted value must be validated against the closed `{"centralized", "single", "split"}` set on load — a malformed/tampered `settings.json` must degrade to the safe default, never propagate an unvalidated string into `rc_paths_for_mode`/`ban_rc_paths` |
| V6 Cryptography | No | No new crypto surface (existing checksum verification in `installer/checksums.py` is unchanged and out of scope) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| A tampered/corrupted `settings.json` feeding an unvalidated `link_mode` string into `rc_paths_for_mode` | Tampering | Validate against the closed literal set on load (mirrors `installer/version_cache.py`'s existing "malformed entry degrades to 'never checked'" pattern) — reject and fall back to a safe default rather than propagating an arbitrary string into a file-path-selection function |
| Streamed subprocess output rendered into a Textual `RichLog`/`TextArea` containing terminal escape sequences from a misbehaving install script | Tampering / Denial of Service (terminal corruption) | `RichLog.write()` renders through Rich's own renderer, which does not execute raw ANSI escapes as terminal control codes the way a naive `print()` to a real terminal would — confirm this holds for whichever widget is chosen (`RichLog` is the safer default per its own rendering model; a plain `TextArea` used as a write-only buffer should be checked for the same property before being chosen) |
| A hung/wedged child process during a streamed install (e.g. a script waiting on stdin the installer never provides) | Denial of Service (the worker thread never returns, the screen never reaches D-02's "done" state) | `stdin=subprocess.DEVNULL` (no existing install command reads stdin — verified via the `Runner`-seam grep above, every call is `curl`/`chmod`/`unzip`/`ln`/`sh -c` argv, none interactive); consider a bounded overall timeout for the worker as a defense-in-depth measure, distinct from `run_query`'s existing `QUERY_TIMEOUT` (a query timeout is wrong here — a real `pnpm add -g` install legitimately takes minutes, per `DoctorScreen`'s own reinstall-worker precedent, which sets no timeout) |

## Sources

### Primary (HIGH confidence — read directly from this repository/its installed dependencies this session)

- `installer/app.py` (full file) — `run_wizard`, `configure_path`, the
  console-drop boundary
- `setup.py` (full file) — composition root, `_select_catalog`,
  `_resolve_link_mode`, `_build_app`, `_apply_fix`
- `installer/wizard_app.py` (full file, 1682 lines) — `DoctorScreen`,
  `UninstallScreen`, `PoliciesScreen`, `UnifiedApp`, every existing
  `@work`/`post_message` pattern
- `installer/ui_common.py` (full file) — `VIEWS`, `AppScreen`, `run_live`
- `installer/catalog_tui.py` (full file) — `CatalogScreen.Decided`, the
  existing version-refresh worker pattern
- `installer/session.py` (full file) — `run_installs`, `Summary`,
  `OnMismatch`
- `installer/engine.py` (full file) — `install_tool`, `MethodAwareRunner`
- `installer/render.py` (full file) — every `render_*` helper that must be
  adapted to widget text
- `installer/run.py` (full file) — every existing `Runner` implementation
- `installer/cli.py` (full file) — `Options`, existing headless flags
- `installer/locations.py` (full file) — `rc_paths_for_mode`, `ensure_dir`
- `installer/atomic.py` (full file) — `atomic_write_text`
- `installer/version_cache.py` (partial, load/save/default_cache_path) —
  the JSON-persistence pattern to mirror
- `installer/download.py`, `installer/postinstall.py` (grepped for `Runner`
  call sites) — confirmed the single-seam claim
- `.venv/lib/python3.12/site-packages/textual/app.py` — `call_from_thread`,
  `push_screen_wait` (read this session, quoted verbatim)
- `.venv/lib/python3.12/site-packages/textual/_work_decorator.py` — `work()`
  decorator signature
- `.venv/lib/python3.12/site-packages/textual/widgets/_rich_log.py` —
  `RichLog.write()` signature and threading note
- `.planning/phases/13-.../13-CONTEXT.md`, `13-AUDIT-install-experience.md`
  — the phase's own locked decisions and the abandoned-branch audit
- `.claude/architecture.md` — the five architecture rules, Phase 12 version-
  cache and worker precedents documented in prose
- `docs/prds/unified-ui-redesign-v1.0-prd.md:120-138` — the original
  "deferred fork" scoping language
- `tests/test_wizard_app.py`, `tests/test_app.py`, `tests/test_cli.py`
  (grepped for existing test shapes) — `Pilot`-based testing convention,
  `select_catalog` seam tests
- `pyproject.toml` — `textual>=8` pin, pytest config

### Secondary (MEDIUM confidence)

None — every claim in this document that is not a direct repository/
dependency read is explicitly logged in the Assumptions table above.

### Tertiary (LOW confidence)

None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependency; existing pin verified in the
  project's own `.venv`
- Architecture: HIGH for everything reusing existing patterns (worker/
  post_message, Console-redirect, atomic JSON state); MEDIUM for the
  `call_from_thread`+`push_screen_wait` combination specifically, because
  it is verified against Textual's own source but not yet exercised
  anywhere in this codebase
- Pitfalls: HIGH — every pitfall traces to either the phase's own audit
  file or a concrete code-level seam this session actually read

**Research date:** 2026-09-13
**Valid until:** 30 days (stable codebase, no external API/version churn
risk — the one time-sensitive fact, the installed Textual version, is
pinned in this project's own `pyproject.toml` and unlikely to change
mid-phase)
