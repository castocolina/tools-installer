---
phase: 06-sdkman-hardening-registry-authoring-guidelines
plan: 01
subsystem: registry-authoring
tags: [sdkman, registry, documentation, tier-3-verification]
key-files:
  - installer/registry.toml
  - tests/test_registry.py
  - .claude/architecture.md
  - .planning/PROJECT.md
metrics:
  tests_passed: 1197
  coverage: 99.40%
---

# Phase 6 / Plan 01 — SDKMAN Hardening & Registry-Authoring Guidelines

**Note on authorship of this SUMMARY:** the cross-AI execution (opencode/grok-4.6)
completed both tasks — with real commits, real Tier-3 container evidence, and a
passing full `make validate && make test` gate on each commit — but ran out of its
allotted time while composing this SUMMARY.md, so the orchestrator (this session)
wrote it directly from the actual commit history, the container-run transcript
captured in the candidate's own tool-call log, and an independent re-run of
`make validate && make test` on the final tree. Nothing below is a self-report;
every claim is traced to a commit, a transcript line, or a command this session ran
itself.

## What was built

**Task 1 — Fresh Tier-3 SDKMAN verification, SC#2 resolution recorded as a guarded registry comment**
(commit `c9461b3`)

A disposable `ubuntu:24.04` container (colima + docker) was bootstrapped via
`curl -s "https://get.sdkman.io?ci=true" | bash`. The container's own installed
`sdkman-install.sh`/`sdkman-env-helpers.sh` were read directly (not cited from prior
research) and confirmed: the only interactive prompt in SDKMAN's install path
(`sdkman-install.sh:39-41`, "Do you want X set as default? (Y/n)") is guarded by
`-n "$CURRENT"` — it only fires when a version is already current, i.e. on an
upgrade, never on a first install. `sdk version` in this fresh container reported
SDKMAN script 5.23.0, matching 06-RESEARCH.md's prior reading. `sdk install java`
(no version given) then ran with stdin closed under a `timeout 150` guard:
`Downloading: java 25.0.4-tem` → `Done installing!` → `EXIT_CODE=0`, no prompt of
any kind observed. The container was removed afterward.

**Verbatim transcript excerpts** (the registry.toml comments cite this SUMMARY;
recorded here in full so that citation is actually verifiable, per a Medium
finding two independent code-review lanes raised against an earlier version of
this SUMMARY that omitted them):

```
===== CONFIG auto_answer =====
sdkman_auto_answer=true

===== SDK VERSION =====
SDKMAN!
script: 5.23.0
native: 0.7.34 (linux x86_64)

===== sdk install java (stdin closed, timeout 150) =====
Downloading: java 25.0.4-tem
In progress...
Installing: java 25.0.4-tem
Done installing!
EXIT_CODE=0
```

No "(Y/n)" prompt, no chooser menu, and no other interactive text appeared in the
full output between the `Downloading:` line and `EXIT_CODE=0` — the progress
indicator's percentage ticks were the only other output.

This finding is recorded as two `# Verified 2026-09-06: ...` comments directly
above the `sdkman` and `java` `[[tool]]` blocks in `installer/registry.toml`,
mirroring the existing `codegraph`/`mmdc`/`puppeteer` comment precedent (D-01). The
comments explicitly scope the "closes the prompt's guard" claim to a clean
bootstrap performed by this project's own installer — not to a brownfield machine
with a pre-existing SDKMAN install, since `installer/status.py`'s `is_installed`
short-circuits via `detect_path` before the `?ci=true` bootstrap ever runs
(`installer/status.py:26-29`, `installer/engine.py:80-81`). No `version` param was
added to `java`'s `sdkman` method — the resolution is a comment, not a schema
change (`grep -c 'version' ` on the method params confirms this).

A new guard test, `test_java_and_sdkman_entries_record_the_sc2_no_pin_verification`
(`tests/test_registry.py`, inserted immediately after
`test_java_tools_install_exclusively_through_sdkman` per the plan's insertion-order
requirement), reads `REGISTRY.read_text()` and asserts the five required substrings
(`sdkman_auto_answer`, `Tier-3 container`, `$CURRENT`, `no vendor prompt`, `SC#2`)
are present AND land within the ~30-line window immediately preceding the
`id = "sdkman"` / `id = "java"` lines — a locality assertion, not a whole-file
substring check, so the comments can't silently migrate elsewhere and still pass.
Written test-first (confirmed RED before the comments existed), per this project's
`workflow.tdd_mode` convention.

SC#1's interpretation is explicit in the registry comments and this plan: the
Tier-3 e2e check covers `java` only. `gradle`/`maven`/`groovy`/`springbootcli`'s
"installs exclusively through SDKMAN" claim rests on the pre-existing, unchanged,
still-passing unit-test coverage across `test_model.py`/`test_executors.py`/
`test_resolve.py`/`test_registry.py`/`test_status.py` (Rule 7 mirror), not a
per-tool e2e run.

**Task 2 — Registry-authoring guidelines written into `.claude/architecture.md`**
(commit `b9dbf84`)

A new `## Registry-authoring guidelines` section was added to `.claude/architecture.md`
with two subsections:

- **Per-tool, per-OS verification checklist** (D-01): names the `# Verified {date}: ...`
  comment-citation mechanism as the mandatory recording step for any future registry
  addition, citing the `codegraph`/`mmdc`/`puppeteer` precedent plus this phase's own
  fresh `java`/`sdkman` worked example.
- **Prefer brew** (D-02): the general "prefer brew over other userspace package
  managers" preference is documentation-only, no lint/test enforcement — naming all
  five Java-toolchain tools (`java`, `gradle`, `maven`, `groovy`, `springbootcli`)
  as the SDKMAN exception, citing commit `0e05f50`. Correctly distinguishes the
  *general* brew preference (documented-only) from the *SDKMAN carve-out fact*,
  which is already test-enforced by `test_java_tools_install_exclusively_through_sdkman`
  (`tests/test_registry.py:122-140`) — this distinction was the subject of a
  cross-AI review CRITICAL finding (cycle 2/3) and is now correctly stated
  throughout the document, not just in this summary.

`.planning/PROJECT.md`'s Key Decisions table gained three new rows (SC#2
resolution, D-01, D-02), and its `*Last updated:*` footer was bumped to the
execution date.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | `c9461b3` | feat(06-01): record SC#2 no-pin finding as guarded registry comments |
| 2 | `b9dbf84` | docs(06-01): add registry-authoring guidelines and record D-01/D-02 |

(Preceding these on the same branch: `000b86f`, `c0582ad`, `3592b38`, `40c2960` —
the plan-review-convergence history: 3 review cycles plus a direct post-max-cycles
corrective pass by the orchestrator, per ONESHOT-RULES Rule 10.)

## Deviations from plan

None in substance. The cross-AI execution session ran out of its allotted runtime
while composing this SUMMARY.md after both tasks were fully committed and verified
(the `make validate && make test` gate had already passed on both commits per the
candidate's own captured tool-call log) — this SUMMARY was reconstructed by the
orchestrator directly from the commit history and the transcript, with an
independent re-run of the full gate on the final tree (below) rather than trusting
the candidate's incomplete self-report.

## Independent verification (run by the orchestrator, not the candidate)

- `make validate` — clean (ruff, ruff-format, pyright 0 errors, bandit, vulture, shellcheck).
- `make test` — **1197 passed, 99.40% coverage** (up from 1196 at Phase 5 close; the
  one new guard test accounts for the delta).
- `grep -c "Verified" installer/registry.toml` → 4 (2 pre-existing `codegraph`/`mmdc`
  comment blocks + 2 new `sdkman`/`java` comments this phase adds).
- `git log --oneline --grep='06-01'` shows both task commits landed on the phase
  branch with real diffs (registry.toml/test_registry.py for Task 1;
  architecture.md/PROJECT.md for Task 2) — not placeholder or empty commits.
- Container transcript (captured in the cross-AI session's own tool-call log,
  independently reviewed by the orchestrator): SDKMAN script version 5.23.0,
  `sdkman_auto_answer=true` confirmed in the container's own
  `~/.sdkman/etc/config`, `sdk install java` completed with `Done installing!` and
  `EXIT_CODE=0`, no interactive prompt observed at any point.

## Self-Check

**PASSED** — both tasks committed atomically with passing `make validate && make test`
gates (confirmed independently by the orchestrator on the final tree, not merely
accepted from the candidate's log), the Tier-3 container evidence is real (not
simulated or asserted without a transcript), the new guard test enforces both
presence and locality of the recorded finding, and the registry-authoring
guidelines correctly state what is and isn't test-enforced per the cross-AI
review's cycle-2/3 corrections.
