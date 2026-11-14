# sdkman - catalog audit 2026-11-13

## Versions
- pinned: unpinned (script)
- verified: 2026-11-13
- installed: 5.23.0 (`~/.sdkman/var/version`, read by `facts`)
- latest: 5.24.0 (GitHub releases/latest, https://api.github.com/repos/sdkman/sdkman-cli/releases/latest, published 2026-10-24)
- note: registry.toml:1976 records 5.23.2 read on 2026-10-13; today's probe reads 5.23.0; which state is current is unverified
- note: GitHub's rolling `latest` pre-release tag is not a version and is ignored

## Changelog
- 5.23.1 (2026-09-19): PATH entry replacement regex made more expressive (#1562), a shell config edit, https://github.com/sdkman/sdkman-cli/releases/tag/5.23.1
- 5.23.2 (2026-10-06): install path avoids bash 4-only uppercase expansion so it runs on macOS bash 3.2, https://github.com/sdkman/sdkman-cli/releases/tag/5.23.2
- 5.24.0 (2026-10-24): no install, update, removal, config or MCP note; help routing only, https://github.com/sdkman/sdkman-cli/releases/tag/5.24.0

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the documented CI-mode bootstrap is `curl -s "https://get.sdkman.io?ci=true"` piped to bash, https://sdkman.io/install (CI Mode); registry.toml:1972 uses the same URL |
| update argv | unknown | reason: unverified whether `sdk selfupdate` still runs after `?ci=true` sets sdkman_selfupdate_feature=false; the command itself is documented at https://sdkman.io/usage (Self-Update); a run needs a container, which this batch does not run |
| removal recipe and paths | drift | the script method declares no `paths` and no `remove` (registry.toml:1970-1983, comment at 1980-1982), but `.claude/skills/tool-onboarding/SKILL.md:109` requires `paths` for a `script` method; the vendor uninstall is `rm -rf ~/.sdkman` plus removing the shell init snippet by hand, https://sdkman.io/install (Uninstallation); container check not run in this batch |
| tuning keys | ok | the entry declares no tuning; `?ci=true` sets sdkman_auto_answer, sdkman_colour_enable=false and sdkman_selfupdate_feature=false, https://sdkman.io/install (CI Mode); sdkman_auto_answer and sdkman_selfupdate_feature are still listed in https://sdkman.io/usage (Configuration) and none is marked renamed or deprecated |
| postinstall hook | ok | the entry declares no postinstall (registry.toml:1970-1983), matching the tree at `.claude/skills/tool-onboarding/SKILL.md:164` with no hook; zip and unzip are carried by `requires` (registry.toml:1969), matching the prerequisites in https://sdkman.io/install (bash, zip, unzip, curl); the rc snippet is covered under removal |

## Proposed changes
- declare the install footprint on the script method: `paths` for the directory the installer owns and `config_paths` for ~/.sdkman/etc/config, per `.claude/skills/tool-onboarding/SKILL.md:98` (step 4b); a removal of ~/.sdkman deletes every installed JDK, so run a container check first; risk: medium; evidence: https://sdkman.io/install (Uninstallation)
- correct the comment at registry.toml:1980-1982: the upstream docs describe the shell init snippet as something the install adds (`?rcupdate=false` skips it) and the uninstall removes, so "the rc init snippet is the user's, not ours" does not match upstream; risk: low; evidence: https://sdkman.io/install (Install without modifying shell config; Uninstallation)

<!-- catalog-audit:complete -->
