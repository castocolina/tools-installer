# Phase 24 Plan 03: skill-judge before and after

Target: `.claude/skills/tool-onboarding/SKILL.md`. Rubric `rubric_version` 4, `spec_sha`
`69ef37e9424c0a7ea9dd2293b559e43ec8176379` (skill-judge, `judge: direct`).

## Baseline (fresh, 2026-11-08)

A fresh run on the unedited skill (HEAD 9e2ff7b), before the first edit of this plan. It was
produced by the previous executor of this plan, which stopped right after the judge and changed
nothing; the orchestrator handed its scores over, so the per-dimension numbers below are that run's
and the JSON line is rebuilt from them (the raw line was not kept). Findings listed are the two main
ones that run reported.

Verdict: 67.2% (grade D), 84/125.

```json
{"skill":"tool-onboarding","judge":"direct","rubric_version":4,"spec_sha":"69ef37e9424c0a7ea9dd2293b559e43ec8176379","scores":{"D1":15,"D2":13,"D3":11,"D4":12,"D5":13,"D6":12,"D7":0,"D8":8},"max":{"D1":20,"D2":15,"D3":15,"D4":15,"D5":15,"D6":15,"D7":15,"D8":15},"total":84,"max_total":125,"percent":67.2,"grade":"D","findings":[{"id":"D7-1","dimension":"D7","severity":"high","file":".claude/skills/tool-onboarding/SKILL.md","line":null,"evidence":"No evals/ directory in the supplied files","fix":"Add evals/evals.json and evals/trigger-queries.json"},{"id":"D8-1","dimension":"D8","severity":"high","file":".claude/skills/tool-onboarding/SKILL.md","line":118,"evidence":"Pre-Phase-22 removal text: 'do NOT claim the tool is removable' (also lines 90 and 195)","fix":"Rewrite to the L1/L2/L3 removal contract"}]}
```

Context only, never the baseline (D-24): 23.2 recorded an after-score of 72.0% (grade C) for its
own edit of this skill (before 71.2%, 23.2-05-SUMMARY). That run used an earlier skill text and is
not comparable.

## Round 1 (after the edit)

After the edit: step 4b rewritten (method table with a `cargo_distrobox` row, a parsed TOML example,
L1/L2/L3 and one line per `paths`, `remove`, `update`, `writable_prefix`, `config_paths`), the false
"Then check the platform can express it" paragraph gone, step 4 item 4 and the step 8 classifier
bullet on the Phase 22 contract, the step 2 skill-pack clause and the Overview "removal path for a
script install" clause dropped, the step 7 terminal bullet. D8 gains the most (stale text gone, one
runnable-shaped example per param); D7 stays 0 (no `evals/`, outside this plan's files).

```json
{"skill":"tool-onboarding","judge":"direct","rubric_version":4,"spec_sha":"69ef37e9424c0a7ea9dd2293b559e43ec8176379","scores":{"D1":15,"D2":13,"D3":11,"D4":12,"D5":13,"D6":12,"D7":0,"D8":11},"max":{"D1":20,"D2":15,"D3":15,"D4":15,"D5":15,"D6":15,"D7":15,"D8":15},"total":86,"max_total":125,"percent":68.8,"grade":"D","findings":[{"id":"D1-1","dimension":"D1","severity":"low","file":".claude/skills/tool-onboarding/SKILL.md","line":41,"evidence":"Step 1 restates 'do online research ... cite what you found'","fix":"Cut step 1 to the one non-obvious rule: cite sources in # Verified"},{"id":"D2-1","dimension":"D2","severity":"low","file":".claude/skills/tool-onboarding/SKILL.md","line":38,"evidence":"Nine numbered steps with no ordering rationale between 4b and 8","fix":"State which step blocks the next (removal before the entry, classifiers before the block)"},{"id":"D3-1","dimension":"D3","severity":"medium","file":".claude/skills/tool-onboarding/SKILL.md","line":246,"evidence":"Common Mistakes bullets name the miss but few give the reason","fix":"Add a because-clause to each bullet, as the Policies bullet has"},{"id":"D4-1","dimension":"D4","severity":"medium","file":".claude/skills/tool-onboarding/SKILL.md","line":3,"evidence":"description has WHAT and WHEN but no boundary for near-miss tasks (editing installer/*.py)","fix":"Use when adding or reviewing a [[tool]] block in installer/registry.toml ... Not for editing installer/*.py code."},{"id":"D5-1","dimension":"D5","severity":"low","file":".claude/skills/tool-onboarding/SKILL.md","line":163,"evidence":"Step 6 points to .claude/architecture.md without saying which sections not to load","fix":"Name the one section to read"},{"id":"D6-1","dimension":"D6","severity":"low","file":".claude/skills/tool-onboarding/SKILL.md","line":135,"evidence":"remove example is illustrative: no registry entry ships one","fix":"Replace with a shipped example once an entry declares remove"},{"id":"D7-1","dimension":"D7","severity":"high","file":".claude/skills/tool-onboarding/SKILL.md","line":null,"evidence":"No evals/ directory","fix":"Add evals/evals.json and evals/trigger-queries.json"},{"id":"D8-1","dimension":"D8","severity":"medium","file":".claude/skills/tool-onboarding/SKILL.md","line":105,"evidence":"cargo_distrobox row and example describe a kind that lands with plan 24-01, not yet in installer/model.py at this commit","fix":"Re-check the example against METHOD_PARAMS once 24-01 is merged"}]}
```

## Final

Verdict: 68.8% (grade D), 86/125.

final 86 >= baseline 84

Per dimension, baseline to final: D1 15 to 15, D2 13 to 13, D3 11 to 11, D4 12 to 12, D5 13 to 13,
D6 12 to 12, D7 0 to 0, D8 8 to 11.

Not done here, by design of this plan: D7 (`evals/` for the skill), the D4 description boundary and
the D3 reasons on Common Mistakes bullets. They are the next points to gain if the skill is judged
again.
