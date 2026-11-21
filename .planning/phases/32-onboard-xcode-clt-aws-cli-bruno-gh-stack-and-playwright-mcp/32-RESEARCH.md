# Phase 32: Onboard Xcode CLT, AWS CLI, Bruno, gh-stack and Playwright MCP - Research

**Researched:** 2026-11-21
**Domain:** registry onboarding (`installer/registry.toml`), small method-kind extensions (`installer/model.py`, `installer/executors.py`, `installer/resolve.py`), an MCP-server registration writer (`installer/postinstall.py`, `installer/agent_settings.py`), container proofs (`scripts/container-e2e-verify.sh`)
**Confidence:** MEDIUM overall (HIGH for the code facts and live pins; MEDIUM-LOW for the per-host MCP file schemas and the AppImage runtime behavior, which need a container or the owner)

<user_constraints>
## User Constraints (from CONTEXT.md)

Copied verbatim from `32-CONTEXT.md` (2026-11-19, written before phases 27 to 31 executed; see `## CONTEXT Reconciliation` for every statement the code has since moved past).

### Locked Decisions

#### Xcode CLT (ONB-11)
- **D-01: A detect-only macOS entry** (`os = ["macos"]`): `cmd` never resolves on PATH (`xcode-select` itself is always present, so it cannot be the `cmd`; `oh-my-zsh` is the precedent, `installer/registry.toml:599-624`) and `detect_path` names a file under `/Library/Developer/CommandLineTools` (`installer/status.py:114-211`; `detect_path` is allowed only on `script` and `brew`, `model.py:45-62,104`). The row shows the exact `xcode-select --install` through a small extension of the manual hand-off path: a `script` method with a never-writable `writable_prefix` (`/Library/Developer/CommandLineTools`) and a **closed hand-off name** param mapped to a code-owned table entry; the method has no `url` and is never executed because `needs_manual` runs first (`installer/executors.py:749-769`; `installer/session.py:736-750`; `installer/engine.py:254-265`). A free-text display string is refused: the registry names actions from a closed set (`.claude/architecture.md:337-342`). No receipt is ever written, so Uninstall offers nothing (`installer/version_status.py:2016-2028`). The grep test asserts `xcode-select --install` appears only in the display table and the registry, never in a runner argv, and that no `installer/` code passes `sudo`, `pkexec`, `doas` or `softwareupdate` to a runner (`ELEVATION_COMMANDS`, `model.py:545-554`). jev first rung none_of_these 0.77 contradicted the evidence; second opinion code_owned_table 0.91. **jev overridden.**
- **D-02: Detect the CLT path only** (the strict SPEC wording); a Mac with Xcode.app but no CLT shows missing with the hand-off, recorded in `# Verified`; a Homebrew `requires` edge on the CLT row is deferred to its own todo (research `SUMMARY.md:154`). jev clt_path_only_no_edge 0.98 (TypeSafe).

#### AWS CLI v2 (ONB-12)
- **D-03: A `script` method** with `url = "https://awscli.amazonaws.com/v2/install.sh"`, `shell = "bash"`, no args, `bin_dir = "~/.local/bin"`, `paths = ["~/.local/share/aws-cli/", "~/.local/bin/aws", "~/.local/bin/aws_completer"]`, `update = ["aws", "update"]`, no `remove`, `~/.aws` never in `config_paths`, `requires = ["unzip"]`. Read (not run) from the vendor script: it installs into the user's home by default under `${XDG_DATA_HOME:-~/.local/share}/aws-cli` with symlinks in `${XDG_BIN_HOME:-~/.local/bin}`; Linux needs unzip and verifies the zip with gpg in a temporary keyring (pinned key expiring 2027-07-01) and exits 1 when gpg is missing; macOS uses `installer -pkg ... -target CurrentUserHomeDirectory` (no root); the same version is a no-op (exit 0), an older target exits 2. `aws update` verifies `install.sh.sig` with gpg. The uv and claude script entries are the precedent for `paths`/`update` without `remove` (`registry.toml:74-86,1530-1541`). A custom `XDG_DATA_HOME` or `XDG_BIN_HOME` installs outside the declared `paths` (`env` values are shell-quoted, `executors.py:453-468`): a recorded limit.
- **D-04: A narrow, validated preference ranks this tool's script before brew, honored on every host,** so brew is the real fallback when the script fails (for example gpg missing). The ladder sorts by `_RANK` alone (brew 5, script 10; `installer/resolve.py:15-31,96-99`); ungated, brew would win on every brew host (including Bazzite's linuxbrew) and invert the owner's "script first", and a brew install cannot use `aws update`. `_RANK` is also the install-preference order in `installer/ownership.py`, with a parity test (`tests/test_resolve.py`), so the preference is tested in the ladder test. jev script_first_everywhere 0.92 (TypeSafe).
- **D-05: The container plan covers both hosts:** Fedora with gpg (script install, `aws --version`, a second run is a no-op, uninstall leaves a seeded `~/.aws/config` byte-identical) and debian-slim without gnupg (fails closed with the script's gpg message and the row reports the error or the fallback). Pattern: `tests/test_container_e2e_receipts.py`, `scripts/detect-container-runtime.sh`. jev both_hosts 0.94.

#### Bruno (ONB-13)
- **D-06: macOS is `kind = "cask"`, `cask = "bruno"`, `app = "Bruno.app"`** (cask API read live: 4.3.0, no `binary` stanza, no `depends_on.macos`), bundle to `~/Applications` through `--appdir` (`executors.py:699-704`); Bruno has no macOS CLI, so there is nothing to link; uninstall is `brew uninstall --cask` without zap, so `~/Documents/bruno` is kept.
- **D-07: Linux uses two `tarball` methods, one per arch, with `raw = true` and `member = "bruno"`,** URL `https://github.com/usebruno/bruno/releases/download/v{ver}/bruno_{ver}_x86_64_linux.AppImage` and the `arm64` name, pinned `version` and `sha256` together (digests read live from the GitHub release: x86_64 `3c386b10...80bb`, arm64 `6048c3ae...3469`). `raw` becomes an allowed key on `tarball` (the install path checks `raw` without looking at the kind, `installer/download.py:408,418,460`; shared with phase 30's Ghostty). Reason: `github_release` takes no `version` or `sha256` (`installer/model.py:69-82`; it resolves the latest tag at install time, `download.py:116-140`), while `tarball` pins (`model.py:83-96,646-666`); pinning keeps SPEC R3 and phase 33's coverage ("Bruno AppImages") valid, and verify-registry already handles tarball pins (`verify_registry.py:294-341,536-554,1188-1198`). **Own reasoning** (jev pin_version_and_hash low 0.73; first rung low 0.38; the analyzer's unpinned drawio pattern was weighed against SPEC R3 and phase 33). Ledger.
- **D-08: `smoke_argv` is confirmed in a container** (the smallest argument list that runs the Electron binary itself, never an `--appimage-*` runtime flag; `.claude/skills/tool-onboarding/SKILL.md` Common Mistakes). No desktop entry is written (none exists in `installer/` except cargo_distrobox's `desktop_entry.py`): recorded as a gap shared with WezTerm and draw.io; FUSE 2 behavior is a container finding. No method mentions `bru` or `@usebruno/cli`. jev first rung none_of_these 0.84 contradicted the evidence; second opinion confirm_in_container 0.98. **jev overridden.**

#### gh-stack (ONB-14)
- **D-09: The `script` kind gains a validated fixed-argv install option** (tokens validated like `update`/`remove`, an elevation head refused, stdin closed, no shell); install argv exactly `gh extension install https://github.com/github/gh-stack`, `requires = ["gh"]`. Today `script` only runs `curl url | shell` (`executors.py:471-491`), so no kind runs a fixed argv; script tokens accept `:` and `/` (`model.py:172,477-485`); a `gh_extension` kind is out (research `SUMMARY.md:70`). **Own reasoning** (jev script_argv_install low 0.67; first rung low 0.44). Ledger.
- **D-10: Detection is file-based:** `detect_path = "~/.local/share/gh/extensions/gh-stack/manifest.yml"`. Live (gh 2.101.0, scratch HOME, no token, stdin closed): `install` and a second `install` exit 0; `gh extension list`, `upgrade stack` and `remove stack` each exit 4 ("please run: gh auth login") without prompting; upstream `command.go:421` disables the auth check only on `install`. `GH_DATA_DIR`/`XDG_DATA_HOME` relocation is a recorded limit. This **amends ONB-14 / SPEC R4** ("detected through `gh extension list`"); **flagged: needs confirmation**. jev manifest_file 0.87 (TypeSafe).
- **D-11: Update is `["gh","extension","upgrade","stack"]`** through PATH (`gh` is not a declared leaf; `update.py:531-545`) and reports the login-required message cleanly; **removal deletes the receipt-proven `paths = ["~/.local/share/gh/extensions/gh-stack/"]`**; the SPEC's `remove = ["gh","extension","remove","stack"]` is dropped because `_recipe_argv` binds the first word to a receipt-proven leaf of the same tool (`installer/uninstall.py:343-373`) and would never run it; relaxing that rule is a security-relevant change and out of scope. This amends ONB-14 / SPEC R4; **flagged: needs confirmation**. jev first rung none_of_these 0.95 contradicted the evidence; second opinion delete_proven_folder 0.99. **jev overridden.**

#### Playwright MCP (ONB-15)
- **D-12: `tier = "ai"`, `requires = ["bun"]`, a `bun` method** `npm_pkg = "@playwright/mcp"` with `versions = { "@playwright/mcp" = "<pin>" }` and `min_node` matching the pin; `cmd = "playwright-mcp"` gives detection, update and L1 removal; the registered server is `bunx @playwright/mcp@<pin>` reading the same `versions` entry (one pin source). Precedents: pi and mmdc (`registry.toml:2805-2810,3290-3297`); the bun executor appends `name@version` (`executors.py:633-653`). jev install_and_register_one_pin 0.72.
- **D-13: The pin is `0.0.85` (Node 18 floor, published 2026-11-09);** `0.0.86` (Node >= 20, published 2026-11-18, npm latest) is recorded in `# Verified` as the alternative. Pins are bumped by hand or by catalog-audit: `verify-registry` checks only `CHECKABLE_KINDS` downloads (`verify_registry.py:344-395`), so SPEC acceptance "verify-registry passes for every new pinned artifact" does not cover the npm pin and is reworded. jev research_version_node18 0.81 (TypeSafe).
- **D-14: Registration is a singular postinstall hook that writes each present host's real MCP config file through a merge-safe writer** (existing `present_harnesses`/`register_hooks`/`receipt.hooks`, `postinstall.py:131-158,641-675`; `agent_settings` already returns `set_by_you`, keeps user keys and refuses on a write race, `agent_settings.py:36,610-621`), with a file-revert undo. An existing `playwright` entry, or a host whose official Playwright plugin is enabled, counts as existing and is kept. No MCP-server writer exists for any host today (adapters point at settings files, `agent_env.py:51-77`; the only registration route calls the vendor binary, `postinstall.py:286-315`); each host's file path and schema (Claude user scope may be `~/.claude.json`, not `settings.json`) is confirmed in planning. **Own reasoning** (jev call_host_cli low 0.64; first rung low 0.48). Ledger.
- **D-15: The Flatpak Chrome path** (`/var/lib/flatpak/exports/bin/com.google.Chrome`, only when that file exists) goes into the `env` of each server entry the hook writes, which also covers cursor-agent (8 env vars only); no `~/.myshellrc` tweak bundle (those are Policies rows). The `~/.claude/settings.json` `env` key (the only fix for the official plugin's server) is written only after consent, as **a separate step listed in the plan confirmation** (a new reviewed path: the old consent machinery was retired in Phase 25, `.claude/architecture.md:771-775`, and install-time questions are a TUNE-04 miss); a declined plan writes nothing, and `--yes` counts as that consent. jev plan_step_listed 0.99 (TypeSafe).

#### Tests and corrections
- **D-16:** Registry tests for each entry; the Xcode grep test; the AWS container checks (D-05); a Playwright headless launch smoke in a Fedora/Bazzite container with no Flatpak Chrome (for example distro chromium via `--executable-path`); the phase 27 skill table has no new terminal row. SPEC edge rows corrected: Linux hosts show an OS-gated row as a dimmed "– unavailable" row, not hidden (`installer/catalog_tui.py:208-216`, `resolve.py:158-188`); an unauthenticated `gh` does not list extensions (D-10).

### Claude's Discretion
- Entry ids, the closed hand-off name, the wording of the `# Verified` comments, and the Playwright server entry's key spelling per host.

### Deferred Ideas (OUT OF SCOPE)
- A Homebrew `requires` edge on the Xcode CLT row: its own todo.
- To confirm in planning: each host's MCP config path, schema and any `mcp add` command (Claude `~/.claude.json` vs `settings.json`, Cursor, Copilot CLI, OpenCode, Codex); whether `bunx @playwright/mcp@<pin>` reuses a global install; Bruno's non-GUI `--version` argv, FUSE 2 and `--no-sandbox` needs; whether Homebrew accepts Xcode.app alone in place of the CLT; the macOS `installer -pkg -target CurrentUserHomeDirectory` route without admin rights (Mac UAT).

(The second bullet is "to confirm in planning", not out of scope; this research answers what it can of it in `## Per-host MCP files`.)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ONB-11 | Xcode CLT detected on macOS; when missing the exact `xcode-select --install` is shown; never run; no uninstall | `## Entry 1: Xcode CLT`; reconciliation R1-R4 (handoff must be unconditional, update must be refused, ownership reads "installer" by elimination) |
| ONB-12 | AWS CLI v2 via official user-scope `install.sh` (gpg kept, no `--system`), brew `awscli` fallback, `aws update`, `~/.aws` untouched | `## Entry 2: AWS CLI v2`; the D-04 preference design; the env pin that keeps gpg on; container target D-05 |
| ONB-13 | Bruno via cask on macOS and digest-verified AppImage per arch on Linux; no `bru` | `## Entry 3: Bruno`; pins re-read live 2026-11-21; `desktop` key now exists (reconciliation R7) |
| ONB-14 | gh-stack install/detect/update/remove without login prompts (amended by D-10, D-11) | `## Entry 4: gh-stack`; the new `install` argv param; elevation test must cover it |
| ONB-15 | Playwright MCP pinned `bunx @playwright/mcp@0.0.85` per present host, existing entry kept, Flatpak Chrome env, consent before `~/.claude/settings.json` write | `## Entry 5: Playwright MCP`, `## Per-host MCP files`; reconciliation R10-R13 (hook undo cannot fire for a bun tool; ledger is the file-revert) |
</phase_requirements>

## Project Constraints (from CLAUDE.md / AGENTS.md / .claude/*.md)

- English only, everywhere. [VERIFIED: AGENTS.md]
- uv owns the environment; never pip/poetry/conda. [VERIFIED: AGENTS.md]
- Never bypass a gate; no `skip`/`xfail` to go green; never lower the coverage floor; never `--no-verify`. [VERIFIED: AGENTS.md, .claude/testing.md]
- Plans are `type: execute`, test-first inside one green commit; keep the RED output in the SUMMARY. [VERIFIED: .claude/testing.md "Test-first inside one green commit"]
- While working run only targeted tests (`uv run pytest <files> --no-cov -q`); after a plan, `make validate` and `make test` once each. Never chain them per commit. [VERIFIED: AGENTS.md]
- `make test` = `pytest -n auto` capped at ~40% threads; every test xdist-safe (`tmp_path`, `monkeypatch`, no fixed paths/ports). [VERIFIED: .claude/testing.md]
- Never mutate the developer's host: no `make run/fix/uninstall/doctor/dev-setup`, no real installs; real installs only in disposable containers via `scripts/detect-container-runtime.sh`, removed afterwards. [VERIFIED: AGENTS.md]
- Zero sudo: no code path runs `sudo`, `pkexec`, `doas`; anything needing root is handed off as the exact command. [VERIFIED: AGENTS.md]
- The registry selects actions by NAME from closed, code-owned sets, never a command string. [VERIFIED: .claude/architecture.md:337-342 "the registry can only select a hook NAME from a closed, code-owned set in every one of these mechanisms — never a literal command string."]
- No install-time question (TUNE-04); a new consent needs its own reviewed path. [VERIFIED: .claude/architecture.md:771-775 "No post-install action asks a question at install time: the consent machinery was retired in Phase 25 ... a future action that needs consent must add a reviewed path of its own."]
- Temporary files: own `$TMPDIR/<run-id>`, trap cleanup on every exit. [VERIFIED: user CLAUDE.md]
- CI runs Python 3.15, local venv 3.12.12 (probed). Stdlib areas this phase touches that may differ: `tomllib` (stable), `pathlib.Path.is_relative_to`/`resolve(strict=True)` (stable), `subprocess` (stable), `json` (stable). No 3.13+-only API is needed; avoid `pathlib.Path.copy`/`move` (3.14+) so 3.12 local runs stay green. [ASSUMED for 3.15 behavior; probed local 3.12.12]

## Summary

All five entries fit existing method kinds, but three of them need small, validated extensions that do not exist yet, and the code that phases 27 to 31 landed changes several CONTEXT premises. `tarball` already takes `raw`, `note` and `desktop` (phase 30), so Bruno needs no model change, and its pins still match GitHub's digests on 2026-11-21. The `script` kind still has no fixed-argv install and no closed hand-off name, so gh-stack and Xcode CLT each need one new validated param. `_RANK` still sorts brew (5) before script (10), so AWS CLI needs a narrow preference.

The biggest planning risk is Playwright MCP (D-14). The existing postinstall-hook undo is argv-based and runs only through a receipt-proven executable named `tool.cmd`. A `bun` receipt carries no artifacts, so for a bun tool that undo can never fire (`installer/uninstall.py:390-411`, `installer/receipts.py:506-509`). The "file-revert undo" D-14 asks for therefore has to be the config-write ledger in `installer/agent_settings.py`: insert-if-absent, `set_by_you` when the user holds the key, revert only what still holds our value. That needs a new MCP-file map per agent, because MCP servers do not live in the settings files the ledger knows today. Claude keeps user-scope servers in `~/.claude.json`, Cursor in `~/.cursor/mcp.json`, Copilot in `~/.copilot/mcp-config.json`, OpenCode v2 under `mcp.servers`, and Codex in `[mcp_servers.<name>]` tables. Pi has no ledger at all.

The second risk is cross-entry fallout. A script method with no `url` reaches `executors._script` on two unguarded paths, the update path and a root-run `prefix_writable`. A new install argv key must join the elevation test. The generic `make e2e` pass now installs every new entry (Bruno is 175 MB, and the Playwright hook would write into the container's agent hosts), and the usage text shifts the classified PATH lines.

**Primary recommendation:** plan five entry plans plus one shared "script-kind extensions + preference" plan and one "MCP writer" plan. Build the MCP writer on `agent_settings._apply_once`/`_revert_once` with a per-agent MCP-file map, and undo it from `app._after_removal` (not from `_hook_undo`). Make the Xcode handoff unconditional and refuse its update. Add the new install argv key to every elevation check.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Entry declarations, pins, `# Verified` | Registry data (`installer/registry.toml`) | Model validation (`installer/model.py`) | The catalog is the single source; every new key is refused at load unless validated |
| Xcode hand-off text | Executors closed table (`installer/executors.py` `needs_manual`) | Plan/render (`session._row`, `render.py`) | Display strings live only in a code-owned table; the registry names the entry |
| AWS script-before-brew order | Resolver (`installer/resolve.py`) | Ownership (unchanged; it never reads index 0) | Install preference is the ladder's job; provenance is ownership's |
| gh-stack fixed argv install | Executors (`_script`) | Model validation (token regex, elevation head) | Same seam as `update`/`remove`, runner with stdin closed |
| Bruno AppImage + menu | Download (`installer/download.py`) | `installer/appimage_menu.py` | Existing raw-tarball path (phase 30) |
| Playwright install | Executors `_bun` | Update (`update.py` bun branch refuses an exact pin) | Existing kind |
| MCP server registration | Postinstall hook (`installer/postinstall.py`) | Ledger writer (`installer/agent_settings.py`) and removal sweep (`installer/app.py::_after_removal`) | Hook decides hosts and records them; the ledger owns write and revert |
| Claude settings `env` consent | Plan review (`installer/session.py::build_plan` rows/steps) | Hook (writes only when the step was confirmed) | Consent = a listed, confirmed plan step (D-15) |
| Container proofs | `scripts/container-e2e-verify.sh` + `tests/e2e_*_driver.py` | Host tests with stubbed `ct` | Pattern of `cmd_ghostty`/`cmd_herdr_app` |

## CONTEXT Reconciliation

Each row: what CONTEXT says, what the code is now (read this session), what the plan should do. Locked decisions are not overridden; conflicts are flagged.

| # | CONTEXT says | Code now | Plan should |
|---|---|---|---|
| R1 | D-01 cites `oh-my-zsh` at `registry.toml:599-624`, `detect_path` on script and brew at `model.py:45-62,104` | oh-my-zsh is at `registry.toml:600-625`; `detect_path` is in `METHOD_PARAMS["script"]` (`model.py:45-62`) and `"brew": frozenset({"formula", "detect_path", "min_os_version", "bin_dir", "smoke_argv"})` (`model.py:108`). An absolute `detect_path` already exists: `detect_path = "/opt/homebrew/bin/bash"` (`registry.toml:665`) | Line refs only; mechanism unchanged. Use an absolute `detect_path` like gnu-bash |
| R2 | D-01: never executed "because `needs_manual` runs first" with a never-writable `writable_prefix` (`executors.py:749-769`) | `needs_manual` is at `executors.py:753-773`; it returns the handoff only `if not isinstance(prefix, str) or writable(prefix): return None` is false, and builds `command = f'{shell} -c "$(curl -fsSL {url})"'` from `require_str(method, "url")` (`executors.py:759-767`). `prefix_writable` answers True for root: a missing prefix's nearest parent `/` passes `os.lstat(existing).st_uid == os.getuid()` when uid 0 (`executors.py:732-750`) | **Conflict-free refinement, flag for review:** keep `writable_prefix` as D-01 says (it feeds `version_status._unwritable_prefixes`, `version_status.py:1115-1122`, and the plan's `state.unwritable`), but make the hand-off branch return whenever the closed name is set, before the writability test, so a root process or a future writable path can never fall through to `_script` with no `url` |
| R3 | D-01: "No receipt is ever written, so Uninstall offers nothing" (`version_status.py:2016-2028`) | `uninstall_group` is at `version_status.py:2022-2034`; a present tool with nothing removable is `UninstallState.MANAGED`, listed with no action. Ownership gives a present script tool with no manager claim `owner="installer"` by elimination: `script_method = next(...)` then `OwnershipCandidate(owner="installer", ..., evidence="vendor install script with no competing manager claim")` (`ownership.py:829-849`) | The row is listed (MANAGED), with no argv; its label is `removal_label` → `"script": "own installer"` (`ownership.py:1362`). Test the MANAGED group and empty argv; decide whether "own installer" is acceptable copy (open question Q3) |
| R4 | D-01 does not mention update | `update_refusal` returns None for an installer-owned script; `_update_installer_owned` then calls `executors.execute(method, runner)` when the method has no `update` (`update.py:502-506`), which reaches `_script` → `require_str(method, "url")` → `ExecutorError` | Add a refusal for a hand-off method in `update_refusal` (status `unsupported`, display text naming Apple's Software Update, no argv); test it. Without it the Update action on a CLT-present Mac reports "failed: missing ... 'url'" |
| R5 | D-03: env values shell-quoted (`executors.py:453-468`) | `_env_prefix` is at `executors.py:457-472`; values are `shlex.quote`d, so `~`/`$HOME` cannot be pinned through `env` | Keep the XDG relocation as a recorded limit. Add `env = { AWS_CLI_INSTALL_SKIP_SIGNATURE_VERIFICATION = "false" }` (see Entry 2): the vendor script skips gpg when that variable is `true` in the inherited environment |
| R6 | D-04: `_RANK` brew 5, script 10; parity test in `tests/test_resolve.py` | Unchanged: `_RANK = {"brew": 5, "cask": 5, "bun": 6, "node": 7, "script": 10, ...}` (`resolve.py:15-31`); `resolve_methods` sorts by `_RANK[m.kind]` (`resolve.py:96-99`). Tests that pin it: `test_rank_order_is_brew_cask_then_bun_then_node` (`tests/test_resolve.py:1008-1018`), `test_without_homebrew_every_tool_keeps_the_pre_phase_order` (`:959-973`), `test_brew_and_cask_keep_declaration_order` (`:982-985`), and `test_ownership_only_kinds_declaration_matches_helper_reach` iterates `resolve._RANK` (`tests/test_ownership.py:1620-1660`) | Implement the preference as a per-method sort key, not a `_RANK` edit, so every pinned test stays valid; see Entry 2 |
| R7 | D-07: "`raw` becomes an allowed key on `tarball`"; D-08: "No desktop entry is written (none exists in `installer/` except cargo_distrobox's `desktop_entry.py`)" | Phase 30 already did it: `"tarball": frozenset({"url", "member", "strip", "raw", "note", "desktop", "bin_name", "archive", "bin_dir", "version", "sha256", "smoke_argv"})` (`model.py:84-99`), validated (`model.py:672-703`), and `installer/appimage_menu.py` places a raw AppImage's menu entry and icon from `desktop` (used by ghostty: `desktop = "com.mitchellh.ghostty"`, `registry.toml:3233`) | **No model change for Bruno.** D-08's "no desktop entry" premise is now false; **flag to owner (D-08 is locked):** Bruno could declare `desktop = "bruno"` if the AppImage carries `bruno.desktop` and `bruno.png` at its AppDir root (likely for electron-builder, ASSUMED; confirm in the container with `--appimage-extract bruno.desktop`). Recommend asking the owner whether to amend D-08 |
| R8 | D-09: `_script` only runs `curl url \| shell` (`executors.py:471-491`); tokens accept `:` and `/` (`model.py:172,477-485`) | `_script` is at `executors.py:475-495`; `_SCRIPT_ARG_RE = re.compile(r"^[A-Za-z0-9=._:/+-]+$")` (`model.py:176`); `_script_token_ok` at `model.py:482-490`; `_elevation_head`/`ELEVATION_COMMANDS = frozenset({"sudo", "pkexec", "doas"})` at `model.py:551-559` | Unchanged premise; new param needed (Entry 4). `https://github.com/github/gh-stack` passes `_SCRIPT_ARG_RE` |
| R9 | D-11: `_recipe_argv` binds the first word to a proven leaf (`uninstall.py:343-373`); update through PATH (`update.py:531-545`) | Both confirmed at those lines | Unchanged |
| R10 | D-14: "existing `present_harnesses`/`register_hooks`/`receipt.hooks`" with "a file-revert undo" | Hook undo is argv-only: `HookPair.unregister: Callable[[str, tuple[str, ...]], tuple[tuple[str, ...], ...]]` (`postinstall.py:543`); `_hook_undo` returns `(), ()` unless `_proven_named(base, tool.id, tool.cmd, ("link", "leaf", "file"))` finds a receipt artifact (`uninstall.py:390-411`); `receipts.record` docstring: "Manager kinds get none" (artifacts) (`receipts.py:506-509`) | **Conflict with D-14's mechanism, not its intent.** For a `bun` tool the hook's undo can never run. Plan the file-revert as the ledger (`agent_settings` `_apply_once`/`_revert_once`, `agent_settings.py:935-1002, 1155-1229`) and call the revert from `app._after_removal` for this tool (today it reverts only `tool.id in receipts.CONFIG_AGENTS`, `app.py:628-631`). Keep `receipt.hooks` for "which hosts were registered" (drift fact and RECONFIGURE need it) |
| R11 | D-14: `agent_settings` "returns `set_by_you`, keeps user keys and refuses on a write race" (`agent_settings.py:36,610-621`) | Confirmed: `CHANGED_WHILE_WRITING: Final = "changed while being written"` (`:36`); `KeyKind = Literal["wrote", "set_by_you", "already", "replaced_default", "replaced_ours", "removed", "kept_changed"]` (`:610-612`). But the writer is bound to settings files: `settings_file()` uses the adapter path (`:766-774`), `_agent_files()` refuses any other file on revert with `NOT_A_SETTINGS_FILE` (`:1232-1253`), formats exist only for `AGENT_FORMATS = {"claude": "json", "codex": "toml", "opencode": "jsonc", "cursor-agent": "json", "vscode": "jsonc", "copilot": "jsonc", "herdr": "toml"}` (`:613-621`), and ledgers exist only for `CONFIG_AGENTS = ("claude", "codex", "opencode", "cursor-agent", "vscode", "copilot", "herdr")` (`receipts.py:292`) | Add an MCP-file map keyed by (agent, setting), accept those files in `_agent_files` for that setting only, and add a `DYNAMIC_KEYS`-style allow-listed key path per agent. **Pi has no ledger**: exclude pi with a recorded gap, or add a pi ledger (scope growth). See Q1 |
| R12 | D-14: hosts from `present_harnesses` | Harness ids differ from ledger ids: harness `cursor` vs ledger `cursor-agent` (`HOST_CATALOG_IDS`, `postinstall.py:40-47`). `present_harnesses` also reports antigravity, gemini-cli, kilo and others (`postinstall.py:58-81`) | The hook's `targets` map must list only hosts with a writer (claude, codex, opencode, cursor, copilot) and map harness→ledger id |
| R13 | D-14: drift and kept entries | The drift fact marks every present target not in `receipt.hooks` as `≈ config` unless `pair.settled` reports it, and `settled` runs only `if pending and pair.settled is not None and binary is not None` (`version_status.py:917-921`) | A kept user `playwright` entry (not recorded) would read `≈ not registered` forever. Give the HookPair a `settled` that reads each host file (ignores `binary`), and make sure `binary` is non-None for a bun tool, or the row never settles |
| R14 | D-15: "a separate step listed in the plan confirmation" | `PlanRow.steps: tuple[ConfigStep, ...]` (`session.py:177`), `ConfigStepKind = Literal["terminal_sync", "pnpm_group_install", "hook_register", "zshenv_shell", "install_tuning"]` (`model.py:308-314`); `_run_step` refuses an unknown kind (`session.py:363-380`); steps are built for present rows (`version_status.py:776, 934`) | A new reviewed path is needed (consent machinery is gone). Cheapest shape: a new `ConfigStepKind` for the Claude env write, attached to the playwright row when claude is present and its official plugin is enabled, shown in review; the executor runs it only as part of the confirmed plan. Planner decides (Q2) |
| R15 | D-16: OS-gated row is a dimmed "– unavailable" (`catalog_tui.py:208-216`, `resolve.py:158-188`) | `_HEALTH_WORD` includes `Health.UNAVAILABLE: "unavailable"` and the legend `[dim]– unavailable[/]` (`catalog_tui.py:200-216`); `unavailable_reason` is at `resolve.py:158-216` | Line refs fine |
| R16 | D-13: verify-registry checks only `CHECKABLE_KINDS` (`verify_registry.py:344-395`) | `CHECKABLE_KINDS = ("github_release", "tarball", "app")` (`verify_registry.py:90`); `_collect_targets` at `:344` | Unchanged; Bruno's tarballs join verify-registry automatically, the npm pin does not |
| R17 | D-12 cites pi/mmdc at `registry.toml:2805-2810,3290-3297`; bun executor `executors.py:633-653` | mmdc at `registry.toml:2795`, pi at `:3403-3429`; `_bun` at `executors.py:637-665` | Line refs only |
| R18 | (not in CONTEXT) update of an exact bun pin | `update_refusal`: when bun's global manifest holds an exact version, `status="unsupported"`, detail `"pinned to {listed.range} in bun's global manifest; bun update keeps that version — change the pin with `bun add -g {ownership.package}@<range>`"` (`update.py:343-355`) | With `versions = { "@playwright/mcp" = "0.0.85" }` the Update action refuses by design (ASSUMED that `bun add -g pkg@0.0.85` records the exact range; check in the bun container). The pin moves only by editing the registry. Record in `# Verified` |

## Standard Stack

No Python dependency is added. The "stack" is the registry pins and the in-repo mechanisms.

### Pins (re-read live 2026-11-21)

| Artifact | Pin | Evidence |
|---|---|---|
| Bruno Linux AppImage x86_64 | `4.3.0`, sha256 `3c386b1007f66d875c34a2a502063fbad65c66e37409a316ebe518788b1e80bb` | [VERIFIED: `gh api repos/usebruno/bruno/releases/latest`: tag v4.3.0, published 2026-10-22, asset `bruno_4.3.0_x86_64_linux.AppImage`, digest as quoted] |
| Bruno Linux AppImage arm64 | `4.3.0`, sha256 `6048c3aeb76607c71df7558deea83cfef9d33cf24a63da9e7c5268ab19d13469` | [VERIFIED: same call, asset `bruno_4.3.0_arm64_linux.AppImage`] |
| Bruno cask | `bruno` 4.3.0, `app = "Bruno.app"`, `depends_on {}`, `auto_updates true`, zap includes `rmdir ~/Documents/bruno` | [VERIFIED: formulae.brew.sh/api/cask/bruno.json] |
| Bruno on Arch | no official package (AUR only) | [VERIFIED: archlinux.org packages search JSON returned no results] → tarball methods cover arch too |
| AWS CLI brew formula | `awscli` stable 2.42.1, bottles for arm64/x86_64 Linux and macOS | [VERIFIED: formulae.brew.sh/api/formula/awscli.json] (SPEC's 2.41.1 is stale; brew is unpinned, no edit needed) |
| AWS install.sh | `https://awscli.amazonaws.com/v2/install.sh`, 764 lines | [VERIFIED: fetched and read 2026-11-21; facts in Entry 2] |
| gh-stack | `github/gh-stack` v0.3.0 (2026-10-26), not archived, precompiled binary assets `linux-amd64`, `linux-arm64`, `darwin-amd64`, `darwin-arm64`, ... | [VERIFIED: `gh api repos/github/gh-stack` and `/releases/latest`] → a binary extension, so gh writes `manifest.yml` (consistent with D-10's live test) and needs no git |
| @playwright/mcp | `0.0.85`: `engines {'node': '>=18'}`, `bin {'playwright-mcp': 'cli.js'}`, published 2026-11-09T18:31:27Z, no install/postinstall script; `0.0.86`: `engines {'node': '>=20'}`, latest | [VERIFIED: registry.npmjs.org/@playwright%2fmcp] |

### Mechanisms used (in-repo)

| Mechanism | File | Used by |
|---|---|---|
| `script` kind + `detect_path` + `writable_prefix` + `needs_manual` | `model.py:45-62`, `executors.py:753-773` | Xcode CLT, AWS, gh-stack |
| raw `tarball` + `desktop` + `appimage_menu` | `model.py:84-99, 672-703`, `appimage_menu.py` | Bruno Linux |
| `cask` with `--appdir` | `executors.py:703-708` | Bruno macOS |
| `bun` with `versions`, `min_node` | `model.py:704-773`, `executors.py:637-665` | Playwright |
| postinstall hook table | `postinstall.py:555-570` | Playwright registration |
| config-write ledger | `agent_settings.py`, `receipts.py:288-330` | Playwright MCP entries |

## Package Legitimacy Audit

The phase adds no project dependency. It registers one npm package that the installer installs on user machines.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `@playwright/mcp` (pinned 0.0.85) | npm | package years old; 0.0.85 published 2026-11-09; 0.0.86 on 2026-11-18 | 11,283,200/wk | github.com/microsoft/playwright-mcp | [SUS] reason `too-new` (the seam judged the latest version, 3 days old) | Flagged: planner adds a `checkpoint:human-verify` before the entry lands (the owner already chose this pin in D-13; the checkpoint confirms 0.0.85 is still the pin) |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** `@playwright/mcp` (verdict driven by the latest release's age; no postinstall, Microsoft repo)

## Architecture Patterns

### System Architecture Diagram

```
registry.toml entry ──load_tools (model.py: METHOD_PARAMS + validators)──► Tool/Method
        │
        ▼
resolve_methods (resolve.py: _applies + sort key) ──► ordered methods
        │
        ├─► session.build_plan ──► PlanRow (INSTALL | MANUAL+manual_command | steps)
        │        │                         ▲
        │        │                         └─ needs_manual(handoff name → closed table)  [Xcode]
        │        ▼
        │   review confirmation (consent = listed step)  [Claude env write, D-15]
        │        ▼
        └─► engine.install_tool
                 ├─ is_installed (which | detect_path | bin_dir | artifacts | app bundle)
                 ├─ needs_manual → MANUAL_REQUIRED (no run)                 [Xcode]
                 ├─ executors._script: curl→file→shell  | fixed argv (new)  [AWS | gh-stack]
                 ├─ download (raw tarball, sha256) → appimage_menu          [Bruno Linux]
                 ├─ executors._cask (--appdir ~/Applications)               [Bruno macOS]
                 ├─ executors._bun (bun add -g pkg@pin)                     [Playwright]
                 ├─ smoke (manager: <cmd> --version; download: smoke_argv)
                 ├─ receipts.record (paths created, or none for managers)
                 └─ register_hooks → MCP writer (agent_settings ledger, per host file) [Playwright]
                                         │
uninstall: removal_plan (L1 manager | L2 receipt paths | L3 recipe)
           └─ app._after_removal → ledger revert for the MCP setting (new branch)
update:    ownership → update_refusal → brew/cask/bun/installer branches
```

### Recommended file touch map

```
installer/model.py          # script: new `install` argv + `handoff` name keys and validators; HANDOFF_NAMES; preference key
installer/executors.py      # _script fixed-argv branch; needs_manual handoff table
installer/resolve.py        # sort key honoring the preference
installer/update.py         # refuse update of a handoff method
installer/postinstall.py    # new HookPair "playwright-mcp-register" (targets, register, settled; no argv unregister)
installer/agent_settings.py # MCP file map, per-agent server key, revert acceptance
installer/app.py            # _after_removal: revert the MCP setting for this tool
installer/session.py        # (if Q2 = step) the Claude env step kind and branch
installer/registry.toml     # five entries with # Verified
scripts/container-e2e-verify.sh + tests/e2e_*_driver.py + tests/test_container_e2e_*.py  # aws-cli, playwright-mcp targets
```

### Pattern 1: Closed hand-off name (Xcode CLT)
**What:** a `script` param naming an entry of a code-owned display table; `model.py` keeps a duplicated name set (the `SMOKE_CHECK_NAMES`/`POSTINSTALL_HOOK_NAMES` layering precedent: "Duplicated (not imported) from installer/postinstall.py::POSTINSTALL_HOOKS's keys", `model.py:16-23`).
```python
# installer/model.py (sketch; names are Claude's discretion)
HANDOFF_NAMES: frozenset[str] = frozenset({"xcode-clt"})
# installer/executors.py (sketch) - display strings only, never executed
_HANDOFF_COMMANDS: dict[str, tuple[str, str]] = {
    "xcode-clt": ("Apple's installer needs an administrator (never run here)", "xcode-select --install"),
}
def needs_manual(method, *, writable):
    if method.kind == "script":
        name = method.params.get("handoff")
        if isinstance(name, str):                      # unconditional (R2)
            why, command = _HANDOFF_COMMANDS[name]
            return ManualHandoff(f"{why}; you run: `{command}`", command)
        ...existing writable_prefix branch...
```
The `ManualHandoff(f"{why}; you run: `{command}`", command)` shape is the existing one (`executors.py:767,773`). Load validation: `handoff` must be in `HANDOFF_NAMES`; a script must declare exactly one of `url`, `install`, `handoff`; `handoff` refuses `url`, `shell`, `env`, `args`, `install`, `update`, `remove`, `paths`.

### Pattern 2: Fixed-argv install on `script` (gh-stack)
```python
# installer/executors.py::_script (sketch)
install = method.params.get("install")
if isinstance(install, list):
    runner([str(token) for token in install])   # no shell; run.py passes stdin=subprocess.DEVNULL (run.py:117)
    return
```
Validation in `load_tools` mirrors `remove`/`update` (`model.py:802-811`): `_is_argv(..., _script_token_ok)` and `_elevation_head(...) is None`; refuse `install` together with `url`/`shell`/`env`/`args`. Add `"install"` to the keys loop and to `tests/test_executors.py::test_no_registry_argv_starts_with_an_elevation_command`, which iterates only `for key in ("remove", "update")` today (`tests/test_executors.py:151-161`).

### Pattern 3: Narrow install preference (AWS CLI)
A per-method boolean on `script` (name is discretion, for example `prefer = true`), validated as a bool, allowed only on `script`, and refused unless the same tool declares a `brew` method (so it can only ever express "script before brew"):
```python
# installer/resolve.py (sketch)
def _sort_key(method: Method) -> int:
    # The preference lifts a script above brew/cask/bun/node but never above another rank-equal kind.
    return 0 if method.params.get("prefer") is True else _RANK[method.kind]
def resolve_methods(tool, platform):
    applicable = [m for m in tool.methods if _applies(m, platform)]
    return sorted(applicable, key=_sort_key)
```
`_RANK` stays untouched, so the four rank tests remain true. Add a test that AWS resolves `["script", "brew"]` on macOS, fedora-immutable and fedora-mutable fixtures, and `["script"]` on debian (has_brew=False). `test_without_homebrew_every_tool_keeps_the_pre_phase_order` stays green because the pre-phase ladder already had script (10) before brew (40) (`tests/test_resolve.py:941-956`).

### Pattern 4: MCP server via the ledger (Playwright)
`apply_value` takes only `DYNAMIC_KEYS` pairs and writes to `settings_file()` (`agent_settings.py:1055-1078, 766-774`). Add a sibling that targets the MCP file:
```python
# installer/agent_settings.py (sketch)
MCP_FILES: Final[dict[str, Callable[[Path, Mapping[str, str]], Path]]] = {...}   # agent -> path
MCP_SERVER_KEY: Final[dict[str, KeyPath]] = {
    "claude": ("mcpServers", "playwright"),
    "cursor-agent": ("mcpServers", "playwright"),
    "copilot": ("mcpServers", "playwright"),
    "opencode": ("mcp", "servers", "playwright"),          # OpenCode v2 schema
    # codex: written as its own [mcp_servers.playwright] table, see Pitfall 6
}
def apply_mcp_server(agent, value, *, home, platform_os, environ) -> FileResult:
    path = MCP_FILES[agent](home, environ or {})
    return _retry(lambda: _apply_once(agent, "mcp-playwright", path, MCP_FORMATS[agent],
                                      (SettingKey(MCP_SERVER_KEY[agent], value),), home=home, skip_recorded=False))
```
`_apply_pass` already gives the semantics D-14 wants: a missing key is `wrote`, an equal one `already`, any other value `set_by_you` and kept (`agent_settings.py:863-895`). The revert path must accept the MCP file for this setting (today `_agent_files` returns only the adapter path, `:1232-1239`) and allow-list the key path the way `DYNAMIC_KEYS` does in `_revert_once` (`:1169-1177`), because "The ledger is user-writable JSON".

### Anti-Patterns to Avoid
- **Editing `_RANK` for AWS:** breaks four pinned ladder tests and reorders every brew+script tool (uv, bun, pnpm, fnm).
- **An argv `unregister` for the Playwright hook:** it would never run for a bun tool (R10), and a vendor CLI route was weighed and declined in D-14.
- **Writing `~/.claude/settings.json` from the hook unconditionally:** that file needs the D-15 consent step. `~/.claude.json` is the MCP file, and it is a different file (Q4).
- **A `bru` or `@usebruno/cli` method:** out of scope (SPEC).
- **A Bruno `smoke_argv` with `--appimage-*`:** answers before Electron runs (skill Common Mistakes).

## Entry 1: Xcode CLT (ONB-11)

```toml
# Verified 2026-11-2x: detect-only. Homebrew's own installer probes /Library/Developer/CommandLineTools/usr/bin/git;
# xcode-select is always present, so cmd never resolves. Xcode.app without the CLT reads missing (D-02).
# The hand-off command is code-owned (handoff = "xcode-clt"); nothing runs it and no receipt is written.
[[tool]]
id = "xcode-clt"            # discretion
name = "Xcode Command Line Tools"
category = "dev"            # discretion (pkg-mgr is the alternative)
cmd = "xcode-clt"           # a probe name nothing creates (gnu-bash precedent)
priority = "P1"
audience = "both"
tier = "system"
verified = 2026-11-2x
[[tool.method]]
kind = "script"
os = ["macos"]
detect_path = "/Library/Developer/CommandLineTools/usr/bin/git"
writable_prefix = "/Library/Developer/CommandLineTools"
handoff = "xcode-clt"
```
- Detect path: Homebrew's install.sh tests `! [[ -e "/Library/Developer/CommandLineTools/usr/bin/git" ]]` (install.sh:452). [VERIFIED: raw.githubusercontent.com/Homebrew/install/HEAD/install.sh, fetched 2026-11-21]
- `_WRITABLE_PREFIX_RE = re.compile(r"^/[A-Za-z0-9._/-]+$")` (`model.py:178`) accepts `/Library/Developer/CommandLineTools`. [VERIFIED: model.py:178]
- The test `test_every_script_method_declares_a_location_or_explains_no_bin_dir` accepts a method body containing `detect_path` (`tests/test_registry.py:1594-1624`). [VERIFIED]
- `SCRIPT_LIFECYCLE_DATA` must gain the `("xcode-clt", ("macos",), ())` stanza with `paths/remove/update` all `None` (`tests/test_registry.py:2987-3036` pins equality of the stanza set). [VERIFIED]
- Linux shows it unavailable ("macos only"): `MACOS_ONLY = {"gnu-bash", "iterm2"}` (`tests/test_registry.py:800`) gains the id. [VERIFIED]
- Grep test (D-01): AST walk over `installer/**/*.py` and `setup.py` for a list/tuple literal whose first element is `"xcode-select"` or `"softwareupdate"` (extend `_ELEVATION_WORDS`-style test at `tests/test_executors.py:164-174`), plus a text check that the string `xcode-select --install` occurs in `installer/` only inside the hand-off table.
- Ownership/update: see R3, R4.

## Entry 2: AWS CLI v2 (ONB-12)

```toml
[[tool]]
id = "aws-cli"              # discretion; cmd must be "aws"
name = "AWS CLI"
category = "dev"
cmd = "aws"
tier = "user"
requires = ["unzip"]        # Linux needs unzip (install.sh check_dependencies)
[[tool.method]]
kind = "script"
url = "https://awscli.amazonaws.com/v2/install.sh"
shell = "bash"
bin_dir = "~/.local/bin"
env = { AWS_CLI_INSTALL_SKIP_SIGNATURE_VERIFICATION = "false" }
paths = ["~/.local/share/aws-cli/", "~/.local/bin/aws", "~/.local/bin/aws_completer"]
update = ["aws", "update"]
prefer = true               # name is discretion (Pattern 3)
[[tool.method]]
kind = "brew"
formula = "awscli"
```
Facts read from the vendor script on 2026-11-21 [VERIFIED: install.sh fetched from awscli.amazonaws.com and read; scratch dir removed]:
- Header: "Defaults to a user-local install under XDG paths. Use --system for the traditional /usr/local layout (requires root)." (lines 5-6). The default user-local paths are `INSTALL_DIR="$data_home/aws-cli"`, `BIN_DIR="$bin_home"` with `data_home="${XDG_DATA_HOME:-$HOME/.local/share}"`, `bin_home="${XDG_BIN_HOME:-$HOME/.local/bin}"` (lines 346-357). macOS uses the same `INSTALL_DIR`.
- gpg: `error 1 "gpg not found; cannot verify the installer signature. ..."` (line 465); temporary keyring `gpghome="$TEMP_DIR/gpghome"     # isolated keyring; never touches user's ~/.gnupg` (line 471); key comment `# Expires 2027-07-01.` (line 27).
- **Skip switch:** `AWS_CLI_INSTALL_SKIP_SIGNATURE_VERIFICATION` "Set to "true" (case-insensitive) to skip signature verification" (help text, lines 162-170); `verify_installer` returns early when skip is set (lines 513-520). An inherited `true` would silently drop gpg, so the entry pins it to `false` (defense in depth, like `HOMEBREW_NO_SUDO`).
- Same version: `info "AWS CLI $TARGET_VERSION is already installed ...; nothing to do."` then `exit 0`; older target: `error 2 "AWS CLI $PRE_INSTALL_VERSION is already installed ..."` (lines 581-590).
- Linux deps: `required+=(unzip)`; macOS: `required+=(installer pkgutil)` (lines 268-271). glibc only; musl exits 1 (lines 287-300).
- macOS: `installer -pkg "$INSTALLER_PATH" -target CurrentUserHomeDirectory -applyChoiceChangesXML "$choices"` then `ln -sf` into `BIN_DIR` (lines 662-669). Works without admin rights only if the pkg allows a user-domain install: ASSUMED, Mac UAT.
- The script writes `install.json` inside the install tree (`$INSTALL_DIR/v2/current/dist/awscli/data/install.json` on Linux), so it sits under the declared `~/.local/share/aws-cli/` tree (lines 700-707).
- `aws update` exists since 2.36.0 and reuses the current installation path; supported only for official-installer/script installs. [CITED: aws.amazon.com/blogs/developer/installing-and-updating-the-aws-cli-with-single-line-commands/]
- `update = ["aws", "update"]`: `_declared_leaf` binds `aws` to the receipt leaf `~/.local/bin/aws` (a path artifact named `aws`), so the installer's copy runs, never a PATH copy (`update.py:531-545`). [VERIFIED]
- Fallback: when the script exits 1 (gpg missing), `engine.install_tool` appends the `CommandError` and tries the next method (`engine.py:322-323`), which is brew where `has_brew`. On debian without brew the row is FAILED with the script's message. [VERIFIED: engine.py:241-323]
- `config_paths`: none; `~/.aws` must never appear (credentials). `_config_path_flaw` would accept `~/.aws/...` (two levels), so the protection is the absence of the key plus a test asserting `tools["aws-cli"].config_paths == ()`.

## Entry 3: Bruno (ONB-13)

```toml
[[tool.method]]
kind = "tarball"
os = ["debian", "fedora", "arch"]   # Arch has no official package (AUR only)
arch = ["amd64"]
url = "https://github.com/usebruno/bruno/releases/download/v{ver}/bruno_{ver}_x86_64_linux.AppImage"
version = "4.3.0"
sha256 = "3c386b1007f66d875c34a2a502063fbad65c66e37409a316ebe518788b1e80bb"
member = "bruno"
raw = true
# desktop = "bruno"   # only if the owner amends D-08 (R7) and the container shows bruno.desktop/bruno.png at the AppDir root
[[tool.method]]
kind = "tarball"
os = ["debian", "fedora", "arch"]
arch = ["arm64"]
url = "https://github.com/usebruno/bruno/releases/download/v{ver}/bruno_{ver}_arm64_linux.AppImage"
version = "4.3.0"
sha256 = "6048c3aeb76607c71df7558deea83cfef9d33cf24a63da9e7c5268ab19d13469"
member = "bruno"
raw = true
[[tool.method]]
kind = "cask"
os = ["macos"]
cask = "bruno"
app = "Bruno.app"
```
- Ghostty is the exact precedent for per-arch raw pinned tarballs (`registry.toml:3224-3245`). [VERIFIED]
- Bruno's builder config: `appId: 'com.usebruno.app'`, package `"name": "bruno"`, linux targets AppImage x64/arm64, `desktop: { MimeType: 'x-scheme-handler/bruno;' }`, `electron-builder: ^24.13.3`, `electron: ~37.6.1`. [VERIFIED: gh api contents of packages/bruno-electron/electron-builder-config.js and package.json at v4.3.0]
- FUSE: electron-builder 24.x AppImages use the classic runtime that needs libfuse2; without it they print a FUSE error and exit. ASSUMED (container finding, D-08). Bazzite ships fuse 2.9.9 (ghostty `# Verified`, `registry.toml:3194`). A Fedora container needs `fuse-libs` or `APPIMAGE_EXTRACT_AND_RUN=1` to run it.
- `smoke_binary` strips `DISPLAY`/`WAYLAND_DISPLAY` and treats any exit other than 126/127 or a loader-error line as "ran" (`executors.py:86-123`). An Electron app with no display exits non-zero, so a plain `--version` smoke passes even if Bruno ignores `--version`. A missing-libfuse failure does not match `_LOADER_ERROR` (`GLIBC_|error while loading shared libraries|Exec format error|cannot execute binary file|Library not loaded`, `executors.py:30-33`) unless it exits 127. Confirm the exit code in the container before choosing `smoke_argv`.
- Electron sandbox: an AppImage cannot keep a setuid `chrome-sandbox`; on hosts that restrict user namespaces Electron needs `--no-sandbox`. ASSUMED; container finding.
- `config_paths` (recommended): `["~/.config/bruno", "~/Library/Application Support/bruno"]` (the cask zap lists `~/Library/Application Support/bruno`; the Linux name is ASSUMED from the Electron app name). Never `~/Documents/bruno` (collections).
- verify-registry covers both tarballs (`CHECKABLE_KINDS`), as it does for ghostty.

## Entry 4: gh-stack (ONB-14)

```toml
[[tool]]
id = "gh-stack"
category = "git"
cmd = "gh-stack"            # not on PATH (the extension runs as `gh stack`)
tier = "user"
requires = ["gh"]
[[tool.method]]
kind = "script"
install = ["gh", "extension", "install", "https://github.com/github/gh-stack"]
detect_path = "~/.local/share/gh/extensions/gh-stack/manifest.yml"
paths = ["~/.local/share/gh/extensions/gh-stack/"]
update = ["gh", "extension", "upgrade", "stack"]
```
- `_script_paths_refusal` accepts a trailing `/` (`rest.removesuffix("/")`, `model.py:584`); herdr-app is the precedent for a tree path (`registry.toml:3313`). [VERIFIED]
- `test_no_declared_path_is_or_contains_a_harness_marker` passes: no marker under `.local/share/gh` (`tests/test_registry.py:3013-3025`, `HARNESS_MARKER_DIRS`, `model.py:157-175`). [VERIFIED]
- Removal: receipt type `script` with a proven tree → `level = "recipe"` label but empty argv; L2 deletes the proven tree (`uninstall.py:426-435`). [VERIFIED]
- The receipt records the tree only if this install created it (not in `preexisting`) (`receipts.py:503-506`), so a gh-stack the user installed earlier is never claimed. [VERIFIED]
- Unauthenticated `gh extension install` downloads release assets through the unauthenticated API (60 requests/hour). ASSUMED; low risk.
- macOS data dir: gh uses `~/.local/share/gh` on macOS too (D-10 live test was Linux). ASSUMED; Mac UAT line. `GH_DATA_DIR` is not documented on `gh help environment` [VERIFIED: cli.github.com/manual/gh_help_environment lists GH_PROMPT_DISABLED, GH_NO_UPDATE_NOTIFIER, GH_NO_EXTENSION_UPDATE_NOTIFIER and no GH_DATA_DIR].

## Entry 5: Playwright MCP (ONB-15)

```toml
[[tool]]
id = "playwright-mcp"
category = "ai"
cmd = "playwright-mcp"      # the package's bin: {'playwright-mcp': 'cli.js'}
tier = "ai"
audience = "ai"
requires = ["bun"]
postinstall = "playwright-mcp-register"   # new POSTINSTALL_HOOK_NAMES member
[[tool.method]]
kind = "bun"
npm_pkg = "@playwright/mcp"
versions = { "@playwright/mcp" = "0.0.85" }
min_node = "18"
```
- `test_only_codegraph_tealdeer_and_herdr_declare_a_postinstall_hook` must gain the id (`tests/test_registry.py:2243-2251`); `POSTINSTALL_HOOK_NAMES = frozenset({"codegraph-mcp-register", "herdr-integration", "tealdeer-cache"})` (`model.py:21-23`) gains the name; the postinstall test that keeps both sets equal follows. [VERIFIED]
- `test_shipped_bun_tools_require_bun` passes with `requires = ["bun"]` (`tests/test_registry.py:2174-2181`). [VERIFIED]
- Server value written per host (D-12, D-15), example for JSON hosts:
  `{"command": "<bunx>", "args": ["@playwright/mcp@0.0.85"], "env": {"PLAYWRIGHT_MCP_EXECUTABLE_PATH": "/var/lib/flatpak/exports/bin/com.google.Chrome"}}` with `env` only when that file exists.
- `<bunx>`: GUI-launched hosts and cursor-agent (8 env vars) may not have `~/.bun/bin` on PATH; recommend the absolute path of the resolved bun's `bunx` (`resolve_bun()`), test-pinned. ASSUMED that a bare `bunx` fails there; this is discretion ("key spelling per host").
- `bunx` respects a `#!/usr/bin/env node` shebang and runs Node, so `min_node` still matters at run time. ASSUMED (bun docs not fetched this session).
- Env var and default-channel facts: `PLAYWRIGHT_MCP_EXECUTABLE_PATH` maps to `--executable-path`, and the default channel `chrome` resolves to `/opt/google/chrome/chrome`. [CITED: .planning/research/2026-10-13-from-ai-kit/16-playwright-chrome-bazzite.md, tested against 0.0.83]
- The Flatpak wrapper exists on this host: `/var/lib/flatpak/exports/bin/com.google.Chrome`. [VERIFIED: ls]
- Existing entry kept: `_apply_pass` reports `set_by_you` for any non-equal value (R11). For Claude, an enabled official plugin (`enabledPlugins["playwright@claude-plugins-official"]` in `~/.claude/settings.json`, ASSUMED key spelling) counts as existing: write no server, offer only the D-15 env step.

### Per-host MCP files

| Harness → ledger | File | Key / shape | Source |
|---|---|---|---|
| claude → claude | `~/.claude.json` | top-level `mcpServers.<name>` = `{command, args, env}` (no `type` means stdio) | [CITED: code.claude.com/docs/en/mcp: "User-scoped servers are stored in `~/.claude.json`"] |
| cursor → cursor-agent | `~/.cursor/mcp.json` | `mcpServers.<name>` = `{command, args, env}`; forum reports say cursor-agent CLI does not always read the global file | [CITED: cursor.com/docs/mcp via search; MEDIUM] |
| copilot → copilot | `~/.copilot/mcp-config.json` (moves with `COPILOT_HOME`) | `mcpServers.<name>` = `{type: "local", command, args, env, tools: ["*"]}` | [CITED: docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers] |
| opencode → opencode | `opencode.json` / `opencode.jsonc` (same file as settings) | v2: `mcp.servers.<name>` = `{type: "local", command: [exe, ...args], environment: {...}}`; no `enabled` (use `disabled`) | [CITED: opencode.ai/docs/mcp-servers/] |
| codex → codex | `~/.codex/config.toml` (same file as settings) | `[mcp_servers.<name>]` with `command`, `args`, `[mcp_servers.<name>.env]` | [CITED: learn.chatgpt.com/docs/extend/mcp?surface=cli] |
| pi → (no ledger) | `~/.pi/agent/mcp.json` (registry comment) | schema not read | [ASSUMED]; pi is not in `CONFIG_AGENTS` |

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Merge-safe JSON/JSONC/TOML key insert and revert | a new JSON writer per host | `agent_settings._apply_once` / `_revert_once` | comment-preserving JSONC edits, BOM, race retry (`CHANGED_WHILE_WRITING`), created-file and created-dir cleanup, user-writable ledger guards already exist |
| AppImage menu entry | a desktop-file writer | `appimage_menu.install` + `desktop_entry.render` | phase 30 handles kept user files, proven leaves, rollback |
| Pinned download verification | custom sha check | raw `tarball` with `version` + `sha256` | verify-registry and bump tooling already cover it |
| Hand-off display | free text in the registry | closed table in `executors.py` | architecture rule: names, never strings |
| Script-before-brew | a new method kind | one validated per-method key + sort key | `_RANK` stays the pinned ladder |
| Container lifecycle | ad-hoc podman calls | `landing_*` helpers in `scripts/container-e2e-verify.sh` | PID-named boxes, transcripts, teardown traps |

**Key insight:** every risky operation in this phase (config writes, removals, elevation) already has a reviewed seam; the work is wiring new names into those seams and extending their allow-lists, not new machinery.

## Common Pitfalls

### Pitfall 1: A url-less script reaching `_script`
**What goes wrong:** Update (R4) or a root-run `prefix_writable` (R2) sends the Xcode method to `_script`, which raises "missing or empty required param 'url'".
**How to avoid:** unconditional hand-off branch; `update_refusal` for hand-off methods; tests for both.
**Warning signs:** an Update row for xcode-clt that reads "failed".

### Pitfall 2: The new install argv escaping the elevation checks
**What goes wrong:** `tests/test_executors.py:151-161` and `model.py:802-811` check only `remove`/`update`.
**How to avoid:** add the new key to both, with a refusal test (`["sudo", ...]` install argv refused at load).

### Pitfall 3: Hook undo never firing for a bun tool (R10)
**How to avoid:** ledger revert from `_after_removal`; a removal test in a scratch HOME that seeds each host file, installs (fake runner), removes, and diffs bytes (existing user entry byte-identical; our entry gone; created file deleted only when nothing of the user's remains).

### Pitfall 4: Kept entry reads `≈ config` forever (R13)
**How to avoid:** a `settled` callback that reads host files; test the drift fact with a kept entry.

### Pitfall 5: `~/.claude.json` is Claude's live state file
**What goes wrong:** Claude rewrites `~/.claude.json` often; an edit can be lost to a running Claude or race. `write_if_unchanged` catches a change during our write only.
**How to avoid:** document the limit in `# Verified`; the drift fact re-offers registration if the key vanishes; Q4 decides whether the consent step also covers this file.

### Pitfall 6: Codex TOML refusal
**What goes wrong:** inserting key path `("mcp_servers", "playwright")` with an inline table raises `SettingsEditRefused("[mcp_servers] exists but takes no new key here")` when the user only has `[mcp_servers.other]` headers, because `lookup(doc, table)` is not ABSENT and no `[mcp_servers]` header line exists (`agent_settings.py:375-391`).
**How to avoid:** write three keys under a new `[mcp_servers.playwright]` table (`command`, `args`, `env` as an inline table), checking first that `mcp_servers.playwright` is absent as a whole; test with a config that has `[mcp_servers.foo]`.

### Pitfall 7: OpenCode v1 vs v2 schema
v2 nests servers under `mcp.servers`; v1 used `mcp.<name>` with `enabled`. The registry installs v2 (`latest_npm = "@opencode/cli"`, `registry.toml:1597`), but a host may run v1. Detect the shape or write v2 only and record the limit.

### Pitfall 8: The generic `make e2e` pass picks up every new entry
`GENERIC_SKIP_TOOLS=herdr-app` (`scripts/container-e2e-verify.sh:333`), and `tests/test_container_e2e_herdr_app.py:1230-1233` pins that exact line. The new entries join pass1: Bruno downloads 175 MB per run, AWS needs gpg and unzip in the box, and the Playwright hook would write into the container's claude/codex/opencode/copilot configs and must revert cleanly for the residue diff. Decide per entry whether to add it to `GENERIC_SKIP_TOOLS` (its dedicated target proves it) and update the pinned test.

### Pitfall 9: Usage text shifts the classified PATH lines
`CLASSIFIED` in `tests/test_shell_scripts_path.py:511-541` pins `scripts/container-e2e-verify.sh` lines `440`, `563`, `618`, `885`. Every usage line added above them shifts all four (31-07 hit this). Plan the data edit in the same commit as the new target.

### Pitfall 10: Reachability guard
`tests/test_reachability.py::test_every_installer_module_is_reachable_from_an_entry_point` fails on a new `installer/*.py` that no reachable module imports. Wire any new module in the same commit (31-05 hit this).

### Pitfall 11: Files, not pipes, for child output in drivers
An AppImage's FUSE helper keeps a pipe open, so `--version` waited 120 s (30-05). Drivers capture child output through files (`run_version` test, `tests/test_container_e2e_herdr_app.py:378`).

### Pitfall 12: Rootless podman limits
No `/dev/fuse` unless passed (`ghostty_run_args` adds `--device /dev/fuse` only when present, `scripts/container-e2e-verify.sh:3036-3043`); `--security-opt label=disable`. Chromium in a rootless box needs Playwright's default `--no-sandbox` (Playwright's `chromiumSandbox` defaults to false: ASSUMED).

### Pitfall 13: Registry touch list misses (phases 30 and 31 hit each)
See `## Registry touch list`.

## Registry touch list (five new entries)

Read this session in `tests/test_registry.py` and `tests/test_resolve.py`:

| Pin | Where | Change |
|---|---|---|
| Tool count | `assert len(tools) == 89  # Phase 31 adds iTerm2 and herdr-app` (`tests/test_registry.py:1233`) | 94 |
| Tier distribution | `"system": 28, "ai": 9, "user": 52` (`:1285-1289`) | xcode-clt system, aws-cli user, bruno user, gh-stack user, playwright-mcp ai → `system 29, ai 10, user 55` (if tiers as proposed) |
| Audience distribution | `"both": 50, "ai": 8, "human": 31` (`:303-307`) | depends on chosen audiences |
| `_POST_15_3_HUMAN_TOOLS` | `{"alacritty", "copilot", "ghostty", "herdr-app", "iterm2", "neovim"}` (`:278-285`) | add any new `human` entry (Bruno is the candidate) |
| `MACOS_ONLY` | `{"gnu-bash", "iterm2"}` (`:800`) | add `xcode-clt` |
| Stranded-tool test | `test_every_tool_resolves_at_least_one_method_on_each_platform` (`:823-855`) | passes once xcode-clt is in `MACOS_ONLY` |
| `SCRIPT_LIFECYCLE_DATA` + `test_every_script_stanza_has_lifecycle_data_or_a_reason` | `:2987-3036` | three stanzas: xcode-clt, aws-cli, gh-stack |
| Postinstall declarers | `test_only_codegraph_tealdeer_and_herdr_declare_a_postinstall_hook` (`:2243-2251`) | add playwright-mcp |
| `_FIRST_METHOD` (four fixtures) | `tests/test_resolve.py:559-924`; fixtures `macos` (has_brew), `fedora-mutable` (has_brew), `fedora-immutable` (has_brew), `debian` (no brew) (`:549-553`) | macos: xcode-clt `script`, aws-cli `script`, bruno `cask`, gh-stack `script`, playwright-mcp `bun`; fedora-*: xcode-clt `None`, aws-cli `script`, bruno `tarball`, gh-stack `script`, playwright-mcp `bun`; debian: same as fedora |
| Elevation test | `tests/test_executors.py:151-161` | iterate the new install key |
| Owner probes | `OWNER_PROBES = ("brew", "apt", "dnf", "pacman", "rpm-ostree", "pnpm", "sdkman")` (`model.py:146-154`) | none needed (no native method); `test_native_package_manager_rows_declare_their_owner_probes` (`:2415`) unaffected |
| Skill table | rows only for `Category.TERMINAL`/`EDITOR` (`tests/test_tool_onboarding_skill.py:163`) | no new row (D-16) |
| `GENERIC_SKIP_TOOLS` pin | `tests/test_container_e2e_herdr_app.py:1230-1233` | only if entries are skipped (Pitfall 8) |
| `CLASSIFIED` PATH lines | `tests/test_shell_scripts_path.py:511-541` | shift by the usage lines added |
| docs-only LEDGER | `tests/test_docs_only.py:209-293` | only if a new test contains a `.md` literal (for example `CLAUDE.md` in a Playwright test) |
| verify-registry | none to edit; Bruno tarballs checked automatically | run `make verify-registry` read-only once (network) |
| Registry docs | no doc lists catalog entries (`rg` over `docs/`, `README.md`) | none |

## Code Examples

### Hand-off row in the plan (existing shape)
```python
# Source: installer/session.py:736-750
handoff = executors.needs_manual(methods[0], writable=lambda prefix: prefix not in state.unwritable) if methods else None
if handoff is None:
    return make(disposition, reason, can_reinstall=can_reinstall)
return make(Disposition.MANUAL, handoff.reason, manual_command=handoff.command)
```

### Ledger insert semantics (existing)
```python
# Source: installer/agent_settings.py:863-895 (abridged)
elif current is ABSENT:   -> insert, ledger ConfigWrite, KeyResult "wrote"
elif same_value(current, key.value): -> "already"
else:                      -> "set_by_you", key dropped (kept)
```

### Hook table entry (sketch)
```python
# installer/postinstall.py
"playwright-mcp-register": HookPair(
    targets={"claude": "claude", "codex": "codex", "opencode": "opencode",
             "cursor": "cursor-agent", "copilot": "copilot"},
    register=_playwright_register,     # ledger writes; returns registered harness ids
    settled=_playwright_settled,       # hosts whose file already holds a playwright entry
),                                     # no argv unregister: the ledger revert runs in _after_removal
```
Check `unregister_hosts`/`unregister_argvs` tolerate `unregister=None` with `targets` set (they do: `if pair is None or pair.targets is None or pair.unregister is None: return ()`, `postinstall.py:580-582`).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `aws/install --update` with explicit dirs | `aws update` (2.36.0+) and the XDG user-local `install.sh` | 2026 | the entry can declare `update = ["aws", "update"]` |
| OpenCode `mcp.<name>` + `enabled` | `mcp.servers.<name>` + `disabled` (v2) | OpenCode 2 | writer must target v2 |
| Playwright MCP latest on Node 18 | 0.0.86 needs Node 20 | 2026-11-18 | 0.0.85 pin (D-13) |

**Deprecated/outdated:** SPEC's "Homebrew awscli at 2.41.1" (now 2.42.1).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Bruno AppImage carries `bruno.desktop` and `bruno.png` at the AppDir root | Entry 3, R7 | `desktop = "bruno"` would extract nothing; menu step notes a failure (non-fatal) |
| A2 | electron-builder 24.x AppImage needs libfuse2; no extract-and-run fallback | Entry 3 | smoke and container plan differ; Bazzite still works |
| A3 | Electron needs `--no-sandbox` on some hosts | Entry 3 | Bruno fails to start there; not an install failure |
| A4 | `bun add -g @playwright/mcp@0.0.85` records the exact range, so Update refuses | R18 | Update might run `bun update -g` and keep 0.0.85 anyway |
| A5 | A bare `bunx` is not on PATH for GUI-launched hosts / cursor-agent | Entry 5 | absolute path is harmless either way |
| A6 | `bunx` runs a `#!/usr/bin/env node` bin with Node | Entry 5 | `min_node` might be moot |
| A7 | Claude's official plugin key is `enabledPlugins["playwright@claude-plugins-official"]` | Entry 5 | the plugin case is misdetected; a duplicate server may be written |
| A8 | gh data dir is `~/.local/share/gh` on macOS | Entry 4 | macOS detection misses; Mac UAT |
| A9 | The AWS pkg installs to `CurrentUserHomeDirectory` without admin rights | Entry 2 | macOS falls to brew; Mac UAT |
| A10 | Pi's MCP file is `~/.pi/agent/mcp.json` with an unknown schema | Per-host table | pi excluded or a wrong write |
| A11 | Playwright's `chromiumSandbox` default false lets Chromium run in a rootless box | Pitfall 12 | container smoke needs an explicit arg |
| A12 | Unauthenticated `gh extension install` uses the 60/h API budget | Entry 4 | rare install failure under rate limit |
| A13 | Python 3.15 stdlib behavior matches 3.12 for the APIs used | Constraints | CI-only failure |
| A14 | Bruno's Linux config dir is `~/.config/bruno` | Entry 3 | a config path that never exists (harmless) |

## Open Questions (RESOLVED)

Each question below was decided by the plans and the orchestrator decisions (`32-REVIEWS.md` and the plans' decision records, 2026-11-21): Q1 hosts via the settings ledger (pi named only), Q2 and Q4 consent through the existing `hook_register` step with the install-time hand-off, Q3 Xcode hand-off unconditional with update refused, Q5 Bruno keeps D-08 (no desktop entry, backlog 999.32), Q6 `GENERIC_SKIP_TOOLS` grows per container plan.

1. **Q1: Which hosts get the Playwright server?**
   - Known: ledger-backed hosts are claude, codex, opencode, cursor-agent, copilot. Pi has no ledger. Antigravity and the other harnesses have no writer.
   - Recommendation: the five ledger-backed hosts. Record pi and the rest as a gap in `# Verified` and in a backlog item. Adding a pi ledger is scope growth for the owner to choose.
2. **Q2: The shape of the D-15 consent step.**
   - Recommendation: a new `ConfigStepKind` (for example `claude_env`) shown on the playwright row in review when claude is present and the official plugin is enabled. The row writes only inside a confirmed run, and `--yes` counts. A test proves a declined plan writes nothing (the plan never runs) and that a run without the step writes nothing to `~/.claude/settings.json`.
3. **Q3: Xcode Uninstall and owner copy.** A present CLT reads MANAGED, label "own installer". Acceptable, or add a hand-off-specific label ("Apple")?
4. **Q4: Does the SPEC's consent rule cover `~/.claude.json`?** SPEC names only `~/.claude/settings.json`. The MCP entry for Claude lives in `~/.claude.json`, Claude's live state file. Recommend asking the owner. Default: no consent for `~/.claude.json` (an absent-only insert, reverted by the ledger), consent for `settings.json` `env`.
5. **Q5: Bruno `desktop` (D-08 amendment).** Owner decision; the code now supports it.
6. **Q6: `GENERIC_SKIP_TOOLS`.** Skip bruno and playwright-mcp in `make e2e` (dedicated targets prove them), or keep them in pass1?

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| podman | container targets | ✓ | 6.1.3 (`scripts/detect-container-runtime.sh` → `CONTAINER_TOOL=podman`) | — |
| gh | gh-stack live checks, `gh api` pins | ✓ | 2.101.0 | — |
| gpg | AWS host-side reading only | ✓ | 2.4.9 | container installs its own |
| bun | Playwright (container) | ✓ host 1.3.14 | — | container installs bun from the catalog |
| node | `min_node` | ✓ | v24.21.0 | — |
| uv / Python | tests | ✓ | uv 0.11.28, Python 3.12.12 | CI 3.15 |
| Flatpak Chrome wrapper | Bazzite env branch | ✓ | `/var/lib/flatpak/exports/bin/com.google.Chrome` | test with a scratch path |
| macOS host | Xcode, cask, AWS pkg | ✗ | — | UAT lines deferred to the owner's Mac |
| /dev/fuse in rootless box | Bruno FUSE pass | conditional | — | `fuse-libs` + extract-and-run, or UNPROVEN line (ghostty precedent) |

**Missing dependencies with no fallback:** a real Mac (manual UAT only).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-xdist + coverage (config in `pyproject.toml`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]`, `tests/conftest.py` (worker cap) |
| Quick run command | `uv run pytest tests/test_registry.py tests/test_resolve.py tests/test_model.py tests/test_executors.py --no-cov -q` |
| Full suite command | `make test` (after each plan, once), `make validate` once |
| Container commands | `scripts/container-e2e-verify.sh aws-cli` and `... playwright-mcp` (new targets; owner-allowed, disposable) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ONB-11 | handoff name validated; unknown name refused; exactly one of url/install/handoff | unit | `uv run pytest tests/test_model.py -k handoff --no-cov -q` | ❌ Wave 0 (new tests in existing file) |
| ONB-11 | `needs_manual` returns `xcode-select --install` unconditionally (also with `writable=lambda _: True`) | unit | `uv run pytest tests/test_executors.py -k handoff --no-cov -q` | ❌ |
| ONB-11 | missing CLT → MANUAL plan row with the exact command; present (detect_path in tmp) → present | unit | `uv run pytest tests/test_plan.py tests/test_status.py -k xcode --no-cov -q` | ❌ |
| ONB-11 | grep/AST: no runner argv starts with `xcode-select` or `softwareupdate`; string only in the table | unit | `uv run pytest tests/test_executors.py -k "elevation or xcode" --no-cov -q` | partial (elevation tests exist) |
| ONB-11 | update refused; Uninstall group MANAGED, argv empty | unit | `uv run pytest tests/test_update.py tests/test_version_status.py -k xcode --no-cov -q` | ❌ |
| ONB-12 | preference sorts script before brew on brew hosts; validator refuses misuse | unit | `uv run pytest tests/test_resolve.py tests/test_model.py -k prefer --no-cov -q` | ❌ |
| ONB-12 | entry shape: no `--system`, env pin false, paths exclude `~/.aws`, no config_paths | unit | `uv run pytest tests/test_registry.py -k aws --no-cov -q` | ❌ |
| ONB-12 | script failure falls through to brew (fake runner) | unit | `uv run pytest tests/test_engine.py -k aws --no-cov -q` | ❌ |
| ONB-12 | Fedora+gpg install, `aws --version`, second run no-op, uninstall leaves seeded `~/.aws/config` byte-identical; debian-slim without gnupg fails closed with the gpg message | container | `scripts/container-e2e-verify.sh aws-cli` (+ host tests with stubbed `ct`: `uv run pytest tests/test_container_e2e_aws_cli.py --no-cov -q`) | ❌ |
| ONB-13 | entry loads; pins equal live digests (read-only verify-registry); no `bru`; cask uses Bruno.app | unit + network | `uv run pytest tests/test_registry.py -k bruno --no-cov -q`; `make verify-registry` | ❌ |
| ONB-13 | smoke_argv runs Electron (container finding) | container/manual | a step in an existing or new driver | ❌ |
| ONB-14 | install argv validated (elevation head refused); `_script` runs it with no shell | unit | `uv run pytest tests/test_model.py tests/test_executors.py -k install_argv --no-cov -q` | ❌ |
| ONB-14 | detect via manifest file; removal deletes only the proven tree; update argv exact | unit | `uv run pytest tests/test_registry.py tests/test_uninstall.py -k gh_stack --no-cov -q` | ❌ |
| ONB-15 | writer: absent → wrote; existing `playwright` → set_by_you and file byte-identical; only present hosts; env only when wrapper exists; codex `[mcp_servers.foo]` case; opencode v2 shape | unit | `uv run pytest tests/test_agent_settings.py tests/test_postinstall.py -k playwright --no-cov -q` | ❌ |
| ONB-15 | removal reverts our entries via the ledger; user entry kept | unit | `uv run pytest tests/test_app.py -k playwright --no-cov -q` (or the file that covers `_after_removal`) | ❌ |
| ONB-15 | consent: no step → `~/.claude/settings.json` unchanged; confirmed step → env key written | unit | `uv run pytest tests/test_session.py -k claude_env --no-cov -q` | ❌ |
| ONB-15 | headless launch: bunx @playwright/mcp@0.0.85 with distro chromium via `--executable-path`, JSON-RPC initialize + tools/list + navigate to a `data:` URL | container | `scripts/container-e2e-verify.sh playwright-mcp` + host tests | ❌ |
| all | registry counts, sets, first-method tables, lifecycle stanzas | unit | `uv run pytest tests/test_registry.py tests/test_resolve.py --no-cov -q` | ✅ (edit pins) |

### What host tests with a stubbed `ct` can prove
The verb dispatch and refusal outside a container, the usage text naming every verdict, the verdict functions (pure: install, idempotence, byte-identical seed, gpg-missing message, launch probe), the cleanup ordering, and the transcript parser (the `tests/test_container_e2e_herdr_app.py` set: `install_verdict`, `digest_path`, `run_order`, `gate_problem`). They cannot prove that the vendor script really verifies gpg, that the AppImage runs, or that Chromium launches. Those are the container lines, with UNPROVEN as a legitimate verdict where the box lacks a device (ghostty precedent).

### Sampling Rate
- **Per task commit:** the targeted files above (`--no-cov -q`).
- **Per plan:** `make validate` and `make test` once each.
- **Phase gate:** full suite green, both container targets PASS (or UNPROVEN with reason), before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_container_e2e_aws_cli.py` + `tests/e2e_aws_cli_driver.py`: cover ONB-12 container lines
- [ ] `tests/test_container_e2e_playwright_mcp.py` + `tests/e2e_playwright_mcp_driver.py`: cover ONB-15 launch smoke
- [ ] New test cases in existing files (`test_model.py`, `test_executors.py`, `test_resolve.py`, `test_registry.py`, `test_update.py`, `test_version_status.py`, `test_agent_settings.py`, `test_postinstall.py`, the `_after_removal` test file, `test_session.py`/`test_plan.py`)
- No framework install needed.

### Manual-only (real Mac, deferred to the owner; no agent marks them passed)
- Xcode CLT: missing row shows `xcode-select --install`; present row reads present; Update refused; Uninstall lists no action.
- AWS CLI: `install.sh` on macOS installs under `~/.local/share/aws-cli` without admin rights, or falls to brew.
- Bruno: cask places `~/Applications/Bruno.app`; uninstall keeps `~/Documents/bruno`.
- gh-stack: macOS data dir path.
- Playwright: registration in a real Claude/Cursor on macOS.
- Bazzite host: Bruno FUSE mount and menu entry; Playwright with the real Flatpak Chrome (`browser_navigate` reaches a page).

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | no login is ever run (gh unauthenticated paths only) |
| V3 Session Management | no | — |
| V4 Access Control | yes | zero sudo; hand-off for root-owned prefixes; receipt-proven removal only |
| V5 Input Validation | yes | load-time validators in `model.py` (token regex, elevation head, closed names, paths under `~/`) |
| V6 Cryptography | yes | sha256 pins for AppImages; vendor gpg for AWS (kept on via env pin); never hand-roll |
| V10 Malicious Code / supply chain | yes | pinned npm version, pinned digests, no `@latest` |
| V12 Files and Resources | yes | ledger writes refuse symlinks/races; no write into another tool's config without a ledger entry |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Registry argv starting with `sudo`/`pkexec`/`doas` | Elevation | `_elevation_head` on every argv key incl. the new install key; AST test |
| Inherited `AWS_CLI_INSTALL_SKIP_SIGNATURE_VERIFICATION=true` | Tampering | method `env` pins it to `false` |
| User-edited ledger naming another file or key | Tampering | `_agent_files` allow-list and key-path allow-list on revert |
| Overwriting a user's MCP server | Tampering / data loss | absent-only insert; `set_by_you` kept; byte-identical test |
| Deleting `~/.aws` credentials | Information disclosure / data loss | no `config_paths`; container byte-identical check |
| Unpinned MCP package drift | Tampering | exact `@playwright/mcp@0.0.85` in the server args, one pin source |
| `~/.claude/settings.json` write without consent | Repudiation | listed, confirmed plan step (D-15) |

## Sources

### Primary (HIGH confidence)
- In-repo code read this session: `installer/model.py`, `resolve.py`, `executors.py`, `engine.py`, `status.py`, `session.py`, `update.py`, `uninstall.py`, `ownership.py`, `postinstall.py`, `post_install.py`, `agent_settings.py`, `agent_env.py`, `receipts.py`, `app.py`, `version_status.py`, `appimage_menu.py`, `registry.toml`, `scripts/container-e2e-verify.sh`, `tests/test_registry.py`, `tests/test_resolve.py`, `tests/test_executors.py`, `tests/test_shell_scripts_path.py`, `tests/test_reachability.py`, `tests/test_docs_only.py`, `.claude/skills/tool-onboarding/SKILL.md`, `.claude/testing.md`, `.claude/architecture.md`
- `gh api repos/usebruno/bruno/releases/latest`, `repos/github/gh-stack`, `.../releases/latest`, Bruno builder config at v4.3.0
- registry.npmjs.org `@playwright/mcp`; formulae.brew.sh cask `bruno`, formula `awscli`; archlinux.org package search
- awscli.amazonaws.com/v2/install.sh (read 2026-11-21); Homebrew install.sh (CLT probe)

### Secondary (MEDIUM confidence)
- [Claude Code MCP docs](https://code.claude.com/docs/en/mcp) (user scope in `~/.claude.json`)
- [Copilot CLI: add MCP servers](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers)
- [OpenCode MCP servers](https://opencode.ai/docs/mcp-servers/)
- [Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
- [Cursor MCP](https://cursor.com/docs/mcp) and [forum: CLI does not detect MCP settings](https://forum.cursor.com/t/cursor-cli-does-not-detect-mcp-settings/148397)
- [AWS blog: single-line install and update](https://aws.amazon.com/blogs/developer/installing-and-updating-the-aws-cli-with-single-line-commands/)
- [gh help environment](https://cli.github.com/manual/gh_help_environment)
- `.planning/research/2026-10-13-from-ai-kit/16-playwright-chrome-bazzite.md`

### Tertiary (LOW confidence)
- Electron/AppImage runtime behavior, bunx shebang handling, Pi MCP schema (Assumptions A1-A3, A6, A10)

## Metadata

**Confidence breakdown:**
- Standard stack (pins, kinds): HIGH: pins re-read live, kinds read in code.
- Architecture (extensions, ledger-based MCP writer): MEDIUM: the code facts are verified, but the MCP writer design is a recommendation that resolves a conflict with D-14's mechanism.
- Pitfalls: HIGH for the code-derived ones (1-4, 6, 8-10), MEDIUM for host/runtime ones (5, 7, 11, 12).

**Research date:** 2026-11-21
**Valid until:** 2026-12-05 for pins and host schemas (fast-moving: npm latest, OpenCode v2, Claude docs); 2026-12-21 for the code facts.
