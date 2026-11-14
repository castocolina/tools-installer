# graphify - catalog audit 2026-11-13

## Versions
- pinned: none (the uv-tool method is unpinned; uv installs the latest graphifyy)
- verified: 2026-10-14
- installed: 0.9.103 (`graphify --version`, from facts)
- latest: 0.9.108 (PyPI, https://pypi.org/pypi/graphifyy/json, uploaded 2026-11-12)
- latest: 0.9.108 (GitHub releases, https://api.github.com/repos/Graphify-Labs/graphify/releases, tag v0.9.108, 2026-11-12)
- note: the PyPI distribution is `graphifyy` (double y), matching the registry's pypi_pkg

## Changelog
- 0.9.106 (2026-11-10): `requires-python` is capped to `>=3.10,<3.15`, so a fresh `uv tool install graphifyy` no longer selects Python 3.15 (https://api.github.com/repos/Graphify-Labs/graphify/releases, tag v0.9.106)
- 0.9.103 (2026-11-05): uninstall removes the global skill registration that graphify wrote (https://api.github.com/repos/Graphify-Labs/graphify/releases, tag v0.9.103)
- 0.9.104 to 0.9.108 contain no install, update, removal or config note beyond those above (same URL)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | `uv tool install graphifyy` is the first install command in https://pypi.org/project/graphifyy/ (README, line 200); the registry's uv-tool method with pypi_pkg `graphifyy` matches (installer/registry.toml:1845-1847) |
| update argv | ok | the uv-tool method owns the package, so the registry declares no update argv (installer/registry.toml:1845-1847); the README names no separate upgrade command (https://pypi.org/project/graphifyy/, lines 200-202) |
| removal recipe and paths | drift | installer/registry.toml:1827-1828 says every host install is project/CWD-scoped, but the README says a bare `graphify install` registers the skill in the user profile (https://pypi.org/project/graphifyy/, lines 205-213); graphifyy 0.9.108 graphify/install.py:1106-1108 writes ~/.claude/skills/graphify/SKILL.md and registers it in ~/.claude/CLAUDE.md. The entry declares `paths` none, so removal (uv tool uninstall) leaves those files |
| tuning keys | n/a | reason: the entry declares no tuning key and no post_install action (installer/registry.toml:1816-1847) |
| postinstall hook | ok | the entry declares no postinstall hook; the registry comment says the postinstall was removed (installer/registry.toml:1827); graphify's host registration is a user step (https://pypi.org/project/graphifyy/, line 205) |

## Proposed changes
- correct the `# Verified` comment: a bare `graphify install` is user-global, and `--project` is the project-scoped form (https://pypi.org/project/graphifyy/, lines 205-213); risk: low; evidence: https://pypi.org/project/graphifyy/
- decide whether the removal flow should run `graphify uninstall` (README line 318 names it) before `uv tool uninstall`, or document that host registrations stay; risk: medium; evidence: graphifyy 0.9.103 changelog, https://api.github.com/repos/Graphify-Labs/graphify/releases

<!-- catalog-audit:complete -->
