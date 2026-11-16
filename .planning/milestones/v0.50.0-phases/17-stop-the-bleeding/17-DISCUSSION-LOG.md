# Phase 17: Stop the bleeding - Discussion Log (Assumptions Mode)

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the analysis.

**Date:** 2026-10-13
**Phase:** 17-stop-the-bleeding
**Mode:** assumptions (`--analyze --all --batch`; the typed flag "—asumotions" was read as assumptions mode)
**Areas analyzed:** Link safety and removal proof; Atomic writes and failure reporting; Runtime safety; Doctor, CI and governance

## Assumptions Presented

The analyzer was `gsd-assumptions-analyzer` (sonnet) with the jev-fast-decision skill injected. It read about 106 tool calls' worth of code.

### Link safety and removal proof
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| `is_file()` guard plus `atomic.replace_symlink` at 3 sites; fix Sublime `member` | Confident | download.py:189-190,403-404; apps.py:100; atomic.py:117; registry.toml:2270,2278 |
| graphify branch decided by an isolated-HOME container probe | Confident (approach) / Unclear (outcome) | postinstall.py:256-274; TA H2, O14 |
| One archive-layout predicate for the TUI and `--yes` | Confident | uninstall.py:56-97,260-339; registry raw methods (yq :450, direnv :616) |
| App-kind bundles stay removable under the interim proof | Unclear | uninstall.py:33-53; tests/test_uninstall.py:184-276. Laya: archive_layout_covered p=0.70, confidence 0.12 (advisory) |

### Atomic writes and honest failure
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| `atomic_write_text` at the guards/tweaks rc and shim writes | Confident | guards.py:388..564; tweaks.py:254,297,308; atomic.py:34-50 |
| `clean_rc_duplicates` byte re-check | Confident | app.py:418-448 |
| Worker `except Exception`, failure state carried to the exit code | Likely | execute_screen.py:593-656; session.py:105-113; setup.py:1275,1509; ui_common.py:52-55 |

### Runtime safety
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| `move_link_mode` helper in policy.py | Likely | wizard_app.py:2179-2194; policy.py:121-157; uninstall.py:401-444 |
| `start_new_session=True` plus codex env | Confident | run.py:232-240; registry env pattern |
| Catch `UnicodeDecodeError`; warn through a separate probe | Confident / Likely | settings.py:44-63; 21 tests |
| `execute=` on every route | Confident | setup.py:755,1166-1211,1234-1239 |

### Doctor, CI and governance
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| Generic broken-link scan in doctor.py | Likely | doctor.py:1-27; locations.py:55 |
| CI fixes: `mapfile` loop; `time`/dash; width; barrier | Confident / Likely | prune-tmp-linux.sh:101; test_shellrc.py ~2645 |
| Branch protection and R13 are process actions | Confident | 16-SECURITY.md (stops at T-16-19), 16-VALIDATION.md (2026-10-10) |

## Corrections Made

### App-kind removal (Unclear → resolved from the SPEC, not asked)
- **Original assumption:** app bundles stay removable.
- **Resolution:** demote them to "remove it yourself" for the interim. 17-SPEC R3 lists "app files" among the cases that are not deleted.

### Settings warning
- **Original assumption:** a separate `settings_warning(path)` probe (smallest diff).
- **User correction:** "pensemos [no] en lo mas facil sino en lo mejor" — choose the best design, not the easiest, for this batch and future ones.
- **Decision:** a single read and parse that returns a typed result with the warning; the store keeps an invalid flag; all 7 callers and the tests are updated.

### dash `time` test
- **Original assumption:** dash forks a subshell under `time`; drop `sh` from the case.
- **Evidence (throwaway ubuntu container):** `/usr/bin/sh -> dash`; `sh -c "time . f"` prints `time: not found` and does not source; bash sources it.
- **Decision (best over easiest):** keep `sh`, and assert each shell's real behaviour; the classifier refuses in all three.

### Confirmed as recommended (user, batch of 4)
- `Summary` fields for the exit code (D-08); the `move_link_mode` helper in policy.py (D-09); the generic Doctor scan (D-13).

## Trade-off tables shown (`--analyze`)

| # | Decision | A (rec.) | B | Trade-off |
|---|---|---|---|---|
| 1 | Exit-code propagation | `Summary` fields | `UnifiedApp` attribute | One read point vs a second source |
| 2 | Link-mode move | helper in policy.py | inside `set_link_mode` | Architecture rule and scoped blast radius vs every caller |
| 3 | Settings warning | separate probe | typed return | Untouched signature vs single read and parse (user chose the best: typed return) |
| 4 | Doctor scan | generic `bin_dir` | registry links only | Catches foreign links vs names the exact tool |

## Reviewed Todos

- Dangling pnpm shims in Doctor (score 0.9): not folded; it belongs to Phase 21 (UI-07).

## Best-over-easy audit (second pass, 2026-10-13)

The user asked: "Quiero estar seguro las decisiones fueron las mejores y no las mas faciles". All 18 decisions were re-checked against the current code (codegraph: `_build_app`, `ExecuteInputs`, `Summary`), and the two suspect ones were screened with jev.

| Decision | Verdict | Evidence / jev |
|---|---|---|
| D-01..D-07, D-09, D-13..D-18 | Kept as best | Reuse the existing primitives; one predicate; boundary-level except; the SPEC locks D-04/D-06/D-09 semantics |
| D-08 `Summary` fields | **Refined**: id tuples (`not_attempted`, `update_failed`) plus `crash_error`, instead of booleans | Laya boolean_flags p=0.50 (needs fallback); TypeSafe outcome_id_tuples p=0.98; user confirmed |
| D-10 codex env | **Verified** | `codex/install.sh` lines 6 and 100: `CODEX_NON_INTERACTIVE` accepts 1/true/yes (the script was downloaded to scratch and deleted) |
| D-12 execute wiring | **Changed**: `_build_app` builds `ExecuteInputs`; the optional parameter is removed | It was the easy fix (pass at 4 sites). Laya factory_builds_it p=0.42 (needs fallback); TypeSafe factory_builds_it p=0.99; TA §7 says the same; user confirmed |
