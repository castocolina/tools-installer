---
phase: 27
review: 27-REVIEW.md
titles: json
findings:
  - id: WR-01
    severity: warning
    disposition: fixed
    title: "catalog-audit still runs `make validate` then `make test` per approved change, against the new AGENTS rule"
  - id: WR-02
    severity: warning
    disposition: fixed
    title: "git-workflow says the push gate tests every commit's tree; it tests only the tip"
  - id: WR-03
    severity: warning
    disposition: fixed
    title: "AGENTS.md says `devtools/docs_only.py` lists the tests that read a non-Python file; it does not"
  - id: WR-04
    severity: warning
    disposition: fixed
    title: "The push gate ignores untracked `.planning/` files, but two tests now read `.planning/` files"
  - id: WR-05
    severity: warning
    disposition: fixed
    title: "The CI check accepts a Test step that skips macOS"
  - id: WR-06
    severity: warning
    disposition: fixed
    title: "The skill calls every terminal default a `post_install` action, but rule (a) is not one"
  - id: WR-07
    severity: warning
    disposition: fixed
    title: "\"Sandbox every real install in a disposable container\" cannot cover macOS methods"
  - id: WR-08
    severity: warning
    disposition: fixed
    title: "Two config paths in the closed table disagree with the installer"
  - id: IN-01
    severity: info
    disposition: fixed
    title: "The skill shows two backslashes where the layout breaks one"
  - id: IN-02
    severity: info
    disposition: skipped
    title: "The \"asks about a default\" and \"Option-as-Alt\" detectors miss common phrasings"
  - id: IN-03
    severity: info
    disposition: skipped
    title: "`_phase_dir` globs directories, not the verdict files"
  - id: IN-04
    severity: info
    disposition: deferred
    title: "The shared parser does not check `max` against the rubric"
  - id: IN-05
    severity: info
    disposition: deferred
    title: "The verdict fixture builder is still duplicated, and the underscore aliases add four import statements"
  - id: IN-06
    severity: info
    disposition: deferred
    title: "`rule_items` repeats `_items`"
  - id: IN-07
    severity: info
    disposition: skipped
    title: "Already-defended-elsewhere: the `make validate` after a plan repeats the last commit hook's run"
  - id: IN-08
    severity: info
    disposition: fixed
    title: "git-workflow's docs-only definition misses the `.planning/` files tests read"
---

# Phase 27: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| WR-01 | warning | fixed | fixed in c955da0a (review fix round, 27-REVIEW-FIX.md) |
| WR-02 | warning | fixed | fixed in 6b4de439 |
| WR-03 | warning | fixed | fixed in 6b4de439 |
| WR-04 | warning | fixed | external lane (opencode referee-one), confirmed by the reviewer; fixed in 24a73427, real glob checked in a scratch repo |
| WR-05 | warning | fixed | external lane (opencode referee-one), confirmed by the reviewer; fixed in 54cf2674 |
| WR-06 | warning | fixed | fixed in 54cf2674 |
| WR-07 | warning | fixed | external lane (opencode referee-one), confirmed by the reviewer; fixed in 54cf2674 |
| WR-08 | warning | fixed | external lane (opencode referee-one), confirmed by the reviewer; fixed in 54cf2674 |
| IN-01 | info | fixed | fixed in 54cf2674 |
| IN-02 | info | skipped | accepted: heuristic detectors by design (test plus judgment); widening them would flag legitimate extras text (27-02 ledger) |
| IN-03 | info | skipped | rejected: reopens D-07, decided in the discuss step; needs an unrelated `27-*` entry to bite |
| IN-04 | info | deferred | backlog 999.26: the shared parser would also check `max` for catalog-audit verdicts; `verdict_regressions` already does it for this skill |
| IN-05 | info | deferred | backlog 999.26: share the verdict fixture builder; tidiness only |
| IN-06 | info | deferred | backlog 999.26: dedupe `rule_items`; tidiness only |
| IN-07 | info | skipped | rejected: the owner asked for `make validate` after a plan (2026-11-20) |
| IN-08 | info | fixed | fixed in 6b4de439 |

The external lane's claim 3 (the targeted-test rule misses indirect callers) was rejected by the reviewer: targeted runs are a working-time subset, `make test` runs after each plan and the push gate runs the full suite.
