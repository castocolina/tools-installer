# Catalog audit - 2026-11-13
complete 86/86

## Proposed changes
- brew: drop the macOS amd64 script method (registry.toml:186-195) and update the `# Verified` comment to say Homebrew supports Apple Silicon only on macOS; risk: low; evidence: https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh lines 169-171
- bat: add config_paths for bat's config dir (confirm the exact path with `bat --config-dir` in a container) to the bat [[tool]] entry; risk: low; evidence: https://github.com/sharkdp/bat/blob/v0.26.1/README.md
- eza: move Arch to a pacman method and Fedora to a dnf method, keep github_release for Debian and brew for macOS; on Fedora Atomic hosts the dnf method needs the rpm-ostree owner probe as git uses (installer/registry.toml:303); risk: medium; evidence: https://github.com/eza-community/eza/blob/v0.23.5/INSTALL.md
- eza: add config_paths = ["~/.config/eza"] to the eza [[tool]] entry (EZA_CONFIG_DIR overrides it); risk: low; evidence: https://github.com/eza-community/eza/blob/v0.23.5/README.md
- zoxide: add config_paths = ["~/.local/share/zoxide", "~/Library/Application Support/zoxide"] to the zoxide entry so the database is recorded and kept on removal by default; risk: low; evidence: https://raw.githubusercontent.com/ajeetdsouza/zoxide/main/README.md lines 404-411
- lazygit: add config_paths = ["~/.config/lazygit", "~/Library/Application Support/lazygit"] to the lazygit entry so the config and state directory is recorded and kept on removal by default; risk: low; evidence: https://raw.githubusercontent.com/jesseduffield/lazygit/master/docs/Config.md lines 5-6 and 1001
- gh: add ~/.local/state/gh to the gh entry's config_paths so the state directory is recorded and kept on removal by default; risk: low; evidence: https://raw.githubusercontent.com/cli/go-gh/trunk/pkg/config/config.go lines 291-303
- starship: add `config_paths = ["~/.config/starship.toml"]` to the starship tool so removal states the config policy; risk: low; evidence: https://starship.rs/config/
- oh-my-zsh: declare `paths = ["~/.oh-my-zsh"]` on the script method so Uninstall removes the framework directory, keeping `~/.zshrc` with the rc ledger and the user's `custom/` dir under the keep policy, after a container check; risk: medium; evidence: `upstream tools/install.sh:92`, `upstream tools/uninstall.sh:21`
- direnv: add `config_paths = ["~/.config/direnv"]` to the direnv tool so removal states the config policy (default keep, since direnv.toml is user-written); risk: low; evidence: https://direnv.net/man/direnv.toml.1.html
- gum: move the arch and fedora methods to the vendor-listed `pacman` and `dnf` packages once their current version is checked; risk: low; evidence: https://github.com/charmbracelet/gum#installation
- glow: make `config_paths` per OS: `~/.config/glow` on Linux and the macOS directory on darwin once the app-name join is checked; risk: medium; evidence: https://raw.githubusercontent.com/charmbracelet/glow/main/main.go
- glow: move the arch method to `pacman -S glow` once its current version is checked; risk: low; evidence: https://github.com/charmbracelet/glow#installation
- xh: declare `config_paths` for xh (`~/.config/xh` on Linux, with the macOS path checked) and state the default config policy `keep` or `ask`, so a delete choice reaches the session files; risk: medium; evidence: https://raw.githubusercontent.com/ducaale/xh/master/src/utils.rs
- xh: move the arch and debian methods to `pacman -S xh` and `sudo apt install xh` once their current version is checked; risk: low; evidence: https://github.com/ducaale/xh#installation
- difftastic: move the arch and fedora methods to `pacman -S difftastic` and `dnf install difftastic` once their current version is checked; risk: low; evidence: https://difftastic.wilfred.me.uk/installation.html
- gitui: declare `config_paths = ["~/.config/gitui"]` and state the default config policy `keep` or `ask`, so a delete choice covers the user's `.ron` files; risk: medium; evidence: https://raw.githubusercontent.com/gitui-org/gitui/master/THEMES.md
- gitui: move the arch and fedora methods to `pacman -S gitui` and `sudo dnf install gitui` once their current version is checked; risk: low; evidence: https://github.com/gitui-org/gitui#installation
- lazydocker: add `config_paths` for the Linux and macOS config locations, with the macOS path as a per-OS variant; risk: low; evidence: https://raw.githubusercontent.com/jesseduffield/lazydocker/master/docs/Config.md
- lazydocker: record the docker runtime expectation in a `# Verified` note, or add an edge if the catalog should install docker first; risk: low; evidence: https://raw.githubusercontent.com/jesseduffield/lazydocker/master/README.md
- docker: move the Debian and Ubuntu apt method to the Docker apt repository, or record in `# Verified` why the distro package is kept; risk: medium; evidence: https://docs.docker.com/engine/install/ubuntu/
- docker: declare the data path `/var/lib/docker` and the client config `~/.docker` as removal-policy paths, with the keep default; risk: medium; evidence: https://docs.docker.com/engine/install/ubuntu/ and `cli/config/config.go:27-28` in https://github.com/docker/cli
- docker: add a `# Verified` note for the daemon expectation, or an edge, as chosen for lazydocker; risk: low; evidence: https://formulae.brew.sh/api/formula/docker.json
- podman: add a macOS pkg or GitHub release method ahead of brew, or record in `# Verified` why brew stays; risk: medium; evidence: https://podman.io/docs/installation
- podman: record the podman machine runtime expectation in `# Verified`, and confirm the machine data directories before declaring any path; risk: low; evidence: https://podman.io/docs/installation
- colima: add `config_paths = ["~/.colima"]` so the Uninstall screen lists the config and VM data, with the keep default; risk: medium; evidence: https://github.com/abiosoft/colima docs/FAQ.md lines 124-137
- dive: add the upstream user config paths `~/.config/dive` and `~/.dive.yaml` to the dive entry's `config_paths` with the default `keep` policy; risk: low; evidence: https://github.com/wagoodman/dive/blob/v0.13.1/README.md (Configuration)
- duf: add a dnf method for fedora (or drop the github_release fedora method) if the install-method drift is accepted, so the distro package owns duf there; risk: medium; evidence: https://github.com/muesli/duf (README) and `rpm -qf /usr/bin/duf` output above
- miller: add the upstream user config paths `~/.mlrrc` and `~/.config/miller` to the miller entry's `config_paths` with the default `keep` policy; risk: low; evidence: https://github.com/johnkerl/miller/blob/main/docs/src/customization.md
- tealdeer: add ~/.config/tealdeer to the tealdeer entry's config_paths so the config file is recorded and kept on removal by default; risk: low; evidence: https://api.github.com/repos/tealdeer-rs/tealdeer/contents/src/config.rs?ref=v1.9.1 lines 874-881
- fx: add config_paths = ["~/.fxrc.js", "~/.config/fx/.fxrc.js"] to the fx entry so the user's rc file is recorded and kept on removal by default; risk: low; evidence: https://api.github.com/repos/antonmedv/fx/contents/internal/engine/fxrc.go?ref=40.0.1 lines 21-31
- dasel: add config_paths = ["~/dasel.yaml"] to the dasel entry so the user's config file is recorded and kept on removal by default; risk: low; evidence: https://api.github.com/repos/TomWright/dasel/contents/internal/cli/query.go?ref=v3.11.2 line 17
- gron: move the brew method ahead of the two github_release methods for gron or pin sha256 for the release assets so the first method is checksum-verified; risk: medium; evidence: https://formulae.brew.sh/api/formula/gron.json
- codex: declare `update = ["codex", "update"]` on the script method and drop the "no `codex update`" comment; risk: low; evidence: https://developers.openai.com/codex/cli/reference
- opencode: switch the script method to https://opencode.ai/v2/install with `paths` listing both `~/.opencode/bin/opencode` and `~/.opencode/bin/opencode2`, and drop `update` so an update re-runs the v2 installer; risk: medium; evidence: https://opencode.ai/v2/install lines 345-374
- opencode: add a removal recipe that stops the background service before the binary goes; risk: medium; evidence: https://opencode.ai/v2/install lines 345-374 (opencode2 shim) and the v2 service CLI
- opencode: move the brew method from the tap formula anomalyco/tap/opencode to homebrew/core opencode; risk: low; evidence: https://formulae.brew.sh/api/formula/opencode.json
- opencode: write `permissions` for auto-approve and keep `permission` as a revert-only retired key; risk: medium; evidence: https://opencode.ai/config.json
- opencode: add an npm-based latest source for the script method (GitHub's latest is the 1.x line); risk: low; evidence: https://registry.npmjs.org/@opencode/cli
- antigravity: correct the `# Verified` comment: install.sh checks the SHA-512 against the manifest it fetched from the same host and does not verify a signature (https://antigravity.google/cli/install.sh lines 122-142 and 188-199), so "signed manifest" is not supported; risk: low; evidence: https://antigravity.google/cli/install.sh
- antigravity: record the ~/.gemini/bin and ~/.gemini/antigravity-cli state in the `# Verified` comment so removal is not assumed complete; risk: low; evidence: https://antigravity.google/docs/changelog
- codegraph: add `"copilot": "copilot-cli"` to `_CODEGRAPH_TARGETS` in `installer/postinstall.py:161` (the CSV order test in `tests/test_postinstall.py` pins the current four ids); risk: low; evidence: `codegraph install --print-config copilot-cli` exits 0 on v1.6.2, https://github.com/colbymchenry/codegraph/blob/main/src/installer/targets/copilot-cli.ts
- codegraph: add `"pi": "pi"` only behind a per-target capability probe (`codegraph install --print-config pi` must exit 0), because an unknown target aborts the whole CSV and so the claude, codex, opencode and cursor registrations in the same call; risk: medium; evidence: `codegraph install --print-config pi` exits 1 on v1.6.2, https://github.com/colbymchenry/codegraph/blob/main/src/installer/targets/pi.ts
- codegraph: declare ~/.codegraph as a tool-level `config_paths` entry for codegraph with an explicit keep or delete policy, and cover a vendor self-upgrade in removal; risk: medium; evidence: https://raw.githubusercontent.com/colbymchenry/codegraph/main/install.sh
- graphify: correct the `# Verified` comment: a bare `graphify install` is user-global, and `--project` is the project-scoped form (https://pypi.org/project/graphifyy/, lines 205-213); risk: low; evidence: https://pypi.org/project/graphifyy/
- graphify: decide whether the removal flow should run `graphify uninstall` (README line 318 names it) before `uv tool uninstall`, or document that host registrations stay; risk: medium; evidence: graphifyy 0.9.103 changelog, https://api.github.com/repos/Graphify-Labs/graphify/releases
- sdkman: declare the install footprint on the script method: `paths` for the directory the installer owns and `config_paths` for ~/.sdkman/etc/config, per `.claude/skills/tool-onboarding/SKILL.md:98` (step 4b); a removal of ~/.sdkman deletes every installed JDK, so run a container check first; risk: medium; evidence: https://sdkman.io/install (Uninstallation)
- sdkman: correct the comment at registry.toml:1980-1982: the upstream docs describe the shell init snippet as something the install adds (`?rcupdate=false` skips it) and the uninstall removes, so "the rc init snippet is the user's, not ours" does not match upstream; risk: low; evidence: https://sdkman.io/install (Install without modifying shell config; Uninstallation)
- java: give the `sdkman` kind an L1 removal argv (`sdk uninstall java <version>`) in `installer/uninstall.py` MANAGER_UNINSTALL_ARGV, or record the removal as a SDKMAN hand-off message like `_SDKMAN_DETAIL`; risk: medium; evidence: https://sdkman.io/usage (uninstall example)
- groovy: none beyond the sdkman removal argv proposed for the `java` entry, which covers this kind (`installer/uninstall.py` MANAGER_UNINSTALL_ARGV); risk: medium; evidence: https://sdkman.io/usage (uninstall example)
- springbootcli: none for this entry beyond the sdkman removal argv proposed in the java report, which covers this kind (`installer/uninstall.py` MANAGER_UNINSTALL_ARGV); risk: medium; evidence: https://sdkman.io/usage (uninstall example)
- gradle: none for this entry beyond the sdkman removal argv proposed in the java report, which covers this kind (`installer/uninstall.py` MANAGER_UNINSTALL_ARGV); risk: medium; evidence: https://sdkman.io/usage (uninstall example)
- bun: record the vendor script's `# bun` rc block in the entry's `# Verified` comment and decide its removal (leave it, or remove that block by ownership); risk: medium; evidence: https://bun.sh/install:236-246
- volta: keep Volta with a re-dated note, or replace it with mise through tool-onboarding; this is the user's decision because the vendor now recommends mise; risk: medium; evidence: https://raw.githubusercontent.com/volta-cli/volta/main/README.md line 21
- vale: switch both stanzas to repo = "vale-cli/vale" at installer/registry.toml:2389 and :2397; risk: low; evidence: https://api.github.com/repos/errata-ai/vale
- vale: record the config and data paths that `vale sync` writes, after a container check of that step; risk: medium; evidence: https://github.com/vale-cli/vale/releases/tag/v3.27.0
- broot: declare config_paths = ["~/.config/broot"] with the default keep policy, and ask the user whether the br shell function is wanted as install tuning; risk: low; evidence: https://github.com/Canop/broot/blob/main/src/conf/mod.rs#L60-L61
- vscode: declare the VS Code User directory per OS as config_paths (~/.config/Code/User on Linux, ~/Library/Application Support/Code/User on macOS) with the default keep policy; risk: medium; evidence: installer/agent_env.py:36-39
- sublime: after the vendor doc for Sublime's user data directory is found, declare config_paths for it; risk: low; evidence: https://www.sublimetext.com/docs/3/linux.html redirects to a 404 page, so the source is still missing
- neovim: re-check the Debian 13 claim in the registry.toml neovim comment (0.10.4) against the suite the apt method really installs, since sources.debian.org shows 0.12.4-1; risk: low; evidence: https://sources.debian.org/api/src/neovim/
- mmdc: raise the mmdc node method's min_node from 22.12.0 to 22.13.0 (installer/registry.toml:2765), so the preflight matches the package floor; risk: low; evidence: https://registry.npmjs.org/@mermaid-js/mermaid-cli/12.2.0
- puppeteer: when the linux amd64 gate is revisited, run a container check that starts a linux-arm64 Chrome before lifting arch = ["amd64"] (installer/registry.toml:2894-2902); risk: medium; evidence: https://registry.npmjs.org/@puppeteer/browsers/-/browsers-3.2.7.tgz (package/lib/browser-data/chrome.js:13-17)
- puppeteer: record ~/.cache/puppeteer as a leftover of the node method in the dated # Verified comment, since no removal path clears it; risk: low; evidence: https://registry.npmjs.org/puppeteer/-/puppeteer-25.17.0.tgz (package/src/getConfiguration.ts:162-165)
- kitty: record the macOS script removal gap in the backlog: the installer cannot remove /Applications/kitty.app until the script paths schema accepts an absolute, system-owned path; risk: medium; evidence: installer/model.py:577-585 and https://sw.kovidgoyal.net/kitty/binary/
- wezterm: declare config_paths = ["~/.config/wezterm"] on the wezterm entry so removal lists the synchronizer's file; the legacy ~/.wezterm.lua is one level under ~ and the validator refuses it (installer/model.py:439), so that case is a backlog gap; risk: low; evidence: https://wezterm.org/config/files.html
- herdr: add a brew method for macOS and Linux, since the formula is at the current 0.9.5 and tool-onboarding step 4 ranks a current package manager above a release asset; risk: low; evidence: https://formulae.brew.sh/api/formula/herdr.json
- glab: replace the Debian apt method with Homebrew on Linux, the vendor's officially supported method, or keep apt only where its package is current; risk: medium; evidence: https://gitlab.com/gitlab-org/cli/-/raw/main/docs/installation_options.md and https://sources.debian.org/api/src/glab/
- glab: declare config_paths for glab (Linux ~/.config/glab-cli, macOS ~/Library/Application Support/glab-cli), keep as the default policy, and record the plaintext-credential fallback in `# Verified`; risk: low; evidence: https://gitlab.com/gitlab-org/cli/-/raw/main/docs/source/configuration.md
- pi: refresh the Pi `desc`, `verified` and `# Verified` text at `installer/registry.toml:3201-3205`: latest is 1.5.2, the vendor now recommends the pi.dev installer or npm, `pi update` is the vendor update route, and Pi has built-in MCP; risk: low; evidence: https://github.com/earendil-works/pi#getting-started
- pi: keep the method change in Backlog 999.13 (do not adopt `pi.dev/install.sh` as is: it is 1853 lines and `sudo` appears 15 times, run_with_sudo for Node, npm and xz-utils installs on Debian and Alpine and printed `sudo npm` hints, https://pi.dev/install.sh read as data only); risk: medium; evidence: `.planning/ROADMAP.md:905`
- pi: declare Pi's `~/.pi` as a tool-level `config_paths` entry with a keep policy and state why in `# Verified`; risk: low; evidence: https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/mcp.md
- pi: decide how the catalog treats a bun global Pi (this host, `~/.bun/install/global/node_modules/@earendil-works/pi-coding-agent`): `Owner` has no bun value (`installer/ownership.py:80`), so the installer sees it as unknown-owner and refuses update and removal, while `pi update` itself detects it and runs `bun install -g --ignore-scripts --minimum-release-age=0 <spec>`; risk: medium; evidence: https://github.com/earendil-works/pi/blob/main/packages/coding-agent/src/config.ts
- pi: add a Node 22.19 floor note: Pi requires Node.js >=22.19.0 (packages/coding-agent/package.json engines) and the entry's `requires` lists only pnpm; whether the installer enforces Node elsewhere is unverified; risk: low; evidence: https://registry.npmjs.org/@earendil-works/pi-coding-agent
- pi: when codegraph releases a `pi` target, add `pi` to `_CODEGRAPH_TARGETS` behind the capability probe only; today `installer/postinstall.py:161` correctly omits it; risk: low; evidence: https://github.com/colbymchenry/codegraph/tree/main/src/installer/targets
- drawio-desktop: bump the two macOS app pins (version and sha256) to 32.6.10 with `make verify-registry ARGS="--write"`; risk: low; evidence: GitHub digests sha256 for `draw.io-arm64-32.6.10.zip` and `draw.io-x64-32.6.10.zip` in https://github.com/jgraph/drawio-desktop/releases/download/v32.6.10/Files-SHA256-Hashes.txt

## Drift
| entry | check | status | source | disposition |
|---|---|---|---|---|
| brew | install method | drift | the registry's macOS amd64 script method (installer/registry.toml:186-195, `arch = ["amd64"]`, bin_dir `/usr/local/bin`) targets an Intel Mac, but the upstream installer aborts there: https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh lines 169-171 `abort "Homebrew on macOS is only supported on Apple Silicon processors!"`; the vendor's install page gives `/opt/homebrew` as the macOS prefix, https://docs.brew.sh/Installation; the arm64 macOS method (registry.toml:174-185) and the Linux methods (registry.toml:198-) match the upstream script (install.sh:175 and install.sh:198 prefix defaults) | proposed |
| bat | removal recipe and paths | drift | installer/registry.toml:236-244 declares no config_paths for bat, while the vendor README documents the config dir via `bat --config-dir` (https://github.com/sharkdp/bat/blob/v0.26.1/README.md, line 565); removal policy for user config cannot be applied | proposed |
| eza | install method | drift | installer/registry.toml:358-364 uses github_release on Arch and Fedora, while the vendor INSTALL.md recommends `pacman -S eza` (https://github.com/eza-community/eza/blob/v0.23.5/INSTALL.md, Arch Linux section) and `dnf install eza` (same file, Fedora section), and Arch extra and Fedora rawhide both carry 0.23.5; installer rule step 4 prefers a package manager when it is current enough (.claude/skills/tool-onboarding/SKILL.md, section 4) | proposed |
| eza | removal recipe and paths | drift | installer/registry.toml:348-368 declares no config_paths, while the vendor README places user config in `$XDG_CONFIG_HOME/eza` (https://github.com/eza-community/eza/blob/v0.23.5/README.md, line 207); the config policy cannot be applied | proposed |
| zoxide | removal recipe and paths | drift | the entry declares no config_paths (installer/registry.toml:370-396), but the README documents the frecency database at $XDG_DATA_HOME/zoxide or ~/.local/share/zoxide on Linux and ~/Library/Application Support/zoxide on macOS (https://raw.githubusercontent.com/ajeetdsouza/zoxide/main/README.md lines 404-411); the binary removal itself is ok (L2 receipt for github_release, L1 for brew) | proposed |
| lazygit | removal recipe and paths | drift | the entry declares no config_paths (installer/registry.toml:430-457), but the upstream docs put config.yml and the state files in ~/.config/lazygit on Linux and ~/Library/Application Support/lazygit on macOS (https://raw.githubusercontent.com/jesseduffield/lazygit/master/docs/Config.md lines 5-6 and 1001); the binary removal itself is ok (L2 receipt for github_release, L1 for brew) | proposed |
| gh | removal recipe and paths | drift | the entry declares config_paths ~/.config/gh only (installer/registry.toml:470), which matches the manual's config default (https://cli.github.com/manual/gh_help_environment, GH_CONFIG_DIR), but gh's state directory is $XDG_STATE_HOME/gh or ~/.local/state/gh (https://raw.githubusercontent.com/cli/go-gh/trunk/pkg/config/config.go lines 291-303) and holds state.yml, telemetry and the refresh lock (https://raw.githubusercontent.com/cli/cli/v2.104.0/internal/config/refreshable.go lines 113-117); the binary removal itself is ok (L2 receipt for github_release, L1 for brew) | proposed |
| starship | removal recipe and paths | drift | `installer/registry.toml:520` declares no `config_paths`, but the vendor reads the user config at `~/.config/starship.toml` (https://starship.rs/config/), so the Uninstall screen has no config row or default config policy as tool-onboarding 4b requires | proposed |
| oh-my-zsh | removal recipe and paths | drift | the entry declares no `paths` and no `remove` (`installer/registry.toml:599-624`), so the Uninstall screen never removes `~/.oh-my-zsh`, which `upstream tools/install.sh:92` creates and `upstream tools/install.sh:565-583` refuses to overwrite; the registry comment justifies skipping only the `~/.zshrc` rename that `upstream tools/uninstall.sh:24-27` performs, which does not cover the framework directory (step 4b: a script declares what it creates in `paths`) | proposed |
| direnv | removal recipe and paths | drift | the entry declares no `config_paths` (`installer/registry.toml:672-699`), but the vendor reads its config from `~/.config/direnv/direnv.toml` (https://direnv.net/man/direnv.toml.1.html), so the Uninstall screen has no config row or default config policy as tool-onboarding 4b requires; the binary removal itself is correct (L1 brew, L2 receipt for the release binaries) | proposed |
| gum | install method | drift | the upstream README Installation section recommends `pacman -S gum` (Arch) and `dnf install gum` (Fedora) before any release asset, https://github.com/charmbracelet/gum#installation, while `installer/registry.toml:859` installs the release asset on arch and fedora; package currency on those distros is unverified (no pacman or dnf query run); the macOS and Linux brew and checksummed asset rows match the vendor's brew line and the downloads that `verify-registry.md:154-157` passed | proposed |
| glow | install method | drift | the upstream README Installation section lists `pacman -S glow` for Arch, https://github.com/charmbracelet/glow#installation, while `installer/registry.toml:892` installs the release asset on arch; the Fedora and Debian rows use the Charm yum or apt repo in the README, which need a third-party repo and root, so the release asset stays; arch package currency is unverified (no pacman query run); the macOS and Linux asset and brew rows match the downloads `verify-registry.md:146-149` passed | proposed |
| glow | removal recipe and paths | drift | `installer/registry.toml:890` declares `config_paths = ["~/.config/glow"]` for every OS, but glow resolves its default config directory through go-app-paths (`glow` main.go:436-473, https://raw.githubusercontent.com/charmbracelet/glow/main/main.go), which on darwin uses `/Library/Preferences` under the home directory (go-app-paths v0.2.2 `paths_darwin.go:12,75`, https://raw.githubusercontent.com/muesli/go-app-paths/v0.2.2/paths_darwin.go); the macOS path is therefore `~/Library/Preferences/...`, and the app-name join beneath it is unverified; on Linux `~/.config/glow` matches `main.go:444-445` (XDG_CONFIG_HOME/glow) | proposed |
| xh | install method | drift | the upstream README install table lists `pacman -S xh` for Arch and `sudo apt install xh` for Debian and Ubuntu (https://github.com/ducaale/xh#installation), both distro packages that step 4 ranks above the release asset, while `installer/registry.toml:922` installs the release asset on debian, arch and fedora; the Fedora row is a third-party COPR repo, so the release asset stays there; package currency on Arch and Debian is unverified (no pacman or apt query run); the macOS and brew rows match the README's Homebrew line | proposed |
| xh | removal recipe and paths | drift | the entry declares no `config_paths` (`installer/registry.toml:912-938`), but `xh --session` writes session files under `config_dir()/sessions` (`src/session.rs:171-173`, https://raw.githubusercontent.com/ducaale/xh/master/src/session.rs), and `config_dir()` resolves to `~/.config/xh` on Linux and to a legacy or XDG path on macOS (`src/utils.rs:77-89`, https://raw.githubusercontent.com/ducaale/xh/master/src/utils.rs); the session format holds auth fields (`src/session.rs:410`), so the default config policy must be stated | proposed |
| difftastic | install method | drift | the upstream manual lists `sudo pacman -S difftastic` for Arch and `sudo dnf install difftastic` for Fedora before the prebuilt binary (https://difftastic.wilfred.me.uk/installation.html), while `installer/registry.toml:949` installs the release asset on arch and fedora; package currency is unverified (no pacman or dnf query run); the macOS and Linux asset rows match the brew line and the downloads that `verify-registry.md:96-99` passed | proposed |
| gitui | install method | drift | the upstream README install list recommends `sudo pacman -S gitui` for Arch and `sudo dnf install gitui` for Fedora (https://github.com/gitui-org/gitui#installation), while `installer/registry.toml:979` installs the release asset on arch and fedora; package currency is unverified (no pacman or dnf query run); the Linux and macOS asset rows match the downloads that `verify-registry.md:142-145` passed, and the brew row matches the README's Homebrew line | proposed |
| gitui | removal recipe and paths | drift | the entry declares no `config_paths` (`installer/registry.toml:968-1000`), but the upstream KEY_CONFIG and THEMES pages place user-authored `key_bindings.ron` and `theme.ron` in `~/.config/gitui` on macOS and Linux (https://raw.githubusercontent.com/gitui-org/gitui/master/KEY_CONFIG.md, https://raw.githubusercontent.com/gitui-org/gitui/master/THEMES.md), and the README's diagnostics section writes `gitui.log` under `~/Library/Caches/gitui` (macOS) or `~/.cache/gitui` (Linux) when run with `-l` (https://github.com/gitui-org/gitui#diagnostics); the default config policy is therefore unstated | proposed |
| lazydocker | removal recipe and paths | drift | the entry declares no `config_paths`, but the vendor documents the user config at `~/.config/lazydocker/config.yml` (Linux) and `~/Library/Application Support/jesseduffield/lazydocker/config.yml` (macOS), https://raw.githubusercontent.com/jesseduffield/lazydocker/master/docs/Config.md (lines 11-12); `installer/registry.toml:1004-1005` shows the block without it | proposed |
| lazydocker | postinstall hook | drift | lazydocker is a UI over a running docker environment (README line 43) and the entry carries neither a `requires` edge nor a `# Verified` note for that runtime expectation, which tool-onboarding step 6 requires (`installer/registry.toml:1004-1033`) | proposed |
| docker | install method | drift | Docker's Ubuntu install page lists `docker.io` among the "unofficial packages to uninstall" before installing the official Engine, and its recommended method is the Docker apt repository, https://docs.docker.com/engine/install/ubuntu/ ("Uninstall old versions", "Installation methods"); the entry's apt method is `docker.io` at `installer/registry.toml:1074-1075` | proposed |
| docker | update argv | drift | the upgrade path on that page is the Docker apt repository ("Upgrade Docker Engine"), not the `docker.io` package the entry re-runs, https://docs.docker.com/engine/install/ubuntu/ | proposed |
| docker | removal recipe and paths | drift | Docker's Ubuntu uninstall section says images, containers, volumes and networks in /var/lib/docker/ are not removed automatically, https://docs.docker.com/engine/install/ubuntu/ ("Uninstall Docker Engine"); the entry declares no paths, and the client config `~/.docker/config.json` is not declared either (docker/cli `cli/config/config.go:27-28`) | proposed |
| docker | postinstall hook | drift | the Homebrew formula's Linux caveat says the daemon is a separate formula, `brew install docker-engine` (homebrew-core Formula/d/docker.rb, caveats), and the entry's CLI is not a daemon; the entry has no `requires` edge and no `# Verified` note for that runtime expectation, which tool-onboarding step 6 requires (`installer/registry.toml:1059-1081`) | proposed |
| podman | install method | drift | the vendor's install page says the Homebrew route is "Not recommended" because it is community-maintained, and points macOS users to the GitHub release pkg installer, https://podman.io/docs/installation ("Installing on Mac & Windows"); the entry's macOS arm64 method is brew (`installer/registry.toml:1105-1107`) and it has no pkg or release method for macOS. The Linux rows follow the page's per-distro package commands ("Installing on Linux") | proposed |
| podman | update argv | drift | for macOS the same page's recommended route is the pkg installer, so re-running the brew method is the path the vendor does not recommend (https://podman.io/docs/installation); the Linux package-manager upgrade is unchanged | proposed |
| podman | postinstall hook | drift | the vendor page's macOS setup creates a machine with `podman machine init` and `podman machine start` (https://podman.io/docs/installation, "Installing on Mac & Windows"); the entry declares no postinstall, `requires`, or `# Verified` note for that runtime expectation, which tool-onboarding step 6 requires (`installer/registry.toml:1084-1111`) | proposed |
| colima | removal recipe and paths | drift | the vendor keeps its config and VM data under `$HOME/.colima` (https://github.com/abiosoft/colima docs/FAQ.md lines 124-137) and `colima delete --data` is the vendor's data removal (FAQ.md line 695); the entry declares no `config_paths`, so the Uninstall screen cannot show or offer those paths (`installer/registry.toml:1115-1127`) | proposed |
| dive | removal recipe and paths | drift | the upstream README (Configuration, https://github.com/wagoodman/dive/blob/v0.13.1/README.md) says dive reads `$XDG_CONFIG_HOME/dive/*.yaml`, `$XDG_CONFIG_DIRS/dive/*.yaml`, `~/.config/dive/*.yaml` and `~/.dive.yaml`, while the entry declares no `config_paths`; container check not run (the batch forbids containers), the drift is from the upstream text | proposed |
| duf | install method | drift | upstream README (https://github.com/muesli/duf (README), Installation) names `dnf install duf` for Fedora, and the host's Fedora package is already duf-0.9.1 (`rpm -qf /usr/bin/duf`), current with latest; step 4 rule 1 prefers that package manager, yet `installer/registry.toml:1209-1210` declares a github_release tarball for fedora and no dnf method | proposed |
| miller | removal recipe and paths | drift | upstream docs/src/customization.md (https://github.com/johnkerl/miller/blob/main/docs/src/customization.md, "Where to put your .mlrrc") names `$HOME/.mlrrc`, `$XDG_CONFIG_HOME/miller/mlrrc` (default `$HOME/.config/miller/mlrrc`) and `./.mlrrc`, while the entry declares no `config_paths`; container check not run (the batch forbids containers), the drift is from the upstream text | proposed |
| tealdeer | removal recipe and paths | drift | config_paths lists only cache directories (installer/registry.toml:1327); upstream resolves the config dir to the XDG path on Linux and macOS (https://api.github.com/repos/tealdeer-rs/tealdeer/contents/src/config.rs?ref=v1.9.1 lines 874-881, with the XDG preference at lines 60-72) and the config file is config.toml (same file line 25), so ~/.config/tealdeer is missing from the entry | proposed |
| fx | removal recipe and paths | drift | upstream 40.0.1 reads user config from ~/.fxrc.js and $XDG_CONFIG_HOME/fx/.fxrc.js, defaulting to ~/.config/fx/.fxrc.js (https://api.github.com/repos/antonmedv/fx/contents/internal/engine/fxrc.go?ref=40.0.1 lines 21-31), but the entry declares no config_paths (installer/registry.toml:1349-1374) | proposed |
| dasel | removal recipe and paths | drift | dasel reads a user config file at the default path ~/dasel.yaml (https://api.github.com/repos/TomWright/dasel/contents/internal/cli/query.go?ref=v3.11.2 line 17, and https://api.github.com/repos/TomWright/dasel/contents/internal/cli/interactive.go?ref=v3.11.2 line 32), loaded read-only by LoadConfig (https://api.github.com/repos/TomWright/dasel/contents/internal/cli/config.go?ref=v3.11.2 lines 26-57), but the entry declares no config_paths (installer/registry.toml:1377-1402) | proposed |
| gron | install method | drift | the github_release assets carry no checksum file and no GitHub digest (0 of 11 assets, https://api.github.com/repos/tomnomnom/gron/releases/latest), and verify-registry.md:8-9 lists them as unverified at install; the brew formula serves the same 0.7.1 with a sha256 (https://formulae.brew.sh/api/formula/gron.json) and is declared for all OS and arch (installer/registry.toml:1428-1430); the installer's step 4 ranks a package manager ahead of an unchecksummed asset (.claude/skills/tool-onboarding/SKILL.md:77) | proposed |
| codex | update argv | drift | `installer/registry.toml:1493` says the docs name no `codex update`, but https://developers.openai.com/codex/cli/reference lists `codex update` (Stable, applies an update when the release supports self-update) and the CLI source has an `Update` subcommand, https://github.com/openai/codex/blob/main/codex-rs/cli/src/main.rs | proposed |
| opencode | install method | drift | `installer/registry.toml:1575` still installs through https://opencode.ai/install, which says "This installer only installs OpenCode 1" and refuses 2.x (https://opencode.ai/install lines 70-75); the v2 installer is https://opencode.ai/v2/install; the brew method `installer/registry.toml:1586` is the tap formula that serves 1.19.5 (https://github.com/anomalyco/homebrew-tap/blob/main/opencode.rb) while homebrew/core opencode serves 2.3.0 and has no conflicts (https://formulae.brew.sh/api/formula/opencode.json); pacman serves 2.2.7 and stays valid | proposed |
| opencode | update argv | drift | `installer/registry.toml:1580` runs `opencode upgrade`, which without `--major` stays on OpenCode 1 (https://github.com/anomalyco/opencode/blob/v1.19.5/packages/opencode/src/cli/cmd/upgrade.ts lines 22, 79, 102); re-running the v2 installer is the 2.x route; not run in a container here, the orchestrator owns containers | proposed |
| opencode | removal recipe and paths | drift | `installer/registry.toml:1579` declares only `~/.opencode/bin/opencode`, but the v2 installer also writes `~/.opencode/bin/opencode2` (https://opencode.ai/v2/install lines 345-374) and that file exists on this host; no `remove` recipe, so a 2.x install leaves the opencode2 shim and a running `opencode serve --service` behind | proposed |
| opencode | tuning keys | drift | `installer/agent_settings.py:679` writes `("opencode", "auto-approve")` to the key path `permission`, which the schema marks `deprecated: true` while `permissions` takes a rule array with `action`, `resource` and `effect` (https://opencode.ai/config.json) | proposed |
| opencode | script | drift | installer/agent_settings.py:679: `permission` deprecated in the opencode schema | proposed |
| cursor-agent | script | drift | installer/cursor_shim.py:65: `exec "$target" ` shim exec line rewrites argv: exec "$target" {…}"$@" | proposed |
| codegraph | removal recipe and paths | drift | `installer/registry.toml:1756` declares no tool-level `config_paths` although codegraph keeps its data in ~/.codegraph (telemetry.json, beta-signup.json, daemons/, and versions/ plus current after `codegraph upgrade`, https://raw.githubusercontent.com/colbymchenry/codegraph/main/install.sh lines 21 and 79-87); the unregister hook runs `codegraph uninstall --keep-cli` (`installer/postinstall.py:204`) and the receipt proves only the installer's own link and opt dir, so after a vendor self-upgrade `installer/uninstall.py:402` finds no proven executable and unregisters nothing | proposed |
| codegraph | postinstall hook | drift | `installer/postinstall.py:161` `_CODEGRAPH_TARGETS` maps claude, codex, opencode and cursor only; codegraph v1.6.2 also supports `copilot-cli` (`codegraph install --print-config copilot-cli` exits 0 and shows ~/.copilot/mcp-config.json), and the installer already knows the copilot and pi hosts (`installer/postinstall.py:46`); Pi is only on codegraph main and unreleased (`codegraph install --print-config pi` exits 1 with Unknown target "pi", Known: claude, cursor, codex, opencode, hermes, gemini, antigravity, kiro, copilot-vscode, copilot-cli, copilot-jetbrains), so a Pi mapping needs a capability gate first | proposed |
| codegraph | script | drift | .claude/architecture.md:355: doc names `present_agent_hosts`, which does not exist; the code has present_hosts() and present_harnesses (installer/postinstall.py:84,95) | proposed |
| codegraph | script | drift | .claude/architecture.md:623: doc names `present_agent_hosts`, which does not exist; the code has present_hosts() and present_harnesses (installer/postinstall.py:84,95) | proposed |
| codegraph | script | drift | .claude/skills/tool-onboarding/SKILL.md:176: doc names `present_agent_hosts`, which does not exist; the code has present_hosts() and present_harnesses (installer/postinstall.py:84,95) | proposed |
| graphify | removal recipe and paths | drift | installer/registry.toml:1827-1828 says every host install is project/CWD-scoped, but the README says a bare `graphify install` registers the skill in the user profile (https://pypi.org/project/graphifyy/, lines 205-213); graphifyy 0.9.108 graphify/install.py:1106-1108 writes ~/.claude/skills/graphify/SKILL.md and registers it in ~/.claude/CLAUDE.md. The entry declares `paths` none, so removal (uv tool uninstall) leaves those files | proposed |
| zip | script | drift | installer/versions.py:211: `zip --version` prints the copyright line "1990-2008" first; extract_observed_version (installer/versions.py:211) reads those years, not "Zip 3.0" on line 2 | proposed |
| sdkman | removal recipe and paths | drift | the script method declares no `paths` and no `remove` (registry.toml:1970-1983, comment at 1980-1982), but `.claude/skills/tool-onboarding/SKILL.md:109` requires `paths` for a `script` method; the vendor uninstall is `rm -rf ~/.sdkman` plus removing the shell init snippet by hand, https://sdkman.io/install (Uninstallation); container check not run in this batch | proposed |
| java | removal recipe and paths | drift | the candidate is removed by the manager (`sdk uninstall java <version>`, the form shown at https://sdkman.io/usage in its uninstall example), and `.claude/skills/tool-onboarding/SKILL.md:106` says sdkman removal derives from the manager (L1); but MANAGER_UNINSTALL_ARGV has no `sdkman` key (installer/uninstall.py:111-117), so `_manager_argv` returns nothing for this kind (installer/uninstall.py:332-333); container check not run in this batch | proposed |
| groovy | removal recipe and paths | drift | the candidate is removed by the manager (`sdk uninstall groovy <version>`, the form shown at https://sdkman.io/usage), and `.claude/skills/tool-onboarding/SKILL.md:106` says sdkman removal derives from the manager (L1); but MANAGER_UNINSTALL_ARGV has no `sdkman` key (installer/uninstall.py:111-117), so `_manager_argv` returns nothing for this kind (installer/uninstall.py:332-333); container check not run in this batch | proposed |
| springbootcli | removal recipe and paths | drift | the candidate is removed by the manager (`sdk uninstall springboot <version>`, the form shown at https://sdkman.io/usage), and `.claude/skills/tool-onboarding/SKILL.md:106` says sdkman removal derives from the manager (L1); but MANAGER_UNINSTALL_ARGV has no `sdkman` key (installer/uninstall.py:111-117), so `_manager_argv` returns nothing for this kind (installer/uninstall.py:332-333); the vendor docs name no uninstall of their own (unverified); container check not run in this batch | proposed |
| gradle | removal recipe and paths | drift | the candidate is removed by the manager (`sdk uninstall gradle <version>`, the form shown at https://sdkman.io/usage), and `.claude/skills/tool-onboarding/SKILL.md:106` says sdkman removal derives from the manager (L1); but MANAGER_UNINSTALL_ARGV has no `sdkman` key (installer/uninstall.py:111-117), so `_manager_argv` returns nothing for this kind (installer/uninstall.py:332-333); container check not run in this batch | proposed |
| bun | removal recipe and paths | drift | the script appends a `# bun` PATH/BUN_INSTALL block to the user's shell config (`>>"$zsh_config"` at https://bun.sh/install:246; `>>"$bash_config"` at https://bun.sh/install:293, bash configs listed at lines 269-278), but `paths` declares only `~/.bun/bin/bun` and `~/.bun/bin/bunx` (`installer/registry.toml:2196`) and the `# Verified` comment (`installer/registry.toml:2191-2195`) does not record the rc edit, which the installer's rule requires for anything else a script creates; the vendor's own removal (https://bun.sh/docs/installation, "Uninstall") is `rm -rf ~/.bun`, which the entry deliberately does not run (its comment at `installer/registry.toml:2192` keeps the tree out of `paths`) | proposed |
| volta | install method | drift | the vendor README (https://raw.githubusercontent.com/volta-cli/volta/main/README.md line 21) no longer recommends Volta for new installs and names mise instead; the entry still installs Volta through https://get.volta.sh and the brew formula (installer/registry.toml:2263-2294), so the mechanics still work but the method is not the vendor's recommendation | proposed |
| vale | install method | drift | the registry names errata-ai/vale (installer/registry.toml:2389 and :2397), but https://api.github.com/repos/errata-ai/vale reports full_name vale-cli/vale and https://formulae.brew.sh/api/formula/vale.json points at github.com/vale-cli/vale; the downloads still resolve (.planning/audits/catalog/2026-11-13/verify-registry.md:226-229, Passed), so this is a slug drift, not a broken download; whether the redirect stays is unverified | proposed |
| vale | removal recipe and paths | drift | the entry records no config_paths or data paths (installer/registry.toml:2377-2385), which tool-onboarding step 4b requires per tool (.claude/skills/tool-onboarding/SKILL.md, section 4b); v3.27.0 `vale sync` downloads models and grammars at runtime (https://github.com/vale-cli/vale/releases/tag/v3.27.0), and where they land is unverified here, so the removal recipe cannot account for them; the receipt of the release binary's paths is covered by verify-registry.md:226-229 | proposed |
| broot | removal recipe and paths | drift | the registry declares no config_paths (registry.toml:2407); upstream prefers the per-user config directory ~/.config/broot (https://github.com/Canop/broot/blob/main/src/conf/mod.rs#L60-L61, main branch, not the v1.62.0 tag) | proposed |
| vscode | removal recipe and paths | drift | installer/agent_env.py:81 writes the agent settings to vscode_user / settings.json, whose directory is set at installer/agent_env.py:36-39 (~/.config/Code/User on Linux, ~/Library/Application Support/Code/User on macOS), but the entry declares no config_paths (registry.toml:2438-2503) | proposed |
| mmdc | install method | drift | installer/registry.toml:2765 sets min_node = "22.12.0" on the node method, but the npm manifest of @mermaid-js/mermaid-cli 12.2.0 declares engines node >=22.13.0 (https://registry.npmjs.org/@mermaid-js/mermaid-cli/12.2.0); the preflight at installer/executors.py:513-519 enforces the lower floor, so Node 22.12.x passes it | proposed |
| puppeteer | install method | drift | installer/registry.toml:2815-2819 says @puppeteer/browsers still maps LINUX_ARM to linux64, which is why linux arm64 is gated off; @puppeteer/browsers 3.2.7 maps LINUX_ARM to linux-arm64 for Chrome builds from 153.0.8001.0 on (https://registry.npmjs.org/@puppeteer/browsers/-/browsers-3.2.7.tgz, package/lib/browser-data/chrome.js:13-17), and 25.17.0 ships Chrome 157; whether a linux-arm64 Chrome archive is published is unverified here. The macos node method has no gap found | proposed |
| kitty | removal recipe and paths | drift | the Linux script method is ok: paths ~/.local/kitty.app/ (installer/registry.toml:2961) matches the vendor's "simply delete that directory" (https://sw.kovidgoyal.net/kitty/binary/). The macOS script method declares no paths (installer/registry.toml:2971) because the schema refuses absolute paths (installer/model.py:577-585), so the installer has no removal for /Applications/kitty.app that the vendor's own uninstall covers. This is a schema gap to record in the backlog, not an entry fix | proposed |
| wezterm | removal recipe and paths | drift | the AppImage receipt (installer/registry.toml:3040-3048) and pacman and cask removals are fine, but the entry declares no config_paths (installer/registry.toml:3027-3054). The installer's terminal-shell synchronizer writes the owned region of the wezterm config at $XDG_CONFIG_HOME/wezterm/wezterm.lua or ~/.wezterm.lua (installer/terminal_shell.py:163-170 and :967-972), and config_targets reads only config_paths (installer/uninstall.py:119-121), so removal never lists that file. The vendor documents the same paths (https://wezterm.org/config/files.html) | proposed |
| glab | install method | drift | the Debian apt package is 1.53.0-1 (https://sources.debian.org/api/src/glab/) while the latest is 1.130.0; the vendor's officially supported Linux method is Homebrew and it lists WakeMeOps for Debian and Ubuntu, not the distro package (https://gitlab.com/gitlab-org/cli/-/raw/main/docs/installation_options.md, Linux section); brew and pacman serve 1.130.0; Fedora stable is unverified | proposed |
| glab | removal recipe and paths | drift | the manager's own remove (L1) is right, but installer/registry.toml:3169-3190 declares no config_paths while glab writes its config to ~/.config/glab-cli/config.yml on Linux and ~/Library/Application Support/glab-cli/config.yml on macOS, and stores plaintext credentials there when no keyring is used (https://gitlab.com/gitlab-org/cli/-/raw/main/docs/source/configuration.md, Configuration file locations; https://gitlab.com/gitlab-org/cli/-/raw/main/docs/source/authentication.md, Credential storage); the default config policy is not recorded (tool-onboarding step 4b) | proposed |
| pi | install method | drift | `installer/registry.toml:3201` and `installer/registry.toml:3204` describe a pnpm host-setup handoff verified against "latest 1.5.0" and an "interactive" setup, while the vendor README now recommends `curl -fsSL https://pi.dev/install.sh \\| sh` (managed install, pinned dependencies, `pi update`) or `npm install -g --ignore-scripts`, and npm latest is 1.5.2, https://github.com/earendil-works/pi#getting-started | proposed |
| pi | removal recipe and paths | drift | `installer/registry.toml:3194` to `installer/registry.toml:3210` declare no `config_paths` for `~/.pi` (agent settings, `auth.json`, `sessions`, `mcp.json` live there, https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/mcp.md) and no remove recipe, and the host_setup row of tool-onboarding step 4b asks for an explicit recipe; removal on this host (bun global) is also not derivable because `installer/ownership.py:135` maps only `pnpm` | proposed |
| drawio-desktop | install method | drift | the macOS app methods pin 32.6.1 (`installer/registry.toml:3250`, `installer/registry.toml:3260`) while v32.6.10 is the stable release, `.planning/audits/catalog/2026-11-13/verify-registry.md:5` and `.planning/audits/catalog/2026-11-13/verify-registry.md:6`, https://api.github.com/repos/jgraph/drawio-desktop/releases/latest; Linux AppImage methods are ok: `drawio-x86_64-32.6.10.AppImage` and `drawio-arm64-32.6.10.AppImage` exist with the same names and a listed digest, https://github.com/jgraph/drawio-desktop/releases/download/v32.6.10/Files-SHA256-Hashes.txt, and are recorded in `.planning/audits/catalog/2026-11-13/verify-registry.md:110` and `.planning/audits/catalog/2026-11-13/verify-registry.md:111` | proposed |
| (installer) | script | drift | installer/guards.py:218: `exec ` shim exec line rewrites argv: exec {…} {…} "$@" | proposed |
| (installer) | script | drift | installer/guards.py:260: `exec ` shim exec line rewrites argv: exec {…} "$@" | proposed |
| (installer) | script | drift | installer/guards.py:333: `exec ` shim exec line rewrites argv: exec {…} install "$@" | proposed |

## Entries
### uv
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### rg
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | n/a | n/a | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### jq
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | n/a | n/a | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### brew
| check | status | report | findings |
|---|---|---|---|
| install method | drift | drift | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### fd
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | n/a | n/a | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### bat
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | drift | drift | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### sd
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### git
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### delta
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### eza
| check | status | report | findings |
|---|---|---|---|
| install method | drift | drift | - |
| update argv | ok | ok | - |
| removal recipe and paths | drift | drift | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### zoxide
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | drift | drift | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | n/a | n/a | - |
### fzf
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | n/a | n/a | - |
### lazygit
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | drift | drift | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | n/a | n/a | - |
### gh
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | drift | drift | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | n/a | n/a | - |
### yq
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | n/a | n/a | - |
### starship
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | drift | drift | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### zsh
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### oh-my-zsh
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | drift | drift | - |
| tuning keys | ok | ok | - |
| postinstall hook | ok | ok | - |
### gnu-bash
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### direnv
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | drift | drift | - |
| tuning keys | ok | ok | - |
| postinstall hook | ok | ok | - |
### just
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### ruff
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### dust
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### hyperfine
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### bottom
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### gum
| check | status | report | findings |
|---|---|---|---|
| install method | drift | drift | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### glow
| check | status | report | findings |
|---|---|---|---|
| install method | drift | drift | - |
| update argv | ok | ok | - |
| removal recipe and paths | drift | drift | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### xh
| check | status | report | findings |
|---|---|---|---|
| install method | drift | drift | - |
| update argv | ok | ok | - |
| removal recipe and paths | drift | drift | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### difftastic
| check | status | report | findings |
|---|---|---|---|
| install method | drift | drift | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### gitui
| check | status | report | findings |
|---|---|---|---|
| install method | drift | drift | - |
| update argv | ok | ok | - |
| removal recipe and paths | drift | drift | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### lazydocker
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | drift | drift | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | drift | drift | - |
### watch
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### docker
| check | status | report | findings |
|---|---|---|---|
| install method | drift | drift | - |
| update argv | drift | drift | - |
| removal recipe and paths | drift | drift | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | drift | drift | - |
### podman
| check | status | report | findings |
|---|---|---|---|
| install method | drift | drift | - |
| update argv | drift | drift | - |
| removal recipe and paths | unknown | unknown | unknown (reason: container check not run (Linux methods are sudo handoffs the harness never runs; macOS brew not runnable in a Linux container)) |
| tuning keys | n/a | n/a | - |
| postinstall hook | drift | drift | - |
### colima
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | drift | drift | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### container
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | unknown | unknown | unknown (reason: container check not run (macOS-only entry, no Linux container can run it)) |
| tuning keys | n/a | n/a | - |
| postinstall hook | unknown | unknown | unknown (reason: container check not run (macOS-only entry, no Linux container can run it)) |
### dive
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | drift | drift | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### duf
| check | status | report | findings |
|---|---|---|---|
| install method | drift | drift | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | unknown | ok (container: .planning/audits/catalog/2026-11-13/containers/fedora-pass2-transcript.log) |
| tuning keys | n/a | n/a | - |
| postinstall hook | unknown | unknown | unknown (reason: container check not run (the harness does not exercise this postinstall expectation)) |
### hexyl
| check | status | report | findings |
|---|---|---|---|
| install method | unknown | unknown | unknown (reason: container check not run for package currency (the install itself passed: container .planning/audits/catalog/2026-11-13/containers/fedora-pass1-transcript.log)) |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### miller
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | drift | drift | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### shfmt
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | n/a | n/a | - |
### tealdeer
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | drift | drift | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### fx
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | drift | drift | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | n/a | n/a | - |
### dasel
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | drift | drift | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | n/a | n/a | - |
### gron
| check | status | report | findings |
|---|---|---|---|
| install method | drift | drift | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | n/a | n/a | - |
### aichat
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | n/a | n/a | - |
### codex
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | drift | drift | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | ok | ok | - |
| postinstall hook | ok | ok | - |
### claude
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | ok | ok | - |
| postinstall hook | ok | ok | - |
### opencode
| check | status | report | findings |
|---|---|---|---|
| install method | drift | drift | - |
| update argv | drift | drift | - |
| removal recipe and paths | drift | drift | - |
| tuning keys | drift | drift | - |
| postinstall hook | n/a | n/a | - |
### cursor-agent
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | ok | ok | - |
| postinstall hook | ok | ok | - |
### copilot
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | ok | ok | - |
| postinstall hook | ok | ok | - |
### antigravity
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | unknown | ok (container: .planning/audits/catalog/2026-11-13/containers/fedora-pass2-transcript.log) |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### codegraph
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | drift | drift | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | drift | drift | - |
### graphify
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | drift | drift | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### deno
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### unzip
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### zip
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### sdkman
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | unknown | unknown | unknown (reason: container check not run (the harness rerun reports already current; an update needs a newer upstream than the install)) |
| removal recipe and paths | drift | drift | - |
| tuning keys | ok | ok | - |
| postinstall hook | ok | ok | - |
### java
| check | status | report | findings |
|---|---|---|---|
| install method | unknown | unknown | unknown (reason: container check not run for package currency (the install itself passed: container .planning/audits/catalog/2026-11-13/containers/fedora-pass1-transcript.log)) |
| update argv | ok | ok | - |
| removal recipe and paths | drift | drift | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### groovy
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | drift | drift | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### springbootcli
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | drift | drift | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### gradle
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | drift | drift | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### maven
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | unknown | unknown | unknown (reason: container check not run (the harness rerun reports already current; an update needs a newer upstream than the install)) |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | n/a | n/a | - |
### procs
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | unknown | unknown | unknown (reason: container check not run (the harness rerun reports already current; an update needs a newer upstream than the install)) |
| removal recipe and paths | ok | unknown | ok (container: .planning/audits/catalog/2026-11-13/containers/fedora-pass2-transcript.log) |
| tuning keys | n/a | n/a | - |
| postinstall hook | n/a | n/a | - |
### ast-grep
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | unknown | unknown | unknown (reason: container check not run (the harness rerun reports already current; an update needs a newer upstream than the install)) |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | n/a | n/a | - |
### jless
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | unknown | unknown | unknown (reason: container check not run (the harness rerun reports already current; an update needs a newer upstream than the install)) |
| removal recipe and paths | ok | unknown | ok (container: .planning/audits/catalog/2026-11-13/containers/fedora-pass2-transcript.log) |
| tuning keys | n/a | n/a | - |
| postinstall hook | n/a | n/a | - |
### bun
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | drift | drift | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | n/a | n/a | - |
### pnpm
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### volta
| check | status | report | findings |
|---|---|---|---|
| install method | drift | drift | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### fnm
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### gitleaks
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### vale
| check | status | report | findings |
|---|---|---|---|
| install method | drift | drift | - |
| update argv | ok | ok | - |
| removal recipe and paths | drift | drift | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### broot
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | drift | drift | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### vscode
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | unknown | unknown | unknown (reason: container check not run (the harness rerun reports already current; an update needs a newer upstream than the install)) |
| removal recipe and paths | drift | drift | - |
| tuning keys | ok | ok | - |
| postinstall hook | ok | ok | - |
### jetbrains-toolbox
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | unknown | unknown | unknown (reason: container check not run (the harness rerun reports already current; an update needs a newer upstream than the install)) |
| removal recipe and paths | ok | unknown | ok (container: .planning/audits/catalog/2026-11-13/containers/fedora-pass2-transcript.log) |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### sublime
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | unknown | unknown | unknown (reason: container check not run (the harness rerun reports already current; an update needs a newer upstream than the install)) |
| removal recipe and paths | ok | unknown | ok (container: .planning/audits/catalog/2026-11-13/containers/fedora-pass2-transcript.log) |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### neovim
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### mmdc
| check | status | report | findings |
|---|---|---|---|
| install method | drift | drift | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### puppeteer
| check | status | report | findings |
|---|---|---|---|
| install method | drift | drift | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | ok | ok | - |
### kitty
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | drift | drift | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | n/a | n/a | - |
### wezterm
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | drift | drift | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | n/a | n/a | - |
### alacritty
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | ok | ok | - |
| postinstall hook | ok | ok | - |
### herdr
| check | status | report | findings |
|---|---|---|---|
| install method | ok | ok | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | ok | ok | - |
| postinstall hook | ok | ok | - |
### glab
| check | status | report | findings |
|---|---|---|---|
| install method | drift | drift | - |
| update argv | ok | ok | - |
| removal recipe and paths | drift | drift | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | n/a | n/a | - |
### pi
| check | status | report | findings |
|---|---|---|---|
| install method | drift | drift | - |
| update argv | ok | ok | - |
| removal recipe and paths | drift | drift | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | n/a | n/a | - |
### drawio-desktop
| check | status | report | findings |
|---|---|---|---|
| install method | drift | drift | - |
| update argv | ok | ok | - |
| removal recipe and paths | ok | ok | - |
| tuning keys | n/a | n/a | - |
| postinstall hook | n/a | n/a | - |

## verify-registry
exit: 1
- `drawio-desktop` `https://github.com/jgraph/drawio-desktop/releases/download/v32.6.1/draw.io-arm64-32.6.1.zip` — `newer stable release v32.6.10 (pinned 32.6.1)` ()
- `drawio-desktop` `https://github.com/jgraph/drawio-desktop/releases/download/v32.6.1/draw.io-x64-32.6.1.zip` — `newer stable release v32.6.10 (pinned 32.6.1)` ()

## Script scan
- installer/env_redirect.py (installer): ok
- installer/post_install.py (installer): ok
- installer/postinstall.py (installer): ok
- scripts/container-e2e-verify.sh (maintainer): ok
- scripts/detect-container-runtime.sh (maintainer): ok
- scripts/lib/prune-tmp-common.sh (maintainer): ok
- scripts/prune-tmp-linux.sh (maintainer): ok
- scripts/prune-user-tmpdir.sh (maintainer): ok

## Script findings
| location | entry | status | pattern | state | disposition |
|---|---|---|---|---|---|
| .claude/architecture.md:355 | codegraph | drift | doc names `present_agent_hosts`, which does not exist; the code has present_hosts() and present_harnesses (installer/postinstall.py:84,95) | current | proposed |
| .claude/architecture.md:623 | codegraph | drift | doc names `present_agent_hosts`, which does not exist; the code has present_hosts() and present_harnesses (installer/postinstall.py:84,95) | current | proposed |
| .claude/skills/tool-onboarding/SKILL.md:106 | gradle | drift | the candidate is removed by the manager (`sdk uninstall gradle <version>`, the form shown at https://sdkman.io/usage), and `.claude/skills/tool-onboarding/SKILL.md:106` says sdkman removal derives from the manager (L1); but MANAGER_UNINSTALL_ARGV has no `sdkman` key (installer/uninstall.py:111-117), so `_manager_argv` returns nothing for this kind (installer/uninstall.py:332-333); container check not run in this batch | stale | proposed |
| .claude/skills/tool-onboarding/SKILL.md:106 | groovy | drift | the candidate is removed by the manager (`sdk uninstall groovy <version>`, the form shown at https://sdkman.io/usage), and `.claude/skills/tool-onboarding/SKILL.md:106` says sdkman removal derives from the manager (L1); but MANAGER_UNINSTALL_ARGV has no `sdkman` key (installer/uninstall.py:111-117), so `_manager_argv` returns nothing for this kind (installer/uninstall.py:332-333); container check not run in this batch | stale | proposed |
| .claude/skills/tool-onboarding/SKILL.md:106 | java | drift | the candidate is removed by the manager (`sdk uninstall java <version>`, the form shown at https://sdkman.io/usage in its uninstall example), and `.claude/skills/tool-onboarding/SKILL.md:106` says sdkman removal derives from the manager (L1); but MANAGER_UNINSTALL_ARGV has no `sdkman` key (installer/uninstall.py:111-117), so `_manager_argv` returns nothing for this kind (installer/uninstall.py:332-333); container check not run in this batch | stale | proposed |
| .claude/skills/tool-onboarding/SKILL.md:106 | springbootcli | drift | the candidate is removed by the manager (`sdk uninstall springboot <version>`, the form shown at https://sdkman.io/usage), and `.claude/skills/tool-onboarding/SKILL.md:106` says sdkman removal derives from the manager (L1); but MANAGER_UNINSTALL_ARGV has no `sdkman` key (installer/uninstall.py:111-117), so `_manager_argv` returns nothing for this kind (installer/uninstall.py:332-333); the vendor docs name no uninstall of their own (unverified); container check not run in this batch | stale | proposed |
| .claude/skills/tool-onboarding/SKILL.md:109 | sdkman | drift | the script method declares no `paths` and no `remove` (registry.toml:1970-1983, comment at 1980-1982), but `.claude/skills/tool-onboarding/SKILL.md:109` requires `paths` for a `script` method; the vendor uninstall is `rm -rf ~/.sdkman` plus removing the shell init snippet by hand, https://sdkman.io/install (Uninstallation); container check not run in this batch | current | proposed |
| .claude/skills/tool-onboarding/SKILL.md:176 | codegraph | drift | doc names `present_agent_hosts`, which does not exist; the code has present_hosts() and present_harnesses (installer/postinstall.py:84,95) | current | proposed |
| installer/agent_settings.py:679 | opencode | drift | `installer/agent_settings.py:679` writes `("opencode", "auto-approve")` to the key path `permission`, which the schema marks `deprecated: true` while `permissions` takes a rule array with `action`, `resource` and `effect` (https://opencode.ai/config.json) | stale | proposed |
| installer/agent_settings.py:679 | opencode | drift | `permission` deprecated in the opencode schema | current | proposed |
| installer/cursor_shim.py:65 | cursor-agent | drift | `exec "$target" ` shim exec line rewrites argv: exec "$target" {…}"$@" | current | proposed |
| installer/guards.py:218 | (installer) | drift | `exec ` shim exec line rewrites argv: exec {…} {…} "$@" | current | proposed |
| installer/guards.py:260 | (installer) | drift | `exec ` shim exec line rewrites argv: exec {…} "$@" | current | proposed |
| installer/guards.py:333 | (installer) | drift | `exec ` shim exec line rewrites argv: exec {…} install "$@" | current | proposed |
| installer/postinstall.py:161 | codegraph | drift | `installer/postinstall.py:161` `_CODEGRAPH_TARGETS` maps claude, codex, opencode and cursor only; codegraph v1.6.2 also supports `copilot-cli` (`codegraph install --print-config copilot-cli` exits 0 and shows ~/.copilot/mcp-config.json), and the installer already knows the copilot and pi hosts (`installer/postinstall.py:46`); Pi is only on codegraph main and unreleased (`codegraph install --print-config pi` exits 1 with Unknown target "pi", Known: claude, cursor, codex, opencode, hermes, gemini, antigravity, kiro, copilot-vscode, copilot-cli, copilot-jetbrains), so a Pi mapping needs a capability gate first | stale | proposed |
| installer/registry.toml:186 | brew | drift | the registry's macOS amd64 script method (installer/registry.toml:186-195, `arch = ["amd64"]`, bin_dir `/usr/local/bin`) targets an Intel Mac, but the upstream installer aborts there: https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh lines 169-171 `abort "Homebrew on macOS is only supported on Apple Silicon processors!"`; the vendor's install page gives `/opt/homebrew` as the macOS prefix, https://docs.brew.sh/Installation; the arm64 macOS method (registry.toml:174-185) and the Linux methods (registry.toml:198-) match the upstream script (install.sh:175 and install.sh:198 prefix defaults) | stale | proposed |
| installer/registry.toml:236 | bat | drift | installer/registry.toml:236-244 declares no config_paths for bat, while the vendor README documents the config dir via `bat --config-dir` (https://github.com/sharkdp/bat/blob/v0.26.1/README.md, line 565); removal policy for user config cannot be applied | stale | proposed |
| installer/registry.toml:348 | eza | drift | installer/registry.toml:348-368 declares no config_paths, while the vendor README places user config in `$XDG_CONFIG_HOME/eza` (https://github.com/eza-community/eza/blob/v0.23.5/README.md, line 207); the config policy cannot be applied | stale | proposed |
| installer/registry.toml:358 | eza | drift | installer/registry.toml:358-364 uses github_release on Arch and Fedora, while the vendor INSTALL.md recommends `pacman -S eza` (https://github.com/eza-community/eza/blob/v0.23.5/INSTALL.md, Arch Linux section) and `dnf install eza` (same file, Fedora section), and Arch extra and Fedora rawhide both carry 0.23.5; installer rule step 4 prefers a package manager when it is current enough (.claude/skills/tool-onboarding/SKILL.md, section 4) | stale | proposed |
| installer/registry.toml:520 | starship | drift | `installer/registry.toml:520` declares no `config_paths`, but the vendor reads the user config at `~/.config/starship.toml` (https://starship.rs/config/), so the Uninstall screen has no config row or default config policy as tool-onboarding 4b requires | stale | proposed |
| installer/registry.toml:599 | oh-my-zsh | drift | the entry declares no `paths` and no `remove` (`installer/registry.toml:599-624`), so the Uninstall screen never removes `~/.oh-my-zsh`, which `upstream tools/install.sh:92` creates and `upstream tools/install.sh:565-583` refuses to overwrite; the registry comment justifies skipping only the `~/.zshrc` rename that `upstream tools/uninstall.sh:24-27` performs, which does not cover the framework directory (step 4b: a script declares what it creates in `paths`) | stale | proposed |
| installer/registry.toml:672 | direnv | drift | the entry declares no `config_paths` (`installer/registry.toml:672-699`), but the vendor reads its config from `~/.config/direnv/direnv.toml` (https://direnv.net/man/direnv.toml.1.html), so the Uninstall screen has no config row or default config policy as tool-onboarding 4b requires; the binary removal itself is correct (L1 brew, L2 receipt for the release binaries) | stale | proposed |
| installer/registry.toml:859 | gum | drift | the upstream README Installation section recommends `pacman -S gum` (Arch) and `dnf install gum` (Fedora) before any release asset, https://github.com/charmbracelet/gum#installation, while `installer/registry.toml:859` installs the release asset on arch and fedora; package currency on those distros is unverified (no pacman or dnf query run); the macOS and Linux brew and checksummed asset rows match the vendor's brew line and the downloads that `verify-registry.md:154-157` passed | stale | proposed |
| installer/registry.toml:890 | glow | drift | `installer/registry.toml:890` declares `config_paths = ["~/.config/glow"]` for every OS, but glow resolves its default config directory through go-app-paths (`glow` main.go:436-473, https://raw.githubusercontent.com/charmbracelet/glow/main/main.go), which on darwin uses `/Library/Preferences` under the home directory (go-app-paths v0.2.2 `paths_darwin.go:12,75`, https://raw.githubusercontent.com/muesli/go-app-paths/v0.2.2/paths_darwin.go); the macOS path is therefore `~/Library/Preferences/...`, and the app-name join beneath it is unverified; on Linux `~/.config/glow` matches `main.go:444-445` (XDG_CONFIG_HOME/glow) | stale | proposed |
| installer/registry.toml:892 | glow | drift | the upstream README Installation section lists `pacman -S glow` for Arch, https://github.com/charmbracelet/glow#installation, while `installer/registry.toml:892` installs the release asset on arch; the Fedora and Debian rows use the Charm yum or apt repo in the README, which need a third-party repo and root, so the release asset stays; arch package currency is unverified (no pacman query run); the macOS and Linux asset and brew rows match the downloads `verify-registry.md:146-149` passed | stale | proposed |
| installer/registry.toml:912 | xh | drift | the entry declares no `config_paths` (`installer/registry.toml:912-938`), but `xh --session` writes session files under `config_dir()/sessions` (`src/session.rs:171-173`, https://raw.githubusercontent.com/ducaale/xh/master/src/session.rs), and `config_dir()` resolves to `~/.config/xh` on Linux and to a legacy or XDG path on macOS (`src/utils.rs:77-89`, https://raw.githubusercontent.com/ducaale/xh/master/src/utils.rs); the session format holds auth fields (`src/session.rs:410`), so the default config policy must be stated | stale | proposed |
| installer/registry.toml:922 | xh | drift | the upstream README install table lists `pacman -S xh` for Arch and `sudo apt install xh` for Debian and Ubuntu (https://github.com/ducaale/xh#installation), both distro packages that step 4 ranks above the release asset, while `installer/registry.toml:922` installs the release asset on debian, arch and fedora; the Fedora row is a third-party COPR repo, so the release asset stays there; package currency on Arch and Debian is unverified (no pacman or apt query run); the macOS and brew rows match the README's Homebrew line | stale | proposed |
| installer/registry.toml:949 | difftastic | drift | the upstream manual lists `sudo pacman -S difftastic` for Arch and `sudo dnf install difftastic` for Fedora before the prebuilt binary (https://difftastic.wilfred.me.uk/installation.html), while `installer/registry.toml:949` installs the release asset on arch and fedora; package currency is unverified (no pacman or dnf query run); the macOS and Linux asset rows match the brew line and the downloads that `verify-registry.md:96-99` passed | stale | proposed |
| installer/registry.toml:968 | gitui | drift | the entry declares no `config_paths` (`installer/registry.toml:968-1000`), but the upstream KEY_CONFIG and THEMES pages place user-authored `key_bindings.ron` and `theme.ron` in `~/.config/gitui` on macOS and Linux (https://raw.githubusercontent.com/gitui-org/gitui/master/KEY_CONFIG.md, https://raw.githubusercontent.com/gitui-org/gitui/master/THEMES.md), and the README's diagnostics section writes `gitui.log` under `~/Library/Caches/gitui` (macOS) or `~/.cache/gitui` (Linux) when run with `-l` (https://github.com/gitui-org/gitui#diagnostics); the default config policy is therefore unstated | stale | proposed |
| installer/registry.toml:979 | gitui | drift | the upstream README install list recommends `sudo pacman -S gitui` for Arch and `sudo dnf install gitui` for Fedora (https://github.com/gitui-org/gitui#installation), while `installer/registry.toml:979` installs the release asset on arch and fedora; package currency is unverified (no pacman or dnf query run); the Linux and macOS asset rows match the downloads that `verify-registry.md:142-145` passed, and the brew row matches the README's Homebrew line | stale | proposed |
| installer/registry.toml:1004 | lazydocker | drift | lazydocker is a UI over a running docker environment (README line 43) and the entry carries neither a `requires` edge nor a `# Verified` note for that runtime expectation, which tool-onboarding step 6 requires (`installer/registry.toml:1004-1033`) | stale | proposed |
| installer/registry.toml:1004 | lazydocker | drift | the entry declares no `config_paths`, but the vendor documents the user config at `~/.config/lazydocker/config.yml` (Linux) and `~/Library/Application Support/jesseduffield/lazydocker/config.yml` (macOS), https://raw.githubusercontent.com/jesseduffield/lazydocker/master/docs/Config.md (lines 11-12); `installer/registry.toml:1004-1005` shows the block without it | stale | proposed |
| installer/registry.toml:1059 | docker | drift | the Homebrew formula's Linux caveat says the daemon is a separate formula, `brew install docker-engine` (homebrew-core Formula/d/docker.rb, caveats), and the entry's CLI is not a daemon; the entry has no `requires` edge and no `# Verified` note for that runtime expectation, which tool-onboarding step 6 requires (`installer/registry.toml:1059-1081`) | stale | proposed |
| installer/registry.toml:1074 | docker | drift | Docker's Ubuntu install page lists `docker.io` among the "unofficial packages to uninstall" before installing the official Engine, and its recommended method is the Docker apt repository, https://docs.docker.com/engine/install/ubuntu/ ("Uninstall old versions", "Installation methods"); the entry's apt method is `docker.io` at `installer/registry.toml:1074-1075` | stale | proposed |
| installer/registry.toml:1084 | podman | drift | the vendor page's macOS setup creates a machine with `podman machine init` and `podman machine start` (https://podman.io/docs/installation, "Installing on Mac & Windows"); the entry declares no postinstall, `requires`, or `# Verified` note for that runtime expectation, which tool-onboarding step 6 requires (`installer/registry.toml:1084-1111`) | stale | proposed |
| installer/registry.toml:1105 | podman | drift | the vendor's install page says the Homebrew route is "Not recommended" because it is community-maintained, and points macOS users to the GitHub release pkg installer, https://podman.io/docs/installation ("Installing on Mac & Windows"); the entry's macOS arm64 method is brew (`installer/registry.toml:1105-1107`) and it has no pkg or release method for macOS. The Linux rows follow the page's per-distro package commands ("Installing on Linux") | stale | proposed |
| installer/registry.toml:1115 | colima | drift | the vendor keeps its config and VM data under `$HOME/.colima` (https://github.com/abiosoft/colima docs/FAQ.md lines 124-137) and `colima delete --data` is the vendor's data removal (FAQ.md line 695); the entry declares no `config_paths`, so the Uninstall screen cannot show or offer those paths (`installer/registry.toml:1115-1127`) | stale | proposed |
| installer/registry.toml:1209 | duf | drift | upstream README (https://github.com/muesli/duf (README), Installation) names `dnf install duf` for Fedora, and the host's Fedora package is already duf-0.9.1 (`rpm -qf /usr/bin/duf`), current with latest; step 4 rule 1 prefers that package manager, yet `installer/registry.toml:1209-1210` declares a github_release tarball for fedora and no dnf method | stale | proposed |
| installer/registry.toml:1493 | codex | drift | `installer/registry.toml:1493` says the docs name no `codex update`, but https://developers.openai.com/codex/cli/reference lists `codex update` (Stable, applies an update when the release supports self-update) and the CLI source has an `Update` subcommand, https://github.com/openai/codex/blob/main/codex-rs/cli/src/main.rs | stale | proposed |
| installer/registry.toml:1575 | opencode | drift | `installer/registry.toml:1575` still installs through https://opencode.ai/install, which says "This installer only installs OpenCode 1" and refuses 2.x (https://opencode.ai/install lines 70-75); the v2 installer is https://opencode.ai/v2/install; the brew method `installer/registry.toml:1586` is the tap formula that serves 1.19.5 (https://github.com/anomalyco/homebrew-tap/blob/main/opencode.rb) while homebrew/core opencode serves 2.3.0 and has no conflicts (https://formulae.brew.sh/api/formula/opencode.json); pacman serves 2.2.7 and stays valid | stale | proposed |
| installer/registry.toml:1579 | opencode | drift | `installer/registry.toml:1579` declares only `~/.opencode/bin/opencode`, but the v2 installer also writes `~/.opencode/bin/opencode2` (https://opencode.ai/v2/install lines 345-374) and that file exists on this host; no `remove` recipe, so a 2.x install leaves the opencode2 shim and a running `opencode serve --service` behind | stale | proposed |
| installer/registry.toml:1580 | opencode | drift | `installer/registry.toml:1580` runs `opencode upgrade`, which without `--major` stays on OpenCode 1 (https://github.com/anomalyco/opencode/blob/v1.19.5/packages/opencode/src/cli/cmd/upgrade.ts lines 22, 79, 102); re-running the v2 installer is the 2.x route; not run in a container here, the orchestrator owns containers | stale | proposed |
| installer/registry.toml:1756 | codegraph | drift | `installer/registry.toml:1756` declares no tool-level `config_paths` although codegraph keeps its data in ~/.codegraph (telemetry.json, beta-signup.json, daemons/, and versions/ plus current after `codegraph upgrade`, https://raw.githubusercontent.com/colbymchenry/codegraph/main/install.sh lines 21 and 79-87); the unregister hook runs `codegraph uninstall --keep-cli` (`installer/postinstall.py:204`) and the receipt proves only the installer's own link and opt dir, so after a vendor self-upgrade `installer/uninstall.py:402` finds no proven executable and unregisters nothing | stale | proposed |
| installer/registry.toml:1827 | graphify | drift | installer/registry.toml:1827-1828 says every host install is project/CWD-scoped, but the README says a bare `graphify install` registers the skill in the user profile (https://pypi.org/project/graphifyy/, lines 205-213); graphifyy 0.9.108 graphify/install.py:1106-1108 writes ~/.claude/skills/graphify/SKILL.md and registers it in ~/.claude/CLAUDE.md. The entry declares `paths` none, so removal (uv tool uninstall) leaves those files | stale | proposed |
| installer/registry.toml:2196 | bun | drift | the script appends a `# bun` PATH/BUN_INSTALL block to the user's shell config (`>>"$zsh_config"` at https://bun.sh/install:246; `>>"$bash_config"` at https://bun.sh/install:293, bash configs listed at lines 269-278), but `paths` declares only `~/.bun/bin/bun` and `~/.bun/bin/bunx` (`installer/registry.toml:2196`) and the `# Verified` comment (`installer/registry.toml:2191-2195`) does not record the rc edit, which the installer's rule requires for anything else a script creates; the vendor's own removal (https://bun.sh/docs/installation, "Uninstall") is `rm -rf ~/.bun`, which the entry deliberately does not run (its comment at `installer/registry.toml:2192` keeps the tree out of `paths`) | stale | proposed |
| installer/registry.toml:2377 | vale | drift | the entry records no config_paths or data paths (installer/registry.toml:2377-2385), which tool-onboarding step 4b requires per tool (.claude/skills/tool-onboarding/SKILL.md, section 4b); v3.27.0 `vale sync` downloads models and grammars at runtime (https://github.com/vale-cli/vale/releases/tag/v3.27.0), and where they land is unverified here, so the removal recipe cannot account for them; the receipt of the release binary's paths is covered by verify-registry.md:226-229 | stale | proposed |
| installer/registry.toml:3194 | pi | drift | `installer/registry.toml:3194` to `installer/registry.toml:3210` declare no `config_paths` for `~/.pi` (agent settings, `auth.json`, `sessions`, `mcp.json` live there, https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/mcp.md) and no remove recipe, and the host_setup row of tool-onboarding step 4b asks for an explicit recipe; removal on this host (bun global) is also not derivable because `installer/ownership.py:135` maps only `pnpm` | stale | proposed |
| installer/registry.toml:3201 | pi | drift | `installer/registry.toml:3201` and `installer/registry.toml:3204` describe a pnpm host-setup handoff verified against "latest 1.5.0" and an "interactive" setup, while the vendor README now recommends `curl -fsSL https://pi.dev/install.sh \\| sh` (managed install, pinned dependencies, `pi update`) or `npm install -g --ignore-scripts`, and npm latest is 1.5.2, https://github.com/earendil-works/pi#getting-started | stale | proposed |
| installer/registry.toml:3250 | drawio-desktop | drift | the macOS app methods pin 32.6.1 (`installer/registry.toml:3250`, `installer/registry.toml:3260`) while v32.6.10 is the stable release, `.planning/audits/catalog/2026-11-13/verify-registry.md:5` and `.planning/audits/catalog/2026-11-13/verify-registry.md:6`, https://api.github.com/repos/jgraph/drawio-desktop/releases/latest; Linux AppImage methods are ok: `drawio-x86_64-32.6.10.AppImage` and `drawio-arm64-32.6.10.AppImage` exist with the same names and a listed digest, https://github.com/jgraph/drawio-desktop/releases/download/v32.6.10/Files-SHA256-Hashes.txt, and are recorded in `.planning/audits/catalog/2026-11-13/verify-registry.md:110` and `.planning/audits/catalog/2026-11-13/verify-registry.md:111` | stale | proposed |
| installer/versions.py:211 | zip | drift | `zip --version` prints the copyright line "1990-2008" first; extract_observed_version (installer/versions.py:211) reads those years, not "Zip 3.0" on line 2 | stale | proposed |
