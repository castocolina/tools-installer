---
phase: 24-onboarding-through-the-skill-and-e2e
plan: "03"
subsystem: onboarding-skill
tags: [skill, docs, skill-judge, cargo_distrobox, lifecycle]
requires: []
provides:
  - tool-onboarding skill documents the Phase 22 lifecycle params and the cargo_distrobox kind
  - 24-SKILL-JUDGE.md baseline and final verdicts
affects: [24-01 (the skill example mirrors its param shapes)]
tech-stack:
  added: []
  patterns: [heading-anchored doc tests that parse the skill's own TOML example]
key-files:
  created:
    - .planning/phases/24-onboarding-through-the-skill-and-e2e/24-SKILL-JUDGE.md
  modified:
    - .claude/skills/tool-onboarding/SKILL.md
    - tests/test_docs.py
    - docs/catalog-unsupported-tools.md
    - .planning/phases/24-onboarding-through-the-skill-and-e2e/24-SPEC.md
    - .planning/REQUIREMENTS.md
decisions:
  - "The cargo_distrobox example is a `[[tool]]` plus `[[tool.method]]` pair so tomllib yields a tool list the doc test can walk"
  - "The `remove` example uses `{omz_root}/tools/uninstall.sh`, the only placeholder SCRIPT_ROOTS allows, marked illustrative (no entry ships `remove`)"
metrics:
  duration: "about 40 minutes"
  completed: 2026-11-13
status: complete
actuals:
  tokens: 14000
  tasks: 2
  commits: 2
plan_head_before: 9e2ff7b1716b5d34b7f959f682d0bf15e0c74e25
plan_head_after: 642467885ab120bd725976d8c33e2008c4db66ef
commits: 2
---

# Phase 24 Plan 03: Onboarding skill lifecycle params and cargo_distrobox Summary

The tool-onboarding skill now teaches removal by receipt (L1/L2/L3) with one TOML line per lifecycle param (`paths`, `remove`, `update`, `writable_prefix`, tool-level `config_paths`) and a parsed `cargo_distrobox` example; skill-judge went from 84/125 to 86/125 (baseline 67.2%, final 68.8%), so `final >= baseline` holds.

## Commits

- `0fcea8d` docs(24-03): onboarding skill covers lifecycle params and cargo_distrobox; judge before and after (Task 1)
- `6424678` docs(24-03): Alacritty builds in a Distrobox; terminfo goes to ~/.terminfo (Task 2)

## What changed

- SKILL.md step 4b: method table with a `cargo_distrobox` row and a separate `script` row, a fenced TOML example (Alacritty-shaped: `repo`, `image`, `packages`, two `artifacts` tables, `config_paths`), the L1/L2/L3 paragraph and four param lines; the false "do NOT claim the tool is removable" paragraph is gone.
- Step 4 item 4 and step 8's `removal_plan` bullet speak the Phase 22 contract; the Overview no longer lists "a removal path for a script install" as a platform gap (the same stale idea, found beyond the plan's list); step 2 no longer mentions skill packs; step 7's terminal bullet names the zsh terminal sync and `post_install` tuning, never a Policies row. 23.2's rule text is untouched and pinned.
- tests/test_docs.py: six tests (`names_every_lifecycle_param`, `keeps_the_policies_rule_verbatim`, `has_no_skill_pack_text`, `terminal_bullet`, `has_a_cargo_distrobox_example`, `has_no_pre_phase_22_removal_text`) and a `_skill_section` helper.
- docs/catalog-unsupported-tools.md: the Alacritty section rewritten. No test pinned the old wording.
- 24-SPEC.md (R3 bullet, acceptance, R3 edge row; R8 note) and REQUIREMENTS.md ONB-06: dated `*(amended 2026-11-08, ...)*` notes, original words kept.

## RED (Task 1)

`uv run pytest tests/test_docs.py -k "tool_onboarding" -q --no-cov -n 0` before any skill edit: 5 failed, the existing tests passed:

```
FAILED tests/test_docs.py::test_tool_onboarding_skill_names_every_lifecycle_param
FAILED tests/test_docs.py::test_tool_onboarding_skill_has_no_skill_pack_text
FAILED tests/test_docs.py::test_tool_onboarding_skill_terminal_bullet - Asser...
FAILED tests/test_docs.py::test_tool_onboarding_skill_has_a_cargo_distrobox_example
FAILED tests/test_docs.py::test_tool_onboarding_skill_has_no_pre_phase_22_removal_text
```

(`keeps_the_policies_rule_verbatim` passed already: it is a regression pin of text that exists. Failures were
`AssertionError: 4b has no fenced toml block with kind = cargo_distrobox` and
`'removal-manifest' is contained here`.)

## Judge result

Baseline 84/125 (67.2%, D), from the previous executor's fresh run on the unedited skill, passed in by the orchestrator. Final 86/125 (68.8%, D) after the edit, one round. D8 8 to 11; D7 stays 0 (no `evals/`). 23.2's 72.0% (C) is context only. Details and both verdict lines in 24-SKILL-JUDGE.md.

Honest limits: the baseline JSON line is rebuilt from the handed-over scores (the raw line was not kept), and the final verdict is my own in-session application of the rubric (I read `rubric.md` in full but not the bundled spec copies it cites). The +2 margin is small; a stricter judge could differ, and D7 (0/15) is the cheap upside if the user wants the grade to move.

## Orchestrator: ROADMAP amendment

Apply after the merge (this plan did not touch ROADMAP.md). In `.planning/ROADMAP.md`, Phase 24 criterion 2, replace the words

old: `with its desktop entry, icon and terminfo under `~/.local/share`, all recorded in the receipt`

new: `with its desktop entry and icon under `~/.local/share` and its terminfo under `~/.terminfo`, all recorded in the receipt`

and append at the end of that criterion line:

`*(amended 2026-11-08, 24 D-07: the terminfo goes to `~/.terminfo`, not `~/.local/share/terminfo`; ncurses 6.6 and Alacritty 0.17 do not search `~/.local/share/terminfo`, reproduced in a scratch HOME)*`

(The old line is ROADMAP.md line 500, ending in the existing 2026-11-07 D-19 amendment.) ONB-03 can be marked complete: the plan closed with `final >= baseline`.

## Deviations from Plan

**1. [Rule 2 - Missing] Overview clause on script removal** — the Overview listed "a removal path for a script install" as a capability the platform lacks; with `paths`/`remove` that is false. Dropped from the same SKILL.md edit (commit 0fcea8d). Also added a numbered `cargo_distrobox` option to step 4's method list so the new kind is reachable from the choice step, not only from 4b.

**2. [Rule 3 - Blocking] Test line length** — three new test lines exceeded ruff's 100 columns; reflowed. No gate was silenced.

ROADMAP.md was not edited, per the orchestrator's instruction (the plan lists it in `files_modified`).

## Known Stubs

None. The `remove` example and the `cargo_distrobox` example describe things not yet in `installer/model.py` / the registry at this commit (24-01 lands the kind in parallel); both are marked as such in the skill text or judge findings (D8-1, D6-1). Re-check the example against `METHOD_PARAMS["cargo_distrobox"]` after 24-01 merges.

## Threat Flags

None.

## Self-Check: PASSED

- SKILL.md, tests/test_docs.py, 24-SKILL-JUDGE.md, docs/catalog-unsupported-tools.md, 24-SPEC.md, REQUIREMENTS.md exist and changed; commits 0fcea8d and 6424678 are ancestors of HEAD.
- `rg -n -i "skill.pack|skill_lifecycle"` on SKILL.md exits 1; the 23.2 Policies sentences are present once each; `removal-manifest` and `download and app kinds only` count 0.
- `make validate` and `make test` (6038 passed, coverage 96.19%) exit 0 on both task trees.
