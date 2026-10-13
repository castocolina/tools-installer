# Audit F: registry, ai tier (17 tools)

**Date:** 2026-10-13 · **Auditor:** F (read-only) · **Branch:** gsd/phase-16-detection-version-and-ownership-must-answer-is-it-on-this-di (7861ced)

**What was checked live (evidence comes from running something, not from docs):**
- Resolver matrix. A probe (`/tmp/claude-1000/auditF/probe.py`) runs `load_tools` and `resolve_methods` with synthetic `Platform` objects: macOS arm64/amd64, then debian, fedora, fedora-immutable and arch, each on amd64 and arm64, each with and without brew (18 cells). For every github_release method it renders the asset and checksum names with `installer.assets.render_asset` and checks them against `gh api repos/<r>/releases/latest`.
- Host state on this machine (Bazzite, fedora immutable, amd64, has brew). These were read-only probes that reused the installer's own functions:
  - `inspect_skill_packs`, `present_agent_hosts` and `present_harnesses` (probe2).
  - `read_inventory`, `resolve_ownership` and `plan_uninstall` (probe3).
  - Read-only reads of `~/.claude.json`, `~/.claude/settings.json`, `~/.codex/{config.toml,AGENTS.md}`, `~/.config/opencode/opencode.jsonc`, `~/.cursor/{mcp,hooks}.json`, `~/.gemini/settings.json` and `~/.pi/agent/settings.json`.
  - `claude plugin list`, `codex plugin list`, `pi list`, and the `--help` output of `graphify`, `rtk`, `codegraph install|uninstall|upgrade`.
- Upstream source, read at the latest tags via `gh api`:
  - rtk v0.52.0: `src/main.rs`, `src/hooks/init/{mod,claude}.rs`.
  - codegraph v1.6.2: `src/installer/{index,targets/claude,targets/registry}.ts`, `src/upgrade/index.ts`.
  - graphify 0.9.54, from the installed site-packages: `graphify/install.py`.
- Registries: PyPI (`specify-cli`, `graphifyy`), npm (`puppeteer`, `@fission-ai/openspec`, `@opengsd/gsd-core`) and the Chrome-for-Testing platform JSON.

**Taken from docs only, not executed:** the per-harness install commands of the 7 skill packs, which were verified 2026-10-10, 3 days ago, and spot-checked against the spec-kit and mattpocock READMEs. I did not install, register or remove anything.

---

## Matrix

Legend for the install column: "all 18" means every cell resolves a method. A ✓ after an asset means it exists in the latest release; "ck" means a checksum file is verified.

| Tool | Install coverage (cells missing) | Detect / version / owner | Uninstall: now → correct? | Configure per host (needed vs done) | Health detectable? | Verdict |
|---|---|---|---|---|---|---|
| rg | all 18, github_release musl/darwin ✓ ck ✓ (native/brew are fallbacks) | ✓ / ✓ 15.2.0 / installer·direct | opt dir + link removed ✓ (F1 name-match caveat, known) | none needed | n/a | **OK** |
| fd | all 18 ✓, **no checksum** | ✓ / ✓ 10.5.0 / installer | opt + link ✓ | none | n/a | minor |
| bat | all 18 ✓, **no checksum** | ✓ / ✓ 0.26.1 / installer | opt + link ✓ | none | n/a | minor |
| sd | all 18 ✓, **no checksum** | ✓ / 1.0.0 → 1.1.0 outdated shown ✓ / installer | opt + link ✓ | none | n/a | minor |
| eza | Linux 16 ✓ (gnu), macOS **brew-only** (no upstream asset), **no checksum** | ✓ / ✓ (v0.23.5 parsed from line 2) / installer | opt + link ✓ | none | n/a | minor |
| ast-grep | all 18 ✓ (gnu zip), **no checksum** | ✓ / 0.45.3 → 0.50.0 / installer | opt + link ✓ | none | n/a | minor |
| codegraph | all 18 ✓ ck SHA256SUMS ✓, no fallback | ✓ / **owner unknown on this host** (self-managed `~/.codegraph/versions`) | deletes `~/.local/bin/codegraph` link only → leaves `~/.codegraph/`, MCP entries in 4 configs, the `codegraph prompt-hook` in Claude settings and the CLAUDE.md block ✗ | MCP for claude/codex/opencode/cursor ✓. Gemini, Antigravity and Copilot are supported by codegraph and present on the host, but not wired ✗. Never re-run for a new host ✗ | ✗ (nothing reads MCP configs) | **major** |
| graphify | all 18 (uv-tool) | ✓ / **owner unknown although `uv tool list` has graphifyy** (NEW bug) → no latest shown (PyPI 0.9.89 vs 0.9.54) | MANAGED with a generic hint, `uv tool uninstall graphifyy` not offered; project files written by the hook never reverted ✗ | **The hook writes CLAUDE.md, AGENTS.md, `.claude/settings.json`, `.cursor/rules` and `.opencode` into the process CWD**; the global skill (`graphify install --platform X`) is never run ✗ | ✗ (`.graphify_version` stamp unused) | **blocker** |
| rtk | all 18 ✓ ck checksums.txt ✓ (arm64 gnu) | ✓ / 0.44.1 → 0.52.0 outdated ✓ / "installer direct" for a hand-placed `~/.local/bin/rtk` (F1/999.2) | binary only → Claude hook + RTK.md, OpenCode plugin, Codex `@RTK.md` and Cursor hooks stay pointing at a missing binary ✗ (`rtk init -g --uninstall` exists) | claude/codex ✓. **opencode branch writes Claude files or fails** ✗. Cursor gate obsolete ✗. pi/gemini/antigravity/copilot not wired ✗. **This host: wired to Codex only, undetected** | ✗ (`rtk init --show` and `rtk verify` unused) | **major** |
| puppeteer | macOS 2 + Linux amd64 8; **Linux arm64 none, by design** | ✓ / **dangling pnpm shim, broken=True** (999.7) / unknown | MANAGED (pnpm; coupled with the mmdc group) | none | Doctor launch smoke ✓ | minor |
| ponytail | skill_pack, all 18 (manual handoff) | claude ✓ codex ✓ present (live); pi not probed although `pi install` is documented | Uninstall "not installed" (F6); removal text Codex-only, though Claude also has it | manual; filtered to present hosts ✓ | version (5.1.0 in plugin list) not read | minor |
| openspec | skill_pack (pnpm) | no probes → `is_installed(openspec)` ✓ (volta here) / owner unknown (volta unmodeled) | MANAGED generic, registry removal text not shown (F6) | project-level `openspec init`, honestly unknowable | ✗ | minor |
| superpowers | skill_pack | claude ✓ codex absent (true) pi ✓; cursor/opencode/gemini/antigravity/copilot/droid/grok **present on host but unprobed → unknown** | "not installed" (F6) | manual | ✗: **4 duplicate Claude installs (2 marketplaces × 2 scopes, 6.4.1 + 6.2.0) read as plain "present"** | **major** |
| softaworks-agent-toolkit | skill_pack | skills-lock: claude ✓ codex ✓ (shared `~/.agents/skills`), cursor absent | "not installed" (F6) | manual | partial-host not flagged | minor |
| matt-pocock-skills | skill_pack | claude/codex probed via plugin-cli, but the default instruction installs via the skills CLI → **false "absent"** | "not installed" (F6) | manual | ✗ | **major** |
| opengsd | skill_pack | install-state: claude/codex/cursor/opencode present ✓ (live) | "not installed" (F6) | manual; **needs Node ≥24 (npm engines), undeclared** | `~/.claude/gsd-core/VERSION` unused | minor |
| spec-kit | skill_pack (uv) | no probes → `is_installed(specify)`; uv-installed but no uv-tool method → owner unknown | MANAGED generic (F6) | project-level | ✗ | minor |

**Verdict counts:** OK 1 · minor 11 · major 4 · blocker 1.

---

## Per-tool notes

### Binaries: rg, fd, bat, sd, eza, ast-grep
- All 18 cells resolve to a github_release asset that exists today:

  | Tool | Latest tag |
  |---|---|
  | ripgrep | 15.2.0 |
  | fd | v10.5.0 |
  | bat | v0.26.1 |
  | sd | v1.1.0 |
  | eza | v0.23.5 |
  | ast-grep | 0.50.0 |

  On fedora-immutable, native rungs drop out as designed (`resolve.py:76-77`), and github_release is ranked first anyway.
- Only rg has a checksum. fd, bat, sd, eza and ast-grep upstreams publish no checksum file, but **GitHub's release API exposes a per-asset `digest: sha256:…`** for every one of those assets (seen in the `gh api` output). The architecture only knows checksum *files* (`download.py:98-120`). This is NEW, see X5.
- eza: macOS has no upstream asset (comment `registry.toml:317`), so a Mac without brew gets no method until brew lands. `platform_could_support` handles this correctly.
- Uninstall plans `~/.local/opt/<bin>` and `~/.local/bin/<bin>` (`uninstall.py:56-97`). That is correct for installer-made copies. The name-match proof gap is known (F1, 999.8).
- No agent configuration is needed. The shared guidance block (`agent_guidance.py`) names rg, fd, bat and eza, but it lives in the unwired agent-policy code (F11, 999.10).

### codegraph: major
- Install: assets and `SHA256SUMS` are fine for v1.6.2 in all cells. `# Verified 2026-09-05` is more than 30 days old, so I re-checked it, and the asset names still hold.
- **Ownership on this host:** `~/.local/bin/codegraph` is a symlink to `~/.codegraph/versions/v1.6.0/bin/codegraph`, made by codegraph's own `install.sh`. As a result `resolve_ownership` returns unknown, "not attributable". `plan_uninstall` still lists the symlink, so Uninstall would delete codegraph's own link and leave `~/.codegraph/versions`. That is F1 (known).
- **NEW, self-update takes the install away from the installer:** codegraph's MCP server and banner tell the user to run `codegraph upgrade`.
  - For an installer-made bundle in `~/.local/opt/codegraph`, `detectInstallMethod` sees a bundle with `installDir = null` (upstream `src/upgrade/index.ts:88-93,136`).
  - It then runs `install.sh` with its defaults (`:566` only sets `CODEGRAPH_INSTALL_DIR` when known). The tool moves into `~/.codegraph/versions`, ownership flips to unknown, the installer refuses to update it, and `~/.local/opt/codegraph` is orphaned.
  - The herdr note in 999.11 raises the same "who owns updates" question; codegraph is a live instance of it.
- **Postinstall writes more than the registry says.** `registry.toml:1538-1542` claims `--no-permissions` "keeps this call scoped to MCP registration only". In codegraph 1.6.2 that is false:
  - `--yes` forces `promptHook = true` whenever Claude is a target (`src/installer/index.ts:215-219`), so the `codegraph prompt-hook` UserPromptSubmit hook is written.
  - The `~/.claude/CLAUDE.md` instruction block is always upserted (`targets/claude.ts:152-169`).
  - `--no-permissions` only skips the allow list. There is no non-interactive opt-out flag in `codegraph install --help`.
- Hosts: the hook knows 4 (`postinstall.py:26,67-72`). codegraph 1.6.x also supports gemini, antigravity, copilot, hermes and kiro (`codegraph install --help`). gemini (`gemini` on PATH) and copilot are present on this host but are not wired.
- **Uninstall never calls `codegraph uninstall --target … --keep-cli`.** After a file-level removal, these stay behind:
  - every host's MCP entry. Live: `~/.claude.json` mcpServers, `~/.codex/config.toml`, `~/.config/opencode/opencode.jsonc` and `~/.cursor/mcp.json` all contain codegraph. Each agent session would then try to spawn a missing server.
  - the Claude `prompt-hook`, which would fail on every prompt.
  - the `mcp__codegraph__*` allow rule and the CLAUDE.md block.
- Health: nothing reads agent configs. `codegraph install --print-config <id>` (no writes) and `install --refresh` exist upstream and could provide detection and repair.

### graphify: blocker
- **NEW, the hook writes into the wrong place.** `_graphify_register` runs `graphify <host> install` (`postinstall.py:250-274`) with no cwd, and the Runner sets none (`run.py:232-240`). In graphify 0.9.54 those subcommands are **project-scoped, relative to `Path(".")`**:
  - `claude install` writes `./CLAUDE.md` plus a PreToolUse hook in `./.claude/settings.json` (site-packages `graphify/install.py:1766-1781,1794-1813`, dispatch at `:2176-2183`).
  - `codex` and `opencode` write `./AGENTS.md`, plus `.codex/hooks.json` or a `.opencode` plugin (`:1530-1553`, `:2322-2329`).
  - `cursor` writes `./.cursor/rules/graphify.mdc` (`:1147-1160`).
  - Upstream README line 307 says "Run `graphify <platform> install` once **in your project**". The *global* per-user skill is `graphify install [--platform X]` (README lines 203-216), which the hook never calls.
  - So every graphify install or update (`update.py:309` re-runs it) commits graphify sections and an absolute-path hook into whatever directory `make setup` was started from, normally this repo. If started from `$HOME`, it writes `~/CLAUDE.md` and patches the global `~/.claude/settings.json`.
  - 12.4-RESEARCH.md:279 states "bare `graphify <host> install` … is global/user-scope by design". That is wrong; the merge-safety test ran inside a scratch project, which hid it.
- **NEW, ownership bug:** `owner_dirs` gives uv only `~/.local/bin` (`ownership.py:456-463`), but `attribute_path` resolves the active path through uv's symlink into `~/.local/share/uv/tools/graphifyy/bin/graphify` (`:466-483`). On this host the result is owner unknown, even though `uv tool list` lists graphifyy (probe3). Knock-on effects:
  - no latest version (0.9.89 available vs 0.9.54 installed);
  - Update refuses (unknown-owner);
  - Uninstall shows the generic hint.
  - This affects every uv-tool-installed binary. It is the root cause behind ponytail-audit #4 "ruff Owner unknown".
- Hosts: graphify supports pi, gemini, antigravity, copilot, hermes, kiro and devin. The hook does 4.
- Removal: `graphify uninstall` (all platforms) and `graphify <host> uninstall` exist, but no removal path calls them.
- Health: the skill dir carries `.graphify_version` (live: `~/.claude/skills/graphify/.graphify_version` = 0.9.54). A stale-skill check would be cheap, but none exists.

### rtk: major
- Install is fine (v0.52.0 assets and `checksums.txt` present). The registry text is verified at 0.49.0. The local binary is 0.44.1 and is correctly shown as outdated.
- **NEW, the opencode branch breaks D-01a.** In rtk 0.52.0 `install_claude = !cursor && !windsurf && !cline` (`src/main.rs:2662-2671`), so `rtk init -g --opencode --auto-patch` runs `run_default_mode`, which writes `~/.claude/RTK.md` before the OpenCode plugin (`src/hooks/init/claude.rs:329-345`).
  - On an OpenCode-only machine the result is either Claude scaffolding nobody asked for (if `~/.claude` exists) or a failed OpenCode registration. `_RTK_HOST_CONFIG_DIR` only creates `.claude` for claude and cursor-agent (`postinstall.py:163-166`).
  - `_rtk_register` gates only cursor on Claude being present (`:231`).
- **Stale gate:** rtk #2097 is fixed. `--agent cursor` no longer writes `~/.claude` (main.rs comment at 2666-2670), so the cursor-only-with-claude gate now skips Cursor-only machines for no reason.
- Hosts: rtk 0.52 supports `--agent pi|antigravity|hermes|droid|kimi`, `--gemini` and `--copilot`. pi, gemini, agy, copilot and droid are present on this host but not wired.
- **Live misconfiguration the UI cannot show:** rtk reads ✓ (outdated), but it is wired only into Codex (`~/.codex/AGENTS.md` has `@…/RTK.md`). Claude `settings.json` has no rtk hook, there is no `~/.claude/RTK.md`, OpenCode has no `rtk.ts` plugin and Cursor's `hooks.json` has no rtk entry.
- Removal: a file-only uninstall leaves Codex instructions telling the agent to prefix commands with a now-missing `rtk`, plus Claude, OpenCode and Cursor hook entries. Upstream `rtk init -g --uninstall [--codex|--agent …]` exists (`init/mod.rs:832-903`).
- Minor items:
  - CLI path (`app.py:133` → `run.py:50-56`, stdin inherited): `rtk init` can open a telemetry consent prompt (`init/mod.rs:752-777`) during `--yes`. The TUI uses DEVNULL, so it is unaffected.
  - Update re-runs registration (`update.py:309`) with no record of opt-out, so it would re-add a hook the user removed on purpose (this host suggests exactly that for Claude).

### puppeteer: minor
- Install on Linux arm64 is NONE, as designed (`registry.toml:2422-2430`). Chrome-for-Testing now publishes `linux-arm64` (Stable 155.0.8059.39), but `@puppeteer/browsers@latest` still maps `LINUX_ARM` → `linux64` (`lib/cjs/browser-data/chrome.js`), so the exclusion still holds. Re-check when puppeteer changes that mapping.
- `unavailable_reason` on arm64 says "debian not supported; not built for arm64". It mixes in the macOS method's os rejection, which is misleading.
- Live: a dangling pnpm shim (`broken=True`, owner unknown). Known in 999.7.

### Skill packs: ponytail, openspec, superpowers, softaworks, matt-pocock, opengsd, spec-kit
- Install: `skill_pack` applies in every cell (`resolve.py:54-65`). `perform_action` returns a manual handoff filtered to `present_harnesses` (`skill_lifecycle.py:245-285`), which works.
- Detection, live (probe2):

  | Pack | Result |
  |---|---|
  | ponytail | claude present, codex present |
  | superpowers | claude present, codex absent, pi present |
  | softaworks | claude present, codex present, cursor absent, adal absent |
  | matt-pocock | all absent |
  | opengsd | present for claude, codex, cursor, opencode |
  | openspec, spec-kit | `{}` (no probes) |

- Gaps that are NEW in detail (they deepen AR-03 and F6):
  - **No "partial" state.** `_present` / `_inst_cell` show ✓ if any host is present (`catalog_tui.py:479-517`). "Absent on a harness that IS present", for example softaworks on cursor or superpowers on codex, is indistinguishable from "host not installed". `inspect_skill_packs` never joins with `present_harnesses`.
  - **`_claude_matches` ignores Status and Scope** (`skill_lifecycle.py:34-42`). A disabled plugin, or a project-scoped install from another project, reads as present. **Duplicates are invisible.** Live, superpowers is installed 4 times in Claude (`@claude-plugins-official` user 6.4.1 and project 6.2.0, `@superpowers-marketplace` user and project 6.2.0). The registry's own claude instructions offer both marketplaces with "or, instead" (`registry.toml:3095-3100`).
  - **One probe per harness** (`model.py:434-438` rejects repeats). matt-pocock's claude and codex probes are plugin-cli (`registry.toml:3231-3232`), but its default instruction is `npx skills@latest add mattpocock/skills` (`:3248`), which lands in `~/.claude/skills` and `~/.agents/skills`. A user who follows it reads "absent", and Execute offers the install again.
  - **No revision observation.** `revision_policy` is declared but never compared with anything. `codex plugin list` and `claude plugin list` print versions (ponytail 5.1.0; superpowers 6.4.1/6.2.0), and opengsd writes `~/.claude/gsd-core/VERSION` (1.16.0). None of these are read, so "plugin cache outdated" cannot be detected.
- Uninstall: known. F6 says the Uninstall row reads "not installed"; ponytail-audit line 174 says the removal instructions are never shown. For openspec and spec-kit, `cmd` on PATH turns the row into MANAGED with the generic "managed outside this installer" text instead of the pack's removal steps.
- Per tool:
  - **ponytail:** the pi probe is missing (`pi install git:github.com/DietrichGebert/ponytail` is documented at `:2919`, and `_pi_matches` would match `DietrichGebert/ponytail`). Removal and approval text cover Codex only, though the probe also finds Claude.
  - **superpowers:** 7 present hosts are unprobed. Duplicate Claude installs are undetected.
  - **opengsd:** `npx @opengsd/gsd-core@latest` needs Node ≥24 (npm `engines.node` of 1.16.0), and that is not declared.
  - **spec-kit:** the PyPI name `specify-cli` is legitimate (1.1.3 uploaded 2026-10-09T19:35Z, 5 minutes after GitHub release v1.1.3; the README says `uv tool install specify-cli`). It is installed by uv, but the entry has no uv-tool method, so ownership stays unknown.
  - **openspec:** it is volta-shimmed on this host, and volta is not a modelled owner.

---

## Cross-cutting architecture gaps

| # | Gap | Status |
|---|---|---|
| X1 | **Postinstall hooks are install-only and one-way.** (a) They are never re-run when an agent host is installed later: `ALREADY_INSTALLED` short-circuits (`engine.py:132-133`) and `reapply_post_install` dispatches `post_install` actions only, not `postinstall` hooks (`engine.py:200-216`). (b) They are never reversed on removal: `plan_uninstall` deletes files only and no `uninstall` hook table exists. They do re-run on Update (`update.py:309`) and Repair, which is accidental coverage. Upstream reversals all exist: `codegraph uninstall --keep-cli`, `rtk init -g --uninstall`, `graphify <host> uninstall`. | Accepted D-01 for (a), noted again for herdr in 999.11. (b) is **NEW** and belongs in 999.8 as a per-method "unconfigure" level. |
| X2 | **No configuration health model.** Nothing detects a missing or stale MCP entry, a missing or stale hook, or a missing skill on a present host. Live proof: rtk is wired only to Codex, and Gemini lacks codegraph. Upstream read-only probes exist: `codegraph install --print-config`, `rtk init --show`, `rtk verify`, graphify `.graphify_version`, `claude/codex plugin list` versions, opengsd `VERSION`. | **NEW** (fits 999.6 `ToolState` as a "configured-for-host" facet) |
| X3 | **Four disagreeing agent-host lists:** `postinstall._AGENT_HOST_IDS` (4), `skill_lifecycle.HARNESS_PRESENCE` (17), `agent_env.adapters` (claude/codex/opencode/pi/antigravity, unwired F11), `INSTALL_STATE_HARNESS_DIRS` (9). pi and antigravity are catalog hosts but invisible to every postinstall hook. Gemini CLI is present on the host but not in the catalog. | **NEW**, related to AR-03 |
| X4 | **uv attribution:** the uv owner dir is `~/.local/bin`, but `attribute_path` resolves symlinks into `$(uv tool dir)` → every uv-tool reads owner unknown (graphify live). | **NEW** root cause of ponytail #4 |
| X5 | **Checksums:** 50 of 89 github_release methods have no checksum file. The GitHub API `digest` field (sha256 per asset) could verify all of them without a schema change for authors. This includes herdr in 999.11. | **NEW** |
| X6 | **Self-updating tools** (codegraph `upgrade`, herdr `update`) move the install out of the installer's layout, and ownership flips to unknown. | Known for herdr (999.11). codegraph instance is **NEW**. |
| X7 | **Skill-pack state is ✓/○/? only.** There is no partial or duplicate/disabled state and no revision. One probe per harness forbids "plugin OR skills-CLI". | Deepens AR-03 and F6 (999.6) |
| X8 | Skill-pack Uninstall reads "not installed", and removal text is never shown. | Known F6 (999.6) and ponytail-audit line 174 |
| X9 | Postinstall `--yes` side effects are wider than documented (codegraph prompt-hook and CLAUDE.md block; rtk `--opencode` → Claude files). There is no recorded write set, so nothing can be reverted precisely. | **NEW**, needs 999.2 receipts |

## Registry fixes (data only)
1. `graphify`: the hook argv cannot be fixed from data; it needs code (`graphify install --platform <host>`, global). Until then, correct the `# Verified 2026-09-11` text: `<host> install` is project/CWD-scoped. If removal stays manual, add `uninstall = "graphify uninstall; uv tool uninstall graphifyy"`.
2. `codegraph`: correct `registry.toml:1538-1542`. `--no-permissions` does NOT stop the `codegraph prompt-hook` UserPromptSubmit hook or the `~/.claude/CLAUDE.md` block in v1.6.2. Re-date `# Verified` to v1.6.2, and record that `codegraph upgrade` migrates the install to `~/.codegraph/versions`.
3. `rtk`: re-date to 0.52.0. Record that `--opencode` implies Claude install (main.rs:2671) and that `--agent cursor` no longer touches `~/.claude` (#2097). The gating itself lives in code (`postinstall.py:231`).
4. `ponytail`: add `{ harness = "pi", via = "plugin-cli", match = "DietrichGebert/ponytail" }`. Add Claude removal lines (`/plugin uninstall ponytail@ponytail`) next to the Codex ones, because the probe already detects Claude.
5. `superpowers`: drop the "or, instead, from the obra marketplace" alternative from `by_harness.claude`. It produces the live duplicate installs.
6. `matt-pocock-skills`: either make the default instruction the claude/codex plugin route, or (given one probe per harness) switch the claude probe to `skills-lock` with `match = "mattpocock/skills"` so the documented default `npx skills add` is detected.
7. `opengsd`: note Node ≥24 (npm `engines`) in the instructions, or add a node requirement.
8. `puppeteer`: append to the arm64 note that CfT now ships linux-arm64 (2026-10) but `@puppeteer/browsers` still maps `LINUX_ARM` to `linux64`. Re-verify on the next puppeteer major.

---
Not checked: a macOS host, Linux arm64 hosts, the contents of the rtk macOS arm64 tarball, and every skill pack's install command beyond spec-kit and mattpocock. I never ran a postinstall hook.
