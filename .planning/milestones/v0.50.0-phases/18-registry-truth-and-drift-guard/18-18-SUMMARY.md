---
phase: 18-registry-truth-and-drift-guard
plan: "18"
subsystem: testing
tags: [e2e, container, ruff, drawio, smoke, registry]

requires:
  - phase: 18-registry-truth-and-drift-guard
    provides: Final registry from 18-15, dev-synced harness from 18-05, smoke rules from 18-09/18-19
provides:
  - Disposable-container proof of clean install, rerun, uninstall, and reinstall (SPEC R5/R6)
  - ROADMAP SC4 ruff owner evidence under launch-form setup
  - draw.io AppImage smoke fix (headless argv + container FUSE harness)
affects: [18-19, 18-20]

actuals:
  tokens: 4000
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Container-only AppImage gaps: APPIMAGE_EXTRACT_AND_RUN in e2e harness, not registry argv that bypasses mount"
    - "Electron GUI smoke in headless CI: smoke_argv with --ozone-platform=headless when DISPLAY is stripped"

key-files:
  created: []
  modified:
    - scripts/container-e2e-verify.sh
    - installer/registry.toml
    - tests/test_registry.py

key-decisions:
  - "draw.io Linux AppImage smoke uses --ozone-platform=headless --version after in-container diagnosis (FUSE then X11 failures)"
  - "E2e harness sets APPIMAGE_EXTRACT_AND_RUN=1; production smoke on hosts without FUSE still fails honestly (D-06)"

patterns-established:
  - "Registry smoke_argv documents the smallest argv that prints version for a given binary; harness handles environment gaps"

requirements-completed: [REG-05, REG-06, REG-09]

coverage:
  - id: D1
    description: "Full Fedora container e2e pass1 clean install with smoke and verification"
    requirement: REG-05
    verification:
      - kind: e2e
        ref: ".e2e-artifacts/container/18-18-pass1.log TRACER_CLEAN_INSTALL_OK"
        status: pass
    human_judgment: false
  - id: D2
    description: "Launch form hides dev ruff; installer owns ~/.local/bin/ruff through pass2"
    requirement: REG-06
    verification:
      - kind: e2e
        ref: ".e2e-artifacts/container/18-18-ruff-probe.log; pass2-transcript.log ruff uninstall lines"
        status: pass
    human_judgment: false
  - id: D3
    description: "draw.io and other GUI smokes pass without appimage-version registry hack"
    requirement: REG-09
    verification:
      - kind: unit
        ref: tests/test_registry.py#test_drawio_desktop_declares_its_smoke_argv
        status: pass
      - kind: other
        ref: "grep -c appimage-version installer/registry.toml → 0"
        status: pass
    human_judgment: false

duration: 180min
completed: 2026-10-15
status: complete
---

# Phase 18 Plan 18: Registry truth — container e2e (R5/R6)

**Disposable Fedora e2e proves clean install, pass2 lifecycle, launch-form ruff ownership, and draw.io AppImage smoke after container-only harness fixes.**

## Performance

- **Duration:** ~180 min (includes fresh bootstrap, pass1 full catalog, pass2, prior draw.io diagnosis)
- **Tasks:** 2
- **Commits:** 2 (feat + docs)

## Task Commits

1. **Task 1: harness FUSE + draw.io smoke_argv + registry test** — `17d404b`
2. **Plan summary** — `e9d5f4b`

## Container identity (one id for all steps)

```
bootstrap: 6d3bd01af112bd507c376dc7b045ad7f1fe2f5eec080d7eba13dd39d1c818356
probe:     6d3bd01af112bd507c376dc7b045ad7f1fe2f5eec080d7eba13dd39d1c818356
pass1:     6d3bd01af112bd507c376dc7b045ad7f1fe2f5eec080d7eba13dd39d1c818356
pass2:     6d3bd01af112bd507c376dc7b045ad7f1fe2f5eec080d7eba13dd39d1c818356
```

Recorded in `.e2e-artifacts/container/18-18-container-id.log`. Container removed after pass2 (`TRACER_CONTAINER_TEARDOWN_OK`).

## Pass1 verdict

```
PASS1_COUNTS installed=74 already=0 failed=0 dependency_failed=0 mismatched=0 no_method=0 manual_required=8 setup_exit=0
TRACER_CLEAN_INSTALL_OK installed=74 failed=0 no_method=0 manual_required=8
```

macOS paths were not exercised (Linux container only).

## Ruff probes (SC4)

```
control: /home/tester/workspace/.venv/bin/ruff
launch-before: None
launch-after: /home/tester/.local/bin/ruff
```

Pass1 verification row:

```
  ruff: sha256 ✓
```

Pass2 uninstall preview (from `pass2-transcript.log`):

```
  /home/tester/.local/bin/ruff
  /home/tester/.local/opt/ruff
```

Reinstall row:

```
  ruff: sha256 ✓
```

Pass2 markers: `TRACER_RERUN_OK`, `TRACER_UNINSTALL_OK`, `TRACER_REINSTALL_OK`.

## GUI / download smoke (pass1)

| Tool | Verification row | Notes |
|------|------------------|-------|
| hyperfine | `hyperfine: sha256 ✓` | musl binary (ledger D7) |
| drawio-desktop | `drawio-desktop: sha256 ✓` | AppImage; see deviation below |
| sublime | `sublime: sha256 ✓` | pinned app |
| jetbrains-toolbox | unverified (unpinned url) | installed; no sha256 row |

sdkman installed with no `smoke run failed` for `sdkman-init.sh` (L-18-14 / plan 18-19).

## draw.io deviation (container diagnosis)

Prior pass1 failed on `drawio-desktop` smoke exit 127. Fresh-container diagnosis (`.e2e-artifacts/container/18-18-drawio-diagnosis.log`):

| Mode | Result |
|------|--------|
| No `APPIMAGE_EXTRACT_AND_RUN`, `--version` | FUSE: `fuse: device not found` / `Cannot mount AppImage` → exit 127 |
| `APPIMAGE_EXTRACT_AND_RUN=1`, plain `--version` | X11: `Missing X server or $DISPLAY` → exit 127 |
| `APPIMAGE_EXTRACT_AND_RUN=1`, `--ozone-platform=headless --version` | Prints `32.4.1`, exit 0 (dbus noise only) |

**Fixes (with evidence):**

1. `scripts/container-e2e-verify.sh`: `export APPIMAGE_EXTRACT_AND_RUN=1` in `run_setup_as_tester` (container has no FUSE device).
2. `installer/registry.toml`: Linux draw.io AppImage methods declare `smoke_argv = ["--ozone-platform=headless", "--version"]` (smoke strips DISPLAY; Electron needs headless ozone for `--version`).
3. `tests/test_registry.py`: `test_drawio_desktop_declares_its_smoke_argv`.

`grep -c 'appimage-version' installer/registry.toml` → **0** (no registry argv that bypasses AppImage mount).

## Automated plan verify (all exit 0)

- Ruff probe paths and launch-form outside `.venv`
- Pass1/probe logs newer than bootstrap; `TRACER_CLEAN_INSTALL_OK` and ruff sha256 row
- Single container id across bootstrap/probe/pass1/pass2
- Pass2 transcript ruff lines and markers; container absent after run

## Validation

```
make validate && make test
```

3868 passed, 4 skipped; coverage 95.29%.
