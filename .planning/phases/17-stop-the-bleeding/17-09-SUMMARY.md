---
phase: 17-stop-the-bleeding
plan: "09"
subsystem: uninstall
tags: [uninstall, removal-proof, symlink, opt-dir, safe-deletion, tui, cli]

requires:
  - phase: 17-02
    provides: shared test-fixture patterns (public fixture builders, scratch-HOME sandboxing)
  - phase: 17-06
    provides: Sublime member/bin_name registry correction (D-02) that link_name depends on
provides:
  - download.link_name(method, member) — one link-naming rule for install, update and uninstall
  - uninstall._download_link — the one link lookup shared by plan_uninstall and plan_removal
  - RemovalPlan + plan_removal — the D-04 archive-layout removal proof
  - strict classify_tools — the Uninstall view offers only proven artifacts
  - strict run_uninstall — `--yes` deletes only proven artifacts and prints the manual list
  - render.render_remove_yourself — the "remove it yourself" listing
  - tests/test_uninstall.py::plant_removal_fixtures — the public H3 fixture tree
affects: [17-13 (e2e pass2 uninstall), phase-19 (receipts restore app-kind removability), doctor]

actuals:
  tokens: 52500
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "proof-by-layout: deletion requires a symlink resolving to a regular file inside the same tool's opt dir"
    - "one predicate for TUI rows and the --yes CLI path (plan_removal), pinned by a same-set test"

key-files:
  created:
    - .planning/phases/17-stop-the-bleeding/17-09-SUMMARY.md
  modified:
    - installer/uninstall.py
    - installer/download.py
    - installer/app.py
    - installer/render.py
    - tests/test_uninstall.py
    - tests/test_app.py
    - tests/test_render.py

key-decisions:
  - "Removal proof is one predicate in plan_removal: link.is_symlink() and resolved.is_file() and resolved.is_relative_to(opt_dir(name).resolve()) (D-04)"
  - "plan_uninstall stays lenient (ownership evidence for version_status.py and setup.py); its only change is naming the link via _download_link/link_name"
  - "App bundles, raw files, uv/pip files and shared files are 'remove it yourself' until Phase 19 receipts"
  - "classify_tools routes unproven-but-matching tools to MANAGED with a 'remove it yourself:' hint; no new UninstallState member"

patterns-established:
  - "plant_removal_fixtures: one public fixture tree shared by TUI-row tests and CLI-path tests so both paths provably run on identical trees"
  - "render_remove_yourself names paths only — never sudo/pkexec/doas"

requirements-completed: [SAFE-03]

coverage:
  - id: D1
    description: "A tool is removable only when bin link is a symlink resolving to a regular file inside its own opt dir; uv ruff, pip yq and shared drawio produce 0 deletions and are listed as remove-it-yourself"
    requirement: SAFE-03
    verification:
      - kind: unit
        ref: "tests/test_uninstall.py#test_plan_removal_proves_only_the_archive_layout"
        status: pass
      - kind: unit
        ref: "tests/test_uninstall.py#test_classify_rows_follow_the_removal_proof"
        status: pass
      - kind: unit
        ref: "tests/test_app.py#test_run_uninstall_deletes_only_proven_artifacts"
        status: pass
    human_judgment: false
  - id: D2
    description: "A link into another tool's opt dir is not removed; no matches means empty plan; a second --yes run deletes nothing"
    requirement: SAFE-03
    verification:
      - kind: unit
        ref: "tests/test_uninstall.py#test_plan_removal_rejects_a_link_into_another_tools_opt_dir"
        status: pass
      - kind: unit
        ref: "tests/test_uninstall.py#test_plan_removal_with_no_matches_is_empty"
        status: pass
      - kind: unit
        ref: "tests/test_app.py#test_second_yes_run_deletes_nothing"
        status: pass
    human_judgment: false
  - id: D3
    description: "TUI and --yes CLI delete the identical proven set from the same fixture tree"
    requirement: SAFE-03
    verification:
      - kind: unit
        ref: "tests/test_uninstall.py#test_tui_and_cli_delete_the_same_set"
        status: pass
    human_judgment: false
  - id: D4
    description: "The manual list names paths without any privilege-escalation command; empty list prints nothing"
    requirement: SAFE-03
    verification:
      - kind: unit
        ref: "tests/test_render.py#test_render_remove_yourself_lists_paths_without_escalation"
        status: pass
    human_judgment: false
  - id: D5
    description: "plan_uninstall names the link like install (bin_name first via link_name); a failed opt-dir delete leaves the remainder listed on the next plan"
    requirement: SAFE-03
    verification:
      - kind: unit
        ref: "tests/test_uninstall.py#test_plan_uninstall_names_the_link_like_install"
        status: pass
      - kind: unit
        ref: "tests/test_uninstall.py#test_failed_opt_dir_delete_leaves_the_remainder_listed"
        status: pass
    human_judgment: false

duration: 52min
completed: 2026-10-14
status: complete
---

# Plan 17-09 Summary

**Removability is now proven by the archive layout — one predicate (`plan_removal`) gates both the Uninstall TUI and `make uninstall --yes`; uv/pip files, foreign links, shared files and app bundles are listed as "remove it yourself" and never deleted (SAFE-03/H3).**

## Performance

- **Duration:** 52 min
- **Tasks:** 2 of 2
- **Files modified:** 7 (+1 summary)

## Accomplishments
- `installer/download.py::link_name(method, member)` is the one link-naming rule (`bin_name` first, else member basename), used by `install_download`, `update_download` and the new `uninstall._download_link` — install, update and uninstall can no longer drift on what a link is called (Sublime's `subl` is now findable).
- `RemovalPlan`/`plan_removal` prove a download method only when the link is a symlink resolving to a regular file inside that same tool's `opt_dir(<link>)`; everything else the lenient `plan_uninstall` matches lands in `yourself`. `plan_uninstall` itself stays lenient for its ownership-evidence callers (`version_status.py`, `setup.py`).
- `classify_tools` (TUI rows) and `run_uninstall` (`--yes` path) both consume `plan_removal`; `run_uninstall` prints the manual list via the new `render.render_remove_yourself` in both the preview and the nothing-to-uninstall early return (which stays confirm-free), and is idempotent — a second `--yes` run deletes nothing and returns `[]`.

## Task Commits

1. **Task 1: one predicate decides removability in the TUI rows** — `c867a5c` (feat)
2. **Task 2: `--yes` uses the same proof, prints the manual list, is idempotent** — `5c559ae` (feat)

## TDD RED evidence (trimmed)

Task 1 (before implementation):
```
tests/test_uninstall.py:6: in <module>
    from installer.download import link_name
E   ImportError: cannot import name 'link_name' from 'installer.download'
```
Behavioral RED against the old lenient code (plain pip `yq` file):
```
BEHAVIORAL RED: removable True
```

Task 2 (before implementation):
```
FAILED tests/test_render.py::test_render_remove_yourself_lists_paths_without_escalation - ImportError
FAILED tests/test_app.py::test_run_uninstall_deletes_only_proven_artifacts - AssertionError
FAILED tests/test_app.py::test_run_uninstall_with_only_unproven_matches_still_lists_them
FAILED tests/test_app.py::test_second_yes_run_deletes_nothing
FAILED tests/test_uninstall.py::test_tui_and_cli_delete_the_same_set
FAILED tests/test_uninstall.py::test_failed_opt_dir_delete_leaves_the_remainder_listed
```

## Verify-command results

- Task 1 `<verify>`: `uv run pytest tests/test_uninstall.py -q --no-cov -k "plan_removal or classify_rows_follow or names_the_link_like_install or link_name_prefers"` — 11 passed; neighbor suites (uninstall, e2e, download, wizard_app, version_status, ownership) all green.
- Task 2 `<verify>`: 6 targeted tests passed; `tests/test_app.py tests/test_render.py tests/test_uninstall.py tests/test_uninstall_e2e.py tests/test_setup.py` all green.
- All acceptance greps pass (`plan_removal`/`RemovalPlan`/`link_name`/`_download_link`×3/`link_name(`×1 in uninstall.py/`plant_removal_fixtures`/classify range has 1 `plan_removal(` and 0 `plan_uninstall(`; run_uninstall range likewise; no `UninstallState`/wizard_app/enums changes in either commit).
- Final: `make validate` green; `make test` green — 3534 passed, 4 skipped (pre-existing platform skips), coverage 95.90% ≥ 90% floor.

## Deviations from Plan

None — plan executed exactly as written. (Two test-authoring fixes during Task 2 — restoring `shutil.rmtree` via a second `monkeypatch.setattr` instead of `monkeypatch.undo()` so the `Path.home` patch survived, and reusing one kwargs dict across the two `run_uninstall` calls in `test_second_yes_run_deletes_nothing` so the second call could not rewrite `~/.myshellrc` — were made before the commit, inside the planned files.)

## Issues Encountered
- One transient self-inflicted loss: a `git checkout` used while capturing RED evidence reverted the Task 1 test edits; they were re-applied verbatim before any commit. No impact on the committed tree.
- Existing `test_run_uninstall_aborts_when_declined` plants a link to the opt DIR (never a proven layout); it stays green because after the change that tree takes the confirm-free early return and still returns `[]`. Left as-is: its subject is the declined path, and its fixture is now covered by the strict-shape tests.

## Notes for the orchestrator
- e2e pass2 (plan 17-13): TRACER_UNINSTALL_OK now proves only the proven-owned set was removed; reinstall `already=` is expected to rise above the Step-0 baseline. Record before/after numbers as the Phase 19 baseline per the plan's `<verification>`.
- Phase 19 receipts must restore app-kind removability; today app bundles and their CLI links are always "remove it yourself".

## Next Phase Readiness
- Wave-3 neighbor 17-10 (wizard_app) untouched and green; `tests/test_wizard_app.py` plants no bin fixtures and needed no change.

---
*Phase: 17-stop-the-bleeding*
*Completed: 2026-10-14*
