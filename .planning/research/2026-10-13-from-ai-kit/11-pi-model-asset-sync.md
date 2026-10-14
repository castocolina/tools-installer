# 11 - opencode → pi: model, credential and asset sync

Date: 2026-10-13. Scope: read-only research plus a scratchpad prototype. Nothing under `~/.pi`, `~/.config/opencode`, or any repo was modified. No package was installed. No secret value was printed; auth files were read for key names only.

Evidence base:
- pi 1.2.0 tarballs: `@earendil-works/pi-coding-agent` and `@earendil-works/pi-ai`, downloaded from the npm registry to scratchpad `dl11/{ca,ai}/package/`. Paths below like `ai/dist/...` and `ca/docs/...` are relative to `dl11/`.
- Local configs, plus `opencode models --verbose` saved to scratchpad `opencode-models-verbose.txt`.
- `opencode auth list`, `cursor-agent models`, and official docs on the web.

## TL;DR (ranked)

1. **A model sync script is mostly unnecessary.** pi 1.2.0 already includes every opencode provider the user has: `opencode` (Zen), `opencode-go`, `xai`, `openai-codex`, `anthropic`, and `github-copilot`. Its catalog also refreshes itself from pi.dev.
   - Only the **credentials** are missing in pi.
   - The model gap is **1 model**: `opencode/cat-jam-free`.
   - Zen: 38 of 39 opencode models are in pi's catalog. Go: 31 of 31. xAI: every chat model, except 4 that pi deliberately removed and 5 image/video models.
2. **Cursor cannot be a pi model.** Cursor has no official inference API. A Cursor API key only drives the Cloud Agents API.
   - opencode does **not** have Cursor either. `opencode models` shows no cursor provider, and `opencode auth list` shows only xAI and OpenCode.
   - Workaround: delegate to `cursor-agent -p`, for example through a small pi tool extension.
3. **router-env is already synced into pi by llm-env** (`setup/lib/install-agent-clients.sh:199-229`). Two defects:
   - It writes the router API key as a **literal** into both `~/.pi/agent/models.json` and `opencode.jsonc`.
   - It **overwrites** `settings.json.enabledModels` with router-only ids on every run (`:109-116`).
4. **The current pi install is broken.** `pi` is not on PATH, and the volta install that research 06 measured (0.82.1) is gone.
   - **6 dangling symlinks**: `extensions/subagent/{index,agents}.ts` plus `agents/{planner,reviewer,scout,worker}.md`. They point into the deleted `~/.volta/.../pi-coding-agent/examples/`.
5. **Skills:** pi reads `~/.agents/skills` natively, but **not** `~/.claude/skills`.
   - `~/.pi/agent/skills` is 33 symlinks that duplicate `~/.agents/skills`, which produces name-collision warnings. Delete it.
   - 93 Claude-only skills are invisible to pi: 18 ai-kit symlinks, the gsd-* skills, graphify, and a few others.
6. **MCP:** pi ≥0.99 reads only `~/.pi/agent/mcp.json` and a trusted project `.pi/mcp.json`. It does not import other hosts' configs; its docs give mechanical conversion rules instead.
   - The prototype converts opencode's `codegraph` and `gsd` entries.
   - `codegraph install` has no pi target.
7. **Ownership:**
   - tools-installer: the credential overlay, the MCP conversion and the skills fix. It already owns pi's install (`host_setup.py:28-41`) and cross-host skill and MCP registration.
   - llm-env: keeps router-env, after its `enabledModels` overwrite is fixed.
   - ai-kit: none of this.

## 1. What pi 1.2.0 supports natively

### Providers and auth

Generated from `ai/dist/providers/*.js` (`envApiKeyAuth`/`lazyOAuth` calls). The full list of API-key providers is in `ca/docs/providers.md:31-65`.

- **OAuth and API key:**
  - `anthropic`: "Claude Pro/Max".
  - `openai-codex`: OAuth only, "ChatGPT Plus/Pro".
  - `openai`: `OPENAI_API_KEY`, or "Sign in with ChatGPT", added in 0.99.0.
  - `xai`: `XAI_API_KEY`, or "Sign in with SuperGrok or X Premium" device-code OAuth (`ai/dist/providers/xai.js:9-19`, since 0.80.8 per CHANGELOG:1256,1273).
  - `github-copilot`, `kimi-coding`, `meta` (Muse), `openrouter`, `radius`.
- **API key only:**
  - `opencode` (Zen) and `opencode-go` both use **`OPENCODE_API_KEY`** (`ai/dist/providers/opencode.js:12`, `opencode-go.js:12`).
  - Also: deepseek, google, groq, mistral, cerebras, together, fireworks, zai, minimax, moonshot, qwen-token-plan*, xiaomi*, typesafe, vercel-ai-gateway, huggingface, nvidia, baseten, ant-ling and azure.
  - Ambient credentials: bedrock, vertex and cloudflare.
- **Credential precedence:** `--api-key`, then `auth.json`, then `models.json` `apiKey`, then the environment variable (`ca/docs/models.md:23`).
  - `apiKey` accepts `$NAME`, `${NAME}`, a literal, or `!command`. In `models.json` the command runs on each request and is not cached (`models.md:65`).
- **The catalog refreshes itself:** pi starts from its bundled catalog and overlays newer pi.dev data, cached in `models-store.json` (`models.md:15`).
  - `pi update --models` forces a refresh. New Zen, Go or xAI models therefore reach pi without any sync.

### Per account

#### (a) opencode Zen and Go: **native**
- Providers `opencode` (base `https://opencode.ai/zen`) and `opencode-go` (`https://opencode.ai/zen/go`). Both returned unauthenticated `GET .../v1/models` → 200.
- opencode itself uses `https://opencode.ai/inference/...` URLs. That is irrelevant to pi.
- One key covers both. opencode stores it as `auth.json` → `opencode: {type: api, key}`, read for key names only.

#### (b) xAI / Grok: **native, API key or subscription OAuth**
- opencode's binary contains the **same xAI OAuth client id** as pi: `b1a00492-…`, at `ai/dist/auth/oauth/xai.js:5`, found by `grep -a` on `~/.opencode/bin/opencode`.
- So the token shapes match. **Do not copy tokens.** Each client refreshes on its own, and a rotated refresh token would break the other host. Run a separate `/login xai` in pi instead.
- The same account limits apply in both hosts. See the 2026-09-14 memory: opencode's xai lane was blocked with 403 spending-limit.

#### (c) Cursor: **not possible**
- No official OpenAI-compatible endpoint exists. A Cursor API key (`crsr_…`) covers the Cloud Agents API and SDKs only (forum.cursor.com/t/…/164522, 2026-07-01, with no staff reply).
- Cursor Bridge (cursorbridge.dev) is unofficial and a ToS risk, so it is not recommended.
- Workaround: keep `cursor-agent -p --output-format text --model <m> --trust < /dev/null` as a separate delegation lane. Its account models (from `cursor-agent models`) include composer-2.5, cursor-grok-*, and gpt-5.3-codex*.
  - In pi, this would be a ~40-line tool extension: `registerTool("cursor_agent")` spawning the CLI. That is a delegate, not a `/model` entry.
  - A provider extension wrapping cursor-agent would be semantically wrong, because cursor-agent runs its own tools, so pi's tool calls would never reach pi.

#### (d) OpenAI Codex / ChatGPT: **native**
- Already logged in: `~/.pi/agent/auth.json` has `openai-codex: oauth` and `anthropic: oauth`.
- **Future accounts:** `auth.json` holds one credential per provider id. For a second ChatGPT account:
  - Use a separate `PI_CODING_AGENT_DIR` (`ca/docs/environment-variables.md:81`), or
  - Put it in the `openai` provider's "Sign in with ChatGPT" slot. That this gives a second, independent slot is my inference, not tested.
- Custom providers cannot carry OAuth: the `oauth` field accepts only `"radius"` (`ca/schemas/models.schema.json`).

#### (e) router-env: **custom provider, already written by llm-env**
- `~/.pi/agent/models.json` has `router-env` with `api: openai-completions`, `baseUrl` `http://127.0.0.1:20128/v1`, compat `{supportsDeveloperRole: false, supportsReasoningEffort: false}`, and 3 combos. It matches opencode's entry.

### Exact `models.json` schema (`ca/schemas/models.schema.json`)
- Top level: `{ "$schema"?, "providers": { <id>: Provider } }`. `providers` is required.
- **Provider:** `name`, `baseUrl`, `apiKey`, `api`, `oauth` (const `"radius"`), `headers` {str:str}, `compat` (ProviderCompat, about 40 flags), `authHeader` bool, `models[]`, `modelOverrides` {id: partial model}.
- **Model:** `id` (required), `name`, `api`, `baseUrl`, `reasoning`, `thinkingLevelMap` {off…max}, `input` ["text","image"], `inputLimits`, `cost` {input, output, cacheRead, cacheWrite, tiers?}, `promptCache` {short, long}, `contextWindow`, `maxTokens`, `samplingParams`, `samplingParamsByThinkingLevel`, `headers`, `compat`.
- **Validation** (`ca/dist/core/provider-composer.js:83-160`):
  - A model needs an `api` from the model, the provider, or the built-in default.
  - Custom models need a `baseUrl`, which can be inherited from the built-in provider.
  - A provider entry must set at least one of `baseUrl`, `headers`, `compat`, `modelOverrides`, `models`, `apiKey`, `oauth` or `authHeader`. **An `apiKey`-only entry on a built-in id is valid**, and that is the credential-reference trick the prototype uses.
  - A `models` entry adds or replaces a model by id on that provider (`models.md:67`).
  - Defaults: `contextWindow` 128000, `maxTokens` 16384, `cost` 0, `input` ["text"].

## 2. opencode's side (names only)

- **`~/.config/opencode/opencode.jsonc`** has the top-level keys `$schema`, `plugin`, `provider` and `mcp`.
  - `provider` has only `router-env`: `@ai-sdk/openai-compatible`, `http://127.0.0.1:20128/v1`, models my-planning, my-plan-review and my-coding. Its `apiKey` is a literal `sk…`.
  - `mcp`: `codegraph` (local) and `gsd` (local, npx `@opengsd/gsd-core gsd-mcp-server`).
  - `plugin`: superpowers and ponytail. No Cursor plugin.
- **Credentials** (`~/.local/share/opencode/auth.json`, from `opencode auth list`): `xai` (oauth) and `opencode` (api).
- **`opencode models`** lists 86 models: opencode 39, opencode-go 31, xai 13, router-env 3.
- **Adapters** (`--verbose` `api.npm`):
  - `@ai-sdk/openai-compatible` → pi `openai-completions`
  - `@ai-sdk/openai` → `openai-responses`
  - `@ai-sdk/anthropic` → `anthropic-messages`
  - `@ai-sdk/google` → `google-generative-ai`
  - `@ai-sdk/xai` → `openai-responses`
  - `@ai-sdk/mistral` (one Zen model) → unmapped, but pi's catalog already has it.
- **Gap against pi 1.2.0's catalog** (scratchpad `pi-builtin-models.txt`):
  - opencode-only, Zen: `cat-jam-free`.
  - opencode-only, xAI:
    - `grok-4.20-0309-{reasoning,non-reasoning}` and `grok-4.20-multi-agent-0309`. pi removed them on purpose (CHANGELOG 0.80.9, #6734).
    - `grok-build-0.1`. pi removed it as "unavailable" (#9093).
    - 5 `grok-imagine-*` models. These are image/video, not chat.
  - Go: no gap.

## 3. Sync script: design and prototype

Prototype: scratchpad `pi-sync/pi_sync.py` (296 lines, stdlib only) plus a self-check, `pi-sync/test_pi_sync.py`. Run with `python3 -I test_pi_sync.py` → `ok`.

Dry run against the live state: `python3 -I pi_sync.py --opencode-models ../opencode-models-verbose.txt --pi-ai-data ../dl11/ai/package/dist/providers/data --out out`. Outputs:
- `pi-sync/out/report.txt`
- `pi-sync/out/models.diff`
- `pi-sync/out/mcp.diff`
- `pi-sync/out/candidate-{models,mcp}.json`. Literal keys are redacted; `$`/`!` references are kept.

**What it plans for this machine** (`out/report.txt`):
- `opencode` and `opencode-go`: `apiKey: "!jq -r .opencode.key ~/.local/share/opencode/auth.json"`. This is a credential **by reference**: no copy, and rotation in opencode follows automatically.
- `opencode/cat-jam-free`: added as `openai-completions`, inheriting pi's Zen base URL.
- `xai`: LOGIN instruction only (`/login xai` or `XAI_API_KEY`). The 4 removed models and 5 non-chat models are skipped, with the reason stated.
- `router-env`: skipped, because llm-env owns it.
- `mcp.json`: `codegraph` → `{command: codegraph, args: [serve, --mcp]}` and `gsd` → `{command: npx, args: [...]}`. The rules come from `ca/docs/mcp.md:113`: split the `command` array, `environment` → `env`, `{env:X}` → `${X}`.

**Rules:**
- **Dry run by default.** `--write` is the only path that touches `--pi-dir`. It writes atomically, at mode 0600, and keeps a `.bak`.
- **Idempotent.** The test asserts that a second run is a no-op.
- **User entries win.** It never edits or deletes an existing provider key, model id or MCP server, and adds `apiKey` only where none exists.
- **Stale entries are reported, never removed**, because deleting them would need ownership state.
- **Never copies OAuth tokens.**
- **Never copies a literal key.** A custom provider with a literal key in `opencode.jsonc` gets a MANUAL note telling the user to use `$ENV` or `!cmd`.
- **Catalog source:** pi-ai's `dist/providers/data/*.json` beside the installed `pi` (realpath of `which pi`), plus `models-store.json`. `pi --list-models` is not usable for this: it shows only models that have credentials (`ca/dist/cli/list-models.js:25`).

**Shortcuts:**
- `jq` is resolved through `$PATH` (`/home/linuxbrew/.linuxbrew/bin/jq`) when pi runs the command. Use an absolute path if pi is launched with a reduced PATH.
- The inline JSONC stripper should be swapped for ai-kit's `jsonc_edit.strip_jsonc_comments`, if the script lands in ai-kit.
- opencode `openai` is mapped to pi `openai-codex`, which assumes ChatGPT OAuth rather than an API key.

### Where it should live

**tools-installer** (recommended):
- It owns pi's install handoff (`installer/host_setup.py:28-41`, registry `id = "pi"` at `registry.toml:2691`).
- It owns per-host skill directories (`installer/skill_lifecycle.py:134-164`, where pi → `.agents/skills`), host-presence detection (`:174-191`), and cross-host MCP registration (`installer/postinstall.py:26` `_AGENT_HOST_IDS`; pi is missing from it).
- Ship the script as a reviewed post-setup handoff: dry-run first, then `--write`. That matches its "display reviewed commands, never auto-launch" contract (`host_setup.py:1-7`).

**llm-env:**
- Keep router-env there, since it already writes pi.
- Fix `_iac_stage_pi_settings` so it **merges** `enabledModels` instead of replacing it, and reference the key file with `"!cat <key-file>"` instead of embedding the literal.

**ai-kit:** not a fit. It is spec-workflow skills. Its only overlap is `ai-kit-opencode-providers`' read-only listing, and its config-doctor PRD covers Claude, opencode and codex, not pi.

## 4. What pi reads automatically

### Skills
- pi reads `~/.pi/agent/skills`, **`~/.agents/skills`**, project `.pi/skills` and `.agents/skills` (walked to the repo root), packages, `settings.skills`, and `--skill` (`ca/docs/skills.md:59-63`).
- Project `.agents/skills` is trust-gated (`ca/dist/core/trust-manager.js:146-160`), so it is ignored in `-p` without trust.
- **No `.claude/skills`**: no such path exists in `ca/dist`.
- Name collisions keep the first skill found and warn (`skills.md:85`).

### Prompt templates (commands)
- `~/.pi/agent/prompts/*.md`, `.pi/prompts` (trust-gated), and `settings.prompts`. Only direct children of a directory are loaded unless globs are used.
- Supports `$1`, `$@` and `$ARGUMENTS` (`ca/docs/prompt-templates.md`).
- Does not read `.claude/commands`.

### Agents (subagent extension)
- `~/.pi/agent/agents/*.md` plus the nearest `.pi/agents/` (`ca/examples/extensions/subagent/agents.ts:119,129`).
- Frontmatter fields: `name`, `description`, `tools`, `model`.

### MCP
- `~/.pi/agent/mcp.json` and project `.pi/mcp.json` (trust-gated), in `mcpServers` format, managed with `pi mcp add|list|login` (`ca/docs/mcp.md`).
- **No import.** There is only a conversion table (`mcp.md:106-113`).
- The default exposure is `codemode`.

### opencode, for comparison
- **Skills:** `~/.config/opencode/skills`, **`~/.claude/skills`** and `~/.agents/skills`, plus project `.opencode/`, `.claude/` and `.agents/skills` (opencode.ai/docs/skills).
- **Agents:** `~/.config/opencode/agents` and `.opencode/agents` only.
- **Commands:** `~/.config/opencode/commands` and `.opencode/commands` only (opencode.ai/docs/agents, /commands).

### Inventory on this machine (names and counts)

#### Skills
- **`~/.claude/skills`: 135 entries.**
  - 42 are symlinks into `~/.agents/skills`.
  - 18 are symlinks into the `ai-kit/skills` repo.
  - The rest are real directories: gsd-*, graphify, jev-fast-decision, mermaid-audit and `synced`.
  - opencode sees all 135. pi sees none of the 93 that are not under `.agents`.
- **`~/.agents/skills`: 42.** pi, opencode and codex all read it.
- **`~/.pi/agent/skills`: 33 symlinks**, all into `~/.agents/skills`. Redundant; they collide.
- **opencode `skills/`, `agents/` and `commands/` dirs: empty.** So GSD's opencode artifacts are absent, even though `gsd-install-state.json` exists.

#### Agents
- **`~/.claude/agents`:** 35 gsd-* agents.
- **`~/.pi/agent/agents`:** 6 real sdd-* agents and 4 dangling symlinks.

#### Commands
- **Project `ai-kit/.claude/commands`:** 72 gsd-*.

#### MCP servers
- Claude user (`~/.claude.json`): `codegraph`. Claude plugins add more.
- opencode: `codegraph`, `gsd`.
- cursor (`~/.cursor/mcp.json`): `codegraph`.
- codex: `codegraph`.
- pi: none. `mcp.json` is absent.

#### GSD on pi
- The capability registry lists pi with `installSurface: "profile-marker-only"` and an empty `artifactLayout` (`~/.claude/gsd-core/bin/lib/capability-registry.cjs`, pi entry). GSD installs no skills or commands for pi.

### Smallest asset sync (owner: tools-installer)
1. Delete `~/.pi/agent/skills`. pi already reads `~/.agents/skills`; this removes 33 collision warnings.
2. For cross-host skills that should reach pi, link them into **`~/.agents/skills`**, the shared directory that `skill_lifecycle.py` already maps pi to, instead of only `~/.claude/skills`.
   - The one-line alternative is `"skills": ["~/git/personal/ai-kit/skills"]` in pi `settings.json`.
   - Do **not** add all of `~/.claude/skills`. That would bring in about 75 Claude-runtime gsd-* skills (AskUserQuestion/Agent tools) and duplicate the 42.
3. MCP: the prototype's `plan_mcp` (opencode → pi `mcp.json`).
   - Also add `"pi"` to `postinstall.py` `_AGENT_HOST_IDS`, but codegraph itself has no pi target (`codegraph install --help`). So pi needs the converter path, not `codegraph install`.
4. Prompts and agents: no sync. The user has no Claude user-level commands, and the gsd-* agents and commands are Claude-specific.
5. Re-point the 6 dangling symlinks after reinstalling (§5).

## 5. Upgrade and reinstall plan

### Package manager
- pnpm, as tools-installer's reviewed handoff already says (`host_setup.py:31`): `pnpm add -g --ignore-scripts @earendil-works/pi-coding-agent@1.2.0`.
- Environment: pnpm 11.18.0 and node v24.21.0, which satisfies engines `>=22.19.0`. The bin is `dist/bundle/cli.js`, and no install scripts are needed.
- Risk, unverified: pnpm 11 may enforce a default minimum release age. 1.2.0 was published 2026-10-12T23:03Z. If the install is refused, pin `@1.1.0` or wait until after 2026-10-13T23:03Z.

### Risks from 0.8x to 1.x (CHANGELOG "Breaking" 0.84.1 → 1.2.0)
- **Extension API** (0.86.0 and 0.87.0): `user_bash` now fails closed, the `TurnEndEvent` shape changed, and stream input changed.
  - The user's `rtk.ts` uses only `pi.on("tool_call")` and `isToolCallEventType`, which are still exported (`ca/dist/index.d.ts:9`). Low risk.
  - The subagent extension must come from the **new** package's `examples/`. Do not resurrect the old copy.
- **0.99.0:** MCP, codemode and tool-search are built-in extensions that load by default. `-ne` now also disables them.
- **1.0.0:** the TUI is fullscreen by default (set `tuiMode: "regular"` to keep scrollback), and the system theme is the default (the user pins `theme: dark`, so no change).
- **1.0.3:** Azure was renamed. Not used here.
- **1.0.x:** the default Codex model is `gpt-6.1-sol`. The user pins `gpt-5.6-terra` and `xhigh`, so they are unaffected. Keep pinning `--model` and `--thinking` for headless runs (research 06).
- **1.2.0:** `pi mcp list --json` changed shape, and theme schema URLs moved.
- **Existing `auth.json` OAuth entries** keep their shape (`type`, `access`, `refresh`, `expires`). Expect them to keep working. Run `/login` again if a refresh fails.
- `settings.lastChangelogVersion` is 0.84.1, so pi shows its changelog once.

### What the user must run themselves (in order)
1. `pnpm add -g --ignore-scripts @earendil-works/pi-coding-agent@1.2.0`, then `pi --version`.
2. Re-point the symlinks, using `P=$(dirname $(dirname $(dirname $(readlink -f $(which pi)))))`:
   - `ln -sfn $P/examples/extensions/subagent/{index,agents}.ts ~/.pi/agent/extensions/subagent/`
   - `ln -sfn $P/examples/extensions/subagent/agents/{planner,reviewer,scout,worker}.md ~/.pi/agent/agents/`
   - Or copy the files, so future upgrades cannot break them.
3. `rm -r ~/.pi/agent/skills`. It holds only symlinks into `~/.agents/skills`.
4. `pi update`, which re-fetches the superpowers git package.
5. In pi: `/login xai` (SuperGrok device code). Optionally check that `openai-codex` and `anthropic` still work.
6. Run the sync:
   - Dry run: `python3 -I pi_sync.py --out /tmp/x`.
   - Review the diff.
   - Apply: `python3 -I pi_sync.py --write`.
7. Check `pi --list-models`. `opencode/*` and `opencode-go/*` should appear once the key reference resolves.
8. If `mcp.json` was written, run `pi mcp list`. It exits 1 if a server is down.

## Verified vs inferred

**Verified** (source, config or command output):
- The provider and auth table.
- The schema and validation rules.
- The catalog gap.
- opencode's credentials, models and MCP entries.
- That Cursor is absent from opencode.
- The identical xAI client id.
- That llm-env writes pi's config.
- The dangling symlinks.
- Skill paths, both pi source and docs.
- The prototype's dry-run output and self-check.

**Inferred:**
- That `openai` "Sign in with ChatGPT" works as a second-account slot.
- pnpm 11's release-age default.
- That `!jq` key resolution works end to end in pi. Not run, because pi is not installed. The command itself returns a 52-byte value; the value was not printed.

**Not tested:**
- Any pi run on 1.2.0.
- `/login xai` in pi.
- MCP servers under pi.
