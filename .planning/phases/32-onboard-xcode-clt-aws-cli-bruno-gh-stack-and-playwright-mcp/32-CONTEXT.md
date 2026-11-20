# Phase 32: Onboard Xcode CLT, AWS CLI, Bruno, gh-stack and Playwright MCP - Context

**Gathered:** 2026-11-19 (assumptions mode, after 32-SPEC.md)
**Status:** Ready for planning

<domain>
## Phase Boundary

Five tools are onboarded through the tool-onboarding skill: a detect-only Xcode CLT row with a code-owned hand-off command, AWS CLI v2 through the official user-scope script, Bruno (cask and pinned AppImages), gh-stack as a GitHub CLI extension, and a pinned Playwright MCP server registered in each present agent host. Each has an install, detection, update and removal route that needs no sudo and no login.
</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**5 requirements are locked.** See `32-SPEC.md` for full requirements, boundaries, and acceptance criteria.

Downstream agents MUST read `32-SPEC.md` before planning or implementing. Requirements are not duplicated here.

**In scope (from SPEC.md):** five registry entries with `# Verified` comments, detection, update and removal routes, tests; container checks for AWS CLI and the Playwright launch. *Amended 2026-11-19 (32 D-01, D-04, D-07, D-09, D-14):* small parameter extensions to existing method kinds (a closed hand-off name and a fixed-argv install option on `script`; `raw` as an allowed key on `tarball`), a narrow validated install preference for the AWS CLI script over brew, and per-host MCP config writers.
**Out of scope (from SPEC.md):** running `xcode-select --install`; the `bru` CLI; interactive logins; new method kinds; real-Mac checks.

</spec_lock>

<decisions>
## Implementation Decisions

### Xcode CLT (ONB-11)
- **D-01: A detect-only macOS entry** (`os = ["macos"]`): `cmd` never resolves on PATH (`xcode-select` itself is always present, so it cannot be the `cmd`; `oh-my-zsh` is the precedent, `installer/registry.toml:599-624`) and `detect_path` names a file under `/Library/Developer/CommandLineTools` (`installer/status.py:114-211`; `detect_path` is allowed only on `script` and `brew`, `model.py:45-62,104`). The row shows the exact `xcode-select --install` through a small extension of the manual hand-off path: a `script` method with a never-writable `writable_prefix` (`/Library/Developer/CommandLineTools`) and a **closed hand-off name** param mapped to a code-owned table entry; the method has no `url` and is never executed because `needs_manual` runs first (`installer/executors.py:749-769`; `installer/session.py:736-750`; `installer/engine.py:254-265`). A free-text display string is refused: the registry names actions from a closed set (`.claude/architecture.md:337-342`). No receipt is ever written, so Uninstall offers nothing (`installer/version_status.py:2016-2028`). The grep test asserts `xcode-select --install` appears only in the display table and the registry, never in a runner argv, and that no `installer/` code passes `sudo`, `pkexec`, `doas` or `softwareupdate` to a runner (`ELEVATION_COMMANDS`, `model.py:545-554`). jev first rung none_of_these 0.77 contradicted the evidence; second opinion code_owned_table 0.91. **jev overridden.**
- **D-02: Detect the CLT path only** (the strict SPEC wording); a Mac with Xcode.app but no CLT shows missing with the hand-off, recorded in `# Verified`; a Homebrew `requires` edge on the CLT row is deferred to its own todo (research `SUMMARY.md:154`). jev clt_path_only_no_edge 0.98 (TypeSafe).

### AWS CLI v2 (ONB-12)
- **D-03: A `script` method** with `url = "https://awscli.amazonaws.com/v2/install.sh"`, `shell = "bash"`, no args, `bin_dir = "~/.local/bin"`, `paths = ["~/.local/share/aws-cli/", "~/.local/bin/aws", "~/.local/bin/aws_completer"]`, `update = ["aws", "update"]`, no `remove`, `~/.aws` never in `config_paths`, `requires = ["unzip"]`. Read (not run) from the vendor script: it installs into the user's home by default under `${XDG_DATA_HOME:-~/.local/share}/aws-cli` with symlinks in `${XDG_BIN_HOME:-~/.local/bin}`; Linux needs unzip and verifies the zip with gpg in a temporary keyring (pinned key expiring 2027-07-01) and exits 1 when gpg is missing; macOS uses `installer -pkg ... -target CurrentUserHomeDirectory` (no root); the same version is a no-op (exit 0), an older target exits 2. `aws update` verifies `install.sh.sig` with gpg. The uv and claude script entries are the precedent for `paths`/`update` without `remove` (`registry.toml:74-86,1530-1541`). A custom `XDG_DATA_HOME` or `XDG_BIN_HOME` installs outside the declared `paths` (`env` values are shell-quoted, `executors.py:453-468`): a recorded limit.
- **D-04: A narrow, validated preference ranks this tool's script before brew, honored on every host,** so brew is the real fallback when the script fails (for example gpg missing). The ladder sorts by `_RANK` alone (brew 5, script 10; `installer/resolve.py:15-31,96-99`); ungated, brew would win on every brew host (including Bazzite's linuxbrew) and invert the owner's "script first", and a brew install cannot use `aws update`. `_RANK` is also the install-preference order in `installer/ownership.py`, with a parity test (`tests/test_resolve.py`), so the preference is tested in the ladder test. jev script_first_everywhere 0.92 (TypeSafe).
- **D-05: The container plan covers both hosts:** Fedora with gpg (script install, `aws --version`, a second run is a no-op, uninstall leaves a seeded `~/.aws/config` byte-identical) and debian-slim without gnupg (fails closed with the script's gpg message and the row reports the error or the fallback). Pattern: `tests/test_container_e2e_receipts.py`, `scripts/detect-container-runtime.sh`. jev both_hosts 0.94.

### Bruno (ONB-13)
- **D-06: macOS is `kind = "cask"`, `cask = "bruno"`, `app = "Bruno.app"`** (cask API read live: 4.3.0, no `binary` stanza, no `depends_on.macos`), bundle to `~/Applications` through `--appdir` (`executors.py:699-704`); Bruno has no macOS CLI, so there is nothing to link; uninstall is `brew uninstall --cask` without zap, so `~/Documents/bruno` is kept.
- **D-07: Linux uses two `tarball` methods, one per arch, with `raw = true` and `member = "bruno"`,** URL `https://github.com/usebruno/bruno/releases/download/v{ver}/bruno_{ver}_x86_64_linux.AppImage` and the `arm64` name, pinned `version` and `sha256` together (digests read live from the GitHub release: x86_64 `3c386b10...80bb`, arm64 `6048c3ae...3469`). `raw` becomes an allowed key on `tarball` (the install path checks `raw` without looking at the kind, `installer/download.py:408,418,460`; shared with phase 30's Ghostty). Reason: `github_release` takes no `version` or `sha256` (`installer/model.py:69-82`; it resolves the latest tag at install time, `download.py:116-140`), while `tarball` pins (`model.py:83-96,646-666`); pinning keeps SPEC R3 and phase 33's coverage ("Bruno AppImages") valid, and verify-registry already handles tarball pins (`verify_registry.py:294-341,536-554,1188-1198`). **Own reasoning** (jev pin_version_and_hash low 0.73; first rung low 0.38; the analyzer's unpinned drawio pattern was weighed against SPEC R3 and phase 33). Ledger.
- **D-08: `smoke_argv` is confirmed in a container** (the smallest argument list that runs the Electron binary itself, never an `--appimage-*` runtime flag; `.claude/skills/tool-onboarding/SKILL.md` Common Mistakes). No desktop entry is written (none exists in `installer/` except cargo_distrobox's `desktop_entry.py`): recorded as a gap shared with WezTerm and draw.io; FUSE 2 behavior is a container finding. No method mentions `bru` or `@usebruno/cli`. jev first rung none_of_these 0.84 contradicted the evidence; second opinion confirm_in_container 0.98. **jev overridden.**

### gh-stack (ONB-14)
- **D-09: The `script` kind gains a validated fixed-argv install option** (tokens validated like `update`/`remove`, an elevation head refused, stdin closed, no shell); install argv exactly `gh extension install https://github.com/github/gh-stack`, `requires = ["gh"]`. Today `script` only runs `curl url | shell` (`executors.py:471-491`), so no kind runs a fixed argv; script tokens accept `:` and `/` (`model.py:172,477-485`); a `gh_extension` kind is out (research `SUMMARY.md:70`). **Own reasoning** (jev script_argv_install low 0.67; first rung low 0.44). Ledger.
- **D-10: Detection is file-based:** `detect_path = "~/.local/share/gh/extensions/gh-stack/manifest.yml"`. Live (gh 2.101.0, scratch HOME, no token, stdin closed): `install` and a second `install` exit 0; `gh extension list`, `upgrade stack` and `remove stack` each exit 4 ("please run: gh auth login") without prompting; upstream `command.go:421` disables the auth check only on `install`. `GH_DATA_DIR`/`XDG_DATA_HOME` relocation is a recorded limit. This **amends ONB-14 / SPEC R4** ("detected through `gh extension list`"); **flagged: needs confirmation**. jev manifest_file 0.87 (TypeSafe).
- **D-11: Update is `["gh","extension","upgrade","stack"]`** through PATH (`gh` is not a declared leaf; `update.py:531-545`) and reports the login-required message cleanly; **removal deletes the receipt-proven `paths = ["~/.local/share/gh/extensions/gh-stack/"]`**; the SPEC's `remove = ["gh","extension","remove","stack"]` is dropped because `_recipe_argv` binds the first word to a receipt-proven leaf of the same tool (`installer/uninstall.py:343-373`) and would never run it; relaxing that rule is a security-relevant change and out of scope. This amends ONB-14 / SPEC R4; **flagged: needs confirmation**. jev first rung none_of_these 0.95 contradicted the evidence; second opinion delete_proven_folder 0.99. **jev overridden.**

### Playwright MCP (ONB-15)
- **D-12: `tier = "ai"`, `requires = ["bun"]`, a `bun` method** `npm_pkg = "@playwright/mcp"` with `versions = { "@playwright/mcp" = "<pin>" }` and `min_node` matching the pin; `cmd = "playwright-mcp"` gives detection, update and L1 removal; the registered server is `bunx @playwright/mcp@<pin>` reading the same `versions` entry (one pin source). Precedents: pi and mmdc (`registry.toml:2805-2810,3290-3297`); the bun executor appends `name@version` (`executors.py:633-653`). jev install_and_register_one_pin 0.72.
- **D-13: The pin is `0.0.85` (Node 18 floor, published 2026-11-09);** `0.0.86` (Node >= 20, published 2026-11-18, npm latest) is recorded in `# Verified` as the alternative. Pins are bumped by hand or by catalog-audit: `verify-registry` checks only `CHECKABLE_KINDS` downloads (`verify_registry.py:344-395`), so SPEC acceptance "verify-registry passes for every new pinned artifact" does not cover the npm pin and is reworded. jev research_version_node18 0.81 (TypeSafe).
- **D-14: Registration is a singular postinstall hook that writes each present host's real MCP config file through a merge-safe writer** (existing `present_harnesses`/`register_hooks`/`receipt.hooks`, `postinstall.py:131-158,641-675`; `agent_settings` already returns `set_by_you`, keeps user keys and refuses on a write race, `agent_settings.py:36,610-621`), with a file-revert undo. An existing `playwright` entry, or a host whose official Playwright plugin is enabled, counts as existing and is kept. No MCP-server writer exists for any host today (adapters point at settings files, `agent_env.py:51-77`; the only registration route calls the vendor binary, `postinstall.py:286-315`); each host's file path and schema (Claude user scope may be `~/.claude.json`, not `settings.json`) is confirmed in planning. **Own reasoning** (jev call_host_cli low 0.64; first rung low 0.48). Ledger.
- **D-15: The Flatpak Chrome path** (`/var/lib/flatpak/exports/bin/com.google.Chrome`, only when that file exists) goes into the `env` of each server entry the hook writes, which also covers cursor-agent (8 env vars only); no `~/.myshellrc` tweak bundle (those are Policies rows). The `~/.claude/settings.json` `env` key (the only fix for the official plugin's server) is written only after consent, as **a separate step listed in the plan confirmation** (a new reviewed path: the old consent machinery was retired in Phase 25, `.claude/architecture.md:771-775`, and install-time questions are a TUNE-04 miss); a declined plan writes nothing, and `--yes` counts as that consent. jev plan_step_listed 0.99 (TypeSafe).

### Tests and corrections
- **D-16:** Registry tests for each entry; the Xcode grep test; the AWS container checks (D-05); a Playwright headless launch smoke in a Fedora/Bazzite container with no Flatpak Chrome (for example distro chromium via `--executable-path`); the phase 27 skill table has no new terminal row. SPEC edge rows corrected: Linux hosts show an OS-gated row as a dimmed "– unavailable" row, not hidden (`installer/catalog_tui.py:208-216`, `resolve.py:158-188`); an unauthenticated `gh` does not list extensions (D-10).

### Claude's Discretion
- Entry ids, the closed hand-off name, the wording of the `# Verified` comments, and the Playwright server entry's key spelling per host.

### Folded Todos
- The pending todos for Xcode CLT, Bruno, AWS CLI, gh-stack and the Playwright Flatpak Chrome path (roadmap note).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `.planning/phases/32-onboard-xcode-clt-aws-cli-bruno-gh-stack-and-playwright-mcp/32-SPEC.md` — Locked requirements — MUST read before planning
- `.planning/research/SUMMARY.md`, `.planning/research/2026-10-13-from-ai-kit/16-playwright-chrome-bazzite.md`
- `installer/model.py`, `installer/executors.py`, `installer/resolve.py`, `installer/engine.py`, `installer/status.py`, `installer/uninstall.py`, `installer/update.py`, `installer/postinstall.py`, `installer/agent_settings.py`, `installer/agent_env.py`, `installer/download.py`, `installer/verify_registry.py`
- `.claude/architecture.md` (closed action sets, consent retirement), `.planning/phases/27-tool-onboarding-skill-terminal-defaults-as-rules/27-CONTEXT.md`
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `oh-my-zsh`'s non-PATH `cmd` plus `detect_path`; the manual hand-off path (`needs_manual`); drawio and pi/mmdc registry entries; `agent_settings` merge-safe writer; the container e2e harness.

### Established Patterns
- The registry selects actions by name from closed sets; detection by `cmd`/`detect_path`/`bin_dir`; removal by receipt-proven paths; pins live in the catalog and `verify-registry` bumps them.

### Integration Points
- `METHOD_PARAMS` (`model.py`), `resolve._RANK`, `POSTINSTALL_HOOK_NAMES`, per-host adapters in `agent_env.py`.
</code_context>

<specifics>
## Specific Ideas

Live facts that changed the SPEC (amended in this commit): gh-stack's list, upgrade and remove need a login (only install works without one); no method kind runs a fixed argv or shows `xcode-select --install`; `github_release` has no pins; the consent machinery was retired; no MCP writer exists; `_RANK` puts brew before script; the Playwright latest needs Node 20; `verify-registry` does not check npm pins.
</specifics>

<deferred>
## Deferred Ideas

- A Homebrew `requires` edge on the Xcode CLT row: its own todo.
- To confirm in planning: each host's MCP config path, schema and any `mcp add` command (Claude `~/.claude.json` vs `settings.json`, Cursor, Copilot CLI, OpenCode, Codex); whether `bunx @playwright/mcp@<pin>` reuses a global install; Bruno's non-GUI `--version` argv, FUSE 2 and `--no-sandbox` needs; whether Homebrew accepts Xcode.app alone in place of the CLT; the macOS `installer -pkg -target CurrentUserHomeDirectory` route without admin rights (Mac UAT).

### Reviewed Todos (not folded)
None other matched.
</deferred>
