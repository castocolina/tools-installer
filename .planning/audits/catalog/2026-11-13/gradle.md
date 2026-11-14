# gradle - catalog audit 2026-11-13

## Versions
- pinned: unpinned (sdkman)
- verified: 2026-10-13
- installed: 9.9.1 (`gradle --version`, read by `facts`)
- latest: 9.9.1 (vendor current, https://services.gradle.org/versions/current, buildTime 2026-11-10)
- latest: 9.9.1 (GitHub releases/latest, https://api.github.com/repos/gradle/gradle/releases/latest, tag v9.9.1, published 2026-11-10)
- latest: 9.9.1 (SDKMAN default candidate, https://api.sdkman.io/2/candidates/default/gradle)
- note: installed equals latest on all three sources, so the short path applies

## Changelog
- none: installed 9.9.1 equals latest 9.9.1, so there is no install, update, removal, config or MCP note between them

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the vendor's install guide names SDKMAN as a package manager and says "Gradle is deployed and maintained by SDKMAN!" with `sdk install gradle`, https://docs.gradle.org/current/userguide/installation.html (Linux and macOS sections); the same guide covers Linux, macOS and Windows through WSL; `requires = ["sdkman"]` (registry.toml:2064) follows `.claude/skills/tool-onboarding/SKILL.md:86` |
| update argv | ok | the entry declares no update argv (facts: update none); the installer hands SDKMAN-owned upgrades to the user as `sdk upgrade {candidate}` (installer/update.py:124-126, `_SDKMAN_DETAIL`), and SDKMAN documents `sdk upgrade <candidate>` (https://sdkman.io/usage, Upgrade Version(s)); the vendor guide directs project upgrades through the Gradle Wrapper and says nothing about the global binary (unverified) |
| removal recipe and paths | drift | the candidate is removed by the manager (`sdk uninstall gradle <version>`, the form shown at https://sdkman.io/usage), and `.claude/skills/tool-onboarding/SKILL.md:106` says sdkman removal derives from the manager (L1); but MANAGER_UNINSTALL_ARGV has no `sdkman` key (installer/uninstall.py:111-117), so `_manager_argv` returns nothing for this kind (installer/uninstall.py:332-333); container check not run in this batch |
| tuning keys | n/a | reason: the entry declares no tuning keys and no post_install action (facts: tuning none, post_install none) |
| postinstall hook | ok | the entry declares no postinstall (registry.toml:2055-2067) and `requires = ["sdkman"]` carries the only edge, matching the tree at `.claude/skills/tool-onboarding/SKILL.md:164` |

## Proposed changes
- none for this entry beyond the sdkman removal argv proposed in the java report, which covers this kind (`installer/uninstall.py` MANAGER_UNINSTALL_ARGV); risk: medium; evidence: https://sdkman.io/usage (uninstall example)

<!-- catalog-audit:complete -->
