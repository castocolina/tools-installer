# zsh - catalog audit 2026-11-13

## Versions
- pinned: unpinned (dnf, apt, pacman, brew)
- verified: 2026-09-06
- installed: 5.9.2 (`zsh --version`)
- latest: 5.9.2 (upstream tag zsh-5.9.2, `gh api repos/zsh-users/zsh/git/refs/tags/zsh-5.9.2`)
- latest: 5.9.2-4.fc46 (Fedora rawhide, https://mdapi.fedoraproject.org/rawhide/pkg/zsh)
- latest: 5.9.2-1 (Debian, https://sources.debian.org/api/src/zsh/)
- latest: 5.9.2-1 (Arch extra, https://archlinux.org/packages/search/json/?name=zsh)
- latest: 5.9.2 (Homebrew formula, https://formulae.brew.sh/api/formula/zsh.json)

## Changelog
- no install, update, removal, config or MCP note between 5.9.2 and 5.9.2 (NEWS at tag zsh-5.9.2, `gh api repos/zsh-users/zsh/contents/NEWS?ref=zsh-5.9.2`)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the four package-manager methods are the first choice in tool-onboarding step 4 (`installer/registry.toml:572-583`, dnf, apt, pacman, brew); each manager's current package matches 5.9.2 (fedora rawhide, debian, arch extra, homebrew URLs in Versions); the zsh.org index is archive-only and names no install method (https://www.zsh.org/) |
| update argv | ok | `update: none` (facts): the owning package manager upgrades zsh, so no argv is declared; the step 4b table makes these methods removal-by-manager (`.claude/skills/tool-onboarding/SKILL.md` step 4b) |
| removal recipe and paths | ok | removal is the manager's own remove (L1) for all four methods (`installer/registry.toml:572-583`); `paths: none` is correct because nothing is receipt-proven; `~/.zshrc` is not a zsh receipt; the installer's own writes to it go through `zshrc_path` (`installer/post_install.py:361`), not through zsh's removal |
| tuning keys | n/a | reason: the entry declares no tuning keys and no `post_install` action (`installer/registry.toml:561-571`) |
| postinstall hook | ok | the entry declares no `postinstall` hook and no host_setup (`installer/registry.toml:561-571`), so the classification tree from architecture.md ends at none |

## Proposed changes
- none

<!-- catalog-audit:complete -->
