# Phase 9 Plan Reviews (Cross-AI Convergence)

## Cycle 1 (codex-sol-high)

**Scope:** `09-01-PLAN.md`, `09-02-PLAN.md` (pre-execution plan review)

**HIGH 1** — The proposed field does not satisfy the required registry contract:
`Tool.postinstall` as a closed hook name conflicts with REQ-postinstall-field's
inline-command/`postinstall_script` requirement (ROADMAP SC#1); the dispatcher receives
only `(name, runner)`, not the successful `Method`, so the "method-aware" claim is false,
conflicting with REQ-postinstall-execution-timing.
Required revision: implement the declared inline/script field shapes at a Method-aware
boundary, or formally revise the requirement; pass the successful Method (or equivalent
context) to the postinstall executor.

**HIGH 2** — Host detection explicitly violates the critical `is_installed` requirement:
the plan uses `shutil.which(tool_id)` directly instead of `installer.status.is_installed`
(mandated by 09-RESEARCH.md lines 62-68), which also covers `detect_path` and app bundles.
Required revision: give the hook access to real catalog `Tool` objects and call
`is_installed(tool)` for each host; test the `is_installed` seam.

**HIGH 3** — A postinstall exception can still turn a completed install into FAILED:
`run_postinstall` is inserted inside the engine's existing install-method `try` block
(which catches `CommandError`/`ExecutorError`/`VersionError` around the whole success
branch), and the plan explicitly refuses defensive containment outside individual hooks.
Required revision: isolate postinstall execution from the install-method exception ladder;
add an engine test where `run_postinstall` itself raises, asserting the result stays
`INSTALLED`, a distinct warning is populated, and no fallback method executes.

**HIGH 4** — Tier-3 can pass without proving the MCP filesystem effect: asserts only
captured argv + exit code (never inspects resulting Claude/Cursor config files); `<verify>`
is an unconditional `echo` (not a real automated gate); `logging_runner` uses raw
`subprocess.run(..., check=True)` instead of this project's `run_command`/`CommandError`
seam, so the described `postinstall_warning` retry path "cannot work as described."
Required revision: make the real container command the automated verifier, use
`run_command` rather than raw `subprocess.run`, assert actual MCP config-file entries in
the throwaway filesystem, add a second zero-host case proving no Claude config is created.

**MEDIUM 1** — The 16-case matrix only asserts `"auto"` absence, not full expected argv
per subset (order, exclusions, `cursor-agent`->`cursor` mapping).

**LOW 2** — Malformed `postinstall` values (non-string, empty) are rejected by the parser
but untested in the same commit.

**Confirmed correct:** the `["codegraph","install","--target",csv,"--location","global",
"--yes"]` construction never uses `--target auto`; the `cursor-agent`->`cursor` mapping is
present; the zero-host branch skips the runner; D-01 is implemented simply (not
over-engineered); both plans have `cross_ai: true`; core same-commit test coverage exists
(gaps are about contract completeness, not total absence).

`CYCLE_SUMMARY: current_high=4 current_actionable=2`

**Disposition:** All 4 HIGH + MEDIUM 1 + LOW 2 fixed directly in `09-01-PLAN.md`/
`09-02-PLAN.md` per Rule 10 (no re-spawn of gsd-planner):
- HIGH 1: `run_postinstall`/hooks now receive the successful `Method`
  (`PostinstallHook = Callable[[Method, Runner, Mapping[str, Tool]], str | None]`);
  `design_decisions` now explicitly reconciles REQ-postinstall-field's literal
  inline/script wording against the closed-dispatch-name shape chosen, recorded as a
  deliberate, documented interpretation (also captured as a Key Decision row in
  09-02 Task 2).
- HIGH 2: hook host-presence check switched from bare `shutil.which(tool_id)` to
  `installer.status.is_installed(tool)`, with the four host `Tool` objects threaded
  through a new `tools: Mapping[str, Tool]` parameter on `install_tool`/`run_postinstall`,
  populated by `run_wizard`'s already-loaded catalog.
- HIGH 3: postinstall dispatch moved to its own dedicated `try/except Exception` at the
  call site, positioned after the method's own success/exception handling has already
  concluded — never sharing the method ladder's `except CommandError | ExecutorError |
  VersionError` block. New behavior/test: `run_postinstall` itself raising is proven to
  leave `status == INSTALLED` with a populated `postinstall_warning` and dispatch no
  fallback method.
- HIGH 4: Tier-3's `<verify>` now re-execs a scoped assertion inside the same container
  reading the fake `$HOME/.claude.json`/cursor MCP config path(s) for the real
  `mcpServers.codegraph` entry; `logging_runner` now wraps `installer.run.run_command`
  (raising `CommandError`, not raw `subprocess.CalledProcessError`); a second all-hosts-
  absent case is added proving no Claude config file is created at all.
- MEDIUM 1: the 16-subset matrix test now asserts full expected argv (or no call) for
  every subset, not merely `"auto"`'s absence.
- LOW 2: same-commit tests added for empty-string and non-string `postinstall` values.

Proceeding to cycle 2.
