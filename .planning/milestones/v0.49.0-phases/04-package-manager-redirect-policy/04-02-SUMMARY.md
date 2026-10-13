---
phase: 04-package-manager-redirect-policy
plan: 02
subsystem: catalog
tags: [volta, registry.toml, system-tier, npm-postinstall, D-07]

requires:
  - phase: 01-catalog-tier-foundation
    provides: Tool.tier, load_tools validation, resolve_methods
provides:
  - installer/registry.toml [[tool]] id = "volta" as tier=system
  - ~/.volta/bin declared on both volta methods
  - D-07 volta-shells-out-to-npm finding recorded on the entry
affects:
  - 04-03 argv-conditional npm/pnpm wrappers (redirect target must be installable)
  - 04-04 doctor UI copy (consumes the recorded tradeoff)

actuals:
  tokens: 1900
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - catalog entry comments record verified caveats beside the methods they constrain
    - bin_dir declared on every method that should contribute a managed PATH dir

key-files:
  created: []
  modified:
    - installer/registry.toml
    - tests/test_registry.py

key-decisions:
  - "D-06/R-02: volta is a tier=system catalog tool so the global-install redirect has an installable target"
  - "D-07: volta install runs npm install --global with install scripts ungated — recorded on the entry, not assumed safe"
  - "No macOS script fallback: brew-only on macOS; a Mac without Homebrew cannot install volta (04-03 fails safe)"
  - "~/.volta/bin is declared on both methods; collect_bin_dirs still requires the directory to exist"

patterns-established:
  - "Record source-verified security findings as TOML comments on the catalog entry they describe"
  - "Declare bin_dir on every method of a tool whose installed CLIs live in a fixed shim dir, including brew"

requirements-completed:
  - REQ-npm-global-volta-redirect

coverage:
  - id: D1
    description: "volta is a browsable system-tier catalog tool that resolves brew first on macOS and the official install script first on Linux, with ~/.volta/bin on both methods"
    requirement: REQ-npm-global-volta-redirect
    verification:
      - kind: unit
        ref: tests/test_registry.py#test_volta_resolves_to_script_on_linux_and_brew_on_macos
        status: pass
      - kind: unit
        ref: tests/test_registry.py#test_registry_includes_requested_installable_entries
        status: pass
      - kind: unit
        ref: tests/test_registry.py#test_every_tool_resolves_at_least_one_method_on_each_platform
        status: pass
    human_judgment: false
  - id: D2
    description: "The registry records that volta install runs npm install --global via run_global_install with install scripts ungated, and a test fails if that record is dropped"
    requirement: REQ-npm-global-volta-redirect
    verification:
      - kind: unit
        ref: tests/test_registry.py#test_volta_entry_records_the_npm_postinstall_finding
        status: pass
    human_judgment: false

duration: 10min
completed: 2026-09-05
status: complete
---

# Phase 4 Plan 02: volta system-tier catalog entry Summary

**Volta is a `tier="system"` catalog tool (Linux script + macOS brew) with `~/.volta/bin` on both methods and the source-verified npm-postinstall finding recorded on the entry.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-09-05T13:37:47Z
- **Completed:** 2026-09-05T13:48:23Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `volta` loads as `tier="system"`, `category="pkg-mgr"`, `cmd="volta"`, `audience="both"`.
- Methods, in declared order: `kind="script"` `os=["debian","arch","fedora"]` `url="https://get.volta.sh"` `shell="bash"` `bin_dir="~/.volta/bin"`; then `kind="brew"` `formula="volta"` `bin_dir="~/.volta/bin"`.
- `bin_dir` is on both methods because volta places shims for every CLI it installs in `~/.volta/bin` regardless of how volta itself was installed — a brew-only `bin_dir` would leave macOS volta-installed globals off PATH.
- D-07 finding is committed on the entry (see below) and guarded by `test_volta_entry_records_the_npm_postinstall_finding`.

## Exact methods declared

1. Script (Linux): `https://get.volta.sh` via bash — Volta's published getting-started path. `resolve_methods` returns this first on debian/arch/fedora.
2. Brew (macOS and as Linux fallback when brew is present): formula `volta`, confirmed in homebrew-core. `resolve_methods` returns this first on macOS.

No `requires` list — volta bundles its own Node toolchain; brew is not declared as a dependency, matching `uv`/`pnpm`.

## D-07 finding as committed

```
volta install <pkg> runs a real `npm install --global --loglevel=warn
--no-update-notifier --no-audit <pkg>` subprocess, with no flag that disables
install scripts — verified by reading Volta's own source,
crates/volta-core/src/tool/package/install.rs, function run_global_install
(github.com/volta-cli/volta, fetched 2026-09-05).
Consequence: anything installed through volta runs npm's preinstall/install/
postinstall scripts unrestricted, which pnpm has gated behind an opt-in
allowlist since pnpm v10 (pnpm.io/supply-chain-security). Routing global
installs to volta is therefore a security-for-stability tradeoff the user
accepted in D-06/D-08 to fix pnpm's global-package loss on self-update —
it is not a clean win.
Version caveat: npm v12 flips install scripts to opt-in
(github.blog/changelog/2026-06-09-upcoming-breaking-changes-for-npm-v12/).
The finding above holds for the npm versions Volta pins today and should be
re-verified with `volta run --node <pinned-version> npm --version` if this
entry is revisited after 2026-10-05.
```

## Recorded limits

1. **No macOS script fallback.** Brew only on macOS. A Mac with no Homebrew cannot install the redirect target. Plan 04-03 gates the redirect on volta resolving, so that machine keeps today's npm hard block. Remedy: install `brew`. Do not invent an unpublished macOS script URL.
2. **`~/.volta/bin` may not exist yet right after installing volta.** `collect_bin_dirs` adds a declared `bin_dir` only when the directory already exists (`require_exists=True`). A brew-installed volta may not create its shim dir until the first `volta install` or `volta setup`. PATH repair is then a second step (`make fix` / Doctor apply). Not special-cased — changing `require_exists` would wire non-existent directories into PATH for every catalog tool.

## Task Commits

1. **Task 1: volta as a system-tier catalog entry** - `b9b1a25d7969dedb391d813e20810ddf82ba98f5` (feat)
2. **Task 2: Record the Volta-shells-out-to-npm finding on the entry** - `e7451ebd006b1579752d0989d875b445200113fb` (feat)

## Files Created/Modified

- `installer/registry.toml` — `[[tool]] id = "volta"` after pnpm, with D-07 comment block and the two recorded limits
- `tests/test_registry.py` — requested-entries set, per-platform resolution + `bin_dir`, finding-not-dropped guard, system-tier pin 21 → 22

## Decisions Made

Followed the plan: D-06, D-07, D-08, R-02. No unpublished macOS script URL. `desc` stays the one-line catalog label; the finding lives in the TOML comment (and later in 04-04 doctor copy).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Bump pinned system-tier count**
- **Found during:** Task 1 (volta catalog entry)
- **Issue:** `test_registry_tier_distribution_is_pinned` pins `system: 21` and requires any catalog add to update the count in the same commit.
- **Fix:** `"system": 21` → `"system": 22`.
- **Files modified:** `tests/test_registry.py`
- **Verification:** `uv run pytest tests/test_registry.py -x -q` exits 0.
- **Committed in:** `b9b1a25d7969dedb391d813e20810ddf82ba98f5` (Task 1)

**2. [project rule] One commit per task, no RED-only commit**
- **Found during:** Task 1 (tdd="true")
- **Issue:** GSD TDD wants a failing-test commit then a green commit. This repo forbids committing a broken tree (`make validate && make test` must pass; one commit per task).
- **Fix:** RED was run uncommitted; GREEN shipped as the Task 1 commit. Task 2 is not TDD.
- **Files modified:** none extra
- **Verification:** Task 1 RED failed (`volta` missing); GREEN + `make validate && make test` passed before commit.
- **Committed in:** `b9b1a25d7969dedb391d813e20810ddf82ba98f5` (Task 1)

---

**Total deviations:** 2 auto-fixed (1 missing-critical pin update, 1 commit-protocol alignment with project gates).
**Impact on plan:** Pin update is the tripwire's intended use. No scope creep. `REQ-npm-global-volta-redirect` stays incomplete until 04-03 (shared ID).

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 04-03: argv-conditional `npm install -g` / `pnpm add -g` → `volta install`, gated on volta resolving. The catalog target and the D-07 record both exist.

## Self-Check: PASSED

`make validate` — ruff, ruff format, pyright 0 errors 0 warnings, bandit, vulture, shellcheck. `make test` — full suite green, coverage floor held. `volta` not in `MACOS_ONLY`. `grep -c 'run_global_install' installer/registry.toml` is 1. `grep -c 'no Homebrew' installer/registry.toml` is 1.

---
*Phase: 04-package-manager-redirect-policy*
*Completed: 2026-09-05*
