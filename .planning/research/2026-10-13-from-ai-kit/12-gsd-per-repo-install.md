# 12 — GSD per-repo install: graphify conflict, install modes, migration, ownership

Date: 2026-10-13. Read-only research. Nothing was installed, uninstalled or edited. The only writes were a throwaway repro dir in the scratchpad, since deleted, and this report.

## 0. The brief's premise is partly out of date (verify first)

- `~/.claude/settings.json` (mtime 2026-10-13 12:34:40 -03) registers **no GSD hooks**. It has only 3 hooks: ai-kit `claude_session_start.py`, `herdr-agent-state.sh`, and `codegraph prompt-hook`. The backup `settings.json.bak` (Oct 9) has none either; it has orca hooks.
- A global GSD install **does** exist. `~/.claude/gsd-file-manifest.json` has `scope: global, version 1.16.0, timestamp 2026-10-13T13:39Z`, with 72 skills, 35 agents, 33 hook files and 787 `gsd-core/` files. The 28 `gsd-*` hook *files* sit in `~/.claude/hooks/`, but none is wired into `settings.json`, so they are inert.
- Two repos **already have local installs**: `ai-kit` and `tools-installer`. Each has `.claude/gsd-core` (1.16.0), 72 flat `commands/gsd-*.md`, 35 agents, hooks, and **19 GSD hook registrations in `.claude/settings.local.json`**. Their manifests say `scope: local`, installed 2026-10-09.
- Repos with `.planning/config.json` (`fd -H -t d -g .planning ~/git -d 3`): ai-kit, tools-installer, gitid, home-mobility, kitty-setup, wezterm-setup. `~/git/llm-env` has **no** `.planning/`, so it is a non-GSD repo.
- So the user's real state is: global skills/agents (no hooks) **plus** local installs in 2 of 6 repos. The docs say a global skill always wins the `/gsd-<name>` trigger over a local command (W028, see §2). So in ai-kit and tools-installer the *global* skills currently shadow the local commands.

## 1. The graphify conflict

### Finding: no GSD hook reacts to graphify in a non-GSD repo. The trigger is the `gsd-graphify` skill sitting next to `graphify`.

Evidence, hook by hook:
- `~/.claude/hooks/gsd-graphify-update.sh:40` runs `[ -f .planning/config.json ] || exit 0` as its very first gate. It is also PostToolUse/Bash-only, needs a HEAD-advancing git command (`:78-82`), the default branch (`:105-106`), and `graphify.enabled && graphify.auto_update` (`:109-116`). It never prints anything (`:32` "Returns 0 in all cases").
- `gsd-workflow-guard.js:177-186`: `workflowGuardEnabled()` returns false unless `.planning/config.json` exists **and** `hooks.workflow_guard` is truthy. None of the 6 repos sets `hooks.workflow_guard`, so the advisory never fires anywhere today.
- `gsd-prompt-guard.js:146-149` only scans Write/Edit into `.planning/` paths.
- Repro (scratchpad temp dirs, payloads fed on stdin to `~/.claude/hooks/*`):
  - In the non-GSD dir: `gsd-graphify-update.sh`, `gsd-workflow-guard.js` (both Write and Bash), `gsd-prompt-guard.js`, `gsd-session-state.sh` and `gsd-read-guard.js` all exit 0 with **empty output**.
  - In a GSD dir with `hooks.workflow_guard:true`: only `gsd-workflow-guard.js` prints, on a Write. It emits `"WORKFLOW ADVISORY ... Consider using /gsd-fast ... or /gsd-quick ..."`, which is the "ceremony" text. It is reachable **only** in a GSD repo with that opt-in.
  - `codegraph prompt-hook` on a `/graphify .` prompt: empty. The ai-kit `claude_session_start.py`: tool hints only, nothing about GSD.
- `~/.agents/AGENTS-TOOLING.md` and `~/.claude/CLAUDE.md` have no GSD/graphify coupling. The CLAUDE.md `# graphify` block only says to use `~/.claude/skills/graphify`.

What does produce GSD ceremony: the global skill `~/.claude/skills/gsd-graphify/SKILL.md` (re-created 2026-10-13 10:39 by the global reinstall).
- Its description is "Build, query, and inspect the project knowledge graph in .planning/graphs/".
- Step 1 (Config Gate) reads `.planning/config.json`. If the file is missing, it prints "Knowledge graph is disabled. To activate: node <runtime-home>/gsd-core/bin/gsd-tools.cjs config-set graphify.enabled true … Then run /gsd-graphify build".
- Step 3's build pipes `graphify update .` into `.planning/graphs/` plus gsd-tools snapshots.
- Both `graphify` and `gsd-graphify` are always in the global skill listing. In a budget-truncated listing (as in this very session) both appear as bare names with no description. A natural-language "graphify this" or a tab-completed `/g…graphify` can land on `gsd-graphify`. This mechanism is inferred: I could not find the exact incident transcript (searched `~/.claude/projects/**/*.jsonl` for `/graphify` prompts and the `GSD > GRAPHIFY` banner; no hit outside research sessions).

Historical second cause (confirmed): the 2026-09-09 llm-env session (`~/.claude/projects/-var-home-bazzite-git-llm-env/90f8b262-….jsonl`, lines 1368-1405).
- After an earlier `--uninstall --global`, the hook files were deleted but their `settings.json` registrations stayed.
- As a result, **every** Bash call in every repo errored with `gsd-graphify-update.sh: No such file or directory`. That was a global GSD graphify hook "firing" in a non-GSD repo.
- 1.16.0's `uninstall()` now strips GSD hooks from settings (`bin/install.js:9040-9073`, "Removed GSD hooks from settings").

Answer to "does it check `.planning/`?": yes. Every GSD hook checks `.planning/config.json` (or `.planning/` paths) before doing anything. The global-scope problem is about *skills* and *stale registrations*, not hook logic.

Fix that follows: removing the global install removes `gsd-graphify` from non-GSD repos. In GSD repos, the local `commands/gsd-graphify.md` and the global `graphify` skill are distinct and coexist.

## 2. GSD's supported install modes (gsd-core 1.16.0)

Sources:
- `~/.npm/_npx/4ed68bd1cad489d9/node_modules/@opengsd/gsd-core/bin/install.js` (14,852 lines);
- `gsd-core/bin/lib/runtime-name-policy.cjs`;
- https://raw.githubusercontent.com/open-gsd/gsd-core/main/docs/how-to/install-on-your-runtime.md.

### Global vs local (Claude)

The flags are `-g/--global` and `-l/--local` (`install.js:872-873`). They are mutually exclusive (`:14817`). `--config-dir` is not allowed with `--local` (`:14820`), and `--uninstall` requires a scope (`:14824`).

| Item | Global (`~/.claude`) | Local (`<repo>/.claude`) |
|---|---|---|
| Commands / skills | `skills/gsd-*/SKILL.md` | flat `commands/gsd-*.md` (`install.js:9843`, "#1367") |
| Agents | `agents/gsd-*.md` | `agents/gsd-*.md` |
| Engine | `gsd-core/` | `gsd-core/` (14 MB) |
| Hook files | `hooks/` | `hooks/` |
| Helper scripts | `scripts/` | `scripts/` |
| Hook registration | `settings.json` | `settings.local.json`, with `"$CLAUDE_PROJECT_DIR"/.claude/hooks/...` commands (`install.js:13123-13150, 13257`) |
| Bookkeeping | `gsd-file-manifest.json`, `gsd-install-state.json` | `gsd-file-manifest.json`, `gsd-install-state.json` |
| Worktree base | — | `worktree.baseRef: "head"` written into `settings.local.json` unless `workflow.use_worktrees:false` (`:13397-13420`) |

**Hooks can be project-scoped.** A local Claude install registers hooks only in the repo's `settings.local.json`. It even migrates GSD entries out of a shared `settings.json` (#338). Verified live in `ai-kit/.claude/settings.local.json` (19 entries).

**Includes.**
- Local installs bake absolute paths into commands and agents, e.g. `ai-kit/.claude/commands/gsd-execute-phase.md:41` has `@~/git/personal/ai-kit/.claude/gsd-core/workflows/execute-phase.md`.
- The gsd-tools resolver default is `CLAUDE_CONFIG_DIR:-~/git/personal/ai-kit/.claude` (`.claude/gsd-core/references/gsd-run-resolver.md:7`).
- `--relative-includes` writes project-relative includes instead (help text, `install.js:1225`).

**Updates.**
- The `gsd-check-update.js` SessionStart hook only checks npm in the background and writes a cache. It looks for a project `gsd-core/VERSION` first, then the global one (`gsd-check-update.js:59-68`). It never installs anything.
- Real updates go through `/gsd-update` (`gsd-core/workflows/update.md`). It resolves scope LOCAL/GLOBAL via `update-context` ("local-over-global", `update.md:79`) and re-runs the installer for that scope. Re-running `npx @opengsd/gsd-core@<v> --claude --local` in the repo is equivalent.
- Updates are **per install**, so N repos means N updates. `--profile` is persisted and respected by update.

**Coexistence.** The docs say global + local is "a supported configuration", **but "the global skill always wins the `/gsd-<name>` trigger over the local command"**. The installer prints which scope wins, and `/gsd-health` reports W028 (advisory).

**Other runtimes.** Local dir names come from `runtime-name-policy.getDirName`: opencode `.opencode`, codex `.codex`, cursor `.cursor`, pi `.pi`, kimi `.kimi-code`.
- Help text shows `--local` examples for cursor, copilot, windsurf, antigravity, augment, trae, hermes, cline and codebuddy.
- The docs fully document only the Claude local layout:
  - Pi local is `.pi/extensions/gsd.js`;
  - Copilot local writes `AGENTS.md` and `.github/hooks/gsd-session.json`;
  - Cline local writes only `.clinerules/`;
  - Kimi `--local` is "deferred and guarded".
- Only Claude gets the `settings.local.json` split; the others reuse `settings.json`-style surfaces (`hostBehaviorsFor(...).settingsFileByScope` is defined only for claude).
- On this machine, opencode, codex and cursor have **no GSD files**, only leftover `gsd-install-state.json`, `.gsd-staging` and `gsd-migration-journal`. So the migration is Claude-only.

**Uninstall.** `uninstall()` (`install.js:8283`) removes by **prefix**: `gsd-*` skills, flat `gsd-*.md` commands (`:8638-8653`) and `gsd-*.md` agents (`:8838-8844`). It also removes GSD hooks from settings (`:9040-9073`).
- Prefix check on this machine: the only `*gsd*` skills not in the global manifest are `ai-kit-gsd-curated-config` and `ai-kit-spec-execute-gsd`, both symlinks into ai-kit. Neither starts with `gsd-`, so they are safe.
- Uninstall leaves `gsd-install-state.json` behind, as the opencode/codex/cursor residue shows.

## 3. Migration design: global → per-repo local (GSD repos only)

### Target state
- **Global:** nothing from GSD. Do not keep a global `gsd-new-project` bootstrap. Because of W028 a global skill shadows the local command in every GSD repo, and bootstrapping is already one command: `pnpm dlx @opengsd/gsd-core@<v> --claude --local` (or `npx -y …`) in the repo, then `/gsd-new-project`.
- ai-kit's own `ai-kit-gsd-curated-config` and `ai-kit-spec-execute-gsd` stay global (they are ai-kit's skills), but they need the resolver fix below.
- **Per repo:** the full local install in each of the 6 `.planning/` repos, **gitignored, never committed**. Reasons:
  - 14 MB of vendored engine;
  - absolute machine paths are baked in (`@~/...`, the resolver default);
  - hook commands embed the volta node path;
  - `settings.local.json` is per-user by GSD design (#338).
- Commit only `.planning/`, as today.
- Do **not** use `--relative-includes`. With `.claude/` gitignored, worktrees under `.claude/worktrees/` have no `.claude/gsd-core` of their own. The baked absolute paths are exactly what lets worktree agents reach the main checkout's engine.

### Steps (each repo-touching step needs the user's consent)
1. **Backup:**
   - `tar` `~/.claude/{gsd-core,skills/gsd-*,agents/gsd-*,hooks,gsd-file-manifest.json,gsd-install-state.json}`;
   - copy `~/.claude/settings.json`;
   - copy each repo's `.claude/settings.local.json`.
2. **Fix ai-kit first** (otherwise the curated-config skill breaks the moment global is gone):
   - `skills/ai-kit-gsd-curated-config/ai_kit_gsd_curated_config/gsd_catalog.py:16-62`: `resolve_gsd_tools_path` checks only `$HOME`-relative roots. Prepend `<git toplevel or cwd>/.claude/gsd-core/bin/gsd-tools.cjs`, the same order as GSD's own resolver. Add a test in `tests/test_ai_kit_gsd_curated_config.py`.
   - `skills/ai-kit-spec-execute-gsd/SKILL.md:238,247`: the error-path pointer `$HOME/.claude/skills/gsd-execute-phase/SKILL.md` should also name `.claude/commands/gsd-execute-phase.md`. Invoking `/gsd-execute-phase` via the Skill tool works for a project command too.
   - The other `gsd-core/bin` hits (`adapter.py:111`, `gsd_config.py:19,31,37`) are comments only.
   - Per the user's skill-judge rule, run `/skill-judge` on both changed skills.
3. **Install locally in the 4 repos that lack it** (gitid, home-mobility, kitty-setup, wezterm-setup), pinning the same version for parity: `pnpm dlx @opengsd/gsd-core@1.16.0 --claude --local`.
   - First add gitignore lines in home-mobility, kitty-setup and wezterm-setup, which don't ignore `.claude/` and track some `.claude/*.md`: `.claude/gsd-core/`, `.claude/commands/gsd-*.md`, `.claude/agents/gsd-*.md`, `.claude/hooks/`, `.claude/scripts/`, `.claude/gsd-*.json`, `.claude/settings.local.json`.
   - ai-kit, tools-installer and gitid already ignore `.claude/gsd-core`.
4. **Close all Claude sessions.** Skill/command listings and hook registrations load at session start, so open sessions keep stale lists and would break mid-flow.
5. **Global uninstall:** `pnpm dlx @opengsd/gsd-core@1.16.0 --claude --global --uninstall`. Then check:
   - no `~/.claude/{skills,agents}/gsd-*`, no `~/.claude/gsd-core`, no `~/.claude/hooks/gsd-*`;
   - no gsd entries in `settings.json`;
   - the `Bash(npx gsd-core *)` permission can stay.
   - Optionally delete the inert `gsd-install-state.json`/`.gsd-staging`/`gsd-migration-journal` in `~/.config/opencode`, `~/.codex` and `~/.cursor`.
6. **Verify:**
   - In a non-GSD repo (llm-env): no `gsd-*` in the skill listing, and `/graphify` runs the standalone skill.
   - In each GSD repo: `/gsd-health` shows no W028, `/gsd-progress` works, `/hooks` lists the 19 project hooks, and `ai-kit-gsd-curated-config --check`-style resolution finds the local gsd-tools.
   - Pilot one worktree-based `/gsd-execute-phase` in ai-kit (worktree agents resolve via the baked main-checkout path; this is untested here).

### Impact
- **`.planning/config.json`:** none. Config is already per-repo, and the installer only reads `workflow.use_worktrees`. Graphify auto-rebuild stays opt-in per repo (tools-installer and gitid have `graphify.auto_update:true`).
- **Running sessions:** must restart (step 4). Today no global hooks are registered, so a missed session loses only the skill listing, not a hook chain.
- **Token cost:** non-GSD sessions stop paying for 72 skill names plus 35 agent descriptions (README: full profile is about 12k cold-start tokens). GSD repos are unchanged.
- **Updates:** become per repo. `gsd-check-update` already prefers the project VERSION. Six `/gsd-update` runs per release, which is the job to automate (see §4).

### Risks
1. ai-kit resolver regression (step 2 mitigates it).
2. Repo move or rename breaks the baked absolute paths. Re-run the local install.
3. Version drift across repos. Pin the version, or let tools-installer loop the updates.
4. The worktree path chain is unverified (step 6 pilot).
5. Prefix-based uninstall: confirmed safe today. Re-check before running if new `gsd-*` user skills appear.
6. tools-installer status becomes wrong:
   - its `install-state` probe (`installer/skill_lifecycle.py:364-369`) checks only `$HOME/<runtime>/gsd-install-state.json`;
   - it already reports **false "present"** for opencode/codex/cursor (the residue state files);
   - after the migration it would report claude "absent" while 6 repos have GSD.

### Rollback
- Re-run `pnpm dlx @opengsd/gsd-core@1.16.0 --claude --global`. This restores skills, agents and hooks, and re-registers hooks in `settings.json`. Or restore the step 1 tar and `settings.json` copy.
- Per repo: `pnpm dlx @opengsd/gsd-core@1.16.0 --claude --local --uninstall` inside the repo, then revert the gitignore lines.
- The ai-kit resolver change is backward compatible (home candidates kept), so it does not need rolling back.

## 4. Ownership: recommend **tools-installer**, with a small ai-kit fix

- tools-installer already owns GSD as a third-party skill pack. `installer/registry.toml:3291-3357` has `id = "opengsd"` with `targets` for `scope = "global"` **and** `scope = "project"` (`<project>/<selected-runtime-dir>`), lifecycle mode `manual-required`, update `/gsd-update`, and removal `npx @opengsd/gsd-core@latest --<runtime> --global|--local --uninstall`.
- What tools-installer would add:
  - project-scope enumeration: repos with `.planning/config.json`, plus local status via `<repo>/.claude/gsd-file-manifest.json` (`scope: local`, `version`);
  - fix the probe to check `gsd-core/VERSION` or the manifest instead of the uninstall-surviving `gsd-install-state.json`;
  - an "update all local installs" loop over the official installer, never copying files (GSD README: "do not copy files from `agents/` or `commands/` directly").
- ai-kit should only:
  - make its two GSD-adjacent skills resolve the project-local `gsd-tools.cjs` (§3 step 2);
  - keep shipping its own skills.
- ai-kit should not install or uninstall GSD. That duplicates tools-installer's registry, and it crosses the ownership line in the brief.

## Orchestrator correction (2026-10-13 12:4x)

When re-checked, `~/.claude/settings.json` (modified at 12:40, after this agent's read) DOES register 15 GSD hooks globally: agent-isolation-guard, check-update, config-reload, context-monitor, graphify-update, phase-boundary, prompt-guard, read-guard, read-injection-scanner, secret-read-guard, session-state, validate-commit, workflow-guard, worktree-path-guard and write-guard.

ai-kit's `.claude/settings.local.json` also registers 15 GSD hooks, so inside ai-kit (and probably tools-installer) both sets fire, and every GSD hook runs twice. Something re-registered the global hooks at 12:40; it may have been a tools-installer or GSD install run today.

The conclusion that GSD hooks are inert in non-GSD repos still holds: every hook checks for `.planning/config.json` first.
