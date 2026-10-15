---
phase: 18-registry-truth-and-drift-guard
plan: "24"
subsystem: registry
tags: [strip, verify-registry, tar, zip, load_tools, WR-02]

requires:
  - phase: 18-registry-truth-and-drift-guard
    provides: verify-registry drift guard and registry loader from plans 18-21..18-23
provides:
  - Loader validation for strip value and placement (tar-only)
  - _member_present mirroring tar --strip-components and unzip exact paths
  - Regression tests for WR-02 divergences
affects: [18-registry-truth-and-drift-guard, verify-registry, weekly registry verification]

actuals:
  tokens: 1200
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "strip is rejected at load time when install cannot honor it"
    - "verify-registry member checks mirror download._extract_into semantics"

key-files:
  created: []
  modified:
    - installer/model.py
    - installer/registry.toml
    - installer/verify_registry.py
    - tests/test_model.py
    - tests/test_registry.py
    - tests/test_verify_registry.py

key-decisions:
  - "Bring verify-registry to install semantics; do not change download._extract_into"
  - "Remove gh macOS zip strip=0 rather than keeping a loader/checker fiction"

patterns-established:
  - "Archive member presence: zip exact name match; tar split-based strip like GNU tar"

requirements-completed: [REG-01, REG-03]

coverage:
  - id: D1
    description: "load_tools rejects invalid strip values and zip/raw strip placement"
    requirement: REG-01
    verification:
      - kind: unit
        ref: tests/test_model.py#test_strip_must_be_a_non_negative_integer
        status: pass
      - kind: unit
        ref: tests/test_model.py#test_strip_is_rejected_where_install_ignores_it
        status: pass
    human_judgment: false
  - id: D2
    description: "verify-registry _member_present matches tar/unzip extraction"
    requirement: REG-03
    verification:
      - kind: unit
        ref: tests/test_verify_registry.py#test_dot_prefixed_tar_strips_like_tar
        status: pass
      - kind: unit
        ref: tests/test_verify_registry.py#test_zip_member_must_match_the_stored_name
        status: pass
    human_judgment: false

duration: 45min
completed: 2026-10-15
status: complete
---

# Phase 18 Plan 24 Summary

**Loader and verify-registry now agree with install on `strip` and archive member paths (WR-02 closed).**

## Performance

- **Duration:** ~45 min
- **Tasks:** 2 (+ summary commit)
- **Files modified:** 6 source files + SUMMARY

## Review finding dispositions

| ID | Source | Outcome | Commit | Test |
|----|--------|---------|--------|------|
| WR-02 (loader: strip bool/zip/raw) | 18-REVIEW | Closed | `419411d` | `test_strip_must_be_a_non_negative_integer`, `test_strip_is_rejected_where_install_ignores_it` |
| WR-02 (gh macOS strip=0 hide) | 18-15 data | Removed line | `419411d` | `test_audit_fix_d3_gh_has_a_macos_release`, shipped registry load |
| WR-02 (checker `./` tar strip) | 18-REVIEW | Closed | `4fdc1ba` | `test_dot_prefixed_tar_strips_like_tar` |
| WR-02 (checker zip exact member) | 18-REVIEW | Closed | `4fdc1ba` | `test_zip_member_must_match_the_stored_name` |

## TDD RED evidence

**Task 1** (`uv run pytest tests/test_model.py tests/test_registry.py -q --no-cov -k "strip or d3_gh"`):

```
FAILED ... test_strip_must_be_a_non_negative_integer[strip = true] - Failed: DID NOT RAISE ValueError
FAILED ... test_strip_must_be_a_non_negative_integer[strip = -1] - Failed: DID NOT RAISE ValueError
FAILED ... test_strip_must_be_a_non_negative_integer[strip = "1"] - Failed: DID NOT RAISE ValueError
FAILED ... test_strip_is_rejected_where_install_ignores_it[archive = "zip"\nstrip = 0] - DID NOT RAISE
FAILED ... test_strip_is_rejected_where_install_ignores_it[raw = true\nstrip = 1] - DID NOT RAISE
```

**Task 2** (`uv run pytest tests/test_verify_registry.py -q --no-cov -k "dot_prefixed or stored_name"` before fix):

- `test_dot_prefixed_tar_strips_like_tar`: `good` was `drift` (wanted `ok`); separate probe showed `member = "bin/tool"` with `strip = 1` wrongly **`ok`** (install would not find it) — the RED case called out in the plan.
- `test_dot_prefixed_tar_without_strip_matches_the_normalized_name`: passed before and after (normalization pin).

## Fixture cleanup (Task 1)

Removed `strip = 0` immediately after `archive = "zip"` in `tests/test_verify_registry.py` at lines **408, 728, 736, 778, 790, 2962, 2978, 2994**. Adjusted `test_corrupt_archive_is_drift` so zip cases omit `strip` (tar-only).

## Line-count / diff evidence

**After Task 1 commit (pre-commit tree):**

```
  1605 tests/test_model.py
  2573 tests/test_registry.py
  3002 tests/test_verify_registry.py
   970 installer/model.py
 installer/model.py            |  9 +++++
 installer/registry.toml       |  1 -
 tests/test_model.py           | 76 +++++++++++++++++++++++++++++++++++++++++++
 tests/test_registry.py        |  2 +-
 tests/test_verify_registry.py | 11 ++----
```

**After Task 2 commit (pre-commit tree):**

```
  3123 tests/test_verify_registry.py
  1713 installer/verify_registry.py
 installer/verify_registry.py  |  33 ++++++++----
 tests/test_verify_registry.py | 119 ++++++++++++++++++++++++++++++++++++++++++
```

`git diff --quiet HEAD -- installer/download.py` remained clean throughout.

## Task commits

1. **Task 1: loader + gh strip + fixtures** — `419411d1a4f97df9899eecb99887eaf311ef39e8`
2. **Task 2: _member_present rewrite** — `4fdc1bace1b043cb7ccce20607e64b52a55a69cd`

## Verify results

- Task 1: `uv run pytest tests/test_model.py tests/test_registry.py tests/test_verify_registry.py tests/test_download.py -q --no-cov` — pass; shrink guards pass; `make validate && make test` — pass (3895+ tests).
- Task 2: full `tests/test_verify_registry.py` — pass; `-k "dot_prefixed or stored_name or differing_only_in_strip or strip_change"` — 5 passed; `make validate && make test` — pass (3898 passed).

## Deviations from plan

None — plan executed as written. `test_corrupt_archive_is_drift` zip arm was updated so zip fixtures load under the new rule (same intent, not listed explicitly in the plan).

## Issues for orchestrator

None.

---
*Phase: 18-registry-truth-and-drift-guard*
*Completed: 2026-10-15*
