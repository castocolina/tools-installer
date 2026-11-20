# Skill-judge before verdict - tool-onboarding

- Date: 2026-11-20
- Judge: a fresh subagent (opus, no prior context, never edited the skill) invoking the user-level `skill-judge` skill (rubric v4), read-only, on `.claude/skills/tool-onboarding/` at gsd/phase-27-tool-onboarding-skill-terminal-defaults-as-rules 8a97ea70; SKILL.md last changed in 1bb31e00; SKILL.md blob 8fda04a7a1af006f1dcbdda82a8e759245e5f872

## Summary (as printed)

## skill-judge: `.claude/skills/tool-onboarding/` (judge: direct)

**69.6% — grade D** (87/125, rubric v4)

The skill directory holds only `SKILL.md` (268 lines). There is no `evals/`, `references/`, `scripts/` or `README.md`, and no `tests/skills/tool-onboarding/` in the repo.

| id | name | score | max |
|----|------|-------|-----|
| D1 | Knowledge Delta | 16 | 20 |
| D2 | Mindset, Procedures and Patterns | 13 | 15 |
| D3 | Anti-Pattern Quality | 10 | 15 |
| D4 | Specification Compliance | 12 | 15 |
| D5 | Progressive Disclosure | 12 | 15 |
| D6 | Freedom Calibration | 12 | 15 |
| D7 | Tests and Evals | 1 | 15 |
| D8 | Practical Usability | 11 | 15 |

### Top three findings

1. **D7 (-14, high): no evals at all.** The skill has no `evals/evals.json` and no `evals/trigger-queries.json`. `tests/test_docs.py` and `tests/test_catalog_audit_skill.py` only check the skill's wording; they do not show what the skill produces or when it triggers.
   - **Fix:** add `evals/evals.json` with about 3 realistic prompts, each with verifiable assertions. Suggested prompts:
     - a vendor-script tool on Linux arm64 (asserts `paths`/`remove`/`update` plus a `# Verified` note);
     - a cask on macOS plus a tarball on Linux;
     - an edge case where the schema cannot express the artifact (asserts a backlog gap, not a bent method).
   - Also add `evals/trigger-queries.json` with about 20 queries. Make `catalog-audit` and `make verify-registry` requests the near-miss negatives.

2. **D3 (-5, medium): no Gotchas section, and many mistakes carry no reason.** Lines 249-268 mostly restate the steps without a WHY, for example "Skipping the marketplace question for LLM tooling." The environment facts that catch people out are buried in prose:
   - two near-identical mechanisms: `postinstall`/`POSTINSTALL_HOOKS` (host wiring) versus `post_install`/`POST_INSTALL_HOOKS` (install tuning);
   - `{omz_root}` is the only placeholder a script argv may use;
   - a file with the right name is never proof we wrote it.
   - **Fix:** add a `## Gotchas` section with these facts and the consequence of each. Give every remaining Common Mistakes bullet its non-obvious reason, and delete the bullets that only restate a step.

3. **D8 (-4, medium): one fact is out of date, and the validation step names no commands.**
   - Line 131 says `remove` is a param "which no entry ships yet". In fact `installer/registry.toml:1595` (opencode, script method) ships `remove = ["opencode2", "service", "stop"]`.
   - Step 9 (lines 244-245) says only "validate with the repo's gates".
   - Line 171, "Walk the tree: `postinstall` hook / none.", is a broken sentence.
   - **Fix:** cite the opencode entry as the real L3 example. Replace step 9's validation line with an explicit check-and-fix loop: `make verify-registry`, `make validate`, `make test`, then the disposable-container install and removal check, re-run until all pass. Rewrite line 171 as a full sentence.

All other mechanisms the skill cites exist in code: `POSTINSTALL_HOOKS`, `POST_INSTALL_HOOKS`, `POST_INSTALL_ACTIONS`, `METHOD_PARAMS`, `removal_plan`, `present_hosts`, `is_installed`, `resolve_ownership`, `terminal_shell.py`, the architecture.md sections and the worked-example action names.

## Verdict (verbatim)

```json
{"skill":"tool-onboarding","judge":"direct","rubric_version":4,"spec_sha":"69ef37e9424c0a7ea9dd2293b559e43ec8176379","scores":{"D1":16,"D2":13,"D3":10,"D4":12,"D5":12,"D6":12,"D7":1,"D8":11},"max":{"D1":20,"D2":15,"D3":15,"D4":15,"D5":15,"D6":15,"D7":15,"D8":15},"total":87,"max_total":125,"percent":69.6,"grade":"D","findings":[{"id":"D7-1","dimension":"D7","severity":"high","file":".claude/skills/tool-onboarding/SKILL.md","line":null,"evidence":"Skill directory contains only SKILL.md: no evals/evals.json, no evals/trigger-queries.json; tests/test_docs.py and tests/test_catalog_audit_skill.py only assert wording","fix":"Add evals/evals.json with 3 prompts (vendor-script tool on Linux arm64; cask on macOS plus tarball on Linux; schema-gap edge case) with verifiable assertions (script method declares paths/remove/update, # Verified comment present, gap recorded instead of a bent method), and evals/trigger-queries.json with ~20 queries using catalog-audit and make verify-registry requests as near-miss negatives"},{"id":"D3-1","dimension":"D3","severity":"medium","file":".claude/skills/tool-onboarding/SKILL.md","line":255,"evidence":"'Skipping the marketplace question for LLM tooling.' - Common Mistakes bullets restate steps without reasons; no Gotchas section, and the postinstall vs post_install near-homonym is never flagged","fix":"Add a ## Gotchas section: postinstall/POSTINSTALL_HOOKS (host wiring in installer/postinstall.py) and post_install/POST_INSTALL_HOOKS (install tuning in installer/post_install.py) are different mechanisms; {omz_root} is the only script-argv placeholder; a same-named file is never ownership proof. Give each remaining Common Mistakes bullet its non-obvious why and drop pure restatements"},{"id":"D8-1","dimension":"D8","severity":"medium","file":".claude/skills/tool-onboarding/SKILL.md","line":131,"evidence":"'example per script param (from the registry, except `remove`, which no entry ships yet' - installer/registry.toml:1595 ships remove = [\"opencode2\", \"service\", \"stop\"]; step 9 line 244 says only 'validate with the repo's gates'","fix":"Cite the opencode script method as the real L3 remove example, and replace step 9's validation with a loop: make verify-registry, make validate, make test, then a disposable-container install+removal; fix and re-run until all pass. Rewrite line 171 'Walk the tree: `postinstall` hook / none.' as a full sentence"},{"id":"D1-1","dimension":"D1","severity":"low","file":".claude/skills/tool-onboarding/SKILL.md","line":249,"evidence":"'**Authoring from one OS.** Check every OS and arch the vendor ships for.' - Common Mistakes largely duplicates steps 1-7; step 1 (lines 41-48) is generic 'research online first' advice","fix":"Delete Common Mistakes bullets that duplicate a step and cut step 1 to one line naming what to cite in # Verified; keep only project-specific content"},{"id":"D2-1","dimension":"D2","severity":"low","file":".claude/skills/tool-onboarding/SKILL.md","line":43,"evidence":"'When ANY of the following is uncertain, do online research (vendor docs, release page, README, package-manager listings) BEFORE choosing anything' - generic procedure; the Process pattern has no explicit checkpoints between phases","fix":"Turn steps 3, 4b and 7 into explicit checkpoints (per-OS/arch method table complete; removal level decided per method; user answers on customizations recorded) before step 9"},{"id":"D4-1","dimension":"D4","severity":"medium","file":".claude/skills/tool-onboarding/SKILL.md","line":3,"evidence":"Description says 'or reviewing an existing entry' with no boundary against catalog-audit, whose description covers checking one existing entry against upstream; the boundary sits only in the body (line 37)","fix":"Use when adding a new tool to installer/registry.toml or reworking one [[tool]] block by hand: research what it is and which OS/arch it ships for, pick the install method per platform (brew, cask, apt/dnf/pacman, github_release, tarball, bun/uv-tool, vendor script, cargo_distrobox, marketplace vs symlink), define its removal (L1 manager, L2 receipt paths, L3 script remove, keep/delete config), tier, requires/recommends, postinstall host wiring and post_install tuning (terminal keybindings, shell integration, companion plugins), and the dated # Verified comment. Use even when the user only says 'add X to the catalog' or 'support Y on Linux arm64'. Not for auditing many entries or checking an existing entry against upstream (catalog-audit), or bumping release pins (make verify-registry)."},{"id":"D5-1","dimension":"D5","severity":"low","file":".claude/skills/tool-onboarding/SKILL.md","line":99,"evidence":"Step 4b (lines 99-149) inlines the per-kind removal table and two TOML examples needed only for script and cargo_distrobox methods","fix":"Move the cargo_distrobox and script param examples to references/removal-examples.md and gate it: 'Read references/removal-examples.md only when a method is script or cargo_distrobox'"},{"id":"D6-1","dimension":"D6","severity":"medium","file":".claude/skills/tool-onboarding/SKILL.md","line":110,"evidence":"'run the vendor installer in a disposable container and list what it wrote' - a host-mutation-risk step with no exact command, although the repo has scripts/detect-container-runtime.sh","fix":"Give the exact sequence: detect the runtime with scripts/detect-container-runtime.sh, run the vendor installer in a throwaway container, diff the filesystem, remove the container; never run it on the host"}]}
```
