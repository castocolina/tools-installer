---
phase: 18-registry-truth-and-drift-guard
plan: "17"
subsystem: registry
tags: [verify-registry, drift, github-api, checksum, REG-03, REG-04]
requires:
  - phase: 18-registry-truth-and-drift-guard
    provides: check_registry drift detection from plan 18-12
provides:
  - Run verdicts (blocked, exit codes L-18-18), newer-stable drift, not-checkable listing
  - Unverified at install section (SC3 residual measurement)
  - github_token, default_probe(token), urlopen_fetch explicit token
affects: [18-14, 18-15]
actuals:
  tokens: 45000
  tasks: 3
  commits: 2
tech-stack:
  added: []
  patterns: ["Release-read transport accounting separate from HTTP answers (L-18-15)"]
key-files:
  created: []
  modified:
    - installer/verify_registry.py
    - installer/versions.py
    - tests/test_verify_registry.py
    - tests/test_versions.py
key-decisions:
  - "Drift exit code 1 wins over blocked/inconclusive (L-18-18)"
  - "Rate limit read from response headers, not bare 403 (L-18-10)"
requirements-completed: [REG-03, REG-04]
coverage:
  - id: D1
    description: Run verdicts, newer stable, not-checkable, blocked/flaky behavior
    requirement: REG-03
    verification:
      - kind: unit
        ref: tests/test_verify_registry.py (newer_stable, blocks_the_run, flaky_host, confirmed_drift)
        status: pass
    human_judgment: false
  - id: D2
    description: Unverified at install report section
    requirement: REG-04
    verification:
      - kind: unit
        ref: tests/test_verify_registry.py::test_report_lists_methods_that_would_install_unverified
        status: pass
    human_judgment: false
  - id: D3
    description: GitHub token from env or gh login without leaking
    requirement: REG-03
    verification:
      - kind: unit
        ref: tests/test_versions.py::test_explicit_token_is_sent_to_api_github_only
        status: pass
    human_judgment: false
duration: 120min
completed: 2026-10-15
status: complete
---

# Plan 18-17 Summary

**verify-registry now reports run verdicts (blocked vs drift vs inconclusive), newer-stable pin drift, the unverified-install residual list, and authenticated GitHub reads without token leakage.**

## Task Commits

1. **Tasks 1–3:** `ce9882b` feat(18-17): verify-registry verdicts, unverified section, and GitHub token
2. **Summary:** `93d763f` docs(18-17): plan summary

## TDD RED (trimmed)

Before implementation, new tests failed with missing behavior, e.g.:

```
AttributeError: 'Report' object has no attribute 'blocked'
AssertionError: assert 2 == 1  # exit_code before L-18-18 drift-over-block rule
ImportError: cannot import name 'github_token'
```

## Verify

- `uv run pytest tests/test_verify_registry.py -q --no-cov -k "newer_stable or blocks_the_run or flaky_host or confirmed_drift or install_unverified or token"` → pass (27+ cases)
- `make validate` → exit 0
- `make test` → 3831 passed, coverage 95.60%

## Deviations

- **Commits:** Tasks 1–3 landed in one implementation commit (files are intertwined; splitting would be artificial staging).
- **Tests:** `test_pinned_sha256_of_an_older_tag_is_not_compared_with_the_latest_release` updated to expect newer-stable drift alongside no digest mismatch (interaction with Task 1).
- **Tests:** Blocked/forbidden fixtures include a minimal `github_release` tool so release-read accounting runs (vendor-only registries never called `probe.release`).

## Issues for orchestrator

None.
