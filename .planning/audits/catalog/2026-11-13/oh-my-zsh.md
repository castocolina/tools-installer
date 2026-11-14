# oh-my-zsh - catalog audit 2026-11-13

## Versions
- pinned: unpinned (script)
- verified: 2026-11-04
- installed: not installed (facts: `installed: not installed`)
- latest: master 6010fb6 (2026-11-09, https://api.github.com/repos/ohmyzsh/ohmyzsh/commits?per_page=1)
- note: no GitHub release exists (https://api.github.com/repos/ohmyzsh/ohmyzsh/releases/latest returns 404); master is the only channel, so latest is a commit

## Changelog
- be8da5c (2026-09-11) adds an update cooldown, default 0 days, so `tools/upgrade.sh` with no flag behaves as before; config is `zstyle ':omz:update' cooldown` (https://github.com/ohmyzsh/ohmyzsh/commit/be8da5c, `tools/upgrade.sh:27`, README.md:506-511)
- f5d571c (2026-11-09) prints a star-us line at the end of `tools/install.sh`; it is output only and asks nothing (https://github.com/ohmyzsh/ohmyzsh/commit/f5d571c, `tools/install.sh:531`)
- no uninstall.sh commit since 2026-09-06 (https://api.github.com/repos/ohmyzsh/ohmyzsh/commits?path=tools/uninstall.sh)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the vendor's README recommends `sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"` and lists no package manager (README.md:104-106); the registry uses the same script URL with the env the script reads (`upstream tools/install.sh:28-30`, `upstream tools/install.sh:100-102`), and the script is the only vendor method, so step 4 rule 4 applies |
| update argv | ok | the registry argv `{omz_root}/tools/upgrade.sh` matches the README's documented update path (`omz update` runs `tools/upgrade.sh`, README.md:514-518); `upstream tools/upgrade.sh:1` is `#!/usr/bin/env zsh` and `upstream tools/upgrade.sh:19-23` derives `ZSH` from its own location, so the argv works directly |
| removal recipe and paths | drift | the entry declares no `paths` and no `remove` (`installer/registry.toml:599-624`), so the Uninstall screen never removes `~/.oh-my-zsh`, which `upstream tools/install.sh:92` creates and `upstream tools/install.sh:565-583` refuses to overwrite; the registry comment justifies skipping only the `~/.zshrc` rename that `upstream tools/uninstall.sh:24-27` performs, which does not cover the framework directory (step 4b: a script declares what it creates in `paths`) |
| tuning keys | ok | the keys the post_install actions write are `ZSH_THEME` and `plugins=(...)` (README.md:189, README.md:154), both still documented upstream and not deprecated; the entry declares no tuning keys of its own (`tuning: none`), and the writes are installer post_install actions (`installer/post_install.py:378`, `_tune_omz_plugins`) |
| postinstall hook | ok | the entry declares no `postinstall` hook (`installer/registry.toml:599-624`); its install-time work is the named post_install actions `set_login_shell`, `set_omz_theme`, `set_omz_plugins` (`installer/registry.toml:609`), which is the install-tuning branch of the architecture tree |

## Proposed changes
- declare `paths = ["~/.oh-my-zsh"]` on the script method so Uninstall removes the framework directory, keeping `~/.zshrc` with the rc ledger and the user's `custom/` dir under the keep policy, after a container check; risk: medium; evidence: `upstream tools/install.sh:92`, `upstream tools/uninstall.sh:21`

<!-- catalog-audit:complete -->
