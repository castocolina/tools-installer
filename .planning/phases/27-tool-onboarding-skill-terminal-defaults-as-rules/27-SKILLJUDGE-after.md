# Skill-judge after verdict - tool-onboarding

- Date: 2026-11-20
- Judge: a fresh subagent (opus, no prior context, never edited the skill) invoking the user-level `skill-judge` skill (rubric v4), read-only, on `.claude/skills/tool-onboarding/` at gsd/phase-27-tool-onboarding-skill-terminal-defaults-as-rules 24a73427; SKILL.md blob 5e3411f8d69a65e98d44d25dd3143bfa97467eb6

## Summary (as printed)

I ran skill-judge (rubric v4, judge slug `direct`) on `.claude/skills/tool-onboarding/` and changed nothing.

**tool-onboarding: 73.6% — grade C** (92 of 125)

| id | name | score | max |
|----|------|-------|-----|
| D1 | Knowledge Delta | 15 | 20 |
| D2 | Mindset, Procedures and Patterns | 13 | 15 |
| D3 | Anti-Pattern Quality | 13 | 15 |
| D4 | Specification Compliance | 13 | 15 |
| D5 | Progressive Disclosure | 11 | 15 |
| D6 | Freedom Calibration | 13 | 15 |
| D7 | Tests and Evals | 2 | 15 |
| D8 | Practical Usability | 12 | 15 |

**Top three findings**

1. **D7 (-13, high): there is no `evals/` directory.** The skill folder holds only `SKILL.md` (331 lines). `tests/test_tool_onboarding_skill.py` only checks that the text and the terminal table match the registry. It does not test what the skill produces or when it triggers. **Fix:** add `evals/evals.json` with 3 realistic prompts, each with assertions that can be checked:
   - a Linux-only CLI installed by a vendor script (assert `paths` and `remove` are set and a `# Verified` line exists);
   - a macOS app shipped only as a `.dmg` (edge case: assert it is recorded as a platform gap, not approximated);
   - a review of an existing terminal entry (assert steps 3, 4b and 8 are run and its table row is updated).

   Also add `evals/trigger-queries.json` with about 20 queries. Make the negatives near-misses: a catalog sweep (catalog-audit), "bump the pins" (`make verify-registry`), and "install kitty on my laptop".
2. **D1 (-5, medium): repetition and generic content dilute the expert material.**
   - The rule that the four terminal defaults are never asked appears five times (lines 190, 194, 253, 284, 316).
   - Step 1 (lines 44-51) is generic "research before writing" advice the model already follows.
   - The table cells hold short-lived roadmap status ("planned (phase 29)", "unverified").

   **Fix:** state the never-asked rule once in step 7 and delete the other copies. Cut step 1 to one line: cite the vendor source in `# Verified`. Keep phase status in the roadmap, not in the always-loaded body.
3. **D5 (-4, medium): about 40 lines of terminal-only content load on every run.** Lines 192-232 (defaults, the per-terminal table, Conflicts, macOS testing) load even when the tool being onboarded is an MCP server or a CLI. **Fix:** move them to `references/terminal-defaults.md`. At the start of step 7, add: "Read `references/terminal-defaults.md` when the entry's category is terminal or editor; do NOT load it for other tools." Point the table test at the new path.

**Other findings**
- **D8 (-3):** lines 60-61 contradict each other. Line 60 says "the catalog installs no skills", while line 61 says to prefer the marketplace, or symlinks into the host's skills dir. An agent onboarding a skill pack gets opposite instructions.
- **D4 (-2):** the 854-character description lists internal mechanics, says nothing about when to trigger if the user does not name the registry, and does not name `catalog-audit` as the neighbouring skill. The full replacement text is in the JSON.
- **D2 (-2):** at 331 lines the skill runs past the ~200-line process pattern because a large data table is embedded in step 7.
- **D3 (-2):** line 315 gives no reason, and line 317 repeats step 7(b).
- **D6 (-2):** line 123 asks for a container install and a list of what it wrote, with no exact commands.

## Verdict (verbatim)

```json
{"skill":"tool-onboarding","judge":"direct","rubric_version":4,"spec_sha":"69ef37e9424c0a7ea9dd2293b559e43ec8176379","scores":{"D1":15,"D2":13,"D3":13,"D4":13,"D5":11,"D6":13,"D7":2,"D8":12},"max":{"D1":20,"D2":15,"D3":15,"D4":15,"D5":15,"D6":15,"D7":15,"D8":15},"total":92,"max_total":125,"percent":73.6,"grade":"C","findings":[{"id":"D7-1","dimension":"D7","severity":"high","file":".claude/skills/tool-onboarding/SKILL.md","line":null,"evidence":"The skill directory contains only SKILL.md; no evals/evals.json or evals/trigger-queries.json. tests/test_tool_onboarding_skill.py checks structure and table drift, not output or triggering","fix":"Add evals/evals.json with 3 realistic prompts and verifiable assertions (Linux-only vendor-script CLI: paths and remove declared plus a # Verified line; macOS .dmg-only app edge case: recorded as a platform gap; review of an existing terminal entry: steps 3, 4b and 8 run and the table row updated), and evals/trigger-queries.json with about 20 queries, 8-10 positive and 8-10 near-miss negatives (catalog sweep, make verify-registry pin bump, install kitty on this machine)"},{"id":"D1-1","dimension":"D1","severity":"medium","file":".claude/skills/tool-onboarding/SKILL.md","line":190,"evidence":"'Only extras beyond them are offered to the developer' is restated at lines 194, 253, 284 and 316, and the table cells carry roadmap status ('planned (phase 29)', 'unverified')","fix":"State the defaults-are-rules-never-asked rule once in step 7, delete the other four restatements, and keep phase status in the roadmap rather than the always-loaded body"},{"id":"D1-2","dimension":"D1","severity":"low","file":".claude/skills/tool-onboarding/SKILL.md","line":44,"evidence":"'Research first — never write from memory ... do online research (vendor docs, release page, README, package-manager listings) BEFORE choosing anything'","fix":"Reduce step 1 to one line: cite the vendor source for OS/arch, install and uninstall in the # Verified comment; the model already researches before writing"},{"id":"D5-1","dimension":"D5","severity":"medium","file":".claude/skills/tool-onboarding/SKILL.md","line":192,"evidence":"Lines 192-232 (terminal and IDE defaults, closed per-terminal table, Conflicts, Testing macOS behavior) load on every run, including onboarding an MCP server or a CLI","fix":"Move them to references/terminal-defaults.md and open step 7 with: 'Read references/terminal-defaults.md when the entry's category is terminal or editor; do NOT load it for other tools.' Point tests/test_tool_onboarding_skill.py at the new path"},{"id":"D8-1","dimension":"D8","severity":"medium","file":".claude/skills/tool-onboarding/SKILL.md","line":60,"evidence":"Line 60: 'the catalog installs no skills'; line 61: 'prefer the marketplace route ... use symlinks into the host's skills dir only when no marketplace exists'","fix":"Pick one branch: either 'Skill and agent packs are out of catalog scope: stop and report' and delete the marketplace-vs-symlink row and its Common Mistakes item, or scope line 60 to the hosts and pack kinds the catalog does install"},{"id":"D4-1","dimension":"D4","severity":"low","file":".claude/skills/tool-onboarding/SKILL.md","line":3,"evidence":"854-character description lists internal mechanics ('marketplace vs symlink', 'keep-config vs delete-all policy') but has no trigger clause for users who do not name the registry, and does not name the catalog-audit neighbour","fix":"Onboard or review one [[tool]] entry in installer/registry.toml: research the tool, pick an install method per OS and architecture (brew, cask, apt/dnf/pacman, release asset, bun/uv-tool, vendor script, cargo_distrobox), plan its per-method removal and config policy, set tier, requires and postinstall/post_install hooks, and apply the four terminal and IDE defaults as rules. Use when asked to add, onboard, package or support a new CLI, app, terminal, editor or LLM tool in the installer catalog, or to check why an existing entry lacks a platform, an uninstall path or a postinstall, even without naming registry.toml. Not for sweeping every entry against upstream (catalog-audit), checking release pins only (make verify-registry), or installing a tool on this machine."},{"id":"D2-1","dimension":"D2","severity":"low","file":".claude/skills/tool-onboarding/SKILL.md","line":209,"evidence":"Process-pattern skill at 331 lines (pattern target about 200) with a tool-style data table embedded in step 7","fix":"Keep SKILL.md as the phased process with checkpoints and move the terminal data table to a gated reference (see D5-1)"},{"id":"D3-1","dimension":"D3","severity":"low","file":".claude/skills/tool-onboarding/SKILL.md","line":315,"evidence":"'Shipping a non-terminal extra nobody asked for ... or skipping that question.** Offer, ask, record.' gives no reason; line 317 repeats step 7(b) verbatim in substance","fix":"Give line 315 its reason (an unrequested extra writes host config the developer must then find and revert) and delete line 317, which duplicates step 7(b)"},{"id":"D6-1","dimension":"D6","severity":"low","file":".claude/skills/tool-onboarding/SKILL.md","line":123,"evidence":"'run the vendor installer in a disposable container (scripts/detect-container-runtime.sh picks the runtime; never on the host) and list what it wrote'","fix":"Give the exact sequence: get the runtime from scripts/detect-container-runtime.sh, run the container with --rm, touch a stamp file, run the vendor installer, list new files with find / -xdev -newer <stamp>, and use that list as paths"}]}
```
