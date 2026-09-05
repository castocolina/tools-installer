---
phase: 05-registry-method-corrections-codegraph-mmdc-puppeteer
plan: 02
subsystem: registry
tags: [codegraph, github_release, SHA256SUMS, catalog]

requires:
  - phase: 05-01
    provides: sequenced tree so this plan's TDD red phase does not collide with 05-01's make validate && make test gate
provides:
  - codegraph catalog entry as checksum-verified kind=github_release
  - live v1.6.0 GitHub-API verification record on the entry
  - ai-tier tripwire moved 9 -> 10
affects:
  - 05-03 (user-tier tripwire 35 -> 36; do not reorder)
  - Phase 8 REQ-agent-host-entries (inherits this github_release finding)
  - Phase 9 REQ-codegraph-mcp-postinstall (needs this entry as its proving case)

actuals:
  tokens: 4000
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - os-split github_release with checksum=SHA256SUMS and nested member=bin/codegraph strip=1
    - volta-style comment block recording a live-verified no-fallback rung

key-files:
  created: []
  modified:
    - installer/registry.toml
    - tests/test_registry.py

key-decisions:
  - "codegraph is github_release only; no node, script, or brew method"
  - "No Homebrew formula exists as of 2026-09-05, so a checksum mismatch is terminal (checksum_policy=fail, no second rung)"
  - "ai-tier tripwire moved 9 -> 10 in the same commit as the entry; plan 05-03 moves user 35 -> 36 next"

patterns-established:
  - "A github_release-only ladder with no brew fallback must record that absence as a decision, not an oversight"
  - "test_registry_tier_distribution_is_pinned moves in the commit that earns the count"

requirements-completed:
  - REQ-codegraph-github-release

coverage:
  - id: D1
    description: "codegraph is a checksum-verified github_release catalog tool that resolves exactly one method on macOS and every supported Linux distro, amd64 and arm64, with no npm/pnpm method"
    requirement: REQ-codegraph-github-release
    verification:
      - kind: unit
        ref: tests/test_registry.py#test_codegraph_github_release_is_os_split_checksum_verified_and_nested
        status: pass
      - kind: unit
        ref: tests/test_registry.py#test_codegraph_methods_are_github_release_only
        status: pass
    human_judgment: false
  - id: D2
    description: "Registry comment records the v1.6.0 live verification, SHA256SUMS, strip=1 layout, and that there is no Homebrew formula"
    requirement: REQ-codegraph-github-release
    verification:
      - kind: unit
        ref: tests/test_registry.py#test_codegraph_entry_records_the_no_brew_formula_finding
        status: pass
    human_judgment: false
  - id: D3
    description: "Catalog ai-tier tripwire moved from 9 to 10 in the same commit as the entry"
    requirement: REQ-codegraph-github-release
    verification:
      - kind: unit
        ref: tests/test_registry.py#test_registry_tier_distribution_is_pinned
        status: pass
    human_judgment: false

duration: 11 min
completed: 2026-09-05
status: complete
---

# Phase 05 Plan 02: codegraph github_release entry Summary

**`codegraph` is a checksum-verified `kind="github_release"` catalog tool (os-split darwin/linux tarballs, `SHA256SUMS`, nested `bin/codegraph`) with no npm/pnpm/brew rung.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-09-05T23:11:36Z
- **Completed:** 2026-09-05T23:22:48Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `codegraph` loads as `tier="ai"`, `audience="ai"`, `category="dev"`, `cmd="codegraph"`, `priority="P1"`, with exactly two `kind="github_release"` methods and no `requires`/`recommends`.
- macOS resolves `codegraph-darwin-{arch.x64}.tar.gz`; debian/arch/fedora (including immutable, no-brew) resolve `codegraph-linux-{arch.x64}.tar.gz`. Every method has `repo="colbymchenry/codegraph"`, `checksum="SHA256SUMS"`, `member="bin/codegraph"`, `strip=1`.
- The v1.6.0 live GitHub-API verification, tarball layout, and no-Homebrew-formula finding are recorded on the entry; dropping `v1.6.0` from the registry text fails a test.
- `test_registry_tier_distribution_is_pinned` moved `ai` from 9 to 10 in the same commit as the entry. Plan 05-03 moves `user` from 35 to 36 next — do not reorder those two plans.

## Task Commits

1. **Task 1: `codegraph` as a checksum-verified github_release entry, with the tier tripwire updated** - `814edbc` (feat)
2. **Task 2: Record what was verified, and that this ladder has no second rung** - `13c327e` (feat)

## Files Created/Modified

- `installer/registry.toml` - `[[tool]] id = "codegraph"` after `opencode` and before `deno`, plus the v1.6.0 verification comment
- `tests/test_registry.py` - resolution/kind/id-set cases, no-brew-formula record guard, ai-tier pin 9 -> 10

## Exact fields and methods

Tool-level: `id = "codegraph"`, `name = "CodeGraph"`, `category = "dev"`, `cmd = "codegraph"`, `priority = "P1"`, `audience = "ai"`, `tier = "ai"`, `desc = "Local code-intelligence knowledge graph CLI and MCP server; ships its own Node runtime"`. No `requires`, no `recommends`.

Methods (declared order):

1. `os = ["macos"]`, `kind = "github_release"`, `repo = "colbymchenry/codegraph"`, `asset = "codegraph-darwin-{arch.x64}.tar.gz"`, `checksum = "SHA256SUMS"`, `member = "bin/codegraph"`, `strip = 1`
2. `os = ["debian", "arch", "fedora"]`, `kind = "github_release"`, `repo = "colbymchenry/codegraph"`, `asset = "codegraph-linux-{arch.x64}.tar.gz"`, `checksum = "SHA256SUMS"`, `member = "bin/codegraph"`, `strip = 1`

Live-verified 2026-09-05 against tag `v1.6.0` via `repos/colbymchenry/codegraph/releases/latest`: `codegraph-darwin-arm64.tar.gz`, `codegraph-darwin-x64.tar.gz`, `codegraph-linux-arm64.tar.gz`, `codegraph-linux-x64.tar.gz`, and `SHA256SUMS` in `<hash>  <filename>` form.

Tarball top level is `codegraph-<os>-<arch>/` containing `bin/codegraph`, a sibling vendored `node`, and `lib/` — that is why `strip = 1` plus `member = "bin/codegraph"` unpacks into `~/.local/opt/codegraph/` and symlinks `~/.local/bin/codegraph` at the extracted launcher.

There is no Homebrew formula for this tool as of 2026-09-05, so `github_release` is the only rung. A checksum mismatch or network failure has no fallback. `installer/engine.py`'s default `checksum_policy="fail"` makes a mismatch terminal by design.

**Out of scope:** codegraph's MCP postinstall registration belongs to Phase 9 (`REQ-codegraph-mcp-postinstall`). This plan does not add it.

## Decisions Made

- Followed the plan: github_release-only ladder, no brew invented, no Phase 8 `recommends` pre-emption, no Phase 9 postinstall.
- Comment wording uses "there is no Homebrew formula" so the case-sensitive acceptance grep `no Homebrew formula` matches.

## Deviations from Plan

None - plan executed exactly as written.

**Total deviations:** 0
**Impact:** none

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 05-03. That plan must update `test_registry_tier_distribution_is_pinned`'s `user` count from 35 to 36 in the commit that adds its entry; the `ai` count is already 10. Phase 8 can inherit the github_release finding. Phase 9 still needs the postinstall mechanism.

## Self-Check: PASSED

- `installer/registry.toml` and `tests/test_registry.py` exist with the codegraph entry and tests
- `git log --oneline --all --grep="05-02"` returns `814edbc` and `13c327e`
- `uv run pytest tests/test_registry.py -x -q` passed
- All Task 1 and Task 2 `<acceptance_criteria>` passed, including the python one-liners, asset greps, `codegraph not in MACOS_ONLY`, SHA256SUMS count >= 5, and `no Homebrew formula`
- `make validate` and `make test` passed on the Task 2 tree
- No real package install or shell-config edit was performed against this machine

---
*Phase: 05-registry-method-corrections-codegraph-mmdc-puppeteer*
*Completed: 2026-09-05*
