# vale - catalog audit 2026-11-13

## Versions
- pinned: unpinned (github_release, brew)
- verified: 2026-11-03
- installed: none (vale is not on this host, facts block)
- latest: v3.27.0 (GitHub releases/latest, published 2026-11-12, https://github.com/vale-cli/vale/releases/tag/v3.27.0)
- latest: 3.27.0 (brew formula, https://formulae.brew.sh/api/formula/vale.json)
- note: the repository is now vale-cli/vale; https://api.github.com/repos/errata-ai/vale still answers with full_name vale-cli/vale, so the registry's old slug resolves only through the GitHub redirect

## Changelog
- v3.27.0: "run `vale sync` after upgrading" when linting source code; `vale sync` installs the language models and the tree-sitter grammars, and the release binaries no longer need CGo (https://github.com/vale-cli/vale/releases/tag/v3.27.0; touches install)

## Checks
| check | status | source |
|---|---|---|
| install method | drift | the registry names errata-ai/vale (installer/registry.toml:2389 and :2397), but https://api.github.com/repos/errata-ai/vale reports full_name vale-cli/vale and https://formulae.brew.sh/api/formula/vale.json points at github.com/vale-cli/vale; the downloads still resolve (.planning/audits/catalog/2026-11-13/verify-registry.md:226-229, Passed), so this is a slug drift, not a broken download; whether the redirect stays is unverified |
| update argv | ok | the entry declares no update, so re-running the release method is the upgrade (installer/registry.toml:2377-2404); the v3.27.0 notes name no self-update command (https://github.com/vale-cli/vale/releases/tag/v3.27.0) |
| removal recipe and paths | drift | the entry records no config_paths or data paths (installer/registry.toml:2377-2385), which tool-onboarding step 4b requires per tool (.claude/skills/tool-onboarding/SKILL.md, section 4b); v3.27.0 `vale sync` downloads models and grammars at runtime (https://github.com/vale-cli/vale/releases/tag/v3.27.0), and where they land is unverified here, so the removal recipe cannot account for them; the receipt of the release binary's paths is covered by verify-registry.md:226-229 |
| tuning keys | n/a | reason: the entry declares no tuning keys and no post_install action (installer/registry.toml:2377-2385) |
| postinstall hook | ok | no Tool.postinstall is declared (installer/registry.toml:2377-2404), which is the None branch of "Postinstall-per-harness classification" at .claude/architecture.md:331 |

## Proposed changes
- switch both stanzas to repo = "vale-cli/vale" at installer/registry.toml:2389 and :2397; risk: low; evidence: https://api.github.com/repos/errata-ai/vale
- record the config and data paths that `vale sync` writes, after a container check of that step; risk: medium; evidence: https://github.com/vale-cli/vale/releases/tag/v3.27.0

<!-- catalog-audit:complete -->
