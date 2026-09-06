---
phase: 09-postinstall-hooks-mechanism
plan: 02
subsystem: infra
tags: [postinstall-hooks, codegraph, mcp, tier3-container, docker, colima, architecture-docs]

requires:
  - phase: 09-postinstall-hooks-mechanism
    provides: "09-01's postinstall dispatch mechanism (Tool.postinstall, installer/postinstall.py, install_tool wiring) and unit-level proof"
provides:
  - "Real Tier-3 disposable-container evidence (colima + docker) that the postinstall mechanism's host-presence-aware CSV composition works end to end against a real filesystem"
  - "Real evidence that codegraph's own fresh github_release install succeeds end to end and its MCP registration writes real ~/.claude.json and ~/.cursor/mcp.json config entries"
  - "Real evidence of the documented no-op: zero hosts present -> no codegraph install call, no ~/.claude.json created"
  - ".claude/architecture.md '## Phase 9: postinstall hooks' section documenting the mechanism as a discoverable convention"
  - ".planning/PROJECT.md Key Decisions table gains four Phase 9 rows consolidating this phase's real decisions"
affects: []

actuals:
  tokens: 1600
  tasks: 2
  commits: 1

tech-stack:
  added: []
  patterns:
    - "Tier-3 disposable-container verification (colima + docker, python:3.13-slim base) run through the real installer.engine.install_tool production entry point, never a hand-built Method/ExecContext or stubbed dispatch"
    - "Single set -euo pipefail script wrapping two separate docker run invocations (one per host-presence case), so a failure in either case aborts the whole gate with a non-zero exit"

key-files:
  created: []
  modified:
    - .claude/architecture.md
    - .planning/PROJECT.md

key-decisions:
  - "Task 1's tier3-verify.sh script was written, run, and its full output recorded verbatim below, then deleted (left uncommitted) per the plan's own instruction that it is a temporary verification tool, not production or test code"
  - "Task 1 produced no commit of its own (pure verification, no production/test file changes) — its evidence is folded into this SUMMARY per the plan's acceptance criteria and human_verify_mode: end-of-phase's consolidation design"
  - "The new architecture.md section was appended immediately after the existing 'Phase 3: install, uninstall, and tweak lifecycle' section (the only other phase-numbered heading in the file), before 'Registry-authoring guidelines' — the plan's named anchor point, applied literally since no additional phase-specific headings existed to reconsider the anchor"

requirements-completed:
  - REQ-codegraph-mcp-postinstall

coverage:
  - id: D1
    description: "Real disposable-container proof (colima+docker) that the postinstall mechanism's host-presence-aware --target CSV composition works against genuine PATH detection, through the real installer.engine.install_tool entry point and the real committed codegraph registry entry"
    requirement: REQ-codegraph-mcp-postinstall
    verification:
      - kind: e2e
        ref: ".planning/phases/09-postinstall-hooks-mechanism/tier3-verify.sh (run_case present) — TIER3_CASE_OK[present]"
        status: pass
    human_judgment: false
  - id: D2
    description: "Real disposable-container proof that zero installed hosts produces the documented no-op: no codegraph install call captured, no ~/.claude.json file created"
    requirement: REQ-codegraph-mcp-postinstall
    verification:
      - kind: e2e
        ref: ".planning/phases/09-postinstall-hooks-mechanism/tier3-verify.sh (run_case absent) — TIER3_CASE_OK[absent]"
        status: pass
    human_judgment: false
  - id: D3
    description: "Postinstall hooks mechanism documented as a discoverable architectural convention in .claude/architecture.md"
    verification:
      - kind: other
        ref: "grep -q '## Phase 9: postinstall hooks' .claude/architecture.md"
        status: pass
    human_judgment: false
  - id: D4
    description: "Phase 9's four real decisions consolidated into .planning/PROJECT.md's Key Decisions table with Outcome = Phase 9"
    verification:
      - kind: other
        ref: "[ \"$(grep -cE '\\| Phase 9 \\|$' .planning/PROJECT.md)\" -eq 4 ]"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-09-06
status: complete
---

# Phase 9 Plan 2: Tier-3 Container Proof and Architecture/Decision Consolidation Summary

**Real disposable-container run proves codegraph's postinstall MCP-registration hook composes the correct host-presence-aware `--target` CSV and writes real `~/.claude.json`/`~/.cursor/mcp.json` entries; zero-hosts case proves the documented no-op; mechanism documented in architecture.md and four decisions consolidated into PROJECT.md.**

## Performance

- **Duration:** ~25 min
- **Completed:** 2026-09-06
- **Tasks:** 2 (Task 1: pure verification, no commit; Task 2: docs, 1 commit)
- **Files modified:** 2 (`.claude/architecture.md`, `.planning/PROJECT.md`)

## Base-branch correction (pre-execution)

Before starting, per the launch instructions, the worktree's branch was found to be based
several phases behind (`worktree-agent-a50c0389828b874cc` at `581c097`, the tip of the
`feat/tui-interaction-consistency` line, predating all of Phase 1-9's `.planning/` work).
`git merge-base HEAD fdc5cd0` returned `581c097` (== `HEAD`), confirming `HEAD` was a strict
ancestor of `gsd/phase-09-postinstall-hooks-mechanism`'s tip `fdc5cd0`, not diverged from it.
`git merge --ff-only fdc5cd0` fast-forwarded cleanly (196 files changed, 0 conflicts),
bringing in all of Phases 1-9's `.planning/` history plus `installer/postinstall.py`,
`installer/engine.py`'s `tools`-threaded `install_tool`, and the `codegraph` registry entry's
`postinstall = "codegraph-mcp-register"` field that this plan's Tier-3 container recipe
requires. Verified present before proceeding.

## Accomplishments

- Confirmed colima was already running (`colima status` reported `macOS Virtualization.Framework`, `runtime: docker`) — no `brew install docker`/`colima start` needed.
- Wrote `.planning/phases/09-postinstall-hooks-mechanism/tier3-verify.sh` exactly per the plan's literal `<action>` block: two separate `docker run` invocations (host-`present` and host-`absent`) wrapped in one `set -euo pipefail` script, each running the real `installer.engine.install_tool` against the real `codegraph` registry entry inside a throwaway `python:3.13-slim` container, with NO `uv` installed and NO `~/.local/bin` ever placed on `PATH`.
- Ran the script: **both cases passed**, `TIER3_GATE_OK` printed, exit 0. Full transcript recorded verbatim below.
- Deleted `tier3-verify.sh` after use per the plan's own instruction that it is a temporary verification tool, not production or test code (left uncommitted, as permitted).
- Added a new `## Phase 9: postinstall hooks` section to `.claude/architecture.md`, appended immediately after the existing `## Phase 3: install, uninstall, and tweak lifecycle` section (the only other phase-specific heading in the file) — documenting `Tool.postinstall`'s closed dispatch-hook design, its Method-aware/`try-except`-isolated dispatch, `postinstall_warning`'s non-fatal surface, and codegraph's live `is_installed`-based host-presence check with the `cursor-agent` -> `cursor` id mapping and the `--target auto` rejection.
- Added four new rows to `.planning/PROJECT.md`'s Key Decisions table (Outcome = `Phase 9`, unsuffixed), each condensed to a decision + rationale + cross-reference, mirroring the exact three-column shape of every prior phase's rows. Bumped the `*Last updated: ...*` footer to `2026-09-06 after Phase 9 Postinstall Hooks Mechanism (09-01..09-02)`.
- `make validate && make test` passed on the committed tree: ruff (check + format), pyright (0 errors), bandit, vulture, shellcheck all clean; `pytest --cov` — 1296 passed, 99.41% coverage (gate: 90%).
- Verified `git diff -- .claude/architecture.md` shows only the new appended section, and `git diff -- .planning/PROJECT.md` shows only the four new rows plus the footer line — no existing content altered, reordered, or removed.

## Tier-3 Container Transcript (verbatim, both cases)

Command: `bash .planning/phases/09-postinstall-hooks-mechanism/tier3-verify.sh`

Package-manager noise (`apt-get`/`debconf` output, identical in both runs) is elided below
with `[... apt-get install curl/tar/ca-certificates output, identical in both runs ...]`;
everything printed by the Python verification body and the real `codegraph` CLI is verbatim
and complete.

### Case: `present` (fake `claude`/`cursor-agent` planted, `codex`/`opencode` absent)

```
[... apt-get install curl/tar/ca-certificates output, identical in both runs ...]
Python 3.13.15
/usr/local/bin/claude
/usr/local/bin/cursor-agent
┌  CodeGraph v1.6.0
│
◆  Claude Code: Created ~/.claude.json
│
◆  Claude Code: Created ~/.claude/settings.json
│
◆  Claude Code: Updated ~/.claude/settings.json
│
◆  Claude Code: Created ~/.claude/CLAUDE.md
│
◆  Cursor: Created ~/.cursor/mcp.json
│
●  Cursor: Restart Cursor for MCP changes to take effect.
│
◇  Next: index a project ──────────────────────────────────────────────────╮
│                                                                          │
│  cd <your-project>                                                       │
│  codegraph init        # build a project's graph (one time; auto-syncs   │
│  after)                                                                  │
│  # (codegraph install --init does both steps in one command)             │
│                                                                          │
├──────────────────────────────────────────────────────────────────────────╯
codegraph collects anonymous usage stats (no code, paths, or names) — "codegraph telemetry off" or CODEGRAPH_TELEMETRY=0 disables. Details: https://github.com/colbymchenry/codegraph/blob/main/TELEMETRY.md
│
└  Done! Restart your agents to use CodeGraph.

CODEGRAPH_OUTCOME[present] installed github_release True
POSTINSTALL_ARGV[present] [['/root/.local/bin/codegraph', 'install', '--target', 'claude,cursor', '--location', 'global', '--yes']]
POSTINSTALL_WARNING[present] None
CLAUDE_MCP_ENTRY[present] {'type': 'stdio', 'command': 'codegraph', 'args': ['serve', '--mcp']}
CURSOR_MCP_ENTRY[present] [(PosixPath('/root/.cursor/mcp.json'), {'type': 'stdio', 'command': 'codegraph', 'args': ['serve', '--mcp', '--path', '${workspaceFolder}']})]
TIER3_CASE_OK[present]
```

### Case: `absent` (zero agent-host stubs planted)

```
[... apt-get install curl/tar/ca-certificates output, identical in both runs ...]
Python 3.13.15
CODEGRAPH_OUTCOME[absent] installed github_release True
POSTINSTALL_ARGV[absent] []
POSTINSTALL_WARNING[absent] None
TIER3_CASE_OK[absent]
```

### Gate result

```
TIER3_GATE_OK
```

Script exit code: 0.

## Requirement-by-Requirement Confirmation (phase close-out, per `human_verify_mode: end-of-phase`)

- **REQ-postinstall-field** — satisfied by 09-01 (`Tool.postinstall` closed-set field, `installer/model.py::POSTINSTALL_HOOK_NAMES`); documented as a discoverable convention in this plan's new `.claude/architecture.md` section.
- **REQ-postinstall-execution-timing** — satisfied by 09-01 (`installer/engine.py::install_tool` dispatches immediately after the succeeding `Method`, Method-aware, never on `ALREADY_INSTALLED`); restated in this plan's architecture.md section and PROJECT.md decision row 3.
- **REQ-postinstall-idempotency-live-check** — satisfied by 09-01 (`_codegraph_mcp_register`'s live `is_installed` check, no state-tracking database); this plan's Tier-3 `absent` case proves the live no-op empirically (zero hosts -> zero `codegraph install` calls, no config file written).
- **REQ-postinstall-noninteractive-only** — satisfied by 09-01 (`--yes` plus always-explicit `--target`/`--location`); this plan's real container run confirms the actual `codegraph` CLI never blocked on a prompt in either case.
- **REQ-codegraph-mcp-postinstall** — the requirement this plan exists to close: SC#5's real-machine half. Proven above by the Tier-3 transcript — real `codegraph install --target claude,cursor --location global --yes` argv captured exactly as expected, real `~/.claude.json` and `~/.cursor/mcp.json` `mcpServers.codegraph` entries found, and the all-hosts-absent case proving no config file is created at all.

This closes Phase 9: SC#1-SC#4 and the mechanism half of SC#5 (09-01) plus the real-container
half of SC#5 (this plan) are all satisfied.

## Task Commits

1. **Task 1: Tier-3 verification — real install of `codegraph` plus its postinstall MCP-registration hook** — no commit (pure verification, no production or test file changes, per the plan's own acceptance criteria; evidence recorded above).
2. **Task 2: Document the postinstall mechanism in `.claude/architecture.md` and consolidate Phase 9's decisions into `.planning/PROJECT.md`** - `fe1eb8d` (docs)

## Files Created/Modified
- `.claude/architecture.md` - Added `## Phase 9: postinstall hooks` section documenting the closed dispatch-hook mechanism
- `.planning/PROJECT.md` - Added 4 Key Decisions rows (Outcome = Phase 9) and bumped the `Last updated` footer

## Decisions Made

- Task 1's `tier3-verify.sh` was deleted after producing its recorded evidence, per the plan's own "temporary — deleted or left uncommitted after this task" instruction. Its full source (as written and run) matched the plan's `<action>` block verbatim; no deviation.
- The new `.claude/architecture.md` section was placed immediately after the `## Phase 3` section (the only other phase-numbered heading found in the file) and before `## Registry-authoring guidelines` — the plan's named anchor, applied literally.
- No production or test code was touched by either task, matching the plan's stated scope boundary.

## Deviations from Plan

None - plan executed exactly as written. The base-branch fast-forward described above was a pre-execution correction mandated by the launch instructions, not a deviation from the plan's own task content.

## Issues Encountered

None. Colima was already running, so the `<precondition>` needed no remediation. The Tier-3 script passed on the first run in both cases — no retry was needed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 9 (postinstall hooks mechanism) is fully closed: both plans (09-01, 09-02) executed,
all five requirements this phase owns are satisfied and evidenced, `make validate && make
test` pass on the committed tree (1296 passed, 99.41% coverage), and the Tier-3 real-container
evidence ONESHOT-RULES Rule 14 requires for this milestone's one genuinely new
install-adjacent mechanism is recorded above. No blockers for the next phase.

---
*Phase: 09-postinstall-hooks-mechanism*
*Completed: 2026-09-06*

## Self-Check: PASSED

- `09-02-SUMMARY.md` exists on disk: FOUND
- `.claude/architecture.md` contains `## Phase 9: postinstall hooks`: FOUND
- `.planning/PROJECT.md` contains exactly 4 rows ending in `| Phase 9 |`: FOUND (4)
- Commit `fe1eb8d` exists in git log: FOUND
- `make validate && make test` exit 0 on the committed tree: CONFIRMED (1296 passed, 99.41% coverage)
