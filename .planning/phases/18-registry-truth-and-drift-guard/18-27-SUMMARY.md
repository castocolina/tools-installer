---
phase: 18-registry-truth-and-drift-guard
plan: "27"
subsystem: installer
tags: [verify-registry, download, refactor, pyright-strict, dataclasses]

requires:
  - phase: 18-registry-truth-and-drift-guard
    provides: "plans 18-22..18-26: check_registry request sites, transport-error tuple, auto-bump flow, ExecContext release resolver wiring"
provides:
  - "ExecContext with exactly runner, platform and a required resolve_release (constructor contract test)"
  - "DownloadTarget.verified property, public UNPINNED_REASON, one tarball return"
  - "_target_finding / _transport_finding: one failure ladder for HEAD, checksum sidecar and asset download, pinned by a 21-case parity test"
  - "Finding.latest_tag: auto-bump no longer parses the human reason; _NEWER_STABLE_RE deleted"
  - "one app member/unverified rule in _resolve_app_target; _merge_findings shared by both report paths"
affects: [phase-25-lean, verify-registry, download]

actuals:
  tokens: 6800
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "one rule per concept: transport classification, finding construction, findings merge each live in exactly one function"

key-files:
  created: []
  modified:
    - installer/download.py
    - installer/engine.py
    - installer/update.py
    - installer/verify_registry.py
    - tests/test_download.py
    - tests/test_update.py
    - tests/test_verify_registry.py

key-decisions:
  - "_transport_finding is called from both an `except HTTPError` and an `except _TRANSPORT_ERRORS` clause at each site: HTTPError is a subclass of the OSError-adjacent family only via http.client, but urllib's HTTPError is not in _TRANSPORT_ERRORS, so the two clauses keep the ladder single-sourced without widening the tuple"
  - "email.message.Message.get replaces _header_get; the `if headers else` guard stays because HTTPError.headers can be None"

patterns-established:
  - "_target_finding(target, status, reason) is the only place a finding copies a _TargetIdentity's identity fields"

requirements-completed: [REG-03, REG-04]

coverage:
  - id: D1
    description: "ExecContext cannot be constructed without a digest-aware release resolver"
    requirement: REG-03
    verification:
      - kind: unit
        ref: "tests/test_download.py#test_exec_context_requires_a_release_resolver"
        status: pass
    human_judgment: false
  - id: D2
    description: "All three request sites classify transport failures identically (404/410 drift, everything else inconclusive)"
    requirement: REG-04
    verification:
      - kind: unit
        ref: "tests/test_verify_registry.py#test_every_request_site_classifies_a_failure_the_same_way"
        status: pass
    human_judgment: false
  - id: D3
    description: "Auto-bump reads the newer tag from Finding.latest_tag; pinned apps are never listed unverified; one findings merge"
    requirement: REG-04
    verification:
      - kind: unit
        ref: "tests/test_verify_registry.py#test_report_lists_methods_that_would_install_unverified"
        status: pass
    human_judgment: false

duration: 48min
completed: 2026-10-15
status: complete
---

# Phase 18 / Plan 27: Registry truth and drift guard — lean consolidation Summary

**One release resolver per download context, one failure ladder and finding builder in check_registry, bump tag as finding data — verify_registry.py shrank 1768 → 1655 lines with the full suite green.**

## Performance

- **Duration:** 48 min
- **Tasks:** 3 / 3
- **Files modified:** 7

## Accomplishments
- ponytail M5: `ExecContext` is now `runner, platform, resolve_release` with no defaults; a forgotten resolver fails at construction and in pyright. Production callers pass `release_resolver(resolve_tag)` (engine, update) or the live resolver (verify_registry).
- ponytail M4: `_target_finding` and `_transport_finding` own all target-derived `Finding` construction and the 404/410→drift / other→inconclusive ladder at HEAD, checksum sidecar and asset download; a 21-case parametrized parity test pins it.
- ponytail #9, #11, #12, #13, #15, #18: `dataclasses.replace` for platform merges, `Message.get` replaces `_header_get`, `Finding.latest_tag` replaces reason parsing (`_NEWER_STABLE_RE` deleted), the app unverified rule lives once in `_resolve_app_target`, `_merge_findings` serves both `check_registry` and `_finalize_report_after_bumps`, `DownloadTarget.verified` / `UNPINNED_REASON` / one engine leftover message each exist once.

## Task Commits

1. **Task 1: one release resolver per download context + small download/engine duplicates** — `d042844` (refactor)
2. **Task 2: one failure ladder and finding builder in check_registry** — `0cf4e00` (refactor)
3. **Task 3: bump tag as data; one app member/unverified rule; one merge** — `8aa847f` (refactor)

## TDD RED evidence

**Task 1 (structural RED):**
```
FAILED tests/test_download.py::test_exec_context_requires_a_release_resolver
E       AssertionError: assert {'platform', ...ag', 'runner'} == {'platform', ...se', 'runner'}
E         Extra items in the left set: 'resolve_tag'
```

**Task 2 (mutation RED, checksum ladder treated only 404 as missing, run before the refactor):**
```
FAILED test_every_request_site_classifies_a_failure_the_same_way[checksum-410]
E       AssertionError: assert 'inconclusive' == 'drift'
```

**Task 3 (mutation RED, `_resolve_app_target` always setting an unverified reason, run after the change):**
```
FAILED test_report_lists_methods_that_would_install_unverified
E       AssertionError: assert ('mixed', 6, 'app') not in {..., ('mixed', 6, 'app')}
```

## Verify results

- Task 1: `pytest tests/test_download.py tests/test_engine.py tests/test_update.py tests/test_verify_registry.py tests/test_apps.py -q --no-cov` → all pass; `-k "exec_context_requires or digest or unverified"` → 8 passed (7 existing + new).
- Task 2: `pytest tests/test_verify_registry.py tests/test_verify_registry_workflow.py -q --no-cov` → all pass; parity test → 21 passed.
- Task 3: full `tests/test_verify_registry.py` pass; `-k "install_unverified or bump or newer_stable"` → 13 passed (12 before this task + the new pinned-app assertion inside the existing test).
- Every task: `make validate && make test` → 0 errors, **3949 passed, 4 skipped**, coverage 95.66% (floor 90%).
- `git diff --exit-code 6794a65 -- pyproject.toml uv.lock` → clean (no dependency change).

## Line counts

| File | Before | After |
|---|---|---|
| installer/verify_registry.py | 1768 | 1655 |
| installer/download.py | 442 | 437 |
| installer/engine.py | 293 | 290 |
| installer/update.py | 513 | 512 |

Net diff for the plan: 238 insertions, 262 deletions; every shrink-guard check passed before each commit.

## Per-finding outcomes

| Finding | Source | Outcome | Commit | Test |
|---|---|---|---|---|
| M5 two release resolvers | ponytail | fixed | d042844 | test_exec_context_requires_a_release_resolver |
| #18 verified test / tarball returns / leftover tail | ponytail | fixed | d042844 | existing digest/unverified tests unchanged |
| M4 three error ladders | ponytail | fixed | 0cf4e00 | test_every_request_site_classifies_a_failure_the_same_way (mutation-proven) |
| #9 identity rebuilt field-by-field | ponytail | fixed (shared-key half not taken, per plan) | 0cf4e00 | existing multi-platform tests |
| #11 _header_get | ponytail | fixed | 0cf4e00 | existing rate-limit tests unchanged |
| #12 reason-parsed bump tag | ponytail | fixed | 8aa847f | existing auto-bump tests pass unchanged |
| #13 app member/unverified ×3 | ponytail | fixed | 8aa847f | test_report_lists_methods_that_would_install_unverified (+ pinned-app assertion) |
| #15 duplicated merge | ponytail | fixed | 8aa847f | existing report-format tests unchanged |

## Deviations from Plan

1. **Parity test shape** — the plan's per-case `name` for `_transport_finding` is realized as the site's asset/checksum filename passed at each call; the except-clause split (`except HTTPError` + `except _TRANSPORT_ERRORS`, both delegating to `_transport_finding`) is an implementation detail HTTPError's type hierarchy forces. Reason strings are byte-identical.
2. **Task 3 mutation timing** — the plan says "mutation RED, after the change"; run exactly then and pasted above.
3. **`_identity_finding` helper** — the two identity-preserving `replace(url_wide[...])` copies in the loop and the post-loop sweep also went through `_target_finding`-style consolidation (a `replace`-based helper), slightly beyond the plan's minimum; needed to satisfy the `platforms=target.platforms ≤ 2` acceptance grep honestly.

## Issues Encountered

- `make validate` caught two lambda/ruff-format/pyright issues in the new test code (E731, reportRedeclaration, untyped failure tuples); fixed at the root with named functions and a typed `_FailureSpec` alias. No suppressions used.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The "Deferred to Phase 25 (Lean)" list in the plan is the hand-off list for the next lean pass (IN-02 partial, IN-03, IN-04, IN-05, IN-06, #10/#14/#18-partial/#19, apps._UNVERIFIED_REASON import swap).
- No blockers.

---
*Phase: 18-registry-truth-and-drift-guard*
*Completed: 2026-10-15*
