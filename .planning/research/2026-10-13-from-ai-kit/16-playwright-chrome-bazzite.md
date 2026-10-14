# Playwright + Chrome MCPs on Bazzite (2026-10-13)

Claude Code 2.1.296. Plugin `playwright@claude-plugins-official` at commit b8e53f1c05df. `@playwright/mcp` 0.0.83 (bundles playwright-core 1.64.0-alpha).

## Verdict

- **The Playwright MCP is broken in every session, including subagents.** The cause is the upstream default browser channel, not the plugin.
- **A one-line fix works.** It was tested end to end without editing any config. Put this in `~/.claude/settings.json`:
  `"env": {"PLAYWRIGHT_MCP_EXECUTABLE_PATH": "/var/lib/flatpak/exports/bin/com.google.Chrome"}`
- **claude-in-chrome is not connected right now.** Its tools load, but the extension bridge reports "not connected".
- **Subagents do get both MCPs.** This general-purpose subagent saw `mcp__plugin_playwright_playwright__*` and `mcp__claude-in-chrome__*` as deferred tools, loaded them with ToolSearch, and called them.
  - The calls reached the servers: the errors came from the servers, not from a missing tool.
  - An agent with a `tools:` allowlist only gets the MCP tools it names. `gsd-dom-verifier` names `mcp__chrome-devtools__*` (not installed) and `mcp__claude-in-chrome__*` (not connected), and does not name Playwright. Today it has no working browser at all.

## 1. Configuration evidence

**Plugin config:**
- The plugin's `.mcp.json`, identical in all 3 cached versions, is `{"playwright": {"command": "npx", "args": ["@playwright/mcp@latest"]}}`.
- It has no args, no env and no `userConfig`. The plugin is only `.mcp.json` plus `plugin.json`, with no skills.

**Why it runs as `pnpm dlx`:**
- `~/.local/bin/npx` is the tools-installer redirect shim: `exec ~/.volta/bin/pnpm dlx "$@"`.
- The live process tree confirms it: `claude` -> `pnpm dlx @playwright/mcp@latest` -> `node .../@playwright/mcp/0.0.83/cli.js`.

**Where the wrong default lives.** It is in `@playwright/mcp`, inside the bundled `playwright-core/lib/coreBundle.js`, function `validateBrowserConfig`:
```js
if (!browserName) { browserName = "chromium"; if (browser.launchOptions.channel === void 0) browser.launchOptions.channel = "chrome"; }
```
Channel `chrome` resolves to the hard-coded `/opt/google/chrome/chrome`.

**Browser option mapping** (`resolveBrowserParam`):
- `chrome` and `msedge*` -> that channel.
- `chromium` -> channel `chrome-for-testing`, which means Playwright's own download in `~/.cache/ms-playwright`.
- `firefox` and `webkit` -> the bundled builds.
- `--help` lists only `chrome, firefox, webkit, msedge`, but `chromium` is accepted.

**Documented options** (README, verified online, plus the env-var names found in the installed source):

| Flag | Env var |
| --- | --- |
| `--browser` | `PLAYWRIGHT_MCP_BROWSER` |
| `--executable-path` | `PLAYWRIGHT_MCP_EXECUTABLE_PATH` |
| `--headless` (headed is the default) | `PLAYWRIGHT_MCP_HEADLESS` |
| `--isolated` (profile kept in memory) | `PLAYWRIGHT_MCP_ISOLATED` |
| `--user-data-dir` | `PLAYWRIGHT_MCP_USER_DATA_DIR` |

The default mode uses a persistent profile, which the README places at `~/.cache/ms-playwright/mcp-{channel}-{hash}`.

**Browsers on this machine:**
- `command -v google-chrome chromium chromium-browser`: no results.
- `rpm -q google-chrome-stable`: not installed.
- `/opt/google`: does not exist (`/opt` is a symlink to `var/opt`).
- Flatpak:
  - `com.google.Chrome` 155.0.8059.39, wrapper at `/var/lib/flatpak/exports/bin/com.google.Chrome` (`exec flatpak run --branch=stable --arch=x86_64 com.google.Chrome "$@"`).
  - `org.chromium.Chromium` 155.0.8059.39.
- Playwright cache (`~/.cache/ms-playwright`): `chromium-1228/1234/1237/1243/1246`.
  - The current `@latest` needs **1247**, so the cache is one revision behind.
  - This is the drift problem: every `@latest` revision bump orphans the cache.

## 2. Live Playwright MCP (in-session)

`browser_navigate https://example.com` returned:
```
Error: async initializeServer: Chromium distribution 'chrome' is not found at /opt/google/chrome/chrome
Run "pnpm exec playwright install chrome"
```
- Snapshot and close were not reached in a meaningful way, because no page ever opened.
- The suggested fix is wrong for this host. `install chrome` installs a system Chrome package into `/opt`, which does not fit rpm-ostree (inferred, not run). `pnpm exec` is also meaningless under `pnpm dlx`.

## 3. claude-in-chrome

I made one read-only call, `tabs_context_mcp`. It returned "Browser extension is not connected… ensure the Claude browser extension is installed and running… logged into claude.ai with the same account". I made no other calls.

## 4. Candidate fixes, tested without editing config

**Test method:**
- I wrote a stdio JSON-RPC probe (`scratchpad/pwtest/probe.py`).
- It sends initialize, tools/list (25 tools), `browser_navigate https://example.com`, then `browser_close`.
- It runs against the already-cached `cli.js`. Nothing new was fetched; `pnpm dlx` had already populated the cache.

| Candidate | Result |
| --- | --- |
| default (no flag) | FAIL: same `/opt/google/chrome/chrome` error |
| `--browser chromium` | FAIL: `Browser "chrome-for-testing" is not installed; expected executable at ~/.cache/ms-playwright/chromium-1247/chrome-linux64/chrome. Run npx @playwright/mcp install-browser chrome-for-testing` |
| `--executable-path ~/.cache/ms-playwright/chromium-1246/chrome-linux64/chrome` | OK, "Example Domain" (works now, breaks when that cache dir is pruned) |
| same path, but via the env var `PLAYWRIGHT_MCP_EXECUTABLE_PATH` | OK |
| `--executable-path /var/lib/flatpak/exports/bin/com.google.Chrome` (headless, isolated) | OK |
| Flatpak Chrome, persistent `--user-data-dir` in scratchpad | OK, but **the profile dir stayed empty on the host**. The Flatpak sandbox has a private `/tmp` and no `~` access, so the profile is effectively ephemeral. |
| Flatpak Chrome, default persistent mode (no profile flags) | OK |

**End-to-end test through Claude Code itself, with no file edits:**
```
claude -p "<navigate example.com, close>" --model haiku \
  --settings '{"env":{"PLAYWRIGHT_MCP_EXECUTABLE_PATH":"/var/lib/flatpak/exports/bin/com.google.Chrome","PLAYWRIGHT_MCP_HEADLESS":"1","PLAYWRIGHT_MCP_ISOLATED":"1"}}' \
  --allowedTools=mcp__plugin_playwright_playwright__browser_navigate,mcp__plugin_playwright_playwright__browser_close,ToolSearch
-> "Example Domain"
```
This proves that settings `env` reaches the **plugin** MCP server process. Supporting evidence: the Claude-spawned MCP processes carry the full environment (116 vars). The cursor-agent-spawned ones carry only 8 vars.

### How Claude Code lets you override a plugin MCP (docs)

- **Same-name override does not work for plugins.** Per https://code.claude.com/docs/en/mcp, duplicates across the local/project/user scopes are matched by name, but "plugins and connectors [are matched] by endpoint". A user-scope `playwright` server with different args therefore would **not** replace the plugin server; both would run.
  - Override route (a) means: add the server at user scope (`~/.claude.json`), then disable the plugin server with the `/mcp` toggle (`disabledMcpServers`, stored per project in `~/.claude.json`) or with `deniedMcpServers`. Alternatively, disable the plugin entirely through `enabledPlugins`.
- **Plugins cannot be parameterised from outside** except through `userConfig` (`${user_config.KEY}`), and this plugin declares none (https://code.claude.com/docs/en/plugins-reference).
- **settings `env`** is documented only as "for every session and its subprocesses". The test above confirms that this includes stdio MCP servers, unless `CLAUDE_CODE_MCP_ALLOWLIST_ENV=1` is set.

### Ranked fixes

1. **(a, simplest) `env.PLAYWRIGHT_MCP_EXECUTABLE_PATH` -> the Flatpak Chrome wrapper, in `~/.claude/settings.json`.**
   - Size: 1 key.
   - Survives plugin updates and `@latest` revision bumps, because Flatpak updates Chrome.
   - No plugin disable and no duplicate server.
   - Also reaches subagents and `claude -p` children.
   - Side effect: Bash tool subprocesses also see the variable. That is harmless, because only `@playwright/mcp` reads it.
   - Optional: add `PLAYWRIGHT_MCP_ISOLATED=1`, which matches the effective Flatpak behaviour.
   - Limits:
     - Uploads are probably limited (untested): the Flatpak sandbox likely can't read host paths outside Downloads/Documents/Pictures/Music/Videos, so `browser_file_upload` from `~/git/...` is likely to fail.
     - The profile is not persisted.
     - Headed mode is untested; I skipped it so no windows would pop up on the desktop.
2. **(c) as an MCP arg instead of env.** Same effect, but it needs route (a)'s user-scope server plus disabling the plugin. That is more config for no gain over fix 1.
3. **(b) `PLAYWRIGHT_MCP_BROWSER=chromium` plus `pnpm dlx @playwright/mcp@latest install-browser chrome-for-testing`.**
   - Gives a non-sandboxed browser, so uploads work.
   - Re-breaks on each Chromium revision bump until the install is re-run. The cache already shows 5 stale revisions.
   - This would be a package install. I did not run it.
   - Viable only with a pinned version, e.g. `@playwright/mcp@0.0.83`, which needs override route (a).
4. **(d) Patching the cached `.mcp.json`.** Overwritten on every plugin update; there are already 3 cached versions. Reject.
5. **(e) Upstream issue.** Worth filing (draft below), but it is not a local fix.

**Out of scope:** cursor-agent spawns its own Playwright MCP with a stripped env, so it has the same bug and needs its own `env` in Cursor's MCP config.

## 5. "Claude setup" patch: Config Doctor rows, not a new script

**What Config Doctor already has:**
- Per-row check/apply.
- A `dry=True` preview (`literal_resulting_config` shown in `ConfirmApplyScreen` for security-relevant rows).
- Atomic writes (`config_doctor_appliers.atomic_write_json`: tempfile + fsync + `os.replace`, mode preserved).
- Idempotence by construction: a row whose current value equals the recommended value is a no-op.
- It targets `~/.claude/settings.json` (user scope).
- Missing pieces: **backups** and **project scope**.

**tools-installer overlap:**
- `installer/tweaks.py` writes only marker blocks into `~/.myshellrc`.
- `agent_policy.py` writes opencode/antigravity permissions and guidance blocks.
- Neither touches these Claude keys, so there is no overlap.
- The `npx` -> `pnpm dlx` guard there explains the launch path.

**Smaller option (ponytail): 3 new `CheckRow`s plus one generic applier.**
- `claude-disable-claudeai-connectors`: read `_nested(ctx, "disableClaudeAiConnectors", default=False)`, recommend `True`.
- `claude-sync-claudeai-skills`: read `_nested(ctx, "syncClaudeAiSkills", default=True)`, recommend `False`.
  - Valid only at user, local or managed scope. A `false` in project `.claude/settings.json` is ignored (per the settings docs).
- `claude-playwright-executable-path`:
  - Applicable only when `enabledPlugins["playwright@claude-plugins-official"]` is set, `/opt/google/chrome/chrome` is missing, and neither `env.PLAYWRIGHT_MCP_EXECUTABLE_PATH` nor `env.PLAYWRIGHT_MCP_BROWSER` is set.
  - Recommends the first existing path among `/var/lib/flatpak/exports/bin/com.google.Chrome`, `~/.local/share/flatpak/exports/bin/com.google.Chrome`, and the same two for `org.chromium.Chromium`.
  - If none exists, it is report-only, with the `install-browser` hint.
- `_apply_claude_key(ctx, (key_path, value), dry)`: about 15 lines, mirroring `_apply_claude_sandbox_enabled`. It copies `settings.json` to `settings.json.bak` before the real write. That is the one missing requirement, and it is scoped to the new applier so existing rows are untouched.
- Tests: one per row in `tests/test_config_doctor.py` (dry run returns the diff, apply writes, re-apply is a no-op, the `.bak` exists).

**Skipped on purpose:**
- A project-scope chooser. The Playwright path is machine-specific, so it must never go in a committed `.claude/settings.json`.
- `syncClaudeAiSkills` is ignored there anyway.
- Users who want per-project behaviour can hand-edit `settings.local.json`.
- A standalone script would duplicate the TTY, preview and atomic-write plumbing that Config Doctor already has, roughly 150+ lines against about 60.

## 6. Upstream issue draft (do not file)

**Repo:** `microsoft/playwright-mcp`.
- The default (`channel: "chrome"`) lives in its code, now bundled in playwright-core.
- The plugin just forwards `@playwright/mcp@latest`.
- A secondary, optional request to `anthropics/claude-plugins-official`: add `userConfig` for browser/executable-path.

**Title:** Default `chrome` channel fails on immutable/Flatpak Linux (Fedora Atomic, Bazzite); add fallback or clearer guidance

**Body:**
> On Linux hosts where Chrome is installed only as a Flatpak (Fedora Atomic/Bazzite/Silverblue, SteamOS-likes), `@playwright/mcp` with no flags fails on the first tool call because the default config hard-sets `channel: "chrome"`, which resolves to `/opt/google/chrome/chrome`.
>
> The suggested remedy (`playwright install chrome`) installs a system Chrome package into `/opt`, which does not fit rpm-ostree hosts. `--browser chromium` then fails until `install-browser chrome-for-testing` is run, and fails again after every `@latest` revision bump.
>
> **Repro**
> 1. Fedora Atomic host, Chrome via `flatpak install com.google.Chrome`, no `/opt/google`.
> 2. `npx @playwright/mcp@latest` (here 0.0.83), connect any MCP client, call `browser_navigate {"url":"https://example.com"}`.
> 3. Result: `Error: async initializeServer: Chromium distribution 'chrome' is not found at /opt/google/chrome/chrome`.
>
> **Workaround verified:** `PLAYWRIGHT_MCP_EXECUTABLE_PATH=/var/lib/flatpak/exports/bin/com.google.Chrome` works (headless, isolated, and default persistent mode). Note that the persistent profile isn't written to the host because of the Flatpak sandbox.
>
> **Ask (any of):**
> - (1) When channel `chrome` is missing, fall back to an installed chrome-for-testing/chromium, or detect the Flatpak exports (`/var/lib/flatpak/exports/bin/com.google.Chrome`, `~/.local/share/flatpak/exports/bin/...`).
> - (2) Make the error mention `--executable-path` / `PLAYWRIGHT_MCP_EXECUTABLE_PATH` and `--browser chromium` + `install-browser`.
> - (3) List `chromium` in the `--browser` help text; it is accepted, mapping to chrome-for-testing, but undocumented in `--help`/README.
>
> **Environment:** Bazzite (Fedora 44 Atomic), kernel 7.2.4, Node 24.18 (Volta), pnpm dlx, @playwright/mcp 0.0.83 / playwright-core 1.64.0-alpha-1790635538000, Flatpak com.google.Chrome 155.0.8059.39. Client: Claude Code 2.1.296 via the `playwright@claude-plugins-official` plugin.

## Not checked

- Headed mode with Flatpak Chrome.
- `browser_file_upload` from host paths under Flatpak.
- Whether claude.ai connectors reach subagents.
- Why claude-in-chrome is disconnected; I did not inspect the extension, because that would mean touching the user's browser.

Sources: [microsoft/playwright-mcp README](https://github.com/microsoft/playwright-mcp), [microsoft/playwright#41631](https://github.com/microsoft/playwright/issues/41631), [Claude Code MCP docs](https://code.claude.com/docs/en/mcp), [plugins reference](https://code.claude.com/docs/en/plugins-reference), [settings](https://code.claude.com/docs/en/settings), [env vars](https://code.claude.com/docs/en/env-vars).
