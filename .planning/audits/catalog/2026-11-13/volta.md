# volta - catalog audit 2026-11-13

## Versions
- pinned: unpinned (script, brew)
- verified: 2026-11-04
- installed: 2.0.2 (~/.volta/bin/volta --version, facts block)
- latest: 2.0.2 (GitHub releases/latest, https://api.github.com/repos/volta-cli/volta/releases/latest)
- latest: 2.0.2 (brew formula, https://formulae.brew.sh/api/formula/volta.json)

## Changelog
- README: "Volta is unmaintained" and "We recommend migrating to mise" for new installs (https://raw.githubusercontent.com/volta-cli/volta/main/README.md, line 21; touches install)
- no release note between 2.0.2 and 2.0.2 touches install, update, removal, config or MCP (https://github.com/volta-cli/volta/releases/tag/v2.0.2 lists dependency and header changes only)

## Checks
| check | status | source |
|---|---|---|
| install method | drift | the vendor README (https://raw.githubusercontent.com/volta-cli/volta/main/README.md line 21) no longer recommends Volta for new installs and names mise instead; the entry still installs Volta through https://get.volta.sh and the brew formula (installer/registry.toml:2263-2294), so the mechanics still work but the method is not the vendor's recommendation |
| update argv | ok | re-running the install script is the upgrade path: https://get.volta.sh reads the previous version at line 111 before reinstalling; Volta has no upgrade subcommand (https://raw.githubusercontent.com/volta-cli/volta/main/src/command/mod.rs); brew upgrades the formula; installer/registry.toml:2263-2294 declares no update, which matches |
| removal recipe and paths | ok | the release tarball https://github.com/volta-cli/volta/releases/download/v2.0.2/volta-2.0.2-linux.tar.gz lists volta, volta-shim and volta-migrate; https://get.volta.sh line 345 extracts them into the bin directory; the paths at installer/registry.toml:2295-2305 match; the node, npm, npx, pnpm, yarn and yarnpkg shims come from `volta --version` (https://get.volta.sh line 230), which this audit did not run (unverified here); the profile lines that `volta setup` writes (https://raw.githubusercontent.com/volta-cli/volta/main/src/command/setup.rs lines 45-82) are not removed by the recipe, as the registry comment at installer/registry.toml:2291-2294 already records |
| tuning keys | n/a | reason: the entry declares no tuning keys; its only post_install action is source_shell_init (installer/registry.toml:2267) |
| postinstall hook | ok | no Tool.postinstall is declared (installer/registry.toml:2263-2294); the shell-init step is a post_install action, the first branch of "Postinstall-per-harness classification" at .claude/architecture.md:308 |

## Proposed changes
- keep Volta with a re-dated note, or replace it with mise through tool-onboarding; this is the user's decision because the vendor now recommends mise; risk: medium; evidence: https://raw.githubusercontent.com/volta-cli/volta/main/README.md line 21

<!-- catalog-audit:complete -->
