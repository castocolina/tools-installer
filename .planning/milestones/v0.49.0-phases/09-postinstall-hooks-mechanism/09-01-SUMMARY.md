---
phase: 09-postinstall-hooks-mechanism
plan: 01
subsystem: infra
tags: [postinstall-hooks, codegraph, mcp, registry, install-engine, catalog]

requires:
  - phase: 08-ai-tier-catalog-expansion-uv-tool-executor
    provides: codegraph's own registry entry (github_release methods, ai-tier catalog)
provides:
  - "Tool.postinstall: closed-set-validated registry field naming a one-time follow-up hook"
  - "installer/postinstall.py: closed PostinstallHook dispatch table, codegraph's own MCP-register hook"
  - "InstallOutcome.postinstall_warning: non-fatal failure surface dispatched from install_tool"
  - "render_postinstall_warnings wired into the real run_wizard path"
  - "codegraph's registry.toml entry declares postinstall = codegraph-mcp-register with a dated, substring-pinned comment"
affects: [09-02-postinstall-hooks-mechanism-tier3-container-proof]

actuals:
  tokens: 5699
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Closed dispatch-by-name table (installer/postinstall.py) mirroring installer.executors's SMOKE_CHECKS pattern, validated at registry-load time"
    - "try/except/else isolation boundary in a ladder loop: a new else clause runs only on the try's success, keeping a post-success side-effect's own exception handling structurally separate from the loop's own exception clauses"

key-files:
  created:
    - installer/postinstall.py
    - tests/test_postinstall.py
  modified:
    - installer/model.py
    - installer/engine.py
    - installer/session.py
    - installer/render.py
    - installer/app.py
    - installer/registry.toml
    - tests/test_model.py
    - tests/test_engine.py
    - tests/test_session.py
    - tests/test_render.py
    - tests/test_app.py
    - tests/test_registry.py

key-decisions:
  - "postinstall lives on Tool (not Method) as a closed dispatch-hook NAME, never a literal command string, mirroring the existing smoke param"
  - "Host-presence check uses installer.status.is_installed against real catalog Tool objects, threaded into install_tool via a new tools: Mapping[str, Tool] | None parameter, reached through the real run_wizard -> run_installs -> install_tool chain via a new catalog parameter on run_installs"
  - "install_tool's method ladder uses try/except/else so a postinstall hook's own exception is isolated from the method ladder's CommandError/ExecutorError/VersionError handling and can never masquerade as a method failure"
  - "codegraph's hook never passes --target auto (confirmed unsafe by 09-RESEARCH.md); it always composes an explicit --target CSV from live is_installed checks, mapping cursor-agent -> codegraph's own cursor id"
  - "codegraph is invoked by its resolved absolute bin_dir path, never a bare codegraph name relying on PATH"

requirements-completed:
  - REQ-postinstall-field
  - REQ-postinstall-execution-timing
  - REQ-postinstall-idempotency-live-check
  - REQ-postinstall-noninteractive-only
  - REQ-codegraph-mcp-postinstall

coverage:
  - id: D1
    description: "Tool.postinstall field parses from registry.toml, closed-set validated at load time (unknown name, empty string, non-string all rejected)"
    requirement: REQ-postinstall-field
    verification:
      - kind: unit
        ref: "tests/test_model.py#test_postinstall_field_parses_with_a_known_hook_name"
        status: pass
      - kind: unit
        ref: "tests/test_model.py#test_unknown_postinstall_name_is_rejected"
        status: pass
      - kind: unit
        ref: "tests/test_model.py#test_empty_string_postinstall_is_rejected"
        status: pass
      - kind: unit
        ref: "tests/test_model.py#test_non_string_postinstall_is_rejected"
        status: pass
    human_judgment: false
  - id: D2
    description: "install_tool dispatches a tool's postinstall hook exactly once, immediately after the succeeded Method, isolated from the method ladder's own exception handling"
    requirement: REQ-postinstall-execution-timing
    verification:
      - kind: unit
        ref: "tests/test_engine.py#test_postinstall_hook_dispatches_after_a_successful_install"
        status: pass
      - kind: unit
        ref: "tests/test_engine.py#test_postinstall_hook_exception_does_not_fail_the_install_or_crash"
        status: pass
      - kind: unit
        ref: "tests/test_engine.py#test_already_installed_never_dispatches_postinstall"
        status: pass
      - kind: unit
        ref: "tests/test_engine.py#test_failed_install_never_dispatches_postinstall"
        status: pass
    human_judgment: false
  - id: D3
    description: "A postinstall failure is carried on InstallOutcome.postinstall_warning and rendered on the real run_wizard path, without ever changing status away from INSTALLED"
    requirement: REQ-postinstall-execution-timing
    verification:
      - kind: unit
        ref: "tests/test_engine.py#test_postinstall_failure_does_not_fail_the_install"
        status: pass
      - kind: unit
        ref: "tests/test_render.py#test_render_postinstall_warnings_names_the_tool_and_the_detail"
        status: pass
      - kind: unit
        ref: "tests/test_app.py#test_run_wizard_surfaces_a_postinstall_warning_on_the_real_path"
        status: pass
    human_judgment: false
  - id: D4
    description: "codegraph's MCP-register hook composes an explicit, never-auto --target CSV from a live is_installed host-presence check (cursor-agent mapped to cursor), invoking codegraph by its resolved absolute bin_dir path, across all 16 host-presence subsets"
    requirement: REQ-codegraph-mcp-postinstall
    verification:
      - kind: unit
        ref: "tests/test_postinstall.py#test_codegraph_hook_matches_expected_argv_for_every_host_presence_subset"
        status: pass
      - kind: unit
        ref: "tests/test_postinstall.py#test_codegraph_hook_preserves_declared_host_order"
        status: pass
      - kind: unit
        ref: "tests/test_postinstall.py#test_codegraph_hook_maps_cursor_agent_alone_to_cursor"
        status: pass
      - kind: unit
        ref: "tests/test_postinstall.py#test_codegraph_hook_invokes_the_resolved_absolute_binary_path_not_a_bare_name"
        status: pass
    human_judgment: false
  - id: D5
    description: "The full loaded catalog reaches install_tool via a new catalog parameter threaded through run_installs's Install protocol and all three of its install(...) call sites, and via run_wizard building {t.id: t for t in tools} into run_installs"
    requirement: REQ-postinstall-idempotency-live-check
    verification:
      - kind: unit
        ref: "tests/test_session.py#test_run_installs_threads_catalog_into_every_install_call"
        status: pass
      - kind: unit
        ref: "tests/test_app.py#test_run_wizard_passes_the_full_catalog_as_tools_by_id_into_run_installs"
        status: pass
    human_judgment: false
  - id: D6
    description: "codegraph's real registry.toml entry declares postinstall = codegraph-mcp-register with a dated comment recording the research findings (codegraph-mcp-register, --target auto, cursor-agent, is_installed, D-01)"
    requirement: REQ-codegraph-mcp-postinstall
    verification:
      - kind: unit
        ref: "tests/test_registry.py#test_codegraph_declares_the_mcp_postinstall_hook"
        status: pass
      - kind: unit
        ref: "tests/test_registry.py#test_codegraph_entry_records_the_postinstall_research_findings"
        status: pass
      - kind: unit
        ref: "tests/test_registry.py#test_only_codegraph_declares_a_postinstall_hook"
        status: pass
    human_judgment: false

duration: 45min
completed: 2026-09-06
status: complete
---

# Phase 9 Plan 1: Postinstall Hooks Mechanism Summary

**Wired a closed, code-owned postinstall-hooks mechanism end-to-end through `installer/model.py` -> `installer/postinstall.py` -> `installer/engine.py` -> `installer/session.py` -> `installer/render.py` -> `installer/app.py`, proven via codegraph's own MCP-server registration for whichever agent hosts are already present.**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-09-06 (session start)
- **Completed:** 2026-09-06
- **Tasks:** 2/2 completed
- **Files modified:** 14 (7 production, 7 test; 2 new files)

## Accomplishments

- `Tool.postinstall: str | None` field, closed-set validated at `load_tools` time against `POSTINSTALL_HOOK_NAMES`, mirroring the existing `smoke` param's closed-dispatch-by-name shape — a registry edit alone can never introduce arbitrary post-install execution.
- New `installer/postinstall.py` module: `PostinstallHook` dispatch table, `POSTINSTALL_HOOKS`, `run_postinstall`, and `_codegraph_mcp_register` — codegraph's own hook composes an explicit, never-`auto` `--target` CSV from a live `installer.status.is_installed` host-presence check (mapping `cursor-agent` -> codegraph's own `cursor` id), invoking the freshly-installed binary by its resolved absolute `bin_dir`-relative path.
- `installer/engine.py::install_tool` dispatches a tool's `postinstall` hook immediately after the succeeding `Method`, via a `try/except/else` restructure of the method ladder that structurally isolates a hook's own exception from the ladder's `CommandError`/`ExecutorError`/`VersionError` handling. A hook failure (returned string, or a caught crash) is carried on the new `InstallOutcome.postinstall_warning` field and never changes `status` away from `INSTALLED`.
- The full loaded catalog reaches `install_tool` through the real production call chain: a new `catalog: Mapping[str, Tool] | None` parameter on `installer/session.py::run_installs`, threaded as `tools=catalog` into all three of its `install(...)` call sites, sourced from `run_wizard`'s own `tools: list[Tool]` parameter (`{t.id: t for t in tools}`) with zero new file I/O.
- `installer/render.py::render_postinstall_warnings` prints each tool's postinstall warning (silent when none), wired into `run_wizard` between `render_skipped` and `render_verification`.
- `installer/registry.toml`'s `codegraph` entry declares `postinstall = "codegraph-mcp-register"` with a dated comment recording this session's live research findings.
- Task 2 pinned the mechanism exhaustively: a 16-subset parametrized matrix over every combination of `claude`/`codex`/`opencode`/`cursor-agent` presence, a declared-order CSV pin, an isolated `cursor-agent` -> `cursor` mapping test, and an engine-level test proving a tool with no successful method never reaches the postinstall dispatch. Task 2 shipped tests-only, as the plan predicted — Task 1's implementation already had the correct shape.

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end postinstall mechanism wired through every layer** - `e352d6d` (feat)
2. **Task 2: Exhaustive host-presence matrix and edge-case tests** - `957a0b2` (test)

_Note: Task 1 was `tdd="true"` — RED tests were written first (confirmed failing for `AttributeError`/`ModuleNotFoundError`/`DID NOT RAISE` reasons, never a typo), then implementation made them GREEN, all within the single Task 1 commit per the plan's tracer-task pattern (production-quality, single commit, not a separate RED/GREEN commit pair)._

## Files Created/Modified

- `installer/postinstall.py` - New module: closed `PostinstallHook` dispatch table and codegraph's own MCP-register hook
- `installer/model.py` - `Tool.postinstall` field + `POSTINSTALL_HOOK_NAMES` closed-set validation
- `installer/engine.py` - `InstallOutcome.postinstall_warning`, `try/except/else` dispatch in `install_tool`
- `installer/session.py` - `catalog` parameter threaded through `run_installs`'s `Install` protocol and all three call sites
- `installer/render.py` - `render_postinstall_warnings`
- `installer/app.py` - Wires `render_postinstall_warnings` + catalog-building into `run_wizard`
- `installer/registry.toml` - `codegraph`'s `postinstall = "codegraph-mcp-register"` with dated research comment
- `tests/test_postinstall.py` - New file: hook composition, no-op path, absolute-path resolution, 16-subset matrix
- `tests/test_model.py`, `tests/test_engine.py`, `tests/test_session.py`, `tests/test_render.py`, `tests/test_app.py`, `tests/test_registry.py` - Mirror coverage for each touched production file

## Decisions Made

- `postinstall` lives on `Tool`, not `Method` — codegraph's postinstall command is identical regardless of which `github_release` method succeeded, and this mirrors where `requires`/`recommends` already live.
- Host-presence detection uses `installer.status.is_installed` (never a hook-local `shutil.which` reimplementation), threaded in as a `tools: Mapping[str, Tool]` parameter rather than reloading the registry inside the hook.
- The method ladder's `try/except/else` restructure (not a same-`try` placement) is the only shape that structurally guarantees a postinstall hook's own exception can never be caught by, or mistaken for, the ladder's own `CommandError`/`ExecutorError`/`VersionError` handling.
- codegraph's hook resolves and invokes the binary by its absolute `bin_dir`-relative path (matching exactly what `install_download` itself wrote), never a bare `"codegraph"` relying on the current process's PATH.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] Fixed pyright strict-mode failures from untyped test lambdas and literal typing**
- **Found during:** Task 1, running `make validate` before the Task 1 commit
- **Issue:** Several new tests used bare `lambda`s assigned to variables (pyright cannot infer parameter/return types for these under strict mode: `reportUnknownLambdaType`/`reportUnknownVariableType`/`reportUnknownArgumentType`), one `iter([...])` produced a `str` where `MismatchChoice` (a `Literal`) was required (`reportReturnType`), and one recording tuple used `object`/`object()` instead of the real `Runner` type.
- **Fix:** Replaced the flagged lambdas with named, fully-typed nested functions (matching this file's own existing convention, e.g. `_not_installed`); replaced the `iter([...])`-based mismatch-choice fixture with an explicitly `list[MismatchChoice]`-typed queue; typed the `run_postinstall` dispatch-forwarding test's runner/hook signatures against the real `Runner`/`PostinstallHook`-shaped types instead of `object`.
- **Files modified:** `tests/test_engine.py`, `tests/test_postinstall.py`, `tests/test_session.py`, `tests/test_app.py`
- **Verification:** `make validate` (pyright strict) passes with 0 errors
- **Committed in:** `e352d6d` (part of Task 1's commit)

**2. [Rule 3 - Blocking issue] Removed private-symbol access flagged by pyright**
- **Found during:** Task 2, running `make validate` before the Task 2 commit
- **Issue:** The 16-subset parametrized test computed its expected CSV by reaching into `installer.postinstall`'s private `_CODEGRAPH_TARGETS` mapping from the test module (`reportPrivateUsage`).
- **Fix:** Added a local `_EXPECTED_TARGET_FOR` mapping in the test file (mirroring, not importing, the production mapping) — the same "duplicated, not imported" layering discipline this plan's own design decisions already apply to `SMOKE_CHECK_NAMES`/`POSTINSTALL_HOOK_NAMES`.
- **Files modified:** `tests/test_postinstall.py`
- **Verification:** `make validate` passes with 0 pyright errors; the 16-subset matrix still asserts the exact expected argv
- **Committed in:** `957a0b2` (part of Task 2's commit)

**3. [Proactive, no rule needed] `test_codegraph_hook_returns_a_warning_string_on_command_error_not_raise` written in Task 1 instead of Task 2**
- **Found during:** Task 1, writing `tests/test_postinstall.py`
- **Issue:** The plan's Task 2 `<behavior>` section lists this test, but Task 1's own `<behavior>` section requires the same underlying guarantee (a hook returns a warning string on `CommandError`, never raises) to make the Task 1 `<verify>` automated command's zero-hosts/present-hosts assertions meaningful, and the module docstring for `_codegraph_mcp_register` documents this contract directly.
- **Fix:** No fix needed — the test was written once, during Task 1, and Task 2 confirmed it (and the rest of Task 1's shape) already satisfied every new assertion added.
- **Files modified:** none (documentation-only note)
- **Verification:** n/a
- **Committed in:** `e352d6d` (Task 1)

---

**Total deviations:** 2 auto-fixed (2x Rule 3 — both were `make validate` strict-typing/lint failures caught before commit, not correctness bugs), 1 proactive test-placement note.
**Impact on plan:** No scope creep. Both Rule 3 fixes were required to satisfy this project's own non-negotiable "never bypass a quality gate" rule (CLAUDE.md) and the plan's own acceptance criterion that `make validate && make test` exits 0 on each task's commit; neither touched behavior, only test-code typing.

## Issues Encountered

**Worktree base mismatch (resolved before any task work began).** This agent's worktree (`worktree-agent-a2208af7682feb776`) was initially on a branch whose tip (`581c097`, the "TUI interaction consistency" feature branch) predated `gsd/phase-09-postinstall-hooks-mechanism`'s tip by several phases' worth of catalog/model work (Tier, `recommends`, `sdkman`, `uv-tool`, etc. — all absent from the stale base). Verified `581c097` is a genuine git ancestor of `gsd/phase-09-postinstall-hooks-mechanism`'s tip (`33cabec`) via `git merge-base --is-ancestor`, confirming zero risk of data loss, then fast-forwarded (`git merge --ff-only`) this worktree's branch to `33cabec` before touching any file. This was a non-destructive, history-preserving operation (no `reset --hard`, no rebase, no force-push) consistent with the destructive-git prohibitions governing this session. Both plan tasks were then executed entirely on the correct base.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

The postinstall-hooks mechanism is fully wired, tested, and proven at the unit level across every host-presence combination. `09-02-PLAN.md` (Tier-3 real-container proof) can proceed: it needs only this plan's production code (`installer/postinstall.py`, `installer/engine.py`'s dispatch, `installer/registry.toml`'s `codegraph` entry) — no further changes to this plan's files are anticipated. No blockers.

---
*Phase: 09-postinstall-hooks-mechanism*
*Completed: 2026-09-06*

## Self-Check: PASSED

- All 14 claimed key-files (7 production, 7 test) verified present on disk via `ls`.
- Both task commits (`e352d6d`, `957a0b2`) verified present via `git log --oneline --all`.
- `make validate && make test` re-run on the final committed tree: 0 lint/format/type/security/dead-code findings, 1296 tests passed, 99.41% coverage (floor 90%).
- All `<acceptance_criteria>` from both tasks re-verified passing (mechanism script prints `MECHANISM_OK`, docstring substrings present, registry greps ≥1, registry `load_tools` check passes, 16-subset parametrized matrix all green).
