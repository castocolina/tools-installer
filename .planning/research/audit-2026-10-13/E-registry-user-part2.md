# Registry audit E: user tier, part 2 (24 tools)

Date: 2026-10-13. Auditor E of 7. Read-only: no code, registry or config was changed and nothing was installed or removed.

Tools: dasel, gron, aichat, codex, claude, opencode, cursor-agent, antigravity, procs, jless, gitleaks, vale, broot, vscode, jetbrains-toolbox, sublime, mmdc, kitty, wezterm, alacritty, glab, pi, drawio-desktop, drawio-cli.

## How this was checked

**Checked live:**
- **Resolver probe** (`/tmp/claude-1000/auditE/probe.py`). It loads `installer/registry.toml` and runs `resolve_methods` and `unavailable_reason` on 10 synthetic `Platform` cells, each with and without brew. The cells are macOS arm64/amd64, then Debian, Fedora, immutable Fedora and Arch, each on amd64/arm64.
- **Host probe on this Bazzite host** (`/tmp/claude-1000/auditE/live.py`). The host is immutable Fedora amd64 with linuxbrew. For each tool the probe runs:
  - `is_installed`
  - `read_inventory` + `resolve_ownership` (with the real `run_probe`)
  - `owner_label` / `removal_hint`
  - `version_status._version_argv`
  - `plan_uninstall` and `classify_tools` against `~/.local/bin`
- **Upstream checks:**
  - `gh api repos/<repo>/releases/latest` for every `github_release` repo.
  - `curl -I` on every pinned or `latest` URL: VS Code ×4, Sublime 4200 ×3, JetBrains `linux` and `linuxARM64`, draw.io v31.0.2 zips.
  - Streamed archive listings for the JetBrains Toolbox tarball, the Sublime tarball, the VS Code tarball and the broot zip.
  - The draw.io `Files-SHA256-Hashes.txt` file.
  - Sublime's `stable_update_check`.
- **Vendor install scripts** fetched and read: codex, claude, cursor, opencode, antigravity. I also read `opencode uninstall --help` and the `--help` output of each agent CLI for update and uninstall subcommands.
- **`--version` output** of installed tools, checked against `installer.versions.extract_observed_version`.

**From documentation (WebFetch):**
- code.claude.com/docs/en/setup (native uninstall and config paths).
- sw.kovidgoyal.net/kitty/binary (uninstall, desktop integration, installer.sh works on macOS).
- cursor.com/docs/cli/installation (no uninstall documented).

**Not done:**
- No install, update or uninstall was executed.
- macOS was not run; the macOS cells are resolver output only.
- The codex tty-prompt hang is proven from the script source and from `installer/run.py`, not reproduced in the TUI.

## Resolver result per platform cell

`gr` = github_release. "nobrew" = the same cell when `has_brew=False`. Only cells that differ from "every cell resolves" are listed.

| Tool | Methods picked | Cells with NO method | Acceptable? |
|---|---|---|---|
| dasel, gron, aichat, procs, gitleaks, vale | gr > brew (every cell) | none | yes |
| jless | gr > brew | none on paper. On Linux arm64 `gr` is attempted and fails with a 404 (no aarch64 Linux asset upstream), then falls to brew. Without brew it fails at run time. | Wrong ladder. Data fix below. |
| broot | gr > brew | none on paper. On macOS amd64 the zip has no `x86_64-apple-darwin/broot` member, so unzip fails, then falls to brew. | Wrong ladder. Data fix below. |
| codex, claude | script (> cask on macOS) | none | yes |
| opencode | script > brew (Arch: script > pacman > brew) | none | yes |
| cursor-agent, antigravity | script | none | yes |
| vscode | app > cask (mac); tarball (Linux) | none | yes |
| jetbrains-toolbox | cask (mac); tarball (Linux amd64) | Linux arm64 ×4 (all distros). macOS without brew. | No. An arm64 URL exists (`platform=linuxARM64`, 302 to `jetbrains-toolbox-3.8.1.88030-arm64.tar.gz`). The macOS artifact is a dmg only (999.3). |
| sublime | app > cask (mac); tarball (Linux) | none | yes (but see blocker) |
| mmdc | node (every cell) | none here. Linux arm64 is skipped through puppeteer's `arch=["amd64"]` gate. | yes (documented) |
| kitty | cask (mac); script > native (mutable Linux); script (immutable) | macOS without brew | Weak. kitty's installer.sh also supports macOS. |
| wezterm | cask (mac); gr AppImage (deb/fed amd64, incl. immutable); pacman (Arch) | deb/fed/fedImm arm64. macOS without brew. | arm64: upstream ships only `.deb` arm64. macOS: upstream ships `WezTerm-macos-<tag>.zip`, so an `app` method is possible. |
| alacritty | apt/dnf/pacman | macOS ×2, immutable Fedora ×2 | Known (999.11) |
| glab | brew | every cell without brew | Weak on a Linux host with no brew |
| pi | host_setup handoff | none | yes |
| drawio-desktop / drawio-cli | app (mac, pinned v31.0.2); gr AppImage (Linux) | none | yes (but see uninstall/update) |

`unavailable_reason` wording is misleading for mixed rejections. On wezterm Fedora arm64 it says "fedora not supported; not built for arm64; fedora not supported" (the macOS-only cask's rejection is reported as "fedora not supported"). This is a minor UI issue (NEW, near 999.6).

## Matrix

Uninstall levels follow 999.8: L1 = derived from the manager, L2 = paths derived from method params, L3 = explicit recipe needed. "Now" is what `classify_tools`/`plan_uninstall` does today.

| Tool | Install coverage (cells missing) | Detect / version / owner | Uninstall (now → correct?) | Configure needs (met?) | Health detectable? | Verdict |
|---|---|---|---|---|---|---|
| dasel | all | detect ✓, owner ✓ (GitHub release). Version ✗: dasel v3 rejects `--version` (exit 80). | REMOVABLE `~/.local/bin/dasel` → correct (L2) | none | n/a | minor |
| gron | all | detect ✓, owner ✓. Version ✗: upstream binary prints `gron version dev`. | REMOVABLE opt + link → correct (L2) | none | n/a | minor |
| aichat | all | not installed here; shape same as gron | L2 ✓. Config `~/.config/aichat` holds API keys → policy should be ask. | First-run config/API key not handled | no | minor |
| codex | all | detect ✓, owner "own installer" ✓, version ✓ | MANAGED "own installer" → needs L3 recipe | companions via postinstall ✓, alias tweak ✓, herdr 999.11 | self-update ✓. **Install/update can block on a /dev/tty prompt** | **major** |
| claude | all | detect ✓, version ✓. **Owner unknown** (active path `~/.local/share/claude/versions/<v>`, no bin_dir). | MANAGED, hint **"remove with your package manager" (wrong)** → L3: `rm ~/.local/bin/claude; rm -rf ~/.local/share/claude` | as codex | Owner cell empty on the primary agent | **major** |
| opencode | all | detect ✓, owner "own installer" ✓ | MANAGED → L3: `opencode uninstall --keep-config --keep-data` (the vendor default deletes config) | Vendor script appended `export PATH=…/.opencode/bin` to `~/.bashrc` (live), duplicating `~/.myshellrc` | rcclean can see the duplicate | minor |
| cursor-agent | all | detect ✓, version ✓. **Owner unknown** (versioned dir). | MANAGED, wrong generic hint → L3: rm `~/.local/bin/{cursor-agent,agent}`, `~/.local/share/cursor-agent`. Keep `~/.cursor` (shared with the IDE). | alias/function tweak ✓, companions ✓ | Owner empty | **major** |
| antigravity | all | detect ✓, owner ✓, version ✓ | MANAGED → L3: `rm ~/.local/bin/agy`. **Never** delete `~/.gemini` (shared with Gemini CLI, `oauth_creds.json`). | no companions (D-01 deferred) | **`u` update is a silent no-op**: the script exits 0 when agy exists | minor |
| procs | all | detect ✓, owner ✓. Version ✗: output `procs "0.14.12 (…` is not parsed. | L2 ✓ | none | n/a | minor |
| jless | Linux arm64 needs brew | ✓ | L2 ✓ | none | n/a | minor |
| gitleaks | all (checksummed) | ✓ (8.30.1) | L2 ✓ | none | n/a | OK |
| vale | all (checksummed) | absent here; same shape as gitleaks | L2 ✓ | per-project `.vale.ini` / `vale sync` (not the installer's job) | n/a | OK |
| broot | macOS amd64 needs brew | absent here | L2 ✓ | `broot --install` (the `br` shell function) not done | no | minor |
| vscode | all | live: cask `visual-studio-code-linux` ✓ | Linux tarball: L2 opt + link ✓. Cask: L1 hint ✓. | Linux tarball: no desktop entry, no update/version source | no | minor |
| jetbrains-toolbox | Linux arm64 ×4, macOS without brew | live: cask `jetbrains-toolbox-linux` ✓ | L3 (Toolbox relocates itself to `~/.local/share/JetBrains/Toolbox` + autostart + desktop entry) | — | — | **blocker** (Linux tarball install always fails) |
| sublime | all | **Live host broken**: `~/.local/bin/subl` → directory; `is_installed=False` but owner "installer by-elimination" | REMOVABLE lists only `~/.local/bin/subl` (F7 known) | none | **Not detected**. A reinstall makes it worse. | **blocker** |
| mmdc | all (arm64 gated) | live: brew `mermaid-cli`, flagged off_policy ✓ | MANAGED brew hint ✓ (L1). pnpm group coupling noted in registry. | puppeteer group (pnpm) | Doctor smoke test covers pnpm only. A brew mmdc (registry says broken) is not smoke-tested. | minor |
| kitty | macOS without brew | detect ✓ (bin_dir), owner "own installer" ✓ | MANAGED → L3 (999.2/999.8 known) | Linux zsh shell ✓, macOS skipped. Desktop integration ✗, keybindings ✗, `$SHELL` 999.4. | no | minor (known) |
| wezterm | deb/fed arm64, macOS without brew | ✓ (AppImage) | REMOVABLE `~/.local/bin/wezterm` → L2 correct; stale `org.wezfurlong.wezterm.desktop` left | Linux `default_prog` ✓, keybindings ✗ | AppImage needs libfuse2 (missing by default on Ubuntu 24.04): not checked | minor |
| alacritty | macOS ×2, immutable ×2 | absent | UNAVAILABLE "not available on fedora" | not covered by `terminal_shell.py` | — | **major** (known 999.11) |
| glab | every no-brew cell | brew ✓ | L1 ✓ | `glab auth login` (token in `~/.config/glab-cli`) | no | minor |
| pi | all (manual handoff) | detect ✓. **Owner never resolves** (host-setup probe discarded). **Version probe runs `volta-shim` directly → error.** | MANAGED generic hint. The registry `uninstall` text is never read (F11). | herdr integration missing (999.11) | no | **major** |
| drawio-desktop | all | Linux ✓. macOS cli name `draw.io` not `drawio` (AR-07 known). | REMOVABLE shared file (F1 known) | none | **`u` on macOS re-downloads pinned v31.0.2** (downgrade of a self-updated app) | **major** |
| drawio-cli | all | same file as drawio-desktop | same file → removing one removes the other (F1 known) | none | as above | **major** (known) |

Counts: OK 2, minor 13, major 7, blocker 2.

## Per-tool notes

### Blockers

**sublime (Linux): every install produces a broken `subl`; a second install destroys the binary. NEW, live-confirmed.**
- `registry.toml:2266-2279` declares `member = "sublime_text"`, no `strip`. The official tarball's top level is a `sublime_text/` directory (listing: `sublime_text/`, `sublime_text/Packages/…`). So `download.py:_install_unverified` (lines 176-189) and `_place_verified` (lines 376-404) do this:
  1. Compute `binary = ~/.local/opt/subl/sublime_text`, which is the directory.
  2. `chmod +x` that directory.
  3. Run `ln -sf <dir> ~/.local/bin/subl`.
- On reinstall, GNU `ln -sf` without `-n` dereferences the existing link-to-directory. It replaces `~/.local/opt/subl/sublime_text/sublime_text`, the real binary, with a symlink to its own parent directory. I reproduced this in scratch.
- Live host evidence:
  - `~/.local/bin/subl -> ~/.local/opt/subl/sublime_text`, a directory, so running it gives "Is a directory".
  - `~/.local/opt/subl/sublime_text/sublime_text -> ~/.local/opt/subl/sublime_text`, a self-loop dated Sep 23 18:44, which is a second run.
  - The real executable is gone.
- Detection: `shutil.which` rejects a directory, so `is_installed=False` and the catalog offers a reinstall, which repeats the damage. `resolve_ownership` still says owner=installer, by-elimination, because the artifact exists. The Uninstall view removes only `~/.local/bin/subl` (F7). Nothing flags this as broken.
- `update_download` → `_replace_archive` checks `os.access(live_binary, X_OK)`. A directory passes that check, so an update also reports success.

**jetbrains-toolbox (Linux): the tarball method cannot succeed. NEW.**
- The `latest` tarball (3.8.1.88030) unpacks to `jetbrains-toolbox-<v>/bin/jetbrains-toolbox`. After `strip = 1` the binary is at `~/.local/opt/jetbrains-toolbox/bin/jetbrains-toolbox`. The registry `member = "jetbrains-toolbox"` (`registry.toml:2216-2222`) points to a path that does not exist, so `chmod +x` fails.
- No other Linux method exists. Every Linux amd64 host without the linuxbrew cask gets FAILED and a 150 MB orphan `~/.local/opt/jetbrains-toolbox`.
- This host works only because the cask `jetbrains-toolbox-linux` is installed. Ownership attributes it correctly.
- Separately, the "no stable arm64 URL could be confirmed" comment is stale. `?platform=linuxARM64&code=TBA` returns 302 to `jetbrains-toolbox-3.8.1.88030-arm64.tar.gz`.
- Removal: Toolbox moves itself to `~/.local/share/JetBrains/Toolbox` on first run and writes `~/.local/share/applications/jetbrains-toolbox.desktop` plus an autostart entry. The `~/.local/opt` copy is only a launcher. This is L3.

### Agent CLIs

**codex: the vendor installer prompts on `/dev/tty`. NEW. Proven from source, not reproduced.**
- `https://chatgpt.com/codex/install.sh` always calls `maybe_launch_codex_now` at its end (line 1305). It reads `prompt_yes_no "Start Codex now?"` from `/dev/tty` whenever `( : </dev/tty )` succeeds (lines 842-870). A brew/npm/bun copy triggers a second prompt, "Uninstall the existing … Codex now?" (line 937).
- `installer/run.py` never detaches the child from the controlling terminal. `run_output` uses `subprocess.run(..., capture_output=True)`, which inherits the tty. `StreamRunner` uses `stdin=DEVNULL` but has no `start_new_session`.
- So under Textual, the prompt is written into the frame and `read` competes with Textual for the raw-mode tty. The likely result is an install (and every `u` update, which re-runs the script, `update.py:337`) that hangs until a keypress.
- The script documents `CODEX_NON_INTERACTIVE=1`, and the registry already supports `env = {…}` on script methods (`executors._env_prefix`).

**Self-updating CLIs (codex, claude, cursor-agent, antigravity, opencode).**
- `update.py:_update_installer_owned` re-runs the vendor script. For antigravity that is a no-op: the script prints "already installed" and `exit 0` (agy.sh lines 56-63). The UI reports "updated".
- Vendor update commands exist and are the right L3 update recipes: `codex update`, `claude update`, `cursor-agent update`, `agy update`, `opencode upgrade`.
- claude and cursor-agent resolve to owner `unknown`. `u` is refused, which is correct, but the Owner column is empty for the two most-used agents.
- The cause is that their binaries live in versioned directories (`~/.local/share/claude/versions/<v>`, `~/.local/share/cursor-agent/versions/<rel>/`) that no `bin_dir` can name. The registry deliberately declares "no bin_dir". The model has no "install root" location proof (`ownership.py:914-930` only knows `<bin_dir>/<cmd>`). This maps to 999.2 (receipt) or a declared install root.

**Vendor removal recipes and config policy (input for 999.8).**

| Tool | Binary removal | Config / data | Default policy |
|---|---|---|---|
| codex | `rm ~/.local/bin/codex ~/.local/bin/codex-code-mode-host; rm -rf ~/.codex/packages/standalone`; remove the `# >>> Codex installer >>>` block if the script added one | `~/.codex` (config.toml, **auth.json**, sessions, AGENTS.md) | keep config; ask before credentials |
| claude | `rm -f ~/.local/bin/claude; rm -rf ~/.local/share/claude` (official docs) | `~/.claude/`, `~/.claude.json` (docs warn they are shared with the IDE plugins and Desktop) | keep |
| opencode | `opencode uninstall --keep-config --keep-data` (vendor default deletes both) | `~/.config/opencode` (live uses `opencode.jsonc`) | keep |
| cursor-agent | `rm ~/.local/bin/cursor-agent ~/.local/bin/agent; rm -rf ~/.local/share/cursor-agent` (from script lines 110-131; no documented uninstall) | `~/.cursor/cli-config.json`; `~/.cursor` shared with the Cursor IDE | keep, never rm `~/.cursor` |
| antigravity | `rm ~/.local/bin/agy` | `~/.gemini/antigravity-cli`; `~/.gemini` shared with Gemini CLI (`oauth_creds.json`) | keep |
| pi | the `pnpm remove -g …` / `volta uninstall …` that matches the real owner | `~/.pi` | keep |
| aichat | L2 paths | `~/.config/aichat` (API keys) | ask |

- opencode's own installer appends PATH to rc files unless given `--no-modify-path` (opencode.sh lines 20, 386-435). Live `~/.bashrc:47-48` has `# opencode` / `export PATH=…/.opencode/bin:$PATH` next to the managed `~/.myshellrc` line 5.
- `agent_env.py:42-47` assumes `opencode.json`, while live is `opencode.jsonc`. That code is unreachable today (F11), but it would create a second config file if it were ever wired.

**pi.**
- The `host_setup` probe (`install_ownership._host_setup`) returns a verified pnpm owner. But `ownership._native_owner` discards every non-native verified manager (`ownership.py:794-800`), and `_collect_candidates` only creates pnpm candidates for `node` methods. So a pnpm-installed pi always reads `unknown`.
- On this host pi is a Volta global (`~/.volta/bin/pi -> volta-shim`, package in `~/.volta/tools/image/packages/@earendil-works`). That is neither the declared pnpm owner nor a known Owner.
- `_version_argv` (`version_status.py:225-227`) runs `ownership.active_path`, which is the resolved symlink target. Running `volta-shim --version` prints "Volta error: 'volta-shim' should not be called directly". `pi --version` gives `0.82.1`.
- Every argv[0]-dispatch shim breaks the same way (volta, mise, busybox-style links). This is a NEW cross-cutting bug.

### Terminals

**kitty.**
- Linux: the script runs on every Linux cell, including immutable, and `kitty.conf` gets the owned `shell … -l` region (`terminal_shell.py:410-418`).
- Gaps:
  - Linux desktop integration is never done. kitty docs say to copy `kitty.desktop` and `kitty-open.desktop` into `~/.local/share/applications` and fix their paths.
  - The Uninstall view cannot remove kitty (999.2/999.8). Docs: "delete that directory", plus the links and desktop files.
  - macOS needs brew, although installer.sh supports macOS.
  - `$SHELL` mismatch (999.4).
  - No keybindings: alt+arrow word navigation, Cmd+K / Ctrl+Shift+K clear. ROADMAP lists these only for Alacritty (999.11). For kitty/WezTerm they are NEW.
- The user's own `kitty-setup` include, which provides `clear.conf`, is outside the installer.

**wezterm.**
- The AppImage asset and `.sha256` match release `20240203-110809-5046fc22`. That is the newest stable release (2024-02-03); upstream ships nightlies since.
- Version compare works: `extract_observed_version` → `20240203-110809-5046fc22`, `is_outdated` False.
- No health signal if libfuse2 is missing.
- Uninstall removes the AppImage. The desktop entry and the `wezterm.lua` region are left, and leaving the config is acceptable.
- macOS: the `WezTerm-macos-<tag>.zip` asset would let an `app` method cover hosts without brew.

**alacritty:** state as documented in 999.11. Nothing new.

### Diagrams

**drawio-desktop / drawio-cli.**
- Already known: the shared artifact (F1) and the ignored `cli_name` (AR-07).
- NEW 1: macOS `app` URLs are pinned to v31.0.2 while latest is v32.4.1. `catalog_tui.action_update_tool` (lines 899-951) lets `u` proceed whenever `outdated` is not `False`. For an `app` method there is no version source (`github_repo` only reads `github_release`), so `outdated` stays `None`. `apps.update_app` then re-downloads the pin. That downgrades a draw.io that has updated itself. Sublime's macOS pin (4200 vs latest 4215) has the same shape.
- NEW 2: upstream publishes `Files-SHA256-Hashes.txt` in `<hash>  <name>` format with both AppImage lines. The Linux methods could be checksum-verified (data-only).

**mmdc.** This host has brew `mermaid-cli` 11.17.0. Ownership attributes it to brew and flags off_policy, which is correct. The registry says the brew mmdc fails at render time. The Doctor's puppeteer smoke test (`pnpm_globals.audit_node_globals`) runs only for pnpm-managed tools, so the known-broken brew shape gets no health warning.

### CLIs

- **jless** (`registry.toml:1918-1923`): the Linux `github_release` method declares no `arch`, so Linux arm64 tries a 404 first. Without brew it ends FAILED instead of "not built for arm64".
- **broot**: verified zip members: `x86_64-unknown-linux-gnu/broot`, `aarch64-unknown-linux-gnu/broot`, `aarch64-apple-darwin/broot`. There is no `x86_64-apple-darwin`, so the macOS method should be `arch = ["arm64"]`. The `br` shell function (`broot --install`) is not offered.
- **Version blind spots on installer-owned github_release tools:**
  - dasel: `--version` is unsupported in v3 (`dasel version` works).
  - gron: release binary says `dev`.
  - procs: quoted output is not parsed.
  - In each case `outdated` is `None` forever. The schema has no per-tool version argv override (only `version_file`).
- **glab**: brew only. GitLab's releases live on gitlab.com, which `github_release` cannot express. Distro packages are worth verifying as no-brew fallbacks.

## Cross-cutting architecture gaps

1. **NEW: archive installs never verify that the linked member is an executable file, and `ln -sf` lacks `-n`.**
   - Where: `download.py:189` and `:404`.
   - Effect: a wrong `member` silently installs a link to a directory (sublime). A reinstall over a link-to-directory overwrites the file inside it.
   - The update path checks `os.access(X_OK)`, which a directory passes.
   - Fix: `ln -sfn` (or the existing `atomic.replace_symlink`), plus an `is_file()` check after extraction.
   - Also needs a registry test that resolves each tarball/zip member against a recorded archive listing. Close to 999.3/999.8.
2. **NEW: side-effecting children keep the controlling tty.**
   - Where: `run.py` `run_output` / `StreamRunner` (no `start_new_session=True`).
   - Effect: vendor scripts that read `/dev/tty` (codex) or run `stty` can hang or corrupt the TUI.
   - Fix: set `start_new_session` for install/update children and add the vendor non-interactive env.
3. **NEW: the version probe runs the resolved real path.**
   - Where: `version_status._version_argv` uses `ownership.active_path`, which comes from `_resolve_active_path` (`Path.resolve()`).
   - Effect: breaks argv[0]-dispatch shims (volta live, mise likely). It should run the unresolved `which` path.
4. **NEW: no per-tool version-probe override.** dasel, gron and procs stay "version unknown", so updates are never signalled.
5. **NEW: installer-owned updates are unsafe for pinned or self-updating payloads.**
   - Pinned `app` URLs (drawio, sublime) downgrade.
   - `script` re-runs are no-ops for antigravity.
   - Vendor `update` subcommands are not modelled.
   - Gating `u` on `outdated is None` (no version source) would stop silent downgrades.
6. **999.2 / 999.6: vendor scripts that install into versioned directories have no ownership proof.** claude and cursor-agent read `unknown`, and their Uninstall hint says "remove with your package manager", which is false. Needs a receipt or a declared install root.
7. **NEW (near F11): the `host-setup` owner probe result is discarded.** `_native_owner` keeps only native managers, so the pi pnpm owner is never shown. Volta is not an `Owner` at all.
8. **999.8:** level-3 recipes and config policy are needed for 7 script tools plus pi. The vendor recipes and policies are in the table above. Shared config directories (`~/.cursor`, `~/.gemini`, `~/.claude` used by IDE plugins) must be marked never-delete.
9. **NEW: desktop integration for Linux GUI payloads.**
   - Not created: kitty script, VS Code tarball, Sublime tarball (it ships `sublime_text.desktop`), draw.io and WezTerm AppImages.
   - Not removed: entries written by others (wezterm, Toolbox).
   - Stale `.desktop` files are not detected.
10. **NEW (999.11 covers only Alacritty):** terminal keybinding customizations (word navigation, clear-scrollback) for kitty/WezTerm. macOS terminal shell sync is skipped by design (`terminal_shell.py:385`).
11. **999.3:** macOS artifacts that are dmg-only (Toolbox, kitty) or zip-without-`{ver}` (WezTerm) cannot install without brew. The `app` kind is zip-only (`apps.py:88`).
12. **Health (999.6/999.9-adjacent, NEW signals):** none of these are detected today:
    - link to a directory or broken link in `~/.local/bin` (sublime)
    - stale `.desktop` files
    - vendor rc edits that duplicate the managed PATH (opencode; `rcclean` could report it)
    - AppImage FUSE dependency
    - brew-owned mmdc with no smoke test

    `ownership.broken` exists only for pnpm dangling shims (`status.dangling_shim`).

## Registry fixes (data only)

1. **sublime** Linux ×2: `member = "sublime_text/sublime_text"` (keep strip 0, `bin_name = "subl"`). Fix the existing live breakage by removing `~/.local/opt/subl` and reinstalling once code gap 1 lands; until then a reinstall over the existing link is destructive. Optionally re-pin to 4215 (mac and Linux).
2. **jetbrains-toolbox**: `member = "bin/jetbrains-toolbox"` (strip 1). Add an arm64 tarball method with `url = "https://data.services.jetbrains.com/products/download?platform=linuxARM64&code=TBA"` and `arch = ["arm64"]`. Update the stale "no arm64 URL" comment.
3. **codex** script: `env = { CODEX_NON_INTERACTIVE = "1" }`.
4. **opencode** script: `args = ["--no-modify-path"]`. The installer already manages `~/.opencode/bin` in `~/.myshellrc`.
5. **jless** Linux `github_release`: `arch = ["amd64"]`.
6. **broot** macOS `github_release`: `arch = ["arm64"]`.
7. **drawio-desktop / drawio-cli** Linux methods: `checksum = "Files-SHA256-Hashes.txt"`. Re-pin the macOS zips to 32.4.1, or stop `u` from downgrading (gap 5).
8. **kitty**: allow the script method on macOS too (`os` += `"macos"`). Re-verify the install root `/Applications/kitty.app` and the `bin_dir` before doing this.
9. **wezterm**: optional macOS `app` method from `WezTerm-macos-<tag>.zip`. It needs a pinned URL because the `app` kind takes no `{ver}`.
10. **glab**: research and add native fallbacks (Fedora `glab`, Arch `glab`, Debian availability) for hosts without brew. Unverified here.
11. **pi**: the `uninstall` text names pnpm, but this host's real owner is Volta. Either have the hint follow the resolved owner (gap 7), or soften the text.

Not checked: macOS behaviour live; JetBrains/VS Code/Sublime/draw.io dmg/zip internals beyond the listings above; Arch/Debian/glab native package names; whether `claude install` itself touches the tty.
