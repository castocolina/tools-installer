---
phase: 17-stop-the-bleeding
plan: "04"
subsystem: doctor
tags: [doctor, symlink, guidance, diagnostics, d-13, safe-01]

requires:
  - phase: 17-stop-the-bleeding
    provides: "Doctor audit seam (doctor_data / run_doctor / doctor_guidance) from earlier phases"
provides:
  - BrokenLink dataclass and scan_bin_links(bin_dir) in installer/doctor.py
  - DoctorReport.broken_links (appended, default ()) covered by has_problems
  - doctor_data fills broken_links; both console and TUI render the finding
  - doctor_guidance emits one error Guidance per broken link with shlex-quoted repair text
affects: [17-02 link-safety, 19 receipts, 21 UI-07 pnpm shims]

actuals:
  tokens: 15500
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "registry-independent read-only Doctor scan (no registry import, nothing executed)"

key-files:
  created: []
  modified:
    - installer/doctor.py
    - installer/guidance.py
    - installer/app.py
    - tests/test_doctor.py
    - tests/test_guidance.py

key-decisions:
  - "Both guidance wording branches (opt_dir set / None) shipped in Task 1's commit as one code path; Task 2 added the proving tests, which were therefore green on arrival (no RED for Task 2)."
  - "No-opt-dir wording per RUN-LEDGER Q4: remove the link (rm <quoted path>), or reinstall the tool that owns it — never names an opt dir the link does not point into."
  - "Test evidence normalizes console-wrapped output via whitespace join rather than pinning render line breaks."

patterns-established:
  - "Broken-link repair text is shlex-quoted and free of sudo/pkexec/doas and of the 'Run `make fix`'/'Run `make setup`' prefixes DoctorScreen._tui_guidance rewrites."

requirements-completed: [SAFE-01]

coverage:
  - id: D1
    description: "A bin-dir symlink to a directory (the live subl case) is one finding with an opt-dir removal + catalog reinstall repair"
    requirement: SAFE-01
    verification:
      - kind: unit
        ref: "tests/test_doctor.py#test_scan_reports_a_link_to_a_directory"
        status: pass
      - kind: unit
        ref: "tests/test_guidance.py#test_broken_link_guidance_names_the_opt_dir_repair"
        status: pass
    human_judgment: false
  - id: D2
    description: "A dangling link is reported; outside an opt dir the repair removes the link or reinstall its owner"
    requirement: SAFE-01
    verification:
      - kind: unit
        ref: "tests/test_doctor.py#test_scan_reports_a_dangling_link"
        status: pass
      - kind: unit
        ref: "tests/test_guidance.py#test_dangling_link_without_opt_dir_guidance_removes_the_link"
        status: pass
    human_judgment: false
  - id: D3
    description: "Doctor run reaches the finding in both renderers and changes nothing on disk; guidance never escalates"
    requirement: SAFE-01
    verification:
      - kind: unit
        ref: "tests/test_doctor.py#test_run_doctor_reports_broken_links_and_changes_nothing"
        status: pass
      - kind: unit
        ref: "tests/test_doctor.py#test_scan_ignores_regular_files_and_good_links"
        status: pass
      - kind: unit
        ref: "tests/test_guidance.py#test_broken_link_guidance_never_escalates"
        status: pass
      - kind: unit
        ref: "tests/test_guidance.py#test_only_broken_links_is_a_problem"
        status: pass
    human_judgment: false

duration: 35min
completed: 2026-10-14
status: complete
---

# Plan 17-04 Summary

**Doctor now scans every bin-dir symlink (D-13): dangling links and directory-pointing links each produce one error finding with shlex-quoted, non-escalating repair text in both `make doctor` and the TUI, and the scan executes nothing.**

## Performance

- **Duration:** ~35 min
- **Tasks:** 2 of 2
- **Files modified:** 5 (all within the plan's files_modified)

## Accomplishments

- `installer/doctor.py`: frozen `BrokenLink(path, target, kind, opt_dir)` and `scan_bin_links(bin_dir)` — a sorted, registry-independent, read-only walk of the bin dir's symlinks; a target that resolves inside `opt_dir(entry.name)` sets `opt_dir`, otherwise `None`; per-entry `OSError` and a missing bin dir yield `()`.
- `DoctorReport.broken_links: tuple[BrokenLink, ...] = ()` appended (existing equality constructions untouched) and folded into `has_problems`.
- `installer/app.py`: `doctor_data` fills the field once via `dataclasses.replace(report, broken_links=scan_bin_links(default_bin_dir))`; `run_doctor` and `_build_app` consume it with no further wiring.
- `installer/guidance.py`: one `Severity.ERROR` Guidance per broken link — title `<path> is a broken link`; meaning distinguishes "a directory" from "nothing"; next step is `Remove <opt_dir> (rm -rf '<opt_dir>'), then reinstall <name> from the catalog (make setup).` when `opt_dir` is set, else `Remove the link (rm '<path>'), or reinstall the tool that owns it.`
- The TUI needed zero code change: `DoctorScreen` renders `doctor_guidance` output, and the wording provably avoids the `Run \`make fix\`` / `Run \`make setup\`` prefixes `_tui_guidance` rewrites (`git show --stat 75a4e30 -- installer/wizard_app.py` is empty).

## Task Commits

1. **Task 1: a link to a directory reaches `make doctor` end to end, nothing changed on disk** — `80f2073` (feat)
2. **Task 2: dangling links, no-opt-dir wording, TUI-safety tests** — `75a4e30` (test)

## TDD RED Evidence

**Task 1** (tests written first, before any implementation):

```
>       from installer.doctor import BrokenLink, scan_bin_links
E       ImportError: cannot import name 'BrokenLink' from 'installer.doctor' (/.../installer/doctor.py)
FAILED tests/test_doctor.py::test_scan_reports_a_link_to_a_directory - Import...
FAILED tests/test_doctor.py::test_scan_ignores_regular_files_and_good_links
FAILED tests/test_doctor.py::test_run_doctor_reports_broken_links_and_changes_nothing
```

**Task 2:** no RED captured — the guidance's `opt_dir is None` branch (RUN-LEDGER Q4 wording) already landed in Task 1's commit because both wording branches are one code path in `doctor_guidance`. Task 2's five tests passed on first run; the commit is tests-only by design (acceptance criterion: no `installer/wizard_app.py` change).

## Verify Results

- `uv run pytest tests/test_doctor.py -q --no-cov` — 7 passed
- `uv run pytest tests/test_guidance.py tests/test_doctor.py -q --no-cov` — 67 passed
- `-k "dangling or opt_dir_repair or never_escalates or only_broken_links"` — 5 passed
- `make validate` — pass (ruff, ruff format, pyright, bandit, vulture, shellcheck)
- `make test` — 3485 passed, 4 skipped; coverage gate 95.88% ≥ 90% (run before each commit)
- Acceptance greps: `def scan_bin_links` ×1, `broken_links: tuple[BrokenLink, ...] = ()` ×1, `registry` ×0 in doctor.py, `scan_bin_links(` ×1 in app.py, `sudo|pkexec|doas` ×0 in doctor.py

## Decisions Made

- No-opt-dir repair wording (RUN-LEDGER Q4, planner discretion): `Remove the link (rm <quoted path>), or reinstall the tool that owns it.` — never names an opt dir the link does not point into (protects uv/pnpm shims; RESEARCH Pattern 7).
- Both wording branches implemented in Task 1 (single code path, best-over-easy rule); Task 2 becomes a pure test commit proving the second branch, the escalation ban, and has_problems coverage.
- Test output assertions normalize console line wrapping (whitespace join) instead of asserting raw wrapped text.

## Deviations from Plan

**1. Task 2 has no RED run**
- **Found during:** Task 2
- **Issue:** The plan sequenced the None-branch wording into Task 2, but implementing both guidance branches together in Task 1 (one code path) left Task 2's tests green on arrival.
- **Fix:** None needed — recorded here; Task 2's commit is tests-only as its acceptance criteria require.
- **Committed in:** 75a4e30

**Total deviations:** 1 (ordering only; no scope or behavior change)

## Issues Encountered

- Quality-gate fixes during development (all root-cause fixes, none silenced): ruff import sorting/line length, a `kind` Literal type annotation pyright required in doctor.py and tests, and pyright's unknown-type complaints on un-annotated pytest fixture parameters (annotated with `Path` / `pytest.MonkeyPatch`).

## Flagged assumption (carried from the plan, for the orchestrator)

- The SPEC prohibition "an argv scan over the executors finds no sudo" cannot pass in Phase 17: `installer/executors.py:371,375,379` still build `sudo dnf|apt-get|pacman` argv; that replacement is Phase 22 (LIFE-02). This plan enforces the prohibition on all Phase 17 text.

## Next Phase Readiness

- 17-02 (link-site file checks) can now be verified against Doctor output that shows the damage H1 already did, with exact repair steps.
- Phase 21 UI-07 can extend `BrokenLink.kind`/meaning with pnpm-specific dangling-shim reasons without re-touching the scan.

---
*Phase: 17-stop-the-bleeding*
*Completed: 2026-10-14*
