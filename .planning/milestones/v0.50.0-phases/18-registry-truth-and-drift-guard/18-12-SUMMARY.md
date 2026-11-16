---
phase: 18-registry-truth-and-drift-guard
plan: "12"
subsystem: testing
tags: [registry, drift, verify_registry, checksums, tarfile, zipfile]

requires:
  - phase: 18-registry-truth-and-drift-guard
    provides: resolve_target, pinned_url, Release digests (plans 18-07, 18-09, 18-16)
provides:
  - installer/verify_registry.py check core (Probe, check_registry, format_report, main, state cache)
  - Offline test suite tests/test_verify_registry.py (29 tests)
affects: [18-13, 18-14, 18-15, 18-17]

actuals:
  tokens: 45000
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Per-target state keys include tool id and extraction settings (archive/strip/raw)"
    - "Url-wide drift overrides cached ok findings after the walk"

key-files:
  created:
    - installer/verify_registry.py
    - tests/test_verify_registry.py
  modified: []

key-decisions:
  - "Pinned GitHub app/tarball digest comparison uses registry_pin, not GitHub-release digest expected hash"
  - "load_tools returns a list; check_registry walks Sequence[Tool]"

patterns-established:
  - "Members listed via tarfile.getnames / zipfile.namelist only; never extract"

requirements-completed: [REG-03]

coverage:
  - id: D1
    description: "Read-only verify_registry check core with resolver, HEAD, digest/member checks, and state cache"
    requirement: REG-03
    verification:
      - kind: unit
        ref: "tests/test_verify_registry.py (29 tests)"
        status: pass
    human_judgment: false

duration: 90min
completed: 2026-10-15
status: complete
---

# Phase 18 Plan 12 Summary

**Read-only `verify_registry` reuses the install resolver, caches verified fingerprints, and catches asset/member/checksum drift offline before users hit install failures.**

## Performance

- **Duration:** ~90 min
- **Tasks:** 2
- **Files modified:** 2 (new module + tests)

## Accomplishments

- Task 1: `installer/verify_registry.py` with `check_registry`, `format_report`, `main`, HEAD-based drift for missing assets, inconclusive on non-404 HEAD failures, Passed section with platforms, state file persistence.
- Task 2: Digest/checksum/member verification with conditional download, pinned-vs-latest GitHub digest check, url-wide failure override, strip/archive identity in `state_key`, and 22 additional offline tests.

## Task Commits

1. **Task 1: HEAD checks and report CLI** — `2de697f`
2. **Task 2: digest, member checks and state cache** — `e6baa29`

## TDD RED evidence

**Task 1 (before module existed):**

```
ModuleNotFoundError: No module named 'installer.verify_registry'
```

**Task 2 (after tests added, before registry_pin / registry `verified` fixes):**

```
ValueError: tool 'a': 'sha256' needs a url templated with {ver}
assert any(f.status == "drift" for f in report.findings)  # pinned digest test got checksum mismatch only
```

## Verify commands

- `uv run pytest tests/test_verify_registry.py -q --no-cov` → 29 passed
- `uv run python -m installer.verify_registry --help` → exit 0
- `make validate && make test` → exit 0 (coverage 95.33%)

## Deviations from Plan

None — plan executed as written. Test registries add `verified` and `{ver}` tarball URLs where `load_tools` validation requires them.

## Issues Encountered

None blocking. `verify_registry.py` module coverage is ~79% (new code); suite total remains above the 90% gate.

---
*Phase: 18-registry-truth-and-drift-guard*
*Completed: 2026-10-15*
