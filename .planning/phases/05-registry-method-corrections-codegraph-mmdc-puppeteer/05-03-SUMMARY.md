---
phase: 05-registry-method-corrections-codegraph-mmdc-puppeteer
plan: 03
subsystem: registry
tags: [puppeteer, mmdc, co_install, allow_build, pnpm, arm64]

requires:
  - phase: 05-01
    provides: kind=node co_install/allow_build/versions/min_node/smoke and GROUP_PIN=ok
  - phase: 05-02
    provides: ai-tier tripwire already at 10; this plan moves user 35 -> 36
provides:
  - puppeteer catalog entry with platform-conditional node methods
  - mmdc.requires including puppeteer plus grouped co_install/allow_build/versions/smoke
  - recorded mmdc pnpm decision (brew and Volta rejected)
affects:
  - 05-04 Doctor split-group detection (pending plan 05-04 hand-off line)
  - Phase 8/9 (graphify and codegraph MCP stay out of this phase)

actuals:
  tokens: 9000
  tasks: 3
  commits: 2

tech-stack:
  added: []
  patterns:
    - platform-conditional node methods with arch gate for honest unavailability
    - co_install is invocation-only; Tool.requires remains the sole install ORDER mechanism
    - NO_LINUX_ARM64 allowlist mirrors MACOS_ONLY and cannot hide a stranded tool

key-files:
  created: []
  modified:
    - installer/registry.toml
    - tests/test_registry.py
    - tests/test_node_install_e2e.py
    - tests/test_deps.py
    - .planning/PROJECT.md
    - .planning/REQUIREMENTS.md

key-decisions:
  - "GROUP_PIN=ok: mmdc's node method pins puppeteer@^25 inside the comma group"
  - "cmd=puppeteer from object-form bin key, not a bare-string bin"
  - "Linux arm64 resolves no puppeteer method; mmdc is skipped via existing is_blocked"
  - "Clean two-invocation path ends as ONE pnpm group; Installed twice disposition is closed"
  - "Persistent allow-build grant is package-name keyed and is not bounded by ^25"

patterns-established:
  - "co_install names must be a required catalog tool's npm_pkg"
  - "NO_LINUX_ARM64 membership means the tool cannot work on that platform+arch"

requirements-completed:
  - REQ-mmdc-install-decision
  - REQ-puppeteer-catalog-entries

coverage:
  - id: D1
    description: "puppeteer is a user-tier node catalog tool with identical params on macos (both arches) and Linux amd64, and zero methods on Linux arm64"
    requirement: REQ-puppeteer-catalog-entries
    verification:
      - kind: unit
        ref: tests/test_registry.py#test_puppeteer_is_a_user_tier_node_tool_requiring_pnpm
        status: pass
      - kind: unit
        ref: tests/test_registry.py#test_puppeteer_resolves_no_method_on_linux_arm64_because_chrome_has_no_binary
        status: pass
    human_judgment: false
  - id: D2
    description: "Selecting mmdc drags pnpm then puppeteer then mmdc and emits one grouped, pinned, build-allowed pnpm argv"
    requirement: REQ-puppeteer-catalog-entries
    verification:
      - kind: unit
        ref: tests/test_registry.py#test_selecting_mmdc_drags_in_pnpm_and_puppeteer_on_linux_amd64
        status: pass
      - kind: e2e
        ref: tests/test_node_install_e2e.py#test_installing_mmdc_runs_pnpm_add_global_no_bare_npm
        status: pass
    human_judgment: false
  - id: D3
    description: "No chrome-headless-shell catalog entry; REQUIREMENTS.md amended in place"
    requirement: REQ-puppeteer-catalog-entries
    verification:
      - kind: unit
        ref: tests/test_registry.py#test_no_chrome_headless_shell_catalog_entry
        status: pass
    human_judgment: false
  - id: D4
    description: "mmdc stays on pnpm; brew and Volta rejected with four-criteria reasoning recorded on the entry"
    requirement: REQ-mmdc-install-decision
    verification:
      - kind: unit
        ref: tests/test_registry.py#test_mmdc_entry_records_the_brew_rejection_finding
        status: pass
    human_judgment: false
  - id: D5
    description: "Package identity gate for puppeteer and @mermaid-js/mermaid-cli against live npm metadata"
    requirement: REQ-puppeteer-catalog-entries
    verification:
      - kind: other
        ref: "curl registry.npmjs.org legitimacy gate; stdout LEGITIMACY_OK"
        status: pass
    human_judgment: false
  - id: D6
    description: "Persistent --allow-build grant stated as package-level, not pin-bounded, with revocation path"
    requirement: REQ-puppeteer-catalog-entries
    verification:
      - kind: unit
        ref: tests/test_registry.py#test_puppeteer_entry_states_the_persistent_grant_accurately
        status: pass
    human_judgment: false
  - id: D7
    description: "Brownfield gap, Doctor split-group detection hand-off, group-removal coupling, and measured double-install disposition recorded on the registry"
    requirement: REQ-mmdc-install-decision
    verification:
      - kind: unit
        ref: tests/test_registry.py#test_mmdc_entry_records_the_brownfield_gap_and_group_coupling
        status: pass
      - kind: unit
        ref: tests/test_registry.py#test_puppeteer_entry_records_the_double_install_disposition
        status: pass
    human_judgment: false

duration: 18 min
completed: 2026-09-05
status: complete
---

# Phase 05 Plan 03: puppeteer catalog entry and mmdc wiring Summary

**`puppeteer` is a platform-conditional `kind="node"` catalog tool; selecting `mmdc` drags it in as one grouped, `^25`-pinned, build-allowed pnpm install, with brew and Volta both rejected on recorded research.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-09-05T23:28:28Z
- **Completed:** 2026-09-05T23:46:44Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- `puppeteer` loads as `tier="user"`, `audience="both"`, `category="dev"`, `cmd="puppeteer"`, `priority="P3"`, `requires=("pnpm",)`, with exactly two `kind="node"` methods.
- macOS (amd64 and arm64) and Linux debian/arch/fedora amd64 each resolve exactly one method; Linux arm64 resolves none, and selecting `mmdc` there is skipped with a dependency-unavailable warning.
- Selecting `mmdc` on Linux amd64 yields deps-first order `pnpm`, `puppeteer`, `mmdc` and one `pnpm add -g --allow-build=puppeteer "@mermaid-js/mermaid-cli,puppeteer@^25"` invocation.
- `chrome-headless-shell` has no catalog entry; `REQ-puppeteer-catalog-entries` is amended in place dated 2026-09-05.
- User-tier tripwire moved 35 -> 36 in the same commit as the entry.

## Task Commits

1. **Task 1: Package legitimacy gate** — no commit (no repository files modified; evidence below)
2. **Task 2: puppeteer entry and mmdc wiring** - `4cf9fb0` (feat)
3. **Task 3: method decision and caveats** - `dba96cd` (feat)

## Files Created/Modified

- `installer/registry.toml` - `puppeteer` entry after `mmdc`, mmdc `requires`/`co_install`/`allow_build`/`versions`/`min_node`/`smoke`, decision comment blocks
- `tests/test_registry.py` - entry/resolution/arm64/co_install/tier/text-guard cases; `NO_LINUX_ARM64`
- `tests/test_node_install_e2e.py` - grouped argv through `install_tool` with probe and cache stubs
- `tests/test_deps.py` - real-registry `missing_requires` now includes `puppeteer`
- `.planning/REQUIREMENTS.md` - in-place amendment of `REQ-puppeteer-catalog-entries`
- `.planning/PROJECT.md` - mmdc method-decision row and CONTEXT no-new-mechanisms deviation row

## Package legitimacy evidence (Task 1)

Live `registry.npmjs.org` fetch, 2026-09-05, command exited 0 with `LEGITIMACY_OK`.

### puppeteer

- raw `repository.url`: `git+https://github.com/puppeteer/puppeteer.git#main`
- normalized `owner/repo`: `puppeteer/puppeteer` (equals expected)
- `created`: `2013-03-23T01:44:47.039Z`
- published versions: 1010
- `dist-tags.latest`: `25.10.0`
- latest `dist.integrity`: `sha512-9ZfkiaZDQWpGPJp9XTS+Bkn/D78hPvYmtjPfIBeybn05oeY6Jj7aiSbYdfcSQD2UMvC0vE7Yi9PSDo179euRzw==`
- `pinned_resolved` (`^25`): `25.10.0`
- pinned `dist.integrity`: `sha512-9ZfkiaZDQWpGPJp9XTS+Bkn/D78hPvYmtjPfIBeybn05oeY6Jj7aiSbYdfcSQD2UMvC0vE7Yi9PSDo179euRzw==`
- This `25.10.0` integrity is the artifact the phase reasoned about — the version `pnpm add -g puppeteer@^25` resolves to on the day the gate ran.

Disposition: the `SUS` flag is a `too-new`-heuristic false positive on a long-established, canonically-sourced package, discharged on registry metadata rather than on the researcher's judgement alone.

### @mermaid-js/mermaid-cli

- raw `repository.url`: `git+ssh://git@github.com/mermaid-js/mermaid-cli.git`
- normalized `owner/repo`: `mermaid-js/mermaid-cli` (equals expected)
- `created`: `2020-03-01T18:15:14.009Z`
- published versions: 82
- `dist-tags.latest`: `11.17.0`
- latest `dist.integrity`: `sha512-pxF8rmheBb1gabIN4GFDCNWzIUsOzcEsSp7H5CQoL7gv7X8U8r6FFKtdMzEmZMeHmziNAq2B7J7LG+CDSfIg9w==`

Disposition: the `SUS` flag is a `too-new`-heuristic false positive on a long-established, canonically-sourced package, discharged on registry metadata rather than on the researcher's judgement alone.

### What this gate establishes and does not

This gate establishes IDENTITY AND OWNERSHIP ONLY: this package name is published from the canonical upstream repository, and it is a long-established package with a real version history rather than a freshly published look-alike. That is the property the `SUS` flag put in question, and it is fully discharged here.

It is NOT an artifact-integrity approval. It does not authenticate the tarball `pnpm add -g` will download and execute. Repository URL, age and version count are all metadata the publisher controls, and none of them is a signature over artifact bytes. The two integrity values recorded above are a POINT-IN-TIME RECORD, not an approval and not a control: `^25` is a mutable range, so a later install legitimately resolves to a version published after this gate ran, whose bytes this evidence says nothing about. The record's only purpose is forensic — it makes the exact artifact this phase reasoned about identifiable after the fact. The stronger control is npm provenance / pinning installs to an exact `dist.integrity`; it is deliberately NOT adopted, because it freezes puppeteer at one build with no security-update path, and the residual gap is carried as T-05-20 rather than silently closed.

### Persistent build-allowance grant

`puppeteer` is the one package whose postinstall this phase un-gates (`--allow-build=puppeteer`). pnpm records that grant persistently against the package NAME with no version qualifier (`allowBuilds: puppeteer: true` in `pnpm-workspace.yaml`). The `^25` pin therefore does NOT bound it: that pin constrains only the argv this project generates (catalog install and Doctor replay). The grant authorises the postinstall of ANY `puppeteer` version that pnpm ever installs on that machine, including versions installed by commands this project never issues. Revocation: remove the package's entry from pnpm's build-allowance configuration — plan 05-01 recorded the file as `/root/.local/share/pnpm/global/v11/pnpm-workspace.yaml`; on a user machine it is the same `pnpm-workspace.yaml` under the global store. Removing that entry re-gates the package.

## Exact fields and methods

### puppeteer

Tool-level: `id = "puppeteer"`, `name = "Puppeteer"`, `category = "dev"`, `cmd = "puppeteer"`, `priority = "P3"`, `audience = "both"`, `tier = "user"`, `requires = ["pnpm"]`, `desc = "Headless-Chrome automation library; downloads its own Chrome and chrome-headless-shell. Required at runtime by mmdc."`

- `cmd = "puppeteer"`: live registry metadata shows `bin` is an OBJECT whose single key is `puppeteer` and whose value is `lib/puppeteer/node/cli.js`. pnpm links an object-form `bin` under each KEY, so `puppeteer` lands on PATH after a global install and `installer/status.py::is_installed`'s `shutil.which` check works with no `detect_path` fallback.
- `tier = "user"`: exists to serve `mmdc`, a user-tier diagram tool; `tier` is a browsing label only.
- `priority = "P3"`: nobody picks puppeteer for its own sake; `requires` still orders it before `mmdc`.

Methods (identical params, different scope):

1. `os = ["macos"]`, no arch key
2. `os = ["debian", "arch", "fedora"]`, `arch = ["amd64"]`

Params on each: `npm_pkg = "puppeteer"`, `allow_build = ["puppeteer"]`, `versions = { puppeteer = "^25" }`, `min_node = "22.12.0"`, `smoke = "puppeteer-browser"`. No `co_install`.

`min_node = "22.12.0"` is puppeteer 25's `engines.node` floor. `smoke = "puppeteer-browser"` runs the downloaded browser after pnpm exits 0 so a Linux amd64 machine missing shared libraries is told FAILED. The `^25` pin is a COMPATIBILITY control keeping mmdc and puppeteer inside the peer range `^23 || ^24 || ^25`; it does not bound the persistent build-allowance grant.

Linux arm64 resolves to nothing because Chrome publishes no Linux arm64 binary. `installer/deps.py::is_blocked` then skips `mmdc` with a warning. The gate does not cover a Linux arm64 machine that ALREADY has a standalone `mmdc`: `is_blocked` treats `is_installed()` as satisfied, so no skip warning is emitted there.

### mmdc (amended)

`requires = ["pnpm", "puppeteer"]`. Node method stays unscoped and gains `co_install = ["puppeteer"]`, `allow_build = ["puppeteer"]`, `min_node = "22.12.0"`, `smoke = "puppeteer-browser"`, `versions = { puppeteer = "^25" }`. `npm_pkg` unchanged.

Version-pin branch taken: **`GROUP_PIN=ok`** (verbatim from 05-01-SUMMARY: `GROUP_PIN=ok`. `pnpm add -g "<pkg-a>,<pkg-b>@<range>"` accepted a version specifier inside a comma group; the group resolved puppeteer to **25.10.0**).

### Resolved order

- Linux amd64, nothing installed, select `mmdc`: order ids `pnpm`, `puppeteer`, `mmdc` (relative); `dragged_in` contains both `pnpm` and `puppeteer`.
- Linux arm64, nothing installed, select `mmdc`: order contains neither `mmdc` nor `puppeteer`; warning names an unavailable dependency.

## D-01 / D-02 decision (as committed)

`mmdc` stays on pnpm (`kind="node"`). Homebrew is rejected because upstream mermaid-cli's README states that path is "no longer supported", and GitHub issue #1122 (closed "not planned") records brew-installed mmdc failing at runtime because the formula depends only on `node`. Formula version currency (`11.17.0`, matching npm) was never the failure mode. Volta is rejected by reusing this registry's own volta comment: `volta install` runs ungated `npm install --global`, and mermaid-cli has no lifecycle scripts of its own, so the tradeoff buys nothing while giving up pnpm's default-deny gate for puppeteer's postinstall.

Four criteria: stability (brew is a reproducing breakage); security (scoped `--allow-build=puppeteer` versus Volta's blanket execution); simplicity (no migration); maintainability (one manager, one install group).

## chrome-headless-shell

No separate entry: puppeteer's `postinstall` (`node install.mjs`) downloads both Chrome for Testing and `chrome-headless-shell` into `~/.cache/puppeteer`. `.planning/REQUIREMENTS.md` `REQ-puppeteer-catalog-entries` was amended in place dated 2026-09-05; a test asserts no such id exists.

## Brownfield, double-install, group coupling

- **Brownfield:** `install_tool` returns `ALREADY_INSTALLED` before `resolve_methods`, so a pre-existing standalone `mmdc` never reaches the grouped invocation. Tier-3 measured `BROWNFIELD_BEFORE=ok` on pnpm 12.3.4. Remedy: Doctor `r` after plan 05-04. Manual alternative: `pnpm remove -g @mermaid-js/mermaid-cli` then catalog-install `mmdc`. Committed hand-off line: `Doctor split-group detection: pending plan 05-04`. Automatic repair at install time is out of scope.
- **Installed twice:** tracer measured ONE group after invocation B (shared path hash `1525-...`, CACHE_BEFORE_B and CACHE_AFTER_B both 652M). No redundancy exists on this pnpm. Disposition: closed.
- **Group coupling:** `pnpm remove -g` of either member removes the whole group. This installer never performs that removal (`uninstall.py` classifies node tools as externally managed).

## Decisions Made

- Followed the plan: `GROUP_PIN=ok` branch, versions on mmdc, no `chrome-headless-shell` entry, Linux arm64 arch gate, user-tier 36.
- `cmd` rationale uses the object-form `bin` key, not the retracted bare-string claim.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Real-registry missing_requires assertion**
- **Found during:** Task 2
- **Issue:** `tests/test_deps.py::test_missing_requires_matches_the_real_registry_cross_tier_edge` asserted `missing_requires(mmdc) == ("pnpm",)`. Adding `puppeteer` to `mmdc.requires` made the tuple `("pnpm", "puppeteer")`.
- **Fix:** Updated the assertion to the new two-element tuple. Cross-tier pnpm edge is still asserted.
- **Files modified:** `tests/test_deps.py`
- **Verification:** `uv run pytest tests/test_deps.py` passed
- **Committed in:** `4cf9fb0` (Task 2)

---

**Total deviations:** 1 auto-fixed (missing-critical).
**Impact on plan:** None. Required for the plan's own `tests/test_deps.py` verify command.

## Issues Encountered

None that blocked production tasks.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 05-04. That plan must replace `pending plan 05-04` on the `Doctor split-group detection:` line with the truth about what surfaces split groups to a user, and must not move the user-tier tripwire (already 36). `REQ-puppeteer-catalog-entries` stays Pending in REQUIREMENTS.md until 05-04 also finishes (shared-ID gate).

## Self-Check: PASSED

- `installer/registry.toml`, `tests/test_registry.py`, `tests/test_node_install_e2e.py` exist with the puppeteer entry and tests
- `git log --oneline --all --grep="05-03"` returns `4cf9fb0` and `dba96cd`
- Task 1 live gate printed `LEGITIMACY_OK`; both `normalized_repo=` values equal `expected_repo=`
- All Task 2 and Task 3 `<acceptance_criteria>` passed, including python one-liners, greps, `GROUP_PIN=ok` branch, and `make validate` / `make test`
- No real package install or shell-config edit was performed against this machine

---
*Phase: 05-registry-method-corrections-codegraph-mmdc-puppeteer*
*Completed: 2026-09-05*
