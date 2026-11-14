# java - catalog audit 2026-11-13

## Versions
- pinned: unpinned (sdkman)
- verified: 2026-09-06
- installed: 27.0.1.0.3 (`java --version`, read by `facts`)
- latest: 25.0.5.0+8-tem (SDKMAN default candidate, https://api.sdkman.io/2/candidates/default/java)
- latest: 27 GA 2026/09/15, feature line (OpenJDK, https://openjdk.org/projects/jdk/27/ "Build 2026/09/15 General Availability")
- latest: jdk-27.0.1.0.2+1 published 2026-10-24 (newest Temurin 27 GitHub release, https://api.github.com/repos/adoptium/temurin27-binaries/releases/latest)
- note: major split: SDKMAN's default candidate is on the 25 line while OpenJDK's GA line is 27; the installed 27.0.1.0.3 is newer than the Temurin 27 tag read, and which build it is remains unverified
- note: the SDKMAN per-platform version list endpoint (https://api.sdkman.io/2/candidates/java/<platform>/versions/list) returned HTTP 400 for every platform token tried, so per-platform candidate availability is unverified

## Changelog
- no install, update, removal, config or MCP note read; the JDK 27 release notes were not read in this batch (unverified)

## Checks
| check | status | source |
|---|---|---|
| install method | unknown | reason: unverified per platform; the default candidate resolves on https://api.sdkman.io/2/candidates/default/java, but the per-platform list endpoint returned HTTP 400 for every platform token tried; the method kind itself (sdkman with `requires = ["sdkman"]`, registry.toml:2016-2019) follows `.claude/skills/tool-onboarding/SKILL.md:86` |
| update argv | ok | the entry declares no update argv; the installer hands the SDKMAN-owned upgrade to the user as `sdk upgrade {candidate}` (installer/update.py:124-126, `_SDKMAN_DETAIL`), and the vendor upgrade is `sdk upgrade java` (https://sdkman.io/usage, Upgrade Version(s)); the facts line "the installer re-runs the method" is not what update.py says for SDKMAN-owned tools |
| removal recipe and paths | drift | the candidate is removed by the manager (`sdk uninstall java <version>`, the form shown at https://sdkman.io/usage in its uninstall example), and `.claude/skills/tool-onboarding/SKILL.md:106` says sdkman removal derives from the manager (L1); but MANAGER_UNINSTALL_ARGV has no `sdkman` key (installer/uninstall.py:111-117), so `_manager_argv` returns nothing for this kind (installer/uninstall.py:332-333); container check not run in this batch |
| tuning keys | n/a | reason: the entry declares no tuning keys and no post_install action (facts: tuning none, post_install none) |
| postinstall hook | ok | the entry declares no postinstall (registry.toml:2007-2019); the default-version prompt that `sdk install` raises (https://sdkman.io/usage, the "Do you want java ... to be set as default?" example) is covered by `sdkman_auto_answer` (https://sdkman.io/usage, Configuration) only on an installer-bootstrapped SDKMAN, per the brownfield caveat in registry.toml:1940-1958; that caveat is a risk, not drift |

## Proposed changes
- give the `sdkman` kind an L1 removal argv (`sdk uninstall java <version>`) in `installer/uninstall.py` MANAGER_UNINSTALL_ARGV, or record the removal as a SDKMAN hand-off message like `_SDKMAN_DETAIL`; risk: medium; evidence: https://sdkman.io/usage (uninstall example)

<!-- catalog-audit:complete -->
