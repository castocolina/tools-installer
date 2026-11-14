# springbootcli - catalog audit 2026-11-13

## Versions
- pinned: unpinned (sdkman)
- verified: 2026-10-13
- installed: v4.1.0 (`spring --version`, read by `facts`)
- latest: 4.1.2 (GitHub releases/latest, https://api.github.com/repos/spring-projects/spring-boot/releases/latest, tag v4.1.2, published 2026-10-22)
- latest: 4.1.2 (vendor CLI distribution, https://docs.spring.io/spring-boot/installing.html, "spring-boot-cli-4.1.2-bin.zip")
- latest: 4.1.0 (SDKMAN default candidate, https://api.sdkman.io/2/candidates/default/springboot)
- note: the SDKMAN default lags the vendor's stable 4.1.2 by one patch line; the installed 4.1.0 equals the SDKMAN default
- note: GitHub lists v4.2.0-RC2 (prerelease, 2026-11-05); it is not a stable release and is not used as latest

## Changelog
- 4.1.1 (2026-08-20) and 4.1.2 (2026-10-22): a keyword scan of the release notes for cli, sdkman and homebrew found no CLI note; the notes were not read line by line (unverified beyond the scan), https://github.com/spring-projects/spring-boot/releases/tag/v4.1.2

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the vendor's own install section is "Installation with SDKMAN!" with `sdk install springboot`, https://docs.spring.io/spring-boot/installing.html; the method is the one the vendor documents, and `requires = ["sdkman"]` (registry.toml:2050-2056) follows `.claude/skills/tool-onboarding/SKILL.md:86` |
| update argv | ok | the entry declares no update argv (facts: update none); the installer hands SDKMAN-owned upgrades to the user as `sdk upgrade {candidate}` (installer/update.py:124-126, `_SDKMAN_DETAIL`), and SDKMAN documents `sdk upgrade springboot` (https://sdkman.io/usage, Upgrade Version(s)) |
| removal recipe and paths | drift | the candidate is removed by the manager (`sdk uninstall springboot <version>`, the form shown at https://sdkman.io/usage), and `.claude/skills/tool-onboarding/SKILL.md:106` says sdkman removal derives from the manager (L1); but MANAGER_UNINSTALL_ARGV has no `sdkman` key (installer/uninstall.py:111-117), so `_manager_argv` returns nothing for this kind (installer/uninstall.py:332-333); the vendor docs name no uninstall of their own (unverified); container check not run in this batch |
| tuning keys | n/a | reason: the entry declares no tuning keys and no post_install action (facts: tuning none, post_install none) |
| postinstall hook | ok | the entry declares no postinstall (registry.toml:2041-2056) and `requires = ["sdkman"]` carries the only edge, matching the tree at `.claude/skills/tool-onboarding/SKILL.md:164` |

## Proposed changes
- none for this entry beyond the sdkman removal argv proposed in the java report, which covers this kind (`installer/uninstall.py` MANAGER_UNINSTALL_ARGV); risk: medium; evidence: https://sdkman.io/usage (uninstall example)

<!-- catalog-audit:complete -->
