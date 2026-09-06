---
phase: 05-registry-method-corrections-codegraph-mmdc-puppeteer
plan: 01
subsystem: executor
tags: [co_install, allow_build, versions, min_node, smoke, pnpm, puppeteer, mmdc]

requires:
  - phase: 04-package-manager-redirect-policy
    provides: real_pnpm absolute-path resolver so argv[0] cannot hit the volta wrapper
provides:
  - kind=node co_install / allow_build / versions / min_node / smoke params
  - comma-joined pnpm add -g argv builder
  - fail-closed pnpm/node version preflight
  - puppeteer-browser post-install smoke check
  - Tier-3 GROUP_PIN / SPLIT_STATE_JSON / GROUPED_STATE_JSON / LIBCHECK evidence
affects:
  - 05-03 registry data (GROUP_PIN=ok, double-install as one group, Linux limitations)
  - 05-04 Doctor split-group detector (SPLIT vs GROUPED JSON fixtures)

actuals:
  tokens: 18000
  tasks: 4
  commits: 3

tech-stack:
  added: []
  patterns:
    - additive optional node-method params; no-params argv is byte-identical
    - tolerant parse_version for observed --version; strict parse_declared_version for registry floors
    - probe_version is the single injectable runtime-version seam
    - smoke selects a closed code-owned check by name, never a command

key-files:
  created: []
  modified:
    - installer/model.py
    - installer/executors.py
    - installer/versions.py
    - tests/test_model.py
    - tests/test_executors.py
    - tests/test_versions.py
    - .claude/architecture.md

key-decisions:
  - "GROUP_PIN=ok: pnpm 12.3.4 accepts name@range inside a comma group; the group resolved puppeteer 25.10.0"
  - "Clean two-invocation path ends as ONE pnpm group; invocation A's standalone puppeteer is replaced by invocation B's grouped pair"
  - "pnpm list -g --json reports ONE project object; group membership is the per-package path hash, not multiple project objects"
  - "allowBuilds persists as package NAME only (puppeteer: true) with no version qualifier"
  - "BROWNFIELD_BEFORE=ok on this pnpm: autoInstallPeers plus a later allow-build puppeteer install still rendered; SPLIT vs GROUPED path hashes still differ"
  - "LIBCHECK=fail on node:24-bookworm-slim without chromium: install exit 0, chrome-headless-shell cannot load libglib-2.0.so.0"
  - "co_install still ships: autoInstallPeers is user-settable and does not run --allow-build"

patterns-established:
  - "co_install shapes the pnpm INVOCATION only; Tool.requires remains the sole install ORDER mechanism"
  - "allow_build may only name packages the same invocation installs; the grant pnpm records is persistent and package-level, not bounded by ^25"

requirements-completed:
  - REQ-puppeteer-catalog-entries

coverage:
  - id: D1
    description: "kind=node can declare co_install/allow_build/versions and emit one comma-joined pnpm add -g"
    requirement: REQ-puppeteer-catalog-entries
    verification:
      - kind: unit
        ref: tests/test_executors.py#test_node_grouped_pinned_allowed_argv
        status: pass
      - kind: unit
        ref: tests/test_executors.py#test_node_runs_pnpm_add_global_never_bare_npm
        status: pass
    human_judgment: false
  - id: D2
    description: "load_tools rejects malformed co_install/allow_build/versions/min_node/smoke and out-of-group names"
    requirement: REQ-puppeteer-catalog-entries
    verification:
      - kind: unit
        ref: tests/test_model.py#test_node_method_rejects_allow_build_outside_install_group
        status: pass
      - kind: unit
        ref: tests/test_model.py#test_node_method_rejects_min_node_malformed_floor
        status: pass
    human_judgment: false
  - id: D3
    description: "Fail-closed pnpm/node version preflight; no probe on params-free node methods"
    requirement: REQ-puppeteer-catalog-entries
    verification:
      - kind: unit
        ref: tests/test_executors.py#test_node_co_install_refuses_pnpm_10
        status: pass
      - kind: unit
        ref: tests/test_executors.py#test_node_without_new_params_performs_zero_probes
        status: pass
    human_judgment: false
  - id: D4
    description: "smoke=puppeteer-browser fails the install when the browser is missing or cannot start"
    requirement: REQ-puppeteer-catalog-entries
    verification:
      - kind: unit
        ref: tests/test_executors.py#test_smoke_puppeteer_browser_fails_when_browser_cannot_start
        status: pass
      - kind: unit
        ref: tests/test_executors.py#test_smoke_puppeteer_browser_fails_when_cache_empty
        status: pass
      - kind: e2e
        ref: docker run --rm node:24-bookworm-slim Container D LIBCHECK=fail
        status: pass
    human_judgment: false
  - id: D5
    description: "Tier-3 clean install renders SVG via the two-invocation sequence; brownfield remedy renders"
    requirement: REQ-puppeteer-catalog-entries
    verification:
      - kind: e2e
        ref: docker run --rm node:24-bookworm-slim Container A TRACER_RENDER_OK
        status: pass
      - kind: e2e
        ref: docker run --rm node:24-bookworm-slim Container C TRACER_BROWNFIELD_OK
        status: pass
    human_judgment: false

duration: 55 min
completed: 2026-09-05
status: complete
---

# Phase 05 Plan 01: Node co-install mechanism Summary

**kind=node gained co_install/allow_build/versions/min_node/smoke, a fail-closed pnpm/node preflight, and a puppeteer-browser smoke check; a real mmdc rendered SVG inside colima after the exact two-invocation sequence.**

## Performance

- **Duration:** 55 min
- **Started:** 2026-09-05T22:10:37Z
- **Completed:** 2026-09-05T23:05:44Z
- **Tasks:** 4
- **Files modified:** 7

## Accomplishments

- A `kind="node"` method can declare `co_install`, `allow_build`, `versions`, `min_node`, and `smoke`; `_node` emits one `pnpm add -g` with a comma-joined group and per-package `--allow-build` flags.
- Load-time validation rejects malformed lists/tables, commas inside names, out-of-group `allow_build`/`versions`, a non-concrete `min_node`, and an unknown `smoke` name.
- Fail-closed preflight refuses co-install below pnpm 11.0.0, allow-build below pnpm 10.4.0, and a declared `min_node` on an older node. Params-free methods spawn zero probes and keep today's argv.
- `smoke = "puppeteer-browser"` runs the downloaded browser after a zero-exit install and raises `ExecutorError` (FAILED outcome) when it is missing or cannot start.
- Tier-3 containers proved the clean render (`TRACER_RENDER_OK`), the brownfield remedy (`TRACER_BROWNFIELD_OK`), and the missing-shared-library false-success (`TRACER_LIBCHECK_DONE`, `LIBCHECK=fail`).

## Task Commits

1. **Task 1: End-to-end proof** — no commit (no repository files modified; evidence below)
2. **Task 2: Version helpers and load-time validation** - `60ab748` (feat)
3. **Task 3: Grouped argv builder** - `cce3478` (feat)
4. **Task 4: Version preflight and browser smoke check** - `1a903fa` (feat)

## Files Created/Modified

- `installer/versions.py` - `parse_version`, `parse_declared_version`, `meets_minimum`, `probe_version`, pnpm floors
- `installer/model.py` - `_parse_pkg_list`, `_parse_version_map`, `SMOKE_CHECK_NAMES`, node-branch validation
- `installer/executors.py` - grouped argv, preflight, `SMOKE_CHECKS` / `_smoke_puppeteer_browser`
- `tests/test_versions.py`, `tests/test_model.py`, `tests/test_executors.py` - matching cases
- `.claude/architecture.md` - `co_install` is not an ordering mechanism

## Decisions Made

- `GROUP_PIN=ok`: `pnpm add -g "<pkg-a>,<pkg-b>@<range>"` accepted a version specifier inside a comma group on pnpm 12.3.4; the group resolved puppeteer to 25.10.0. Plan 05-03 Task 2 puts the pin on `mmdc`'s method.
- Invocation A's standalone puppeteer and invocation B's grouped puppeteer ended up as ONE group: after B, both packages share path hash `1525-...` and A's standalone hash is gone from `pnpm list -g --json`. `CACHE_BEFORE_B` and `CACHE_AFTER_B` were both 652M with the same `chrome` / `chrome-headless-shell` `linux-152.0.7977.75` listings — the second install did not re-download a browser.
- `pnpm list -g --json` reports ONE global project object. Split-group membership is the per-package `path` hash, not multiple project objects. Plan 05-04 Task 3 STEP 0 must detect split via those hashes.
- The `--allow-build` grant is persisted as package NAME only. `^25` does not bound it.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] pnpm 12 binary lives in `$PNPM_HOME/bin`**
- **Found during:** Task 1
- **Issue:** The plan prepended `$PNPM_HOME` to PATH; pnpm 12.3.4's installer writes `PATH="$PNPM_HOME/bin:$PATH"`.
- **Fix:** Tracer scripts used `$PNPM_HOME/bin`.
- **Verification:** `pnpm --version` printed 12.3.4.
- **Committed in:** n/a (tracer only)

**2. [Rule 2 - Missing Critical] puppeteer 25 needs `unzip` to extract Chrome**
- **Found during:** Task 1
- **Issue:** `node:24-bookworm-slim` has no zip archiver; postinstall failed with "no zip archiver is available. Install `unzip`" while pnpm still exited 0 and left a 20K empty cache.
- **Fix:** Added `unzip` to the container apt-get line (chromium still used as the shared-library provisioner in A/B/C and omitted in D).
- **Verification:** Cache grew to 652M; `chrome-headless-shell` binary present.
- **Committed in:** n/a (tracer only)

**3. [Rule 3 - Blocking] pnpm install.sh requires `ENV` in a slim image**
- **Found during:** Task 1
- **Issue:** `ERR_PNPM_NO_SHELL_CONFIG` when `ENV` is unset.
- **Fix:** `touch /root/.profile; ENV=/root/.profile` before piping the catalog install script.
- **Verification:** pnpm installed to `/root/.local/share/pnpm/bin/pnpm`.
- **Committed in:** n/a (tracer only)

---

**Total deviations:** 3 auto-fixed (2 missing-critical, 1 blocking), all tracer-only.
**Impact on plan:** None on production code. Tracer still used `node:24-bookworm-slim`, the catalog pnpm install script, and puppeteer's own downloaded browser.

## Issues Encountered

None that blocked production tasks. `BROWNFIELD_BEFORE=ok` is recorded DATA, not a failure.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 05-02. Plan 05-03 Task 2 reads `GROUP_PIN=ok` and pins `puppeteer@^25` inside the comma group. Plan 05-03 Task 3 reads the one-group / 652M-unchanged-cache finding. Plan 05-04 Task 3 writes its detector against the SPLIT and GROUPED JSON documents below.

---

## Tier-3 evidence (ONESHOT-RULES Rule 14)

Observed toolchain (every container): **pnpm 12.3.4**, **node v24.20.0**.
Distro `chromium` was the shared-library provisioner in Containers A/B/C and was deliberately omitted in Container D. `unzip` was added so puppeteer's postinstall could extract Chrome (see deviations).

### Invocations (verbatim)

- A: `pnpm add -g --allow-build=puppeteer puppeteer@^25`
- B: `pnpm add -g --allow-build=puppeteer "@mermaid-js/mermaid-cli,puppeteer@^25"`
- Control: `pnpm add -g @mermaid-js/mermaid-cli`
- Brownfield standalone: `pnpm add -g @mermaid-js/mermaid-cli` then `pnpm add -g --allow-build=puppeteer puppeteer@^25`
- Brownfield remedy: `pnpm add -g --allow-build=puppeteer "@mermaid-js/mermaid-cli,puppeteer@^25"`

### GROUP_PIN

`GROUP_PIN=ok`. `pnpm add -g "<pkg-a>,<pkg-b>@<range>"` accepted a version specifier inside a comma group; the group resolved puppeteer to **25.10.0**.

### Cache around invocation B

```
CACHE_BEFORE_B
chrome
chrome-headless-shell
/root/.cache/puppeteer/chrome: linux-152.0.7977.75
/root/.cache/puppeteer/chrome-headless-shell: linux-152.0.7977.75
652M	/root/.cache/puppeteer

CACHE_AFTER_B
(same listings)
652M	/root/.cache/puppeteer
```

### Clean-state `pnpm list -g --json` (Container A)

Count of global project objects: **1**. Packages: `@mermaid-js/mermaid-cli@11.17.0` (hash `1525-...`), `@pnpm/exe@12.3.4` (hash `14d6-...`), `puppeteer@25.10.0` (hash `1525-...`). mermaid-cli and puppeteer share one group; `@pnpm/exe` is pnpm's own install. The `puppeteer` shim on PATH is `$PNPM_HOME/bin/puppeteer`.

```json
[
  {
    "path": "/root/.local/share/pnpm/global/v11",
    "private": true,
    "dependencies": {
      "@mermaid-js/mermaid-cli": {
        "from": "@mermaid-js/mermaid-cli",
        "version": "11.17.0",
        "path": "/root/.local/share/pnpm/global/v11/1525-18d28d7e5d48e5a8-0/node_modules/@mermaid-js/mermaid-cli"
      },
      "@pnpm/exe": {
        "from": "@pnpm/exe",
        "version": "12.3.4",
        "path": "/root/.local/share/pnpm/global/v11/14d6-18d28d4d10f8bf8e-0/node_modules/@pnpm/exe"
      },
      "puppeteer": {
        "from": "puppeteer",
        "version": "25.10.0",
        "path": "/root/.local/share/pnpm/global/v11/1525-18d28d7e5d48e5a8-0/node_modules/puppeteer"
      }
    }
  }
]
```

### Lifecycle

- `LIFECYCLE_RERUN=ok` (grouped invocation a second time, then render still worked)
- `LIFECYCLE_REMOVE=mmdc-broken` (`pnpm remove -g puppeteer` also removed `@mermaid-js/mermaid-cli`; `mmdc: not found`). pnpm's documented "removed together" behaviour is confirmed.

`pnpm list -g` after removal:

```
/root/.local/share/pnpm/global/v11 (PRIVATE)
└── @pnpm/exe@12.3.4
```

### Build-allowance persistence

File: `/root/.local/share/pnpm/global/v11/pnpm-workspace.yaml`

```
allowBuilds:
  puppeteer: true
```

The record carries **only the package name**, no version qualifier. The `^25` pin does not bound the grant.

### Control (Container B)

`CONTROL_INSTALL_EXIT=0`. pnpm printed `Ignored build scripts: puppeteer@25.10.0`.
`CONTROL_RENDER_EXIT=1` / `CONTROL_RENDER=fail`:

```
Error: Could not find chrome-headless-shell (ver. 152.0.7977.75).
```

`autoInstallPeers` pulled puppeteer into mermaid-cli's tree but did **not** run the gated postinstall. `co_install` still ships: `autoInstallPeers` is a user-settable pnpm setting outside this installer's control, so `pnpm config set auto-install-peers false` would silently break `mmdc` again, whereas the comma-joined group is the form pnpm's Global Packages documentation defines as bundling packages that resolve peer dependencies against each other.

### BROWNFIELD_BEFORE

`BROWNFIELD_BEFORE=ok` (render succeeded after standalone mmdc + standalone allow-build puppeteer, without the grouped invocation). The analysed `Cannot find module 'puppeteer'` gap did not reproduce on pnpm 12.3.4 with default `autoInstallPeers`; the later allow-build puppeteer install populated `~/.cache/puppeteer` and mmdc found the browser. Split vs grouped membership is still visible in the path hashes below.

### SPLIT state (Container C, before remedy)

mermaid-cli hash `14f2-...`, puppeteer hash `151d-...` (different groups).

```json
[
  {
    "path": "/root/.local/share/pnpm/global/v11",
    "private": true,
    "dependencies": {
      "@mermaid-js/mermaid-cli": {
        "from": "@mermaid-js/mermaid-cli",
        "version": "11.17.0",
        "path": "/root/.local/share/pnpm/global/v11/14f2-18d28dc072dbf202-0/node_modules/@mermaid-js/mermaid-cli"
      },
      "@pnpm/exe": {
        "from": "@pnpm/exe",
        "version": "12.3.4",
        "path": "/root/.local/share/pnpm/global/v11/14d6-18d28dbf8bf82d48-0/node_modules/@pnpm/exe"
      },
      "puppeteer": {
        "from": "puppeteer",
        "version": "25.10.0",
        "path": "/root/.local/share/pnpm/global/v11/151d-18d28dce58a8e9af-0/node_modules/puppeteer"
      }
    }
  }
]
```

### GROUPED state (Container C, after remedy)

Both mermaid-cli and puppeteer at hash `15c0-...`. Render after remedy: `TRACER_BROWNFIELD_OK`.

```json
[
  {
    "path": "/root/.local/share/pnpm/global/v11",
    "private": true,
    "dependencies": {
      "@mermaid-js/mermaid-cli": {
        "from": "@mermaid-js/mermaid-cli",
        "version": "11.17.0",
        "path": "/root/.local/share/pnpm/global/v11/15c0-18d28df958d4debd-0/node_modules/@mermaid-js/mermaid-cli"
      },
      "@pnpm/exe": {
        "from": "@pnpm/exe",
        "version": "12.3.4",
        "path": "/root/.local/share/pnpm/global/v11/14d6-18d28dbf8bf82d48-0/node_modules/@pnpm/exe"
      },
      "puppeteer": {
        "from": "puppeteer",
        "version": "25.10.0",
        "path": "/root/.local/share/pnpm/global/v11/15c0-18d28df958d4debd-0/node_modules/puppeteer"
      }
    }
  }
]
```

### Container D (missing shared libraries)

- `PUPPETEER_INSTALL_EXIT=0` (the false-success case)
- `BROWSER_BIN=/root/.cache/puppeteer/chrome-headless-shell/linux-152.0.7977.75/chrome-headless-shell-linux64/chrome-headless-shell`
- `LIBCHECK=fail`
- Verbatim: `error while loading shared libraries: libglib-2.0.so.0: cannot open shared object file: No such file or directory`
- `TRACER_LIBCHECK_DONE`

This is the real-world proof that Task 4's post-install check fires on the exact false-success case.

### Limitations for plan 05-03

1. The exact minimal Fedora/Arch package set for headless Chrome remains unverified (05-RESEARCH.md Open Question 1).
2. Puppeteer's troubleshooting documentation states Chrome publishes no Linux arm64 binary, so a Linux arm64 machine cannot run the downloaded browser — plan 05-03 turns this into an arch gate, not a caveat.

### Exact argv shapes (Task 3)

- no params: `[pnpm, add, -g, npm_pkg]`
- co_install: `[pnpm, add, -g, "a,b"]`
- allow_build: `[pnpm, add, -g, --allow-build=puppeteer, puppeteer]`
- versions+allow_build: `[pnpm, add, -g, --allow-build=puppeteer, puppeteer@^25]`
- all three: `[pnpm, add, -g, --allow-build=puppeteer, "@mermaid-js/mermaid-cli,puppeteer@^25"]`

Floors: `PNPM_CO_INSTALL_MIN=11.1.0`, `PNPM_ALLOW_BUILD_MIN=10.4.0` (`--allow-build` added in 10.4.0).

> **Correction (second-pass review, finding H3).** This task shipped `PNPM_CO_INSTALL_MIN=11.0.0`, citing the pnpm Global Packages v11 redesign. That is the wrong version: 11.0 introduced the hash-keyed global layout, and the shared-install-group semantics for a comma-separated spec — the mechanism this phase actually depends on — arrived in 11.1. A pnpm 11.0.x machine therefore passed the preflight without the feature behind it. The constant is now `11.1.0`; see `installer/versions.py`.
 `parse_declared_version("22.bad")` is `None`, so `min_node = "22.bad"` is a load-time config error. `SMOKE_CHECK_NAMES = frozenset({"puppeteer-browser"})` lives in `installer/model.py`; `SMOKE_CHECKS` in `installer/executors.py` is keyed by exactly those names.

## Self-Check: PASSED

- `TRACER_RENDER_OK`, `TRACER_BROWNFIELD_OK`, `TRACER_LIBCHECK_DONE` all present
- `GROUP_PIN=ok`, `LIBCHECK=fail`
- `make validate` and `make test` passed on the Task 4 tree
- `git log --grep=05-01` returns the three feat commits

---
*Phase: 05-registry-method-corrections-codegraph-mmdc-puppeteer*
*Completed: 2026-09-05*
