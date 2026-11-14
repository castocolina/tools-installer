# groovy - catalog audit 2026-11-13

## Versions
- pinned: unpinned (sdkman)
- verified: 2026-10-13
- installed: 6.0.0 (`groovy --version`, read by `facts`)
- latest: 6.0.0 (official download page, https://groovy.apache.org/download.html, "Download 6.0.0")
- latest: 6.0.0 (SDKMAN default candidate, https://api.sdkman.io/2/candidates/default/groovy)
- note: apache/groovy has no GitHub releases (the releases list is empty); the newest tag read is GROOVY_6_0_0 at https://api.github.com/repos/apache/groovy/tags

## Changelog
- none: installed 6.0.0 equals latest 6.0.0, so there is no install, update, removal, config or MCP note between them

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the SDKMAN default candidate is 6.0.0 (https://api.sdkman.io/2/candidates/default/groovy), the same as the vendor's download (https://groovy.apache.org/download.html); the vendor page does not name SDKMAN, so the choice follows `.claude/skills/tool-onboarding/SKILL.md:86` (a language-ecosystem manager with the manager in `requires`, registry.toml:2032-2036) |
| update argv | ok | the entry declares no update argv (facts: update none); the installer hands SDKMAN-owned upgrades to the user as `sdk upgrade {candidate}` (installer/update.py:124-126, `_SDKMAN_DETAIL`), and the vendor's upgrade is `sdk upgrade <candidate>` (https://sdkman.io/usage, Upgrade Version(s)) |
| removal recipe and paths | drift | the candidate is removed by the manager (`sdk uninstall groovy <version>`, the form shown at https://sdkman.io/usage), and `.claude/skills/tool-onboarding/SKILL.md:106` says sdkman removal derives from the manager (L1); but MANAGER_UNINSTALL_ARGV has no `sdkman` key (installer/uninstall.py:111-117), so `_manager_argv` returns nothing for this kind (installer/uninstall.py:332-333); container check not run in this batch |
| tuning keys | n/a | reason: the entry declares no tuning keys and no post_install action (facts: tuning none, post_install none) |
| postinstall hook | ok | the entry declares no postinstall (registry.toml:2023-2036) and `requires = ["sdkman"]` carries the only edge, matching the tree at `.claude/skills/tool-onboarding/SKILL.md:164` |

## Proposed changes
- none beyond the sdkman removal argv proposed for the `java` entry, which covers this kind (`installer/uninstall.py` MANAGER_UNINSTALL_ARGV); risk: medium; evidence: https://sdkman.io/usage (uninstall example)

<!-- catalog-audit:complete -->
